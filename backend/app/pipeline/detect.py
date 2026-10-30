"""Detection readiness. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 9."""
import asyncio
from collections.abc import Awaitable, Callable

from app.mocks import sample_analysis
from app.models import Detection, ReportAnalysis


async def build_detections(analysis: ReportAnalysis,
                           on_detection: Callable[[Detection], Awaitable[None]] | None = None,
                           ) -> list[Detection]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    detections = sample_analysis().detections
    for d in detections:
        if on_detection:
            await on_detection(d)
        await asyncio.sleep(0.05)
    return detections


def readiness(analysis: ReportAnalysis, telemetry: list[str]) -> dict:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    ReadinessResponse, from a plain overlap of required vs available telemetry.
    """
    rows = []
    score = 0.0
    for d in analysis.detections:
        have = [t for t in d.required_telemetry if t in telemetry]
        missing = [t for t in d.required_telemetry if t not in telemetry]
        status = "gap" if not have else "partial" if missing else "covered"
        score += {"covered": 1.0, "partial": 0.5, "gap": 0.0}[status]
        rows.append({"technique_id": d.technique_id, "technique_name": d.technique_name,
                     "status": status, "have": have, "missing": missing})
    return {"readiness_pct": 100 * score / len(rows) if rows else 0, "per_technique": rows}
