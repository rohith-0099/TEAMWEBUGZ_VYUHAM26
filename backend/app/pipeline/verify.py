"""Verifier. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 4."""
import asyncio
from collections.abc import Awaitable, Callable

from app.mocks import sample_analysis
from app.models import IOC, Behaviour, Candidate, Evidence, TechniqueMatch


async def verify_all(text: str, behaviours: list[Behaviour], candidates: dict[str, list[Candidate]],
                     iocs: list[IOC], explicit: list[tuple[str, Evidence]],
                     on_result: Callable[[TechniqueMatch], Awaitable[None]] | None = None,
                     ) -> list[TechniqueMatch]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    Calls on_result for every accepted and rejected match so the UI streams both.
    """
    techniques = sample_analysis().techniques
    for t in techniques:
        if on_result:
            await on_result(t)
        await asyncio.sleep(0.05)
    return techniques
