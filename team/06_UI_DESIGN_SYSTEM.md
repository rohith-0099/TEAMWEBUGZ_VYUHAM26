Restyle the existing TRINETRA frontend to match team/06_UI_DESIGN_SYSTEM.md ("Neon Ops") exactly.
Read that file fully first. It is the single source of truth for colours, fonts, charts and layouts.

RULES
- Restyle only. Do NOT change data flow, API calls, types, SSE logic, routes or props. Everything that works now must still work.
- Use the exact hex values, fonts and component specs from 06. No other colours, no extra gradients, no glassmorphism, no drop shadows.
- Keep all features visible: pipeline canvas, IOC table, technique cards, evidence highlights, attack flow, simulator, detections, memory graph, scoreboard.

STEPS
1. Tokens: put every colour from 06 §1 into globals.css (:root CSS variables) and tailwind.config (theme.extend.colors);
   add TACTIC_COLORS to lib/tactics.ts and make tacticColor(ord) use it.
2. Fonts: Inter (UI), Geist Mono via the `geist` package (numbers, technique IDs, IOCs, tabular-nums),
   Doto from next/font/google with VT323 fallback (console panel titles only).
3. Base: true-black page #000000, cards #0A0A0A + 1px #1F1F1F border + 20px radius, no shadows.
4. Build shared components in components/charts/ per 06 §4 with d3-shape + d3-scale:
   StatCard, PillMarker, BracketChip, NeonRadar (15 tactic spokes, curveCatmullRomClosed, glow filter),
   StreamChart (nested gradient bands, black vertical lines with pill counts), TileGrid, StackedBars, Ridgeline, NeonGauge.
5. Apply them screen by screen exactly as 06 §5 describes:
   Home (input + idle radar + recent reports + activity bars, faint neuron-filament background),
   Report Overview (5 stat cards incl. red "Hallucinations blocked", pipeline + radar row, hallucination-filter stream, IOC table + tactic tiles),
   Pipeline canvas (dotted white boxes, rainbow pipes, neon glow on running stage),
   Evidence tab, Attack flow (neon observed, dashed violet predicted, hatched unknown, tactic-coloured gradient edges, simulator states),
   Detections (neon gauge, status pills, dark Sigma YAML theme), Memory graph (#0B0E14 canvas, Obsidian-style control panel, node colours by type, dark-red edges),
   Scoreboard (big-number comparison cards + ridgeline).
6. Motion: one orchestrated reveal per screen (radar grows, stream fills as stages finish, flow builds node by node);
   continuous animation only while a stage is running; honour prefers-reduced-motion.
7. Quality: IOCs always rendered from `display` (defanged), never as links; colour never the only signal (dashed/hatched/icons);
   visible focus ring 2px #3B6BFF; charts get aria-labels; works at 1280×720 and on mobile.

DONE WHEN
- npm run build passes with zero TypeScript errors.
- npm run dev on mock data: every screen matches 06 (check each against §5), nothing that worked before is broken.
- Give me a short list of what changed per screen and anything you couldn't match.