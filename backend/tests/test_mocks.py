"""The sample analysis is what teammates build against, so it must honour the contracts."""
from app.mocks import SAMPLE_TEXT, sample_analysis
from app.models import Evidence, ReportAnalysis


def _all_evidence(a: ReportAnalysis) -> list[Evidence]:
    found = [e for i in a.iocs for e in i.evidence]
    found += [b.evidence for b in a.behaviours]
    found += [t.evidence for t in a.techniques + a.predictions if t.evidence]
    found += [f.evidence for f in a.injection_flags if f.evidence]
    found += [m.evidence for m in a.migrations if m.evidence]
    return found


def test_model_round_trips_through_json():
    a = sample_analysis()
    assert ReportAnalysis.model_validate_json(a.model_dump_json()) == a


def test_evidence_offsets_are_exact():
    a = sample_analysis()
    evidence = _all_evidence(a)
    assert len(evidence) >= 25
    for e in evidence:
        assert a.text[e.start:e.end] == e.quote


def test_expected_counts():
    a = sample_analysis()
    assert 2300 <= len(SAMPLE_TEXT) <= 2900
    assert len(a.iocs) == 10
    assert sum(1 for i in a.iocs if i.filtered_reason) == 2
    assert len(a.behaviours) == 8
    assert sum(1 for t in a.techniques if t.status == "accepted") == 8
    assert sum(1 for t in a.techniques if t.status == "rejected") == 5
    assert len(a.predictions) == 3
    assert {n.kind for n in a.flow.nodes} == {"observed", "predicted", "unknown"}
    assert len(a.detections) == 3
    assert all(len(d.sigma) == 1 for d in a.detections)
    assert len(a.memory_alerts) == 2
    assert len(a.migrations) == 1


def test_accepted_observed_techniques_have_evidence():
    for t in sample_analysis().techniques:
        if t.status == "accepted":
            assert t.evidence is not None


def test_filtered_iocs_are_defanged():
    for i in sample_analysis().iocs:
        if i.filtered_reason:
            assert "[.]" in i.display and i.display != i.value


def test_flow_edges_reference_real_nodes():
    flow = sample_analysis().flow
    ids = {n.id for n in flow.nodes}
    assert all(e.source in ids and e.target in ids for e in flow.edges)


def test_links_are_consistent_in_both_directions():
    a = sample_analysis()
    iocs = {i.id: i for i in a.iocs}
    for t in a.techniques:
        for ioc_id in t.linked_iocs:
            assert t.technique_id in iocs[ioc_id].linked_techniques
