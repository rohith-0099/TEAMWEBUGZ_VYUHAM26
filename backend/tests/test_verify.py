import pytest

from app.llm import LLMError
from app.mocks import SAMPLE_TEXT
from app.models import IOC, Behaviour, Candidate, Evidence
from app.pipeline import verify
from app.pipeline.verify import _Match, _Out, _Rej

TEXT = ("The actors sent spearphishing emails with malicious attachments. "
        "The loader ran an encoded PowerShell command on each host.")
QUOTE = "ran an encoded PowerShell command"


def ev(quote):
    start = TEXT.index(quote)
    return Evidence(quote=quote, start=start, end=start + len(quote))


BEHAVIOUR = Behaviour(id="b-1", summary="Runs PowerShell", evidence=ev(QUOTE))
CANDIDATES = {"b-1": [Candidate(technique_id="T1059.001", name="PowerShell", score=0.9),
                      Candidate(technique_id="T1059", name="Interpreter", score=0.8)]}
IOCS = [IOC(id="ioc-1", type="domain", value="a.example", display="a[.]example")]


def match(tid="T1059.001", confidence=0.9, quote=QUOTE, **kw):
    return _Match(technique_id=tid, confidence=confidence, evidence_quote=quote, rationale="fits", **kw)


@pytest.fixture
def answer(monkeypatch, fake_store, llm_on):
    """Sets what the fake model returns."""
    box = {}

    async def complete_json(system, user, schema, model="extract", **kw):
        assert model == "verify" and "untrusted" in system
        box["user"] = user
        if isinstance(box["out"], Exception):
            raise box["out"]
        return box["out"]

    monkeypatch.setattr(verify, "complete_json", complete_json)
    return lambda out: box.update(out=out) or box


async def run(explicit=(), behaviours=(BEHAVIOUR,), candidates=CANDIDATES, on_result=None):
    return await verify.verify_all(TEXT, list(behaviours), candidates, IOCS, list(explicit), on_result)


async def test_good_match_is_accepted_with_source_evidence(answer):
    answer(_Out(matches=[match(linked_ioc_ids=["ioc-1"])]))
    [t] = await run()
    assert t.status == "accepted" and t.technique_id == "T1059.001" and t.behaviour_id == "b-1"
    assert TEXT[t.evidence.start:t.evidence.end] == t.evidence.quote
    assert t.confidence.mapping == 0.9 and t.confidence.extraction == 1.0
    assert t.tactics == ["execution"] and t.url and t.linked_iocs == ["ioc-1"]


async def test_hallucinated_id_is_rejected(answer):
    answer(_Out(matches=[match("T9999")]))
    [t] = await run()
    assert (t.status, t.reject_reason) == ("rejected", "id_not_in_v20")


async def test_fabricated_quote_is_rejected_with_no_evidence(answer):
    answer(_Out(matches=[match(quote="the operators deleted all shadow copies")]))
    [t] = await run()
    assert (t.status, t.reject_reason) == ("rejected", "quote_not_in_source")
    assert t.evidence is None


async def test_deprecated_id_is_rejected(answer):
    answer(_Out(matches=[match("T1064")]))
    [t] = await run()
    assert (t.status, t.reject_reason) == ("rejected", "deprecated")


async def test_confidence_can_never_be_inflated_past_the_threshold_rule(answer):
    answer(_Out(matches=[match(confidence=0.59)]))
    [t] = await run()
    assert (t.status, t.reject_reason) == ("rejected", "low_confidence")


async def test_id_outside_candidates_is_discounted(answer):
    answer(_Out(matches=[match("T1486", confidence=0.9)]))
    [t] = await run()
    assert t.status == "accepted" and t.confidence.mapping == pytest.approx(0.72)
    assert t.rationale.startswith("(outside retrieved candidates)")


async def test_discount_can_push_a_match_below_the_threshold(answer):
    answer(_Out(matches=[match("T1486", confidence=0.7)]))
    [t] = await run()
    assert t.reject_reason == "low_confidence"


async def test_fuzzy_quote_is_discounted(answer, monkeypatch):
    monkeypatch.setattr(verify, "find_quote", lambda text, q, near=None: (ev(QUOTE), "fuzzy"))
    answer(_Out(matches=[match(confidence=0.9)]))
    [t] = await run()
    assert t.confidence.mapping == pytest.approx(0.81) and t.confidence.extraction == 0.9


