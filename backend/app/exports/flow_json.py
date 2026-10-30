"""Attack Flow export. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 6."""
from uuid import uuid4

from app.models import ReportAnalysis


def attack_flow_json(analysis: ReportAnalysis) -> dict:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    Bundle-shaped placeholder without the CTID extension; predictions excluded.
    """
    actions = [{"type": "attack-action", "id": f"attack-action--{uuid4()}", "name": n.label,
                "technique_id": n.technique_id}
               for n in analysis.flow.nodes if n.kind != "predicted"]
    return {"type": "bundle", "id": f"bundle--{uuid4()}", "objects": actions}
