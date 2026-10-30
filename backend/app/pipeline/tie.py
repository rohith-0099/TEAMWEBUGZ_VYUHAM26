"""Technique predictions. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 7.

This is the co-occurrence model over ATT&CK v20 groups, campaigns and software (Option B),
not the CTID Technique Inference Engine. Label it that way in the UI.
"""
import math

from app.attack import store
from app.models import TechniqueMatch

MIN_SCORE = 0.15


def _parent(technique_id: str) -> str:
    return technique_id.split(".")[0]


def _with_parents(ids: set[str]) -> set[str]:
    return ids | {_parent(i) for i in ids}


def predict(observed_ids: list[str], top_n: int = 5) -> list[TechniqueMatch]:
    """score(t) = sum over sets s of cos(O, s) for each s containing t, normalised to 0..1."""
    observed = set(observed_ids)
    if not observed:
        return []
    observed_expanded = _with_parents(observed)

    scores: dict[str, float] = {}
    support: dict[str, int] = {}  # sets that back this technique and overlap the report
    together: dict[tuple[str, str], int] = {}  # (candidate, observed) co-occurrence counts
    for raw in store.get_technique_sets():
        technique_set = _with_parents(raw)
        overlap = observed_expanded & technique_set
        if not overlap:
            continue
        similarity = len(overlap) / math.sqrt(len(observed_expanded) * len(technique_set))
        for tid in raw:
            if tid in observed_expanded:  # also covers the parent of an observed sub-technique
                continue
            scores[tid] = scores.get(tid, 0.0) + similarity
            support[tid] = support.get(tid, 0) + 1
            for seen in overlap & observed:
                together[(tid, seen)] = together.get((tid, seen), 0) + 1
    if not scores:
        return []

    top = max(scores.values())
    ranked = sorted(scores, key=lambda t: (-scores[t], t))
    results: list[TechniqueMatch] = []
    for tid in ranked:
        score = scores[tid] / top
        if len(results) == top_n or score < MIN_SCORE:
            break
        row = store.get_technique(tid) if store.technique_exists(tid) else None
        if row is None:
            continue
        drivers = sorted((o for o in observed if (tid, o) in together),
                         key=lambda o: (-together[(tid, o)], o))[:2]
        rationale = (f"Frequently co-occurs with {' and '.join(drivers) or 'the observed techniques'} "
                     f"in {support[tid]} known groups/campaigns/software")
        results.append(TechniqueMatch(
            technique_id=tid, name=row.get("name", tid), tactics=row.get("tactics") or [],
            status="accepted", origin="predicted", prediction_score=round(score, 3),
            rationale=rationale, url=row.get("url"),
        ))
    return results
