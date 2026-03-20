# Session Notes

## Active branch
`claude/entity-model-lkCxq`

## Current state (2026-03-20)

Layer 2 (Entity Model) is complete and stable. Two OOM / startup bugs fixed this session:
- `main.py` — embedding model is now pre-loaded at startup (`get_model()` called in `lifespan`) to prevent OOM kill (exit 137) when first large upload arrives with model not yet in memory
- `main.py` — router imports (`entries`, `search`, `chat`, `entities`) were accidentally dropped by a linter rewrite; restored

### Known environment gotchas
- `ANTHROPIC_API_KEY` must be set in `.env` before `docker compose up`. Missing key → every ingest returns `500 TypeError: Could not resolve authentication method`.
- First startup takes 2–5 min: embedding model (~520 MB) downloads from HuggingFace on first run.
- On memory-constrained hosts (<1 GB free RAM): startup itself may OOM. Switch `EMBED_MODEL` to `BAAI/bge-small-en-v1.5` (384 dims, ~130 MB) and set `EMBED_DIM=384` if needed.

## What to know before starting a new session

- Read `BIGBRAIN.md` for the full project vision, roadmap, and design decisions
- Read `SESSIONS.md` for a history of what was built and why
- The next planned feature is **Layer 2c: Research/Enrichment** (design complete in BIGBRAIN.md)
- All Claude API calls go through `backend/app/services/claude.py` — add new prompts/functions there
- Ingest pipeline: `entries.py` → `claude.enrich_entry()` + `claude.extract_entities()` → `services/entities.py:link_entities_to_entry()`
- DB schema is auto-created on startup via `create_all` — no Alembic
- Never push to a branch other than the one listed above

## Required at end of every session

Before the final commit and push, always update:
1. **`CLAUDE.md`** — update "Current state" with what changed this session and any new gotchas
2. **`SESSIONS.md`** — add a new session entry (Goal / What Got Built / Key Design Decisions / What's NOT here / Migration Notes / Commits / Next Up)
3. **`README.md`** — if any new failure modes, setup steps, or env vars were introduced, add them to the relevant section

This is not optional. Every session ends with a doc commit.
