"""The whole graph with the LLM path switched on, using a scripted provider."""
import json
from types import SimpleNamespace

import litellm
import psycopg
import pytest

from app import db, events, llm
from app.mocks import SAMPLE_TEXT, sample_analysis
from app.models import Candidate
from app.pipeline import graph, runner
from app.pipeline.ingest import IngestResult

GOOD_RULE = """title: Beacon
status: experimental
logsource:
  category: proxy
detection:
  selection:
    c-uri|contains: gate
  condition: selection
level: high
"""


def _reply(system: str, user: str) -> str:
    if "verify mappings" in system:
        if "Runs PowerShell" not in user:
            return json.dumps({"matches": []})
        return json.dumps({"matches": [
            {"technique_id": "T1059.001", "confidence": 0.9, "rationale": "fits",
             "evidence_quote": "launched an encoded PowerShell command"},
            {"technique_id": "T1234.999", "confidence": 0.99, "rationale": "invented",
             "evidence_quote": "launched an encoded PowerShell command"},
            {"technique_id": "T1486", "confidence": 0.95, "rationale": "invented quote",
             "evidence_quote": "the operators wiped every domain controller"},
        ]})
    if "prompt-injection" in system:
        return json.dumps({"injection": False})
    return json.dumps({"sigma_yaml": GOOD_RULE})


@pytest.fixture
def scripted(monkeypatch, fake_store, llm_on):
    try:
        db.init_db()
    except psycopg.OperationalError:
        pytest.skip("Postgres is not reachable")

    async def acompletion(model, messages, **kwargs):
        content = _reply(messages[0]["content"], messages[1]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)

    monkeypatch.setattr(litellm, "acompletion", acompletion)
    monkeypatch.setattr(llm, "_cache_get", lambda key: None)
    monkeypatch.setattr(llm, "_cache_put", lambda key, value: None)

    # Teammates' stages are pinned to the sample, so this stays valid as their stubs get replaced.
    sample = sample_analysis()

    async def ingest(**kwargs):
        return IngestResult(title="Pipeline test", source_url=None, published_at=None, raw_text=SAMPLE_TEXT,
                            text=SAMPLE_TEXT, publisher_domain=None, references=[])

    async def extract_behaviours(text, on_behaviour=None):
        b = sample.behaviours[1].model_copy(update={"summary": "Runs PowerShell"})
        await on_behaviour(b)
        return [b]

    async def label_roles(text, iocs):
        return iocs

    monkeypatch.setattr(graph, "ingest", ingest)
    monkeypatch.setattr(graph, "extract_iocs", lambda text, domain: sample.iocs)
    monkeypatch.setattr(graph, "label_roles", label_roles)
    monkeypatch.setattr(graph, "extract_behaviours", extract_behaviours)
    candidate = Candidate(technique_id="T1059.001", name="PowerShell", score=0.9)
    monkeypatch.setattr(graph, "retrieve_candidates", lambda behaviours: {b.id: [candidate] for b in behaviours})
    monkeypatch.setattr(graph, "explicit_ids", lambda text: [("T9999", sample.techniques[8].evidence)])
    monkeypatch.setattr(graph, "link_iocs", lambda iocs, techniques, text: (iocs, techniques))
    monkeypatch.setattr(graph, "migrate", lambda text, techniques: [])


async def test_hallucinations_never_reach_accepted(scripted):
    analysis_id = await runner.start_analysis(None, "text", None, None, None)
    stream = [e async for e in events.event_stream(analysis_id)]

    assert stream[-1]["stage"] == "pipeline" and stream[-1]["status"] == "done", stream[-1]
    assert not [e for e in stream if e["status"] == "error"]
    assert {e["stage"] for e in stream if e["status"] == "done"} >= {
        "ingest", "guard", "ioc", "ioc_role", "behaviours", "retrieve", "verify", "link", "migrate",
        "tie", "flow", "detect", "memory", "export"}

    a = db.get_analysis(analysis_id)
    outcome = {t.technique_id: (t.status, t.reject_reason) for t in a.techniques}
    assert outcome == {
        "T1059.001": ("accepted", None),
        "T1234.999": ("rejected", "id_not_in_v20"),
        "T1486": ("rejected", "quote_not_in_source"),
        "T9999": ("rejected", "id_not_in_v20"),
    }
    for t in a.techniques:
        if t.status == "accepted":
            assert a.text[t.evidence.start:t.evidence.end] == t.evidence.quote
    assert any(f.pattern == "ignore_instructions" and f.severity == "high" for f in a.injection_flags)
    assert [n.id for n in a.flow.nodes if n.kind == "observed"] == ["n-T1059.001"]
    assert sum(1 for e in stream if e["stage"] == "verify" and e["status"] == "progress") == 4

    detection = next(d for d in a.detections if d.technique_id == "T1059.001")
    assert detection.technique_name == "PowerShell"

    with db.pool.connection() as conn:
        conn.execute("DELETE FROM analyses WHERE id=%s", (analysis_id,))
        conn.execute("DELETE FROM mem_nodes WHERE key=%s", (analysis_id,))
