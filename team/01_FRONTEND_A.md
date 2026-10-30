# 01 — FRONTEND A: Core analysis screens

> **AI agent instructions:** You are building the frontend core of TRINETRA. First read `team/00_SHARED_CONTRACTS.md` completely (architecture, types, API, SSE events, colours). Then build exactly what this file says. Do not invent new API endpoints or change data shapes. Work against **mock data** until the backend is live (`NEXT_PUBLIC_USE_MOCKS=true`). The skeleton repo gives you and Frontend B a starting `lib/`; you complete it and push improvements early because Frontend B builds on it in parallel.

**Person:** Frontend A
**You own:** `frontend/` project setup, `app/layout.tsx`, `app/page.tsx`, `app/report/[id]/page.tsx`, `components/ui/`, `components/{input,pipeline-canvas,report-viewer,ioc-table,technique-card,attack-heatmap,exports,print-report,layout}/`, `lib/*` (except files Frontend B adds under `lib/mock/`).
**You do NOT own:** attack flow, simulator, detections, memory graph, eval, globe (Frontend B). Leave a tab/slot for them.

---

## 1. Where you fit

```
User ──► [Home: input]  ──POST /api/analyses──►  backend
              │
              ▼
      /report/[id]  ── SSE /events ──► live pipeline canvas  (YOU)
              │                         IOC table             (YOU)
              │                         technique cards       (YOU)
              │                         evidence viewer       (YOU)
              │                         ATT&CK heatmap        (YOU)
              │                         exports + print       (YOU)
              ├── tab "Attack Flow"  → Frontend B component
              ├── tab "Detections"   → Frontend B component
              └── tab "Map" (NICE)   → Frontend B component
```

The **first 10 seconds** of the demo are your screens: the judge pastes a URL, the pipeline lights up, IOCs appear instantly, techniques stream in with highlighted evidence. That moment must feel fast, alive and premium.

---

## 2. Tech stack (what you use and where)

| Tool | Install | Used for |
|---|---|---|
| Next.js 15 (App Router) + TypeScript | `npx create-next-app@latest frontend --ts --tailwind --eslint --app --src-dir=false --import-alias "@/*"` | framework |
| Tailwind CSS | (included) | styling with tokens from contracts §11 |
| shadcn/ui | `npx shadcn@latest init` then add: `button card tabs badge tooltip dialog sheet input textarea scroll-area separator skeleton progress dropdown-menu toggle-group accordion sonner` | components |
| Framer Motion | `npm i framer-motion` | glow pulses, list entrance, number counters |
| @xyflow/react | `npm i @xyflow/react` | **pipeline canvas** |
| Zustand | `npm i zustand` | live analysis store fed by SSE |
| @tanstack/react-query | `npm i @tanstack/react-query` | REST fetching |
| lucide-react | `npm i lucide-react` | icons |
| react-dropzone | `npm i react-dropzone` | PDF upload |
| shiki or react-syntax-highlighter | `npm i react-syntax-highlighter` | JSON viewer for STIX preview |
| clsx + tailwind-merge | (shadcn adds) | class helpers |

Fonts: `next/font/google` → Inter + JetBrains Mono.

Do **not** add: Redux, MUI, Chakra, any auth library, any chart library for the heatmap (build it with CSS grid).

---

## 3. The shared `lib/` (you own it; the skeleton gives you a starting version)

The Lead's skeleton repo already contains a Next.js app, `lib/types.ts` and basic mocks, so Frontend B can start at the same time as you. Your first job after cloning is to **complete and own** these files exactly as specified below (push the improved versions early — Frontend B uses them).

### 3.1 `lib/types.ts`
Translate **every** model in contracts §6 and every shape in §8 into TypeScript, 1:1, same field names (snake_case). Include:
`IOCType, IOCRole, Telemetry, Evidence, Confidence, IOC, Behaviour, Candidate, TechniqueMatch, InjectionFlag, FlowNode, FlowEdge, AttackFlow, LogSource, Analytic, DetectionStrategy, SigmaRule, Detection, ReportRef, MemoryAlert, Migration, ReportAnalysis, AnalysisListItem, SimulateResponse, ReadinessResponse, GraphResponse, Tactic, TechniqueDetail, EvalResponse, GeoPoint`, plus:

