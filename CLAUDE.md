# TinyFish — Self-Healing Regulatory Knowledge Graph

A compliance automation system that extracts regulatory data from government websites, maintains a versioned knowledge graph, and auto-fills compliance forms with confidence scoring.

**Current target:** ACRA (Accounting and Corporate Regulatory Authority) — Withdrawal from Being Approved Liquidators
**Stack:** Python, TinyFish (web extraction), OpenAI (reasoning), SQLite (knowledge graph)
**Status:** Phase 10 (frontend integration) complete. PDF fill + GitHub upload + TinyFish autofill wired.

---

## Project Structure

```
TINYFISH/
├── data/
│   ├── form.html             # BizFile+ mock form (bypasses Singpass)
│   ├── review.html           # BizFile+ mock review page
│   ├── frontend_payload.js   # Generated JS payload for Regulator demo
│   ├── CSP_Update registered qualified individual information.pdf  # ACRA form (45 AcroForm fields)
│   └── filled/               # Output directory for filled PDFs
├── db/
│   └── schema.sql            # 3 tables: nodes, node_versions, graph_meta
├── graph/
│   ├── __init__.py            # Re-exports Node + all store functions + hash_json
│   ├── store.py               # Async SQLite CRUD (aiosqlite)
│   ├── models.py              # Node dataclass
│   └── utils.py               # hash_json() utility
├── layers/
│   ├── __init__.py
│   ├── layer0_seed.py         # OpenAI skeleton + goal generation
│   ├── layer1_canary.py       # Seed page hash check
│   ├── layer2_extract.py      # Parallel TinyFish fan-out + 404 repair
│   ├── layer3_diff.py         # OpenAI semantic diff
│   ├── layer4_form.py         # Form filling + confidence scoring
│   ├── layer5_pdf_fill.py     # PDF AcroForm filling (pypdf + OpenAI field mapping)
│   ├── layer6_upload.py       # GitHub Contents API upload
│   └── layer7_autofill.py     # TinyFish browser autofill of mock portal
├── clients/
│   ├── __init__.py            # Re-exports TinyFishClient
│   ├── tinyfish.py            # TinyFish API wrapper (httpx async)
│   └── openai_client.py       # OpenAI wrapper (chat_json)
├── tests/
│   ├── test_db.py             # Phase 1: DB + store tests
│   ├── test_tinyfish.py       # Phase 2: TinyFish client (live API)
│   ├── test_seed.py           # Phase 3: Graph seeding (live OpenAI)
│   ├── test_canary.py         # Phase 4: Canary check (mocked)
│   ├── test_extract.py        # Phase 5: Extraction (mocked)
│   ├── test_diff.py           # Phase 6: Semantic diff (mocked)
│   ├── test_form.py           # Phase 7: Form filling (pure logic)
│   ├── test_repair.py         # Phase 9: 404 repair (mocked)
│   ├── test_pdf_fill.py       # Phase 10: PDF filling (mocked OpenAI)
│   ├── test_upload.py         # Phase 10: GitHub upload (mocked httpx)
│   └── test_autofill.py       # Phase 10: TinyFish autofill (mocked)
├── run.py                     # Main orchestration: python run.py [form_path]
├── config.py                  # API keys, constants (dotenv)
├── sample_form.json           # ACRA withdrawal form definition (5 fields)
├── requirements.txt           # aiosqlite, python-dotenv, httpx, openai
├── .env                       # API keys (not committed)
└── .gitignore
```

---

## Current Form: ACRA Withdrawal from Approved Liquidators

**sample_form.json** defines 5 fields:
- `lodgement_description` — Correct wording for the BizFile+ lodgement
- `required_form_pdf` — Which PDF form to download and attach
- `required_supporting_docs` — Supporting documents needed
- `eligibility_criteria` — Prerequisites for withdrawal
- `applicable_fees` — Filing fees

**Mock HTML (data/):** BizFile+ form and review pages are mocked to bypass Singpass authentication. The frontend will drive the demo using backend JSON output to simulate form autofill.

---

## Pipeline Flow

```
python run.py sample_form.json
```

1. **Seed** (layer0) — OpenAI generates navigation skeleton + extraction goals → writes nodes to SQLite
2. **Canary** (layer1) — TinyFish fetches seed page, hashes it, compares against stored baseline
3. **Extract** (layer2) — TinyFish batch extracts all nodes in parallel, hashes results
4. **Repair** (layer2) — Failed nodes attempt URL repair via parent_url navigation
5. **Diff** (layer3) — OpenAI compares changed nodes against prior versions (material/cosmetic/ambiguous)
6. **Fill** (layer4) — Maps results to form fields with confidence scoring → outputs JSON
7. **PDF Fill** (layer5) — OpenAI maps pipeline fields to PDF AcroForm names, pypdf fills them
8. **Upload** (layer6) — Filled PDF uploaded to GitHub via Contents API → raw URL
9. **Autofill** (layer7) — TinyFish navigates locally-served mock BizFile+ portal, fills web form + uploads PDF

**Output:** JSON with per-field values, confidence levels (high/review_required/missing), summary counts, and autofill result.

---

## Key Interfaces

### config.py
```python
TINYFISH_API_KEY = os.environ["TINYFISH_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DB_PATH = "regflow.db"
OPENAI_MODEL = "gpt-4o"
SEED_URL = "https://www.acra.gov.sg"
```

