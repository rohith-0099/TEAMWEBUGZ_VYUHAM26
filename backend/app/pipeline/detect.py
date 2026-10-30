"""Detection readiness. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 9."""
import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

import psycopg

from app import db
from app.attack import store
from app.models import Analytic, Detection, DetectionStrategy, LogSource, ReportAnalysis
from app.pipeline.sigma import build_rules

log = logging.getLogger(__name__)

# Log source name + data component -> our telemetry buckets. Tune detections here.
TELEMETRY_RULES: list[tuple[str, set[str]]] = [
    (r"sysmon", {"sysmon"}),
    (r"powershell|script block", {"powershell_scriptblock"}),
    (r"winEventLog:Security|windows security|\b(4624|4625|4688|4697|4698|4720)\b", {"windows_security"}),
    (r"process creation", {"sysmon", "edr", "windows_security"}),
    (r"process access|module load|os api execution", {"sysmon", "edr"}),
    (r"command execution", {"powershell_scriptblock", "edr", "sysmon"}),
    (r"file (creation|modification|deletion|access)", {"sysmon", "edr"}),
    (r"windows registry key (creation|modification)", {"sysmon", "edr"}),
    (r"scheduled job creation|service creation", {"windows_security", "sysmon", "edr"}),
    (r"logon session creation|user account authentication", {"windows_security", "cloud_audit"}),
    (r"network connection creation", {"sysmon", "edr", "firewall"}),
    (r"network traffic flow", {"netflow", "firewall"}),
    (r"network traffic content", {"proxy", "netflow"}),
    (r"\bdns\b|domain name|\bquery\b", {"dns"}),
    (r"\bproxy\b|\bhttp\b|\bweb\b", {"proxy"}),
    (r"\be?-?mail\b", {"email_gateway"}),
    (r"\bcloud\b|\baudit\b|azure|\baws\b|\bgcp\b|office 365", {"cloud_audit"}),
    (r"auditd|\blinux\b", {"linux_auditd"}),
]
_COMPILED = [(re.compile(pattern, re.IGNORECASE), buckets) for pattern, buckets in TELEMETRY_RULES]


def telemetry_for(log_source: LogSource, technique_id: str = "") -> set[str]:
    """Buckets that can see this log source; empty means an unknown source."""
    haystack = f"{log_source.name} {log_source.data_component or ''}"
    buckets = {b for pattern, group in _COMPILED if pattern.search(haystack) for b in group}
    if technique_id.startswith("T1566") and "application log content" in haystack.lower():
        buckets.add("email_gateway")
    return buckets


def _legacy_strategies(technique_id: str) -> list[DetectionStrategy]:
    """Fallback for techniques without strategies: their legacy data source list."""
    try:
        with db.pool.connection() as conn:
            row = conn.execute(
                "SELECT data FROM attack_objects WHERE attack_id=%s AND type='attack-pattern'",
                (technique_id,),
            ).fetchone()
    except psycopg.Error as exc:
        log.warning("legacy data sources unavailable for %s: %s", technique_id, exc)
        return []
    sources = (row["data"].get("x_mitre_data_sources") or []) if row else []
    if not sources:
        return []
    # Each data source can detect on its own, so each is its own analytic.
    analytics = [Analytic(id=f"legacy-{i}", name=source,
                          log_sources=[LogSource(name=source, data_component=source.split(":")[-1].strip())])
                 for i, source in enumerate(sources)]
    return [DetectionStrategy(id=f"legacy-{technique_id}", name="ATT&CK data sources", analytics=analytics)]


def _with_telemetry(strategies: list[DetectionStrategy], technique_id: str) -> list[str]:
    """Fills each log source's bucket and returns the union of all buckets."""
    required: set[str] = set()
    for strategy in strategies:
        for analytic in strategy.analytics:
            for source in analytic.log_sources:
                buckets = telemetry_for(source, technique_id)
                required |= buckets
                source.telemetry = min(buckets) if buckets else None
    return sorted(required)


async def _detection(analysis: ReportAnalysis, technique_id: str, name: str) -> Detection:
    strategies = store.get_detection_info(technique_id)
    if not strategies:
        strategies = await asyncio.to_thread(_legacy_strategies, technique_id)
    detection = Detection(technique_id=technique_id, technique_name=name, strategies=strategies,
                          required_telemetry=_with_telemetry(strategies, technique_id))
    detection.sigma = await build_rules(analysis, technique_id, detection)
    return detection


async def build_detections(analysis: ReportAnalysis,
                           on_detection: Callable[[Detection], Awaitable[None]] | None = None,
                           ) -> list[Detection]:
    techniques = {t.technique_id: t.name for t in analysis.techniques if t.status == "accepted"}
    tasks = [asyncio.create_task(_detection(analysis, tid, name)) for tid, name in techniques.items()]
    for finished in asyncio.as_completed(tasks):
        detection = await finished
        if on_detection:
            await on_detection(detection)
    return [t.result() for t in tasks]  # stable order, whichever finished first


def readiness(analysis: ReportAnalysis, telemetry: list[str]) -> dict:
    """ReadinessResponse: an analytic needs all of its log sources to be visible."""
    available = set(telemetry)
    rows = []
    for d in analysis.detections:
        covered = partial = False
        for strategy in d.strategies:
            for analytic in strategy.analytics:
                seen = [bool(telemetry_for(s, d.technique_id) & available) for s in analytic.log_sources]
                covered = covered or (bool(seen) and all(seen))
                partial = partial or any(seen)
        status = "covered" if covered else "partial" if partial else "gap"
        rows.append({"technique_id": d.technique_id, "technique_name": d.technique_name, "status": status,
                     "have": sorted(set(d.required_telemetry) & available),
                     "missing": sorted(set(d.required_telemetry) - available)})
    score = sum({"covered": 1.0, "partial": 0.5, "gap": 0.0}[r["status"]] for r in rows)
    return {"readiness_pct": 100 * score / len(rows) if rows else 0, "per_technique": rows}
