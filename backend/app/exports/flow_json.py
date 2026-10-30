"""CTID Attack Flow export. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 6.

The extension-definition and MITRE identity below are copied from the official example,
stix/attack-flow-example.json in center-for-threat-informed-defense/attack-flow.
"""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.attack import store
from app.models import ReportAnalysis

EXTENSION_ID = "extension-definition--fb9c968a-745b-4ade-9b25-c324172197f4"
MITRE_IDENTITY_ID = "identity--d673f8cb-c168-42da-8ed4-0cb26725f86c"
_EXTENSIONS = {EXTENSION_ID: {"extension_type": "new-sdo"}}

_EXTENSION_DEFINITION = {
    "type": "extension-definition",
    "id": EXTENSION_ID,
    "spec_version": "2.1",
    "name": "Attack Flow",
    "description": "Extends STIX 2.1 with features to create Attack Flows.",
    "created": "2022-08-02T19:34:35.143Z",
    "modified": "2022-08-02T19:34:35.143Z",
    "created_by_ref": MITRE_IDENTITY_ID,
    "schema": "https://center-for-threat-informed-defense.github.io/attack-flow/stix/attack-flow-schema-2.0.0.json",
    "version": "2.0.0",
    "extension_types": ["new-sdo"],
    "external_references": [
        {"source_name": "Documentation", "description": "Documentation for Attack Flow",
         "url": "https://center-for-threat-informed-defense.github.io/attack-flow"},
        {"source_name": "GitHub", "description": "Source code repository for Attack Flow",
         "url": "https://github.com/center-for-threat-informed-defense/attack-flow"},
    ],
}
_MITRE_IDENTITY = {
    "type": "identity",
    "spec_version": "2.1",
    "id": MITRE_IDENTITY_ID,
    "created_by_ref": MITRE_IDENTITY_ID,
    "created": "2022-08-02T19:34:35.143Z",
    "modified": "2022-08-02T19:34:35.143Z",
    "name": "MITRE Center for Threat-Informed Defense",
    "identity_class": "organization",
}


def _stix_id(kind: str, report_id: str, name: str) -> str:
    # Derived, not random, so exporting the same report twice gives identical objects.
    return f"{kind}--{uuid5(NAMESPACE_URL, f'trinetra:{report_id}:{name}')}"


def attack_flow_json(analysis: ReportAnalysis) -> dict:
    """STIX 2.1 bundle. Observed and unknown steps only: predictions are never exported."""
    report_id = analysis.report_id
    stamp = (analysis.created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{stamp.microsecond // 1000:03d}Z"
    common = {"spec_version": "2.1", "created": timestamp, "modified": timestamp}

    identity_id = _stix_id("identity", report_id, "trinetra")
    identity = {"type": "identity", "id": identity_id, "created_by_ref": identity_id, **common,
                "name": "TRINETRA", "identity_class": "system"}

    nodes = [n for n in analysis.flow.nodes if n.kind != "predicted"]
    action_ids = {n.id: _stix_id("attack-action", report_id, n.id) for n in nodes}
    tactic_ids = {t["shortname"]: t["tactic_id"] for t in store.list_tactics()}
    evidence = {t.technique_id: t.evidence.quote for t in analysis.techniques
                if t.status == "accepted" and t.evidence}

    actions = []
    for node in nodes:
        action = {"type": "attack-action", "id": action_ids[node.id], **common, "name": node.label,
                  "effect_refs": [action_ids[e.target] for e in analysis.flow.edges
                                  if e.source == node.id and e.target in action_ids],
                  "extensions": _EXTENSIONS}
        if node.tactic in tactic_ids:
            action["tactic_id"] = tactic_ids[node.tactic]
        if node.kind == "observed":
            action["technique_id"] = node.technique_id
            action["description"] = evidence.get(node.technique_id, "")
        else:
            action["description"] = "not established in report"
        if not action["effect_refs"]:
            del action["effect_refs"]
        actions.append(action)

    targets = {e.target for e in analysis.flow.edges}
    flow = {"type": "attack-flow", "id": _stix_id("attack-flow", report_id, "flow"), **common,
            "created_by_ref": identity_id, "name": analysis.title or "TRINETRA attack flow",
            "scope": "incident", "start_refs": [action_ids[n.id] for n in nodes if n.id not in targets],
            "extensions": _EXTENSIONS}
    if analysis.source_url:
        flow["external_references"] = [{"source_name": "Source report", "url": analysis.source_url}]
    return {"type": "bundle", "id": _stix_id("bundle", report_id, "bundle"),
            "objects": [_EXTENSION_DEFINITION, _MITRE_IDENTITY, identity, flow, *actions]}
