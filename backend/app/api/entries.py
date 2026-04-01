from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_
from pydantic import BaseModel
from ..core.database import get_db
from ..core.models import Entry, Chunk
from ..services.embeddings import embed, chunk_text
from ..services.claude import enrich_entry, extract_entities
from ..services.entities import link_entities_to_entry

router = APIRouter(prefix="/entries", tags=["entries"])


async def _create_chunks(db: AsyncSession, entry_id: int, text: str) -> None:
    for i, chunk in enumerate(chunk_text(text)):
        db.add(Chunk(entry_id=entry_id, chunk_index=i, text=chunk, embedding=embed(chunk)))


class EntryOut(BaseModel):
    id: int
    created_at: datetime
    title: str
    source_type: str
    summary: str | None
    tags: list[str]

    class Config:
        from_attributes = True


class EntryDetail(EntryOut):
    raw_text: str


@router.post("/", response_model=EntryDetail, status_code=201)
async def create_entry(
    text: str = Form(...),
    source_type: str = Form("note"),
    db: AsyncSession = Depends(get_db),
):
    enriched = await enrich_entry(text)
    vec = embed(text)
    entry = Entry(
        title=enriched["title"],
        source_type=source_type,
        raw_text=text,
        summary=enriched.get("summary"),
        tags=enriched.get("tags", []),
        embedding=vec,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await _create_chunks(db, entry.id, text)
    extracted = await extract_entities(text)
    await link_entities_to_entry(db, entry.id, extracted)
    await db.commit()
    return entry


@router.post("/upload", response_model=EntryDetail, status_code=201)
async def upload_entry(
    file: UploadFile = File(...),
    source_type: str = Form("transcript"),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    enriched = await enrich_entry(text)
    vec = embed(text)
    entry = Entry(
        title=enriched.get("title", file.filename or "Untitled"),
        source_type=source_type,
        raw_text=text,
        summary=enriched.get("summary"),
        tags=enriched.get("tags", []),
        embedding=vec,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    await _create_chunks(db, entry.id, text)
    extracted = await extract_entities(text)
    await link_entities_to_entry(db, entry.id, extracted)
    await db.commit()
    return entry


@router.post("/reindex", status_code=200)
async def reindex_entries(db: AsyncSession = Depends(get_db)):
    """Backfill chunks for any entries that were ingested before chunking was added."""
    from sqlalchemy import select as sa_select, text as sa_text
    result = await db.execute(
        sa_text("SELECT id, raw_text FROM entries WHERE id NOT IN (SELECT DISTINCT entry_id FROM chunks)")
    )
    rows = result.fetchall()
    for entry_id, raw_text in rows:
        await _create_chunks(db, entry_id, raw_text)
    await db.commit()
    return {"reindexed": len(rows)}


@router.get("/", response_model=list[EntryOut])
async def list_entries(
    tag: str | None = None,
    source_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Entry).order_by(Entry.created_at.desc()).limit(limit).offset(offset)
    if tag:
        q = q.where(Entry.tags.any(tag))
    if source_type:
        q = q.where(Entry.source_type == source_type)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{entry_id}", response_model=EntryDetail)
async def get_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry


class EntryUpdate(BaseModel):
    raw_text: str | None = None
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    meta: dict | None = None


@router.patch("/{entry_id}", response_model=EntryDetail)
async def update_entry(
    entry_id: int, body: EntryUpdate, db: AsyncSession = Depends(get_db)
):
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")

    if body.title is not None:
        entry.title = body.title
    if body.summary is not None:
        entry.summary = body.summary
    if body.tags is not None:
        entry.tags = body.tags
    if body.meta is not None:
        existing = entry.meta or {}
        existing.update(body.meta)
        entry.meta = existing

    if body.raw_text is not None:
        entry.raw_text = body.raw_text
        entry.embedding = embed(body.raw_text)
        # Re-chunk
        await db.execute(delete(Chunk).where(Chunk.entry_id == entry_id))
        await _create_chunks(db, entry_id, body.raw_text)

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(entry)
    await db.commit()
