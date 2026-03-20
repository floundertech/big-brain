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
