"""Telling described behaviour apart from lists of technique names. Owner: Lead.

CISA's ATT&CK mapping guide: a list of techniques without the technical context of how the
adversary executed them is not enough to map. So ATT&CK tables, appendices and reference
lists are never evidence, even when they name the right technique.
"""
import re

TECHNIQUE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
TACTIC_ID = re.compile(r"\bTA\d{4}\b")
# Whole words only: "ttps" must not match inside "https".
REFERENCE_HEADING = re.compile(r"\b(?:att&ck|att&amp;ck|attack mapping|appendix|techniques|ttps|references)\b",
                               re.IGNORECASE)
_HEADING_LINE = re.compile(r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+|appendix\b)?(?P<title>[A-Z][^\n]{0,98})$",
                           re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z]{2,}")
MIN_ACTION_WORDS = 6  # a technique name rarely runs longer; a described action does


def _heading_lines(text: str) -> list[tuple[int, str]]:
    """(offset, title) of short title-like lines that open a block (start of text or after a blank line)."""
    headings = []
    offset = 0
    previous_blank = True
    for line in text.split("\n"):
        stripped = line.strip()
        marked = re.match(r"^(#{1,6}\s|\d+(\.\d+)*\.?\s+[A-Z]|appendix\b)", stripped, re.IGNORECASE)
        if stripped and (previous_blank or marked) and len(stripped) <= 100 and not stripped.endswith((",", ";", ":")):
            match = _HEADING_LINE.match(stripped)
            # A sentence ends in a full stop; a heading usually doesn't, unless it's a short run-in title.
            if match and (not stripped.endswith(".") or len(stripped.split()) <= 6):
                headings.append((offset, stripped))
        previous_blank = not stripped
        offset += len(line) + 1
    return headings


def section_heading_at(text: str, position: int, headings: list[tuple[int, str]] | None = None) -> str | None:
    """The closest heading-like line at or before `position`."""
    current = None
    for offset, title in headings if headings is not None else _heading_lines(text):
        if offset > position:
            break
        current = title
    return current


def in_reference_section(text: str, position: int, headings: list[tuple[int, str]] | None = None) -> bool:
    heading = section_heading_at(text, position, headings)
    return bool(heading and REFERENCE_HEADING.search(heading))


def reference_sections(text: str) -> list[tuple[int, int]]:
    """(start, end) spans of ATT&CK tables, appendices and reference lists, by heading."""
    headings = _heading_lines(text)
    spans = []
    for i, (offset, title) in enumerate(headings):
        if REFERENCE_HEADING.search(title):
            end = len(text)
            for next_offset, next_title in headings[i + 1:]:
                if not REFERENCE_HEADING.search(next_title) and re.match(r"^\s*(#|\d+\.)", next_title):
                    end = next_offset  # the next numbered/markdown section ends this one
                    break
            spans.append((offset, end))
    return spans


def is_listing(quote: str, technique_names: set[str] | None = None) -> bool:
    """True when a quote is mostly technique IDs and names rather than a described action."""
    if not TECHNIQUE_ID.search(quote) and not TACTIC_ID.search(quote):
        return False
    rest = TACTIC_ID.sub(" ", TECHNIQUE_ID.sub(" ", quote)).lower()
    for name in sorted(technique_names or (), key=len, reverse=True):
        rest = rest.replace(name.lower(), " ")
    return len(_WORD.findall(rest)) < MIN_ACTION_WORDS
