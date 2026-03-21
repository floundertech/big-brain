# Session Summaries

## Session 1: Entity Model Implementation (2026-03-20)

### Goal
Implement full entity model layer (DB → extraction → API → frontend pages) with Person and Organization entity types.

### What Got Built

**Backend: 5 files touched/created**
- `models.py`: `Entity` table (type, name, unique constraint) + `EntryEntity` join table with cascade deletes
- `claude.py`: `extract_entities()` — focused second Claude call per ingest, returns `{people: [], organizations: []}`
- `services/entities.py`: async upsert-and-link helper using `INSERT ... ON CONFLICT DO NOTHING` pattern
- `api/entities.py`: two endpoints:
  - `GET /entities/` — list all, filterable by `entity_type` or `entry_id`
  - `GET /entities/{id}` — entity detail with full entry list
- `entries.py`: wired extraction into both `create_entry` and `upload_entry` handlers
- `main.py`: registered entities router

**Frontend: 4 files touched/created**
- `api.js`: added `entities.list(params)` and `entities.get(id)`
- `EntityDetail.jsx`: new page — entity name, type badge, all linked entries
- `EntryDetail.jsx`: entity pills below tags, violet for people, amber for orgs, clickable to entity page
- `App.jsx`: added `/entity/:id` route

### Key Design Decisions

**Single vs. Multiple Tables**
- One `entities` table with `entity_type` discriminator column, not separate tables
- Simpler to query, extend (adding Project = no schema change), and reason about
- Unique constraint on `(entity_type, name)` provides the same protection

**Separate Extraction Call**
- Added second Claude call per ingest (dedicated to entity extraction only)
- Cost is minimal (256 token limit, very focused prompt)
- Keeps extraction logic isolated and independently tunable
- Alternative was merging into `_ENRICH_PROMPT`, but that risks prompt confusion

**Upsert Pattern**
- Used `INSERT ... ON CONFLICT DO NOTHING` instead of SELECT-then-INSERT
- Prevents race conditions in concurrent requests
- Native to PostgreSQL, clean and efficient

**Entity Pages vs. Inline Embedding**
- Entity pills are clickable links to dedicated pages, not inline expandable sections
- Keeps entry detail page lightweight and focused
- Entity pages are read-only for now (no manual entity editing UI)

**Filtering API**
- `GET /entities/?entry_id=123` to fetch entities for a specific entry
- Alternative was embedding entities in the entry response, but that changes `EntryOut` Pydantic model
- This approach keeps all existing endpoints 100% unchanged

### What's NOT in V2

- No extended entity fields (roles, relationships, org context) — schema starts minimal
- No manual entity creation/editing UI — entities are auto-created by extraction only
- No Project or Topic entities yet — Foundation is Person and Organization only
- No linking entities to each other (person→org relationships come next)

### Migration / Deployment Notes

- New tables auto-created on next `docker compose up` via existing `create_all` pattern
- No Alembic or manual migrations needed
- Existing entry endpoints and frontend pages work unchanged
- All entity functionality is additive — no breaking changes

### Commits

- `3b9aeff` — Add entity model: Person + Organization extraction and pages
- `b89bd7b` — Update docs: mark Layer 2 (Entity Model) complete, add session summary
- `e250fb5` — Docs: add Research/Enrichment feature design (Layer 2c)
- `6d56b87` — Docs: add source provenance requirement to Research feature design
- `9d09717` — Update README, requirements, and .env.example for V2

### Next Up

Layer 2c: Research/Enrichment implementation. Design is complete (see BIGBRAIN.md). Two entry points: Entity page "Enrich" button + standalone Research page. Output saved as `source_type: "research"` entries with source URL provenance. Layer 2b (typed tags) deferred until after gaining more entity usage patterns.

---

## Session 2: Async fix + JSON parsing hardening (2026-03-20)

### Goal
Fix `500 Internal Server Error` on `/entries/upload` caused by two bugs introduced during entity model work.

### What Got Built

**`backend/app/services/claude.py`** — 2 changes:
- Added `_parse_json()` helper: strips ` ```json ` / ` ``` ` markdown fences before calling `json.loads()`. Claude occasionally wraps JSON responses in code fences, which caused `JSONDecodeError` crashes.
- Made `enrich_entry()` and `extract_entities()` `async` using `asyncio.to_thread()`. The sync Anthropic client was being called directly in an async FastAPI handler, which blocks the event loop.

