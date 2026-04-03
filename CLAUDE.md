# Session Notes

## Active branch
`feature/entity-system` — Session 13 (Entity System & Relationship Intelligence).

## Current state (2026-04-02)

Session 13 complete. Full entity system overhaul implementing CRM-like entity layer with 5 phases.

Key implementation details:

**Phase 1 — Enhanced Data Model:**
- `Entity` model expanded: added `meta` (JSONB), `embedding` (vector 768), `updated_at`. Entity type renamed from `person` → `contact`.
- New `EntityRelationship` table: source/target entity IDs, relationship_type (works_at, reports_to, etc.), meta JSONB.
- New `EntryEntityLink` table replaces `EntryEntity` (kept for migration): adds `link_type` (mention/about/from/to), `confidence` (float).
- `init_db()` handles migration: ALTERs existing entities table, migrates entry_entities → entry_entity_links, renames person → contact.

**Phase 2 — Entity Extraction & Matching Pipeline:**
- `services/entity_resolver.py`: structured extraction via Haiku, semantic matching against entity embeddings, three-outcome resolution (matched/ambiguous/new).
- Three new chat tools: `link_entity`, `create_entity`, `update_entity` — added to TOOLS list and chat loop.
- `embed_entity()` helper generates embeddings for entities using `"{type}: {name}. {summary}"` format.

**Phase 3 — Gmail Label-Based Routing:**
- Gmail poller now iterates over multiple labels: `big-brain`, `big-brain/customer`, `big-brain/research`, `big-brain/reference`.
- Each label routes to a pipeline (default, customer_interaction, research, reference).
- Forwarded email parsing: detects Gmail/Outlook/Apple Mail forwarding patterns, extracts original sender/date/subject, separates user annotation.
- Composite dedup key for forwarded emails: `original_sender|original_date|original_subject`.
- New env vars: `GMAIL_LABEL_CUSTOMER`, `GMAIL_LABEL_RESEARCH`, `GMAIL_LABEL_REFERENCE`, `GMAIL_REMOVE_LABEL_AFTER_PROCESSING`.

**Phase 4 — Edit Capabilities:**
- Full entity CRUD: `POST/PATCH/DELETE /entities/`, `POST/DELETE` for relationships, entry-entity linking.
- `PATCH /entries/{id}` for entry editing (re-embeds and re-chunks on raw_text change).
- Meta updates merge fields rather than replacing.

**Phase 5 — Entity Detail Views + Frontend:**
- New `/entities` page: searchable/filterable entity list with inline creation form.
- Enhanced entity detail view: inline field editing (click-to-edit), type-specific meta fields, relationship display, contacts section for orgs, interactions and research sections.
- Navigation updated with "Entities" tab.
- All entity type references updated from `person` → `contact` across frontend.

**DB migration for existing installs:**
```sql
ALTER TABLE entities ADD COLUMN IF NOT EXISTS meta jsonb;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
UPDATE entities SET entity_type = 'contact' WHERE entity_type = 'person';
-- entry_entity_links table and data migration handled automatically by init_db()
```
- **DB migration for existing installs:** `ALTER TABLE entries ADD COLUMN IF NOT EXISTS gmail_message_id varchar(200) UNIQUE;`

---

