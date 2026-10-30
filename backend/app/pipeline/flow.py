"""Attack flow builder. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 6.

Deterministic and explainable. A stage is one column of nodes: nodes in the same stage are
alternatives, and every node connects to every node of the next stage, which is what makes
the simulator's path counts meaningful.
"""
from app.attack import store
from app.models import AttackFlow, FlowEdge, FlowNode, TechniqueMatch

# Tactics worth calling out as a gap when a report skips them (contracts: never tactic *order*).
GAP_TACTICS = {"initial-access", "execution", "persistence", "privilege-escalation",
               "credential-access", "discovery", "lateral-movement", "collection",
               "command-and-control", "exfiltration"}


def _primary_tactic(tactics: list[str], order: dict[str, int]) -> str:
    return min(tactics, key=lambda t: order.get(t, len(order)), default="unknown")


def _observed(techniques: list[TechniqueMatch]) -> dict[str, TechniqueMatch]:
    """Unique accepted techniques, each kept at its earliest evidence."""
    first: dict[str, TechniqueMatch] = {}
    for t in techniques:
        if t.status != "accepted" or t.origin != "observed" or t.evidence is None:
            continue
        current = first.get(t.technique_id)
        if current is None or t.evidence.start < current.evidence.start:
            first[t.technique_id] = t
    return first


def build_flow(techniques: list[TechniqueMatch], predictions: list[TechniqueMatch]) -> AttackFlow:
    order = store.tactic_order()
    rank = lambda tactic: order.get(tactic, len(order))  # noqa: E731
    observed = _observed(techniques)

    grouped: dict[str, list[TechniqueMatch]] = {}
    for t in observed.values():
        grouped.setdefault(_primary_tactic(t.tactics, order), []).append(t)
    if not grouped:
        return AttackFlow()

    first_rank, last_rank = min(map(rank, grouped)), max(map(rank, grouped))
    gaps = [tactic for tactic in order
            if tactic in GAP_TACTICS and tactic not in grouped and first_rank < rank(tactic) < last_rank]

    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []
    stages: list[tuple[str, list[FlowNode]]] = []
    for index, tactic in enumerate(sorted([*grouped, *gaps], key=rank)):
        if tactic in grouped:
            members = sorted(grouped[tactic], key=lambda t: t.evidence.start)
            column = [FlowNode(id=f"n-{t.technique_id}", kind="observed", technique_id=t.technique_id,
                               tactic=tactic, label=f"{t.technique_id} {t.name}",
                               order=index * 100 + position)
                      for position, t in enumerate(members)]
        else:
            column = [FlowNode(id=f"u-{tactic}", kind="unknown", tactic=tactic,
                               label=f"{store.tactic_name(tactic)}: not established in report",
                               order=index * 100)]
        stages.append((tactic, column))
        nodes += column

    for (_, left), (_, right) in zip(stages, stages[1:]):
        edges += [FlowEdge(source=a.id, target=b.id, relation="followed_by") for a in left for b in right]

    # Predicted nodes sit in their tactic's column (or between columns) and are never
    # part of the path graph: the simulator ignores them.
    extra_in_stage: dict[int, int] = {}
    for p in predictions:
        if p.technique_id in observed:
            continue
        tactic = _primary_tactic(p.tactics, order)
        index = sum(1 for name, _ in stages if rank(name) <= rank(tactic)) - 1
        offset = 50 if index < 0 or stages[index][0] != tactic else len(stages[index][1])
        offset += extra_in_stage.get(index, 0)
        extra_in_stage[index] = extra_in_stage.get(index, 0) + 1
        nodes.append(FlowNode(id=f"p-{p.technique_id}", kind="predicted", technique_id=p.technique_id,
                              tactic=tactic, label=f"{p.technique_id} {p.name}",
                              order=max(0, index * 100 + offset)))
        previous = next((column for name, column in reversed(stages)
                         if rank(name) < rank(tactic) and any(n.kind == "observed" for n in column)), [])
        edges += [FlowEdge(source=n.id, target=f"p-{p.technique_id}", relation="followed_by")
                  for n in previous if n.kind == "observed"]
    return AttackFlow(nodes=nodes, edges=edges)