```ts
export type StageName = "ingest"|"guard"|"ioc"|"ioc_role"|"behaviours"|"retrieve"|"verify"
  |"link"|"migrate"|"tie"|"flow"|"detect"|"memory"|"export"|"pipeline";
export type StageStatus = "idle"|"started"|"progress"|"done"|"error"|"skipped";
export type PipelineEvent = { analysis_id: string; stage: StageName;
  status: Exclude<StageStatus,"idle">; data: any; ts: string; elapsed_ms: number };
```

### 3.2 `lib/api.ts`
Typed fetch client. Base URL `process.env.NEXT_PUBLIC_API_URL`. If `NEXT_PUBLIC_USE_MOCKS === "true"`, return the mock JSON instead (with a 300–800 ms fake delay).
Functions (one per endpoint in contracts §8):
```ts
createAnalysis(input: {url?: string; text?: string; title?: string} | File): Promise<{id: string}>
listAnalyses(): Promise<AnalysisListItem[]>
getAnalysis(id: string): Promise<ReportAnalysis>
sendFeedback(id, body): Promise<{ok: boolean}>
simulate(id, blockedNodeIds: string[]): Promise<SimulateResponse>
readiness(id, telemetry: Telemetry[]): Promise<ReadinessResponse>
exportUrl(id, fmt: "stix"|"navigator"|"sigma"|"flow"): string   // used as <a href download>
getGraph(at?: string): Promise<GraphResponse>
getTactics(): Promise<Tactic[]>
getTechnique(id: string): Promise<TechniqueDetail>
getEval(): Promise<EvalResponse>
getGeo(id: string): Promise<GeoPoint[]>
```
Errors: throw `ApiError {status, message}`; UI shows a toast (sonner).

### 3.3 `lib/sse.ts` — `useAnalysisStream(id)`
- Opens `EventSource(`${API}/api/analyses/${id}/events`)`.
- Parses each message as `PipelineEvent`, pushes into the Zustand store.
- Reconnects automatically (EventSource does this); server replays history, so **dedupe** events by `(stage,status,ts,JSON.stringify(data).length)`.
- Closes on `pipeline:done` / `pipeline:error`, then calls `getAnalysis(id)` and replaces store state with the final object.
- **Mock mode:** replay `lib/mock/events.json` with realistic delays (ingest 400 ms, ioc 300 ms, behaviours streaming every 250 ms, verify every 300 ms, etc.) so the canvas animates without a backend.

### 3.4 `lib/store.ts` (Zustand)
```ts
type AnalysisState = {
  analysis: Partial<ReportAnalysis>;          // built up from events
  stages: Record<StageName, {status: StageStatus; startedAt?: number; ms?: number; lastData?: any}>;
  log: PipelineEvent[];
  selectedTechniqueId?: string; hoveredEvidence?: {start:number; end:number};
  applyEvent(e: PipelineEvent): void;          // merges data into analysis
  setFinal(a: ReportAnalysis): void;
  select(techId?: string): void;
};
```
`applyEvent` merge rules: `ingest.done` → title/source; `guard.done` → injection_flags; `ioc.done`/`ioc_role.done`/`link.done` → replace `iocs`; `behaviours.progress` → push behaviour; `verify.progress` → upsert technique by `technique_id+behaviour_id`; `link.done` → replace techniques; `migrate.done`, `tie.done` (predictions), `flow.done`, `detect.progress` (push), `memory.done` (alerts).

### 3.5 `lib/tactics.ts`
`useTactics()` → react-query on `getTactics()`; `tacticColor(ord) = hsl(ord*24, 70%, 60%)`; `tacticByShortname` map. Fallback (only if API fails): show shortname as label, grey colour. **Never hard-code tactic names.**

### 3.6 `lib/defang.ts`
Safety helper: `safeDisplay(ioc) => ioc.display` (never use `value` in the DOM). Lint rule by convention: grep for `.value}` in IOC components before merging.

