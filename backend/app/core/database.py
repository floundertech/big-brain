from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector
from .config import settings

engine = create_async_engine(settings.database_url.replace("postgresql://", "postgresql+asyncpg://"))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Partial expression index for fast RSS article dedup
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_entries_miniflux_entry_id "
            "ON entries ((meta->>'miniflux_entry_id')) "
            "WHERE source_type = 'rss'"
        ))
        # Entity system migrations for existing installs
        await conn.execute(text(
            "ALTER TABLE entities ADD COLUMN IF NOT EXISTS meta jsonb"
        ))
        await conn.execute(text(
            f"ALTER TABLE entities ADD COLUMN IF NOT EXISTS embedding vector({settings.embed_dim})"
        ))
        await conn.execute(text(
            "ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at timestamptz "
            "DEFAULT now()"
        ))
        # Migrate legacy entry_entities → entry_entity_links
        await conn.execute(text("""
            INSERT INTO entry_entity_links (entry_id, entity_id, link_type, confidence, created_at)
            SELECT ee.entry_id, ee.entity_id, 'mention', 1.0, now()
            FROM entry_entities ee
            WHERE NOT EXISTS (
                SELECT 1 FROM entry_entity_links eel
                WHERE eel.entry_id = ee.entry_id AND eel.entity_id = ee.entity_id
            )
        """))
        # Migrate entity_type 'person' → 'contact'
        await conn.execute(text(
            "UPDATE entities SET entity_type = 'contact' WHERE entity_type = 'person'"
        ))
