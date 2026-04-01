import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from ..core.models import Entity, EntryEntityLink
from ..core.config import settings
from .embeddings import embed
from .claude import client, _parse_json, _record_usage
from .pii import scrub_pii
import asyncio
import time

logger = logging.getLogger("big-brain.entity_resolver")

_EXTRACTION_PROMPT = """Analyze the following content and extract mentions of:
1. Organizations (companies, teams, departments)
2. People (by name, title, or role reference)

For each entity found, return:
- entity_type: "organization" or "contact"
- name: canonical name (e.g., "Acme Corp" not "acme" or "them")
- context: the relevant snippet where they appear
- relationship_hint: any implied relationship (e.g., "works at", "is customer")
- structured_fields: any extractable metadata (title, industry, etc.)

Return ONLY a valid JSON array. If no entities found, return empty array.

Content:
{text}"""


async def extract_entities_structured(text: str) -> list[dict]:
    """Extract structured entity candidates from text using Claude."""
    truncated = scrub_pii(text[:8000], operation="extract_entities_structured")
    t0 = time.perf_counter()
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": _EXTRACTION_PROMPT.format(text=truncated)}],
    )
    _record_usage(response, "extract_entities_structured", time.perf_counter() - t0)
    try:
        return _parse_json(response.content[0].text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("Failed to parse entity extraction response")
        return []


async def match_entity(
    db: AsyncSession,
    entity_type: str,
    name: str,
    threshold: float = 0.85,
) -> dict:
    """Match a candidate entity against existing entities.

    Returns:
        {"status": "matched", "entity": Entity} - high-confidence match
        {"status": "ambiguous", "candidates": [Entity, ...]} - multiple close matches
        {"status": "new"} - no match found
    """
    # Exact name match (case-insensitive)
    result = await db.execute(
        select(Entity).where(
            Entity.entity_type == entity_type,
            Entity.name.ilike(name),
        )
    )
    exact = result.scalar_one_or_none()
    if exact:
        return {"status": "matched", "entity": exact}

    # Semantic similarity search
    candidate_embedding = embed(f"{entity_type}: {name}")
    result = await db.execute(
        text("""
            SELECT id, entity_type, name, meta,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM entities
            WHERE entity_type = :etype
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT 5
        """),
        {"vec": str(candidate_embedding), "etype": entity_type},
    )
    rows = [dict(r) for r in result.mappings().all()]
    close_matches = [r for r in rows if r["score"] >= threshold]

    if len(close_matches) == 1:
        entity = await db.get(Entity, close_matches[0]["id"])
        return {"status": "matched", "entity": entity}
    elif len(close_matches) > 1:
        entities = []
        for r in close_matches:
            e = await db.get(Entity, r["id"])
            entities.append(e)
        return {"status": "ambiguous", "candidates": entities}

    return {"status": "new"}


async def resolve_entities(
    db: AsyncSession,
    text_content: str,
    entry_id: int | None = None,
    auto_link_threshold: float = 0.90,
    suggest_threshold: float = 0.75,
) -> dict:
    """Full extraction + matching pipeline.

    Returns:
        {
            "matched": [{"entity": Entity, "candidate": dict}],
            "ambiguous": [{"candidates": [Entity], "candidate": dict}],
            "new": [{"candidate": dict}]
        }
    """
    candidates = await extract_entities_structured(text_content)
    results = {"matched": [], "ambiguous": [], "new": []}

    for candidate in candidates:
        entity_type = candidate.get("entity_type", "contact")
        name = candidate.get("name", "").strip()
        if not name:
            continue

        match = await match_entity(db, entity_type, name, threshold=suggest_threshold)

        if match["status"] == "matched":
            results["matched"].append({"entity": match["entity"], "candidate": candidate})
            # Auto-link if entry_id provided
            if entry_id:
                existing = await db.execute(
                    select(EntryEntityLink.id).where(
                        EntryEntityLink.entry_id == entry_id,
                        EntryEntityLink.entity_id == match["entity"].id,
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(EntryEntityLink(
                        entry_id=entry_id,
                        entity_id=match["entity"].id,
                        link_type="mention",
                        confidence=0.9,
                    ))
        elif match["status"] == "ambiguous":
            results["ambiguous"].append({"candidates": match["candidates"], "candidate": candidate})
        else:
            results["new"].append({"candidate": candidate})

    if entry_id:
        await db.commit()

    return results
