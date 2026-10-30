"""Autonomous intelligence watch engine (NICE). Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 8.
Periodically scrapes advisory listing pages and triggers analyses for newly published reports.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SEEN_URLS_FILE = Path(__file__).parent.parent.parent.parent / "data" / "seen_urls.json"

WATCH_SOURCES = [
    "https://www.cisa.gov/news-events/cybersecurity-advisories",
]


def _load_seen_urls() -> set[str]:
    if SEEN_URLS_FILE.is_file():
        try:
            data = json.loads(SEEN_URLS_FILE.read_text(encoding="utf-8"))
            return set(data)
        except Exception:
            pass
    return set()


def _save_seen_urls(seen: set[str]) -> None:
    SEEN_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_URLS_FILE.write_text(json.dumps(sorted(list(seen)), indent=2), encoding="utf-8")


def run_once(api_base: str = "http://localhost:8000/api") -> list[str]:
    """Check watch sources once, trigger analysis for up to 3 new reports, return triggered URLs."""
    seen = _load_seen_urls()
    new_urls: list[str] = []

    # Scrape listing page
    for source in WATCH_SOURCES:
        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                resp = client.get(source)
                if resp.status_code != 200:
                    continue
                html = resp.text

            # Find advisory URLs (e.g. /news-events/cybersecurity-advisories/aa24-...)
            matches = re.findall(r'href="(/news-events/cybersecurity-advisories/[^"]+)"', html)
            for m in matches:
                full_url = f"https://www.cisa.gov{m}"
                if full_url not in seen and full_url not in new_urls:
                    new_urls.append(full_url)
                    if len(new_urls) >= 3:
                        break
        except Exception as e:
            logger.warning("Error fetching watch source %s: %s", source, e)

        if len(new_urls) >= 3:
            break

    # Trigger analysis for discovered URLs
    triggered: list[str] = []
    for target_url in new_urls:
        try:
            with httpx.Client(timeout=10.0) as client:
                post_resp = client.post(f"{api_base}/analyses", json={"url": target_url})
                if post_resp.status_code in (200, 202):
                    triggered.append(target_url)
                    seen.add(target_url)
        except Exception as e:
            logger.warning("Failed to trigger analysis for %s: %s", target_url, e)

    if triggered:
        _save_seen_urls(seen)

    return triggered
