"""ATT&CK lookups used by everyone. STUB — owner: RAG. See team/04_RAG_AI.md Step 3.

Serves the handful of techniques and the tactics in app/mocks.py, not the real v20 data.
"""
from app.mocks import TACTICS, sample_analysis
from app.models import Analytic, DetectionStrategy, LogSource

_analysis = sample_analysis()
_TECHNIQUES = {t.technique_id: t for t in _analysis.techniques + _analysis.predictions
               if t.reject_reason not in ("id_not_in_v20", "deprecated")}
_REVOKED = {"T1064": ["T1059"]}


def list_tactics() -> list[dict]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. Tactic shape, ordered by ord."""
    return [dict(t) for t in TACTICS]


def tactic_order() -> dict[str, int]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. shortname -> ord."""
    return {t["shortname"]: t["ord"] for t in TACTICS}


def tactic_name(shortname: str) -> str:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return next((t["name"] for t in TACTICS if t["shortname"] == shortname), shortname)


def technique_exists(technique_id: str) -> bool:
    """STUB — owner: RAG. See team/04_RAG_AI.md. ONLY active v20 IDs."""
    return technique_id in _TECHNIQUES


def get_technique(technique_id: str) -> dict | None:
    """STUB — owner: RAG. See team/04_RAG_AI.md. Row as dict, no embedding."""
    t = _TECHNIQUES.get(technique_id)
    if t is None:
        return None
    return {"technique_id": t.technique_id, "name": t.name, "description": f"Mock description of {t.name}.",
            "tactics": t.tactics, "is_subtechnique": "." in t.technique_id,
            "parent_id": t.technique_id.split(".")[0] if "." in t.technique_id else None,
            "platforms": ["Windows"], "url": t.url}


def get_technique_detail(technique_id: str) -> dict | None:
    """STUB — owner: RAG. See team/04_RAG_AI.md. TechniqueDetail shape."""
    return get_technique(technique_id)


def all_technique_ids() -> set[str]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return set(_TECHNIQUES)


def get_procedure_examples(technique_id: str, n: int = 2) -> list[str]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return [f"Mock procedure example for {technique_id}."][:n]


def get_detection_info(technique_id: str) -> list[DetectionStrategy]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return [DetectionStrategy(id="DET-MOCK", name=f"Mock strategy for {technique_id}", analytics=[
        Analytic(id="AN-MOCK", name="Mock analytic", platforms=["Windows"],
                 log_sources=[LogSource(name="WinEventLog:Security", data_component="Process Creation")]),
    ])]


def get_mitigations(technique_id: str) -> list[dict]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. Via "mitigates" relationships."""
    return [{"id": "M1038", "name": "Execution Prevention", "description": "Mock mitigation.",
             "url": "https://attack.mitre.org/mitigations/M1038/"}]


def get_revocation(attack_id: str) -> list[str]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. Replacement IDs, [] if none."""
    return _REVOKED.get(attack_id, [])


def is_deprecated_or_revoked(attack_id: str) -> bool:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return attack_id in _REVOKED


def get_technique_sets() -> list[set[str]]:
    """STUB — owner: RAG. See team/04_RAG_AI.md. Techniques per group/campaign/software."""
    return [{"T1566.001", "T1059.001", "T1486", "T1490"}, {"T1003.001", "T1021.001", "T1486"}]


def get_groups_using(technique_id: str) -> list[str]:
    """STUB — owner: RAG. See team/04_RAG_AI.md."""
    return ["Mock Group"]
