"""Deterministic IOC extraction engine. Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 4.
Must be fast (< 300 ms for 50k chars), no LLM, no network.
Extracts defanged/refanged IOCs, normalizes, applies filters, and extracts evidence.
"""
from __future__ import annotations

import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit

from app.models import IOC, Confidence, Evidence, IOCType
from app.utils.text import defang

# Try importing iocsearcher Searcher (instantiated once if available)
try:
    from iocsearcher.searcher import Searcher
    _ioc_searcher: Searcher | None = Searcher()
except Exception:
    _ioc_searcher = None


# Common file extensions for looks_like_filename filter
FILE_EXTENSIONS = {
    "zip", "mov", "exe", "dll", "pdf", "txt", "doc", "docx", "xls", "xlsx",
    "ppt", "pptx", "bin", "iso", "tar", "gz", "7z", "rar", "png", "jpg",
    "jpeg", "gif", "sh", "bat", "ps1", "py", "vbs", "js", "cfg", "ini",
    "log", "dat", "tmp", "apk", "sys", "drv", "msi", "cmd", "elf",
}

# Reference links domains
REFERENCE_HOSTS = {
    "attack.mitre.org", "cve.mitre.org", "nvd.nist.gov", "virustotal.com",
    "github.com/mitre", "www.virustotal.com",
}


def _load_benign_domains() -> set[str]:
    """Load allowlisted domains from benign_domains.txt."""
    path = Path(__file__).parent.parent / "attack" / "allowlists" / "benign_domains.txt"
    domains: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                domains.add(line)
    return domains


_BENIGN_DOMAINS = _load_benign_domains()


def _refang_str(s: str) -> str:
    """Helper to refang common defanging schemes."""
    res = s.replace("[.]", ".").replace("(.)", ".").replace("{.}", ".")
    res = res.replace("[:]", ":").replace("(:)", ":").replace("{:}", ":")
    res = res.replace("[@]", "@").replace("(@)", "@").replace("{@}", "@")
    res = re.sub(r"^h[xX]{2}ps?://", lambda m: "https://" if "s" in m.group(0).lower() else "http://", res)
    res = re.sub(r"^fxp://", "ftp://", res, flags=re.IGNORECASE)
    return res


# Precompiled regex patterns
RE_CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
RE_REGISTRY = re.compile(
    r"\b(?:HKLM|HKCU|HKCR|HKU|HKEY_LOCAL_MACHINE|HKEY_CURRENT_USER|HKEY_CLASSES_ROOT|HKEY_USERS)\\[^\s\"'<>|]+",
    re.IGNORECASE,
)
RE_WIN_PATH = re.compile(r"\b[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n\s]+")
RE_LINUX_PATH = re.compile(r"(?<![\w/])/(?:tmp|etc|var|usr|home|opt|dev/shm)/[^\s\"'<>]+")
RE_HASH_SHA512 = re.compile(r"\b[0-9a-fA-F]{128}\b")
RE_HASH_SHA256 = re.compile(r"\b[0-9a-fA-F]{64}\b")
RE_HASH_SHA1 = re.compile(r"\b[0-9a-fA-F]{40}\b")
RE_HASH_MD5 = re.compile(r"\b[0-9a-fA-F]{32}\b")
RE_BTC = re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b")
RE_IPV4_DEFANGED = re.compile(r"\b(?:[0-9]{1,3}(?:\[\.\]|\.)){3}[0-9]{1,3}\b")
RE_URL_DEFANGED = re.compile(r"\b(?:h[xX]{2}ps?|https?|ftp|fxp)://[^\s\"'<>]+", re.IGNORECASE)
RE_EMAIL_DEFANGED = re.compile(
    r"\b[a-zA-Z0-9._%+-]+(?:@|\[@\])[a-zA-Z0-9.-]+(?:\[\.\]|\.)[a-zA-Z]{2,}\b"
)
RE_DOMAIN_DEFANGED = re.compile(
    r"\b[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\[\.\]|\.)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])*(?:\[\.\]|\.)[a-zA-Z]{2,}\b"
)


