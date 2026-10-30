"""Behaviour agent. STUB — owner: RAG. See team/04_RAG_AI.md Step 5."""
import asyncio
from collections.abc import Awaitable, Callable

from app.mocks import sample_analysis
from app.models import Behaviour


async def extract_behaviours(text: str,
                             on_behaviour: Callable[[Behaviour], Awaitable[None]] | None = None,
                             ) -> list[Behaviour]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    behaviours = sample_analysis().behaviours
    for b in behaviours:
        if on_behaviour:
            await on_behaviour(b)
        await asyncio.sleep(0.05)
    return behaviours
