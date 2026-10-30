"""STIX 2.1 export engine. Owner: Backend Core.

See team/03_BACKEND_CORE.md Step 6.
Generates valid STIX 2.1 bundles with Identity, Indicators, Vulnerabilities,
AttackPatterns, Relationships, and a container Report.
Predictions are NEVER exported as observed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from app.models import ReportAnalysis

# Try importing stix2 official library
try:
    import stix2
except ImportError:
    stix2 = None


def _escape_stix_val(v: str) -> str:
    """Escape backslashes and single quotes for STIX patterns."""
    return v.replace("\\", "\\\\").replace("'", "\\'")


def build_stix_bundle(analysis: ReportAnalysis) -> dict:
    """Build a STIX 2.1 bundle from an analysis report.

    Validates schema using stix2 library when available, or generates
    exact STIX 2.1 specification dictionary structure.
    """
    now = datetime.now(timezone.utc)
    published_time = analysis.published_at or now

    objects: list = []
    object_refs: list[str] = []

    # 1. Identity
    identity_id = f"identity--{uuid4()}"
    if stix2:
        identity = stix2.Identity(
            id=identity_id,
            name="TRINETRA",
            identity_class="system",
            description="TRINETRA Cyber Threat Intelligence Platform",
        )
        objects.append(identity)
    else:
        identity_dict = {
            "type": "identity",
            "spec_version": "2.1",
            "id": identity_id,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "name": "TRINETRA",
            "identity_class": "system",
            "description": "TRINETRA Cyber Threat Intelligence Platform",
        }
        objects.append(identity_dict)
    object_refs.append(identity_id)

    # 2. Indicators & Vulnerabilities (non-filtered IOCs)
    # Map IOC id -> stix object id for relationship building
    ioc_to_stix_id: dict[str, str] = {}

    for ioc in analysis.iocs:
        if ioc.filtered_reason:
            continue

        ioc_type = ioc.type
        val = ioc.value
        desc = ioc.evidence[0].quote[:300] if ioc.evidence else ""

        # CVE -> Vulnerability object (not an Indicator per STIX spec)
        if ioc_type == "cve":
            vuln_id = f"vulnerability--{uuid4()}"
            ext_refs = [{"source_name": "cve", "external_id": val}]
            if stix2:
                vuln = stix2.Vulnerability(
                    id=vuln_id,
                    name=val,
                    description=desc or f"Vulnerability {val}",
                    created_by_ref=identity_id,
                    external_references=ext_refs,
                )
                objects.append(vuln)
            else:
                objects.append({
                    "type": "vulnerability",
                    "spec_version": "2.1",
                    "id": vuln_id,
                    "created": now.isoformat(),
                    "modified": now.isoformat(),
                    "created_by_ref": identity_id,
                    "name": val,
                    "description": desc or f"Vulnerability {val}",
                    "external_references": ext_refs,
                })
            object_refs.append(vuln_id)
            ioc_to_stix_id[ioc.id] = vuln_id
            continue

        # Skip bitcoin or other unsupported indicator patterns
        if ioc_type in ("btc", "other"):
            continue

        # Pattern mapping
        pattern: str | None = None
        escaped_val = _escape_stix_val(val)

        if ioc_type == "ipv4":
            pattern = f"[ipv4-addr:value = '{escaped_val}']"
        elif ioc_type == "ipv6":
            pattern = f"[ipv6-addr:value = '{escaped_val}']"
        elif ioc_type == "domain":
            pattern = f"[domain-name:value = '{escaped_val}']"
        elif ioc_type == "url":
            pattern = f"[url:value = '{escaped_val}']"
        elif ioc_type == "email":
            pattern = f"[email-addr:value = '{escaped_val}']"
        elif ioc_type == "md5":
            pattern = f"[file:hashes.MD5 = '{escaped_val}']"
        elif ioc_type == "sha1":
            pattern = f"[file:hashes.'SHA-1' = '{escaped_val}']"
        elif ioc_type == "sha256":
            pattern = f"[file:hashes.'SHA-256' = '{escaped_val}']"
        elif ioc_type == "sha512":
            pattern = f"[file:hashes.'SHA-512' = '{escaped_val}']"
        elif ioc_type == "registry":
            pattern = f"[windows-registry-key:key = '{escaped_val}']"
        elif ioc_type == "filepath":
            basename = val.replace("\\", "/").split("/")[-1]
            pattern = f"[file:name = '{_escape_stix_val(basename)}']"

        if not pattern:
            continue

        ind_id = f"indicator--{uuid4()}"
        ind_types = (
            ["malicious-activity"]
            if ioc.role in ("c2", "payload", "exfil", "phishing")
            else ["unknown"]
        )

        if stix2:
            indicator = stix2.Indicator(
                id=ind_id,
                name=ioc.display,
                description=desc,
                indicator_types=ind_types,
                pattern=pattern,
                pattern_type="stix",
                valid_from=now,
                created_by_ref=identity_id,
            )
            objects.append(indicator)
        else:
            objects.append({
                "type": "indicator",
                "spec_version": "2.1",
                "id": ind_id,
                "created": now.isoformat(),
                "modified": now.isoformat(),
                "created_by_ref": identity_id,
                "name": ioc.display,
                "description": desc,
                "indicator_types": ind_types,
                "pattern": pattern,
                "pattern_type": "stix",
                "valid_from": now.isoformat(),
            })

        object_refs.append(ind_id)
        ioc_to_stix_id[ioc.id] = ind_id

    # 3. AttackPatterns (observed accepted techniques only; predictions excluded)
    # Map technique_id -> stix attack-pattern id
    technique_to_stix_id: dict[str, str] = {}

    for tech in analysis.techniques:
        if tech.status != "accepted" or tech.origin != "observed":
            continue

        ap_id = f"attack-pattern--{uuid4()}"
        tech_id = tech.technique_id
        url = tech.url or f"https://attack.mitre.org/techniques/{tech_id.replace('.', '/')}/"

        ext_refs = [{"source_name": "mitre-attack", "external_id": tech_id, "url": url}]
        kill_chains = [
            {"kill_chain_name": "mitre-attack", "phase_name": t}
            for t in tech.tactics
        ]
        evidence_quote = tech.evidence.quote[:300] if tech.evidence else ""
        confidence_mapping = tech.confidence.mapping if tech.confidence.mapping is not None else 0.8

        custom_props = {
            "x_trinetra_evidence": evidence_quote,
            "x_trinetra_confidence": confidence_mapping,
        }

        if stix2:
            ap = stix2.AttackPattern(
                id=ap_id,
                name=tech.name,
                description=tech.rationale or f"ATT&CK Technique {tech_id}: {tech.name}",
                external_references=ext_refs,
                kill_chain_phases=kill_chains,
                created_by_ref=identity_id,
                custom_properties=custom_props,
                allow_custom=True,
            )
            objects.append(ap)
        else:
            ap_dict = {
                "type": "attack-pattern",
                "spec_version": "2.1",
                "id": ap_id,
                "created": now.isoformat(),
                "modified": now.isoformat(),
                "created_by_ref": identity_id,
                "name": tech.name,
                "description": tech.rationale or f"ATT&CK Technique {tech_id}: {tech.name}",
                "external_references": ext_refs,
                "kill_chain_phases": kill_chains,
                **custom_props,
            }
            objects.append(ap_dict)

        object_refs.append(ap_id)
        technique_to_stix_id[tech_id] = ap_id

    # 4. Relationships (indicator indicates attack_pattern)
    for ioc in analysis.iocs:
        if ioc.filtered_reason:
            continue
        ind_stix_id = ioc_to_stix_id.get(ioc.id)
        if not ind_stix_id or ind_stix_id.startswith("vulnerability--"):
            continue

        for tech_id in ioc.linked_techniques:
            ap_stix_id = technique_to_stix_id.get(tech_id)
            if not ap_stix_id:
                continue

            rel_id = f"relationship--{uuid4()}"
            if stix2:
                rel = stix2.Relationship(
                    id=rel_id,
                    source_ref=ind_stix_id,
                    target_ref=ap_stix_id,
                    relationship_type="indicates",
                    created_by_ref=identity_id,
                )
                objects.append(rel)
            else:
                objects.append({
                    "type": "relationship",
                    "spec_version": "2.1",
                    "id": rel_id,
                    "created": now.isoformat(),
                    "modified": now.isoformat(),
                    "created_by_ref": identity_id,
                    "relationship_type": "indicates",
                    "source_ref": ind_stix_id,
                    "target_ref": ap_stix_id,
                })
            object_refs.append(rel_id)

    # 5. Report object referencing all bundled objects
    report_id = f"report--{uuid4()}"
    report_ext_refs = (
        [{"source_name": "source", "url": analysis.source_url}]
        if analysis.source_url
        else []
    )

    if stix2:
        report = stix2.Report(
            id=report_id,
            name=analysis.title or "TRINETRA Threat Intelligence Report",
            published=published_time,
            report_types=["threat-report"],
            object_refs=object_refs,
            created_by_ref=identity_id,
            external_references=report_ext_refs,
        )
        objects.append(report)
        bundle = stix2.Bundle(objects=objects, allow_custom=True)
        return json.loads(bundle.serialize())
    else:
        report_dict = {
            "type": "report",
            "spec_version": "2.1",
            "id": report_id,
            "created": now.isoformat(),
            "modified": now.isoformat(),
            "created_by_ref": identity_id,
            "name": analysis.title or "TRINETRA Threat Intelligence Report",
            "published": published_time.isoformat(),
            "report_types": ["threat-report"],
            "object_refs": object_refs,
            "external_references": report_ext_refs,
        }
        objects.append(report_dict)

        return {
            "type": "bundle",
            "id": f"bundle--{uuid4()}",
            "objects": objects,
        }
