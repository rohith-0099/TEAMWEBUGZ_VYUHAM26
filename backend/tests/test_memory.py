"""Runs against the real Postgres, because this module is mostly SQL."""
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

from app import db
from app.models import IOC, Confidence, Evidence, ReportAnalysis, TechniqueMatch
from app.pipeline import entities, memory

OLD = datetime(2025, 1, 1, tzinfo=timezone.utc)
NEW = datetime(2026, 10, 1, tzinfo=timezone.utc)


@pytest.fixture
def report(monkeypatch):
    try:
        db.init_db()
    except psycopg.OperationalError:
        pytest.skip("Postgres is not reachable")
    monkeypatch.setattr(memory, "find_known_entities", lambda text: [])
    created, value = [], f"{uuid4().hex[:10]}.example"

    def make(role="c2", published=NEW, value_override=None, text="body"):
        rid = f"test-{uuid4().hex[:10]}"
        db.create_analysis(rid, f"Report {rid}", None)
        created.append(rid)
        v = value_override or value
        evidence = Evidence(quote="q", start=0, end=1)
        return ReportAnalysis(
            report_id=rid, title=f"Report {rid}", published_at=published, text=text,
            iocs=[IOC(id="ioc-1", type="domain", value=v, display=v.replace(".", "[.]"), role=role,
                      evidence=[evidence])],
            techniques=[TechniqueMatch(technique_id="T1486", name="Encrypt", tactics=["impact"], status="accepted",
                                       evidence=evidence, confidence=Confidence(mapping=0.9)),
                        TechniqueMatch(technique_id="T9999", name="Fake", tactics=[], status="rejected")],
        )

    make.value = value
    yield make
    with db.pool.connection() as conn:
        conn.execute("DELETE FROM analyses WHERE id = ANY(%s)", (created,))
        conn.execute("DELETE FROM mem_nodes WHERE key = ANY(%s) OR id LIKE %s",
                     ([*created, f"domain:{value}"], f"%{value}%"))


async def test_first_sighting_raises_no_alert(report):
    assert await memory.write_memory(report()) == []


async def test_repeat_sighting_raises_seen_before(report):
    first = report()
    await memory.write_memory(first)
    [alert] = await memory.write_memory(report())
    assert alert.type == "seen_before" and "1 earlier report" in alert.message
    assert alert.reports[0].report_id == first.report_id and alert.reports[0].quote == "q"
    assert "[.]" in alert.entity_display


async def test_different_role_is_a_contradiction_explained_by_time(report):
    await memory.write_memory(report(role="victim", published=OLD))
    alerts = await memory.write_memory(report(role="c2", published=NEW))
    assert [a.type for a in alerts] == ["seen_before", "contradiction"]
    assert "Conflicting claims" in alerts[1].message and alerts[1].explained_by_time is True


async def test_close_in_time_contradiction_is_not_explained_by_time(report):
    await memory.write_memory(report(role="victim", published=NEW))
    alerts = await memory.write_memory(report(role="c2", published=NEW))
    assert alerts[1].explained_by_time is False


async def test_unknown_role_is_not_a_claim(report):
    await memory.write_memory(report(role="unknown"))
    assert [a.type for a in await memory.write_memory(report(role="c2"))] == ["seen_before"]


async def test_attribution_conflict(report, monkeypatch):
    actor = f"Actor-{uuid4().hex[:6]}"

    def entities_for(name):
        ev = Evidence(quote=name, start=0, end=len(name))
        return lambda text: [{"type": "actor", "key": name, "display": name, "evidence": ev, "mentions": [ev]}]

    monkeypatch.setattr(memory, "find_known_entities", entities_for(actor + "-a"))
    await memory.write_memory(report())
    monkeypatch.setattr(memory, "find_known_entities", entities_for(actor + "-b"))
    alerts = await memory.write_memory(report())
    assert alerts[-1].type == "contradiction" and "linked to" in alerts[-1].message
    assert "same actor" not in alerts[-1].message
    with db.pool.connection() as conn:
        conn.execute("DELETE FROM mem_edges WHERE src LIKE %s OR dst LIKE %s", (f"actor:{actor}%", f"actor:{actor}%"))
        conn.execute("DELETE FROM mem_nodes WHERE id LIKE %s", (f"actor:{actor}%",))


async def test_only_verified_output_is_written(report):
    r = report()
    await memory.write_memory(r)
    graph = memory.get_graph(None)
    ids = {n["id"] for n in graph["nodes"]}
    assert "technique:T1486" in ids and "technique:T9999" not in ids


async def test_filtered_iocs_are_not_written(report):
    r = report()
    r.iocs[0].filtered_reason = "benign_domain"
    await memory.write_memory(r)
    assert f"ioc:domain:{report.value}" not in {n["id"] for n in memory.get_graph(None)["nodes"]}


async def test_graph_time_travel_and_report_counts(report):
    await memory.write_memory(report(published=OLD))
    await memory.write_memory(report(published=NEW))
    node_id = f"ioc:domain:{report.value}"
    now = {n["id"]: n for n in memory.get_graph(None)["nodes"]}[node_id]
    assert now["report_count"] == 2 and now["first_seen"] == OLD and now["last_seen"] == NEW

    past = memory.get_graph(datetime(2025, 6, 1, tzinfo=timezone.utc))
    assert {n["id"]: n for n in past["nodes"]}[node_id]["report_count"] == 1
    assert all(e["valid_from"] <= datetime(2025, 6, 1, tzinfo=timezone.utc) for e in past["edges"])


async def test_graph_limit_and_store_wide_contradictions(report):
    await memory.write_memory(report(role="victim", published=OLD))
    await memory.write_memory(report(role="c2", published=NEW))
    graph = memory.get_graph(None)
    assert any(report.value.replace(".", "[.]") in a["entity_display"] for a in graph["alerts"])
    assert len(memory.get_graph(None, limit=1)["nodes"]) == 1


def test_entities_use_word_boundaries_and_case_rules(monkeypatch):
    import re
    patterns = [("actor", "APT29", [re.compile(r"(?<!\w)APT29(?!\w)")]),
                ("malware", "Emotet", [re.compile(r"(?<!\w)Emotet(?!\w)", re.IGNORECASE)])]
    monkeypatch.setattr(entities, "_load", lambda: patterns)
    text = "emotet was dropped by APT29, not by APT299."
    found = {e["key"]: e for e in entities.find_known_entities(text)}
    assert len(found["APT29"]["mentions"]) == 1
    e = found["Emotet"]["evidence"]
    assert text[e.start:e.end] == e.quote == "emotet"
