"""Tests for app.pipeline.link."""

from app.models import Confidence, Evidence, IOC, TechniqueMatch
from app.pipeline.link import link_iocs


def test_link_iocs_overlapping_span():
    text = "The malware connected to 192.168.1.50 over PowerShell to receive commands."
    # IOC: 192.168.1.50
    start_ip = text.find("192.168.1.50")
    ioc = IOC(
        id="ioc-1",
        type="ipv4",
        value="192.168.1.50",
        display="192.168.1[.]50",
        evidence=[Evidence(quote="192.168.1.50", start=start_ip, end=start_ip + 12)],
    )

    # Technique: PowerShell (T1059.001) with broad evidence span covering the full sentence
    tech = TechniqueMatch(
        technique_id="T1059.001",
        name="PowerShell",
        tactics=["execution"],
        status="accepted",
        evidence=Evidence(quote=text, start=0, end=len(text)),
    )

    iocs, techs = link_iocs([ioc], [tech], text)
    assert "ioc-1" in techs[0].linked_iocs
    assert "T1059.001" in iocs[0].linked_techniques
    assert techs[0].confidence.relationship == 0.9


def test_link_iocs_same_sentence():
    text = "Attackers deployed Cobalt Strike. The payload downloaded from evil.com shortly thereafter."
    start_domain = text.find("evil.com")
    ioc = IOC(
        id="ioc-2",
        type="domain",
        value="evil.com",
        display="evil[.]com",
        evidence=[Evidence(quote="evil.com", start=start_domain, end=start_domain + 8)],
    )
    start_payload = text.find("payload downloaded")
    tech = TechniqueMatch(
        technique_id="T1105",
        name="Ingress Tool Transfer",
        tactics=["command-and-control"],
        status="accepted",
        evidence=Evidence(quote="payload downloaded", start=start_payload, end=start_payload + 18),
    )

    iocs, techs = link_iocs([ioc], [tech], text)
    assert "ioc-2" in techs[0].linked_iocs
    assert "T1105" in iocs[0].linked_techniques
    assert techs[0].confidence.relationship == 0.8


def test_link_ignores_rejected_techniques():
    text = "Malware beaconed to c2.attacker.com."
    start = text.find("c2.attacker.com")
    ioc = IOC(
        id="ioc-3",
        type="domain",
        value="c2.attacker.com",
        display="c2[.]attacker[.]com",
        evidence=[Evidence(quote="c2.attacker.com", start=start, end=start + 15)],
    )
    tech = TechniqueMatch(
        technique_id="T1071.001",
        name="Web Protocols",
        tactics=["command-and-control"],
        status="rejected",
        reject_reason="verifier_mismatch",
        evidence=Evidence(quote=text, start=0, end=len(text)),
    )

    iocs, techs = link_iocs([ioc], [tech], text)
    assert techs[0].linked_iocs == []
    assert iocs[0].linked_techniques == []

