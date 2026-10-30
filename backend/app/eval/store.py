"""Evaluation results. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 11."""


def latest_eval() -> dict | None:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    EvalResponse. These numbers are placeholders, not measurements.
    """
    return {
        "ran_at": "2026-10-30T10:00:00Z", "reports": 1,
        "systems": [
            {"system": "baseline", "precision": 0.5, "recall": 0.5, "f1": 0.5, "parent_f1": 0.5,
             "avg_latency_ms": 1000},
            {"system": "trinetra", "precision": 0.5, "recall": 0.5, "f1": 0.5, "parent_f1": 0.5,
             "avg_latency_ms": 1000},
        ],
        "per_report": [{
            "report_id": "mock-report", "title": "[MOCK] Placeholder evaluation",
            "url": "https://intel.example/reports/obsidianlock-2026",
            "baseline": {"tp": ["T1486"], "fp": ["T1190"], "fn": ["T1041"]},
            "trinetra": {"tp": ["T1486", "T1041"], "fp": [], "fn": []},
        }],
    }
