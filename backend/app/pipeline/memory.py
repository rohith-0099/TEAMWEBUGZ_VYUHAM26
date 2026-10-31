"""Temporal memory + contradictions. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 10.

Writes only verified pipeline output. Shared infrastructure never means "same operator",
so alerts say "conflicting claims".
"""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib

from psycopg.types.json import Jsonb

from app import db
from app.models import MemoryAlert, ReportAnalysis, ReportRef
from app.pipeline.entities import find_known_entities
from app.pipeline.notify import notify

CONTRADICTION_WINDOW = timedelta(days=180)
MAX_ALERT_NOTIFICATIONS = 3
QUOTE_CHARS = 400

# ReportAnalysis.text is already normalised by ingest.
_SAME_TEXT = """
    SELECT id, title, published_at, created_at FROM analyses
    WHERE id <> %s AND status = 'done'
      AND encode(sha256(convert_to(result->>'text', 'UTF8')), 'hex') = %s
    ORDER BY created_at LIMIT 1"""
_PRIOR_MENTIONS = """
    SELECT e.report_id, e.valid_from, e.evidence, a.title, a.published_at
    FROM mem_edges e JOIN analyses a ON a.id = e.report_id
    WHERE e.src = %s AND e.relation = 'mentioned_in' AND e.report_id <> %s
    ORDER BY e.valid_from"""
_PRIOR_ATTRIBUTIONS = """
    SELECT e.report_id, e.valid_from, e.evidence, a.title, a.published_at, n.display AS actor
    FROM mem_edges e JOIN analyses a ON a.id = e.report_id JOIN mem_nodes n ON n.id = e.dst
    WHERE e.src = %s AND e.relation = 'attributed_to' AND e.report_id <> %s
    ORDER BY e.valid_from"""


def _upsert_node(conn, kind: str, key: str, display: str, seen: datetime) -> str:
    node_id = f"{kind}:{key}"
    conn.execute(
        """INSERT INTO mem_nodes (id, type, key, display, first_seen, last_seen)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (type, key) DO UPDATE SET
             first_seen = LEAST(mem_nodes.first_seen, EXCLUDED.first_seen),
             last_seen = GREATEST(mem_nodes.last_seen, EXCLUDED.last_seen)""",
        (node_id, kind, key, display, seen, seen),
    )
    return node_id