async def test_unknown_ioc_links_are_dropped(answer):
    answer(_Out(matches=[match(linked_ioc_ids=["ioc-1", "ioc-404", "ioc-1"])]))
    [t] = await run()
    assert t.linked_iocs == ["ioc-1"]


async def test_one_entry_per_technique_and_behaviour(answer):
    answer(_Out(matches=[match(confidence=0.7), match(confidence=0.95)]))
    [t] = await run()
    assert t.confidence.mapping == 0.95


async def test_model_rejections_keep_the_top_three_by_retrieval_score(answer):
    many = [Candidate(technique_id=t, name=t, score=s) for t, s in
            [("T1059", 0.9), ("T1059.001", 0.8), ("T1486", 0.7), ("T1490", 0.6)]]
    answer(_Out(matches=[], rejected=[_Rej(technique_id=c.technique_id, reason="no") for c in reversed(many)]
                + [_Rej(technique_id="T1566.001", reason="not a candidate")]))
    results = await run(candidates={"b-1": many})
    assert [t.technique_id for t in results] == ["T1059", "T1059.001", "T1486"]
    assert all(t.reject_reason == "verifier_mismatch" and t.rationale == "no" for t in results)


async def test_rejection_of_an_accepted_id_is_ignored(answer):
    answer(_Out(matches=[match()], rejected=[_Rej(technique_id="T1059.001", reason="contradiction")]))
    [t] = await run()
    assert t.status == "accepted"


async def test_injected_explicit_id_is_rejected_without_asking_the_model(answer):
    box = answer(_Out(matches=[]))
    results = await run(explicit=[("T9999", ev(QUOTE))], behaviours=(), candidates={})
    assert [(t.technique_id, t.reject_reason) for t in results] == [("T9999", "id_not_in_v20")]
    assert "user" not in box


async def test_deprecated_explicit_id_is_rejected(answer):
    answer(_Out(matches=[]))
    results = await run(explicit=[("T1064", ev(QUOTE))], behaviours=(), candidates={})
    assert [t.reject_reason for t in results] == ["deprecated"]


async def test_explicit_id_near_a_behaviour_becomes_a_candidate(answer):
    box = answer(_Out(matches=[]))
    await run(explicit=[("T1486", ev(QUOTE))])
    assert "T1486 Data Encrypted for Impact" in box["user"]


async def test_lonely_explicit_id_is_verified_from_its_sentence(answer):
    answer(_Out(matches=[match("T1486", quote="sent spearphishing emails")]))
    [t] = await run(explicit=[("T1486", ev("sent spearphishing emails"))], behaviours=(), candidates={})
    assert t.status == "accepted" and t.behaviour_id is None


async def test_on_result_sees_every_result(answer):
    answer(_Out(matches=[match(), match("T9999")]))
    seen = []

    async def on_result(t):
        seen.append(t)

    assert await run(on_result=on_result) == seen and len(seen) == 2


async def test_one_failed_call_does_not_lose_the_others(answer, monkeypatch):
    second = Behaviour(id="b-2", summary="Phishes", evidence=ev("sent spearphishing emails"))
    good = _Out(matches=[match()])

    async def complete_json(system, user, schema, model="extract", **kw):
        if "Phishes" in user:
            raise LLMError("flaky")
        return good

    monkeypatch.setattr(verify, "complete_json", complete_json)
    candidates = {**CANDIDATES, "b-2": CANDIDATES["b-1"]}
    results = await run(behaviours=(BEHAVIOUR, second), candidates=candidates)
    assert [t.behaviour_id for t in results] == ["b-1"]


async def test_all_calls_failing_is_a_pipeline_error(answer):
    answer(LLMError("down"))
    with pytest.raises(LLMError, match="All 1 verifier calls failed"):
        await run()


async def test_offline_mode_serves_the_sample(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    results = await verify.verify_all(SAMPLE_TEXT, [], {}, [], [])
    assert sum(t.status == "accepted" for t in results) == 8


async def test_offline_mode_never_serves_quotes_missing_from_the_report(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_api_key", "")
    results = await verify.verify_all("A report about something else entirely.", [], {}, [], [])
    assert all(t.evidence is None and t.status == "rejected" for t in results)
