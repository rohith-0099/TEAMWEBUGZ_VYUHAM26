# 03 — BACKEND CORE: API, database, ingestion, IOC engine, exports

> **AI agent instructions:** You are building the backend foundation of TRINETRA. First read `team/00_SHARED_CONTRACTS.md` completely. Then build exactly what this file says, in the order given. Keep code **simple and readable**: plain functions, plain SQL, no clever abstractions, no ORM. The person you're helping is newer to backend work, so add short comments explaining *why*, and make every step runnable and testable on its own. Do not change shared data models (`app/models.py`, owned by the Lead) or other people's files.

**Person:** Backend Core
**You own:** `docker-compose.yml`, `.env.example`, `backend/Dockerfile`, `backend/requirements.txt`, `backend/db/schema.sql`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/api/routes.py`, `backend/app/utils/text.py`, `backend/app/attack/allowlists/benign_domains.txt`, `backend/app/pipeline/ingest.py`, `backend/app/pipeline/ioc.py`, `backend/app/pipeline/notify.py`, `backend/app/exports/stix.py`, `backend/app/exports/navigator.py`, and (NICE) `backend/app/pipeline/geo.py`, `backend/scripts/watch.py`, the n8n workflow.

---

## 1. Where you fit

```
Frontend ──HTTP──► routes.py (YOU) ──► runner.start_analysis (Lead)
                                         │
              ingest.py (YOU) ◄──────────┤  stage 1
              ioc.py    (YOU) ◄──────────┤  stage 3 (deterministic IOC engine)
                                         │  ... other stages (RAG person, Lead)
              db.py     (YOU) ◄──────────┤  save results
              exports/stix.py, navigator.py (YOU) ◄── export route
              notify.py (YOU) ◄── Lead calls on alerts → n8n → Telegram
```
You build the **pipes and the first two engines**. Everyone else plugs into your server and database. If your part is solid early, the whole team moves fast.

---

## 2. Tech stack (what you use and where)

| Tool | pip / image | Used in | Why |
|---|---|---|---|
| Python 3.11 | `python:3.11-slim` | everywhere | |
| FastAPI | `fastapi` | `main.py`, `routes.py` | web API |
| Uvicorn | `uvicorn[standard]` | Docker command | runs FastAPI (**1 worker only** — live events live in memory) |
| python-multipart | `python-multipart` | PDF upload route | FastAPI needs it for file uploads |
| pydantic-settings | `pydantic-settings` | `config.py` | read `.env` |
| psycopg 3 + pool | `psycopg[binary]`, `psycopg-pool` | `db.py` | talk to Postgres |
| pgvector (python) | `pgvector` | `db.py` pool setup | lets psycopg send/receive vectors (RAG person needs it) |
| sse-starlette | `sse-starlette` | `routes.py` | live event stream |
| firecrawl-py | `firecrawl-py` | `ingest.py` | URL/PDF → clean markdown |
| httpx | `httpx` | `ingest.py`, `notify.py` | HTTP client |
| trafilatura | `trafilatura` | `ingest.py` | fallback web page → text |
| pdfplumber | `pdfplumber` | `ingest.py` | uploaded PDF → text |
| iocsearcher | `iocsearcher` | `ioc.py` | finds IOCs incl. defanged ones |
| stix2 | `stix2` | `exports/stix.py` | builds valid STIX 2.1 |
| maxminddb (NICE) | `maxminddb` | `geo.py` | offline IP → location |
| pytest | `pytest`, `pytest-asyncio` | `tests/` | tests |
| Postgres + pgvector | image `pgvector/pgvector:pg16` | compose | the only database |

Other people will add their own packages to `requirements.txt` (LangGraph, LiteLLM, fastembed, NetworkX, pySigma, mitreattack-python, rapidfuzz). Accept their PRs. After the first full successful install, **pin versions** with `pip freeze > requirements.lock` and use the lock in Docker.

---

## 3. Step-by-step build order

### Step 0 — Start from the skeleton
The Lead's skeleton repo already contains every file below as a **working first version or stub** (compose, Dockerfile, schema, config, db, main, routes returning mock data). Your job is to **own, finish and harden** them. After cloning: create branch `feat/backend-core`, run `docker compose up --build`, confirm `GET /api/health` works, then follow the steps. Where a step's code already exists, compare it with this spec and complete it.

### Step 1 (45 min) — Project + Docker + DB running (verify and harden)

**`docker-compose.yml`**
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: trinetra
      POSTGRES_PASSWORD: trinetra
      POSTGRES_DB: trinetra
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U trinetra"]
      interval: 3s
      retries: 20
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    depends_on:
      db: { condition: service_healthy }
    volumes: ["./backend:/app", "./data:/data"]   # live reload in dev; /data for geo db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload
volumes:
  pgdata:
```

