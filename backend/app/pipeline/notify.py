"""n8n alerts. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 7."""
from app.config import settings


async def notify(kind: str, payload: dict) -> None:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    Fire-and-forget POST to n8n. No-op if N8N_WEBHOOK_URL is empty. Must never raise.
    """
    if not settings.n8n_webhook_url:
        return
