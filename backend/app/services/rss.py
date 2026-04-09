"""RSS connector — polls Miniflux for articles and ingests them as entries."""
import asyncio
import json
import logging
import re
from datetime import datetime, date, timedelta, timezone
from html import unescape

import httpx
from sqlalchemy import select, text as sa_text

from ..core.config import settings
from ..core.database import SessionLocal as AsyncSessionLocal
from ..core.models import Entry, Chunk, Setting
from ..services.embeddings import embed, chunk_text
from ..services.claude import extract_entities, generate_digest_summary
from ..services.entities import link_entities_to_entry

logger = logging.getLogger("big-brain.rss")

_SETTINGS_KEY = "rss_last_poll_timestamp"


def _strip_html(html: str) -> str:
    """Convert HTML to plain text by stripping tags and normalizing whitespace."""
    # Remove style and script blocks entirely
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Convert common block elements to newlines
    text = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities
    text = unescape(text)
    # Normalize whitespace: collapse runs of spaces (but preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
_DIGEST_DATE_KEY = "rss_last_digest_date"
_DIGEST_CHECK_INTERVAL = 900  # 15 minutes


# ---------------------------------------------------------------------------
# Miniflux HTTP helpers
# ---------------------------------------------------------------------------

def _miniflux_headers() -> dict:
    return {"X-Auth-Token": settings.miniflux_api_key}


def _miniflux_url(path: str) -> str:
    return f"{settings.miniflux_url.rstrip('/')}/v1{path}"


