from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from datetime import datetime
from ..core.database import get_db
from ..core.models import Entity, EntryEntityLink, EntityRelationship, Entry
from ..services.entities import embed_entity

router = APIRouter(prefix="/entities", tags=["entities"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EntityOut(BaseModel):
    id: int
    entity_type: str
    name: str
    meta: dict | None = None
    created_at: datetime
    updated_at: datetime

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


class LinkedEntry(EntrySnippet):
    link_type: str
    confidence: float


class RelationshipOut(BaseModel):
    id: int
    source_entity_id: int
    target_entity_id: int
    relationship_type: str
    meta: dict | None = None
    target_entity_name: str | None = None
    target_entity_type: str | None = None
    source_entity_name: str | None = None
    source_entity_type: str | None = None


class EntityDetail(EntityOut):
    entries: list[LinkedEntry]
    relationships: list[RelationshipOut]


class EntityCreate(BaseModel):
    entity_type: str  # contact | organization
    name: str
    meta: dict | None = None


class EntityUpdate(BaseModel):
    name: str | None = None
    meta: dict | None = None


class RelationshipCreate(BaseModel):
    target_entity_id: int
    relationship_type: str
    meta: dict | None = None


class EntryLinkCreate(BaseModel):
    entity_id: int
    link_type: str = "mention"
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[dict])
async def list_entities(
    entity_type: str | None = None,
    q: str | None = None,
    entry_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if entry_id:
        # Return entities linked to a specific entry, with link_id for unlinking
        query = (
            select(Entity, EntryEntityLink.id.label("link_id"))
            .join(EntryEntityLink, EntryEntityLink.entity_id == Entity.id)
            .where(EntryEntityLink.entry_id == entry_id)
            .order_by(Entity.name)
            .limit(limit)
            .offset(offset)
        )
        if entity_type:
            query = query.where(Entity.entity_type == entity_type)
        if q:
            query = query.where(Entity.name.ilike(f"%{q}%"))
        result = await db.execute(query)
        return [
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "meta": entity.meta,
                "created_at": entity.created_at,
                "updated_at": entity.updated_at,
                "link_id": link_id,
            }
            for entity, link_id in result.all()
        ]

    query = select(Entity).order_by(Entity.name).limit(limit).offset(offset)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if q:
        query = query.where(Entity.name.ilike(f"%{q}%"))
    result = await db.execute(query)
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "name": e.name,
            "meta": e.meta,
            "created_at": e.created_at,
            "updated_at": e.updated_at,
        }
        for e in result.scalars().all()
    ]


@router.get("/{entity_id}", response_model=EntityDetail)
async def get_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Not found")

    # Linked entries with link metadata
    result = await db.execute(
        select(Entry, EntryEntityLink.link_type, EntryEntityLink.confidence)
        .join(EntryEntityLink, EntryEntityLink.entry_id == Entry.id)
        .where(EntryEntityLink.entity_id == entity_id)
        .order_by(Entry.created_at.desc())
    )
    entries = []
    for row in result.all():
        entry, link_type, confidence = row
        entries.append(LinkedEntry(
            id=entry.id,
            created_at=entry.created_at,
            title=entry.title,
            source_type=entry.source_type,
            summary=entry.summary,
            tags=entry.tags,
            link_type=link_type,
            confidence=confidence,
        ))

    # Relationships (both directions)
    result = await db.execute(
        select(EntityRelationship, Entity.name, Entity.entity_type)
        .join(Entity, Entity.id == EntityRelationship.target_entity_id)
        .where(EntityRelationship.source_entity_id == entity_id)
    )
    relationships = []
    for row in result.all():
        rel, target_name, target_type = row
        relationships.append(RelationshipOut(
            id=rel.id,
            source_entity_id=rel.source_entity_id,
            target_entity_id=rel.target_entity_id,
            relationship_type=rel.relationship_type,
            meta=rel.meta,
            target_entity_name=target_name,
            target_entity_type=target_type,
        ))

    # Also include reverse relationships
    result = await db.execute(
        select(EntityRelationship, Entity.name, Entity.entity_type)
        .join(Entity, Entity.id == EntityRelationship.source_entity_id)
        .where(EntityRelationship.target_entity_id == entity_id)
    )
    for row in result.all():
        rel, source_name, source_type = row
        relationships.append(RelationshipOut(
            id=rel.id,
            source_entity_id=rel.source_entity_id,
            target_entity_id=rel.target_entity_id,
            relationship_type=rel.relationship_type,
            meta=rel.meta,
            source_entity_name=source_name,
            source_entity_type=source_type,
        ))

    return EntityDetail(
        id=entity.id,
        entity_type=entity.entity_type,
        name=entity.name,
        meta=entity.meta,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        entries=entries,
        relationships=relationships,
    )