**`backend/Dockerfile`**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download the embedding model so the first request isn't slow (RAG person's model)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" || true
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**`.env.example`** — copy contracts §10 exactly. Create your own `.env` (never commit it; add `.env` to `.gitignore`).

**`backend/db/schema.sql`** — copy contracts §7 exactly.

**`backend/app/config.py`**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://trinetra:trinetra@localhost:5432/trinetra"
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_extract_model: str = ""
    llm_verify_model: str = ""
    llm_concurrency: int = 8
    mapping_confidence_threshold: float = 0.6
    firecrawl_api_key: str = ""
    n8n_webhook_url: str = ""
    attack_version: str = "20.0"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    cors_origins: str = "http://localhost:3000"
    geoip_db_path: str = "/data/dbip-city-lite.mmdb"

settings = Settings()
```

**`backend/app/db.py`**
```python
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from pgvector.psycopg import register_vector
from app.config import settings
from pathlib import Path

def _configure(conn):
    # register vector type AFTER the extension exists (init_db creates it)
    try:
        register_vector(conn)
    except Exception:
        pass

pool = ConnectionPool(settings.database_url, min_size=1, max_size=10,
                      kwargs={"row_factory": dict_row}, configure=_configure, open=False)

def init_db():
    pool.open()
    sql = (Path(__file__).parent.parent / "db" / "schema.sql").read_text()
    with pool.connection() as conn:
        conn.execute(sql)
```
Then write these **plain functions** (sync is fine; others call them via `asyncio.to_thread` when needed):
```python
def create_analysis(analysis_id: str, title: str, source_url: str | None) -> None
def save_analysis(a: "ReportAnalysis") -> None
    # UPDATE analyses SET title, source_url, published_at, status, updated_at=now(),
    #   result = a.model_dump(mode="json")  (use psycopg.types.json.Jsonb)
def get_analysis(analysis_id: str) -> "ReportAnalysis | None"   # ReportAnalysis.model_validate(row["result"])
def list_analyses(limit: int = 50) -> list[dict]                 # AnalysisListItem shape (contracts §8)
    # counts: iocs = non-filtered IOCs, techniques = accepted, alerts = len(memory_alerts) — read from result JSON
def add_feedback(analysis_id, target_type, target_id, verdict, note) -> None
def attack_technique_count() -> int                              # SELECT count(*) FROM attack_techniques
```

**`backend/app/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db
from app.api.routes import router