def _add_edge(conn, src: str, dst: str, relation: str, report_id: str, seen: datetime,
              evidence: dict | None) -> None:
    conn.execute(
        """INSERT INTO mem_edges (src, dst, relation, valid_from, report_id, evidence)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (src, dst, relation, seen, report_id, Jsonb(evidence) if evidence else None),
    )


def _ref(row: dict) -> ReportRef:
    return ReportRef(report_id=row["report_id"], title=row["title"], published_at=row["published_at"],
                     quote=(row["evidence"] or {}).get("quote"))


def _paragraph(text: str, position: int) -> tuple[int, int]:
    start = text.rfind("\n\n", 0, position)
    end = text.find("\n\n", position)
    return (0 if start < 0 else start + 2), (len(text) if end < 0 else end)


def _far_apart(a: datetime | None, b: datetime | None) -> bool:
    return bool(a and b) and abs(a - b) > CONTRADICTION_WINDOW


def _duplicate_alert(conn, a: ReportAnalysis) -> MemoryAlert | None:
    """Re-analysing the same text proves nothing new, so it gets one notice and no graph edges."""
    digest = hashlib.sha256(a.text.encode()).hexdigest()
    row = conn.execute(_SAME_TEXT, (a.report_id, digest)).fetchone()
    if row is None:
        return None
    return MemoryAlert(
        type="duplicate_report", entity_type="report", entity_key=row["id"], entity_display=row["title"],
        message=f"This report was already analysed on {row['created_at']:%d %b %Y}",
        reports=[ReportRef(report_id=row["id"], title=row["title"], published_at=row["published_at"])],
    )


def _write(a: ReportAnalysis) -> list[MemoryAlert]:
    seen = a.published_at or a.created_at or datetime.now(timezone.utc)
    current = ReportRef(report_id=a.report_id, title=a.title, published_at=a.published_at)
    entities = find_known_entities(a.text)
    accepted = {}
    for t in a.techniques:
        if t.status == "accepted" and t.evidence:
            accepted.setdefault(t.technique_id, t)

    alerts: list[MemoryAlert] = []
    with db.pool.connection() as conn:
        duplicate = _duplicate_alert(conn, a)
        if duplicate:
            return [duplicate]

        report_node = _upsert_node(conn, "report", a.report_id, a.title, seen)

        technique_nodes = {}
        for tid, t in accepted.items():
            technique_nodes[tid] = _upsert_node(conn, "technique", tid, f"{tid} {t.name}", seen)
            _add_edge(conn, technique_nodes[tid], report_node, "mentioned_in", a.report_id, seen,
                      t.evidence.model_dump())

        entity_nodes = {}
        for entity in entities:
            node = _upsert_node(conn, entity["type"], entity["key"], entity["display"], seen)
            entity_nodes[entity["key"]] = node
            for technique_node in technique_nodes.values():
                _add_edge(conn, node, technique_node, "uses", a.report_id, seen, entity["evidence"].model_dump())

        for ioc in a.iocs:
            if ioc.filtered_reason:
                continue
            node = _upsert_node(conn, "ioc", f"{ioc.type}:{ioc.value}", ioc.display, seen)
            first = ioc.evidence[0] if ioc.evidence else None
            quote = {"quote": first.quote, "start": first.start, "end": first.end} if first else {}
            prior = conn.execute(_PRIOR_MENTIONS, (node, a.report_id)).fetchall()
            prior_actors = conn.execute(_PRIOR_ATTRIBUTIONS, (node, a.report_id)).fetchall()
            here = current.model_copy(update={"quote": first.quote if first else None})

            _add_edge(conn, node, report_node, "mentioned_in", a.report_id, seen, {**quote, "role": ioc.role})
            actors_here = {}
            for entity in entities:
                for ev in ioc.evidence:
                    start, end = _paragraph(a.text, ev.start)
                    if any(start <= m.start < end for m in entity["mentions"]):
                        paragraph = a.text[start:end][:QUOTE_CHARS]
                        _add_edge(conn, node, entity_nodes[entity["key"]], "attributed_to", a.report_id,
                                  seen, {"quote": paragraph})
                        actors_here[entity["display"]] = paragraph
                        break

            if prior:
                earlier = {row["report_id"]: row for row in prior}
                alerts.append(MemoryAlert(
                    type="seen_before", entity_type="ioc", entity_key=f"{ioc.type}:{ioc.value}",
                    entity_display=ioc.display,
                    message=f"{ioc.display} appeared in {len(earlier)} earlier report(s)",
                    reports=[_ref(row) for row in earlier.values()],
                ))

            other_roles = [r for r in prior if ioc.role != "unknown"
                           and (r["evidence"] or {}).get("role") not in (None, "unknown", ioc.role)]
            if other_roles:
                roles = sorted({r["evidence"]["role"] for r in other_roles})
                alerts.append(MemoryAlert(
                    type="contradiction", entity_type="ioc", entity_key=f"{ioc.type}:{ioc.value}",
                    entity_display=ioc.display,
                    message=(f"Conflicting claims: {ioc.display} is described as {ioc.role} here "
                             f"and as {', '.join(roles)} in earlier reports"),
                    reports=[here, *map(_ref, other_roles)],
                    explained_by_time=any(_far_apart(seen, r["valid_from"]) for r in other_roles),
                ))

            other_actors = [r for r in prior_actors if actors_here and r["actor"] not in actors_here]
            if other_actors:
                names = sorted({r["actor"] for r in other_actors})
                alerts.append(MemoryAlert(
                    type="contradiction", entity_type="ioc", entity_key=f"{ioc.type}:{ioc.value}",
                    entity_display=ioc.display,
                    message=(f"Conflicting claims: {ioc.display} is linked to {', '.join(sorted(actors_here))} "
                             f"here and to {', '.join(names)} in earlier reports"),
                    reports=[here, *map(_ref, other_actors)],
                    explained_by_time=any(_far_apart(seen, r["valid_from"]) for r in other_actors),
                ))
    return alerts


async def write_memory(analysis: ReportAnalysis) -> list[MemoryAlert]:
    alerts = await asyncio.to_thread(_write, analysis)
    for alert in alerts[:MAX_ALERT_NOTIFICATIONS]:
        await notify("memory_alert", {"report_id": analysis.report_id, "title": analysis.title,
                                      "message": alert.message})
    return alerts


def _store_contradictions(conn) -> list[dict]:
    """Role conflicts and attribution conflicts over every report in the store."""
    rows = conn.execute(
        """SELECT e.src, e.relation, e.report_id, e.valid_from, e.evidence, a.title, a.published_at,
                  n.display, d.display AS target
           FROM mem_edges e
           JOIN analyses a ON a.id = e.report_id
           JOIN mem_nodes n ON n.id = e.src
           JOIN mem_nodes d ON d.id = e.dst
           WHERE n.type = 'ioc' AND e.relation IN ('mentioned_in', 'attributed_to')
           ORDER BY e.valid_from"""
    ).fetchall()
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        claim = row["target"] if row["relation"] == "attributed_to" else (row["evidence"] or {}).get("role")
        if claim and claim != "unknown":
            grouped.setdefault((row["src"], row["relation"]), []).append({**row, "claim": claim})

    alerts = []
    for (src, relation), claims in grouped.items():
        distinct = sorted({c["claim"] for c in claims})
        if len(distinct) < 2 or len({c["report_id"] for c in claims}) < 2:
            continue
        verb = "linked to" if relation == "attributed_to" else "described as"
        display = claims[0]["display"]
        dates = [c["valid_from"] for c in claims]
        alerts.append(MemoryAlert(
            type="contradiction", entity_type="ioc", entity_key=src.removeprefix("ioc:"),
            entity_display=display, message=f"Conflicting claims: {display} is {verb} {', '.join(distinct)}",
            reports=[_ref(c) for c in claims], explained_by_time=_far_apart(min(dates), max(dates)),
        ).model_dump(mode="json"))
    return alerts


def get_graph(at: datetime | None, limit: int = 2000) -> dict:
    """GraphResponse as of `at` (or everything), keeping the most connected nodes."""
    with db.pool.connection() as conn:
        nodes = conn.execute(
            """SELECT n.id, n.type, n.display, n.first_seen, n.last_seen,
                      count(DISTINCT e.report_id) AS report_count, count(e.id) AS degree
               FROM mem_nodes n
               LEFT JOIN mem_edges e ON (e.src = n.id OR e.dst = n.id)
                                    AND (%(at)s::timestamptz IS NULL OR e.valid_from <= %(at)s)
               WHERE %(at)s::timestamptz IS NULL OR n.first_seen <= %(at)s
               GROUP BY n.id ORDER BY degree DESC, n.id LIMIT %(limit)s""",
            {"at": at, "limit": limit},
        ).fetchall()
        ids = [n["id"] for n in nodes]
        edges = conn.execute(
            """SELECT id, src, dst, relation, valid_from, valid_to, report_id FROM mem_edges
               WHERE src = ANY(%(ids)s) AND dst = ANY(%(ids)s)
                 AND (%(at)s::timestamptz IS NULL OR valid_from <= %(at)s)""",
            {"ids": ids, "at": at},
        ).fetchall()
        alerts = _store_contradictions(conn)
    return {
        "nodes": [{"id": n["id"], "type": n["type"], "label": n["display"], "first_seen": n["first_seen"],
                   "last_seen": n["last_seen"], "report_count": n["report_count"]} for n in nodes],
        "edges": [{"id": f"e-{e['id']}", "source": e["src"], "target": e["dst"], "relation": e["relation"],
                   "valid_from": e["valid_from"], "valid_to": e["valid_to"], "report_id": e["report_id"]}
                  for e in edges],
        "alerts": alerts,
    }
