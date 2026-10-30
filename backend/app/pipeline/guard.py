"""Prompt-injection firewall. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 5."""
from app.mocks import sample_analysis
from app.models import InjectionFlag


async def scan(raw_text: str, text: str) -> list[InjectionFlag]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return sample_analysis().injection_flags
