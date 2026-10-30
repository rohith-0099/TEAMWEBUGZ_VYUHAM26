// Contracts §6 and §8 in TypeScript, 1:1 with backend/app/models.py (snake_case).

export type IOCType = "ipv4" | "ipv6" | "domain" | "url" | "email" | "md5" | "sha1" | "sha256"
  | "sha512" | "cve" | "filepath" | "registry" | "btc" | "other";
export type IOCRole = "c2" | "payload" | "phishing" | "exfil" | "victim" | "scanner"
  | "infrastructure" | "unknown";
export type Telemetry = "sysmon" | "windows_security" | "powershell_scriptblock" | "edr" | "dns"
  | "proxy" | "firewall" | "netflow" | "cloud_audit" | "email_gateway" | "linux_auditd";

export type Evidence = { quote: string; start: number; end: number };

export type Confidence = {
  extraction: number;
  mapping: number | null;
  role: number | null;
  relationship: number | null;
  freshness: number | null;
};

export type IOC = {
  id: string;
  type: IOCType;
  value: string; // refanged, internal use only: never render it, use `display`
  display: string;
  role: IOCRole;
  evidence: Evidence[];
  confidence: Confidence;
  linked_techniques: string[];
  filtered_reason: string | null;
};

export type Behaviour = { id: string; summary: string; evidence: Evidence };

export type Candidate = {
  technique_id: string;
  name: string;
  score: number;
  source: "vector" | "explicit_id";
};

export type RejectReason = "id_not_in_v20" | "quote_not_in_source" | "verifier_mismatch"
  | "low_confidence" | "deprecated";

export type TechniqueMatch = {
  technique_id: string;
  name: string;
  tactics: string[];
  behaviour_id: string | null;
  evidence: Evidence | null;
  status: "accepted" | "rejected";
  reject_reason: RejectReason | null;
  rationale: string;
  confidence: Confidence;
  linked_iocs: string[];
  origin: "observed" | "predicted";
  prediction_score: number | null;
  url: string | null;
};

export type InjectionFlag = {
  detector: "rule" | "llm";
  pattern: string;
  severity: "high" | "medium" | "low";
  evidence: Evidence | null;
  technique_id: "T1698" | "T1699";
};

export type FlowNode = {
  id: string;
  kind: "observed" | "predicted" | "unknown";
  technique_id: string | null;
  tactic: string;
  label: string;
  order: number;
};

export type FlowEdge = {
  source: string;
  target: string;
  relation: "followed_by" | "enables" | "uses_infrastructure";
};

export type AttackFlow = { nodes: FlowNode[]; edges: FlowEdge[] };

export type LogSource = {
  name: string;
  data_component: string | null;
  telemetry: Telemetry | null;
};

export type Analytic = { id: string; name: string; platforms: string[]; log_sources: LogSource[] };

export type DetectionStrategy = { id: string; name: string; analytics: Analytic[] };

export type SigmaRule = {
  title: string;
  technique_id: string;
  kind: "ioc" | "behaviour";
  yaml: string;
  valid: boolean;
  errors: string[];
  conversions: Record<string, string>;
};

export type Detection = {
  technique_id: string;
  technique_name: string;
  strategies: DetectionStrategy[];
  required_telemetry: Telemetry[];
  sigma: SigmaRule[];
};

export type ReportRef = {
  report_id: string;
  title: string;
  published_at: string | null;
  quote: string | null;
};

export type MemoryAlert = {
  type: "seen_before" | "contradiction";
  entity_type: string;
  entity_key: string;
  entity_display: string;
  message: string;
  reports: ReportRef[];
  explained_by_time: boolean | null;
};

export type Migration = {
  old_id: string;
  new_ids: string[];
  reason: string;
  evidence: Evidence | null;
};

export type ReportAnalysis = {
  report_id: string;
  status: "running" | "done" | "error";
  error: string | null;
  title: string;
  source_url: string | null;
  published_at: string | null;
  created_at: string | null;
  text: string;
  injection_flags: InjectionFlag[];
  iocs: IOC[];
  behaviours: Behaviour[];
  techniques: TechniqueMatch[];
  predictions: TechniqueMatch[];
  flow: AttackFlow;
  detections: Detection[];
  memory_alerts: MemoryAlert[];
  migrations: Migration[];
  timings_ms: Record<string, number>;
};

export type AnalysisListItem = {
  report_id: string;
  title: string;
  source_url: string | null;
  published_at: string | null;
  created_at: string;
  status: "running" | "done" | "error";
  counts: { iocs: number; techniques: number; alerts: number };
};

export type SimulateResponse = {
  total_paths: number;
  broken_paths: number;
  broken_pct: number; // 0..100
  surviving_paths: string[][]; // lists of node ids
  affected_node_ids: string[]; // nodes no longer reachable from any entry
  countermeasures: {
    technique_id: string;
    id: string;
    name: string;
    source: "d3fend" | "attack_mitigation";
    derived: boolean;
    url?: string;
  }[];
  note?: string;
};

export type ReadinessResponse = {
  readiness_pct: number; // 0..100
  per_technique: {
    technique_id: string;
    technique_name: string;
    status: "covered" | "partial" | "gap";
    have: string[];
    missing: string[];
  }[];
};

export type GraphResponse = {
  nodes: {
    id: string;
    type: "ioc" | "technique" | "actor" | "malware" | "report" | "sector";
    label: string;
    first_seen: string | null;
    last_seen: string | null;
    report_count: number;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    relation: string;
    valid_from: string | null;
    valid_to: string | null;
    report_id: string | null;
  }[];
  alerts: MemoryAlert[];
};

export type Tactic = { tactic_id: string; shortname: string; name: string; ord: number };

export type TechniqueDetail = {
  technique_id: string;
  name: string;
  description: string;
  tactics: string[];
  is_subtechnique: boolean;
  parent_id: string | null;
  platforms: string[];
  url: string;
};

type EvalCounts = { tp: string[]; fp: string[]; fn: string[] };

export type EvalResponse = {
  ran_at: string;
  reports: number;
  systems: {
    system: "baseline" | "trinetra";
    precision: number;
    recall: number;
    f1: number;
    parent_f1: number;
    avg_latency_ms: number;
  }[];
  per_report: {
    report_id: string;
    title: string;
    url: string;
    baseline: EvalCounts;
    trinetra: EvalCounts;
  }[];
};

export type GeoPoint = {
  ioc_id: string;
  display: string;
  lat: number;
  lon: number;
  country: string;
  city?: string;
  role: string;
};

export type StageName = "ingest" | "guard" | "ioc" | "ioc_role" | "behaviours" | "retrieve"
  | "verify" | "link" | "migrate" | "tie" | "flow" | "detect" | "memory" | "export" | "pipeline";
export type StageStatus = "idle" | "started" | "progress" | "done" | "error" | "skipped";
export type PipelineEvent = {
  analysis_id: string;
  stage: StageName;
  status: Exclude<StageStatus, "idle">;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any; // payload depends on the stage, see contracts §9
  ts: string;
  elapsed_ms: number;
};
