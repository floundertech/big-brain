from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from ..core.models import Entity, EntryEntity


async def _upsert_and_link(
    db: AsyncSession,
    entry_id: int,
    entity_type: str,
    name: str,
) -> None:
    name = name.strip()
    if not name:
        return

    await db.execute(
        pg_insert(Entity)
        .values(entity_type=entity_type, name=name)
        .on_conflict_do_nothing(constraint="uq_entity_type_name")
    )
    result = await db.execute(
        select(Entity.id).where(Entity.entity_type == entity_type, Entity.name == name)
    )
    entity_id = result.scalar_one()

    await db.execute(
        pg_insert(EntryEntity)
        .values(entry_id=entry_id, entity_id=entity_id)
        .on_conflict_do_nothing()
    )


async def link_entities_to_entry(
    db: AsyncSession,
    entry_id: int,
    extracted: dict,
) -> None:
    for name in extracted.get("people", []):
        await _upsert_and_link(db, entry_id, "person", name)
    for name in extracted.get("organizations", []):
        await _upsert_and_link(db, entry_id, "organization", name)