### 3.7 `lib/mock/` (realistic, hand-made)
- `analysis.json` — a complete `ReportAnalysis` for a fake-but-realistic ransomware report (~3,000 chars of text): 12 IOCs (incl. 2 filtered: a private IP and microsoft.com; defanged display values), 10 behaviours, 9 accepted techniques across ≥7 tactics (e.g. T1566.001, T1204.002, T1059.001, T1547.001, T1003.001, T1021.001, T1071.001, T1041, T1486), 6 rejected candidates covering each `reject_reason`, `injection_flags: []` (make a second file `analysis-poisoned.json` with 1 high-severity flag for testing the banner), 3 predictions, 1 migration, a flow with 9 observed + 3 predicted + 2 unknown nodes, 4 detections with sigma rules, 2 memory alerts (1 seen_before, 1 contradiction). **All evidence offsets must be correct** (write a tiny node script `scripts/check-mock.mjs` that asserts `text.slice(start,end) === quote`).
- `events.json` — the event sequence that produces `analysis.json`.
- `tactics.json` — 15 tactics with `ord` (copy real names from attack.mitre.org v20 Enterprise matrix).
- `list.json` — 4 `AnalysisListItem`s.
Frontend B adds `simulate.json`, `readiness.json`, `graph.json`, `eval.json`, `geo.json`.

---

## 4. Screens and components

### 4.1 App shell — `app/layout.tsx`, `components/layout/`
- Dark theme tokens from contracts §11 as CSS variables in `globals.css`; Tailwind config maps them (`bg-surface`, `text-muted`, `border-line`, `text-accent`).
- Top bar: TRINETRA logo (simple SVG: a stylised eye with a third vertical eye — original design, cyan glow), nav: **Analyze** (`/`), **Memory Graph** (`/graph`), **Scoreboard** (`/eval`). Right side: small "ATT&CK v20" badge and backend health dot (green if `/api/health.ok`).
- Subtle animated grid/noise background on the home page only (CSS, cheap).
- `<Providers>`: React Query + Toaster.

