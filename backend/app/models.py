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
    type: Literal["seen_before","contradiction"]
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
    timings_ms: dict[str, int] = {}