def _strip_trailing_punct(s: str) -> str:
    """Strip trailing punctuation from extracted values."""
    return s.rstrip(".,;:)]\"'")


def _find_evidence_span(text: str, match_start: int, match_end: int) -> tuple[int, int]:
    """Calculate exact start/end sentence boundary centered on match, max 300 chars."""
    sent_start = 0
    for i in range(match_start - 1, -1, -1):
        if text[i] == "\n":
            sent_start = i + 1
            break
        if text[i] in ".!?" and i + 1 < len(text) and text[i + 1] in " \t\r\n":
            j = i + 1
            while j < match_start and text[j] in " \t":
                j += 1
            sent_start = j
            break

    sent_end = len(text)
    for i in range(match_end, len(text)):
        if text[i] == "\n":
            sent_end = i
            break
        if text[i] in ".!?" and (i + 1 == len(text) or text[i + 1] in " \t\r\n"):
            sent_end = i + 1
            break

    while sent_start < match_start and text[sent_start] in " \t":
        sent_start += 1
    while sent_end > match_end and text[sent_end - 1] in " \t":
        sent_end -= 1

    # Cap to 300 chars centered on match if needed
    if (sent_end - sent_start) > 300:
        match_mid = (match_start + match_end) // 2
        win_start = max(sent_start, match_mid - 150)
        win_end = min(sent_end, win_start + 300)
        if win_end == sent_end:
            win_start = max(sent_start, win_end - 300)
        if win_start > match_start:
            win_start = match_start
            win_end = min(sent_end, win_start + 300)
        if win_end < match_end:
            win_end = match_end
            win_start = max(sent_start, win_end - 300)
        sent_start, sent_end = win_start, win_end

    return sent_start, sent_end


def _is_benign_domain(domain: str, allowlist: set[str]) -> bool:
    """Check if domain or parent domain matches allowlist."""
    d = domain.lower().rstrip(".")
    if d in allowlist:
        return True
    for parent in allowlist:
        if d.endswith("." + parent):
            return True
    return False


def _check_version_number(text: str, start: int, value: str) -> bool:
    """Check if IPv4 value is preceded by version / ver / build keywords."""
    # Look back up to 15 characters
    prefix = text[max(0, start - 15):start]
    if re.search(r"(?i)(?:version|ver|v\d*|build)[\s:=]*$", prefix):
        return True
    # If octet exceeds 255 but has 4 dotted numbers, it's a version/build string
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return True
    return False


