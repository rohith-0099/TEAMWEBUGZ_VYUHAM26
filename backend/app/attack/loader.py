"""Load the official MITRE ATT&CK Enterprise v20 STIX bundle."""

import json
import re
from pathlib import Path
from typing import Any

import httpx
from psycopg.types.json import Jsonb

from app.db import pool


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BUNDLE_PATH = DATA_DIR / "enterprise-attack-20.0.json"

BUNDLE_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
    "master/enterprise-attack/enterprise-attack-20.0.json"
)

ATTACK_ID_SOURCES = {
    "mitre-attack",
    "mitre-mobile-attack",
    "mitre-ics-attack",
}

EXAMPLE_SOURCE_TYPES = {
    "intrusion-set",
    "campaign",
    "malware",
    "tool",
}


def clean_attack_text(s: str) -> str:
    """Remove MITRE citations and Markdown links while preserving their text."""
    if not s:
        return ""

    # Remove MITRE citation markers.
    s = re.sub(r"\(Citation:\s*[^)]*\)", "", s, flags=re.IGNORECASE)

    # Convert Markdown links to their visible text.
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)

    # Remove code tags but retain their contents.
    s = re.sub(r"</?code[^>]*>", "", s, flags=re.IGNORECASE)

    # Collapse whitespace.
    return re.sub(r"\s+", " ", s).strip()


def _download_bundle() -> None:
    """Download the pinned Enterprise ATT&CK v20 bundle if it is not cached."""
    if BUNDLE_PATH.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading MITRE ATT&CK Enterprise v20.0...")

    response = httpx.get(BUNDLE_URL, timeout=120.0, follow_redirects=True)
    response.raise_for_status()

    # Validate JSON before saving it.
    bundle = response.json()
    if not isinstance(bundle.get("objects"), list):
        raise ValueError("Downloaded file is not a valid STIX bundle.")

    BUNDLE_PATH.write_text(
        json.dumps(bundle),
        encoding="utf-8",
    )

    print(f"Bundle saved to: {BUNDLE_PATH}")


def _load_bundle() -> list[dict[str, Any]]:
    """Read the cached bundle and verify that it is the requested v20 file."""
    _download_bundle()

    with BUNDLE_PATH.open("r", encoding="utf-8") as file:
        bundle = json.load(file)

    objects = bundle.get("objects")
    if not isinstance(objects, list):
        raise ValueError("Invalid STIX bundle: missing objects list.")

    # The collection object carries no external_references, so match on its name.
    collection = next(
        (
            obj for obj in objects
            if obj.get("type") == "x-mitre-collection"
            and obj.get("name") == "Enterprise ATT&CK"
        ),
        None,
    )

    if collection is None:
        raise ValueError("Enterprise ATT&CK collection not found.")

    version = str(collection.get("x_mitre_version", ""))
    if not version.startswith("20."):
        raise ValueError(f"Expected ATT&CK v20.x, found {version!r}.")

    print("Verified bundle: Enterprise ATT&CK v20.0")
    print(f"Collection metadata version: {collection.get('x_mitre_version')}")

    return objects


def _external_attack_id(obj: dict[str, Any]) -> str | None:
    """Return an ATT&CK ID from an approved external reference source."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") in ATTACK_ID_SOURCES:
            external_id = ref.get("external_id")
            if external_id:
                return external_id

    return None


def _load_objects(
    cursor: Any,
    objects: list[dict[str, Any]],
) -> None:
    """Insert every STIX object into attack_objects."""
    rows = []

    for obj in objects:
        rows.append(
            (
                obj["id"],
                _external_attack_id(obj),
                obj.get("type"),
                obj.get("name"),
                bool(obj.get("x_mitre_deprecated", False)),
                bool(obj.get("revoked", False)),
                Jsonb(obj),
            )
        )

    cursor.executemany(
        """
        INSERT INTO attack_objects
            (stix_id, attack_id, type, name, deprecated, revoked, data)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )

    print(f"Loaded STIX objects: {len(rows)}")