app = FastAPI(title="TRINETRA API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()

app.include_router(router, prefix="/api")
```
**Done when:** `docker compose up --build` → `curl localhost:8000/api/health` returns `{"ok":true,...}` and tables exist (`docker compose exec db psql -U trinetra -c '\dt'`).

### Step 2 (30 min) — `utils/text.py` (everyone depends on this; publish early)

```python
def normalize_text(raw: str) -> str:
    """One canonical text. ALL evidence offsets in the system point into this string."""
```
Rules, in this order:
1. `unicodedata.normalize("NFKC", raw)`
2. `\r\n` and `\r` → `\n`
3. Smart quotes `‘ ’ ‚ ‛` → `'`; `“ ” „ ‟` → `"`; dashes `– — ‒ −` → `-`; non-breaking space `\u00a0` → space.
4. **Do not remove zero-width characters here** (the Lead's firewall needs to see them in `raw_text`); but do remove them from the normalised text: `\u200b \u200c \u200d \u2060 \ufeff`.
5. Replace tabs and runs of spaces with one space; strip spaces at line ends.
6. Collapse 3+ newlines into 2. Strip the whole string.

```python
def defang(value: str, ioc_type: str) -> str:
    """Safe display version. Never used for logic, only for UI/exports labels."""
```
- `ipv4`: `1.2.3.4` → `1[.]2[.]3[.]4`
- `ipv6`: `2001:db8::1` → `2001[:]db8[:][:]1` (replace `:` with `[:]`)
- `domain`: every `.` → `[.]`
- `url`: `http` → `hxxp`, `https` → `hxxps`, `ftp` → `fxp`; dots in the host part → `[.]` (leave the path)
- `email`: `@` → `[@]`, dots after `@` → `[.]`
- everything else (hashes, CVE, paths, registry, btc): unchanged

Tests: `tests/test_text.py` covering each rule.

### Step 3 (1 h 30 min) — `pipeline/ingest.py`

```python
class IngestResult(BaseModel):          # define in this file (pydantic)
    title: str
    source_url: str | None
    published_at: datetime | None
    raw_text: str          # before normalize_text (Lead's firewall scans this)
    text: str              # normalize_text(cleaned)
    publisher_domain: str | None   # e.g. "cisa.gov" — used by IOC allowlist
    references: list[str]  # link targets removed from markdown

async def ingest(url: str | None = None, text: str | None = None,
                 pdf_bytes: bytes | None = None, filename: str | None = None,
                 title: str | None = None) -> IngestResult
```
Logic:
- **Text given:** use it. Title = `title` or first non-empty line (max 120 chars).
- **URL given:**
  1. **Firecrawl** (if `FIRECRAWL_API_KEY` set). The SDK changed between versions — check the installed one:
     - v2: `from firecrawl import Firecrawl; fc = Firecrawl(api_key=KEY); doc = fc.scrape(url, formats=["markdown"])` → `doc.markdown`, `doc.metadata`.
     - v1: `from firecrawl import FirecrawlApp; app = FirecrawlApp(api_key=KEY); r = app.scrape_url(url, formats=["markdown"])`.
     Run it in `asyncio.to_thread` with a 45 s timeout. Firecrawl also handles PDF URLs.
  2. **Fallback:** `httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "TRINETRA/1.0"})` → if content-type is PDF use pdfplumber on bytes; else `trafilatura.extract(html, include_tables=True, include_links=False)`.
  3. Title: metadata `title` / `og:title`, else first heading.
  4. Published date: metadata (`publishedTime`, `article:published_time`, `date`) parsed with `datetime.fromisoformat` (try/except); else `None`.
  5. `publisher_domain`: registrable domain of the URL (strip `www.`; for gov sites like `www.cisa.gov` → `cisa.gov`).
- **PDF bytes given:** `pdfplumber.open(io.BytesIO(pdf_bytes))`, join page texts with `\n\n`; fix hyphenated line breaks (`-\n` + lowercase letter → join). Title = first line or filename.
- **Markdown cleanup (before normalise):** `![alt](src)` → remove; `[text](href)` → `text` and push `href` into `references`; strip leading `#` from headings; keep tables (IOC tables often live there); remove HTML comments.
- Raise `ValueError("Could not extract text")` if final text < 200 chars.

**Done when:** a CISA advisory URL, a PDF file and pasted text each produce clean text in < 5 s (Firecrawl) / < 10 s (fallback). Test: `tests/test_ingest.py` with a small saved HTML file and a tiny PDF (no network in tests).

### Step 4 (2 h) — `pipeline/ioc.py` — the deterministic IOC engine ⭐

```python
def extract_iocs(text: str, publisher_domain: str | None = None) -> list[IOC]
```
Must be **fast (< 300 ms for 50k chars)**, **no LLM, no network**. Role stays `"unknown"` (the RAG person's role agent fills it later).

1. **Find candidates with iocsearcher:**
   ```python
   from iocsearcher.searcher import Searcher
   _searcher = Searcher()                 # create ONCE at import (it's slow to build)
   ```
   Use the method that returns **positions** (in current versions `search_raw(text)` returns tuples like `(type, value, start, raw_text)`). Verify in a Python shell with `help(Searcher)` before coding. If positions are not available, find each match's raw occurrences yourself (search for the refanged value and its common defanged forms).
   iocsearcher refangs values for you (`hxxp://evil[.]com` → `http://evil.com`).
2. **Map types** (skip any type not listed):
   `ip4→ipv4, ip6→ipv6, fqdn→domain, url→url, email→email, md5→md5, sha1→sha1, sha256→sha256, sha512→sha512, cve→cve, bitcoin→btc`.
3. **Add our own regex** (iocsearcher may miss these):
   - CVE: `\bCVE-\d{4}-\d{4,7}\b` (case-insensitive, store upper-case)
   - Windows registry: `\b(?:HKLM|HKCU|HKCR|HKU|HKEY_LOCAL_MACHINE|HKEY_CURRENT_USER|HKEY_CLASSES_ROOT|HKEY_USERS)\\[^\s"'<>|]+`
   - Windows path: `\b[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n\s]+`
   - Linux path (only under common dirs): `(?<![\w/])/(?:tmp|etc|var|usr|home|opt|dev/shm)/[^\s"'<>]+`
4. **Normalise values:** hashes lower-case; domains lower-case and strip trailing `.`; URLs keep case of path but lower-case host; strip trailing punctuation `.,;:)]"'` from all.
5. **Filters** — do NOT delete; set `filtered_reason` (UI shows them as "filtered out"):
   | Rule | `filtered_reason` |
   |---|---|
   | IP is private / loopback / link-local / multicast / reserved / unspecified (Python `ipaddress`) | `"private_or_reserved_ip"` |
   | IPv4 preceded (within 15 chars) by `version`, `ver`, `v` + digits, or `build` | `"version_number"` |
   | Domain or URL host equals or is a subdomain of an allowlisted domain (`benign_domains.txt` + `publisher_domain`) | `"benign_domain"` |
   | URL pointing to a reference site (`attack.mitre.org`, `cve.mitre.org`, `nvd.nist.gov`, `github.com/mitre*`, `virustotal.com` lookups) | `"reference_link"` |
   | Domain whose TLD is a file extension (`zip`, `mov`) and that is not part of a URL, OR domain that equals a file name found in a Windows/Linux path | `"looks_like_filename"` |
   | Domain with no letters in the TLD part, or single-label | `"invalid_domain"` |
6. **`benign_domains.txt`** (you create, one per line, ~80 entries): microsoft.com, windows.com, office.com, live.com, google.com, googleapis.com, gstatic.com, youtube.com, apple.com, icloud.com, amazon.com, amazonaws.com, cloudflare.com, akamai.net, github.com, githubusercontent.com, gitlab.com, mozilla.org, wikipedia.org, linkedin.com, twitter.com, x.com, facebook.com, cisa.gov, us-cert.gov, nist.gov, mitre.org, cert-in.org.in, ncsc.gov.uk, virustotal.com, w3.org, schema.org, adobe.com, oracle.com, java.com, python.org, … Note in the file header: *subdomains of allowlisted parents are also filtered (keeps the rule simple). Attackers sometimes abuse shared hosting such as amazonaws.com or githubusercontent.com, so filtered items stay visible in the UI's "Filtered out" section where analysts can still review them.*
7. **Evidence:** for each IOC keep up to **3 occurrences**. Each evidence = the **sentence** containing the raw match (split sentences on `(?<=[.!?])\s+` and on `\n`), trimmed to max 300 chars centred on the match. `Evidence.quote = text[start:end]` exactly.
8. **Dedupe** by `(type, value)`; merge evidence lists.
9. **IDs:** `"ioc-1"`, `"ioc-2"`, … in order of first appearance.
10. **display:** `defang(value, type)`. `confidence.extraction`: 0.95 for hashes/CVE, 0.9 IP/URL, 0.85 domain/email, 0.75 paths/registry.

**Done when (tests in `tests/test_ioc.py`):**
- `"C2 at hxxp://evil[.]com/gate.php and 45[.]77[.]12[.]9"` → url `http://evil.com/gate.php` (display `hxxp://evil[.]com/gate.php`) and ipv4 `45.77.12.9`.
- `192.168.1.10` → filtered `private_or_reserved_ip`; `microsoft.com` → `benign_domain`; `version 10.0.19041.1` → `version_number`; `invoice.zip` inside `C:\Users\x\invoice.zip` → `looks_like_filename`.
- SHA-256 and MD5 found; `CVE-2026-12345` found once even if written twice.
- 50k-char text runs < 300 ms.

### Step 5 (1 h) — `api/routes.py` (wire everything)

Implement **every** route in contracts §8. Route bodies call other people's functions with these **exact signatures** (stubs already exist in the skeleton and return mock data, so you can call them right away):

```python
from app.pipeline.runner import start_analysis      # Lead: async (url, text, pdf_bytes, filename, title) -> str  (returns analysis id, runs pipeline in background)
from app.events import event_stream                 # Lead: async generator (analysis_id) -> yields dict events (replay + live)
from app.pipeline.simulate import simulate          # Lead: (analysis: ReportAnalysis, blocked_node_ids: list[str]) -> dict
from app.pipeline.detect import readiness           # Lead: (analysis: ReportAnalysis, telemetry: list[str]) -> dict
from app.pipeline.memory import get_graph           # Lead: (at: datetime | None, limit: int) -> dict
from app.eval.store import latest_eval              # Lead: () -> dict | None
from app.exports.sigma_export import sigma_yaml     # Lead: (analysis) -> str
from app.exports.flow_json import attack_flow_json  # Lead: (analysis) -> dict
from app.attack.store import list_tactics, get_technique_detail   # RAG: () -> list[dict], (id) -> dict | None
from app.exports.stix import build_stix_bundle      # YOU
from app.exports.navigator import build_navigator_layer   # YOU
```

Notes:
- `POST /api/analyses`: accept JSON **or** multipart. Implement as two code paths in one handler: `request.headers["content-type"]` starts with `multipart/` → `form = await request.form(); file = form["file"]` (must be PDF, ≤ 20 MB) else `body = await request.json()`. Exactly one of url/text/file required → else 422. Return `{"id": id}` with status 202 **immediately** (the Lead's runner runs in the background).
- `GET /api/analyses/{id}/events`:
  ```python
  from sse_starlette.sse import EventSourceResponse
  async def gen():
      async for evt in event_stream(analysis_id):
          yield {"data": json.dumps(evt, default=str)}
  return EventSourceResponse(gen(), ping=15)
  ```
- 404 when an analysis id doesn't exist (`get_analysis` returns None).
- Exports return downloads: `Response(content, media_type=..., headers={"Content-Disposition": f'attachment; filename="trinetra-{id}-{fmt}.{ext}"'})`. stix/navigator/flow → `application/json`; sigma → `application/x-yaml`. Only allowed when `status == "done"` (else 409).
- `GET /api/health` → `{"ok": True, "attack_loaded": count > 0, "techniques": count}`.
- Use `asyncio.to_thread` for DB calls inside async routes.

**Done when:** `http://localhost:8000/docs` lists all routes; each returns mock/real data; `curl -N .../events` streams.

### Step 6 (1 h 30 min) — Exports

#### `exports/stix.py` — `build_stix_bundle(analysis: ReportAnalysis) -> dict`
Use `stix2` (validates for you). Create:
- `Identity` (name "TRINETRA", identity_class "system").
- One `Indicator` per **non-filtered** IOC, `pattern_type="stix"`, `valid_from=now`, `name=display`, `indicator_types` from role (c2/payload/exfil/phishing → `["malicious-activity"]`, others → `["unknown"]`), `description` = first evidence quote (max 300 chars). Patterns (use refanged `value`; escape `\` as `\\` and `'` as `\'`):
  | type | pattern |
  |---|---|
  | ipv4 | `[ipv4-addr:value = '{v}']` |
  | ipv6 | `[ipv6-addr:value = '{v}']` |
  | domain | `[domain-name:value = '{v}']` |
  | url | `[url:value = '{v}']` |
  | email | `[email-addr:value = '{v}']` |
  | md5 | `[file:hashes.MD5 = '{v}']` |
  | sha1 | `[file:hashes.'SHA-1' = '{v}']` |
  | sha256 | `[file:hashes.'SHA-256' = '{v}']` |
  | sha512 | `[file:hashes.'SHA-512' = '{v}']` |
  | registry | `[windows-registry-key:key = '{v}']` |
  | filepath | `[file:name = '{basename}']` |
  | cve | **not an indicator** → `Vulnerability(name=v, external_references=[{"source_name":"cve","external_id":v}])` |
  | btc / other | skip |
- One `AttackPattern` per **accepted observed** technique: `name`, `external_references=[{"source_name":"mitre-attack","external_id":tid,"url":url}]`, `kill_chain_phases=[{"kill_chain_name":"mitre-attack","phase_name":t} for t in tactics]`, custom property `x_trinetra_evidence` = quote, `x_trinetra_confidence` = mapping (create with `allow_custom=True`).
- `Relationship(indicator, "indicates", attack_pattern)` for every IOC↔technique link.
- `Report(name=title, published=published_at or now, report_types=["threat-report"], object_refs=[all ids], created_by_ref=identity, external_references=[{"source_name":"source","url":source_url}] if url)`.
- Return `json.loads(Bundle(objects, allow_custom=True).serialize())`.
- **Predictions are never exported as observed.** Skip them.
Test: `stix2.parse(bundle, allow_custom=True)` succeeds; indicator count = non-filtered IOC count (minus btc/other).

#### `exports/navigator.py` — `build_navigator_layer(analysis, include_predicted=False) -> dict`
Build the JSON by hand (simplest; matches ATT&CK Navigator layer format 4.5):
```json
{
  "name": "TRINETRA – <title>",
  "versions": {"attack": "20", "navigator": "5.1.0", "layer": "4.5"},
  "domain": "enterprise-attack",
  "description": "Generated by TRINETRA from <source_url>",
  "sorting": 3,
  "layout": {"layout": "side", "showName": true, "showID": true},
  "hideDisabled": false,
  "techniques": [
    {"techniqueID": "T1059.001", "tactic": "execution", "score": 87,
     "comment": "<evidence quote, max 250 chars>", "enabled": true, "showSubtechniques": true}
  ],
  "gradient": {"colors": ["#1e293b", "#22d3ee"], "minValue": 0, "maxValue": 100},
  "legendItems": [{"label": "Observed (score = confidence)", "color": "#22d3ee"},
                  {"label": "Predicted – hunt for these", "color": "#a78bfa"}],
  "showTacticRowBackground": true, "tacticRowBackground": "#0e1117",
  "selectTechniquesAcrossTactics": true, "selectSubtechniquesWithParent": false
}
```
- One entry **per (technique, tactic)** pair. `score = round(mapping*100)`.
- If `include_predicted` (query `?include_predicted=1`): add predictions with `"color": "#a78bfa"`, `"score": 0`, comment "Predicted (not observed)".
- Check the current Navigator release number on its GitHub and update `"navigator"`; test by opening the file at the ATT&CK Navigator web app → "Open Existing Layer → Upload from local".

### Step 7 (30 min) — `pipeline/notify.py` + n8n
```python
async def notify(kind: str, payload: dict) -> None:
    """Fire-and-forget POST to n8n. NEVER raises, never blocks the pipeline > 5 s."""
```
- `kind` ∈ `"analysis_done"`, `"memory_alert"`, `"injection_detected"`. Body: `{"kind": kind, "app": "TRINETRA", "ts": iso_now, **payload}`. The Lead calls this.
- Skip silently if `N8N_WEBHOOK_URL` is empty. Catch all exceptions and log.
- **n8n workflow** (in n8n Cloud/Pro UI): `Webhook (POST)` → `Switch on {{$json.kind}}` → `Telegram: Send Message` (create a bot with @BotFather, put bot token in n8n credentials, get chat id) with message templates:
  - analysis_done: `🔱 TRINETRA analysed "{{title}}": {{iocs}} IOCs, {{techniques}} techniques. {{link}}`
  - memory_alert: `🔁 {{message}}`
  - injection_detected: `⚠️ Prompt-injection attempt in "{{title}}" ({{technique_id}})`
  Export the workflow JSON to `integrations/n8n/trinetra-alerts.json` in the repo.
- Optional branch (NICE): `HTTP Request` node pushing the STIX bundle (`GET /api/analyses/{id}/export/stix`) to a MISP/OpenCTI instance if one exists.

### Step 8 — NICE (only after Steps 1–7 are merged and working)

#### `pipeline/geo.py` + `GET /api/analyses/{id}/geo`
- Download **DB-IP "IP to City Lite"** `.mmdb` (free, CC BY 4.0 — README must credit "IP Geolocation by DB-IP") into `./data/`.
- `maxminddb.open_database(settings.geoip_db_path)` once; for each non-filtered ipv4/ipv6 IOC → `{ioc_id, display, lat, lon, country, city, role}`.
- **Never resolve domains or contact any IOC** (no DNS lookups, no HTTP to indicators) — touching attacker infrastructure is unsafe.

#### `scripts/watch.py` — autonomous intel watch
- Watch list: CISA cybersecurity advisories listing page, CERT-In advisories page (Lead confirms URLs).
- Every 30 min: Firecrawl-scrape the listing page (markdown), extract advisory links (regex on the `references`), compare with `data/seen_urls.json`, and for each new one `POST /api/analyses {"url": ...}` (max 3 per cycle to save credits).
- Run with `python scripts/watch.py --once` for the demo.

---

## 4. Testing checklist
- [ ] `pytest backend/tests -q` green: text, ingest (offline fixtures), ioc, stix (`stix2.parse`), navigator (has required keys, scores 0–100).
- [ ] `docker compose up --build` from a clean clone works with only `.env` filled.
- [ ] All routes visible in `/docs`; 404/409/422 handled.
- [ ] IOC engine: no network calls (run tests with wifi off to prove it).

## 5. Don'ts
- Don't call any LLM in your code.
- Don't contact IOCs (no DNS, no HTTP to indicators, ever).
- Don't run Uvicorn with more than 1 worker (live events are in memory).
- Don't change `models.py` or the schema without telling the Lead.
- Don't swallow errors silently in routes — return proper HTTP errors with a clear `detail`.
- Don't commit `.env`, keys, or the `.mmdb` file (add `data/` to `.gitignore`).

## 6. Your timeline (parallel build — call others' stubs, never wait)
| Time | Deliver |
|---|---|
| 14:45–15:30 | (Before the repo lands) read `00` + this file; install Docker + Python 3.11; in a scratch folder try `iocsearcher` on a few defanged strings and one Firecrawl scrape to learn their APIs |
| 15:30 | Clone skeleton → branch `feat/backend-core` → `docker compose up --build` → `/api/health` OK |
| 15:30–16:00 | Step 1: verify/harden compose, DB, config, health ✅ push |
| 16:00–16:30 | Step 2: `utils/text.py` + tests ✅ push (RAG person + Lead use it) |
| 16:30–18:00 | Step 3: ingestion ✅ push |
| 18:00–20:00 | Step 4: IOC engine + tests ✅ push (needed for Milestone 1 at 20:00) |
| 20:00–21:00 | Step 5: finish all routes on real functions |
| 21:00–22:30 | Step 6: STIX + Navigator exports |
| 22:30–23:00 | Step 7: notify + n8n Telegram workflow |
| 23:00–01:30 | Fix bugs found on real reports with the Lead; then NICE: geo, watch |
| 02:00 | Feature freeze — only fixes after this |

Push small working commits at least every 1–2 hours; never push a broken `docker compose up`.