### store.py (all async, all accept optional db_path)
```
init_db, upsert_node, get_node, get_nodes_by_form_fields,
save_version, update_node_url, get_prior_version, get_meta, set_meta
```

### TinyFish API (ref: .claude/rules/tinyfish_api.md)
- Auth: `X-API-Key` header
- `browser_profile`: `"lite"` | `"stealth"`
- run_single uses POST /v1/automation/run-sse (SSE streaming)
- run_batch uses POST /v1/automation/run-batch + GET /v1/runs/{id} polling (5s interval, 300s timeout)

### OpenAI Client
- `chat_json(system_prompt, user_content, model?)` → parsed dict
- Strips markdown fences, temperature=0, lazy singleton AsyncOpenAI

### Confidence Rules
```
hash unchanged        → high,            review: False
diff: cosmetic        → high,            review: False
diff: material        → review_required, review: True
diff: ambiguous       → review_required, review: True
error_404/error_other → missing,         review: True
no node for field     → missing,         review: True
```

---

## Architectural Decisions Log

- All store.py functions are async (aiosqlite) with optional db_path param for testability
- upsert_node uses ON CONFLICT(url) DO UPDATE to preserve row IDs
- update_node_url does direct SQL UPDATE (preserves row ID + version history)
- get_nodes_by_form_fields uses Python-side JSON filtering for SQLite compatibility
- schema.sql uses IF NOT EXISTS for idempotent init_db()
- TinyFish auth is X-API-Key header, browser_profile is "lite"|"stealth"
- run_batch uses /run-batch + GET /runs/{id} polling (5s interval, 300s timeout)
- OpenAI chat_json() strips markdown fences, uses temperature=0, lazy singleton client
- hash_json(data) in graph/utils.py — SHA-256 of json.dumps(sort_keys=True)
- Canary first run = "stable" (baseline establishment, not false alarm)
- Canary/extraction on fetch error: stored hash/content preserved (no corrupt baseline)
- ExtractionResult + DiffResult are transient dataclasses in their respective layer files
- save_version called for all successful extractions (unchanged + changed) for full audit trail
- Batch chunked at 100 to respect TinyFish API limit
- get_prior_version uses ORDER BY id DESC OFFSET 1 (id tiebreaker, not timestamp)
- First-time extractions skip OpenAI diff, return synthetic "material" DiffResult
- OpenAI diff failures fall back to "ambiguous" (conservative for human review)
- fill_form is synchronous (no I/O) — pure data mapping
- Multiple nodes per field: successful ER preferred over error ER
- repair_404 integrated into parallel_extract — transparent to orchestrator
- MAX_REPAIRS=5 cap per run to control TinyFish API costs
- Seeding prompt is generic (not MAS/ACRA specific) — works with any regulatory authority
- Monkeypatching import-by-name: patch the consuming module's reference, not the source
- Tests use separate test_regflow.db with cleanup in finally block
- venv required — never pip install into system Python
- ACRA CSP_Update PDF has 45 AcroForm fillable fields — pypdf clone_from preserves AcroForm dict
- PdfWriter(clone_from=path) required to keep AcroForm; append_pages_from_reader loses it
- OpenAI maps abstract field IDs (lodgement_description, etc.) to PDF field names (Name, Email Address, etc.)
- GitHub upload uses Contents API (PUT /repos/{owner}/{repo}/contents/{path}) with base64 encoding
- GitHub token sourced from `gh auth token` subprocess
- TinyFish autofill uses run_single (SSE) against locally-served form.html on localhost:8080
- Autofill goal is concrete step-by-step instructions (not abstract) for reliable browser automation
- GITHUB_REPO constant in config.py (jeromepaulteoh/Shikigami)
- Frontend payload generated as both JSON and JS (window.REGULATOR_PAYLOAD) from pipeline output

---

## Completed Phase: Frontend Integration (Phase 10)

**What was built:**
1. `layer5_pdf_fill.py` — Fills ACRA PDF AcroForm fields using pypdf + OpenAI field mapping
2. `layer6_upload.py` — Uploads filled PDF to GitHub via Contents API, returns raw URL
3. `layer7_autofill.py` — TinyFish navigates mock BizFile+ portal, fills web form + uploads PDF
4. Pipeline wired: fill_form → fill_pdf → upload_to_github → run_autofill
5. Frontend payload generation from live pipeline output (frontend_payload.js)

**Demo run:**
1. Start local server: `python -m http.server 8080 --directory data`
2. Run pipeline: `python run.py sample_form.json`
3. Open `Regulator_Demo_Tinyfish.html` to see the demo flow

---

## Demo User Flow: ACRA Withdrawal From Being Approved Liquidators

1. **User uploads the target form** — The run starts from the ACRA withdrawal form
2. **OpenAI preprocesses the form** — Converts to structured fields and extraction goals
3. **System seeds the knowledge graph** — Stores relevant ACRA pages, relationships, and field mappings
4. **TinyFish traces ACRA website** — Uses the graph to navigate and extract relevant information
5. **System compares against version history** — Hashes and diffs to detect changes
6. **Changes reflected in frontend** — Shows detected changes for user review; refreshes graph
7. **No changes → form filled as usual** — Reviewed results populate the form output
8. **Canary monitors site structure** — Regular checks for major ACRA website changes
9. **Autofill simulated in demo** — Frontend shows form-filling driven by backend output; no real submission