def _load_relationships(
    cursor: Any,
    objects: list[dict[str, Any]],
) -> None:
    """Insert all STIX relationships into attack_relationships."""
    rows = [
        (
            obj["id"],
            obj.get("source_ref"),
            obj.get("target_ref"),
            obj.get("relationship_type"),
            clean_attack_text(obj.get("description", "")),
        )
        for obj in objects
        if obj.get("type") == "relationship"
    ]

    cursor.executemany(
        """
        INSERT INTO attack_relationships
            (id, source_ref, target_ref, relationship_type, description)
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows,
    )

    print(f"Loaded relationships: {len(rows)}")


def _load_tactics(
    cursor: Any,
    objects: list[dict[str, Any]],
) -> None:
    """Load Enterprise tactics in the official matrix order."""
    matrix = next(
        obj for obj in objects
        if obj.get("type") == "x-mitre-matrix"
        and "enterprise-attack" in obj.get("x_mitre_domains", [])
    )

    objects_by_id = {obj["id"]: obj for obj in objects}
    rows = []

    for order, tactic_ref in enumerate(matrix.get("tactic_refs", []), start=1):
        tactic = objects_by_id.get(tactic_ref)

        if not tactic or tactic.get("type") != "x-mitre-tactic":
            raise ValueError(f"Missing tactic referenced by matrix: {tactic_ref}")

        tactic_id = _external_attack_id(tactic)
        if not tactic_id:
            raise ValueError(f"Missing ATT&CK ID for tactic: {tactic.get('name')}")

        rows.append(
            (
                tactic_id,
                tactic.get("x_mitre_shortname"),
                tactic.get("name"),
                order,
            )
        )

    cursor.executemany(
        """
        INSERT INTO attack_tactics (tactic_id, shortname, name, ord)
        VALUES (%s, %s, %s, %s)
        """,
        rows,
    )

    print(f"Loaded tactics: {len(rows)}")


def _load_techniques(
    cursor: Any,
    objects: list[dict[str, Any]],
) -> set[str]:
    """Load active Enterprise techniques and return their STIX IDs."""
    rows = []
    active_stix_ids = set()

    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue

        if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
            continue

        if "enterprise-attack" not in obj.get("x_mitre_domains", []):
            continue

        technique_id = _external_attack_id(obj)
        if not technique_id:
            continue

        tactics = [
            phase["phase_name"]
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]

        is_subtechnique = bool(obj.get("x_mitre_is_subtechnique", False))
        parent_id = technique_id.split(".", 1)[0] if is_subtechnique else None

        rows.append(
            (
                technique_id,
                obj["id"],
                obj.get("name", ""),
                clean_attack_text(obj.get("description", "")),
                tactics,
                is_subtechnique,
                parent_id,
                obj.get("x_mitre_platforms", []),
                next(
                    (
                        ref.get("url")
                        for ref in obj.get("external_references", [])
                        if ref.get("source_name") == "mitre-attack"
                        and ref.get("external_id") == technique_id
                    ),
                    None,
                ),
            )
        )

        active_stix_ids.add(obj["id"])

    cursor.executemany(
        """
        INSERT INTO attack_techniques
            (
                technique_id, stix_id, name, description, tactics,
                is_subtechnique, parent_id, platforms, url
            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )

    parent_count = sum(1 for row in rows if not row[5])
    subtechnique_count = sum(1 for row in rows if row[5])

    print(f"Loaded active techniques: {len(rows)}")
    print(f"  Parent techniques: {parent_count}")
    print(f"  Subtechniques: {subtechnique_count}")

    return active_stix_ids


def _load_examples(
    cursor: Any,
    objects: list[dict[str, Any]],
    active_stix_ids: set[str],
) -> None:
    """Load curated procedure examples from uses relationships."""
    objects_by_id = {obj["id"]: obj for obj in objects}
    examples_by_technique: dict[str, list[str]] = {}

    for relationship in objects:
        if (
            relationship.get("type") != "relationship"
            or relationship.get("relationship_type") != "uses"
        ):
            continue

        source = objects_by_id.get(relationship.get("source_ref"))
        target_ref = relationship.get("target_ref")

        if not source or target_ref not in active_stix_ids:
            continue

        if source.get("type") not in EXAMPLE_SOURCE_TYPES:
            continue

        description = clean_attack_text(relationship.get("description", ""))

        if not 30 <= len(description) <= 600:
            continue

        examples_by_technique.setdefault(target_ref, []).append(description)

    rows = []

    for technique_stix_id, descriptions in examples_by_technique.items():
        technique = objects_by_id[technique_stix_id]
        technique_id = _external_attack_id(technique)

        if not technique_id:
            continue

        # Prefer the longer, more informative descriptions.
        unique_descriptions = sorted(
            set(descriptions),
            key=len,
            reverse=True,
        )

        for description in unique_descriptions[:40]:
            rows.append((technique_id, description))

    if rows:
        cursor.executemany(
            """
            INSERT INTO attack_examples (technique_id, text)
            VALUES (%s, %s)
            """,
            rows,
        )

    print(f"Loaded procedure examples: {len(rows)}")


def _load_embeddings(cursor: Any) -> None:
    """Generate and write embeddings for techniques and examples in batches of 256."""
    from app.attack.embed import embed_passages

    print("Generating embeddings for techniques...")
    cursor.execute(
        """
        SELECT technique_id, name, tactics, is_subtechnique, parent_id, description
        FROM attack_techniques
        """
    )
    technique_rows = cursor.fetchall()

    name_by_id = {
        (r["technique_id"] if isinstance(r, dict) else r[0]): (r["name"] if isinstance(r, dict) else r[1])
        for r in technique_rows
    }

    tech_ids = []
    tech_texts = []
    for r in technique_rows:
        tid = r["technique_id"] if isinstance(r, dict) else r[0]
        name = r["name"] if isinstance(r, dict) else r[1]
        tactics = r["tactics"] if isinstance(r, dict) else r[2]
        tactics_str = ", ".join(tactics) if tactics else ""
        is_sub = r["is_subtechnique"] if isinstance(r, dict) else r[3]
        parent_id = r["parent_id"] if isinstance(r, dict) else r[4]
        desc = ((r["description"] if isinstance(r, dict) else r[5]) or "")[:1200]

        if is_sub and parent_id and parent_id in name_by_id:
            parent_name = name_by_id[parent_id]
            text = f"{parent_name}: {name}. Tactics: {tactics_str}. {desc}"
        else:
            text = f"{name}. Tactics: {tactics_str}. {desc}"

        tech_ids.append(tid)
        tech_texts.append(text)

    for i in range(0, len(tech_texts), 256):
        batch_ids = tech_ids[i:i + 256]
        batch_texts = tech_texts[i:i + 256]
        batch_embs = embed_passages(batch_texts)
        cursor.executemany(
            "UPDATE attack_techniques SET embedding = %s WHERE technique_id = %s",
            [(emb, tid) for tid, emb in zip(batch_ids, batch_embs)],
        )
    print(f"Technique embeddings generated: {len(tech_texts)}")

    print("Generating embeddings for examples...")
    cursor.execute("SELECT id, text FROM attack_examples")
    example_rows = cursor.fetchall()
    ex_ids = [r["id"] if isinstance(r, dict) else r[0] for r in example_rows]
    ex_texts = [r["text"] if isinstance(r, dict) else r[1] for r in example_rows]

    for i in range(0, len(ex_texts), 256):
        batch_ids = ex_ids[i:i + 256]
        batch_texts = ex_texts[i:i + 256]
        batch_embs = embed_passages(batch_texts)
        cursor.executemany(
            "UPDATE attack_examples SET embedding = %s WHERE id = %s",
            [(emb, eid) for eid, emb in zip(batch_ids, batch_embs)],
        )
    print(f"Example embeddings generated: {len(ex_texts)}")


def load_attack() -> None:
    """Download and idempotently reload the ATT&CK reference tables."""
    objects = _load_bundle()

    with pool.connection() as connection:
        with connection.cursor() as cursor:
            # Only ATT&CK reference tables are cleared.
            cursor.execute(
                """
                TRUNCATE TABLE
                    attack_examples,
                    attack_techniques,
                    attack_tactics,
                    attack_relationships,
                    attack_objects
                RESTART IDENTITY
                """
            )

            _load_objects(cursor, objects)
            _load_relationships(cursor, objects)
            _load_tactics(cursor, objects)
            active_stix_ids = _load_techniques(cursor, objects)
            _load_examples(cursor, objects, active_stix_ids)
            _load_embeddings(cursor)

    print("\nATT&CK v20.0 loading completed successfully.")
