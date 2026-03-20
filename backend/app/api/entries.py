from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from ..core.database import get_db
from ..core.models import Entry
from ..services.embeddings import embed
from ..services.claude import enrich_entry, extract_entities
from ..services.entities import link_entities_to_entry

router = APIRouter(prefix="/entries", tags=["entries"])


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
    enriched = enrich_entry(text)
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
    extracted = extract_entities(text)
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
    enriched = enrich_entry(text)
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
    extracted = extract_entities(text)
    await link_entities_to_entry(db, entry.id, extracted)
    await db.commit()
    return entry


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


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(entry_id: int, db: AsyncSession = Depends(get_db)):
    entry = await db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(entry)
    await db.commit()
