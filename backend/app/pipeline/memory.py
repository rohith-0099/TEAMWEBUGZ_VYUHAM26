"""Temporal memory. STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md section 10."""
from datetime import datetime

from app.mocks import sample_analysis
from app.models import MemoryAlert, ReportAnalysis


async def write_memory(analysis: ReportAnalysis) -> list[MemoryAlert]:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md."""
    return sample_analysis().memory_alerts


def get_graph(at: datetime | None, limit: int = 2000) -> dict:
    """STUB — owner: Lead. See team/05_LEAD_ARCHITECT.md.

    GraphResponse: the sample report linked to its accepted techniques and live IOCs.
    """
    a = sample_analysis()
    published = a.published_at.isoformat()
    nodes = [{"id": f"report:{a.report_id}", "type": "report", "label": a.title,
              "first_seen": published, "last_seen": published, "report_count": 1}]
    nodes += [{"id": f"ioc:{i.type}:{i.value}", "type": "ioc", "label": i.display,
               "first_seen": published, "last_seen": published, "report_count": 1}
              for i in a.iocs if not i.filtered_reason]
    nodes += [{"id": f"technique:{t.technique_id}", "type": "technique", "label": t.name,
               "first_seen": published, "last_seen": published, "report_count": 1}
              for t in a.techniques if t.status == "accepted"]
    nodes = nodes[:limit]
    edges = [{"id": f"e-{n}", "source": node["id"], "target": nodes[0]["id"],
              "relation": "mentioned_in", "valid_from": published, "valid_to": None,
              "report_id": a.report_id}
             for n, node in enumerate(nodes[1:], start=1)]
    alerts = [m.model_dump(mode="json") for m in a.memory_alerts if m.type == "contradiction"]
    return {"nodes": nodes, "edges": edges, "alerts": alerts}
