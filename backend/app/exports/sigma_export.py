"""Sigma export. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 9."""
from app.models import ReportAnalysis


def sigma_yaml(analysis: ReportAnalysis) -> str:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md. All valid rules joined with ---."""
    return "---\n".join(r.yaml for d in analysis.detections for r in d.sigma if r.valid)
