"""Known actor/malware matching. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 10.

Uses official ATT&CK names and aliases only, so no LLM and no hallucinated actors.
"""
import logging
import re

import psycopg

from app import db
from app.models import Evidence

log = logging.getLogger(__name__)

SHORT_NAME_CHARS = 4
_compiled: list[tuple[str, str, list[re.Pattern]]] = []  # (type, canonical name, patterns)


def _load() -> list[tuple[str, str, list[re.Pattern]]]:
    global _compiled
    if _compiled:
        return _compiled
    try:
        with db.pool.connection() as conn:
            rows = conn.execute(
                """SELECT type, name, data FROM attack_objects
                   WHERE type IN ('intrusion-set', 'malware', 'tool') AND NOT revoked AND NOT deprecated"""
            ).fetchall()
    except psycopg.Error as exc:
        log.warning("known entities unavailable: %s", exc)
        return []
    loaded = []
    for row in rows:
        data = row["data"]
        names = {row["name"], *(data.get("aliases") or []), *(data.get("x_mitre_aliases") or [])}
        patterns = []
        for name in filter(None, names):
            flags = 0 if len(name) <= SHORT_NAME_CHARS else re.IGNORECASE
            patterns.append(re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", flags))
        kind = "actor" if row["type"] == "intrusion-set" else "malware"
        loaded.append((kind, row["name"], patterns))
    _compiled = loaded  # stays empty, and is retried, until the ATT&CK tables are filled
    return loaded


def find_known_entities(text: str) -> list[dict]:
    """[{type, key, display, evidence, mentions}]; evidence is the first of the mentions."""
    found = []
    for kind, name, patterns in _load():
        mentions = sorted((Evidence(quote=m.group(0), start=m.start(), end=m.end())
                           for pattern in patterns for m in pattern.finditer(text)),
                          key=lambda e: e.start)
        if mentions:
            found.append({"type": kind, "key": name, "display": name, "evidence": mentions[0],
                          "mentions": mentions})
    return found
