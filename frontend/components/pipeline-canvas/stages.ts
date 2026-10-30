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

export const STAGES_CONFIG: Record<StageName, StageMeta> = {
  ingest: {
    id: "ingest",
    name: "Ingest",
    kind: "deterministic",
    description: "Fetches and normalizes threat report content from URL, PDF, or text into canonical representation.",
    x: 30,
    y: 90,
  },
  guard: {
    id: "guard",
    name: "Guard Firewall",
    kind: "hybrid",
    description: "Evaluates raw input for adversarial prompt-injection and jailbreak attempts (mapped to T1698/T1699).",
    x: 180,
    y: 90,
  },
  ioc: {
    id: "ioc",
    name: "IOC Engine",
    kind: "deterministic",
    description: "Deterministic regex & iocsearcher extraction of indicators, defanging display, and allowlist filtering.",
    x: 350,
    y: 30,
  },
  ioc_role: {
    id: "ioc_role",
    name: "IOC Role Agent",
    kind: "LLM",
    description: "Labels indicators with contextual attack roles (C2, payload, exfiltration) anchored by exact report quotes.",
    x: 520,
    y: 30,
  },
  behaviours: {
    id: "behaviours",
    name: "Behaviour Agent",
    kind: "LLM",
    description: "Extracts atomic attacker behaviors from report text, each bound to a verbatim evidence quote.",
    x: 350,
    y: 155,
  },
  retrieve: {
    id: "retrieve",
    name: "Retriever",
    kind: "vector",
    description: "Computes fast embeddings and performs cosine similarity search over ATT&CK v20 enterprise techniques.",
    x: 520,
    y: 155,
  },
  verify: {
    id: "verify",
    name: "Verifier",
    kind: "LLM + rules",
    description: "Ground-truth verifier enforcing ATT&CK v20 ID validity, verbatim quote match in text, and threshold.",
    x: 690,
    y: 155,
  },
  link: {
    id: "link",
    name: "Link Engine",
    kind: "deterministic",
    description: "Binds verified IOCs to their corresponding techniques via overlapping textual evidence spans.",
    x: 870,
    y: 90,
  },
  migrate: {
    id: "migrate",
    name: "v20 Migrator",
    kind: "deterministic",
    description: "Translates revoked or deprecated legacy ATT&CK techniques (e.g. Defense Evasion split) into v20.",
    x: 1040,
    y: 90,
  },
  tie: {
    id: "tie",
    name: "TIE Predictor",
    kind: "ML model",
    description: "MITRE CTID Technique Inference Engine predicts unobserved precursor and successor attack techniques.",
    x: 1220,
    y: 10,
  },
  flow: {
    id: "flow",
    name: "Attack Flow",
    kind: "graph",
    description: "Builds a chronological causal DAG of the attack, distinguishing observed, ghost, and unknown gaps.",
    x: 1220,
    y: 75,
  },
  detect: {
    id: "detect",
    name: "Detections & Sigma",
    kind: "hybrid",
    description: "Maps v20 Detection Strategies/Analytics to defender telemetry and compiles validated Sigma rules.",
    x: 1220,
    y: 140,
  },
  memory: {
    id: "memory",
    name: "Temporal Memory",
    kind: "graph",
    description: "Cross-report temporal graph identifying recurring infrastructure and attributing contradictions.",
    x: 1220,
    y: 205,
  },
  export: {
    id: "export",
    name: "Exports",
    kind: "deterministic",
    description: "Builds schema-compliant STIX 2.1 bundles, ATT&CK Navigator v20 layers, and Sigma YAML archives.",
    x: 1400,
    y: 105,
  },
  pipeline: {
    id: "pipeline",
    name: "Pipeline Complete",
    kind: "deterministic",
    description: "Final orchestration termination and verification sync.",
    x: 1550,
    y: 105,
  },
};

export const PIPELINE_EDGES = [
  { id: "e-ingest-guard", source: "ingest", target: "guard" },
  { id: "e-guard-ioc", source: "guard", target: "ioc" },
  { id: "e-guard-behaviours", source: "guard", target: "behaviours" },
  { id: "e-ioc-role", source: "ioc", target: "ioc_role" },
  { id: "e-behaviours-retrieve", source: "behaviours", target: "retrieve" },
  { id: "e-retrieve-verify", source: "retrieve", target: "verify" },
  { id: "e-role-link", source: "ioc_role", target: "link" },
  { id: "e-verify-link", source: "verify", target: "link" },
  { id: "e-link-migrate", source: "link", target: "migrate" },
  { id: "e-migrate-tie", source: "migrate", target: "tie" },
  { id: "e-migrate-flow", source: "migrate", target: "flow" },
  { id: "e-migrate-detect", source: "migrate", target: "detect" },
  { id: "e-migrate-memory", source: "migrate", target: "memory" },
  { id: "e-tie-export", source: "tie", target: "export" },
  { id: "e-flow-export", source: "flow", target: "export" },
  { id: "e-detect-export", source: "detect", target: "export" },
  { id: "e-memory-export", source: "memory", target: "export" },
];
