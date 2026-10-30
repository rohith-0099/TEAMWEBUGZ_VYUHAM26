"""Tests for ingestion pipeline. Owner: Backend Core.

Tests operate offline without requiring external network access.
"""
import asyncio
from datetime import datetime

from app.pipeline.ingest import (
    _clean_markdown,
    _extract_publisher_domain,
    _parse_iso_date,
    ingest,
)


def test_extract_publisher_domain():
    assert _extract_publisher_domain("https://www.cisa.gov/news-events/advisories/aa24-001a") == "cisa.gov"
    assert _extract_publisher_domain("http://intel.cert-in.org.in:8080/reports/123") == "intel.cert-in.org.in"
    assert _extract_publisher_domain("https://microsoft.com/security/blog") == "microsoft.com"
    assert _extract_publisher_domain("invalid-url") is None


def test_parse_iso_date():
    d1 = _parse_iso_date("2026-10-30T14:00:00Z")
    assert isinstance(d1, datetime)
    assert d1.year == 2026
    assert d1.month == 10

    d2 = _parse_iso_date("2026-05-15")
    assert isinstance(d2, datetime)
    assert d2.day == 15

    assert _parse_iso_date("invalid-date") is None
    assert _parse_iso_date(None) is None


def test_clean_markdown():
    sample = (
        "# Executive Summary\n\n"
        "Threat actors deployed malware <!-- hidden comment --> to steal data.\n"
        "![diagram](https://example.com/arch.png)\n\n"
        "For details see [CISA Advisory](https://cisa.gov/advisory/1) and [MITRE](https://attack.mitre.org).\n\n"
        "| Indicator | Type |\n"
        "|---|---|\n"
        "| 1.2.3.4 | IPv4 |\n"
    )
    cleaned, refs = _clean_markdown(sample)

    assert "Executive Summary" in cleaned
    assert not cleaned.startswith("#")
    assert "hidden comment" not in cleaned
    assert "https://example.com/arch.png" not in cleaned
    assert "CISA Advisory" in cleaned
    assert "[CISA Advisory]" not in cleaned
    assert "https://cisa.gov/advisory/1" in refs
    assert "https://attack.mitre.org" in refs
    assert "| Indicator | Type |" in cleaned


def test_ingest_text_success():
    sample_text = (
        "Advisory on APT29 Campaign targeting government cloud services.\n\n"
        "The Cybersecurity and Infrastructure Security Agency (CISA) has observed advanced persistent "
        "threat actors compromising enterprise environments using stolen session tokens and spearphishing.\n\n"
        "During the intrusion, the adversary established persistence via registry Run keys and communicated "
        "with command-and-control servers at hxxp://evil[.]com/c2.php.\n\n"
        "Organizations should review authentication logs, enable multi-factor authentication, and implement "
        "strict conditional access policies to protect their hybrid identity infrastructure from unauthorized access."
    )
    result = asyncio.run(ingest(text=sample_text))

    assert "Advisory on APT29 Campaign" in result.title
    assert len(result.text) >= 200
    assert result.source_url is None
    assert result.raw_text == sample_text
    assert "APT29 Campaign" in result.text


def test_ingest_short_text_raises_error():
    too_short = "Short text alert."
    try:
        asyncio.run(ingest(text=too_short))
        assert False, "Should have raised ValueError for text < 200 chars"
    except ValueError as e:
        assert "too short" in str(e).lower()

