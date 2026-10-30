"""Technique predictions. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 7."""
from app.mocks import sample_analysis
from app.models import TechniqueMatch


def predict(observed_ids: list[str], top_n: int = 5) -> list[TechniqueMatch]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return sample_analysis().predictions[:top_n]
