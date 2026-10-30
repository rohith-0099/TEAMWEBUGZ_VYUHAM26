"""Attack flow builder. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 6."""
from app.mocks import sample_analysis
from app.models import AttackFlow, TechniqueMatch


def build_flow(techniques: list[TechniqueMatch], predictions: list[TechniqueMatch]) -> AttackFlow:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return sample_analysis().flow
