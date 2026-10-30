"""Tests for app.pipeline.migrate."""

from app.models import Evidence, TechniqueMatch
from app.pipeline.migrate import migrate


def test_migrate_explicit_revoked_id():
    text = "The adversary cleared audit trails using T1070.001 to evade detection."
    migrations = migrate(text, [])
    assert len(migrations) >= 1
    m = next((m for m in migrations if m.old_id == "T1070.001"), None)
    assert m is not None
    assert "T1685.005" in m.new_ids
    assert "T1070.001" in m.evidence.quote


def test_migrate_defense_evasion_split():
    text = "Threat actors focused heavily on Defense Evasion across all endpoints."
    migrations = migrate(text, [])
    assert len(migrations) >= 1
    m = next((m for m in migrations if m.old_id == "TA0005"), None)
    assert m is not None
    assert "TA0005" in m.new_ids  # Stealth
    assert "TA0112" in m.new_ids  # Defense Impairment
    assert "Defense Evasion was split" in m.reason


def test_migrate_deprecated_technique_match():
    text = "Some report text without explicit IDs."
    match = TechniqueMatch(
        technique_id="T1070.001",
        name="Clear Windows Event Logs",
        tactics=["defense-evasion"],
        status="rejected",
        reject_reason="deprecated",
        evidence=Evidence(quote="cleared logs", start=0, end=12),
    )
    migrations = migrate(text, [match])
    assert any(m.old_id == "T1070.001" for m in migrations)

