import pytest

from app.models import AttackFlow, FlowEdge, FlowNode, ReportAnalysis
from app.pipeline.simulate import best_single_block, simulate


def analysis(columns, predicted=()):
    """columns: lists of (id, kind); consecutive columns are fully connected."""
    nodes, edges = [], []
    for index, column in enumerate(columns):
        for position, (node_id, kind) in enumerate(column):
            nodes.append(FlowNode(id=node_id, kind=kind, tactic="t", label=node_id,
                                  technique_id=node_id if kind == "observed" else None,
                                  order=index * 100 + position))
    for left, right in zip(columns, columns[1:]):
        edges += [FlowEdge(source=a, target=b, relation="followed_by") for a, _ in left for b, _ in right]
    for node_id, source in predicted:
        nodes.append(FlowNode(id=node_id, kind="predicted", tactic="t", label=node_id, order=150))
        edges.append(FlowEdge(source=source, target=node_id, relation="followed_by"))
    return ReportAnalysis(report_id="r", flow=AttackFlow(nodes=nodes, edges=edges))


O = "observed"
DIAMOND = [[("a", O)], [("b1", O), ("b2", O)], [("c1", O), ("c2", O), ("c3", O)], [("d", O)]]


def test_hand_count_on_a_diamond(fake_store):
    assert simulate(analysis(DIAMOND), [])["total_paths"] == 6  # 1 * 2 * 3 * 1


def test_blocking_one_of_two_alternatives_breaks_half(fake_store):
    result = simulate(analysis(DIAMOND), ["b1"])
    assert (result["broken_paths"], result["broken_pct"]) == (3, 50.0)
    assert len(result["surviving_paths"]) == 3 and all("b1" not in p for p in result["surviving_paths"])
    assert result["affected_node_ids"] == []


def test_blocking_both_alternatives_breaks_everything(fake_store):
    result = simulate(analysis(DIAMOND), ["b1", "b2"])
    assert result["broken_pct"] == 100.0 and result["surviving_paths"] == []
    assert result["affected_node_ids"] == ["a", "c1", "c2", "c3", "d"]


def test_blocking_the_entry_strands_everything_after_it(fake_store):
    result = simulate(analysis(DIAMOND), ["a"])
    assert result["broken_pct"] == 100.0 and "d" in result["affected_node_ids"]


def test_blocking_the_goal_strands_everything_before_it(fake_store):
    result = simulate(analysis(DIAMOND), ["d"])
    assert result["broken_pct"] == 100.0 and "a" in result["affected_node_ids"]


def test_nothing_blocked_breaks_nothing(fake_store):
    result = simulate(analysis(DIAMOND), [])
    assert (result["broken_paths"], result["broken_pct"], result["countermeasures"]) == (0, 0.0, [])


def test_unknown_and_missing_nodes_cannot_be_blocked(fake_store):
    flow = analysis([[("a", O)], [("gap", "unknown")], [("b", O)]])
    assert simulate(flow, ["gap", "nope"])["broken_paths"] == 0


def test_predicted_nodes_are_not_in_the_path_graph(fake_store):
    flow = analysis([[("a", O)], [("b", O)]], predicted=[("p", "a")])
    result = simulate(flow, ["p"])
    assert result["total_paths"] == 1 and result["broken_paths"] == 0
    assert all("p" not in path for path in result["surviving_paths"])


def test_empty_flow_is_safe(fake_store):
    result = simulate(ReportAnalysis(report_id="r"), [])
    assert (result["total_paths"], result["broken_pct"]) == (0, 0.0)


def test_large_flow_is_counted_exactly_and_capped_for_display(fake_store):
    wide = [[(f"n{c}-{i}", O) for i in range(5)] for c in range(8)]
    result = simulate(analysis(wide), [])
    assert result["total_paths"] == 5 ** 8
    assert len(result["surviving_paths"]) == 20 and "note" in result


def test_countermeasures_come_from_attack_mitigations(fake_store):
    [cm] = simulate(analysis(DIAMOND), ["b1"])["countermeasures"]
    assert cm["technique_id"] == "b1" and cm["source"] == "attack_mitigation" and cm["derived"] is False


def test_best_single_block_finds_the_chokepoint(fake_store):
    flow = analysis([[("x", O), ("y", O)], [("choke", O)], [("z", O), ("w", O)]])
    assert best_single_block(flow)["node_id"] == "choke"


@pytest.mark.parametrize("blocked", [["b1"], ["c1"], ["b1", "c2"]])
def test_broken_plus_surviving_equals_total(fake_store, blocked):
    result = simulate(analysis(DIAMOND), blocked)
    assert result["total_paths"] - result["broken_paths"] == len(result["surviving_paths"])
