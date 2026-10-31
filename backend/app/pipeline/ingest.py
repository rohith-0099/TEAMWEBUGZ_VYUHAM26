"""Ingestion engine: URL, PDF, and text ingestion. Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 3.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import io
import re
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.config import settings
from app.utils.text import normalize_text

try:
    import httpx
except ImportError:
    httpx = None

# Optional imports with fallbacks
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import trafilatura
except ImportError:
    trafilatura = None


class IngestResult(BaseModel):
    title: str
    source_url: str | None
    published_at: datetime | None
    raw_text: str                  # before normalize_text (Lead's firewall scans this)
    text: str                      # normalize_text(cleaned)
    publisher_domain: str | None   # e.g. "cisa.gov", used by the IOC allowlist
    references: list[str]          # link targets removed from markdown
    images: list[dict] = []        # {index, source, chars, used} per image considered for OCR
    ocr_status: str | None = None  # "ok" | "no_images" | "unavailable: <reason>"


def _extract_publisher_domain(url: str) -> str | None:
    """Extract registrable/base domain from URL, stripping www and ports."""
    try:
        netloc = urlsplit(url).netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or None
    except Exception:
        return None


def _clean_markdown(md: str) -> tuple[str, list[str]]:
    """Clean markdown:
    - remove HTML comments
    - remove image markdown ![alt](src)
    - replace [text](href) with text and collect hrefs into references
    - strip leading # from headings
    - keep markdown tables intact
    """
    references: list[str] = []

    # 1. Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)

    # 2. Remove images ![alt](src)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # 3. Replace [text](href) with text and collect hrefs
    def _replace_link(match: re.Match) -> str:
        label = match.group(1)
        href = match.group(2)
        if href and href not in references:
            references.append(href)
        return label

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, text)

    # 4. Strip leading # from headings
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("#"):
            # Remove leading '#' characters and the subsequent space
            cleaned_lines.append(re.sub(r"^#+\s*", "", line))
        else:
            cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    return text, references


def _extract_title_from_text(text: str, fallback: str = "Threat Intelligence Report") -> str:
    """Find first non-empty line up to 120 chars."""
    for line in text.splitlines():
        clean = line.strip()
        if clean:
            return clean[:120]
    return fallback


def _parse_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed to process PDF uploads")

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
        raw = "\n\n".join(pages_text)

    # Fix hyphenated line breaks: e.g. "mal-\nware" -> "malware"
    fixed = re.sub(r"-\n([a-z])", r"\1", raw)
    return fixed


def _scrape_with_firecrawl(url: str, api_key: str) -> tuple[str, dict]:
    """Synchronous scrape via firecrawl SDK (v2 or v1)."""
    # Try v2 SDK: from firecrawl import Firecrawl
    try:
        from firecrawl import Firecrawl
        fc = Firecrawl(api_key=api_key)
        doc = fc.scrape(url, formats=["markdown"])
        md = getattr(doc, "markdown", None) or (doc.get("markdown") if isinstance(doc, dict) else "")
        meta = getattr(doc, "metadata", None) or (doc.get("metadata") if isinstance(doc, dict) else {})
        if hasattr(meta, "model_dump"):  # SDK v2 returns a pydantic model, the rest of ingest expects a dict
            meta = {**meta.model_dump(exclude_none=True), **meta.model_dump(by_alias=True, exclude_none=True)}
        return md or "", meta or {}
    except ImportError:
        pass

    # Try v1 SDK: from firecrawl import FirecrawlApp
    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=api_key)
        r = app.scrape_url(url, formats=["markdown"])
        md = r.get("markdown", "") if isinstance(r, dict) else ""
        meta = r.get("metadata", {}) if isinstance(r, dict) else {}
        return md, meta
    except Exception as e:
        raise RuntimeError(f"Firecrawl scrape failed: {e}") from e


async def _fallback_scrape_url(url: str) -> tuple[str, dict]:
    """Fallback URL scrape using httpx and trafilatura / pdfplumber."""
    if httpx is None:
        raise RuntimeError("httpx is required for URL scraping")
    headers = {"User-Agent": "TRINETRA/1.0 (Threat Intelligence Analysis)"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "").lower()

    if "application/pdf" in content_type or url.lower().endswith(".pdf"):
        text = _parse_pdf_bytes(resp.content)
        return text, {"title": url.split("/")[-1]}

    html = resp.text
    metadata: dict = {}

    # Extract title from HTML tags
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.I)
    if not title_match:
        title_match = re.search(r'<title>(.*?)</title>', html, re.I)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # Extract published date from HTML tags
    date_match = re.search(r'<meta\s+(?:property|name)=["\'](?:article:published_time|publishedTime|date)["\']\s+content=["\'](.*?)["\']', html, re.I)
    if date_match:
        metadata["date"] = date_match.group(1).strip()

    # Extract main text via trafilatura if available
    extracted_text = ""
    if trafilatura is not None:
        extracted_text = trafilatura.extract(html, include_tables=True, include_links=False) or ""

    if not extracted_text:
        # Fallback simple tag stripper if trafilatura extraction failed or not available
        clean_html = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.I)
        clean_html = re.sub(r"<style.*?</style>", "", clean_html, flags=re.DOTALL | re.I)
        extracted_text = re.sub(r"<[^>]+>", " ", clean_html)

    return extracted_text, metadata


def _parse_iso_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        # Clean potential trailing Z or offsets
        clean = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


async def _read_images(url: str | None, pdf_bytes: bytes | None, markdown: str, cleaned: str,
                       on_image) -> tuple[str, list[dict], str | None]:
    """OCR blocks to append, the image list, and the OCR status. Never raises."""
    from app.pipeline import ocr
    from app.pipeline.ioc import extract_iocs

    try:
        if pdf_bytes:
            found = await asyncio.to_thread(ocr.ocr_pdf, pdf_bytes)
            sources = [f.source if f else "PDF image" for f in found]
        elif url:
            # Never fetch anything the report lists as an indicator.
            iocs = extract_iocs(normalize_text(cleaned))
            values = {i.value for i in iocs} | {urlsplit(i.value).hostname or "" for i in iocs if i.type == "url"}
            urls = ocr.image_urls(markdown, url, values)
            if not urls:
                return "", [], "no_images"
            found = await ocr.ocr_urls(urls)
            sources = urls
        else:
            return "", [], None
    except ocr.OCRUnavailable as exc:
        return "", [], f"unavailable: {exc}"
    except Exception as exc:  # OCR must never break ingestion
        return "", [], f"unavailable: {exc}"

    images, used = [], []
    for index, (source, item) in enumerate(zip(sources, found), start=1):
        info = {"index": index, "source": item.source if item else source,
                "chars": len(item.text) if item else 0, "used": item is not None}
        images.append(info)
        if item:
            item.index = index
            used.append(item)
        if on_image:
            await on_image(info)
    return ocr.blocks(used), images, ("ok" if images else "no_images")


async def ingest(url: str | None = None, text: str | None = None,
                 pdf_bytes: bytes | None = None, filename: str | None = None,
                 title: str | None = None, on_image=None) -> IngestResult:
    """Ingest threat report from URL, raw text, or PDF upload.

    Returns IngestResult with raw_text (for firewall) and normalized text (for evidence offsets).
    """
    raw_content = ""
    published_at: datetime | None = None
    source_url: str | None = url
    publisher_domain: str | None = None
    references: list[str] = []

    # 1. Text given
    if text:
        raw_content = text
        if not title:
            title = _extract_title_from_text(raw_content)

    # 2. PDF bytes given
    elif pdf_bytes:
        raw_content = _parse_pdf_bytes(pdf_bytes)
        if not title:
            if filename:
                title = filename[:-4] if filename.lower().endswith(".pdf") else filename
            else:
                title = _extract_title_from_text(raw_content)

    # 3. URL given
    elif url:
        publisher_domain = _extract_publisher_domain(url)
        metadata: dict = {}

        if settings.firecrawl_api_key:
            try:
                # Run Firecrawl in thread with timeout
                raw_content, metadata = await asyncio.wait_for(
                    asyncio.to_thread(_scrape_with_firecrawl, url, settings.firecrawl_api_key),
                    timeout=45.0,
                )
            except Exception:
                # Fallback to local HTTP scrape on failure
                raw_content, metadata = await _fallback_scrape_url(url)
        else:
            raw_content, metadata = await _fallback_scrape_url(url)

        if not title:
            title = metadata.get("title") or metadata.get("og:title") or _extract_title_from_text(raw_content)

        # Parse date from metadata
        raw_date = metadata.get("publishedTime") or metadata.get("article:published_time") or metadata.get("date")
        published_at = _parse_iso_date(raw_date)

    else:
        raise ValueError("Must provide at least one of url, text, or pdf_bytes")

    # Clean markdown formatting, strip images, capture references
    cleaned_text, refs = _clean_markdown(raw_content)
    references.extend(refs)

    # Text read from images is appended BEFORE normalisation, in labelled blocks, so every
    # evidence offset stays valid and quotes from images are visibly marked.
    image_blocks, images, ocr_status = await _read_images(url if not text else None, pdf_bytes,
                                                          raw_content, cleaned_text, on_image)

    # Normalize canonical text (ALL evidence offsets point into this string)
    normalized = normalize_text(cleaned_text + image_blocks)

    # Validate minimal length
    if len(normalized) < 200:
        raise ValueError(
            f"Extracted text is too short ({len(normalized)} chars, minimum 200 required). "
            "Could not extract sufficient report content."
        )

    return IngestResult(
        title=title or "Threat Intelligence Report",
        source_url=source_url,
        published_at=published_at,
        raw_text=raw_content,
        text=normalized,
        publisher_domain=publisher_domain,
        references=references,
        images=images,
        ocr_status=ocr_status,
    )