async def _fetch_entries_since(ts: datetime) -> list[dict]:
    """Fetch all Miniflux entries published after *ts* (paginated)."""
    unix_ts = int(ts.timestamp())
    all_entries: list[dict] = []
    offset = 0
    limit = 100

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                _miniflux_url("/entries"),
                headers=_miniflux_headers(),
                params={
                    "after": unix_ts,
                    "order": "published_at",
                    "direction": "asc",
                    "limit": limit,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("entries", [])
            all_entries.extend(entries)
            if len(entries) < limit:
                break
            offset += limit

    return all_entries


async def _fetch_feeds() -> dict[int, dict]:
    """Return a map of feed_id -> {title, feed_url, category_title}."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            _miniflux_url("/feeds"),
            headers=_miniflux_headers(),
        )
        resp.raise_for_status()
    feeds = {}
    for f in resp.json():
        feeds[f["id"]] = {
            "title": f.get("title", ""),
            "feed_url": f.get("feed_url", ""),
            "category_title": f.get("category", {}).get("title", ""),
        }
    return feeds


# ---------------------------------------------------------------------------
# Settings helpers (last poll timestamp)
# ---------------------------------------------------------------------------

async def _get_last_poll_ts() -> datetime | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting).where(Setting.key == _SETTINGS_KEY))
        row = result.scalar_one_or_none()
        if row:
            return datetime.fromisoformat(row.value["timestamp"])
    return None


async def _set_last_poll_ts(ts: datetime) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        await db.execute(
            pg_insert(Setting)
            .values(key=_SETTINGS_KEY, value={"timestamp": ts.isoformat()})
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": {"timestamp": ts.isoformat()}},
            )
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Article ingestion
# ---------------------------------------------------------------------------

async def _is_duplicate(miniflux_entry_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_text(
                "SELECT 1 FROM entries WHERE meta->>'miniflux_entry_id' = :mid "
                "AND source_type = 'rss' LIMIT 1"
            ),
            {"mid": str(miniflux_entry_id)},
        )
        return result.scalar_one_or_none() is not None


async def _ingest_article(article: dict, feed_info: dict) -> int | None:
    """Ingest a single Miniflux article. Returns the new entry ID, or None if skipped."""
    miniflux_id = article["id"]

    if await _is_duplicate(miniflux_id):
        logger.debug("Article %d already ingested, skipping", miniflux_id)
        return None

    title = article.get("title", "Untitled")
    content = article.get("content", "")
    # Miniflux returns HTML — strip to plain text
    raw_text = _strip_html(content)
    if not raw_text:
        logger.warning("Article %d has no content, skipping", miniflux_id)
        return None

    category = feed_info.get("category_title", "")
    tags = [category.lower()] if category else []

    meta = {
        "feed_name": feed_info.get("title", ""),
        "feed_url": feed_info.get("feed_url", ""),
        "feed_category": category,
        "article_url": article.get("url", ""),
        "miniflux_entry_id": miniflux_id,
        "published_at": article.get("published_at", ""),
        "author": article.get("author", ""),
    }

    # Embed (skip enrich_entry — we keep the feed title, not a Claude-generated one)
    vec = embed(raw_text)

    async with AsyncSessionLocal() as db:
        entry = Entry(
            title=title,
            source_type="rss",
            raw_text=raw_text,
            summary=None,
            tags=tags,
            embedding=vec,
            meta=meta,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        # Chunks
        for i, chunk in enumerate(chunk_text(raw_text)):
            db.add(Chunk(entry_id=entry.id, chunk_index=i, text=chunk, embedding=embed(chunk)))

        # Entities
        extracted = await extract_entities(raw_text)
        await link_entities_to_entry(db, entry.id, extracted)
        await db.commit()

    logger.info("Ingested RSS article '%s' (miniflux_id=%d, entry_id=%d)", title, miniflux_id, entry.id)
    return entry.id


# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------

async def poll_once() -> dict:
    """Single poll cycle. Returns stats dict."""
    stats = {"fetched": 0, "ingested": 0, "skipped": 0, "errors": 0}
    try:
        last_ts = await _get_last_poll_ts()
        if last_ts is None:
            last_ts = datetime.now(timezone.utc) - timedelta(days=settings.rss_initial_backfill_days)
            logger.info("First run — backfilling from %s", last_ts.isoformat())

        articles = await _fetch_entries_since(last_ts)
        stats["fetched"] = len(articles)

        if not articles:
            return stats

        feeds = await _fetch_feeds()
        latest_ts = last_ts

        for article in articles:
            try:
                feed_info = feeds.get(article.get("feed_id", 0), {})
                entry_id = await _ingest_article(article, feed_info)
                if entry_id:
                    stats["ingested"] += 1
                else:
                    stats["skipped"] += 1

                # Track the latest published_at we've seen
                pub = article.get("published_at", "")
                if pub:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    # Cap at current time so future-dated articles can't poison the poll timestamp
                    pub_dt = min(pub_dt, datetime.now(timezone.utc))
                    if pub_dt > latest_ts:
                        latest_ts = pub_dt
            except Exception:
                logger.exception("Failed to ingest article %s", article.get("id"))
                stats["errors"] += 1

        await _set_last_poll_ts(latest_ts)
        logger.info(
            "Poll complete: fetched=%d ingested=%d skipped=%d errors=%d",
            stats["fetched"], stats["ingested"], stats["skipped"], stats["errors"],
        )
    except Exception:
        logger.exception("RSS poll_once failed")

    return stats


# ---------------------------------------------------------------------------
# Background poller
# ---------------------------------------------------------------------------

async def run_poller() -> None:
    """Long-running background task — polls Miniflux on a configurable interval."""
    if not settings.miniflux_url or not settings.miniflux_api_key:
        logger.info("Miniflux not configured — RSS poller disabled")
        return

    logger.info(
        "RSS poller started (interval=%ds, url=%s)",
        settings.rss_poll_interval_seconds,
        settings.miniflux_url,
    )
    while True:
        await poll_once()
        await asyncio.sleep(settings.rss_poll_interval_seconds)


# ---------------------------------------------------------------------------
# Daily digest generation
# ---------------------------------------------------------------------------

async def _get_last_digest_date() -> date | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Setting).where(Setting.key == _DIGEST_DATE_KEY))
        row = result.scalar_one_or_none()
        if row:
            return date.fromisoformat(row.value["date"])
    return None


async def _set_last_digest_date(d: date) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        await db.execute(
            pg_insert(Setting)
            .values(key=_DIGEST_DATE_KEY, value={"date": d.isoformat()})
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": {"date": d.isoformat()}},
            )
        )
        await db.commit()


def _render_digest_markdown(digest_data: dict) -> str:
    """Render structured digest JSON into readable markdown."""
    lines = []
    for cat in digest_data.get("categories", []):
        lines.append(f"## {cat['name']}")
        for art in cat.get("articles", []):
            flag = ""
            if art.get("flagged"):
                reason = art.get("flag_reason", "")
                flag = f" 🔴 FLAGGED: {reason}" if reason else " 🔴"
            lines.append(f"- **{art['title']}** — {art['summary']}{flag}")
        lines.append("")
    return "\n".join(lines).strip()


async def generate_daily_digest(target_date: date | None = None) -> dict | None:
    """Generate digest for a given date. Returns the created entry dict, or None if no articles."""
    if target_date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Entry)
            .where(Entry.source_type == "rss")
            .where(Entry.created_at >= day_start)
            .where(Entry.created_at < day_end)
            .order_by(Entry.created_at)
        )
        articles = result.scalars().all()

    if not articles:
        logger.info("No RSS articles for %s, skipping digest", target_date)
        return None

    # Build input for Haiku
    articles_input = []
    for art in articles:
        articles_input.append({
            "entry_id": art.id,
            "title": art.title,
            "category": (art.meta or {}).get("feed_category", "Uncategorized"),
            "text_preview": art.raw_text[:500],
        })

    digest_data = await generate_digest_summary(
        articles_json=json.dumps(articles_input, indent=2),
        topics=settings.rss_relevance_topics,
        model=settings.rss_digest_model,
    )

    # Render markdown
    markdown = _render_digest_markdown(digest_data)

    # Count flagged
    flagged_count = sum(
        1 for cat in digest_data.get("categories", [])
        for art in cat.get("articles", [])
        if art.get("flagged")
    )

    # Collect article entry IDs
    article_entry_ids = [a.id for a in articles]

    meta = {
        "digest_date": target_date.isoformat(),
        "article_count": len(articles),
        "article_entry_ids": article_entry_ids,
        "flagged_count": flagged_count,
        "model_used": settings.rss_digest_model,
        "digest_json": digest_data,
    }

    vec = embed(markdown)

    async with AsyncSessionLocal() as db:
        entry = Entry(
            title=f"Daily Feed Digest — {target_date.strftime('%B %d, %Y')}",
            source_type="rss_digest",
            raw_text=markdown,
            summary=f"{len(articles)} articles, {flagged_count} flagged",
            tags=["digest", "daily"],
            embedding=vec,
            meta=meta,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        # Chunks for the digest itself
        for i, chunk in enumerate(chunk_text(markdown)):
            db.add(Chunk(entry_id=entry.id, chunk_index=i, text=chunk, embedding=embed(chunk)))
        await db.commit()

    # Backfill per-article summaries from structured JSON
    summary_map: dict[int, str] = {}
    for cat in digest_data.get("categories", []):
        for art in cat.get("articles", []):
            eid = art.get("entry_id")
            if eid and art.get("summary"):
                summary_map[eid] = art["summary"]

    if summary_map:
        async with AsyncSessionLocal() as db:
            for eid, summary in summary_map.items():
                await db.execute(
                    sa_text("UPDATE entries SET summary = :summary WHERE id = :eid AND source_type = 'rss'"),
                    {"summary": summary, "eid": eid},
                )
            await db.commit()
        logger.info("Backfilled summaries for %d articles", len(summary_map))

    await _set_last_digest_date(target_date)
    logger.info(
        "Generated digest for %s: %d articles, %d flagged (entry_id=%d)",
        target_date, len(articles), flagged_count, entry.id,
    )
    return {
        "entry_id": entry.id,
        "date": target_date.isoformat(),
        "article_count": len(articles),
        "flagged_count": flagged_count,
    }


async def run_digest_scheduler() -> None:
    """Background loop: checks every 15 min if it's time to generate today's digest."""
    if not settings.miniflux_url or not settings.miniflux_api_key:
        return

    logger.info("RSS digest scheduler started (digest_hour=%d)", settings.rss_digest_hour)
    while True:
        try:
            now = datetime.now(timezone.utc)
            # Check if we're past the digest hour and haven't generated today's digest
            if now.hour >= settings.rss_digest_hour:
                yesterday = (now - timedelta(days=1)).date()
                last_digest = await _get_last_digest_date()
                if last_digest != yesterday:
                    logger.info("Generating digest for %s", yesterday)
                    await generate_daily_digest(yesterday)
        except Exception:
            logger.exception("Digest scheduler error")

        await asyncio.sleep(_DIGEST_CHECK_INTERVAL)


async def get_latest_digest() -> dict | None:
    """Get the most recent digest entry."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Entry)
            .where(Entry.source_type == "rss_digest")
            .order_by(Entry.created_at.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        return {
            "id": entry.id,
            "title": entry.title,
            "raw_text": entry.raw_text,
            "summary": entry.summary,
            "meta": entry.meta,
            "created_at": entry.created_at.isoformat(),
        }


async def get_digest_by_date(target_date: date) -> dict | None:
    """Get digest entry for a specific date."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_text(
                "SELECT id, title, raw_text, summary, meta, created_at "
                "FROM entries WHERE source_type = 'rss_digest' "
                "AND meta->>'digest_date' = :d LIMIT 1"
            ),
            {"d": target_date.isoformat()},
        )
        row = result.first()
        if not row:
            return None
        return {
            "id": row.id,
            "title": row.title,
            "raw_text": row.raw_text,
            "summary": row.summary,
            "meta": row.meta,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


async def get_status() -> dict:
    """Return current RSS polling status for the /rss/status endpoint."""
    last_ts = await _get_last_poll_ts()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_text("SELECT count(*) FROM entries WHERE source_type = 'rss'")
        )
        article_count = result.scalar_one()
        result = await db.execute(
            sa_text("SELECT count(*) FROM entries WHERE source_type = 'rss_digest'")
        )
        digest_count = result.scalar_one()

    return {
        "enabled": bool(settings.miniflux_url and settings.miniflux_api_key),
        "miniflux_url": settings.miniflux_url,
        "last_poll_timestamp": last_ts.isoformat() if last_ts else None,
        "article_count": article_count,
        "digest_count": digest_count,
        "poll_interval_seconds": settings.rss_poll_interval_seconds,
    }
