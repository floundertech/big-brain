from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_db
from ..core.models import Entity, EntryEntity, Entry

router = APIRouter(prefix="/entities", tags=["entities"])


class EntityOut(BaseModel):
    id: int
    entity_type: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class EntrySnippet(BaseModel):
    id: int
    created_at: datetime
    title: str
    source_type: str
    summary: str | None
    tags: list[str]

    class Config:
        from_attributes = True


class EntityDetail(EntityOut):
    entries: list[EntrySnippet]


@router.get("/", response_model=list[EntityOut])
async def list_entities(
    entity_type: str | None = None,
    entry_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Entity).order_by(Entity.name)
    if entity_type:
        q = q.where(Entity.entity_type == entity_type)
    if entry_id is not None:
        q = q.join(EntryEntity, EntryEntity.entity_id == Entity.id).where(
            EntryEntity.entry_id == entry_id
        )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{entity_id}", response_model=EntityDetail)
async def get_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(
        select(Entry)
        .join(EntryEntity, EntryEntity.entry_id == Entry.id)
        .where(EntryEntity.entity_id == entity_id)
        .order_by(Entry.created_at.desc())
    )
    entries = result.scalars().all()

    return EntityDetail(
        id=entity.id,
        entity_type=entity.entity_type,
        name=entity.name,
        created_at=entity.created_at,
        entries=entries,
    )
