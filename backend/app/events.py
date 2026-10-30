"""In-memory SSE event bus (contracts §9). Owner: Lead.

Works only because Uvicorn runs a single worker.
"""
import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import db

HISTORY_TTL_S = 2 * 60 * 60


@dataclass
class _Channel:
    started_at: float = field(default_factory=time.monotonic)
    history: list[dict] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)


_channels: dict[str, _Channel] = {}


def _is_terminal(event: dict) -> bool:
    return event["stage"] == "pipeline" and event["status"] in ("done", "error")


def _evict_old() -> None:
    cutoff = time.monotonic() - HISTORY_TTL_S
    for key in [k for k, ch in _channels.items() if ch.started_at < cutoff and not ch.subscribers]:
        del _channels[key]


def _make_event(analysis_id: str, stage: str, status: str, data: dict | None, elapsed_ms: int) -> dict:
    return {
        "analysis_id": analysis_id,
        "stage": stage,
        "status": status,
        "data": data or {},
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_ms": elapsed_ms,
    }


async def publish(analysis_id: str, stage: str, status: str, data: dict | None = None) -> None:
    """data must be JSON-serialisable: use model_dump(mode="json") for models."""
    if analysis_id not in _channels:
        _evict_old()
        _channels[analysis_id] = _Channel()
    channel = _channels[analysis_id]
    elapsed_ms = int((time.monotonic() - channel.started_at) * 1000)
    event = _make_event(analysis_id, stage, status, data, elapsed_ms)
    channel.history.append(event)
    for queue in channel.subscribers:
        queue.put_nowait(event)


async def event_stream(analysis_id: str) -> AsyncIterator[dict]:
    """Replays past events, then streams live ones until pipeline done/error."""
    channel = _channels.get(analysis_id)
    if channel is None or not channel.history:
        # No in-memory history: the run finished long ago, or the server restarted mid-run.
        analysis = await asyncio.to_thread(db.get_analysis, analysis_id)
        if analysis is not None and analysis.status == "done":
            yield _make_event(analysis_id, "pipeline", "done", {"report_id": analysis_id}, 0)
        else:
            message = (analysis.error if analysis else None) or "Analysis was interrupted"
            yield _make_event(analysis_id, "pipeline", "error", {"message": message}, 0)
        return

    # No await between the snapshot and subscribing, so no event can slip between them.
    replay = list(channel.history)
    queue: asyncio.Queue = asyncio.Queue()
    channel.subscribers.add(queue)
    try:
        for event in replay:
            yield event
            if _is_terminal(event):
                return
        while True:
            event = await queue.get()
            yield event
            if _is_terminal(event):
                return
    finally:
        channel.subscribers.discard(queue)
