# Session Notes

## Active branch
`claude/entity-model-lkCxq`

## Current state (2026-03-20)

Layer 2 (Entity Model) is complete and deployed. The fix landed in this session:
- `claude.py` — `enrich_entry()` and `extract_entities()` are now `async` (via `asyncio.to_thread`); added `_parse_json()` helper that strips markdown code fences before `json.loads()`
- `entries.py` — both calls are now properly `await`-ed in `create_entry` and `upload_entry`

### Known environment gotcha
`ANTHROPIC_API_KEY` must be set in a `.env` file at the repo root before running `docker compose up`. If it's missing, the backend starts but every ingest request returns `500 TypeError: Could not resolve authentication method`. See README Troubleshooting.

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
