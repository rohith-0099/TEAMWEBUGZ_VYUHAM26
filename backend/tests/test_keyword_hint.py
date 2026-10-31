"""The T1190 hint is a project rule: labelled as such, modest, and never able to skip the verifier."""
import pytest

from app.models import Behaviour, Candidate, Evidence
from app.pipeline import retrieve, verify
from app.pipeline.verify import _BatchOut, _Item, _Match, _Rej

QUOTE = "The loader ran an encoded PowerShell command on each host."
BEHAVIOUR = Behaviour(id="b-1", summary="Runs PowerShell", evidence=Evidence(quote=QUOTE, start=0, end=len(QUOTE)))
HINTED = {"b-1": [*[Candidate(technique_id=f"T1059.00{i}", name="x", score=0.9) for i in range(1, 7)],
                  Candidate(technique_id="T1486", name="Encrypt", score=0.6, source="keyword_hint")]}


@pytest.fixture
def answer(monkeypatch, fake_store, llm_on):
    box = {}

    async def complete_json(system, user, schema, model="extract", **kw):
        box["user"] = user
        return _BatchOut(results=[box["out"]])

    monkeypatch.setattr(verify, "complete_json", complete_json)
    return lambda out: box.update(out=out) or box


async def run():
    return await verify.verify_all(QUOTE, [BEHAVIOUR], HINTED, [], [])


def test_t1190_hint_is_a_modest_keyword_hint(monkeypatch):
    monkeypatch.setattr(retrieve, "get_technique", lambda tid: {"name": "Exploit Public-Facing Application"})
    quote = "exploited the PHP-CGI flaw"
    behaviour = Behaviour(id="b", summary=quote, evidence=Evidence(quote=quote, start=0, end=len(quote)))
    [hint] = retrieve._add_public_facing_hint(behaviour, [])
    assert (hint.technique_id, hint.source) == ("T1190", "keyword_hint") and hint.score <= 0.6


async def test_hint_survives_the_cap_despite_its_modest_score(answer):
    box = answer(_Item(behaviour_id="b-1"))
    await run()
    assert "T1486 Data Encrypted for Impact" in box["user"]


async def test_hint_is_labelled_when_accepted(answer):
    answer(_Item(behaviour_id="b-1", matches=[_Match(technique_id="T1486", confidence=0.9, evidence_quote=QUOTE,
                                                     rationale="fits")]))
    [t] = await run()
    assert t.status == "accepted" and t.rationale == f"{verify.HINT_LABEL} fits"


async def test_hint_is_labelled_when_rejected(answer):
    answer(_Item(behaviour_id="b-1", rejected=[_Rej(technique_id="T1486", reason="no")]))
    [t] = await run()
    assert t.status == "rejected" and t.rationale == f"{verify.HINT_LABEL} no"
