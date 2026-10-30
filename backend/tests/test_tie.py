import pytest

from app.attack import store
from app.pipeline.tie import predict


@pytest.fixture
def sets(fake_store, monkeypatch):
    def setter(value):
        monkeypatch.setattr(store, "get_technique_sets", lambda: value)
    return setter


def test_nothing_observed_predicts_nothing(sets):
    sets([{"T1486", "T1490"}])
    assert predict([]) == []


def test_co_occurring_technique_is_predicted(sets):
    sets([{"T1486", "T1490"}, {"T1486", "T1490", "T1562.001"}, {"T1566.001", "T1059.001"}])
    results = predict(["T1486"])
    assert [r.technique_id for r in results] == ["T1490", "T1562.001"]
    top = results[0]
    assert top.origin == "predicted" and top.status == "accepted" and top.evidence is None
    assert top.prediction_score == 1.0 and "T1486" in top.rationale and "2 known" in top.rationale


def test_observed_are_excluded_and_parent_of_observed_is_not_predicted(sets):
    sets([{"T1059", "T1059.001", "T1486"}])
    assert [r.technique_id for r in predict(["T1059.001"])] == ["T1486"]


def test_sub_technique_matches_sets_at_parent_level(sets):
    sets([{"T1059", "T1486"}])
    assert [r.technique_id for r in predict(["T1059.001"])] == ["T1486"]


def test_ids_not_in_v20_are_never_predicted(sets):
    sets([{"T1486", "T9999", "T1490"}])
    assert "T9999" not in [r.technique_id for r in predict(["T1486"])]


def test_top_n_and_low_scores_are_cut(sets):
    sets([{"T1486", "T1490", "T1562.001"}] * 3)
    assert len(predict(["T1486"], top_n=1)) == 1
    weak = [{"T1486", "T1490"}] * 20 + [{"T1486", "T1562.001", *[f"T{i}" for i in range(2000, 2200)]}]
    sets(weak)
    assert [r.technique_id for r in predict(["T1486"])] == ["T1490"]
