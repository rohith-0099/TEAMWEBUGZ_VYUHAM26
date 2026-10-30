"""IOC role agent. STUB — owner: RAG. See team/04_RAG_AI.md Step 7."""
from app.models import IOC


async def label_roles(text: str, iocs: list[IOC]) -> list[IOC]:
    """STUB — owner: RAG. See team/04_RAG_AI.md.

    Sample IOCs already carry their roles, so this returns them unchanged.
    """
    return iocs
