from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from ..core.models import Entity, EntryEntityLink
from ..services.embeddings import embed


async def _upsert_and_link(
    db: AsyncSession,
    entry_id: int,
    entity_type: str,
    name: str,
    link_type: str = "mention",
    confidence: float = 1.0,
) -> int | None:
    name = name.strip()
    if not name:
        return None

    await db.execute(
        pg_insert(Entity)
        .values(entity_type=entity_type, name=name)
        .on_conflict_do_nothing(constraint="uq_entity_type_name")
    )
    result = await db.execute(
        select(Entity.id).where(Entity.entity_type == entity_type, Entity.name == name)
    )
    entity_id = result.scalar_one()

    # Check for existing link to avoid duplicates
    existing = await db.execute(
        select(EntryEntityLink.id).where(
            EntryEntityLink.entry_id == entry_id,
            EntryEntityLink.entity_id == entity_id,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(EntryEntityLink(
            entry_id=entry_id,
            entity_id=entity_id,
            link_type=link_type,
            confidence=confidence,
        ))

    return entity_id


async def link_entities_to_entry(
    db: AsyncSession,
    entry_id: int,
    extracted: dict,
) -> None:
    for name in extracted.get("people", []):
        await _upsert_and_link(db, entry_id, "contact", name)
    for name in extracted.get("organizations", []):
        await _upsert_and_link(db, entry_id, "organization", name)


async def embed_entity(db: AsyncSession, entity_id: int) -> None:
    """Generate and store an embedding for an entity based on its name and summary."""
    entity = await db.get(Entity, entity_id)
    if not entity:
        return
    summary = (entity.meta or {}).get("summary", "")
    text = f"{entity.entity_type}: {entity.name}. {summary}".strip()
    entity.embedding = embed(text)
    await db.commit()
