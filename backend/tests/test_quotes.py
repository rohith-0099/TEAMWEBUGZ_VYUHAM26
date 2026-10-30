"""Tests for app.utils.quotes.find_quote."""

import pytest
from app.utils.quotes import find_quote


def test_find_quote_exact():
    text = "The actors deployed Cobalt Strike beacon on the compromised domain controller."
    res = find_quote(text, "Cobalt Strike beacon")
    assert res is not None
    ev, method = res
    assert method == "exact"
    assert ev.quote == "Cobalt Strike beacon"
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_curly_quotes():
    text = 'The threat actor used "living off the land" binaries.'
    res = find_quote(text, "The threat actor used “living off the land” binaries.")
    assert res is not None
    ev, method = res
    assert method == "normalized"
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_case():
    text = "Malware executed POWERSHELL.EXE to download payload."
    res = find_quote(text, "powershell.exe to download")
    assert res is not None
    ev, method = res
    assert method in ("case", "whitespace")
    assert ev.quote == "POWERSHELL.EXE to download"
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_whitespace():
    text = "The malware    created a new service\nnamed SecurityService."
    res = find_quote(text, "The malware created a new service named SecurityService.")
    assert res is not None
    ev, method = res
    assert method == "whitespace"
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_ellipsis():
    text = "Adversaries downloaded a secondary payload from remote infrastructure and subsequently dumped credentials from LSASS."
    res = find_quote(text, "Adversaries downloaded a secondary payload ... dumped credentials from LSASS.")
    assert res is not None
    ev, method = res
    assert method == "ellipsis"
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_fuzzy():
    text = "The attacker used a customized Mimikatz utility to dump active credentials."
    # 1 word typo: "customised" vs "customized"
    res = find_quote(text, "The attacker used a customised Mimikatz utility to dump active credentials.")
    assert res is not None
    ev, method = res
    assert method == "fuzzy"
    assert "Mimikatz" in ev.quote
    assert text[ev.start:ev.end] == ev.quote


def test_find_quote_fabricated_none():
    text = "The attacker established persistence using Windows services."
    res = find_quote(text, "Completely made up sentence that never appears anywhere in the report.")
    assert res is None

