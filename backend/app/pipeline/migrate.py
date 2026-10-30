"""v20 migrator. Owner: RAG. See team/04_RAG_AI.md Step 8."""

import re
from app.attack.store import get_revocation, is_deprecated_or_revoked, list_tactics
from app.models import Evidence, Migration, TechniqueMatch
from app.pipeline.retrieve import explicit_ids


def migrate(text: str, techniques: list[TechniqueMatch]) -> list[Migration]:
    """Detect deprecated/revoked techniques and tactics, mapping them to v20 equivalents."""
    migrations_by_id: dict[str, Migration] = {}

    # 1. Explicit ID mentions in text
    if text:
        hits = explicit_ids(text)
        for tid, ev in hits:
            if is_deprecated_or_revoked(tid):
                new_ids = get_revocation(tid)
                reason = (
                    f"Revoked/deprecated in ATT&CK v20; replaced by {', '.join(new_ids)}"
                    if new_ids
                    else "Revoked/deprecated in ATT&CK v20"
                )
                if tid not in migrations_by_id:
                    migrations_by_id[tid] = Migration(
                        old_id=tid,
                        new_ids=new_ids,
                        reason=reason,
                        evidence=ev,
                    )

    # 2. Tactic mentions: TA0005 or phrase "Defense Evasion"
    if text:
        tactics = list_tactics()
        stealth_id = next((t["tactic_id"] for t in tactics if t["name"].lower() == "stealth"), "TA0005")
        defense_imp_id = next(
            (t["tactic_id"] for t in tactics if t["name"].lower() == "defense impairment"),
            "TA0112",
        )

        de_pattern = re.compile(r"\b(TA0005|Defense\s+Evasion)\b", flags=re.IGNORECASE)
        for m in de_pattern.finditer(text):
            m_start, m_end = m.start(), m.end()
            # Isolate sentence
            delims = [". ", ".\n", "\n", "? ", "! "]
            s_start = 0
            for d in delims:
                idx = text.rfind(d, 0, m_start)
                if idx != -1:
                    s_start = max(s_start, idx + len(d))
            s_end = len(text)
            for d in delims:
                idx = text.find(d, m_end)
                if idx != -1:
                    s_end = min(s_end, idx + (1 if d.startswith(".") else len(d)))

            sentence = text[s_start:s_end].strip()
            act_start = text.find(sentence, s_start)
            act_end = act_start + len(sentence)
            ev = Evidence(quote=text[act_start:act_end], start=act_start, end=act_end)

            old_id = "TA0005"
            if old_id not in migrations_by_id:
                migrations_by_id[old_id] = Migration(
                    old_id=old_id,
                    new_ids=[stealth_id, defense_imp_id],
                    reason="Defense Evasion was split into Stealth and Defense Impairment in ATT&CK v19",
                    evidence=ev,
                )

    # 3. TechniqueMatch with reject_reason == "deprecated"
    for tech in techniques:
        if tech.reject_reason == "deprecated" and tech.technique_id not in migrations_by_id:
            new_ids = get_revocation(tech.technique_id)
            migrations_by_id[tech.technique_id] = Migration(
                old_id=tech.technique_id,
                new_ids=new_ids,
                reason=(
                    f"Deprecated in ATT&CK v20; replaced by {', '.join(new_ids)}"
                    if new_ids
                    else "Deprecated in ATT&CK v20"
                ),
                evidence=tech.evidence,
            )

    return list(migrations_by_id.values())
