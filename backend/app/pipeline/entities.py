"""Known actor/malware matching. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 10."""
from app.mocks import _ev


def find_known_entities(text: str) -> list[dict]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return [{"type": "malware", "key": "ObsidianLock", "display": "ObsidianLock",
             "evidence": _ev("ObsidianLock ransomware intrusion").model_dump()}]