@router.post("/", response_model=EntityOut, status_code=201)
async def create_entity(body: EntityCreate, db: AsyncSession = Depends(get_db)):
    _VALID_TYPES = ("contact", "organization", "account", "opportunity")
    if body.entity_type not in _VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"entity_type must be one of {_VALID_TYPES}")
    entity = Entity(
        entity_type=body.entity_type,
        name=body.name.strip(),
        meta=body.meta,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    await embed_entity(db, entity.id)
    return entity


@router.patch("/{entity_id}", response_model=EntityOut)
async def update_entity(entity_id: int, body: EntityUpdate, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Not found")

    if body.name is not None:
        entity.name = body.name.strip()
    if body.meta is not None:
        # Merge meta fields — must create a new dict so SQLAlchemy detects the change
        entity.meta = {**(entity.meta or {}), **body.meta}
    await db.commit()
    await db.refresh(entity)

    # Re-embed if name or summary changed
    if body.name is not None or (body.meta and "summary" in body.meta):
        await embed_entity(db, entity.id)

    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(entity)
    await db.commit()


# ---------------------------------------------------------------------------
# Relationship management
# ---------------------------------------------------------------------------

@router.post("/{entity_id}/relationships", response_model=RelationshipOut, status_code=201)
async def add_relationship(
    entity_id: int, body: RelationshipCreate, db: AsyncSession = Depends(get_db)
):
    source = await db.get(Entity, entity_id)
    target = await db.get(Entity, body.target_entity_id)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Entity not found")

    rel = EntityRelationship(
        source_entity_id=entity_id,
        target_entity_id=body.target_entity_id,
        relationship_type=body.relationship_type,
        meta=body.meta,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return RelationshipOut(
        id=rel.id,
        source_entity_id=rel.source_entity_id,
        target_entity_id=rel.target_entity_id,
        relationship_type=rel.relationship_type,
        meta=rel.meta,
        target_entity_name=target.name,
        target_entity_type=target.entity_type,
    )


@router.delete("/relationships/{relationship_id}", status_code=204)
async def delete_relationship(relationship_id: int, db: AsyncSession = Depends(get_db)):
    rel = await db.get(EntityRelationship, relationship_id)
    if not rel:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(rel)
    await db.commit()


# ---------------------------------------------------------------------------
# Entry-entity linking
# ---------------------------------------------------------------------------

@router.post("/entries/{entry_id}/entities", response_model=dict, status_code=201)
async def link_entry_to_entity(
    entry_id: int, body: EntryLinkCreate, db: AsyncSession = Depends(get_db)
):
    entry = await db.get(Entry, entry_id)
    entity = await db.get(Entity, body.entity_id)
    if not entry or not entity:
        raise HTTPException(status_code=404, detail="Entry or entity not found")

    # Check for existing link
    existing = await db.execute(
        select(EntryEntityLink).where(
            EntryEntityLink.entry_id == entry_id,
            EntryEntityLink.entity_id == body.entity_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Link already exists")

    link = EntryEntityLink(
        entry_id=entry_id,
        entity_id=body.entity_id,
        link_type=body.link_type,
        confidence=body.confidence,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {"id": link.id, "entry_id": entry_id, "entity_id": body.entity_id, "link_type": body.link_type}


@router.delete("/entry-entity-links/{link_id}", status_code=204)
async def unlink_entry_entity(link_id: int, db: AsyncSession = Depends(get_db)):
    link = await db.get(EntryEntityLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(link)
    await db.commit()


@router.get("/{entity_id}/entries", response_model=list[LinkedEntry])
async def get_entity_entries(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Not found")

    result = await db.execute(
        select(Entry, EntryEntityLink.link_type, EntryEntityLink.confidence)
        .join(EntryEntityLink, EntryEntityLink.entry_id == Entry.id)
        .where(EntryEntityLink.entity_id == entity_id)
        .order_by(Entry.created_at.desc())
    )
    entries = []
    for row in result.all():
        entry, link_type, confidence = row
        entries.append(LinkedEntry(
            id=entry.id,
            created_at=entry.created_at,
            title=entry.title,
            source_type=entry.source_type,
            summary=entry.summary,
            tags=entry.tags,
            link_type=link_type,
            confidence=confidence,
        ))
    return entries
