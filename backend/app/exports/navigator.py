"""ATT&CK Navigator export. STUB — owner: Backend Core. See team/03_BACKEND_CORE.md Step 6."""
from app.models import ReportAnalysis


def build_navigator_layer(analysis: ReportAnalysis, include_predicted: bool = False) -> dict:
    """STUB — owner: Backend Core. See team/03_BACKEND_CORE.md."""
    techniques = [
        {"techniqueID": t.technique_id, "tactic": tactic, "score": round((t.confidence.mapping or 0) * 100)}
        for t in analysis.techniques if t.status == "accepted" for tactic in t.tactics
    ]
    if include_predicted:
        techniques += [{"techniqueID": t.technique_id, "tactic": tactic, "score": 0, "color": "#a78bfa",
                        "comment": "Predicted (not observed)"}
                       for t in analysis.predictions for tactic in t.tactics]
    return {"name": f"TRINETRA – {analysis.title}", "domain": "enterprise-attack",
            "versions": {"attack": "20", "layer": "4.5"}, "techniques": techniques}
