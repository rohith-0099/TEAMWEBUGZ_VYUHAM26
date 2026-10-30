from app.models import Evidence, TechniqueMatch
from app.pipeline.flow import build_flow


def t(tid, tactics, start=0, status="accepted", origin="observed"):
    evidence = Evidence(quote="q", start=start, end=start + 1) if origin == "observed" else None
    return TechniqueMatch(technique_id=tid, name=tid, tactics=tactics, status=status, origin=origin,
                          evidence=evidence)


def test_no_techniques_gives_an_empty_flow(fake_store):
    assert build_flow([], []).nodes == []


def test_rejected_techniques_are_left_out(fake_store):
    assert build_flow([t("T9999", ["execution"], status="rejected")], []).nodes == []


def test_primary_tactic_is_the_earliest_one(fake_store):
    [node] = build_flow([t("T1547.001", ["privilege-escalation", "persistence"])], []).nodes
    assert node.tactic == "persistence" and node.id == "n-T1547.001"


def test_gaps_only_between_first_and_last_stage(fake_store):
    flow = build_flow([t("T1", ["persistence"]), t("T2", ["lateral-movement"])], [])
    assert [n.id for n in flow.nodes if n.kind == "unknown"] == [
        "u-privilege-escalation", "u-credential-access", "u-discovery"]


def test_tactics_outside_the_gap_list_are_never_gaps(fake_store):
    flow = build_flow([t("T1", ["persistence"]), t("T2", ["credential-access"])], [])
    assert not any(n.tactic in ("stealth", "defense-impairment") for n in flow.nodes)


def test_stages_connect_all_to_all_and_stay_ordered(fake_store):
    flow = build_flow([t("T2", ["execution"], 50), t("T1", ["execution"], 10), t("T3", ["persistence"], 90)], [])
    assert [n.id for n in flow.nodes] == ["n-T1", "n-T2", "n-T3"]
    assert [n.order for n in flow.nodes] == [0, 1, 100]
    assert {(e.source, e.target) for e in flow.edges} == {("n-T1", "n-T3"), ("n-T2", "n-T3")}


def test_duplicate_technique_keeps_one_node_at_first_evidence(fake_store):
    flow = build_flow([t("T1", ["execution"], 80), t("T1", ["execution"], 5)], [])
    assert len(flow.nodes) == 1


def test_predicted_node_joins_its_column_and_hangs_off_the_previous_observed_stage(fake_store):
    flow = build_flow([t("T1", ["execution"]), t("T2", ["impact"])],
                      [t("T3", ["impact"], origin="predicted")])
    predicted = next(n for n in flow.nodes if n.kind == "predicted")
    observed = next(n for n in flow.nodes if n.id == "n-T2")
    assert predicted.id == "p-T3" and predicted.order // 100 == observed.order // 100
    assert {(e.source, e.target) for e in flow.edges if e.target == "p-T3"} == {("n-T1", "p-T3")}


def test_predicted_tactic_with_no_column_sits_between_columns(fake_store):
    flow = build_flow([t("T1", ["persistence"]), t("T2", ["credential-access"])],
                      [t("T3", ["stealth"], origin="predicted")])
    predicted = next(n for n in flow.nodes if n.kind == "predicted")
    assert predicted.order % 100 == 50  # stealth has no column, so it sits between two
    assert any(e.target == predicted.id and e.source == "n-T1" for e in flow.edges)


def test_prediction_already_observed_is_skipped(fake_store):
    flow = build_flow([t("T1", ["execution"])], [t("T1", ["execution"], origin="predicted")])
    assert [n.id for n in flow.nodes] == ["n-T1"]
