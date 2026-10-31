"""Text from images in a report (OCR with Tesseract). Owner: Backend Core. No LLM calls.

Safety: only images hosted by the report's own site are fetched, never a URL or host that is an
extracted indicator, so we never contact attacker infrastructure. OCR can misread characters, so
indicators found only in image text are flagged for verification (see apply_ocr_trust).
"""
from __future__ import annotations

import asyncio
import io
import ipaddress
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import tldextract

from app.config import settings

log = logging.getLogger(__name__)

MAX_IMAGES = 8
MAX_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT_S = 10
MIN_SIDE_PX = 200          # smaller images are icons, logos and badges
MIN_MEANINGFUL_CHARS = 20
SMALL_SIDE_PX = 1000       # upscale ×2 below this
SPARSE_PAGE_CHARS = 50     # a PDF page with less text than this is OCR'd as an image
TESSERACT_CONFIG = "--psm 6"
SKIP_NAME = re.compile(r"(logo|icon|favicon|sprite|avatar|badge|emoji)", re.IGNORECASE)
MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_IMAGE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
BLOCK_HEADER = "[Image {n} text (OCR) — source: {source}]"
# normalize_text turns the em dash into "-", so accept both.
BLOCK_START = re.compile(r"\[Image (\d+) text \(OCR\) [—-] source: ([^\]\n]+)\]")
OCR_EXTRACTION_FACTOR = 0.6
HASH_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64, "sha512": 128}

_suffixes = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


@dataclass
class ImageText:
    source: str
    text: str
    index: int = 0  # position among the images considered, 1-based


class OCRUnavailable(Exception):
    pass


def _tesseract():
    """pytesseract + Pillow, or OCRUnavailable with the reason."""
    if not settings.ocr_enabled:
        raise OCRUnavailable("OCR is turned off (OCR_ENABLED=false)")
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
    except Exception as exc:  # missing package or missing tesseract binary
        raise OCRUnavailable(f"Tesseract is not available: {exc}") from exc
    return pytesseract


def _registrable(host: str) -> str:
    parts = _suffixes(host)
    return f"{parts.domain}.{parts.suffix}" if parts.domain and parts.suffix else host


def image_urls(markdown: str, report_url: str, ioc_values: set[str]) -> list[str]:
    """Image URLs from the report page itself: same registrable domain (any subdomain, e.g. a CDN or
    static host of the same site), http(s), not SVG, not icon-like, and never an indicator."""
    site = _registrable((urlsplit(report_url).hostname or "").lower())
    found: list[str] = []
    for raw in [*MD_IMAGE.findall(markdown), *HTML_IMAGE.findall(markdown)]:
        if raw.startswith("data:") or "Base64-Image-Removed" in raw:
            continue  # inline images Firecrawl removed or embedded: nothing to fetch
        url = urljoin(report_url, raw.strip())
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host:
            continue
        if parts.path.lower().endswith(".svg") or SKIP_NAME.search(parts.path):
            continue
        try:
            ipaddress.ip_address(host)
            continue  # images served from a bare IP are never the report site's own
        except ValueError:
            pass
        if _registrable(host) != site:
            continue
        if url in ioc_values or url.rstrip("/") in ioc_values or host in ioc_values:
            continue  # never contact anything the report lists as an indicator
        if url not in found:
            found.append(url)
        if len(found) == MAX_IMAGES:
            break
    return found


def _ocr_image(pytesseract, data: bytes) -> str | None:
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as img:
        if min(img.size) < MIN_SIDE_PX:
            return None
        gray = ImageOps.grayscale(img)
        if max(gray.size) < SMALL_SIDE_PX:
            gray = gray.resize((gray.width * 2, gray.height * 2), Image.LANCZOS)
        text = pytesseract.image_to_string(gray, lang="eng", config=TESSERACT_CONFIG)
    return _meaningful(text)


def _meaningful(text: str) -> str | None:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    return text if len(re.findall(r"[A-Za-z0-9]", text)) >= MIN_MEANINGFUL_CHARS else None


async def ocr_urls(urls: list[str]) -> list[ImageText | None]:
    """OCR each URL in order; None where the image was skipped or had no readable text."""
    import httpx

    pytesseract = _tesseract()
    results: list[ImageText | None] = []
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, follow_redirects=False,
                                 headers={"User-Agent": "TRINETRA/1.0 (report image OCR)"}) as client:
        for url in urls:
            try:
                async with client.stream("GET", url) as response:
                    kind = response.headers.get("content-type", "")
                    size = int(response.headers.get("content-length") or 0)
                    if response.status_code != 200 or not kind.startswith("image/") or "svg" in kind \
                            or size > MAX_BYTES:
                        results.append(None)
                        continue
                    data = b""
                    async for chunk in response.aiter_bytes():
                        data += chunk
                        if len(data) > MAX_BYTES:
                            break
                if len(data) > MAX_BYTES:
                    results.append(None)
                    continue
                text = await asyncio.to_thread(_ocr_image, pytesseract, data)
                results.append(ImageText(url, text) if text else None)
            except Exception as exc:  # one bad image never stops ingestion
                log.warning("image %s skipped: %s", url, exc)
                results.append(None)
    return results


