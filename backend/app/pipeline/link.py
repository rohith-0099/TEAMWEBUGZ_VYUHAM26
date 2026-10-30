"""IOC <-> technique linker. Owner: RAG. See team/04_RAG_AI.md Step 8."""

import re
from app.models import IOC, TechniqueMatch, Evidence


def _spans_overlap(e1: Evidence, e2: Evidence) -> bool:
    return max(e1.start, e2.start) < min(e1.end, e2.end)


def _same_sentence(e1: Evidence, e2: Evidence, text: str) -> bool:
    s_start = min(e1.start, e2.start)
    s_end = max(e1.end, e2.end)
    between = text[min(e1.end, e2.end):max(e1.start, e2.start)]
    # Check for sentence terminators between them
    return not bool(re.search(r"[.!?]\s+|\n", between))


def _same_paragraph_near(e1: Evidence, e2: Evidence, text: str) -> bool:
    distance = max(0, max(e1.start, e2.start) - min(e1.end, e2.end))
    if distance >= 300:
        return False
    between = text[min(e1.end, e2.end):max(e1.start, e2.start)]
    return "\n\n" not in between


def link_iocs(
    iocs: list[IOC],
    techniques: list[TechniqueMatch],
    text: str,
) -> tuple[list[IOC], list[TechniqueMatch]]:
    """Link accepted techniques with non-filtered IOCs based on textual proximity."""
    if not text:
        return iocs, techniques

    accepted_techniques = [t for t in techniques if t.status == "accepted"]
    non_filtered_iocs = [i for i in iocs if i.filtered_reason is None]

    ioc_by_id = {i.id: i for i in iocs}

    for tech in accepted_techniques:
        tech_ev = tech.evidence
        # Existing verifier hints
        existing_hints = set(tech.linked_iocs)

        for ioc in non_filtered_iocs:
            best_score = 0.0

            if ioc.id in existing_hints:
                best_score = max(best_score, 0.7)

            if tech_ev is not None:
                for ioc_ev in ioc.evidence:
                    if _spans_overlap(tech_ev, ioc_ev):
                        best_score = max(best_score, 0.9)
                    elif _same_sentence(tech_ev, ioc_ev, text):
                        best_score = max(best_score, 0.8)
                    elif _same_paragraph_near(tech_ev, ioc_ev, text):
                        best_score = max(best_score, 0.6)

            if best_score > 0.0:
                if ioc.id not in tech.linked_iocs:
                    tech.linked_iocs.append(ioc.id)
                if tech.technique_id not in ioc.linked_techniques:
                    ioc.linked_techniques.append(tech.technique_id)

                curr_rel_tech = tech.confidence.relationship or 0.0
                tech.confidence.relationship = round(max(curr_rel_tech, best_score), 2)

                curr_rel_ioc = ioc.confidence.relationship or 0.0
                ioc.confidence.relationship = round(max(curr_rel_ioc, best_score), 2)

    return iocs, techniques
