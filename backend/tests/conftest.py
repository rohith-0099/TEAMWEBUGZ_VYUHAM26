"""A small fake ATT&CK store, so these tests don't depend on whose stub is real yet."""
import pytest

from app.attack import store
from app.config import settings

TACTICS = ["reconnaissance", "resource-development", "initial-access", "execution", "persistence",
           "privilege-escalation", "stealth", "defense-impairment", "credential-access", "discovery",
           "lateral-movement", "collection", "command-and-control", "exfiltration", "impact"]
TECHNIQUES = {
    "T1566.001": ("Spearphishing Attachment", ["initial-access"]),
    "T1059": ("Command and Scripting Interpreter", ["execution"]),
    "T1059.001": ("PowerShell", ["execution"]),
    "T1547.001": ("Registry Run Keys", ["persistence", "privilege-escalation"]),
    "T1021.001": ("Remote Desktop Protocol", ["lateral-movement"]),
    "T1071.001": ("Web Protocols", ["command-and-control"]),
    "T1486": ("Data Encrypted for Impact", ["impact"]),
    "T1490": ("Inhibit System Recovery", ["impact"]),
    "T1562.001": ("Disable or Modify Tools", ["defense-impairment"]),
    "T1698": ("Direct Prompt Injection", ["execution"]),
    "T1699": ("Indirect Prompt Injection", ["execution"]),
}
REVOKED = {"T1064": ["T1059"]}


@pytest.fixture
def fake_store(monkeypatch):
    def row(tid):
        if tid not in TECHNIQUES:
            return None
        name, tactics = TECHNIQUES[tid]
        return {"technique_id": tid, "name": name, "tactics": tactics, "description": f"{name} description.",
                "url": f"https://attack.mitre.org/techniques/{tid}/"}

    monkeypatch.setattr(store, "tactic_order", lambda: {t: i for i, t in enumerate(TACTICS)})
    monkeypatch.setattr(store, "tactic_name", lambda s: s.replace("-", " ").title())
    monkeypatch.setattr(store, "list_tactics", lambda: [
        {"tactic_id": f"TA{i:04d}", "shortname": t, "name": t, "ord": i} for i, t in enumerate(TACTICS)])
    monkeypatch.setattr(store, "get_technique", row)
    monkeypatch.setattr(store, "technique_exists", lambda t: t in TECHNIQUES)
    monkeypatch.setattr(store, "is_deprecated_or_revoked", lambda t: t in REVOKED)
    monkeypatch.setattr(store, "get_revocation", lambda t: REVOKED.get(t, []))
    monkeypatch.setattr(store, "get_procedure_examples", lambda t, n=2: [])
    monkeypatch.setattr(store, "get_mitigations", lambda t: [{"id": "M1", "name": f"Mitigate {t}", "url": "u"}])
    monkeypatch.setattr(store, "get_detection_info", lambda t: [])
    return store


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_extract_model", "test/extract")
    monkeypatch.setattr(settings, "llm_verify_model", "test/verify")
    monkeypatch.setattr(settings, "mapping_confidence_threshold", 0.6)