**`backend/app/api/entries.py`** — added `await` to both `enrich_entry()` and `extract_entities()` calls in `create_entry` and `upload_entry`.

**`CLAUDE.md`** — expanded from stub to full session context doc.

**`README.md`** — added "500 on every upload" troubleshooting entry with diagnosis and fix commands.

### Key Design Decisions

**asyncio.to_thread vs. AsyncAnthropic**
Used `asyncio.to_thread` wrapping the sync client rather than switching to `AsyncAnthropic`. Keeps the client instantiation simple (one client at module level) and avoids changing the `chat()` function which is called from a sync context. Can migrate to `AsyncAnthropic` later if needed.

**_parse_json as a shared helper**
Both `enrich_entry` and `extract_entities` need the same stripping logic. Centralizing it means one place to adjust if Claude's formatting behavior changes.

### What's NOT in This Version
- No retry logic on Claude API failures
- `chat()` remains synchronous (it's called from a sync route handler and doesn't need async yet)

### Migration / Deployment Notes
- Drop-in replacement: no DB changes, no new env vars
- Restart backend container to pick up the fix: `docker compose up -d --build backend`

### Commits
- `f2e277d` — Fix transcript upload failing due to Claude returning markdown-wrapped JSON

### Next Up
Layer 2c: Research/Enrichment. Design is complete in BIGBRAIN.md.

---

## Session 3: OOM fix + startup import fix (2026-03-20)

### Goal
Diagnose and fix backend container crashing with exit code 137 on first large `.txt` upload, and a follow-on `NameError` that broke startup entirely.

### What Got Built

**`backend/app/main.py`** — 2 changes:
- Added `get_model()` call inside `lifespan()` startup hook. The fastembed `nomic-embed-text-v1.5` model was lazily loaded on first request; when a large upload arrived the combined memory spike (file + model load + Claude response) OOM-killed the container (exit 137). Pre-loading at startup settles the model into RAM before any request can arrive.
- Restored `from .api import entries, search, chat, entities` import line that was silently dropped by the linter during the previous fix, causing `NameError: name 'entries' is not defined` on every startup.

### Key Design Decisions

**Pre-warm vs. switch model**
Pre-warming at startup is the minimal fix: it doesn't change model quality or vector dimensions, and it keeps the existing `embed_cache` volume working. Switching to a lighter model (`bge-small-en-v1.5`) is documented as a fallback for hosts with <1 GB free RAM.

**No memory limit added to Compose**
Adding `mem_limit` to docker-compose.yml would just make the OOM fail faster with a cleaner error, not prevent it. Pre-warming is the actual fix.

### What's NOT in This Version
- No fallback/retry on embed failure
- No streaming or chunked processing for very large files

### Migration / Deployment Notes
- Pull latest, `docker compose up --build -d`
- No DB changes, no new env vars
- First startup is slower (model loads before the server accepts requests) — this is expected and healthy

### Commits
- `ab5d4be` — Pre-warm embedding model at startup to prevent OOM on large uploads
- `2fc9756` — Fix missing api router imports dropped by linter

### Next Up
Layer 2c: Research/Enrichment. Design is complete in BIGBRAIN.md.

---

## Session 4: Markdown rendering + housekeeping (2026-03-21)

### Goal
Render Claude's chat responses as markdown in the frontend, and add a `.gitignore` to stop committing build artifacts.

### What Got Built

**Frontend: 2 files touched/created**
- `frontend/src/components/Markdown.jsx`: new reusable component wrapping `react-markdown` + `remark-gfm`. Styles paragraphs, lists, headings, inline/block code, blockquotes, links — all scoped to fit the dark chat UI
- `frontend/src/pages/Chat.jsx`: assistant message bubbles now render through `<Markdown>` instead of raw text

**Root**
- `.gitignore`: excludes `node_modules/`, `frontend/dist/`, `__pycache__/`, `*.pyc`, `.env`, `*.egg-info/`, `.venv/`

**Git hygiene**
- `claude/second-brain-platform-design-lkCxq` was rebased onto `main` (had diverged after PRs merged), then force-pushed and merged via PR, then deleted

### Key Design Decisions

