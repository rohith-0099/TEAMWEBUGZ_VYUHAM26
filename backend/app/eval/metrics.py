"""Scoring for the scoreboard. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 11."""
import re

from app.utils.sections import reference_sections

LEAKAGE_RULE = ("Before scoring, every ATT&CK table, appendix and reference section is cut from the report, "
                "every line that names a technique or tactic ID (T1234, T1234.001, TA0001) and is short enough "
                "to be a table row is dropped, and every remaining ID is deleted. Otherwise the report's own "
                "answers would be graded.")

TECHNIQUE_ID = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
TACTIC_ID = re.compile(r"\bTA\d{4}\b")
MAX_TABLE_LINE_CHARS = 200


def strip_leakage(text: str) -> str:
    """Removes the report's own answers: ATT&CK table rows and every explicit ID.

    Without this, the eval would grade the report against itself.
    """
    for start, end in reversed(reference_sections(text)):
        text = text[:start] + text[end:]
    kept = []
    for line in text.split("\n"):
        has_id = TECHNIQUE_ID.search(line) or TACTIC_ID.search(line)
        if has_id and (len(line) <= MAX_TABLE_LINE_CHARS or line.lstrip().startswith("|")):
            continue
        kept.append(TACTIC_ID.sub("", TECHNIQUE_ID.sub("", line)))
    return "\n".join(kept)


def to_parents(ids: set[str]) -> set[str]:
    return {i.split(".")[0] for i in ids}


def score_report(truth: set[str], predicted: set[str]) -> dict[str, list[str]]:
    return {"tp": sorted(truth & predicted), "fp": sorted(predicted - truth), "fn": sorted(truth - predicted)}


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def micro_average(pairs: list[tuple[set[str], set[str]]]) -> dict[str, float]:
    """Micro-averaged scores over (truth, predicted) pairs, plus F1 at parent level."""
    tp = sum(len(t & p) for t, p in pairs)
    fp = sum(len(p - t) for t, p in pairs)
    fn = sum(len(t - p) for t, p in pairs)
    precision, recall, f1 = _f1(tp, fp, fn)
    parents = [(to_parents(t), to_parents(p)) for t, p in pairs]
    _, _, parent_f1 = _f1(sum(len(t & p) for t, p in parents), sum(len(p - t) for t, p in parents),
                          sum(len(t - p) for t, p in parents))
    return {"precision": precision, "recall": recall, "f1": f1, "parent_f1": parent_f1}
