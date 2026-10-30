"""ATT&CK lookups used by everyone. Owner: RAG. See team/04_RAG_AI.md Step 3."""

import json
from pathlib import Path
from typing import Any

from app.attack.loader import clean_attack_text
from app.db import pool
from app.models import Analytic, DetectionStrategy, LogSource

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_BUNDLE_PATH = _DATA_DIR / "enterprise-attack-20.0.json"

# In-memory caches populated at first call
_INITIALIZED: bool = False
_TACTICS: list[dict[str, Any]] = []
_TACTIC_BY_SHORTNAME: dict[str, dict[str, Any]] = {}
_TECHNIQUES: dict[str, dict[str, Any]] = {}  # technique_id -> dict
_TECHNIQUE_BY_STIX: dict[str, str] = {}     # stix_id -> technique_id
_STIX_BY_TECHNIQUE: dict[str, str] = {}     # technique_id -> stix_id
_PROCEDURE_EXAMPLES: dict[str, list[str]] = {}  # technique_id -> list[str]
_REVOCATIONS: dict[str, list[str]] = {}     # attack_id -> list of replacement attack_ids
_DEPRECATED_OR_REVOKED: set[str] = set()
_DETECTION_CACHE: dict[str, list[DetectionStrategy]] = {}
_MITIGATIONS_CACHE: dict[str, list[dict[str, Any]]] = {}
_GROUPS_USING_CACHE: dict[str, list[str]] = {}
_TECHNIQUE_SETS_CACHE: list[set[str]] | None = None


def _ensure_initialized() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    _load_data()
    _INITIALIZED = True


