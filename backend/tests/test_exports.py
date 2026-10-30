"""Tests for STIX and Navigator export modules. Owner: Backend Core."""
from app.exports.navigator import build_navigator_layer
from app.exports.stix import build_stix_bundle
from app.mocks import sample_analysis


def test_stix_export_structure():
    analysis = sample_analysis()
    bundle = build_stix_bundle(analysis)

    assert bundle["type"] == "bundle"
    assert "objects" in bundle
    objects = bundle["objects"]

    types = {obj["type"] for obj in objects}
    assert "identity" in types
    assert "report" in types
    assert "indicator" in types
    assert "attack-pattern" in types

    # Check that predictions are NOT in attack-patterns
    observed_tids = {t.technique_id for t in analysis.techniques if t.status == "accepted"}
    exported_ap_ids = [
        ref["external_id"]
        for obj in objects if obj["type"] == "attack-pattern"
        for ref in obj.get("external_references", [])
        if ref.get("source_name") == "mitre-attack"
    ]
    for tid in exported_ap_ids:
        assert tid in observed_tids

    # Check report references
    report_obj = next(obj for obj in objects if obj["type"] == "report")
    assert len(report_obj["object_refs"]) > 0


def test_navigator_layer_structure():
    analysis = sample_analysis()

    # Without predictions
    layer = build_navigator_layer(analysis, include_predicted=False)
    assert layer["domain"] == "enterprise-attack"
    assert layer["versions"]["attack"] == "20"
    assert layer["versions"]["layer"] == "4.5"
    assert "techniques" in layer
    assert len(layer["techniques"]) > 0

    for t in layer["techniques"]:
        assert "techniqueID" in t
        assert "tactic" in t
        assert 0 <= t["score"] <= 100
        assert "comment" in t
        assert t["enabled"] is True

    # With predictions
    layer_pred = build_navigator_layer(analysis, include_predicted=True)
    assert len(layer_pred["techniques"]) > len(layer["techniques"])
    predicted_entries = [t for t in layer_pred["techniques"] if t.get("color") == "#a78bfa"]
    assert len(predicted_entries) > 0