**Shared Markdown component**
A dedicated `Markdown.jsx` rather than inlining `react-markdown` in `Chat.jsx` — easy to reuse on entry detail pages or anywhere else Claude-generated text appears.

**GFM plugin**
`remark-gfm` enables tables, strikethrough, and task lists — Claude occasionally uses these in structured answers, so worth including from the start.

### What's NOT in This Version
- No syntax highlighting for code blocks (could add `react-syntax-highlighter` later)
- `Markdown.jsx` not yet used on Entry detail / Entity pages (Claude-generated summaries are plain text there)

### Migration / Deployment Notes
- `npm install` (or `docker compose up --build`) picks up `react-markdown` and `remark-gfm` automatically from `package.json`
- No backend changes, no DB changes, no new env vars

### Commits
- `9440ea3` — Add .gitignore (node_modules, dist, pycache, .env)
- `cd73356` — Render chat assistant responses as markdown

### Next Up
Layer 2c: Research/Enrichment. Design is complete in BIGBRAIN.md.

---

## Session 5: Agentic Chat (Layer 2e) (2026-03-21)

### Goal
Replace the static RAG chat with a tool-using agent. Claude can now search notes, look up entities, search the web, and save new entries — all from the chat interface.

### What Got Built

**Backend: 4 files touched, 1 created**
- `backend/app/core/config.py`: added optional `tavily_api_key` setting
- `backend/app/core/models.py`: added `meta` JSON column to `Entry` for storing web source URLs
- `backend/app/services/tavily.py`: new — Tavily web search wrapper (`web_search(query, num_results)`)
- `backend/app/services/claude.py`: replaced `chat()` with `chat_turn()` (returns raw `Message` response); added `TOOLS` list (4 tools) + `_AGENTIC_SYSTEM` prompt
- `backend/app/api/chat.py`: full rewrite — agentic loop (up to 10 iterations), 4 tool implementations, inline entry saving pipeline

**Frontend: no changes.** Chat UI is identical — same input box, same message thread, same `sources` display.

**Design docs**
- `BIGBRAIN.md`: added Layer 2d (Gmail) + Layer 2e (Agentic Chat) design specs, updated data model and roadmap

### Key Design Decisions

**claude.py stays thin; chat.py orchestrates**
`chat_turn()` in claude.py is one Claude API call. The agentic loop, tool dispatch, and DB writes all live in `chat.py`. This keeps claude.py as a service layer (API calls only) and keeps the orchestration close to the route handler where the DB session lives.

**asyncio.to_thread for the sync Anthropic client**
Same pattern as `enrich_entry` / `extract_entities`. No migration to AsyncAnthropic needed.

**Confirmation protocol in the system prompt, not the server**
Claude is instructed to ask before calling `web_search` or `save_entry`. No server-side state tracking. Works naturally with multi-turn message history — user says "yes" → next request Claude sees the confirmation and calls the tool. Simple, no extra infrastructure.

**`meta` not `metadata` on the model**
SQLAlchemy's `Base` class has a class-level `metadata` attribute. Using `meta` as the Python attribute name avoids the conflict while mapping to a `metadata` column in DB (using the column name param). Actually, we use `meta` as both the Python attribute and column name for simplicity.

