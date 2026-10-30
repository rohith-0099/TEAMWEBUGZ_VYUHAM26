"""Tests for app.attack.store."""

import pytest
from app.attack.store import (
    all_technique_ids,
    get_detection_info,
    get_mitigations,
    get_technique,
    is_deprecated_or_revoked,
    list_tactics,
    tactic_name,
    tactic_order,
    technique_exists,
)


def test_tactics_loaded():
    tactics = list_tactics()
    assert len(tactics) == 15
    shortnames = [t["shortname"] for t in tactics]
    assert "reconnaissance" in shortnames
    assert "stealth" in shortnames
    assert "defense-impairment" in shortnames

    order = tactic_order()
    assert order["reconnaissance"] == 1
    assert tactic_name("stealth") == "Stealth"


def test_technique_exists():
    assert technique_exists("T1059.001") is True
    assert technique_exists("T9999") is False
    # Revoked technique should not exist in active techniques
    assert technique_exists("T1070.001") is False


def test_technique_detail():
    tech = get_technique("T1059.001")
    assert tech is not None
    assert tech["name"] == "PowerShell"
    assert tech["is_subtechnique"] is True
    assert tech["parent_id"] == "T1059"


def test_detection_info():
    detections = get_detection_info("T1059.001")
    assert len(detections) >= 1
    strategy = detections[0]
    assert len(strategy.analytics) >= 1
    analytic = strategy.analytics[0]
    assert len(analytic.log_sources) >= 1


def test_revocations_deprecated():
    assert is_deprecated_or_revoked("T1070.001") is True
    assert is_deprecated_or_revoked("T1059.001") is False