def extract_iocs(text: str, publisher_domain: str | None = None) -> list[IOC]:
    """Extract, normalize, deduplicate, filter, and score IOCs from canonical report text.

    Role stays 'unknown' (LLM role agent fills it later).
    """
    if not text:
        return []

    allowlist = set(_BENIGN_DOMAINS)
    if publisher_domain:
        allowlist.add(publisher_domain.lower().strip("."))

    # Collect extracted candidate matches: list of (ioc_type, value, start_idx, end_idx)
    raw_candidates: list[tuple[IOCType, str, int, int]] = []

    # 1. Use iocsearcher if installed
    if _ioc_searcher is not None:
        try:
            # Check if search_raw exists and returns positions
            if hasattr(_ioc_searcher, "search_raw"):
                for item in _ioc_searcher.search_raw(text):
                    # Tuple structure typically: (type, value, start, raw)
                    raw_type, val, start = item[0], item[1], item[2]
                    end = start + len(item[3]) if len(item) > 3 else start + len(val)
                    type_map: dict[str, IOCType] = {
                        "ip4": "ipv4", "ip6": "ipv6", "fqdn": "domain", "url": "url",
                        "email": "email", "md5": "md5", "sha1": "sha1", "sha256": "sha256",
                        "sha512": "sha512", "cve": "cve", "bitcoin": "btc",
                    }
                    if raw_type in type_map:
                        raw_candidates.append((type_map[raw_type], val, start, end))
        except Exception:
            pass

    # 2. Add our deterministic regex extractors (captures positions and defanged indicators)
    # URLs
    for m in RE_URL_DEFANGED.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        refanged = _refang_str(raw_val)
        raw_candidates.append(("url", refanged, m.start(), m.start() + len(raw_val)))

    # IPv4 (defanged or normal)
    for m in RE_IPV4_DEFANGED.finditer(text):
        raw_val = m.group(0)
        refanged = _refang_str(raw_val)
        raw_candidates.append(("ipv4", refanged, m.start(), m.end()))

    # Emails
    for m in RE_EMAIL_DEFANGED.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        refanged = _refang_str(raw_val)
        raw_candidates.append(("email", refanged, m.start(), m.start() + len(raw_val)))

    # Domains
    for m in RE_DOMAIN_DEFANGED.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        # Ensure it's not preceded by @ (which would be email) or :// (url)
        start = m.start()
        if start > 0 and text[start - 1] in "@":
            continue
        if start >= 3 and text[start - 3:start] == "://":
            continue
        refanged = _refang_str(raw_val).lower().rstrip(".")
        raw_candidates.append(("domain", refanged, m.start(), m.start() + len(raw_val)))

    # Hashes (order: sha512, sha256, sha1, md5 to prevent prefix collisions)
    seen_hash_spans: set[tuple[int, int]] = set()

    for m in RE_HASH_SHA512.finditer(text):
        raw_candidates.append(("sha512", m.group(0).lower(), m.start(), m.end()))
        seen_hash_spans.add((m.start(), m.end()))

    for m in RE_HASH_SHA256.finditer(text):
        if not any(s <= m.start() and m.end() <= e for s, e in seen_hash_spans):
            raw_candidates.append(("sha256", m.group(0).lower(), m.start(), m.end()))
            seen_hash_spans.add((m.start(), m.end()))

    for m in RE_HASH_SHA1.finditer(text):
        if not any(s <= m.start() and m.end() <= e for s, e in seen_hash_spans):
            raw_candidates.append(("sha1", m.group(0).lower(), m.start(), m.end()))
            seen_hash_spans.add((m.start(), m.end()))

    for m in RE_HASH_MD5.finditer(text):
        if not any(s <= m.start() and m.end() <= e for s, e in seen_hash_spans):
            raw_candidates.append(("md5", m.group(0).lower(), m.start(), m.end()))

    # CVE
    for m in RE_CVE.finditer(text):
        raw_candidates.append(("cve", m.group(0).upper(), m.start(), m.end()))

    # Registry
    for m in RE_REGISTRY.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        raw_candidates.append(("registry", raw_val, m.start(), m.start() + len(raw_val)))

    # Windows Paths
    for m in RE_WIN_PATH.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        raw_candidates.append(("filepath", raw_val, m.start(), m.start() + len(raw_val)))

    # Linux Paths
    for m in RE_LINUX_PATH.finditer(text):
        raw_val = _strip_trailing_punct(m.group(0))
        raw_candidates.append(("filepath", raw_val, m.start(), m.start() + len(raw_val)))

    # Bitcoin
    for m in RE_BTC.finditer(text):
        raw_candidates.append(("btc", m.group(0), m.start(), m.end()))

    # Collect all file names found in paths (for looks_like_filename filter)
    extracted_filenames: set[str] = set()
    for t, val, _, _ in raw_candidates:
        if t == "filepath":
            # Extract basename
            base = val.replace("\\", "/").split("/")[-1].lower()
            if base:
                extracted_filenames.add(base)

    # Sort candidates by first appearance index
    raw_candidates.sort(key=lambda x: x[2])

    # Group by (type, normalized_value)
    grouped: dict[tuple[IOCType, str], list[tuple[int, int]]] = {}
    first_seen: dict[tuple[IOCType, str], int] = {}

    for ioc_type, val, start, end in raw_candidates:
        val_clean = _strip_trailing_punct(val)

        # Type-specific value normalization
        if ioc_type in ("md5", "sha1", "sha256", "sha512"):
            val_clean = val_clean.lower()
        elif ioc_type == "domain":
            val_clean = val_clean.lower().rstrip(".")
        elif ioc_type == "cve":
            val_clean = val_clean.upper()
        elif ioc_type == "url":
            try:
                parts = urlsplit(val_clean)
                new_netloc = parts.netloc.lower()
                val_clean = parts._replace(netloc=new_netloc).geturl()
            except Exception:
                pass

        key = (ioc_type, val_clean)
        if key not in grouped:
            grouped[key] = []
            first_seen[key] = start

        # Avoid duplicate spans for the same match position
        if not any(abs(start - s) < 3 for s, _ in grouped[key]):
            grouped[key].append((start, end))

    # Evaluate filters and construct IOC objects
    results: list[IOC] = []
    ioc_counter = 1

    # Preserve order of first appearance
    sorted_keys = sorted(grouped.keys(), key=lambda k: first_seen[k])

    for ioc_type, value in sorted_keys:
        occurrences = grouped[(ioc_type, value)]
        first_start = occurrences[0][0]

        filtered_reason: str | None = None

        # Filter 1: Private or reserved IP
        if ioc_type in ("ipv4", "ipv6"):
            try:
                ip = ipaddress.ip_address(value)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                    or ip.is_unspecified
                ):
                    filtered_reason = "private_or_reserved_ip"
            except ValueError:
                # If IPv4 failed parsing, check if it's a version number
                if ioc_type == "ipv4":
                    filtered_reason = "version_number"

        # Filter 2: Version number lookalike
        if ioc_type == "ipv4" and not filtered_reason:
            if _check_version_number(text, first_start, value):
                filtered_reason = "version_number"

        # Filter 3 & 4: Benign domain or reference link
        if ioc_type == "domain":
            # Invalid domain check
            parts = value.split(".")
            tld = parts[-1] if len(parts) > 1 else ""
            if len(parts) < 2 or not tld.isalpha():
                filtered_reason = "invalid_domain"
            elif _is_benign_domain(value, allowlist):
                filtered_reason = "benign_domain"
            elif tld in FILE_EXTENSIONS or value in extracted_filenames:
                filtered_reason = "looks_like_filename"

        if ioc_type == "url":
            try:
                host = urlsplit(value).netloc.lower()
                if ":" in host:
                    host = host.split(":")[0]
                if host in REFERENCE_HOSTS or any(value.startswith(f"https://{h}") or value.startswith(f"http://{h}") for h in REFERENCE_HOSTS):
                    filtered_reason = "reference_link"
                elif _is_benign_domain(host, allowlist):
                    filtered_reason = "benign_domain"
            except Exception:
                pass

        # Calculate evidence for up to 3 occurrences
        evidence_list: list[Evidence] = []
        for s, e in occurrences[:3]:
            # Ensure s and e are within bounds
            s_idx = max(0, min(s, len(text) - 1))
            e_idx = max(s_idx, min(e, len(text)))
            span_s, span_e = _find_evidence_span(text, s_idx, e_idx)
            quote = text[span_s:span_e]
            evidence_list.append(Evidence(quote=quote, start=span_s, end=span_e))

        # Scoring confidence by type
        if ioc_type in ("md5", "sha1", "sha256", "sha512", "cve"):
            conf_val = 0.95
        elif ioc_type in ("ipv4", "ipv6", "url"):
            conf_val = 0.90
        elif ioc_type in ("domain", "email"):
            conf_val = 0.85
        else:
            conf_val = 0.75

        display_val = defang(value, ioc_type)

        results.append(
            IOC(
                id=f"ioc-{ioc_counter}",
                type=ioc_type,
                value=value,
                display=display_val,
                role="unknown",
                evidence=evidence_list,
                confidence=Confidence(extraction=conf_val),
                linked_techniques=[],
                filtered_reason=filtered_reason,
            )
        )
        ioc_counter += 1

    return results
