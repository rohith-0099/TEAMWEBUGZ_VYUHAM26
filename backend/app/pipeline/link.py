"""IOC <-> technique linker. STUB — owner: RAG. See team/04_RAG_AI.md Step 8."""
from app.models import IOC, TechniqueMatch


def link_iocs(iocs: list[IOC], techniques: list[TechniqueMatch],
              text: str) -> tuple[list[IOC], list[TechniqueMatch]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md.

    Sample data is already linked, so this returns it unchanged.
    """
    return iocs, techniques
