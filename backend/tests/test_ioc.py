"""Tests for deterministic IOC extraction engine. Owner: Backend Core."""
import time
from app.pipeline.ioc import extract_iocs


def test_defanged_ioc_extraction():
    text = "Attacker C2 at hxxp://evil[.]com/gate.php and 45[.]77[.]12[.]9 was observed communicating."
    iocs = extract_iocs(text)

    ioc_dict = {i.value: i for i in iocs}

    # URL refanged vs defanged display
    assert "http://evil.com/gate.php" in ioc_dict
    url_ioc = ioc_dict["http://evil.com/gate.php"]
    assert url_ioc.type == "url"
    assert url_ioc.display == "hxxp://evil[.]com/gate.php"
    assert url_ioc.filtered_reason is None

    # IPv4 refanged vs defanged display
    assert "45.77.12.9" in ioc_dict
    ip_ioc = ioc_dict["45.77.12.9"]
    assert ip_ioc.type == "ipv4"
    assert ip_ioc.display == "45[.]77[.]12[.]9"
    assert ip_ioc.filtered_reason is None


def test_filtering_rules():
    text = (
        "Internal IP 192.168.1.10 contacted microsoft.com.\n"
        "Operating system version 10.0.19041.1 was patched.\n"
        "User opened C:\\Users\\victim\\Downloads\\invoice.zip which dropped malware."
    )
    iocs = extract_iocs(text)
    ioc_dict = {i.value: i for i in iocs}

    # Private IP
    assert "192.168.1.10" in ioc_dict
    assert ioc_dict["192.168.1.10"].filtered_reason == "private_or_reserved_ip"

    # Benign domain
    assert "microsoft.com" in ioc_dict
    assert ioc_dict["microsoft.com"].filtered_reason == "benign_domain"

    # Version number
    assert "10.0.19041.1" in ioc_dict
    assert ioc_dict["10.0.19041.1"].filtered_reason == "version_number"

    # Filename looking domain
    if "invoice.zip" in ioc_dict:
        assert ioc_dict["invoice.zip"].filtered_reason == "looks_like_filename"


def test_hashes_cve_and_deduplication():
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    md5 = "d41d8cd98f00b204e9800998ecf8427e"
    text = (
        f"Malware SHA-256: {sha256} and MD5: {md5}.\n"
        "Exploited vulnerability CVE-2026-12345 in initial access.\n"
        "Later notes also cite cve-2026-12345 again."
    )
    iocs = extract_iocs(text)

    values = [i.value for i in iocs]
    assert sha256 in values
    assert md5 in values
    assert "CVE-2026-12345" in values

    # CVE should only appear once (deduplicated)
    cve_matches = [i for i in iocs if i.value == "CVE-2026-12345"]
    assert len(cve_matches) == 1
    # Evidence should have captured both occurrences
    assert len(cve_matches[0].evidence) == 2


def test_evidence_offsets_exact():
    text = (
        "Adversary activity detected.\n"
        "Phishing email sent from badactor[@]evil[.]org to employees.\n"
        "Registry persistence added at HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Backdoor."
    )
    iocs = extract_iocs(text)
    assert len(iocs) >= 2

    for ioc in iocs:
        assert len(ioc.evidence) >= 1
        for ev in ioc.evidence:
            # Must strictly match the source text slice
            assert text[ev.start:ev.end] == ev.quote


def test_performance_under_300ms():
    base_paragraph = (
        "Threat report paragraph. Adversary connected to 185[.]220[.]101[.]5 and hxxp://bad[.]domain[.]com/api. "
        "Persistence was observed via C:\\Windows\\Temp\\payload.exe and registry HKLM\\Run\\Update. "
        "Malware hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. "
        "Patched CVE-2024-21413 on host 10.0.0.1. Reference link at https://attack.mitre.org/techniques/T1566/.\n\n"
    )
    # Replicate to reach ~50,000 characters
    repeat_count = 50000 // len(base_paragraph) + 1
    large_text = base_paragraph * repeat_count

    start_time = time.perf_counter()
    iocs = extract_iocs(large_text)
    duration_ms = (time.perf_counter() - start_time) * 1000

    assert len(iocs) > 0
    # Must complete in under 300ms
    assert duration_ms < 300, f"Extraction took {duration_ms:.2f} ms (target: < 300 ms)"

