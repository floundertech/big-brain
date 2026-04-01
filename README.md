# Big Brain

A self-hosted second brain. Paste notes, upload transcripts, and ask questions across everything you've captured. Claude auto-titles, summarizes, tags, and extracts people and companies from every entry. Click any person or organization to see everything you know about them.

No cloud storage. No SaaS. Your data stays on your hardware.

## Stack

| Layer | Tech |
|---|---|
| LLM | Claude API (claude-sonnet-4-6) |
| Embeddings | fastembed + nomic-embed-text-v1.5 (local CPU, no GPU needed) |
| Storage | PostgreSQL + pgvector |
| Backend | FastAPI (Python 3.11) |
| Frontend | React + Tailwind (Vite) |
| Runtime | Docker Compose |

Only paid dependency: Anthropic API key (you probably already have one).

---

## Setup

### Prerequisites

- Docker + Docker Compose
- An [Anthropic API key](https://console.anthropic.com/)

### First run

```bash
git clone https://github.com/floudertech/big-brain
cd big-brain
cp .env.example .env
```

Open `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...          # required
POSTGRES_PASSWORD=something-strong    # change from default
```

Then:

```bash
docker compose up -d
```

- Frontend: http://localhost:3000
- API: http://localhost:8000/docs

**First startup takes 2–5 minutes.** The backend downloads the embedding model (~520MB) on first run and caches it in a Docker volume. Subsequent starts are instant.

### LAN / VPN access (phone, tablet, other machines)

Set your server's IP in `.env` before starting:

```env
VITE_API_URL=http://192.168.1.x:8000
```

Then rebuild the frontend container:

```bash
docker compose up -d --build frontend
```

The frontend bakes the API URL at build time (Vite env vars), so you need to rebuild when changing it.

### Proxmox / homelab setup

If running in an LXC or VM:

- Expose ports 3000 and 8000 to your LAN, or put behind a reverse proxy (Nginx, Caddy, Traefik)
- If behind a reverse proxy with HTTPS, set `VITE_API_URL` to the HTTPS URL of your API
- The embedding model download happens inside the container — no host-level setup needed
- DB data persists in the `db_data` Docker volume; embedding cache in `embed_cache`

### Updating

```bash
git pull
docker compose up -d --build
```

The DB schema is managed via `CREATE TABLE IF NOT EXISTS` on startup — new tables are created automatically, existing data is preserved.

**After updating to chunk-based RAG (Session 6+):** Run the reindex endpoint once to backfill chunk embeddings for entries ingested before the update:
```bash
curl -X POST http://localhost:8000/entries/reindex
```
Without this, old entries will still be searchable via legacy entry-level embeddings, but results on long transcripts will be less precise.

---

## Features

### Add
Paste text directly or upload a `.txt` file. Claude automatically generates:
- Title
- 2–3 sentence summary
- Tags
- Extracted people and organizations (linked as entities)

Set `source_type` to `note` or `transcript` to categorize the entry.

### Browse
List all entries, filterable by source type. Click any entry to view full detail.

### Search
Semantic vector search — finds conceptually relevant entries, not just keyword matches. Powered by local embeddings (no external API calls).

### Chat
Agentic chat: Claude searches your notes, looks up entities, and optionally searches the web or saves new entries. For local knowledge questions it searches silently and answers directly. For web research it asks before searching (to keep costs visible), and asks before saving anything.

### RSS / Miniflux connector (optional)
Automatically ingests articles from your [Miniflux](https://miniflux.app/) RSS reader. The poller runs every hour (configurable), fetches new articles via the Miniflux API, and stores them as searchable entries with full embeddings and entity extraction. A daily digest is generated via Haiku summarizing the previous day's articles, with relevance flagging for topics you care about.

**Setup:**
1. Generate an API key in your Miniflux instance: Settings → API Keys
2. Add to `.env`:
   ```env
   # Use host.docker.internal (Mac) or host IP — NOT localhost (backend runs in a container)
   MINIFLUX_URL=http://host.docker.internal:8070
   MINIFLUX_API_KEY=your-api-key-here
   ```
3. Restart: `docker compose up -d --build backend`

The poller starts automatically. On first run it backfills the last 30 days of articles (configurable via `RSS_INITIAL_BACKFILL_DAYS`).

**Optional config:**
```env
RSS_POLL_INTERVAL_SECONDS=3600          # how often to check for new articles
RSS_DIGEST_HOUR=5                       # hour (24h UTC) to generate daily digest
RSS_RELEVANCE_TOPICS=Dynatrace,CVE,zero-day  # topics to flag in digest
RSS_INITIAL_BACKFILL_DAYS=30            # days to backfill on first run
```

**How it works:**
- Articles are stored as `source_type="rss"` entries with feed metadata (category, author, article URL) in the `meta` column
- Titles come from the feed (not Claude-generated) — `enrich_entry()` is skipped for RSS
- Dedup uses `meta->>'miniflux_entry_id'` with a partial expression index
- Daily digest (`source_type="rss_digest"`) is generated by Haiku, rendered as markdown, and stored as a searchable entry
- Per-article summaries from the digest are backfilled into individual article entries
- The digest scheduler is idempotent — checks every 15 minutes, safe across restarts
- Miniflux read state is never touched — Big Brain and Miniflux are independent
- If Miniflux is not configured, the poller silently disables itself

**Testing endpoints:**
```bash
curl http://localhost:8000/rss/status           # polling status and counts
curl -X POST http://localhost:8000/rss/poll     # manually trigger a poll
curl -X POST http://localhost:8000/rss/digest/generate  # manually trigger digest
curl http://localhost:8000/rss/digest/latest    # view latest digest
```

### Home page
The landing page (`/`) surfaces a daily digest, recent activity feed across all source types, and a quick-ask prompt bar that redirects to chat. Browse has moved to `/entries`.

### Gmail connector (optional)
Label any Gmail message `big-brain` → it gets ingested automatically. The poller runs every 5 minutes (configurable). After ingestion the label is swapped to `big-brain/done`.

**One-time setup:**
1. Create a Google Cloud project, enable the Gmail API, and create an OAuth 2.0 Desktop App credential at [console.cloud.google.com](https://console.cloud.google.com)
2. Download the credential JSON and save it as `credentials.json` in the project root (gitignored)
3. Run the auth script once (outside Docker — needs a browser):
   ```bash
   pip install google-api-python-client google-auth-oauthlib
   python backend/scripts/gmail_auth.py
   ```
4. `gmail_token.json` is written to the project root (gitignored). Restart the app — the poller starts automatically.

### Entities
People (contacts) and organizations are extracted automatically from every entry and stored as first-class entities with rich metadata, relationships, and linked interactions.

- **Entity list** (`/entities`): searchable, filterable by type (contact/organization), with inline creation
- **Entity detail pages**: click any entity name to see their full profile — metadata, relationships, contacts (for orgs), linked interactions, and related research
- **Inline editing**: click any field on an entity detail page to edit it (title, industry, status, notes, etc.)
- **Relationships**: link contacts to organizations (works_at), track reporting lines, partnerships
- **Chat tools**: create, update, and link entities directly from the chat interface
- **Semantic matching**: new entities are matched against existing ones using embedding similarity to prevent duplicates
- API: `GET /entities/`, `POST /entities/`, `PATCH /entities/:id`, `DELETE /entities/:id`, relationship and linking endpoints

### PII Scrubbing
Structured PII (Social Security numbers, driver's license numbers, credit cards, passports, bank account numbers, ITINs, IBANs) is automatically scrubbed before any text is sent to external APIs (Claude, Tavily). Names and general text pass through untouched — they're needed for entity extraction. Your raw data stored locally in Postgres is never modified.

---

## Ingest from Plaud

1. Export transcript as `.txt` from the Plaud app
2. Go to **Add → Upload .txt**, set type to `transcript`, upload
3. Done — indexed, searchable, and entities extracted in seconds

---

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | From console.anthropic.com |
| `POSTGRES_PASSWORD` | No | `changeme` | Change before exposing to network |
| `VITE_API_URL` | No | `http://localhost:8000` | Set to server IP for LAN access |
| `EMBED_MODEL` | No | `nomic-ai/nomic-embed-text-v1.5` | Override embedding model |
| `TAVILY_API_KEY` | No | — | Enables web search in chat. Free plan at tavily.com (1,000 searches/month). |
| `DT_OTLP_ENDPOINT` | No | — | Dynatrace OTLP endpoint for LLM tracing. Format: `https://{env-id}.live.dynatrace.com/api/v2/otlp` |
| `DT_API_TOKEN` | No | — | Dynatrace API token. Needs scopes: `openTelemetryTrace.ingest`, `metrics.ingest`, `logs.ingest`. Both this and `DT_OTLP_ENDPOINT` must be set to enable tracing. When enabled, each Anthropic call emits span attributes (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.request.model`) **and** the `gen_ai.client.token.usage` OTLP histogram metric, queryable via `timeseries t=sum(gen_ai.client.token.usage)`. |
| `GMAIL_POLL_INTERVAL_SECONDS` | No | `300` | How often the Gmail poller checks for new labeled messages. |
| `GMAIL_INGEST_LABEL` | No | `big-brain` | Gmail label to watch for messages to ingest. |
| `GMAIL_DONE_LABEL` | No | `big-brain/done` | Label applied after successful ingestion (replaces ingest label). |
| `GMAIL_LABEL_CUSTOMER` | No | `big-brain/customer` | Gmail label for customer interaction pipeline routing. |
| `GMAIL_LABEL_RESEARCH` | No | `big-brain/research` | Gmail label for research pipeline routing. |
| `GMAIL_LABEL_REFERENCE` | No | `big-brain/reference` | Gmail label for reference pipeline routing. |
| `GMAIL_REMOVE_LABEL_AFTER_PROCESSING` | No | `false` | Remove routing label after processing (instead of keeping it). |
| `MINIFLUX_URL` | No | — | Miniflux instance URL. Use `host.docker.internal` or host IP, not `localhost`. Both this and `MINIFLUX_API_KEY` must be set to enable RSS. |
| `MINIFLUX_API_KEY` | No | — | API key from Miniflux Settings → API Keys. |
| `RSS_POLL_INTERVAL_SECONDS` | No | `3600` | How often to check Miniflux for new articles. |
| `RSS_DIGEST_HOUR` | No | `5` | Hour (24h UTC) to generate the daily digest. |
| `RSS_DIGEST_MODEL` | No | `claude-haiku-4-5-20251001` | Model for digest summarization. Haiku keeps costs near zero. |
| `RSS_RELEVANCE_TOPICS` | No | — | Comma-separated topics to flag in digests (e.g. `Dynatrace,CVE,zero-day`). |
| `RSS_INITIAL_BACKFILL_DAYS` | No | `30` | How many days back to ingest on first run. |

---

## Data model

```
entries
  id            serial PK
  created_at    timestamptz
  updated_at    timestamptz
  title         text              ← generated by Claude
  source_type   text              ← "note" | "transcript" | "research" | "email" | "rss" | "rss_digest"
  raw_text      text
  summary       text              ← generated by Claude
  tags          text[]            ← generated by Claude
  embedding     vector(768)       ← nomic-embed-text-v1.5 (entry-level, legacy)
  meta          jsonb             ← source URL etc. for research entries

chunks
  id            serial PK
  entry_id      FK → entries.id  (cascade delete)
  chunk_index   int
  text          text
  embedding     vector(768)       ← per-chunk embedding for deep search

entities
  id            serial PK
  entity_type   text              ← "contact" | "organization"
  name          text              ← normalized, unique per type
  meta          jsonb             ← type-specific fields (title, industry, email, etc.)
  embedding     vector(768)       ← semantic search for entity matching
  created_at    timestamptz
  updated_at    timestamptz

entity_relationships
  id            serial PK
  source_entity_id  FK → entities.id
  target_entity_id  FK → entities.id
  relationship_type text          ← "works_at" | "reports_to" | "formerly_at" | etc.
  meta          jsonb
  created_at    timestamptz

entry_entity_links
  id            serial PK
  entry_id      FK → entries.id  (cascade delete)
  entity_id     FK → entities.id (cascade delete)
  link_type     text              ← "mention" | "about" | "from" | "to"
  confidence    float             ← 1.0 for manual, <1.0 for auto
  created_at    timestamptz

settings
  key           varchar(100) PK   ← e.g. "rss_last_poll_timestamp"
  value         jsonb             ← runtime state that must survive restarts
```

---

## API

Interactive docs at http://localhost:8000/docs (Swagger UI).

Key endpoints:

```
POST   /entries/           Create entry from text
POST   /entries/upload     Create entry from .txt file
GET    /entries/           List entries (filter: tag, source_type, limit, offset)
GET    /entries/{id}       Entry detail
DELETE /entries/{id}       Delete entry

PATCH  /entries/{id}       Update entry content/metadata

GET    /entities/          List entities (filter: entity_type, search: q)
GET    /entities/{id}      Entity detail with relationships and linked entries
POST   /entities/          Create entity
PATCH  /entities/{id}      Update entity fields
DELETE /entities/{id}      Delete entity
POST   /entities/{id}/relationships    Add relationship
DELETE /entities/relationships/{id}    Remove relationship
POST   /entities/entries/{id}/entities Link entry to entity
DELETE /entities/entry-entity-links/{id} Unlink

GET    /search/?q=...      Semantic search
POST   /chat/              RAG chat

GET    /rss/status         RSS polling status and counts
POST   /rss/poll           Manually trigger Miniflux poll
GET    /rss/digest/latest  Most recent digest
GET    /rss/digest/{date}  Digest for a specific date (YYYY-MM-DD)
POST   /rss/digest/generate  Manually trigger digest generation

GET    /home/digest        Latest digest for home page
GET    /home/activity      Recent activity feed (last 10 entries)
GET    /home/suggestions   Quick Ask suggestions

GET    /health             Health check
```

---

## Troubleshooting

**500 error on every upload / "Could not resolve authentication method"**
The `ANTHROPIC_API_KEY` is missing or empty. Docker Compose reads it from `.env` in the project root — it does not fall through from your shell environment.
```bash
cp .env.example .env   # if you haven't already
# edit .env and set ANTHROPIC_API_KEY=sk-ant-...
docker compose down && docker compose up -d
```
Confirm it loaded: `docker compose exec backend env | grep ANTHROPIC`

**Backend fails to start / DB connection refused**
The backend waits for Postgres to be healthy before starting. If it fails, check:
```bash
docker compose logs db
docker compose logs backend
```

**Embedding model download fails**
The model downloads from HuggingFace on first run. If behind a firewall or the download fails partway, restart the backend container:
```bash
docker compose restart backend
```

**Frontend shows "Network Error"**
`VITE_API_URL` is baked in at build time. If you changed it, rebuild:
```bash
docker compose up -d --build frontend
```

**Backend exits with code 137 (OOM kill) on first large upload**
The container was killed by the OS out-of-memory killer. Most likely the embedding model hadn't loaded yet and the combined memory spike exceeded available RAM. As of the current build, the model pre-loads at startup to prevent this. If it still happens, your host has less than ~1 GB free. Switch to a lighter model:
```env
# in .env
EMBED_MODEL=BAAI/bge-small-en-v1.5
EMBED_DIM=384
```
Then wipe the DB (vectors are stored at a fixed dimension and must match) and rebuild:
```bash
docker compose down -v
docker compose up -d --build
```

**Chat web search returns "Tavily API key not configured"**
Set `TAVILY_API_KEY=tvly-...` in `.env` (free plan at tavily.com), then restart the backend: `docker compose up -d --build backend`.

**Updating from a version before agentic chat (meta column missing)**
The `meta` column was added to `entries` in Layer 2e. If you're updating an existing install, run this once:
```bash
docker compose exec db psql -U postgres bigbrain -c "ALTER TABLE entries ADD COLUMN IF NOT EXISTS meta jsonb;"
```

**Backend build fails with `ResolutionImpossible` / opentelemetry dependency conflict**
`traceloop-sdk` beta sub-packages each pin `opentelemetry-instrumentation` to their exact beta version, which pip can't satisfy simultaneously. This is a known issue with `==0.33.11`. The `requirements.txt` now uses `>=0.33.11` to let pip find a compatible newer version. If you're on an older checkout, update:
```bash
git pull && docker compose up -d --build backend
```

**LLM traces not appearing in Dynatrace**
Check that both `DT_OTLP_ENDPOINT` and `DT_API_TOKEN` are set in `.env` and forwarded to the container. Confirm the token has `openTelemetryTrace.ingest` scope. Check backend logs on startup — Traceloop logs whether it initialized successfully:
```bash
docker compose logs backend | grep -i traceloop
```

**`gen_ai.client.token.usage` metric not appearing / `timeseries` query returns empty**
The metric is exported via a separate `MeterProvider` (not Traceloop). Check that `DT_API_TOKEN` also has `metrics.ingest` scope. Metrics flush every 15 seconds — wait at least 15s after a Claude API call before querying. On restart, buffered metrics are force-flushed during lifespan shutdown.

**Dynatrace AI Observability tile shows 100% failure rate**
This is a bug in the built-in tile. Its DQL uses `isNull(span.status_code)` as the success condition, but Traceloop correctly sets `span.status_code = "ok"` on successful spans, which the query misreads as failure. Clone the dashboard tile and change the condition to:
```dql
success=countIf(isNull(span.status_code) or span.status_code == "ok")
```

**Chat search misses content in long transcripts (entries ingested before Session 6)**
The chunk-based search index needs to be backfilled. Run once:
```bash
curl -X POST http://localhost:8000/entries/reindex
```

**Gmail connector not ingesting messages**
Check that `gmail_token.json` exists in the project root and is mounted into the container. Backend logs will show `Gmail token not found — poller disabled` on startup if it's missing. If the token is expired, re-run `python backend/scripts/gmail_auth.py`. The poller watches multiple labels: `big-brain`, `big-brain/customer`, `big-brain/research`, `big-brain/reference`. Use the routed labels to classify emails into different pipelines.

**Updating from a version before the entity system overhaul**
The entity type `person` has been renamed to `contact` and the `entry_entities` table has been replaced by `entry_entity_links`. These migrations run automatically on startup via `init_db()`. If you need to run them manually:
```bash
docker compose exec db psql -U postgres bigbrain -c "
  ALTER TABLE entities ADD COLUMN IF NOT EXISTS meta jsonb;
  ALTER TABLE entities ADD COLUMN IF NOT EXISTS embedding vector(768);
  ALTER TABLE entities ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
  UPDATE entities SET entity_type = 'contact' WHERE entity_type = 'person';
"
```

**Updating from a version before Gmail connector (`gmail_message_id` column missing)**
Run once against the existing DB:
```bash
docker compose exec db psql -U postgres bigbrain -c "ALTER TABLE entries ADD COLUMN IF NOT EXISTS gmail_message_id varchar(200) UNIQUE;"
```

**Wipe everything and start fresh**
```bash
docker compose down -v   # -v removes volumes including DB data
docker compose up -d
```
