"""Disruption simulator. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 8."""
from itertools import islice

import networkx as nx

from app.attack import store
from app.models import ReportAnalysis

MAX_SHOWN_PATHS = 20


def _path_graph(analysis: ReportAnalysis) -> tuple[nx.DiGraph, set[str], set[str]]:
    """Observed + unknown nodes, plus the first-stage entries and last-stage goals."""
    nodes = [n for n in analysis.flow.nodes if n.kind != "predicted"]
    graph = nx.DiGraph()
    graph.add_nodes_from(n.id for n in nodes)
    graph.add_edges_from((e.source, e.target) for e in analysis.flow.edges
                         if e.source in graph and e.target in graph)
    if not nodes:
        return graph, set(), set()
    stages = [n.order // 100 for n in nodes]
    entries = {n.id for n, s in zip(nodes, stages) if s == min(stages)}
    goals = {n.id for n, s in zip(nodes, stages) if s == max(stages)}
    return graph, entries, goals


def _count_paths(graph: nx.DiGraph, entries: set[str], goals: set[str]) -> int:
    """Dynamic programming over the DAG: exact, with no enumeration limit."""
    paths: dict[str, int] = {}
    for node in nx.topological_sort(graph):
        paths[node] = (1 if node in entries else 0) + sum(paths[p] for p in graph.predecessors(node))
    return sum(paths[g] for g in goals)


def simulate(analysis: ReportAnalysis, blocked_node_ids: list[str]) -> dict:
    """SimulateResponse. Only observed nodes can be blocked; other ids are ignored."""
    graph, entries, goals = _path_graph(analysis)
    kinds = {n.id: n for n in analysis.flow.nodes}
    blocked = [i for i in dict.fromkeys(blocked_node_ids)
               if i in graph and kinds[i].kind == "observed"]

    total = _count_paths(graph, entries, goals)
    remaining = graph.copy()
    remaining.remove_nodes_from(blocked)
    live_entries, live_goals = entries & set(remaining), goals & set(remaining)
    surviving = _count_paths(remaining, live_entries, live_goals)
    broken = total - surviving

    reachable, can_finish = set(live_entries), set(live_goals)
    for node in live_entries:
        reachable |= nx.descendants(remaining, node)
    for node in live_goals:
        can_finish |= nx.ancestors(remaining, node)

    shown: list[list[str]] = []
    if live_goals:
        for entry in sorted(live_entries):
            if entry in live_goals:
                shown.append([entry])
                continue
            shown += islice(nx.all_simple_paths(remaining, entry, live_goals), MAX_SHOWN_PATHS - len(shown))
            if len(shown) >= MAX_SHOWN_PATHS:
                break

    countermeasures = [
        {"technique_id": kinds[i].technique_id, "id": m["id"], "name": m["name"],
         "source": "attack_mitigation", "derived": False, "url": m.get("url")}
        for i in blocked for m in store.get_mitigations(kinds[i].technique_id)
    ]
    response = {
        "total_paths": total, "broken_paths": broken,
        "broken_pct": 100.0 * broken / total if total else 0.0,
        "surviving_paths": shown,
        "affected_node_ids": sorted(n for n in remaining if n not in reachable or n not in can_finish),
        "countermeasures": countermeasures,
    }
    if surviving > len(shown):
        response["note"] = f"showing {len(shown)} of {surviving} surviving paths"
    return response


def best_single_block(analysis: ReportAnalysis) -> dict | None:
    """The observed node whose removal breaks the most paths: {node_id, broken_pct}."""
    best = None
    for node in analysis.flow.nodes:
        if node.kind == "observed":
            pct = simulate(analysis, [node.id])["broken_pct"]
            if best is None or pct > best["broken_pct"]:
                best = {"node_id": node.id, "broken_pct": pct}
    return best
