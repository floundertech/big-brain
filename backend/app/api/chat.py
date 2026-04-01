import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from pydantic import BaseModel

from ..core.database import get_db
from ..core.models import Entry, Entity, EntryEntityLink, EntityRelationship
from ..services.embeddings import embed
from ..services.claude import chat_turn, enrich_entry, extract_entities
from ..services.entities import link_entities_to_entry, embed_entity
from ..services.pii import scrub_pii
from ..services.tavily import web_search as tavily_search

router = APIRouter(prefix="/chat", tags=["chat"])

_MAX_ITERATIONS = 10


class Message(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _search_notes(query: str, db: AsyncSession, top_k: int = 5) -> tuple[str, list[dict]]:
    vec = embed(query)
    # Search chunks (properly indexed entries) plus fallback for legacy entries without chunks
    result = await db.execute(
        text("""
            (
                SELECT e.id, e.title, c.text AS snippet,
                       1 - (c.embedding <=> CAST(:vec AS vector)) AS score
                FROM chunks c
                JOIN entries e ON e.id = c.entry_id
                ORDER BY c.embedding <=> CAST(:vec AS vector)
                LIMIT :k
            )
            UNION ALL
            (
                SELECT e.id, e.title, LEFT(e.raw_text, 2000) AS snippet,
                       1 - (e.embedding <=> CAST(:vec AS vector)) AS score
                FROM entries e
                WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.entry_id = e.id)
                ORDER BY e.embedding <=> CAST(:vec AS vector)
                LIMIT :k
            )
            ORDER BY score DESC
            LIMIT :k
        """),
        {"vec": str(vec), "k": top_k},
    )
    rows = [dict(r) for r in result.mappings().all()]
    if not rows:
        return "No matching notes found.", []
    formatted = "\n\n---\n\n".join(
        f"[{r['title']}] (score: {r['score']:.2f})\n{r['snippet']}" for r in rows
    )
    sources = [{"id": r["id"], "title": r["title"], "score": r["score"]} for r in rows]
    return formatted, sources


async def _get_entity(name: str, db: AsyncSession) -> str:
    result = await db.execute(
        text("SELECT id, entity_type, name, meta FROM entities WHERE lower(name) LIKE :pat LIMIT 5"),
        {"pat": f"%{name.lower()}%"},
    )
    entities = result.mappings().all()
    if not entities:
        return f"No entity found matching '{name}'."

    parts = []
    for ent in entities:
        result2 = await db.execute(
            text("""
                SELECT e.id, e.title, e.summary FROM entries e
                JOIN entry_entity_links eel ON eel.entry_id = e.id
                WHERE eel.entity_id = :eid
                ORDER BY e.created_at DESC LIMIT 10
            """),
            {"eid": ent["id"]},
        )
        linked = result2.mappings().all()
        entry_lines = "\n".join(
            f"  - [{r['title']}] {r['summary'] or ''}" for r in linked
        )
        meta = ent["meta"] or {}
        meta_lines = ""
        if meta:
            meta_lines = "\n".join(f"  {k}: {v}" for k, v in meta.items() if v) + "\n"
        parts.append(
            f"{ent['entity_type'].title()}: {ent['name']}\n{meta_lines}Linked entries:\n{entry_lines or '  (none)'}"
        )
    return "\n\n".join(parts)


async def _web_search(query: str, num_results: int = 3) -> tuple[str, list[str]]:
    results = await tavily_search(query, num_results)
    urls = [r["url"] for r in results if r.get("url")]
    formatted = "\n\n".join(
        f"**{r['title']}**\n{r['url']}\n{r['content'][:800]}" for r in results
    )
    return formatted or "No results found.", urls


async def _save_entry(text_content: str, title: str, sources: list[str], db: AsyncSession) -> str:
    vec = embed(text_content)
    base_tags = ["source:web"] if sources else []

    entry = Entry(
        title=title,
        source_type="research",
        raw_text=text_content,
        tags=base_tags,
        embedding=vec,
        meta={"sources": sources} if sources else None,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    try:
        enriched = await enrich_entry(text_content)
        entry.summary = enriched.get("summary")
        entry.tags = list(set(enriched.get("tags", []) + base_tags))
        await db.commit()
    except Exception:
        pass  # summary is optional

    extracted = await extract_entities(text_content)
    await link_entities_to_entry(db, entry.id, extracted)
    await db.commit()

    return f"Saved as entry #{entry.id}: '{title}'"


async def _link_entity(entry_id: int, entity_name: str, link_type: str, db: AsyncSession) -> str:
    entry = await db.get(Entry, entry_id)
    if not entry:
        return f"Entry #{entry_id} not found."

    result = await db.execute(
        select(Entity).where(Entity.name.ilike(f"%{entity_name}%"))
    )
    entity = result.scalar_one_or_none()
    if not entity:
        return f"No entity found matching '{entity_name}'. Use create_entity to create one first."

    existing = await db.execute(
        select(EntryEntityLink.id).where(
            EntryEntityLink.entry_id == entry_id,
            EntryEntityLink.entity_id == entity.id,
        )
    )
    if existing.scalar_one_or_none():
        return f"Entry #{entry_id} is already linked to '{entity.name}'."

    db.add(EntryEntityLink(
        entry_id=entry_id,
        entity_id=entity.id,
        link_type=link_type or "mention",
        confidence=1.0,
    ))
    await db.commit()
    return f"Linked entry #{entry_id} to {entity.entity_type} '{entity.name}' as '{link_type}'."


async def _create_entity(
    entity_type: str, name: str, meta: dict | None, related_to: str | None, db: AsyncSession
) -> str:
    entity = Entity(
        entity_type=entity_type,
        name=name.strip(),
        meta=meta,
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    await embed_entity(db, entity.id)

    if related_to:
        result = await db.execute(
            select(Entity).where(Entity.name.ilike(f"%{related_to}%"))
        )
        related = result.scalar_one_or_none()
        if related:
            rel_type = "works_at" if entity_type == "contact" else "partner"
            db.add(EntityRelationship(
                source_entity_id=entity.id,
                target_entity_id=related.id,
                relationship_type=rel_type,
            ))
            await db.commit()
            return f"Created {entity_type} '{name}' (#{entity.id}) and linked to '{related.name}' ({rel_type})."

    return f"Created {entity_type} '{name}' (#{entity.id})."


async def _update_entity(entity_id_or_name: str, updates: dict, db: AsyncSession) -> str:
    entity = None
    if entity_id_or_name.isdigit():
        entity = await db.get(Entity, int(entity_id_or_name))
    if not entity:
        result = await db.execute(
            select(Entity).where(Entity.name.ilike(f"%{entity_id_or_name}%"))
        )
        entity = result.scalar_one_or_none()
    if not entity:
        return f"No entity found matching '{entity_id_or_name}'."

    existing_meta = entity.meta or {}
    existing_meta.update(updates)
    entity.meta = existing_meta
    await db.commit()

    if "summary" in updates:
        await embed_entity(db, entity.id)

    return f"Updated {entity.entity_type} '{entity.name}' with: {', '.join(updates.keys())}."


# ---------------------------------------------------------------------------
# Agentic chat endpoint
# ---------------------------------------------------------------------------

@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    messages = [m.model_dump() for m in req.messages]
    all_sources: list[dict] = []

    for _ in range(_MAX_ITERATIONS):
        response = await asyncio.to_thread(chat_turn, messages)

        if response.stop_reason == "end_turn":
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            return ChatResponse(answer="\n".join(text_parts), sources=all_sources)

        if response.stop_reason == "tool_use":
            # Serialize content blocks for the next messages turn
            serialized = [b.model_dump() for b in response.content]
            messages.append({"role": "assistant", "content": serialized})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                inp = block.input
                result_text = ""

                if block.name == "search_notes":
                    result_text, sources = await _search_notes(inp["query"], db)
                    all_sources = sources

                elif block.name == "get_entity":
                    result_text = await _get_entity(inp["name"], db)

                elif block.name == "web_search":
                    result_text, _ = await _web_search(
                        inp["query"], inp.get("num_results", 3)
                    )

                elif block.name == "save_entry":
                    result_text = await _save_entry(
                        inp["text"], inp["title"], inp.get("sources", []), db
                    )

                elif block.name == "link_entity":
                    result_text = await _link_entity(
                        inp["entry_id"], inp["entity_name"],
                        inp.get("link_type", "mention"), db
                    )

                elif block.name == "create_entity":
                    result_text = await _create_entity(
                        inp["entity_type"], inp["name"],
                        inp.get("meta"), inp.get("related_to"), db
                    )

                elif block.name == "update_entity":
                    result_text = await _update_entity(
                        inp["entity_id_or_name"], inp["updates"], db
                    )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": scrub_pii(result_text, operation="chat_tool_result"),
                })

            messages.append({"role": "user", "content": tool_results})

        else:
            break

    return ChatResponse(answer="I ran into an issue processing your request.", sources=[])
