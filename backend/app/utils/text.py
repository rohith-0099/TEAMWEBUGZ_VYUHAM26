"""Text helpers for normalization and defanging. Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 2.
"""
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


# Zero-width characters removed from normalized text
# (Lead's prompt-injection firewall checks raw_text for these before normalization)
ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff")

# Smart quotes, dashes, non-breaking spaces
SMART_SINGLE_QUOTES = ("‘", "’", "‚", "‛")
SMART_DOUBLE_QUOTES = ("“", "”", "„", "‟")
DASHES = ("–", "—", "‒", "−")


def normalize_text(raw: str) -> str:
    """One canonical text. ALL evidence offsets in the system point into this string.

    Rules applied in exact order:
    1. unicodedata.normalize("NFKC", raw)
    2. \\r\\n and \\r -> \\n
    3. Smart quotes -> ', double quotes -> ", dashes -> -, non-breaking space -> space
    4. Remove zero-width characters: \\u200b, \\u200c, \\u200d, \\u2060, \\ufeff
    5. Replace tabs and runs of spaces with one space; strip spaces at line ends
    6. Collapse 3+ newlines into 2; strip the whole string
    """
    if not raw:
        return ""

    # 1. NFKC unicode normalization
    text = unicodedata.normalize("NFKC", raw)

    # 2. Normalize line endings to \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Smart quotes, dashes, non-breaking space
    for ch in SMART_SINGLE_QUOTES:
        text = text.replace(ch, "'")
    for ch in SMART_DOUBLE_QUOTES:
        text = text.replace(ch, '"')
    for ch in DASHES:
        text = text.replace(ch, "-")
    text = text.replace("\u00a0", " ")

    # 4. Remove zero-width characters
    for zw in ZERO_WIDTH_CHARS:
        text = text.replace(zw, "")

    # 5. Process line by line: collapse runs of spaces/tabs to single space, strip line ends
    lines = text.split("\n")
    processed_lines = []
    for line in lines:
        # Replace tabs and consecutive spaces with a single space
        line_clean = re.sub(r"[ \t]+", " ", line)
        # Strip trailing whitespace on each line
        line_clean = line_clean.rstrip(" ")
        # Also strip leading whitespace if line only had spaces
        if line_clean == " ":
            line_clean = ""
        processed_lines.append(line_clean)
    text = "\n".join(processed_lines)

    # 6. Collapse 3+ newlines into 2, strip leading and trailing whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def defang(value: str, ioc_type: str) -> str:
    """Safe display version of an IOC. Never used for logic, only for UI/exports labels.

    Rules:
    - ipv4: 1.2.3.4 -> 1[.]2[.]3[.]4
    - ipv6: 2001:db8::1 -> 2001[:]db8[:][:]1 (replace : with [:])
    - domain: every . -> [.]
    - url: http -> hxxp, https -> hxxps, ftp -> fxp; dots in host part -> [.], path untouched
    - email: @ -> [@], dots after @ -> [.]
    - everything else (hashes, CVE, paths, registry, btc): unchanged
    """
    if not value:
        return ""

    t = ioc_type.lower()

    if t == "ipv4":
        return value.replace(".", "[.]")

    if t == "ipv6":
        return value.replace(":", "[:]")

    if t == "domain":
        return value.replace(".", "[.]")

    if t == "url":
        # Handle URLs: defang scheme (http -> hxxp, https -> hxxps, ftp -> fxp)
        # and host part (dots -> [.]); keep path/query/fragment dots as is.
        try:
            parts = urlsplit(value)
            scheme = parts.scheme
            scheme_lower = scheme.lower()

            if scheme_lower == "https":
                new_scheme = "hxxps"
            elif scheme_lower == "http":
                new_scheme = "hxxp"
            elif scheme_lower == "ftp":
                new_scheme = "fxp"
            else:
                new_scheme = scheme

            # Defang dots in netloc (host and port)
            new_netloc = parts.netloc.replace(".", "[.]")

            if scheme or parts.netloc:
                return urlunsplit((new_scheme, new_netloc, parts.path, parts.query, parts.fragment))
            else:
                # If urlsplit didn't find scheme/netloc (e.g. malformed or defanged input)
                # Split at first slash for path
                if "/" in value:
                    host_part, path_part = value.split("/", 1)
                    return host_part.replace(".", "[.]") + "/" + path_part
                return value.replace(".", "[.]")
        except Exception:
            return value.replace("http", "hxxp").replace(".", "[.]")

    if t == "email":
        if "@" in value:
            user, domain = value.split("@", 1)
            return f"{user}[@]{domain.replace('.', '[.]')}"
        return value.replace("@", "[@]").replace(".", "[.]")

    # Hashes, CVE, filepath, registry, btc, and other stay unchanged
    return value
