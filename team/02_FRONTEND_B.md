# 02 — FRONTEND B: Visual intelligence screens (the "wow" views)

> **AI agent instructions:** You are building the visual analysis views of TRINETRA. First read `team/00_SHARED_CONTRACTS.md` completely (architecture, types, API, SSE events, colours). Use the shared `lib/` (types, API client, store, tactics helpers) — the Lead's skeleton repo already contains a starting `lib/types.ts` and mocks, and Frontend A completes it. **Import from it, don't duplicate it.** You start at the same time as Frontend A; if a helper you need isn't there yet, write it locally inside your component folder and switch to the shared one when it lands. Work against mock data (`NEXT_PUBLIC_USE_MOCKS=true`) until the backend is live.

**Person:** Frontend B
**You own:** `app/graph/page.tsx`, `app/eval/page.tsx`, `components/{attack-flow,simulator,detection-panel,memory-graph,eval,globe}/`, and your mock files `lib/mock/{simulate,readiness,graph,eval,geo}.json`.
**You do NOT own:** layout, home, report page shell, pipeline canvas, IOC table, technique cards, heatmap, `lib/` core files (Frontend A). Frontend A renders your components inside report tabs: **Attack Flow**, **Detections**, **Map**.

---

## 1. Where you fit

```
/report/[id]   (shell by Frontend A)
   ├─ tab "Attack Flow"  → <AttackFlowView analysis />      ← YOU  (flow + predictions + gaps + simulator)
   ├─ tab "Detections"   → <DetectionPanel analysis />      ← YOU  (readiness + Sigma)
   └─ tab "Map" (NICE)   → <GlobeView analysisId />         ← YOU
/graph                   → <MemoryGraphPage />              ← YOU  (cross-report memory + contradictions)
/eval                    → <ScoreboardPage />               ← YOU  (accuracy proof)
```

Your screens are what judges remember: the attack building itself node by node, blocking a step and watching attack paths die, a detection gap lighting up red, a graph that remembers across reports, and a hard accuracy number.

### Component exports (Frontend A imports these exact names)
```ts
// components/attack-flow/index.ts
export { AttackFlowView } from "./AttackFlowView";       // props: { analysis: Partial<ReportAnalysis> }
// components/detection-panel/index.ts
export { DetectionPanel } from "./DetectionPanel";       // props: { analysis: Partial<ReportAnalysis> }
// components/globe/index.ts
export { GlobeView } from "./GlobeView";                 // props: { analysisId: string }
// components/memory-graph/index.ts
export { ContradictionCard } from "./ContradictionCard"; // props: { alert: MemoryAlert }
```
The skeleton repo already has these as stubs (rendering "Coming soon"), so Frontend A can wire the tabs immediately. You replace the stubs; keep the export names and props unchanged.

---

## 2. Tech stack (what you use and where)

| Tool | Install | Used for |
|---|---|---|
| @xyflow/react (React Flow) | `npm i @xyflow/react` | Attack flow graph + simulator |
| @dagrejs/dagre | `npm i @dagrejs/dagre` | Left→right auto-layout of the flow |
| Framer Motion | (already in project) | Node-by-node build, path-break animation, counters |
| sigma.js + graphology | `npm i sigma graphology @react-sigma/core graphology-layout-forceatlas2 graphology-layout` | WebGL memory graph |
| deck.gl + react-map-gl + maplibre-gl | `npm i deck.gl @deck.gl/react @deck.gl/layers @deck.gl/geo-layers react-map-gl maplibre-gl` | Globe/map (NICE — last) |
| react-syntax-highlighter | (shared) | Sigma YAML viewer |
| shadcn/ui components | (Frontend A installs; you may `npx shadcn@latest add slider switch checkbox table` ) | controls |
| lucide-react | (shared) | icons |

Map tiles for MapLibre: use a free style that needs no key (e.g. `https://demotiles.maplibre.org/style.json`) or a dark style from a provider whose free tier needs no card; **no Mapbox token**.