Session 11 complete. Added PII scrubbing via Microsoft Presidio to prevent structured identifiers (SSN, driver's license, credit card, passport, ITIN, IBAN, bank account) from being sent to external APIs. Names pass through untouched.

Key implementation details:
- `services/pii.py`: `scrub_pii()` function using Presidio `AnalyzerEngine` + `AnonymizerEngine`. Lazy-initialized on first call.
- Only scrubs outbound API calls — raw text stored locally in Postgres is unchanged.
- Scrub points: `enrich_entry()` and `extract_entities()` in `claude.py`, and all tool result text in `chat.py` before it re-enters the Claude message loop.
- Entity list is explicit: `US_SSN`, `US_DRIVER_LICENSE`, `CREDIT_CARD`, `US_PASSPORT`, `US_BANK_NUMBER`, `US_ITIN`, `IBAN_CODE`. No names, emails, or phone numbers.
- Score threshold 0.7 to reduce false positives.
- spaCy `en_core_web_lg` model downloaded at Docker build time (adds ~560 MB to image).
- Presidio engines are lazy-loaded — no startup impact unless PII scrubbing is actually triggered.
- `scrub_pii(text, operation)` emits a `security.pii.scrub.detections` OTel counter (one record per entity type, tagged with `entity_type` and `operation`) and a `pii.scrubbed` span event for trace-level visibility. Counter is a no-op when Dynatrace is not configured.
- Dynatrace's built-in PII/guardrail tiles only work for providers with native guardrail APIs (Bedrock, Azure OpenAI). This custom counter is the only way to surface Presidio scrubbing events in Dynatrace.
- **DQL for single-value total scrub count tile:**
  ```dql
  timeseries detections = sum(security.pii.scrub.detections), from:now()-30d
  | fieldsAdd total = arraySum(detections)
  | summarize total = sum(total)
  ```
  Do **not** add `by:{entity_type, operation}` — grouped `timeseries` produces multiple series and cannot be displayed as a single value. Use a table/bar chart tile for the per-type breakdown.
- **DQL gotcha:** `append` is not a valid DQL command. To handle the zero-data case, set "No data" → `0` in the tile's visualization settings instead.

Session 10 complete. Research/advisory session — no code changes. Investigated Dynatrace cost tile accuracy, Claude API pricing, and prompt caching.

Key findings:
- **Dynatrace built-in cost tile is inaccurate.** It sums all token types without splitting by `gen_ai.token.type`, then applies a simple average of input and output rates — overestimates when input tokens >> output tokens (the norm). Correct DQL splits by type and applies the right rate to each.
- **Correct cost DQL pattern:**
  ```dql
  timeseries tokens = sum(gen_ai.client.token.usage), by:{gen_ai.token.type}
  | fieldsAdd token_sum = arraySum(tokens)
  | fieldsAdd rate = if(gen_ai.token.type == "input", <input_rate>, else:<output_rate>)
  | fieldsAdd cost = token_sum * rate
  | summarize total_cost = sum(cost)
  ```
- **`timeseries` returns empty if the dashboard time range has no data.** Pin an explicit range (`from:now()-30d`) in cost tiles.
- **Prompt caching not used and not worth adding.** `_AGENTIC_SYSTEM` + tool definitions are ~400–500 tokens — below the 1024-token minimum cacheable size for Sonnet. Volume is too low to matter anyway.
- **All three Claude call sites use `claude-sonnet-4-6`.** `enrich_entry` and `extract_entities` are simple JSON extraction tasks — could swap to Haiku (~10× cheaper) if cost becomes a concern. `chat_turn` should stay on Sonnet.
- **Prompt caching token types:** If caching is ever added, `_record_usage()` would need three separate histogram records (`input`, `cache_read`, `cache_write`) to support accurate cost math. Currently all are summed to `input` per OTel convention — correct since caching is off.

Session 9 complete. Research/reference session — no code changes. Reviewed the official Dynatrace Global Field Reference to validate the gen_ai span attribute names and DQL query fixes from Session 8. Key confirmations:
- `span.status_code` legal values are `"ok"` and `"error"` only (null = unset). Session 8's failure-rate DQL fix is spec-correct.
- `gen_ai.provider.name` is the newer official field (`openai`, `aws_bedrock`). Traceloop currently emits `gen_ai.system` — both should be checked in DQL filters.
- `dt.service.request.count` / `dt.service.request.failure_count` are not part of any standard Dynatrace or OTel metric schema — those metric names were invented. Service request count tiles should be built from spans, not from those metric names.
- `gen_ai.client.token.usage` histogram and `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` span attributes confirmed correct per spec.

Session 8 complete. Added `_record_usage()` helper to `claude.py` — attaches `gen_ai.*` token-usage attributes to the active OTel span after every Anthropic API call, and emits the `gen_ai.client.token.usage` OTLP histogram metric. Added `_record_usage()` helper to `claude.py` — attaches `gen_ai.*` token-usage attributes to the active OTel span after every Anthropic API call, and emits the `gen_ai.client.token.usage` OTLP histogram metric. Key implementation details:
- `gen_ai.usage.input_tokens` — sums `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.request.model`, `gen_ai.operation.name`, `gen_ai.response.finish_reasons` set on span
- `gen_ai.client.token.usage` histogram (OTLP metric) — one record per token type (`input`/`output`), tagged with operation and model
- Span attributes and histogram recording are now **independent** — span guard only gates attribute setting, not metric recording
- `MeterProvider` is owned directly (not via global OTel API) to prevent Traceloop from overriding it on first request
- `core/telemetry.py` holds the histogram reference to avoid circular imports
- `force_flush()` + `shutdown()` called in lifespan teardown so buffered metrics aren't lost on container restart
- Applied to all three call sites: `enrich_entry`, `extract_entities`, `chat_turn`

**Dynatrace gotcha found this session:** The built-in AI Observability failure-rate tile uses `isNull(span.status_code)` for success. Traceloop sets `span.status_code = "ok"` on successful spans, causing 100% false failure rate. Fix the DQL query: `success=countIf(isNull(span.status_code) or span.status_code == "ok")`.

Session 7 complete + confirmed working. Auto-instrumentation via OpenLLMetry (Traceloop) for Dynatrace.

Previous sessions: Chunk RAG + Tavily fix, Layer 2e Agentic Chat, Layer 2 Entity Model, async fix, OOM fix, markdown rendering.

**Session 14 changes (2026-04-02):**
- `backend/scripts/gmail_auth.py`: replaced `run_local_server()` with custom `HTTPServer('0.0.0.0', 8090)` — `run_local_server()` binds to container's 127.0.0.1, Docker port mapping can't reach it.
- `docker-compose.yml`: removed `db` service (deployment uses postgres01 on dock12), removed `:ro` from gmail_token mount (backend rewrites token on refresh), `DATABASE_URL` now required with no default.
- Google OAuth app published to production — no more 7-day token expiry.

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
