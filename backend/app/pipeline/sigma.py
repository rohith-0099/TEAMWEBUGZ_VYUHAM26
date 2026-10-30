"""Sigma rules. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 9."""
from app.mocks import sample_analysis
from app.models import Detection, ReportAnalysis, SigmaRule


async def build_rules(analysis: ReportAnalysis, technique_id: str,
                      detection: Detection) -> list[SigmaRule]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return [rule for d in sample_analysis().detections for rule in d.sigma
            if rule.technique_id == technique_id]


def validate(yaml_text: str) -> tuple[bool, list[str], dict[str, str]]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    Returns (valid, errors, conversions). The stub accepts everything.
    """
    return True, [], {"splunk": "mock query"}