Do **not** add another chart library unless the eval page truly needs one; simple bars with divs + Framer Motion look better and load faster. If you need one, use Recharts only.

---

## 3. Attack Flow view — `components/attack-flow/` ⭐⭐ biggest wow

Input: `analysis.flow` (`AttackFlow`), `analysis.techniques` (accepted), `analysis.predictions`, `analysis.iocs`.

### 3.1 Layout
- React Flow canvas, height ~600 px, dark dotted background, minimap + zoom controls.
- Use **dagre** with `rankdir: "LR"`, nodes sorted by `order`; group visually by tactic using faint vertical **swimlane bands** behind nodes (one band per tactic present, coloured via `tacticColor(ord)`, label at top). Compute band x-ranges from node positions after layout.
- Legend (top-right): ● Observed · ◌ Predicted ("hunt for these") · ▨ Unknown gap.

### 3.2 Node types (custom components)
- **ObservedNode**: solid cyan border, tactic colour strip on the left, `T1059.001` (mono) + name, small IOC chips (defanged) for `linked_iocs` (max 3 + "+n"), confidence dot. Click → side panel with evidence quote (reuse Frontend A's technique card if exported; else render quote + rationale).
- **PredictedNode** ("ghost"): dashed violet border, 50 % opacity, label "Hunt for: T1053.005 Scheduled Task", `prediction_score` as a small bar, hover tooltip "Not in the report. Commonly seen with the observed techniques — check your logs."
- **UnknownNode**: hatched grey (CSS `repeating-linear-gradient`), label "Persistence — not established in report", tooltip explains it's a gap in the intelligence, not an observation.
- **Edges**: `followed_by` solid arrow; `enables` thicker arrow; `uses_infrastructure` dotted; edges into predicted nodes are dashed violet.

### 3.3 Build animation (the moment)
- On first render after `flow.done` (or when the tab opens for a finished report), reveal nodes **one by one in `order`** (120–180 ms apart): node scales/fades in, then its incoming edge draws (animate `strokeDashoffset`). Predicted nodes appear last with a soft shimmer; unknown nodes fade in last.
- "▶ Replay" button re-runs the animation.
- Respect `prefers-reduced-motion` (show instantly).

### 3.4 Disruption simulator — `components/simulator/` ⭐ (embedded in this view)
- Toggle "🛡 Simulate defence" switches the canvas to *simulation mode*: clicking an observed node toggles it **blocked** (red border, ⛔ icon, struck label). Multi-select allowed.
- Each change calls `simulate(id, blockedNodeIds)` (debounce 250 ms) → `SimulateResponse`.
- Show a **result panel** (right side, animated):
  - Big number: `broken_pct`% "of attack paths disrupted" (animated counter, colour from red→green as it increases), "`broken_paths` / `total_paths` paths".
  - Nodes in `affected_node_ids` fade to 25 % opacity with a "cut off" badge; edges on any **surviving path** glow amber and animate ("attacker can still get through here").
  - **Countermeasures** list for blocked techniques: name, id, source badge (`D3FEND` or `ATT&CK Mitigation`), "derived" tag if `derived`, link to `url`.
  - If `note` present (e.g. "paths capped"), show it small.
- "Best single block" helper (nice touch): button that calls `simulate` for each observed node one at a time (sequentially, max 15 calls) and highlights the node with the highest `broken_pct` → "Blocking T1071.001 breaks 83 % of paths". Cache results per node.
- Mock: `lib/mock/simulate.json` (+ compute a fake response client-side in mock mode: broken_pct = 100 × blocked nodes on path / total).

### 3.5 Predictions list (below canvas)
Compact table "🎯 Hunt for these": technique ID, name, tactic, prediction score bar, "Why?" tooltip ("Frequently co-occurs with T1566.001, T1059.001 in known campaigns"). Clear label: **Predicted, not observed.**

---

## 4. Detection panel — `components/detection-panel/` ⭐ (tab "Detections")

Input: `analysis.detections` (`Detection[]`), `analysis.techniques`.

### 4.1 Telemetry checklist (top)
- Chips/checkboxes for each `Telemetry` value with friendly names and icons:
  `sysmon` "Sysmon", `windows_security` "Windows Security Log", `powershell_scriptblock` "PowerShell Script Block Logging", `edr` "EDR", `dns` "DNS logs", `proxy` "Web proxy logs", `firewall` "Firewall logs", `netflow` "NetFlow", `cloud_audit` "Cloud audit logs", `email_gateway` "Email gateway", `linux_auditd` "Linux auditd".
- Presets: "Typical SME" (windows_security, firewall, email_gateway), "Mature SOC" (all), "Nothing" (none). Save selection in `localStorage` (wrap in try/catch).
- Any change → `readiness(id, telemetry)` (debounce 250 ms).

### 4.2 Readiness result
- **Readiness gauge**: big radial ring `readiness_pct`% with label "Detection readiness for this attack".
- Matrix/table: rows = techniques; columns = status pill (`covered` green / `partial` amber / `gap` red), "you have" chips, "missing" chips (red). Sort gaps first.
- Toggling a telemetry chip should visibly flip rows (animate row colour). This is the demo moment: "untick PowerShell logging → gap appears".

### 4.3 Technique detection detail (expand row)
- Detection Strategies → Analytics → log sources tree (strategy name + id, analytic name + platforms, log source name + data component + our telemetry bucket).
- **Sigma rules** for the technique: tabs per rule; YAML with syntax highlighting; status badge `✓ Valid (pySigma)` or `✗ Invalid` with errors; "kind" badge (IOC rule / behaviour rule); conversions (e.g. Splunk query) in a sub-tab with copy button; "Download .yml" button (Blob download).
- Global "Download all Sigma (YAML)" → `exportUrl(id,"sigma")`.

---

## 5. Memory graph page — `app/graph/page.tsx`, `components/memory-graph/` ⭐

Input: `getGraph(at?)` → `GraphResponse`.

### 5.1 Graph
- `@react-sigma/core` `SigmaContainer`, full-height dark canvas. Build a graphology graph from nodes/edges; run ForceAtlas2 for ~2 s in a web worker (`graphology-layout-forceatlas2/worker`), then stop.
- Node style by `type`: report (white square-ish, larger), ioc (role colour if known else cyan, label = defanged `label`), technique (tactic colour), actor (red, bigger), malware (orange), sector (blue). Size by `report_count`.
- Hover: highlight neighbours, dim the rest; show label card. Click node → right drawer: type, label, first/last seen, list of reports it appears in (clickable → `/report/[id]`), relationships.
- Search box: find node by label, zoom to it.
- Filters: toggle node types; "only entities seen in ≥2 reports" (the interesting overlaps).

### 5.2 Time slider (temporal replay)
- Slider over the date range of `first_seen..last_seen`. Moving it calls `getGraph(at)` (debounced) or filters client-side by `valid_from <= at && (valid_to == null || valid_to > at)`; nodes/edges fade in/out (animate opacity via sigma reducers).
- "▶ Play" animates from oldest to newest report.

### 5.3 Alerts panel
- Left sidebar: list of `alerts` from `GraphResponse` + latest report alerts. **ContradictionCard** component (exported for Frontend A):
  - Header: "⚡ Conflicting claims about {entity_display}".
  - Two (or more) columns: each report title, date, quote, claim.
  - Footer: `explained_by_time` → "Likely explained by time (infrastructure reused/reassigned)" in amber, else "Genuine conflict — verify before acting" in red. Always add small text: "Shared infrastructure is not proof of the same operator."
- Seen-before alerts: "🔁 {entity_display} appeared in {n} reports" → click focuses node.

---

## 6. Scoreboard page — `app/eval/page.tsx`, `components/eval/` ⭐ (proof)

Input: `getEval()` → `EvalResponse`.
- Hero: "Measured, not claimed." + `reports` count + `ran_at`.
- Two big metric cards side by side: **Plain LLM** vs **TRINETRA**: Precision, Recall, F1, parent-level F1, avg latency. Animated bars; difference badge (e.g. "+0.31 F1"). Values come only from the API — **never hard-code**.
- Explanation strip (3 icons): "Ground truth = ATT&CK tables published in CISA advisories" · "Precision = how many claimed techniques were right" · "Recall = how many real techniques we found".
- Per-report table: title (link), and for each system TP/FP/FN counts; expand row → chips: TP green, FP red ("hallucinated or wrong"), FN grey ("missed").
- Empty state if no run yet: "Run `python scripts/run_eval.py` to generate results."

---

## 7. Globe / Map — `components/globe/` (NICE — only after everything above works)
- `getGeo(analysisId)` → points. deck.gl `GlobeView` (or flat `MapView` if globe is buggy) + `ScatterplotLayer` (colour by role) + `ArcLayer` from IOC points to a single "victim" point if provided, else no arcs.
- Tooltip: defanged display, country, city, role.
- Note under map: "Location from offline IP geolocation (DB-IP Lite). IP location ≠ attacker location."

---

## 8. Mocks you create (realistic, matching contract shapes)
- `simulate.json` — response for blocking one C2 node in Frontend A's mock flow.
- `readiness.json` — 9 techniques, mixed covered/partial/gap.
- `graph.json` — ~60 nodes / ~120 edges across 4 reports with 3 IOCs shared between reports and 1 contradiction alert.
- `eval.json` — 4 reports, plausible structure; label clearly in the file `"_mock": true` and show a "MOCK DATA" ribbon in the UI when that flag is present (so we never demo fake numbers by accident).
- `geo.json` — 8 points.

---

## 9. Quality bar (acceptance checks)
- [ ] `npm run build` passes; no TS errors; no console errors.
- [ ] Attack flow: observed/predicted/unknown are visually unmistakable in a screenshot, even in greyscale (border style + icon, not colour only).
- [ ] Build animation runs smoothly at 60 fps with 25 nodes; replay works.
- [ ] Simulator: blocking/unblocking updates within 300 ms (real API) and the % and surviving paths match the response.
- [ ] Detection panel: toggling a telemetry chip visibly flips at least one row; Sigma YAML renders and downloads.
- [ ] Memory graph renders 500 nodes / 1,500 edges smoothly; time slider and filters work.
- [ ] Scoreboard shows real API numbers; mock ribbon appears when mock data is used.
- [ ] Everything readable on a 1280×720 projector; usable on a phone (graphs become scrollable/zoomable).
- [ ] IOCs only ever shown via `display` (defanged), never as links.

## 10. Don'ts
- Don't compute attack paths or readiness on the client in real mode — the backend is the source of truth (client-side compute is only for mock mode).
- Don't mix predicted techniques into "observed" lists or counts.
- Don't hard-code tactic names or eval numbers.
- Don't add Mapbox or any key-requiring map service.
- Don't edit Frontend A's files; ask them.

## 11. Your timeline (parallel build — you never wait for the backend or Frontend A)
| Time | Deliver |
|---|---|
| 14:45–15:30 | (Before the repo lands) read `00` + this file; install Node 20; sketch the flow/simulator/graph screens |
| 15:30 | Clone skeleton → branch `feat/frontend-b` → `npm install` → install your libs → `npm run dev` works |
| 15:30–16:15 | Your mock JSON files (`simulate`, `readiness`, `graph`, `eval`, `geo`) → push |
| 16:15–19:30 | Attack flow view: node types, dagre layout, swimlanes, build animation (on mock `analysis.json`) |
| 19:30–21:30 | Simulator mode + result panel + best-single-block |
| 21:30–23:30 | Detection panel (telemetry, readiness gauge, Sigma viewer) |
| 23:30–01:00 | Memory graph page + time slider + contradiction cards |
| 01:00–02:00 | Scoreboard page; switch every view to the real API; **feature freeze 02:00** |
| 02:00–04:00 | Globe (only if everything else is solid), polish, recordings for the README GIF |

Push small working commits at least every 1–2 hours; never push a broken `npm run build`.
