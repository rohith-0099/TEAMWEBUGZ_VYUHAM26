# 00 — SHARED CONTRACTS (everyone reads this first)

> **AI agents:** read this whole file before writing code. It defines the architecture, who owns which file, the exact data shapes, database tables, API, live events and environment variables. **Never change a contract on your own.** If you need a change, the human asks the Lead (Person 5) and the Lead updates this file.
>
> Every role file (`01`–`05`) assumes you have read this one.

Project: **TRINETRA** — Team WeBugz · Vyuham'26 Agent Forge · Problem AF-15
Deadline: **31 Oct 2026, 08:30 IST** · Submit by **07:30** · Feature freeze **02:00**

---

## 1. What we are building (30-second version)

The problem statement asks for a platform that **(1) analyzes threat intelligence reports, (2) extracts indicators of compromise (IOCs), and (3) maps observed attack patterns to recognized cybersecurity frameworks**, so security teams can connect indicators with the tactics and techniques used in real attacks.

TRINETRA: paste a report (URL / PDF / text) → get
- **IOCs** (IPs, domains, URLs, hashes, CVEs…) including *defanged* ones like `hxxp://evil[.]com`, each with a role (C2, payload…) and evidence;
- **MITRE ATT&CK v20 techniques**, each proven by an **exact quote** from the report and checked by a **verifier** (no hallucinated IDs or quotes);
- the **attack story** (flow graph with observed / predicted / unknown steps), a **disruption simulator**, **detection gaps + Sigma rules**, **memory across reports** with contradiction alerts, a **prompt-injection firewall**, and **STIX 2.1 / Navigator exports**;
- all shown **live** as each AI agent runs.

**Golden rule:** *No hallucinated output reaches the user.* Technique IDs must exist in ATT&CK v20. Quotes must exist in the report text. Everything else is rejected and shown as rejected.

### ATT&CK facts (use these, not older numbers)
- Current version **v20**, released **13 Oct 2026**. Enterprise: **15 tactics, 227 techniques, 479 sub-techniques**.
- v19 (Apr 2026) **split Defense Evasion (TA0005)** into **Stealth** and **Defense Impairment**.
- v20 added AI techniques incl. **prompt injection: T1698, T1699**.
- Never hard-code tactic names/order in code — always load them from the ATT&CK data (`/api/attack/tactics`).

---

## 2. Team and ownership

| # | Person | Role file | Owns |
|---|---|---|---|
| 1 | Frontend A | `01_FRONTEND_A.md` | App shell, design system, home, pipeline canvas, evidence viewer, IOC table, technique cards, heatmap, exports UI, print/PDF view, `lib/` (types, API client, SSE hook, mocks) |
| 2 | Frontend B | `02_FRONTEND_B.md` | Attack flow graph, disruption simulator UI, detection readiness UI, memory graph page, scoreboard page, globe |
| 3 | Backend Core | `03_BACKEND_CORE.md` | FastAPI skeleton, config, DB schema + access, docker-compose, ingestion, IOC engine, API routes, STIX + Navigator exports, n8n notify, (NICE) geo + watch |
| 4 | RAG + AI | `04_RAG_AI.md` | ATT&CK v20 loader + embeddings, ATT&CK data access functions, quote finder, behaviour agent, retriever, IOC role agent, IOC↔technique linker, v20 migrator |
| 5 | Lead / Architect | `05_LEAD_ARCHITECT.md` | `models.py`, `llm.py`, SSE event bus, LangGraph pipeline + runner, verifier, prompt-injection firewall, attack flow, predictions (TIE), simulator + D3FEND, detection readiness + Sigma, temporal memory + contradictions, evaluation scoreboard, integration, deploy |

**Rule:** only edit files you own. Need something in someone else's file? Ask them (or the Lead).

---

## 3. Architecture

