import type { StageName } from "@/lib/types";

export type StageKind =
  | "deterministic"
  | "LLM"
  | "vector"
  | "hybrid"
  | "graph"
  | "ML model"
  | "LLM + rules";

export type StageMeta = {
  id: StageName;
  name: string;
  kind: StageKind;
  description: string;
  x: number;
  y: number;
};

// Column pitch: node width (152) plus room for the pipes.
const COLUMN = 180;

export const STAGES_CONFIG: Record<StageName, StageMeta> = {
  ingest: {
    id: "ingest",
    name: "Ingest",
    kind: "deterministic",
    description: "Fetches and normalizes threat report content from URL, PDF, or text into canonical representation.",
    x: 0 * COLUMN,
    y: 210,
  },
  guard: {
    id: "guard",
    name: "Guard Firewall",
    kind: "hybrid",
    description: "Evaluates raw input for adversarial prompt-injection and jailbreak attempts (mapped to T1698/T1699).",
    x: 1 * COLUMN,
    y: 210,
  },
  ioc: {
    id: "ioc",
    name: "IOC Engine",
    kind: "deterministic",
    description: "Deterministic regex & iocsearcher extraction of indicators, defanging display, and allowlist filtering.",
    x: 2 * COLUMN,
    y: 70,
  },
  ioc_role: {
    id: "ioc_role",
    name: "IOC Role Agent",
    kind: "LLM",
    description: "Labels indicators with contextual attack roles (C2, payload, exfiltration) anchored by exact report quotes.",
    x: 3 * COLUMN,
    y: 70,
  },
  behaviours: {
    id: "behaviours",
    name: "Behaviour Agent",
    kind: "LLM",
    description: "Extracts atomic attacker behaviors from report text, each bound to a verbatim evidence quote.",
    x: 2 * COLUMN,
    y: 350,
  },
  retrieve: {
    id: "retrieve",
    name: "Retriever",
    kind: "vector",
    description: "Computes fast embeddings and performs cosine similarity search over ATT&CK v20 enterprise techniques.",
    x: 3 * COLUMN,
    y: 350,
  },
  verify: {
    id: "verify",
    name: "Verifier",
    kind: "LLM + rules",
    description: "Ground-truth verifier enforcing ATT&CK v20 ID validity, verbatim quote match in text, and threshold.",
    x: 4 * COLUMN,
    y: 350,
  },
  link: {
    id: "link",
    name: "Link Engine",
    kind: "deterministic",
    description: "Binds verified IOCs to their corresponding techniques via overlapping textual evidence spans.",
    x: 5 * COLUMN,
    y: 210,
  },
  migrate: {
    id: "migrate",
    name: "v20 Migrator",
    kind: "deterministic",
    description: "Translates revoked or deprecated legacy ATT&CK techniques (e.g. Defense Evasion split) into v20.",
    x: 6 * COLUMN,
    y: 210,
  },
  tie: {
    id: "tie",
    name: "TIE Predictor",
    kind: "ML model",
    description: "MITRE CTID Technique Inference Engine predicts unobserved precursor and successor attack techniques.",
    x: 7 * COLUMN,
    y: 0,
  },
  flow: {
    id: "flow",
    name: "Attack Flow",
    kind: "graph",
    description: "Builds a chronological causal DAG of the attack, distinguishing observed, ghost, and unknown gaps.",
    x: 7 * COLUMN,
    y: 140,
  },
  detect: {
    id: "detect",
    name: "Detections & Sigma",
    kind: "hybrid",
    description: "Maps v20 Detection Strategies/Analytics to defender telemetry and compiles validated Sigma rules.",
    x: 7 * COLUMN,
    y: 280,
  },
  memory: {
    id: "memory",
    name: "Temporal Memory",
    kind: "graph",
    description: "Cross-report temporal graph identifying recurring infrastructure and attributing contradictions.",
    x: 7 * COLUMN,
    y: 420,
  },
  vulns: {
    id: "vulns",
    name: "CVE Lookup",
    kind: "deterministic",
    description: "Looks up each CVE in NVD (CVSS, affected versions, patch links) and the CISA KEV catalog.",
    x: 4 * COLUMN,
    y: 70,
  },
  brief: {
    id: "brief",
    name: "Briefing",
    kind: "LLM + rules",
    description: "Writes the plain-English attack story and fix list from verified facts only; code drops anything unproven.",
    x: 8 * COLUMN,
    y: 210,
  },
  export: {
    id: "export",
    name: "Exports",
    kind: "deterministic",
    description: "Builds schema-compliant STIX 2.1 bundles, ATT&CK Navigator v20 layers, and Sigma YAML archives.",
    x: 9 * COLUMN,
    y: 210,
  },
  pipeline: {
    id: "pipeline",
    name: "Pipeline Complete",
    kind: "deterministic",
    description: "Final orchestration termination and verification sync.",
    x: 10 * COLUMN,
    y: 210,
  },
};

// Pipeline order, which also picks each stage's colour.
export const STAGE_ORDER = Object.keys(STAGES_CONFIG) as StageName[];

export const PIPELINE_EDGES = [
  { id: "e-ingest-guard", source: "ingest", target: "guard" },
  { id: "e-guard-ioc", source: "guard", target: "ioc" },
  { id: "e-guard-behaviours", source: "guard", target: "behaviours" },
  { id: "e-ioc-role", source: "ioc", target: "ioc_role" },
  { id: "e-ioc-vulns", source: "ioc", target: "vulns" },
  { id: "e-behaviours-retrieve", source: "behaviours", target: "retrieve" },
  { id: "e-retrieve-verify", source: "retrieve", target: "verify" },
  { id: "e-role-link", source: "ioc_role", target: "link" },
  { id: "e-verify-link", source: "verify", target: "link" },
  { id: "e-link-migrate", source: "link", target: "migrate" },
  { id: "e-migrate-tie", source: "migrate", target: "tie" },
  { id: "e-migrate-detect", source: "migrate", target: "detect" },
  { id: "e-migrate-memory", source: "migrate", target: "memory" },
  { id: "e-tie-flow", source: "tie", target: "flow" },
  { id: "e-flow-brief", source: "flow", target: "brief" },
  { id: "e-detect-brief", source: "detect", target: "brief" },
  { id: "e-memory-brief", source: "memory", target: "brief" },
  { id: "e-vulns-brief", source: "vulns", target: "brief" },
  { id: "e-brief-export", source: "brief", target: "export" },
];