**save_entry runs enrichment post-save**
The entry is committed first (with the agent's title), then `enrich_entry` runs for summary + better tags. If enrichment fails, the entry still exists with the agent's title and no summary. Entity extraction runs after enrichment regardless.

**Tavily as web search provider**
Designed for LLM agents — returns extracted text content, not raw HTML. Free plan (1,000 searches/month) sufficient for personal use. Completely optional: if `TAVILY_API_KEY` is unset, the tool returns an error message and Claude gracefully reports it can't search.

### What's NOT in This Version
- No streaming (still request/response, whole answer returned at once)
- No UI indicator that Claude is using tools (just "Thinking..." during the full agentic loop)
- `meta` column won't auto-add to existing DBs — requires manual `ALTER TABLE` (see migration notes)
- Research page (Layer 2c) is now redundant; deferred/cancelled
- Gmail connector (Layer 2d) not started

### Migration / Deployment Notes
**Existing DB:** The `meta` column is new. `create_all` won't add it to an existing table. Run manually:
```sql
ALTER TABLE entries ADD COLUMN IF NOT EXISTS meta jsonb;
```
Or wipe and rebuild (losing data):
```bash
docker compose down -v && docker compose up -d --build
```

**New env var (optional):**
```env
TAVILY_API_KEY=tvly-...   # from tavily.com, free plan
```
Without it, web search gracefully fails with a message. All other functionality works.

**Rebuild backend:**
```bash
docker compose up -d --build backend
```

### Commits
- `565cb97` — Design: Gmail connector (Layer 2d) + Agentic Chat (Layer 2e)
- `6714a6d` — feat: agentic chat with tool use (Layer 2e)

### Next Up
- Gmail connector (Layer 2d): label-based email ingestion, OAuth2 flow, background poller
- UI polish: tool-use indicator while agent is working, saved entry link in chat response

---

## Session 6: Chunk RAG + Tavily fix (2026-03-21)

### Goal
Improve search recall on long transcripts, and fix web search silently failing despite `TAVILY_API_KEY` being set.

### What Got Built

**Backend: 3 files touched**
- `backend/app/core/models.py`: new `Chunk` table — `entry_id` (FK cascade delete), `chunk_index`, `text`, `embedding vector(768)`
- `backend/app/services/embeddings.py`: added `chunk_text(text, size=1000, overlap=150)` — splits text into overlapping windows and embeds each chunk
- `backend/app/api/entries.py`: ingest pipeline now calls `chunk_text()` and inserts `Chunk` rows after creating an entry; added `POST /entries/reindex` endpoint to backfill chunks for all existing entries
- `backend/app/api/chat.py`: `_search_notes` now queries `chunks` table first; falls back to entry-level embeddings for entries with no chunks (legacy data)

**Infra: 1 file touched**
- `docker-compose.yml`: added `TAVILY_API_KEY` to backend `environment` block — it was in `.env` but not forwarded to the container, causing `web_search` to always fail

**Docs: 1 file touched**
- `.env.example`: added `TAVILY_API_KEY` placeholder with comment

### Key Design Decisions

**Chunk size 1000 / overlap 150**
Long transcripts (Plaud exports, meeting notes) were producing poor search results because a single 768-dim embedding for 5,000+ words collapses too much meaning. 1000-char chunks are large enough to preserve sentence context, small enough to be topically focused. 150-char overlap prevents splits cutting across a key phrase.

**Fallback to entry-level embeddings**
Entries ingested before this change have no chunk rows. Rather than requiring a mandatory migration, `_search_notes` checks both tables and merges results. Run `POST /entries/reindex` to upgrade existing entries.

**Cascade delete on Chunk**
`Chunk.entry_id` has `ON DELETE CASCADE` — deleting an entry automatically cleans up its chunks. No orphan rows.

**docker-compose env forwarding bug**
`.env` is loaded by Docker Compose at the host level, but individual env vars must be explicitly listed under `environment:` in the service definition to reach the container. `TAVILY_API_KEY` was missing from that list.

### What's NOT in This Version
- No chunk-level highlighting in search results (returns entry-level results after deduplication)
- Reindex endpoint is unauthenticated — fine for self-hosted, but worth noting
- No streaming for the agentic loop

### Migration / Deployment Notes
**New table:** `chunks` is auto-created on startup via `create_all`. No manual SQL needed.

**Backfill existing entries:**
```bash
curl -X POST http://localhost:8000/entries/reindex
```
Or from inside the stack: `docker compose exec backend curl -X POST http://localhost:8000/entries/reindex`

**Tavily fix — no action needed** if you're doing a fresh install. If upgrading, `docker compose up -d --build backend` picks up the new env forwarding.

### Commits
- `0d95180` — feat: chunk-based RAG for deep search in long transcripts
- `c1650f5` — docs: add TAVILY_API_KEY to .env.example
- `579b694` — fix: pass TAVILY_API_KEY through to backend container

### Next Up
- Gmail connector (Layer 2d): label-based email ingestion, OAuth2 flow, background poller
- UI: tool-use indicator while agent is working, saved-entry link in chat response

---

## Template for Future Sessions

### Goal
[What are we trying to accomplish?]

### What Got Built
[Files changed, features delivered]

### Key Design Decisions
[Why we chose X over Y]

### What's NOT in This Version
[Deliberately deferred, future layers]

### Migration / Deployment Notes
[How does this ship? Any setup steps?]

### Commits
[Hash — message]

### Next Up
[What's the logical next step?]