```
                         ┌──────── INPUT ────────┐
                         │  URL │ PDF │ text     │
                         └──────────┬────────────┘
                                    ▼
 [ingest]      P3  Firecrawl / pdfplumber → normalised text           (deterministic)
                                    ▼
 [guard]       P5  prompt-injection firewall: rules + 1 LLM call      (hybrid)
                                    ▼
          ┌─────────────────────────┴──────────────────────────┐
          ▼                                                    ▼
 [ioc]      P3  iocsearcher + regex + filters (det.)   [behaviours] P4  LLM → atomic behaviours + exact quotes
          ▼                                                    ▼
 [ioc_role] P4  LLM labels role + quote                [retrieve]   P4  pgvector top-k ATT&CK v20 candidates
          │                                                    ▼
          │                                            [verify]     P5  LLM + hard code checks → accept/reject
          └──────────────────────┬─────────────────────────────┘
                                 ▼
 [link]        P4  IOC ↔ technique                                   (deterministic + verify hints)
                                 ▼
   ┌────────────┬───────────────┼──────────────┬──────────────┬─────────────┐
   ▼            ▼               ▼              ▼              ▼             ▼
 [tie] P5    [flow] P5       [detect] P5    [memory] P5    [migrate] P4  [export] P3/P5
 predicted   attack chain    strategies,    seen-before,   v20 remap     STIX, Navigator,
 techniques  + NetworkX      analytics,     contradictions               Sigma, Flow JSON
                             Sigma
                                 ▼
          every stage emits SSE events → Next.js UI (P1, P2)
```

Orchestration: **LangGraph** in `app/pipeline/graph.py` (P5). The UI never waits for the full result; it renders stage by stage from SSE events.

---

## 4. Tech stack — what each tool does and who uses it

