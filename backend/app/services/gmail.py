"""Gmail connector — polls for messages with configurable labels and ingests them."""
import asyncio
import base64
import logging
import os
import re
from email import message_from_bytes
from email.header import decode_header
from pathlib import Path

from sqlalchemy import select

from ..core.config import settings
from ..core.database import SessionLocal as AsyncSessionLocal
from ..core.models import Entry, Chunk
from ..services.claude import enrich_entry, extract_entities
from ..services.embeddings import embed, chunk_text
from ..services.entities import link_entities_to_entry

logger = logging.getLogger("big-brain.gmail")

_TOKEN_PATH = Path(os.environ.get("GMAIL_TOKEN", "/app/gmail_token.json"))

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Label routing configuration
_LABEL_ROUTES = None


def _get_label_routes() -> list[dict]:
    """Build label routing config from settings."""
    global _LABEL_ROUTES
    if _LABEL_ROUTES is not None:
        return _LABEL_ROUTES

    _LABEL_ROUTES = [
        # Legacy catch-all label
        {"label": settings.gmail_ingest_label, "pipeline": "default", "done_label": settings.gmail_done_label},
        # Routed labels
        {"label": settings.gmail_label_customer, "pipeline": "customer_interaction", "done_label": settings.gmail_done_label},
        {"label": settings.gmail_label_research, "pipeline": "research", "done_label": settings.gmail_done_label},
        {"label": settings.gmail_label_reference, "pipeline": "reference", "done_label": settings.gmail_done_label},
    ]
    return _LABEL_ROUTES


