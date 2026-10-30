"""n8n outbound notification dispatcher. Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 7.
Fire-and-forget POST to n8n webhook. NEVER raises, never blocks > 5 s.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Optional httpx import
try:
    import httpx
except ImportError:
    httpx = None


async def notify(kind: str, payload: dict) -> None:
    """Fire-and-forget notification to n8n webhook for Telegram alerts / MISP push.

    kind: "analysis_done" | "memory_alert" | "injection_detected"
    Never raises an exception, never blocks the pipeline longer than 5 seconds.
    """
    webhook_url = settings.n8n_webhook_url
    if not webhook_url:
        return

    if httpx is None:
        logger.warning("httpx not available; cannot send n8n notification")
        return

    body = {
        "kind": kind,
        "app": "TRINETRA",
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook_url, json=body)
    except Exception as e:
        logger.warning("Failed to dispatch n8n alert for %s: %s", kind, e)