### Backend (Python 3.11+)
| Tool | Purpose | Used in | Owner |
|---|---|---|---|
| FastAPI + Uvicorn | HTTP API server | `app/main.py`, `app/api/routes.py` | P3 |
| Pydantic v2 | Data models / validation | `app/models.py` | P5 (all import it) |
| psycopg 3 + psycopg_pool + pgvector (py) | Postgres access incl. vectors | `app/db.py` | P3 (P4/P5 add their queries in their own modules) |
| sse-starlette | SSE responses | `app/api/routes.py` | P3 (uses P5's event bus) |
| LangGraph | Agent pipeline orchestration | `app/pipeline/graph.py` | P5 |
| LiteLLM | One interface to any LLM provider | `app/llm.py` | P5 |
| fastembed (`BAAI/bge-small-en-v1.5`, 384 dims) | Local embeddings | `app/attack/embed.py` | P4 |
| mitreattack-python | Read ATT&CK STIX, build Navigator layers | `app/attack/loader.py`, `app/exports/navigator.py` | P4, P3 |
| iocsearcher | IOC extraction incl. defanged | `app/pipeline/ioc.py` | P3 |
| rapidfuzz | Fuzzy quote matching | `app/utils/quotes.py` | P4 |
| firecrawl-py | URL/PDF → markdown | `app/pipeline/ingest.py` | P3 |
| pdfplumber, trafilatura, httpx | Fallback ingestion | `app/pipeline/ingest.py` | P3 |
| stix2 | STIX 2.1 bundle | `app/exports/stix.py` | P3 |
| NetworkX | Attack graph + simulator | `app/pipeline/flow.py`, `app/pipeline/simulate.py` | P5 |
| pySigma (+ a backend, e.g. pySigma-backend-splunk) | Validate / convert Sigma | `app/pipeline/sigma.py` | P5 |
| CTID Technique Inference Engine | Predict unreported techniques | `app/pipeline/tie.py` | P5 |
| countermap (check first) / ATT&CK mitigations | Countermeasures | `app/pipeline/simulate.py` | P5 |
| maxminddb + DB-IP Lite (NICE) | Offline IP geolocation | `app/pipeline/geo.py` | P3 |
| pytest | Tests | `backend/tests/` | all backend |

### Frontend (Next.js App Router + TypeScript)
| Tool | Purpose | Used in | Owner |
|---|---|---|---|
| Next.js 15 + TypeScript | App framework | `frontend/app` | P1 |
| Tailwind CSS + shadcn/ui | Styling + UI components | everywhere | P1 sets up, both use |
| Framer Motion | Animations | everywhere | both |
| @xyflow/react (React Flow) | Pipeline canvas; attack flow graph | `components/pipeline-canvas`, `components/attack-flow` | P1, P2 |
| @dagrejs/dagre | Auto-layout for React Flow graphs | attack flow | P2 |
| sigma.js + graphology (+ @react-sigma/core, graphology-layout-forceatlas2) | WebGL memory graph | `components/memory-graph` | P2 |
| deck.gl + react-map-gl + MapLibre GL | Globe / map (NICE) | `components/globe` | P2 |
| Zustand | Client state for live analysis | `lib/store.ts` | P1 |
| @tanstack/react-query | Fetching + caching REST | `lib/api.ts` | P1 |
| lucide-react | Icons | everywhere | both |
| react-syntax-highlighter (or shiki) | YAML/JSON viewers (Sigma, STIX) | panels | both |

### Data + infra
| Tool | Purpose | Owner |
|---|---|---|
| PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16` image) | The only database: reports, ATT&CK, vectors, memory graph, eval, LLM cache | P3 runs it; schema in §7 |
| Docker Compose | One-command start | P3 |
| Vercel (frontend), Railway/Render (backend + Postgres with pgvector) | Deploy | P5 (P3 helps) |

### External services / credits
| Service | Use | Owner |
|---|---|---|
| Organiser LLM key (via LiteLLM) | All LLM calls | P5 |
| Firecrawl (10k credits) | Ingestion; (NICE) change-tracking watch | P3 |
| n8n Pro | Outbound alerts only (Telegram/Slack), push STIX to MISP/OpenCTI | P3 |
| Adaption AI | **Not during hackathon** | — |

**Do NOT add:** Neo4j/Graphiti (unless Lead approves), AutoGen, Suricata, Zeek, Nuclei, ZAP, Semgrep, Trivy, Gitleaks, CRS, Velociraptor, OR-Tools, Mesa, PostGIS, XGBoost, LightGBM, any extra database, any auth system.

---

## 5. Repository layout and ownership

```
trinetra/
├── PLAN.md  README.md  team/                          (P5)
├── docker-compose.yml  .env.example                   (P3)
├── backend/
│   ├── requirements.txt                               (P3; others add lines via PR)
│   ├── Dockerfile                                     (P3)
│   ├── db/schema.sql                                  (P3; tables per §7)
│   ├── app/
│   │   ├── main.py  config.py  db.py                  (P3)
│   │   ├── models.py                                  (P5)
│   │   ├── llm.py  events.py                          (P5)
│   │   ├── api/routes.py                              (P3)
│   │   ├── utils/text.py                              (P3)  normalize_text, defang
│   │   ├── utils/quotes.py                            (P4)  find_quote
│   │   ├── attack/loader.py embed.py store.py         (P4)
│   │   ├── attack/allowlists/benign_domains.txt       (P3)
│   │   ├── pipeline/ingest.py ioc.py                  (P3)
│   │   ├── pipeline/behaviours.py retrieve.py         (P4)
│   │   ├── pipeline/ioc_role.py link.py migrate.py    (P4)
│   │   ├── pipeline/graph.py runner.py verify.py      (P5)
│   │   ├── pipeline/guard.py flow.py tie.py           (P5)
│   │   ├── pipeline/simulate.py detect.py sigma.py    (P5)
│   │   ├── pipeline/memory.py                         (P5)
│   │   ├── pipeline/geo.py  watch.py  notify.py       (P3)
│   │   ├── exports/stix.py navigator.py               (P3)
│   │   ├── exports/flow_json.py sigma_export.py       (P5)
│   │   └── eval/                                      (P5)
│   ├── scripts/load_attack.py                         (P4)
│   ├── scripts/run_eval.py  smoke_test.py             (P5)
│   └── tests/                                         (each owner tests own module)
└── frontend/
    ├── app/layout.tsx, page.tsx (home)                (P1)
    ├── app/report/[id]/page.tsx (tabs shell)          (P1)
    ├── app/graph/page.tsx, app/eval/page.tsx          (P2)
    ├── components/ui/ (shadcn)                        (P1)
    ├── components/pipeline-canvas/ report-viewer/
    │   ioc-table/ technique-card/ attack-heatmap/
    │   exports/ print-report/ input/                  (P1)
    ├── components/attack-flow/ simulator/
    │   detection-panel/ memory-graph/ eval/ globe/    (P2)
    └── lib/types.ts api.ts sse.ts store.ts tactics.ts
        lib/mock/*.json                                (P1; P2 adds its own mock files)
```

### Git rules
- One repo, branch `main`. Each person works on `feat/<name>-<thing>` and merges small PRs often (at least every 2 hours).
- Never commit `.env` or API keys.
- **Skeleton-first, then fully parallel:** the Lead pushes a skeleton repo (all folders, every backend file as a stub with its final signature returning mock data, Next.js app with `lib/types.ts` + mocks, Docker setup). Everyone clones it and **replaces only their own stubs**. The system runs end-to-end on fake data from minute one; every merge swaps a fake part for a real one. Nobody waits for anybody.
- If a function you call isn't real yet, call it anyway — its stub returns mock data.
- Never push code that breaks `docker compose up` or `npm run build`. The Lead pulls `main` every 1–2 hours, runs the full system + smoke test, and reverts any commit that breaks it.

---

## 6. Data models — `backend/app/models.py` (P5 creates this file exactly; everyone imports it)

```python
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

IOCType = Literal["ipv4","ipv6","domain","url","email","md5","sha1","sha256","sha512",
                  "cve","filepath","registry","btc","other"]
IOCRole = Literal["c2","payload","phishing","exfil","victim","scanner","infrastructure","unknown"]
Telemetry = Literal["sysmon","windows_security","powershell_scriptblock","edr","dns","proxy",
                    "firewall","netflow","cloud_audit","email_gateway","linux_auditd"]

class Evidence(BaseModel):
    quote: str                 # exact substring of ReportAnalysis.text
    start: int                 # char offset in ReportAnalysis.text
    end: int                   # text[start:end] == quote

class Confidence(BaseModel):
    extraction: float = 1.0    # 0..1  was it extracted correctly
    mapping: float | None = None       # technique fits the evidence
    role: float | None = None          # IOC role / attribution
    relationship: float | None = None  # IOC<->technique link
    freshness: float | None = None     # how current the intel is

class IOC(BaseModel):
    id: str                    # "ioc-1", "ioc-2", ...
    type: IOCType
    value: str                 # refanged (real) value, internal use only
    display: str               # defanged value for UI, e.g. "evil[.]com"
    role: IOCRole = "unknown"
    evidence: list[Evidence] = []
    confidence: Confidence = Field(default_factory=Confidence)
    linked_techniques: list[str] = []   # technique_ids
    filtered_reason: str | None = None  # set => dropped (private IP, allowlisted...)
    source_key: str | None = None       # app/sources.py key backing filtered_reason
    from_ocr: bool = False              # every evidence span lies in text read from an image (OCR)

class Behaviour(BaseModel):
    id: str                    # "b-1", ...
    summary: str               # short paraphrase, e.g. "Malware adds Run key for persistence"
    evidence: Evidence

class Candidate(BaseModel):    # retriever output (internal + shown as "rejected candidates")
    technique_id: str
    name: str
    score: float               # cosine similarity 0..1
    source: Literal["vector","explicit_id"] = "vector"

class TechniqueMatch(BaseModel):
    technique_id: str          # e.g. "T1071.001" — must exist in v20 if status=="accepted"
    name: str
    tactics: list[str]         # tactic shortnames from ATT&CK data
    behaviour_id: str | None = None
    evidence: Evidence | None = None    # REQUIRED when origin=="observed"
    status: Literal["accepted","rejected"]
    reject_reason: str | None = None    # "id_not_in_v20" | "quote_not_in_source" | "verifier_mismatch" | "low_confidence" | "deprecated"
    source_key: str | None = None       # app/sources.py key backing reject_reason
    rationale: str = ""
    confidence: Confidence = Field(default_factory=Confidence)
    linked_iocs: list[str] = []         # IOC ids
    origin: Literal["observed","predicted"] = "observed"
    prediction_score: float | None = None
    url: str | None = None              # attack.mitre.org link

class InjectionFlag(BaseModel):
    detector: Literal["rule","llm"]
    pattern: str               # rule name or LLM label
    severity: Literal["high","medium","low"]
    evidence: Evidence | None = None
    technique_id: Literal["T1698","T1699"] = "T1699"   # see 05 file for which applies

class FlowNode(BaseModel):
    id: str                    # "n-T1566.001" | "p-T1059" | "u-persistence"
    kind: Literal["observed","predicted","unknown"]
    technique_id: str | None = None
    tactic: str                # tactic shortname
    label: str
    order: int                 # left-to-right position hint

class FlowEdge(BaseModel):
    source: str
    target: str
    relation: Literal["followed_by","enables","uses_infrastructure"]

class AttackFlow(BaseModel):
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []

class LogSource(BaseModel):
    name: str                  # as in ATT&CK, e.g. "WinEventLog:Microsoft-Windows-PowerShell/Operational"
    data_component: str | None = None
    telemetry: Telemetry | None = None   # our normalised bucket

class Analytic(BaseModel):
    id: str; name: str; platforms: list[str] = []; log_sources: list[LogSource] = []

class DetectionStrategy(BaseModel):
    id: str; name: str; analytics: list[Analytic] = []

class SigmaRule(BaseModel):
    title: str
    technique_id: str
    kind: Literal["ioc","behaviour"]
    yaml: str
    valid: bool
    errors: list[str] = []
    conversions: dict[str, str] = {}     # e.g. {"splunk": "...query..."}

class Detection(BaseModel):
    technique_id: str
    technique_name: str
    strategies: list[DetectionStrategy] = []
    required_telemetry: list[Telemetry] = []
    sigma: list[SigmaRule] = []

class ReportRef(BaseModel):
    report_id: str; title: str; published_at: datetime | None = None; quote: str | None = None

class MemoryAlert(BaseModel):
    type: Literal["seen_before","contradiction","duplicate_report"]   # duplicate_report: same normalised text analysed before; sole alert
    entity_type: str           # "ioc" | "actor" | "malware" | "technique"
    entity_key: str            # refanged value or name
    entity_display: str        # defanged for IOCs
    message: str
    reports: list[ReportRef] = []
    explained_by_time: bool | None = None   # contradiction only

class Migration(BaseModel):
    old_id: str
    new_ids: list[str]
    reason: str                # e.g. "TA0005 Defense Evasion split in v19"
    evidence: Evidence | None = None
    source_key: str | None = "attack_v20"

class ReportAnalysis(BaseModel):
    report_id: str
    status: Literal["running","done","error"] = "running"
    error: str | None = None
    title: str = ""
    source_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    text: str = ""
    injection_flags: list[InjectionFlag] = []
    iocs: list[IOC] = []
    behaviours: list[Behaviour] = []
    techniques: list[TechniqueMatch] = []      # accepted + rejected, origin=observed
    predictions: list[TechniqueMatch] = []     # origin=predicted
    flow: AttackFlow = Field(default_factory=AttackFlow)
    detections: list[Detection] = []
    memory_alerts: list[MemoryAlert] = []
    migrations: list[Migration] = []
    images: list[ImageInfo] = []               # images considered for OCR: index, source, chars, used, start, end
    ocr_status: str | None = None              # "ok" | "no_images" | "unavailable: <reason>"
    vulnerabilities: list[VulnInfo] = []       # NVD + CISA KEV facts per CVE IOC (see models.py)
    briefing: Briefing | None = None           # steps + actions, written from verified data only
    timings_ms: dict[str, int] = {}
```

`VulnInfo`, `VulnReference`, `Briefing`, `BriefingStep` and `BriefingAction` are defined in
`backend/app/models.py` and mirrored in `frontend/lib/types.ts`. A failed NVD/KEV lookup is
`nvd_status="unavailable"` / `kev_status="unavailable"` with empty fields, never a guess.

---

## 7. Database — `backend/db/schema.sql` (P3 creates; run once at startup)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- reports / analyses (P3)
CREATE TABLE IF NOT EXISTS analyses (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL DEFAULT '',
  source_url    TEXT,
  published_at  TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'running',     -- running | done | error
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  result        JSONB NOT NULL DEFAULT '{}'::jsonb    -- full ReportAnalysis JSON
);

CREATE TABLE IF NOT EXISTS feedback (
  id           SERIAL PRIMARY KEY,
  analysis_id  TEXT REFERENCES analyses(id) ON DELETE CASCADE,
  target_type  TEXT NOT NULL CHECK (target_type IN ('technique','ioc')),
  target_id    TEXT NOT NULL,
  verdict      TEXT NOT NULL CHECK (verdict IN ('accept','reject')),
  note         TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ATT&CK v20 (P4 fills)
CREATE TABLE IF NOT EXISTS attack_tactics (
  tactic_id  TEXT PRIMARY KEY,        -- "TA0001"
  shortname  TEXT UNIQUE NOT NULL,    -- "initial-access"
  name       TEXT NOT NULL,
  ord        INT NOT NULL             -- matrix order, 0..14
);
CREATE TABLE IF NOT EXISTS attack_techniques (
  technique_id     TEXT PRIMARY KEY,  -- "T1059.001"
  stix_id          TEXT UNIQUE NOT NULL,
  name             TEXT NOT NULL,
  description      TEXT NOT NULL,
  tactics          TEXT[] NOT NULL,   -- tactic shortnames
  is_subtechnique  BOOLEAN NOT NULL,
  parent_id        TEXT,
  platforms        TEXT[],
  url              TEXT,
  embedding        vector(384)
);
CREATE INDEX IF NOT EXISTS attack_techniques_emb ON attack_techniques USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS attack_examples (   -- procedure examples, extra retrieval text
  id            SERIAL PRIMARY KEY,
  technique_id  TEXT NOT NULL REFERENCES attack_techniques(technique_id),
  text          TEXT NOT NULL,
  embedding     vector(384)
);
CREATE INDEX IF NOT EXISTS attack_examples_emb ON attack_examples USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS attack_objects (    -- every STIX object, raw (strategies, analytics, groups, mitigations, deprecated...)
  stix_id    TEXT PRIMARY KEY,
  attack_id  TEXT,                    -- external ATT&CK id if any
  type       TEXT NOT NULL,
  name       TEXT,
  deprecated BOOLEAN NOT NULL DEFAULT false,
  revoked    BOOLEAN NOT NULL DEFAULT false,
  data       JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS attack_objects_aid ON attack_objects(attack_id);
CREATE INDEX IF NOT EXISTS attack_objects_type ON attack_objects(type);
CREATE TABLE IF NOT EXISTS attack_relationships (
  id                 TEXT PRIMARY KEY,
  source_ref         TEXT NOT NULL,
  target_ref         TEXT NOT NULL,
  relationship_type  TEXT NOT NULL,
  description        TEXT
);
CREATE INDEX IF NOT EXISTS attack_rel_src ON attack_relationships(source_ref);
CREATE INDEX IF NOT EXISTS attack_rel_tgt ON attack_relationships(target_ref);

-- temporal memory graph (P5 writes)
CREATE TABLE IF NOT EXISTS mem_nodes (
  id          TEXT PRIMARY KEY,       -- "ioc:domain:evil.com", "technique:T1059", "actor:apt29"
  type        TEXT NOT NULL,          -- ioc | technique | actor | malware | report | sector
  key         TEXT NOT NULL,
  display     TEXT NOT NULL,
  first_seen  TIMESTAMPTZ,
  last_seen   TIMESTAMPTZ,
  UNIQUE (type, key)
);
CREATE TABLE IF NOT EXISTS mem_edges (
  id          SERIAL PRIMARY KEY,
  src         TEXT NOT NULL REFERENCES mem_nodes(id),
  dst         TEXT NOT NULL REFERENCES mem_nodes(id),
  relation    TEXT NOT NULL,          -- mentioned_in | uses | attributed_to | targets | indicates
  valid_from  TIMESTAMPTZ,
  valid_to    TIMESTAMPTZ,
  report_id   TEXT REFERENCES analyses(id) ON DELETE CASCADE,
  evidence    JSONB
);

-- evaluation (P5)
CREATE TABLE IF NOT EXISTS eval_runs (
  id       SERIAL PRIMARY KEY,
  ran_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload  JSONB NOT NULL               -- EvalResponse (see §8)
);

-- LLM response cache (P5)
CREATE TABLE IF NOT EXISTS llm_cache (
  key         TEXT PRIMARY KEY,
  response    JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. REST API (P3 implements routes; bodies call the owners' functions)

Base URL: `http://localhost:8000` (env `NEXT_PUBLIC_API_URL` on the frontend). All JSON. CORS allows the frontend origin.

| Method | Path | Request | Response | Logic owner |
|---|---|---|---|---|
| GET | `/api/health` | – | `{"ok": true, "attack_loaded": bool, "techniques": int}` | P3 |
| POST | `/api/analyses` | JSON `{"url"?: str, "text"?: str, "title"?: str}` **or** multipart `file` (PDF) | `{"id": str}` (202) | P3 route → P5 `start_analysis` |
| GET | `/api/analyses` | – | `AnalysisListItem[]` | P3 |
| GET | `/api/analyses/{id}` | – | `ReportAnalysis` (partial while running) | P3 |
| GET | `/api/analyses/{id}/events` | – | SSE stream (§9) | P3 route → P5 `event_stream` |
| POST | `/api/analyses/{id}/feedback` | `{"target_type":"technique"\|"ioc","target_id":str,"verdict":"accept"\|"reject","note"?:str}` | `{"ok": true}` | P3 |
| POST | `/api/analyses/{id}/simulate` | `{"blocked_node_ids": str[]}` | `SimulateResponse` | P5 |
| POST | `/api/analyses/{id}/readiness` | `{"telemetry": Telemetry[]}` | `ReadinessResponse` | P5 |
| GET | `/api/analyses/{id}/export/{fmt}` | fmt ∈ `stix`,`navigator`,`sigma`,`flow` | file download (JSON / YAML) | P3 (stix, navigator) · P5 (sigma, flow) |
| GET | `/api/analyses/{id}/geo` (NICE) | – | `{"available": bool, "points": GeoPoint[]}`; IPs the offline DB cannot place get no point | P3 |
| GET | `/api/sources` | – | `{"sources": {key: {title,url,publisher,why}}, "rules": {reason: {kind,label,rule,source_keys}}, "glossary": {term: {term,text,source_key}}}` | P5 |
| GET | `/api/graph` | query `at?`=ISO date, `limit?`=int | `GraphResponse` | P5 |
| GET | `/api/attack/tactics` | – | `Tactic[]` ordered | P4 |
| GET | `/api/attack/techniques/{id}` | – | `TechniqueDetail` | P4 |
| GET | `/api/eval` | – | `EvalResponse` (latest run); **404 until `run_eval.py` has really been run** | P5 |

PDF report = browser print view (P1), **not** a backend export.

### Extra response shapes
```ts
type AnalysisListItem = { report_id: string; title: string; source_url: string|null;
  published_at: string|null; created_at: string; status: "running"|"done"|"error";
  counts: { iocs: number; techniques: number; alerts: number } };

type SimulateResponse = { total_paths: number; broken_paths: number; broken_pct: number; // 0..100
  surviving_paths: string[][];        // lists of node ids
  affected_node_ids: string[];        // nodes no longer reachable from any entry
  countermeasures: { technique_id: string; id: string; name: string;
                     source: "d3fend"|"attack_mitigation"; derived: boolean; url?: string }[];
  note?: string };                    // e.g. "paths capped at 500"

type ReadinessResponse = { readiness_pct: number;   // 0..100
  per_technique: { technique_id: string; technique_name: string;
                   status: "covered"|"partial"|"gap"; have: string[]; missing: string[] }[] };

type GraphResponse = {
  nodes: { id: string; type: "ioc"|"technique"|"actor"|"malware"|"report"|"sector";
           label: string; first_seen: string|null; last_seen: string|null; report_count: number }[];
  edges: { id: string; source: string; target: string; relation: string;
           valid_from: string|null; valid_to: string|null; report_id: string|null }[];
  alerts: MemoryAlert[] };            // contradictions across the whole store

type Tactic = { tactic_id: string; shortname: string; name: string; ord: number };

type TechniqueDetail = { technique_id: string; name: string; description: string; tactics: string[];
  is_subtechnique: boolean; parent_id: string|null; platforms: string[]; url: string };

type EvalResponse = { ran_at: string; reports: number;
  systems: { system: "baseline"|"trinetra"; precision: number; recall: number; f1: number;
             parent_f1: number; avg_latency_ms: number }[];
  per_report: { report_id: string; title: string; url: string;
                baseline: { tp: string[]; fp: string[]; fn: string[] };
                trinetra: { tp: string[]; fp: string[]; fn: string[] } }[] };

type GeoPoint = { ioc_id: string; display: string; lat: number; lon: number;
                  country: string; city?: string; role: string };
```

---

## 9. Live events (SSE) — the heartbeat of the UI

`GET /api/analyses/{id}/events` returns `text/event-stream`. Each message is one JSON object in `data:`:

```json
{"analysis_id":"a1b2c3","stage":"verify","status":"progress","data":{...},"ts":"2026-10-30T15:01:02Z","elapsed_ms":4210}
```

- `status`: `started` | `progress` | `done` | `error` | `skipped`
- On connect, the server **replays all past events** for that analysis, then streams new ones. So refreshing the page rebuilds the canvas.
- Keep-alive comment every 15 s.
- The stream ends after `{"stage":"pipeline","status":"done"}` or `{"stage":"pipeline","status":"error"}`.

### Stage list (order = canvas layout) and `data` payloads
| stage | kind (badge) | `progress` data | `done` data |
|---|---|---|---|
| `ingest` | deterministic (+ OCR) | `{image: {index, source, chars, used}}` per image | `{title, source_url, published_at, chars, images, ocr_status}` |
| `guard` | hybrid | – | `{flags: InjectionFlag[]}` |
| `ioc` | deterministic | – | `{iocs: IOC[]}` (incl. filtered ones) |
| `ioc_role` | LLM | – | `{iocs: IOC[]}` (roles filled) |
| `behaviours` | LLM | `{behaviour: Behaviour}` | `{count}` |
| `retrieve` | vector | – | `{candidates: number}` |
| `verify` | LLM + rules | `{technique: TechniqueMatch}` (accepted or rejected, one at a time) | `{accepted, rejected}` |
| `link` | deterministic | – | `{techniques: TechniqueMatch[], iocs: IOC[]}` |
| `migrate` | deterministic | – | `{migrations: Migration[]}` |
| `tie` | ML model | – | `{predictions: TechniqueMatch[]}` |
| `flow` | graph | – | `{flow: AttackFlow}` |
| `detect` | hybrid | `{detection: Detection}` | `{count}` |
| `memory` | graph | – | `{alerts: MemoryAlert[]}` |
| `vulns` | deterministic (NVD + CISA KEV, cached) | – | `{vulnerabilities: VulnInfo[]}` |
| `brief` | LLM + rules | – | `{briefing: Briefing \| null}` |
| `export` | deterministic | – | `{formats: ["stix","navigator","sigma","flow"]}` |
| `pipeline` | – | – | `{report_id}` (or `error` with `{message}`) |

After `pipeline:done`, the frontend fetches `GET /api/analyses/{id}` once to get the complete, final object.

---

## 10. Environment variables (`.env.example`, P3 creates)

```bash
# backend
DATABASE_URL=postgresql://trinetra:trinetra@db:5432/trinetra
LLM_API_KEY=
LLM_API_BASE=                     # optional, for OpenAI-compatible endpoints
LLM_EXTRACT_MODEL=                # e.g. provider/model-name (stronger)
LLM_VERIFY_MODEL=                 # e.g. provider/model-name (faster)
LLM_CONCURRENCY=8
MAPPING_CONFIDENCE_THRESHOLD=0.6
FIRECRAWL_API_KEY=
N8N_WEBHOOK_URL=
ATTACK_VERSION=20.0
EMBED_MODEL=BAAI/bge-small-en-v1.5
CORS_ORIGINS=http://localhost:3000
GEOIP_DB_PATH=/data/dbip-city-lite.mmdb
# frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
```

---

## 11. Visual language (both frontend people use the same tokens)

- Dark "SOC console" theme. Background `#07090D`, surface `#0E1117`, raised `#151A22`, border `#232A35`, text `#E6EDF3`, muted `#8B95A5`.
- Accent (brand, TRINETRA "third eye"): `#22D3EE` (cyan) + glow; secondary `#A78BFA` (violet).
- Status: success `#34D399`, warning `#FBBF24`, danger `#F87171`, info `#60A5FA`.
- **Meaning colours (never reuse for anything else):**
  - observed = solid cyan border/fill
  - predicted = dashed violet border, 50 % opacity ("ghost")
  - unknown gap = hatched grey pattern
  - rejected = muted red, strikethrough ID
  - IOC roles: c2 `#F87171`, payload `#FB923C`, phishing `#FBBF24`, exfil `#E879F9`, victim `#60A5FA`, scanner `#94A3B8`, infrastructure `#2DD4BF`, unknown `#64748B`
- Fonts: **Inter** for UI, **JetBrains Mono** for IDs, IOCs, code.
- Tactic colours: 15 evenly spaced hues generated from `ord` (`hsl(ord*24, 70%, 60%)`), never hard-coded names.
- IOCs are **always shown defanged** (`display` field) and are **never clickable links**.
- Motion: fast and purposeful (150–300 ms). Nodes "light up" with a glow pulse while running.

---

## 12. Shared timeline (IST)

Everyone works **at the same time** after the skeleton lands. The Lead integrates continuously.

| Time | Lead (P5) | Everyone else |
|---|---|---|
| 14:45–15:30 | Builds + pushes the **skeleton repo** (all stubs, mocks, Docker, docs) | Read `00` + own file; install tools (Docker, Node 20, Python 3.11); P4 downloads the ATT&CK v20 bundle and explores it; P3 tries iocsearcher/Firecrawl in a scratch script; P1/P2 sketch layouts |
| 15:30 | **Share repo → everyone clones, creates `feat/<name>-…` branch** | Start replacing own stubs immediately |
| 15:30–20:00 | Real `llm.py`, events, LangGraph, verifier; integrates every 1–2 h | P3 ingest + IOC + routes · P4 loader, store, quotes, behaviours, retriever · P1 canvas, report page · P2 attack flow + simulator UI |
| 20:00 | **Milestone 1:** real CISA report runs end-to-end on real core code | — |
| 20:00–01:00 | Firewall, flow, simulator, detections, Sigma, memory, predictions | P3 exports + n8n · P4 roles, linker, migrator, retrieval tuning · P1 evidence viewer, exports, print · P2 detections, memory graph |
| 01:00 | **Milestone 2:** every feature wired to real data | — |
| 01:00–02:00 | Eval run | Bug fixes on real reports |
| 02:00 | **Feature freeze** (fixes only after this) | |
| 02:00–07:30 | Deploy, seed demo data, README, rehearse, record | P1/P2 polish + screenshots/GIF; P3/P4 fixes + help |
| 07:30 | **Submit** | |

**Integration loop (Lead, every 1–2 h):** `git pull` → `docker compose up --build` → `python scripts/load_attack.py` (once, after P4's loader lands) → `python scripts/smoke_test.py` (one sample report; every SSE stage must reach `done`) → open the UI → revert anything that breaks `main`.

### Cut order if late
Globe → Firecrawl watch → contradiction cards → TIE predictions. **Never cut:** verifier, evidence quotes, scoreboard, live pipeline.
