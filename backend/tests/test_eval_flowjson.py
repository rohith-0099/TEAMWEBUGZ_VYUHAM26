from datetime import datetime, timezone

import pytest

from app.eval.metrics import micro_average, score_report, strip_leakage
from app.exports.flow_json import EXTENSION_ID, attack_flow_json
from app.models import Evidence, ReportAnalysis, TechniqueMatch
from app.pipeline.flow import build_flow


def test_strip_leakage_removes_tables_and_every_id():
    text = ("Tactic | Technique | ID\n| Execution | PowerShell | T1059.001 |\n"
            "The actors used T1059.001 and TA0002 in a long sentence that keeps its other words. " + "x" * 200 +
            "\nNo identifiers on this line.")
    out = strip_leakage(text)
    assert "T1059" not in out and "TA0002" not in out and "PowerShell" not in out
    assert "No identifiers on this line." in out and "keeps its other words" in out


def test_score_report():
    assert score_report({"T1", "T2"}, {"T2", "T3"}) == {"tp": ["T2"], "fp": ["T3"], "fn": ["T1"]}


def test_micro_average_pools_counts_across_reports():
    scores = micro_average([({"T1", "T2"}, {"T1"}), ({"T3"}, {"T3", "T4"})])
    assert scores["precision"] == pytest.approx(2 / 3) and scores["recall"] == pytest.approx(2 / 3)
    assert scores["f1"] == pytest.approx(2 / 3)


def test_parent_f1_forgives_the_wrong_sub_technique():
    scores = micro_average([({"T1059.001"}, {"T1059.003"})])
    assert scores["f1"] == 0 and scores["parent_f1"] == 1


def test_empty_scores_are_zero_not_a_crash():
    assert micro_average([(set(), set())])["f1"] == 0


def _analysis():
    techniques = [
        TechniqueMatch(technique_id="T1566.001", name="Phish", tactics=["initial-access"], status="accepted",
                       evidence=Evidence(quote="sent emails", start=0, end=11)),
        TechniqueMatch(technique_id="T1486", name="Encrypt", tactics=["impact"], status="accepted",
                       evidence=Evidence(quote="encrypted", start=20, end=29)),
    ]
    prediction = TechniqueMatch(technique_id="T1490", name="Recovery", tactics=["impact"], status="accepted",
                                origin="predicted")
    return ReportAnalysis(report_id="r1", title="Report", source_url="https://intel.example/r",
                          created_at=datetime(2026, 10, 30, tzinfo=timezone.utc), techniques=techniques,
                          flow=build_flow(techniques, [prediction]))


def test_attack_flow_structure(fake_store):
    bundle = attack_flow_json(_analysis())
    by_type = {}
    for o in bundle["objects"]:
        by_type.setdefault(o["type"], []).append(o)
    assert by_type["extension-definition"][0]["id"] == EXTENSION_ID
    [flow] = by_type["attack-flow"]
    actions = {a["id"]: a for a in by_type["attack-action"]}
    assert flow["extensions"][EXTENSION_ID]["extension_type"] == "new-sdo"

    # start_refs + effect_refs must walk every action, in contract order
    first = actions[flow["start_refs"][0]]
    assert first["technique_id"] == "T1566.001" and first["tactic_id"] and first["description"] == "sent emails"
    assert any(a.get("description") == "not established in report" and "technique_id" not in a
               for a in actions.values())
    assert all(ref in actions for a in actions.values() for ref in a.get("effect_refs", []))


def test_predictions_are_never_exported(fake_store):
    assert "T1490" not in str(attack_flow_json(_analysis()))


def test_export_is_stable(fake_store):
    analysis = _analysis()
    assert attack_flow_json(analysis) == attack_flow_json(analysis)