### 4.2 Home — `app/page.tsx`, `components/input/`
- Hero: one line "Threat reports in. Verified intelligence out." + sub-line "Every technique proven by the report's own words."
- **Input card** with 3 tabs: *URL* | *Paste text* | *Upload PDF* (react-dropzone, PDF only, max 20 MB).
  - Validate URL format; text ≥ 200 chars.
  - Big "Analyze" button → `createAnalysis` → `router.push('/report/'+id)` immediately (don't wait).
  - "Try a sample" chips: 2–3 preset CISA advisory URLs (Lead gives you the final URLs; placeholders now) and "Poisoned report demo" (preset text from Lead).
- **Recent analyses** list (`listAnalyses`): title, source domain, date, counts (IOCs, techniques, alerts), status pill; click → report page.
- Keyboard: `Cmd/Ctrl+Enter` submits.

### 4.3 Report page — `app/report/[id]/page.tsx`
Layout (desktop ≥1280px):
```
┌──────────────────────────────────────────────────────────────────────┐
│ Title · source domain · published date · status · Export ▾ · Print    │
│ [injection banner if flags]  [memory alert chips]                      │
├──────────────────────────────────────────────────────────────────────┤
│ PIPELINE CANVAS (full width, 220px tall, collapsible after done)       │
├──────────────────────────────────────────────────────────────────────┤
│ Tabs: Overview | Evidence | Attack Flow* | Detections* | Map* | Raw    │
└──────────────────────────────────────────────────────────────────────┘
* = Frontend B components; render <ComingSoon/> placeholder until merged.
```
- Calls `useAnalysisStream(id)`; if analysis already `done` (opening an old report), fetch `getAnalysis` and mark all stages done (no animation replay unless user clicks "Replay pipeline").
- **Stat strip** under header (animated counters): IOCs (non-filtered), Techniques accepted, Tactics covered (/15), Rejected (hallucinations blocked), Time taken. "Hallucinations blocked" = count of rejected with reason `id_not_in_v20` or `quote_not_in_source` — a pitch-worthy number; show it proudly with a shield icon.
- Mobile (<768px): stack everything; canvas becomes a vertical stage list.

### 4.4 Pipeline canvas — `components/pipeline-canvas/` ⭐ wow element
- React Flow, read-only (no dragging), `fitView`, dark background with dots.
- Nodes = stages in contracts §9 order, laid out as the architecture: `ingest → guard → (ioc → ioc_role) ∥ (behaviours → retrieve → verify) → link → (migrate ∥ tie ∥ flow ∥ detect ∥ memory) → export`. Hard-code positions in `layout.ts` (two parallel lanes then a fan-out).
- Custom node component:
  - Icon + name ("IOC Engine", "Behaviour Agent", "Retriever", "Verifier"…) + **badge** with kind from contracts §9 (`deterministic` grey, `LLM` violet, `vector` cyan, `hybrid` amber, `graph` teal, `ML model` pink).
  - States: idle (dim) → started/progress (cyan border + **pulsing glow** via Framer Motion + small spinner + live counter e.g. "7 behaviours") → done (green check + `ms` time) → error (red) → skipped (grey dashed).
  - Edges animate (`animated: true`) while the target is running; turn solid when done.
- Click a node → right **Sheet** with: description of what this agent does (1 line each, write them), status, timing, and the last `data` payload pretty-printed (truncate long arrays to 20 items).
- Under the canvas: a thin **live log ticker** (last 3 events, monospace, fades).

### 4.5 Overview tab
Two columns: left **IOC table**, right **Technique list + heatmap**.

#### IOC table — `components/ioc-table/`
- Columns: Type (icon), Indicator (`display`, monospace, copy button copies `display` — defanged), Role (coloured pill per contracts §11), Confidence (mini bars: extraction / role), Linked techniques (ID chips → click selects technique), Evidence (count; hover shows first quote).
- Filters: type multi-select, role multi-select, search box.
- "Filtered out (n)" collapsible section showing filtered IOCs with `filtered_reason` — proves we remove noise.
- Rows animate in as `ioc.done` arrives; roles shimmer until `ioc_role.done`.
- Never render IOC as `<a>`. Never show `value`.

#### Technique cards — `components/technique-card/`
- Grouped by tactic (ordered by tactic `ord`), each group header coloured.
- Card: `T1059.001` (mono) + name + tactic pills + **confidence ring** (mapping) + evidence quote in a styled blockquote (first 200 chars, "show more") + rationale (muted) + linked IOC chips (defanged) + link icon to `url` (attack.mitre.org opens in new tab — that's fine, it's MITRE not an IOC).
- Buttons: 👍 / 👎 → `sendFeedback` (optimistic UI; toast "Thanks — logged for evaluation").
- "**Show rejected candidates (n)**" accordion per group or global: rejected cards greyed, ID struck through, reason badge with human text:
  - `id_not_in_v20` → "Hallucinated ID — not in ATT&CK v20"
  - `quote_not_in_source` → "Quote not found in report"
  - `verifier_mismatch` → "Evidence doesn't match technique definition"
  - `low_confidence` → "Below confidence threshold"
  - `deprecated` → "Deprecated in v20 — see migration"
- **Migrations** (if any): small banner "3 mappings upgraded to ATT&CK v20" listing `old_id → new_ids` with reason.
- Predictions do **not** appear here (they live in Frontend B's flow tab); show only a link "3 predicted techniques to hunt → Attack Flow".
- Cards appear one by one as `verify.progress` events arrive (Framer Motion layout animation).

#### ATT&CK heatmap — `components/attack-heatmap/`
- 15 columns = tactics from `/api/attack/tactics` (ordered by `ord`), header shows name + count.
- Cells = accepted techniques in that tactic (a technique with multiple tactics appears in each), colour intensity = mapping confidence, predicted techniques shown as dashed violet cells **only if** a toggle "Show predicted" is on.
- Empty tactic column: show a faint "—"; it visually explains "unknown gaps".
- Hover cell → tooltip (name, confidence, quote preview). Click → select technique (scroll card into view + highlight evidence).
- Compact mode for the Overview; full-size in the Evidence tab sidebar.

### 4.6 Evidence tab — `components/report-viewer/` ⭐ trust element
- Left (60%): the full report `text` with **highlights**:
  - Technique evidence spans: underline + background tinted with tactic colour; multiple overlapping spans → render segments (split the text at every start/end boundary; each segment carries the list of covering spans).
  - IOC evidence spans: dotted underline in role colour; the text itself already contains whatever the report had (defanged or not) — that's fine, it's the source; but do not make it clickable.
  - Injection flag spans: red wavy underline + ⚠ icon.
- Right (40%): sticky panel showing the selected technique card (reuse component) + all its evidence spans ("Jump to 1 of 3").
- Clicking a highlight selects its technique; selecting a technique elsewhere scrolls the text to the first span and flashes it.
- Use a virtualised or chunked render if text > 50k chars (render paragraphs; `content-visibility: auto`).

### 4.7 Injection + memory banners
- If `injection_flags.length > 0`: red banner at top "⚠ Prompt-injection attempt detected in this report (mapped to ATT&CK {technique_id}). Content was treated as data only." + "Show where" → jumps to the span in Evidence tab.
- Memory alerts as chips under the header: "🔁 evil[.]com seen in 2 earlier reports" (link to `/graph`), "⚡ Conflicting attribution" (opens a dialog Frontend B builds — import `ContradictionCard` from `components/memory-graph` when available; until then show the `message`).

### 4.8 Exports — `components/exports/`
Dropdown "Export ▾": STIX 2.1 (JSON), ATT&CK Navigator layer (JSON) — tooltip "Open at mitre-attack.github.io/attack-navigator → Open Existing Layer", Sigma rules (YAML), Attack Flow (JSON), Print / Save as PDF.
- Each is `<a href={exportUrl(id,fmt)} download>`; disabled until `pipeline:done`.
- "Preview STIX" opens a dialog with syntax-highlighted JSON (fetch the URL).

### 4.9 Print / PDF report — `components/print-report/`, route `app/report/[id]/print/page.tsx`
- Clean light-theme printable page: title, source, date, summary stats, IOC table (defanged), techniques grouped by tactic with evidence quotes, detection gaps summary, footer "Generated by TRINETRA · ATT&CK v20".
- `@media print` CSS, page breaks between sections; auto-calls `window.print()` when opened with `?auto=1`.

### 4.10 Raw tab
Collapsible JSON of the full `ReportAnalysis` (for judges who want to see structure). Copy button.

---

## 5. Quality bar (acceptance checks)

- [ ] `npm run build` passes with zero TypeScript errors.
- [ ] With `NEXT_PUBLIC_USE_MOCKS=true`, the full flow works: home → analyze → canvas animates → IOCs → techniques stream in → evidence highlights → exports menu.
- [ ] With the real backend, the same flow works on a real CISA advisory.
- [ ] First paint of report page < 1 s; no layout jumps when events arrive (reserve space with skeletons).
- [ ] Every highlight's text equals its `quote` (dev-only assertion logs a console error if not).
- [ ] No IOC is ever rendered from `.value` or as a link.
- [ ] Rejected candidates and their reasons are visible.
- [ ] Refreshing the report page mid-run restores state (server replays events).
- [ ] Works at 1280×720 (projector!) and on a phone (judges open the link).
- [ ] Lighthouse accessibility ≥ 90: focus rings, aria labels on icon buttons, colour is never the only signal (add text/icons).

## 6. Don'ts
- Don't block the UI waiting for the whole analysis — always render progressively from events.
- Don't hard-code tactic names, technique counts or eval numbers.
- Don't fetch `getAnalysis` in a polling loop while SSE is open.
- Don't put API keys in the frontend.
- Don't build Frontend B's components; leave slots.

## 7. Your timeline (parallel build — you never wait for the backend)
| Time | Deliver |
|---|---|
| 14:45–15:30 | (Before the repo lands) read `00` + this file; install Node 20; sketch layouts; pick logo SVG + fonts |
| 15:30 | Clone skeleton → branch `feat/frontend-a` → `npm install` → `npm run dev` works on mocks |
| 15:30–16:30 | Theme tokens, app shell, **complete `lib/` (types, api, sse, store, tactics, realistic mocks) → push** (Frontend B builds on it) |
| 16:30–18:30 | Home + input; pipeline canvas animating on mock events |
| 18:30–20:30 | Report page, IOC table, technique cards, heatmap |
| 20:00 | Backend Milestone 1 → switch `NEXT_PUBLIC_USE_MOCKS=false` and test on a real report |
| 20:30–23:00 | Evidence viewer with highlights + selection sync |
| 23:00–01:00 | Exports, print view, injection/memory banners, mobile, wire Frontend B's tabs |
| 01:00–02:00 | Fix issues on real reports; **feature freeze 02:00** |
| 02:00–05:00 | Polish animations, help Frontend B, screenshots/GIF for README |

Push small working commits at least every 1–2 hours; never push a broken `npm run build`.
