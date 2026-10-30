"""Disruption simulator. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 8."""
from app.attack.store import get_mitigations
from app.models import ReportAnalysis


def simulate(analysis: ReportAnalysis, blocked_node_ids: list[str]) -> dict:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    SimulateResponse. The mock flow has one chain, so any blocked observed node breaks it.
    """
    chain = [n for n in analysis.flow.nodes if n.kind != "predicted"]
    blocked = [n for n in chain if n.id in blocked_node_ids and n.kind == "observed"]
    broken = 1 if blocked else 0
    countermeasures = [
        {"technique_id": n.technique_id, "id": m["id"], "name": m["name"],
         "source": "attack_mitigation", "derived": False, "url": m["url"]}
        for n in blocked for m in get_mitigations(n.technique_id)
    ]
    return {"total_paths": 1, "broken_paths": broken, "broken_pct": 100.0 * broken,
            "surviving_paths": [] if blocked else [[n.id for n in chain]],
            "affected_node_ids": [n.id for n in chain] if blocked else [],
            "countermeasures": countermeasures, "note": "mock result"}
