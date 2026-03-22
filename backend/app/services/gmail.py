"""Gmail connector — polls for messages with the big-brain label and ingests them."""
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
from ..core.models import Entry
from ..services.claude import enrich_entry, extract_entities
from ..services.embeddings import embed, chunk_text
from ..services.entities import link_entities_to_entry

logger = logging.getLogger("big-brain.gmail")

import os
_TOKEN_PATH = Path(os.environ.get("GMAIL_TOKEN", "/app/gmail_token.json"))

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


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


async def _ingest_message(service, msg_id: str, done_label_id: str, ingest_label_id: str) -> None:
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

    # Build text for ingestion
    header_block = f"From: {sender}\nDate: {date_str}\nSubject: {subject}\n\n"
    text = header_block + (body or "(no body)")
    if attachment_count:
        text += f"\n\nNote: this message has {attachment_count} attachment(s). View the original message in Gmail."

    # Run enrichment pipeline
    enriched = await enrich_entry(text)
    vec = embed(text)

    async with AsyncSessionLocal() as db:
        entry = Entry(
            title=enriched.get("title") or subject or "Email",
            source_type="email",
            raw_text=text,
            summary=enriched.get("summary"),
            tags=enriched.get("tags", []),
            embedding=vec,
            gmail_message_id=msg_id,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        # Chunk
        for i, chunk in enumerate(chunk_text(text)):
            from ..core.models import Chunk
            db.add(Chunk(entry_id=entry.id, chunk_index=i, text=chunk, embedding=embed(chunk)))

        extracted = await extract_entities(text)
        await link_entities_to_entry(db, entry.id, extracted)
        await db.commit()

    logger.info("Ingested email '%s' (msg_id=%s, entry_id=%d)", subject, msg_id, entry.id)
    _swap_labels(service, msg_id, ingest_label_id, done_label_id)


def _swap_labels(service, msg_id: str, remove_id: str, add_id: str) -> None:
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [add_id], "removeLabelIds": [remove_id]},
    ).execute()


async def poll_once() -> None:
    """Single poll cycle — fetch labeled messages and ingest them."""
    try:
        service = _get_gmail_service()
        if service is None:
            return

        ingest_label_id = _get_or_create_label(service, settings.gmail_ingest_label)
        done_label_id = _get_or_create_label(service, settings.gmail_done_label)

        result = service.users().messages().list(
            userId="me",
            labelIds=[ingest_label_id],
            maxResults=50,
        ).execute()
        messages = result.get("messages", [])

        if not messages:
            return

        logger.info("Gmail poller: found %d message(s) to ingest", len(messages))
        for msg in messages:
            try:
                await _ingest_message(service, msg["id"], done_label_id, ingest_label_id)
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
        "Gmail poller started (interval=%ds, label='%s')",
        settings.gmail_poll_interval_seconds,
        settings.gmail_ingest_label,
    )
    while True:
        await poll_once()
        await asyncio.sleep(settings.gmail_poll_interval_seconds)
