"""Ingestion. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 3."""
from datetime import datetime

from pydantic import BaseModel

from app.mocks import SAMPLE_TEXT, SAMPLE_TITLE, SAMPLE_URL


class IngestResult(BaseModel):
    title: str
    source_url: str | None
    published_at: datetime | None
    raw_text: str                  # before normalize_text (Lead's firewall scans this)
    text: str                      # normalize_text(cleaned)
    publisher_domain: str | None   # e.g. "cisa.gov", used by the IOC allowlist
    references: list[str]          # link targets removed from markdown


async def ingest(url: str | None = None, text: str | None = None,
                 pdf_bytes: bytes | None = None, filename: str | None = None,
                 title: str | None = None) -> IngestResult:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md.

    Ignores the input and returns the sample report, because all stub downstream
    evidence offsets point into SAMPLE_TEXT.
    """
    return IngestResult(title=title or SAMPLE_TITLE, source_url=url or SAMPLE_URL, published_at=None,
                        raw_text=SAMPLE_TEXT, text=SAMPLE_TEXT, publisher_domain="intel.example",
                        references=[])
