# Session Notes

## Active branch
`claude/docs-session4-lkCxq` (Session 8: gen_ai token usage spans, 2026-03-21)

## Current state (2026-03-21)

Session 8 complete. Added `_record_usage()` helper to `claude.py` — attaches `gen_ai.*` token-usage attributes to the active OTel span after every Anthropic API call:
- `gen_ai.usage.input_tokens` — sums `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.request.model`, `gen_ai.operation.name`, `gen_ai.response.finish_reasons`
- No-op when tracing is disabled (`span.is_recording() == False`)
- Applied to all three call sites: `enrich_entry`, `extract_entities`, `chat_turn`

Session 7 complete + confirmed working. Auto-instrumentation via OpenLLMetry (Traceloop) for Dynatrace. Token/cost data now visible via custom span attributes.

Previous sessions: Chunk RAG + Tavily fix, Layer 2e Agentic Chat, Layer 2 Entity Model, async fix, OOM fix, markdown rendering.

Previous sessions: Chunk RAG + Tavily fix, Layer 2e Agentic Chat, Layer 2 Entity Model, async fix, OOM fix, markdown rendering.

### Known environment gotchas
- `ANTHROPIC_API_KEY` must be set in `.env` before `docker compose up`. Missing key → every ingest returns `500 TypeError: Could not resolve authentication method`.
- First startup takes 2–5 min: embedding model (~520 MB) downloads from HuggingFace on first run.
- On memory-constrained hosts (<1 GB free RAM): startup itself may OOM. Switch `EMBED_MODEL` to `BAAI/bge-small-en-v1.5` (384 dims, ~130 MB) and set `EMBED_DIM=384` if needed.
- **`meta` column migration required on existing DBs:** `ALTER TABLE entries ADD COLUMN IF NOT EXISTS meta jsonb;`
- **`chunks` table migration required on existing DBs:** run `POST /entries/reindex` after deploying to backfill chunks for existing entries (the table is auto-created, but won't be populated until reindex runs).
- `TAVILY_API_KEY` is optional — if unset, web_search tool gracefully returns an error message and Claude reports it.
- `DT_OTLP_ENDPOINT` + `DT_API_TOKEN` are both optional — if either is unset, tracing is skipped entirely. Token needs scopes: `openTelemetryTrace.ingest`, `metrics.ingest`, `logs.ingest`.
- `traceloop-sdk==0.33.11` had an internal OpenTelemetry sub-dependency conflict (beta version pins couldn't be jointly satisfied). Pin is now `>=0.33.11` — let pip resolve the latest compatible version.

## What to know before starting a new session

- Read `BIGBRAIN.md` for the full project vision, roadmap, and design decisions
- Read `SESSIONS.md` for a history of what was built and why
- The next planned feature is **Layer 2d: Gmail Connector** (design complete in BIGBRAIN.md)
- All Claude API calls go through `backend/app/services/claude.py` — add new prompts/functions there
- Chat is now agentic: `chat_turn()` in claude.py + tool loop in `api/chat.py`
- Ingest pipeline: `entries.py` → `claude.enrich_entry()` + `claude.extract_entities()` → `services/entities.py:link_entities_to_entry()`
- DB schema is auto-created on startup via `create_all` — no Alembic (new columns need manual ALTER TABLE)
- New feature branches should follow the `claude/<feature>-<sessionid>` naming convention
- Never push to main directly — always branch, PR, merge

## Required at end of every session

Before the final commit and push, always update:
1. **`CLAUDE.md`** — update "Current state" with what changed this session and any new gotchas
2. **`SESSIONS.md`** — add a new session entry (Goal / What Got Built / Key Design Decisions / What's NOT here / Migration Notes / Commits / Next Up)
3. **`README.md`** — if any new failure modes, setup steps, or env vars were introduced, add them to the relevant section

This is not optional. Every session ends with a doc commit.