def ocr_pdf(pdf_bytes: bytes) -> list[ImageText | None]:
    """Embedded images (same limits as URLs) and pages that have almost no text layer."""
    import pdfplumber

    pytesseract = _tesseract()
    results: list[ImageText | None] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            if len(results) >= MAX_IMAGES:
                break
            try:
                if len((page.extract_text() or "").strip()) < SPARSE_PAGE_CHARS:
                    rendered = page.to_image(resolution=200).original
                    buffer = io.BytesIO()
                    rendered.save(buffer, format="PNG")
                    text = _ocr_image(pytesseract, buffer.getvalue())
                    results.append(ImageText(f"PDF page {number}", text) if text else None)
                    continue
                for image in page.images:
                    if len(results) >= MAX_IMAGES:
                        break
                    if min(image["width"], image["height"]) < MIN_SIDE_PX:
                        continue
                    box = (max(image["x0"], 0), max(image["top"], 0),
                           min(image["x1"], page.width), min(image["bottom"], page.height))
                    crop = page.crop(box).to_image(resolution=200).original
                    buffer = io.BytesIO()
                    crop.save(buffer, format="PNG")
                    if len(buffer.getvalue()) > MAX_BYTES:
                        results.append(None)
                        continue
                    text = _ocr_image(pytesseract, buffer.getvalue())
                    results.append(ImageText(f"PDF page {number}", text) if text else None)
            except Exception as exc:
                log.warning("PDF page %d image skipped: %s", number, exc)
                results.append(None)
    return results


def blocks(found: list[ImageText]) -> str:
    """The labelled text appended to the report, so quotes from images are visibly marked."""
    return "".join(f"\n\n{BLOCK_HEADER.format(n=item.index, source=item.source)}\n{item.text}\n"
                   for item in found)


def block_spans(text: str) -> list[tuple[int, int, int]]:
    """(image number, start, end) of every OCR block in the final (normalised) text."""
    matches = list(BLOCK_START.finditer(text))
    spans = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((int(match.group(1)), match.start(), end))
    return spans


def apply_ocr_trust(iocs, text: str) -> None:
    """Indicators seen ONLY inside OCR blocks: flag them, lower extraction confidence, and drop hashes
    whose characters don't form a clean hex string of the exact length (OCR misreads characters)."""
    spans = [(start, end) for _, start, end in block_spans(text)]
    if not spans:
        return
    _broken_hashes(iocs, text, spans)
    inside = lambda pos: any(start <= pos < end for start, end in spans)  # noqa: E731
    for ioc in iocs:
        if not ioc.evidence or not all(inside(ev.start) for ev in ioc.evidence):
            continue
        ioc.from_ocr = True
        ioc.confidence.extraction = round(ioc.confidence.extraction * OCR_EXTRACTION_FACTOR, 3)
        expected = HASH_LENGTHS.get(ioc.type)
        if expected and not ioc.filtered_reason:
            clean = re.fullmatch(r"[0-9a-f]+", ioc.value) and len(ioc.value) == expected
            # The token as read must also stand alone: hex characters glued on either side mean OCR
            # merged or split it, so the real hash is unknown.
            glued = any(re.search(rf"[0-9A-Za-z]{re.escape(ioc.value)}|{re.escape(ioc.value)}[0-9A-Za-z]",
                                  text[max(0, ev.start):ev.end], re.IGNORECASE) for ev in ioc.evidence)
            if not clean or glued:
                ioc.filtered_reason = "ocr_unreliable"
                ioc.source_key = "tesseract"


# Hex groups separated by spaces, as OCR often splits a long hash.
_SPLIT_HEX = re.compile(r"\b[0-9a-fA-F]{4,}(?: [0-9a-fA-F]{2,}){1,6}\b")


def _broken_hashes(iocs, text: str, spans: list[tuple[int, int]]) -> None:
    """A hash that OCR split into pieces is listed, dropped as ocr_unreliable, so the analyst sees it
    and checks the image, instead of it vanishing or being trusted."""
    from app.models import IOC, Confidence, Evidence

    by_length = {length: kind for kind, length in HASH_LENGTHS.items()}
    known = {i.value for i in iocs}
    for start, end in spans:
        for match in _SPLIT_HEX.finditer(text, start, end):
            joined = match.group(0).replace(" ", "").lower()
            kind = by_length.get(len(joined))
            if not kind or joined in known:
                continue
            known.add(joined)
            iocs.append(IOC(
                id=f"ioc-{len(iocs) + 1}", type=kind, value=joined, display=match.group(0),
                evidence=[Evidence(quote=match.group(0), start=match.start(), end=match.end())],
                confidence=Confidence(extraction=0.95),  # ×0.6 is applied once, below, like any OCR indicator
                filtered_reason="ocr_unreliable", source_key="tesseract", from_ocr=True,
            ))