def _load_from_db() -> bool:
    """Attempt to populate in-memory structures from PostgreSQL."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tactic_id, shortname, name, ord FROM attack_tactics ORDER BY ord ASC")
                tactics = cur.fetchall()
                if not tactics:
                    return False

                _TACTICS.clear()
                _TACTIC_BY_SHORTNAME.clear()
                for row in tactics:
                    t_dict = {
                        "tactic_id": row["tactic_id"] if isinstance(row, dict) else row[0],
                        "shortname": row["shortname"] if isinstance(row, dict) else row[1],
                        "name": row["name"] if isinstance(row, dict) else row[2],
                        "ord": row["ord"] if isinstance(row, dict) else row[3],
                    }
                    _TACTICS.append(t_dict)
                    _TACTIC_BY_SHORTNAME[t_dict["shortname"]] = t_dict

                cur.execute(
                    """
                    SELECT technique_id, stix_id, name, description, tactics,
                           is_subtechnique, parent_id, platforms, url
                    FROM attack_techniques
                    """
                )
                techs = cur.fetchall()
                _TECHNIQUES.clear()
                _TECHNIQUE_BY_STIX.clear()
                _STIX_BY_TECHNIQUE.clear()
                for row in techs:
                    tid = row["technique_id"] if isinstance(row, dict) else row[0]
                    stix = row["stix_id"] if isinstance(row, dict) else row[1]
                    t_data = {
                        "technique_id": tid,
                        "stix_id": stix,
                        "name": row["name"] if isinstance(row, dict) else row[2],
                        "description": row["description"] if isinstance(row, dict) else row[3],
                        "tactics": row["tactics"] if isinstance(row, dict) else row[4],
                        "is_subtechnique": row["is_subtechnique"] if isinstance(row, dict) else row[5],
                        "parent_id": row["parent_id"] if isinstance(row, dict) else row[6],
                        "platforms": row["platforms"] if isinstance(row, dict) else row[7],
                        "url": row["url"] if isinstance(row, dict) else row[8],
                    }
                    _TECHNIQUES[tid] = t_data
                    _TECHNIQUE_BY_STIX[stix] = tid
                    _STIX_BY_TECHNIQUE[tid] = stix

                # Load procedure examples
                cur.execute("SELECT technique_id, text FROM attack_examples")
                _PROCEDURE_EXAMPLES.clear()
                for row in cur.fetchall():
                    tid = row["technique_id"] if isinstance(row, dict) else row[0]
                    txt = row["text"] if isinstance(row, dict) else row[1]
                    _PROCEDURE_EXAMPLES.setdefault(tid, []).append(txt)

                # Revoked/deprecated objects
                cur.execute("SELECT attack_id FROM attack_objects WHERE deprecated = true OR revoked = true")
                _DEPRECATED_OR_REVOKED.clear()
                for row in cur.fetchall():
                    aid = row["attack_id"] if isinstance(row, dict) else row[0]
                    if aid:
                        _DEPRECATED_OR_REVOKED.add(aid)

        return True
    except Exception:
        return False


def _load_from_bundle() -> None:
    """Fallback loader directly from the official v20 STIX JSON bundle."""
    if not _BUNDLE_PATH.exists():
        return

    with _BUNDLE_PATH.open("r", encoding="utf-8") as f:
        bundle = json.load(f)

    objects = bundle.get("objects", [])
    by_id = {obj["id"]: obj for obj in objects}

    def ext_id(obj: dict) -> str | None:
        for ref in obj.get("external_references", []):
            if ref.get("source_name") in ("mitre-attack", "mitre-mobile-attack", "mitre-ics-attack"):
                eid = ref.get("external_id")
                if eid:
                    return eid
        return None

    # Load matrix tactics
    matrix = next(
        (o for o in objects if o.get("type") == "x-mitre-matrix" and "enterprise-attack" in o.get("x_mitre_domains", [])),
        None,
    )
    if matrix:
        _TACTICS.clear()
        _TACTIC_BY_SHORTNAME.clear()
        for ord_idx, tactic_ref in enumerate(matrix.get("tactic_refs", []), start=1):
            t_obj = by_id.get(tactic_ref)
            if t_obj:
                tid = ext_id(t_obj) or ""
                sname = t_obj.get("x_mitre_shortname", "")
                t_dict = {"tactic_id": tid, "shortname": sname, "name": t_obj.get("name", ""), "ord": ord_idx}
                _TACTICS.append(t_dict)
                _TACTIC_BY_SHORTNAME[sname] = t_dict

    # Load active techniques
    _TECHNIQUES.clear()
    _TECHNIQUE_BY_STIX.clear()
    _STIX_BY_TECHNIQUE.clear()
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
            aid = ext_id(obj)
            if aid:
                _DEPRECATED_OR_REVOKED.add(aid)
            continue
        if "enterprise-attack" not in obj.get("x_mitre_domains", []):
            continue
        tid = ext_id(obj)
        if not tid:
            continue
        tactics = [
            p["phase_name"]
            for p in obj.get("kill_chain_phases", [])
            if p.get("kill_chain_name") == "mitre-attack"
        ]
        is_sub = bool(obj.get("x_mitre_is_subtechnique", False))
        parent_id = tid.split(".", 1)[0] if is_sub else None
        url = next(
            (r.get("url") for r in obj.get("external_references", [])
             if r.get("source_name") == "mitre-attack" and r.get("external_id") == tid),
            None,
        )
        t_data = {
            "technique_id": tid,
            "stix_id": obj["id"],
            "name": obj.get("name", ""),
            "description": clean_attack_text(obj.get("description", "")),
            "tactics": tactics,
            "is_subtechnique": is_sub,
            "parent_id": parent_id,
            "platforms": obj.get("x_mitre_platforms", []),
            "url": url,
        }
        _TECHNIQUES[tid] = t_data
        _TECHNIQUE_BY_STIX[obj["id"]] = tid
        _STIX_BY_TECHNIQUE[tid] = obj["id"]

    # Load procedure examples & relationships
    _PROCEDURE_EXAMPLES.clear()
    for rel in objects:
        if rel.get("type") != "relationship":
            continue
        rtype = rel.get("relationship_type")
        s_ref = rel.get("source_ref")
        t_ref = rel.get("target_ref")

        if rtype == "uses" and t_ref in _TECHNIQUE_BY_STIX:
            src = by_id.get(s_ref)
            if src and src.get("type") in ("intrusion-set", "campaign", "malware", "tool"):
                desc = clean_attack_text(rel.get("description", ""))
                if 30 <= len(desc) <= 600:
                    tid = _TECHNIQUE_BY_STIX[t_ref]
                    _PROCEDURE_EXAMPLES.setdefault(tid, []).append(desc)

        if rtype == "revoked-by":
            src = by_id.get(s_ref)
            tgt = by_id.get(t_ref)
            if src and tgt:
                src_aid = ext_id(src)
                tgt_aid = ext_id(tgt)
                if src_aid and tgt_aid:
                    _REVOCATIONS.setdefault(src_aid, []).append(tgt_aid)
                    _DEPRECATED_OR_REVOKED.add(src_aid)


def _load_data() -> None:
    if not _load_from_db():
        _load_from_bundle()


def list_tactics() -> list[dict[str, Any]]:
    """Tactic shape, ordered by ord (route /api/attack/tactics)."""
    _ensure_initialized()
    return [dict(t) for t in _TACTICS]


def tactic_order() -> dict[str, int]:
    """shortname -> ord."""
    _ensure_initialized()
    return {t["shortname"]: t["ord"] for t in _TACTICS}


def tactic_name(shortname: str) -> str:
    """Convert tactic shortname to formal name."""
    _ensure_initialized()
    t = _TACTIC_BY_SHORTNAME.get(shortname)
    return t["name"] if t else shortname


def technique_exists(technique_id: str) -> bool:
    """ONLY active (non-revoked, non-deprecated) v20 IDs."""
    _ensure_initialized()
    return technique_id in _TECHNIQUES


def get_technique(technique_id: str) -> dict[str, Any] | None:
    """Row as dict (no embedding)."""
    _ensure_initialized()
    t = _TECHNIQUES.get(technique_id)
    return dict(t) if t else None


def get_technique_detail(technique_id: str) -> dict[str, Any] | None:
    """TechniqueDetail shape (route /api/attack/techniques/{id})."""
    return get_technique(technique_id)


def all_technique_ids() -> set[str]:
    """Set of all active technique IDs."""
    _ensure_initialized()
    return set(_TECHNIQUES.keys())


def get_procedure_examples(technique_id: str, n: int = 2) -> list[str]:
    """Short procedure examples for verifier context."""
    _ensure_initialized()
    examples = _PROCEDURE_EXAMPLES.get(technique_id, [])
    return examples[:n]


def get_detection_info(technique_id: str) -> list[DetectionStrategy]:
    """ATT&CK v18+ detection strategies -> analytics -> log sources."""
    _ensure_initialized()
    if technique_id in _DETECTION_CACHE:
        return _DETECTION_CACHE[technique_id]

    stix_id = _STIX_BY_TECHNIQUE.get(technique_id)
    if not stix_id or not _BUNDLE_PATH.exists():
        _DETECTION_CACHE[technique_id] = []
        return []

    try:
        with _BUNDLE_PATH.open("r", encoding="utf-8") as f:
            bundle = json.load(f)
        objects = bundle.get("objects", [])
        by_id = {o["id"]: o for o in objects}

        # Data components lookup
        dc_by_id = {o["id"]: o for o in objects if o.get("type") == "x-mitre-data-component"}

        # Find detects relationships where target_ref == stix_id
        detect_rels = [
            o for o in objects
            if o.get("type") == "relationship"
            and o.get("relationship_type") == "detects"
            and o.get("target_ref") == stix_id
        ]

        strategies: list[DetectionStrategy] = []
        for rel in detect_rels:
            strat_obj = by_id.get(rel.get("source_ref"))
            if not strat_obj or strat_obj.get("type") != "x-mitre-detection-strategy":
                continue

            strat_id = next(
                (r.get("external_id") for r in strat_obj.get("external_references", [])
                 if r.get("source_name") == "mitre-attack"),
                strat_obj["id"],
            )

            analytics: list[Analytic] = []
            for an_ref in strat_obj.get("x_mitre_analytic_refs", []):
                an_obj = by_id.get(an_ref)
                if not an_obj or an_obj.get("type") != "x-mitre-analytic":
                    continue

                an_id = next(
                    (r.get("external_id") for r in an_obj.get("external_references", [])
                     if r.get("source_name") == "mitre-attack"),
                    an_obj["id"],
                )

                log_sources: list[LogSource] = []
                for ls_ref in an_obj.get("x_mitre_log_source_references", []):
                    dc_ref = ls_ref.get("x_mitre_data_component_ref")
                    dc_name = dc_by_id.get(dc_ref, {}).get("name") if dc_ref else None
                    log_sources.append(
                        LogSource(
                            name=ls_ref.get("name") or "",
                            data_component=dc_name,
                            telemetry=None,
                        )
                    )

                analytics.append(
                    Analytic(
                        id=an_id,
                        name=an_obj.get("name", ""),
                        platforms=an_obj.get("x_mitre_platforms", []),
                        log_sources=log_sources,
                    )
                )

            strategies.append(
                DetectionStrategy(
                    id=strat_id,
                    name=strat_obj.get("name", ""),
                    analytics=analytics,
                )
            )

        _DETECTION_CACHE[technique_id] = strategies
        return strategies
    except Exception:
        return []


def get_mitigations(technique_id: str) -> list[dict[str, Any]]:
    """[{id: 'M1038', name, description, url}] via mitigates relationships."""
    _ensure_initialized()
    if technique_id in _MITIGATIONS_CACHE:
        return _MITIGATIONS_CACHE[technique_id]

    stix_id = _STIX_BY_TECHNIQUE.get(technique_id)
    if not stix_id or not _BUNDLE_PATH.exists():
        _MITIGATIONS_CACHE[technique_id] = []
        return []

    try:
        with _BUNDLE_PATH.open("r", encoding="utf-8") as f:
            bundle = json.load(f)
        objects = bundle.get("objects", [])
        by_id = {o["id"]: o for o in objects}

        mitigates_rels = [
            o for o in objects
            if o.get("type") == "relationship"
            and o.get("relationship_type") == "mitigates"
            and o.get("target_ref") == stix_id
        ]

        result = []
        for rel in mitigates_rels:
            coa = by_id.get(rel.get("source_ref"))
            if not coa or coa.get("type") != "course-of-action":
                continue

            mid = next(
                (r.get("external_id") for r in coa.get("external_references", [])
                 if r.get("source_name") in ("mitre-attack", "mitre-mobile-attack")),
                coa["id"],
            )
            url = next(
                (r.get("url") for r in coa.get("external_references", [])
                 if r.get("source_name") in ("mitre-attack", "mitre-mobile-attack")),
                "",
            )
            desc = clean_attack_text(rel.get("description") or coa.get("description", ""))[:300]
            result.append({
                "id": mid,
                "name": coa.get("name", ""),
                "description": desc,
                "url": url,
            })

        _MITIGATIONS_CACHE[technique_id] = result
        return result
    except Exception:
        return []


def get_revocation(attack_id: str) -> list[str]:
    """Revoked/deprecated technique -> replacement IDs via revoked-by relationships ([] if none)."""
    _ensure_initialized()
    return list(_REVOCATIONS.get(attack_id, []))


def is_deprecated_or_revoked(attack_id: str) -> bool:
    """True if attack_id is marked deprecated or revoked in ATT&CK."""
    _ensure_initialized()
    return attack_id in _DEPRECATED_OR_REVOKED


def get_technique_sets() -> list[set[str]]:
    """For Lead's prediction fallback: technique sets per intrusion-set, campaign, software."""
    global _TECHNIQUE_SETS_CACHE
    if _TECHNIQUE_SETS_CACHE is not None:
        return _TECHNIQUE_SETS_CACHE

    _ensure_initialized()
    if not _BUNDLE_PATH.exists():
        return []

    try:
        with _BUNDLE_PATH.open("r", encoding="utf-8") as f:
            bundle = json.load(f)
        objects = bundle.get("objects", [])
        by_id = {o["id"]: o for o in objects}

        sets_by_source: dict[str, set[str]] = {}
        for rel in objects:
            if rel.get("type") != "relationship" or rel.get("relationship_type") != "uses":
                continue
            s_ref = rel.get("source_ref")
            t_ref = rel.get("target_ref")
            src = by_id.get(s_ref)
            if src and src.get("type") in ("intrusion-set", "campaign", "malware", "tool"):
                tid = _TECHNIQUE_BY_STIX.get(t_ref)
                if tid:
                    sets_by_source.setdefault(s_ref, set()).add(tid)

        _TECHNIQUE_SETS_CACHE = [s for s in sets_by_source.values() if len(s) >= 2]
        return _TECHNIQUE_SETS_CACHE
    except Exception:
        return []


def get_groups_using(technique_id: str) -> list[str]:
    """Group/actor names using this technique, for UI tooltips."""
    _ensure_initialized()
    if technique_id in _GROUPS_USING_CACHE:
        return _GROUPS_USING_CACHE[technique_id]

    stix_id = _STIX_BY_TECHNIQUE.get(technique_id)
    if not stix_id or not _BUNDLE_PATH.exists():
        return []

    try:
        with _BUNDLE_PATH.open("r", encoding="utf-8") as f:
            bundle = json.load(f)
        objects = bundle.get("objects", [])
        by_id = {o["id"]: o for o in objects}

        names = set()
        for rel in objects:
            if (rel.get("type") == "relationship" and
                    rel.get("relationship_type") == "uses" and
                    rel.get("target_ref") == stix_id):
                src = by_id.get(rel.get("source_ref"))
                if src and src.get("type") == "intrusion-set":
                    name = src.get("name")
                    if name:
                        names.add(name)

        result = sorted(names)
        _GROUPS_USING_CACHE[technique_id] = result
        return result
    except Exception:
        return []