def _get_gmail_service():
    """Build an authenticated Gmail API service. Returns None if credentials absent."""
    if not _TOKEN_PATH.exists():
        return None

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _get_or_create_label(service, label_name: str) -> str:
    """Return the Gmail label ID for label_name, creating it if it doesn't exist."""
    result = service.users().labels().list(userId="me").execute()
    for lbl in result.get("labels", []):
        if lbl["name"].lower() == label_name.lower():
            return lbl["id"]
    # Create it
    created = service.users().labels().create(
        userId="me",
        body={"name": label_name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    logger.info("Created Gmail label '%s' (id=%s)", label_name, created["id"])
    return created["id"]


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _extract_plain_text(raw_bytes: bytes) -> str:
    msg = message_from_bytes(raw_bytes)

    plain = None
    html = None

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and plain is None:
                charset = part.get_content_charset() or "utf-8"
                plain = part.get_payload(decode=True).decode(charset, errors="replace")
            elif ct == "text/html" and html is None:
                charset = part.get_content_charset() or "utf-8"
                html = part.get_payload(decode=True).decode(charset, errors="replace")
    else:
        ct = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            text = payload.decode(charset, errors="replace")
            if ct == "text/plain":
                plain = text
            else:
                html = text

    if plain:
        return plain.strip()

    # Strip HTML tags as last resort
    if html:
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    return ""


def _count_attachments(raw_bytes: bytes) -> int:
    msg = message_from_bytes(raw_bytes)
    count = 0
    for part in msg.walk():
        if part.get_content_disposition() in ("attachment", "inline") and part.get_filename():
            count += 1
    return count


# ---------------------------------------------------------------------------
# Forwarded email parsing
# ---------------------------------------------------------------------------

_FWD_PATTERNS = [
    # Gmail / generic
    re.compile(r"-{5,}\s*Forwarded message\s*-{5,}", re.IGNORECASE),
    # Apple Mail
    re.compile(r"Begin forwarded message:", re.IGNORECASE),
    # Outlook-style headers block
    re.compile(r"^From:\s+.+\nSent:\s+.+\nTo:\s+.+\nSubject:\s+", re.IGNORECASE | re.MULTILINE),
]

_FWD_HEADER_RE = re.compile(
    r"(?:From:\s*(?P<from>.+?)[\r\n])"
    r"(?:.*?(?:Sent|Date):\s*(?P<date>.+?)[\r\n])?"
    r"(?:.*?To:\s*(?P<to>.+?)[\r\n])?"
    r"(?:.*?Subject:\s*(?P<subject>.+?)[\r\n])?",
    re.IGNORECASE | re.DOTALL,
)


def parse_forwarded_email(body: str) -> dict | None:
    """Detect and parse forwarded email content.

    Returns dict with keys: original_sender, original_date, original_subject,
    user_annotation, original_body. Returns None if not a forwarded email.
    """
    for pattern in _FWD_PATTERNS:
        match = pattern.search(body)
        if match:
            split_pos = match.start()
            user_annotation = body[:split_pos].strip()
            forwarded_block = body[match.end():].strip()

            # Try to extract headers from the forwarded block
            header_match = _FWD_HEADER_RE.search(forwarded_block)
            result = {
                "user_annotation": user_annotation or None,
                "original_sender": None,
                "original_date": None,
                "original_subject": None,
                "original_body": forwarded_block,
            }
            if header_match:
                result["original_sender"] = (header_match.group("from") or "").strip() or None
                result["original_date"] = (header_match.group("date") or "").strip() or None
                result["original_subject"] = (header_match.group("subject") or "").strip() or None
                # Strip headers from body
                result["original_body"] = forwarded_block[header_match.end():].strip()

            return result

    return None


# ---------------------------------------------------------------------------
# Message ingestion
# ---------------------------------------------------------------------------

async def _ingest_message(
    service, msg_id: str, done_label_id: str, ingest_label_id: str, pipeline: str = "default"
) -> None:
    """Fetch, parse, and ingest a single Gmail message."""
    async with AsyncSessionLocal() as db:
        # Dedup check
        result = await db.execute(select(Entry).where(Entry.gmail_message_id == msg_id))
        if result.scalar_one_or_none():
            logger.debug("Message %s already ingested, skipping", msg_id)
            _swap_labels(service, msg_id, ingest_label_id, done_label_id)
            return

    # Fetch full message (raw format gives us the RFC 2822 bytes)
    raw = service.users().messages().get(userId="me", id=msg_id, format="raw").execute()
    raw_bytes = base64.urlsafe_b64decode(raw["raw"] + "==")

    msg = message_from_bytes(raw_bytes)
    subject = _decode_header_value(msg.get("Subject", ""))
    sender = _decode_header_value(msg.get("From", ""))
    date_str = msg.get("Date", "")

    body = _extract_plain_text(raw_bytes)
    attachment_count = _count_attachments(raw_bytes)

    if not body and not subject:
        logger.warning("Message %s has no body or subject, skipping", msg_id)
        _swap_labels(service, msg_id, ingest_label_id, done_label_id)
        return

    # Check for forwarded email content
    forwarded = parse_forwarded_email(body) if body else None

    # Build text and meta for ingestion
    meta = {"pipeline": pipeline, "gmail_label": pipeline}

    if forwarded:
        meta["forwarded"] = True
        if forwarded["original_sender"]:
            meta["original_sender"] = forwarded["original_sender"]
        if forwarded["original_date"]:
            meta["original_date"] = forwarded["original_date"]
        if forwarded["original_subject"]:
            meta["original_subject"] = forwarded["original_subject"]
        if forwarded["user_annotation"]:
            meta["user_annotation"] = forwarded["user_annotation"]

        # Use original metadata for the header block
        orig_sender = forwarded["original_sender"] or sender
        orig_subject = forwarded["original_subject"] or subject
        orig_date = forwarded["original_date"] or date_str
        header_block = f"From: {orig_sender}\nDate: {orig_date}\nSubject: {orig_subject}\n"
        if forwarded["user_annotation"]:
            header_block += f"Annotation: {forwarded['user_annotation']}\n"
        header_block += "\n"
        text = header_block + (forwarded["original_body"] or "(no body)")

        # Composite dedup key for forwarded emails
        meta["fwd_dedup_key"] = f"{orig_sender}|{orig_date}|{orig_subject}"
    else:
        header_block = f"From: {sender}\nDate: {date_str}\nSubject: {subject}\n\n"
        text = header_block + (body or "(no body)")

    if attachment_count:
        text += f"\n\nNote: this message has {attachment_count} attachment(s). View the original message in Gmail."

    # Determine source_type based on pipeline
    source_type = "email"
    if pipeline == "customer_interaction":
        source_type = "email"
    elif pipeline == "research":
        source_type = "email"
    elif pipeline == "reference":
        source_type = "email"

    # Run enrichment pipeline
    enriched = await enrich_entry(text)
    vec = embed(text)

    async with AsyncSessionLocal() as db:
        # Forwarded email dedup check
        if forwarded and meta.get("fwd_dedup_key"):
            from sqlalchemy import text as sa_text
            existing = await db.execute(
                sa_text(
                    "SELECT id FROM entries WHERE meta->>'fwd_dedup_key' = :key"
                ),
                {"key": meta["fwd_dedup_key"]},
            )
            if existing.scalar_one_or_none():
                logger.debug("Forwarded email already ingested (dedup key=%s), skipping", meta["fwd_dedup_key"])
                _swap_labels(service, msg_id, ingest_label_id, done_label_id)
                return

        entry = Entry(
            title=enriched.get("title") or subject or "Email",
            source_type=source_type,
            raw_text=text,
            summary=enriched.get("summary"),
            tags=enriched.get("tags", []),
            embedding=vec,
            gmail_message_id=msg_id,
            meta=meta,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        # Chunk
        for i, chunk in enumerate(chunk_text(text)):
            db.add(Chunk(entry_id=entry.id, chunk_index=i, text=chunk, embedding=embed(chunk)))

        extracted = await extract_entities(text)
        await link_entities_to_entry(db, entry.id, extracted)
        await db.commit()

    logger.info(
        "Ingested email '%s' (msg_id=%s, entry_id=%d, pipeline=%s)",
        subject, msg_id, entry.id, pipeline,
    )
    _swap_labels(service, msg_id, ingest_label_id, done_label_id)


def _swap_labels(service, msg_id: str, remove_id: str, add_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [add_id], "removeLabelIds": [remove_id]},
    ).execute()


async def poll_once() -> None:
    """Single poll cycle — fetch labeled messages from all configured labels and ingest them."""
    try:
        service = _get_gmail_service()
        if service is None:
            return

        done_label_id = _get_or_create_label(service, settings.gmail_done_label)

        for route in _get_label_routes():
            label_name = route["label"]
            pipeline = route["pipeline"]

            try:
                ingest_label_id = _get_or_create_label(service, label_name)
            except Exception:
                logger.debug("Could not get/create label '%s', skipping", label_name)
                continue

            result = service.users().messages().list(
                userId="me",
                labelIds=[ingest_label_id],
                maxResults=50,
            ).execute()
            messages = result.get("messages", [])

            if not messages:
                continue

            logger.info("Gmail poller: found %d message(s) with label '%s'", len(messages), label_name)
            for msg in messages:
                try:
                    await _ingest_message(service, msg["id"], done_label_id, ingest_label_id, pipeline)
                except Exception:
                    logger.exception("Failed to ingest message %s", msg["id"])

    except Exception:
        logger.exception("Gmail poll_once failed")


async def run_poller() -> None:
    """Long-running background task — polls Gmail on a configurable interval."""
    if not _TOKEN_PATH.exists():
        logger.info("Gmail token not found (%s) — poller disabled", _TOKEN_PATH)
        return

    logger.info(
        "Gmail poller started (interval=%ds, labels=%s)",
        settings.gmail_poll_interval_seconds,
        [r["label"] for r in _get_label_routes()],
    )
    while True:
        await poll_once()
        await asyncio.sleep(settings.gmail_poll_interval_seconds)
