"""v20 migrator. STUB — owner: RAG. See team/04_RAG_AI.md Step 8."""
from app.mocks import sample_analysis
from app.models import Migration, TechniqueMatch


def migrate(text: str, techniques: list[TechniqueMatch]) -> list[Migration]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return sample_analysis().migrations
