import yaml

from app.config import settings
from app.exports.sigma_export import sigma_yaml
from app.models import (
    IOC, Analytic, Confidence, Detection, DetectionStrategy, Evidence, LogSource, ReportAnalysis, TechniqueMatch,
)
from app.pipeline import detect, sigma
from app.pipeline.detect import readiness, telemetry_for


def ls(name, component=None):
    return LogSource(name=name, data_component=component)


def test_telemetry_mapping_table():
    assert telemetry_for(ls("WinEventLog:Microsoft-Windows-PowerShell/Operational")) == {"powershell_scriptblock"}
    assert telemetry_for(ls("WinEventLog:Security", "Process Creation")) == {"windows_security", "sysmon", "edr"}
    assert telemetry_for(ls("x", "Network Traffic Flow")) == {"netflow", "firewall"}
    assert telemetry_for(ls("x", "Domain Name")) == {"dns"}
    assert telemetry_for(ls("mystery source")) == set()


def test_auditd_is_not_mistaken_for_cloud_audit():
    assert telemetry_for(ls("auditd:SYSCALL")) == {"linux_auditd"}


def test_email_bucket_for_phishing_application_logs_only():
    source = ls("x", "Application Log Content")
    assert "email_gateway" in telemetry_for(source, "T1566.001")
    assert "email_gateway" not in telemetry_for(source, "T1059")


def det(tid, *analytics):
    strategies = [DetectionStrategy(id="d", name="d", analytics=[
        Analytic(id=str(i), name="a", log_sources=sources) for i, sources in enumerate(analytics)])]
    required = sorted({b for sources in analytics for s in sources for b in telemetry_for(s)})
    return Detection(technique_id=tid, technique_name=tid, strategies=strategies, required_telemetry=required)


POWERSHELL = ls("WinEventLog:Microsoft-Windows-PowerShell/Operational")
PROXY = ls("proxy logs")


def test_readiness_flips_when_powershell_logging_is_removed():
    a = ReportAnalysis(report_id="r", detections=[det("T1059.001", [POWERSHELL])])
    assert readiness(a, ["powershell_scriptblock"])["per_technique"][0]["status"] == "covered"
    gone = readiness(a, ["dns"])
    assert gone["per_technique"][0]["status"] == "gap" and gone["readiness_pct"] == 0
    assert gone["per_technique"][0]["missing"] == ["powershell_scriptblock"]


def test_analytic_needs_all_of_its_log_sources():
    a = ReportAnalysis(report_id="r", detections=[det("T1", [POWERSHELL, PROXY])])
    assert readiness(a, ["proxy"])["per_technique"][0]["status"] == "partial"
    assert readiness(a, ["proxy", "powershell_scriptblock"])["per_technique"][0]["status"] == "covered"


def test_any_satisfied_analytic_is_enough():
    a = ReportAnalysis(report_id="r", detections=[det("T1", [POWERSHELL], [PROXY])])
    assert readiness(a, ["proxy"])["per_technique"][0]["status"] == "covered"


def test_readiness_percentage():
    a = ReportAnalysis(report_id="r", detections=[
        det("T1", [PROXY]), det("T2", [POWERSHELL, PROXY]), det("T3", [POWERSHELL])])
    assert readiness(a, ["proxy"])["readiness_pct"] == 50  # (1 + 0.5 + 0) / 3


def test_technique_without_detections_is_a_gap_and_empty_report_is_safe():
    a = ReportAnalysis(report_id="r", detections=[Detection(technique_id="T1", technique_name="x")])
    assert readiness(a, ["proxy"])["per_technique"][0]["status"] == "gap"
    assert readiness(ReportAnalysis(report_id="r"), [])["readiness_pct"] == 0


def _ioc(i, kind, value, linked=("T1071.001",), filtered=None):
    return IOC(id=f"ioc-{i}", type=kind, value=value, display=value, linked_techniques=list(linked),
               filtered_reason=filtered)


def _analysis(*iocs):
    return ReportAnalysis(report_id="r", title="Sample report", source_url="https://intel.example/r",
                          iocs=list(iocs), techniques=[TechniqueMatch(
                              technique_id="T1071.001", name="Web Protocols", tactics=["command-and-control"],
                              status="accepted", evidence=Evidence(quote="q", start=0, end=1),
                              confidence=Confidence(mapping=0.9))])


async def test_every_ioc_family_yields_a_valid_rule(fake_store, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    a = _analysis(_ioc(1, "domain", "evil.example"), _ioc(2, "ipv4", "203.0.113.9"),
                  _ioc(3, "url", "https://evil.example/gate.php?id=1"), _ioc(4, "sha256", "a" * 64))
    rules = await sigma.build_rules(a, "T1071.001", Detection(technique_id="T1071.001", technique_name="Web"))
    assert len(rules) == 4
    for rule in rules:
        assert rule.valid, rule.errors
        assert "splunk" in rule.conversions
        parsed = yaml.safe_load(rule.yaml)
        assert parsed["tags"] == ["attack.t1071.001"] and parsed["author"] == "TRINETRA"


async def test_filtered_and_unlinked_iocs_get_no_rule(fake_store, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    a = _analysis(_ioc(1, "domain", "ok.example", filtered="benign_domain"),
                  _ioc(2, "domain", "other.example", linked=("T1486",)))
    assert await sigma.build_rules(a, "T1071.001", Detection(technique_id="T1071.001", technique_name="W")) == []


async def test_url_wildcards_are_escaped(fake_store, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    a = _analysis(_ioc(1, "url", "https://evil.example/a?b=1"))
    [rule] = await sigma.build_rules(a, "T1071.001", Detection(technique_id="T1071.001", technique_name="W"))
    assert rule.valid and "\\?" in yaml.safe_load(rule.yaml)["detection"]["selection"]["c-uri|contains"][0]


def test_validate_rejects_garbage():
    assert sigma.validate("title: only a title")[0] is False
    assert sigma.validate(": : not yaml : :\n  - [")[0] is False


def _behaviour_setup(monkeypatch, replies):
    calls = []

    async def complete_json(system, user, schema, model="extract", **kw):
        calls.append(user)
        return schema(sigma_yaml=replies.pop(0))

    monkeypatch.setattr(sigma, "complete_json", complete_json)
    detection = Detection(technique_id="T1071.001", technique_name="Web", strategies=[
        DetectionStrategy(id="d", name="d", analytics=[Analytic(id="a", name="a", platforms=["Windows"])])])
    return calls, detection


GOOD_RULE = """title: Beacon
status: experimental
logsource:
  category: proxy
detection:
  selection:
    c-uri|contains: gate
  condition: selection
level: high
"""


async def test_behaviour_rule_is_repaired_once(fake_store, llm_on, monkeypatch):
    calls, detection = _behaviour_setup(monkeypatch, ["title: broken", GOOD_RULE])
    [rule] = await sigma.build_rules(_analysis(), "T1071.001", detection)
    assert rule.valid and rule.kind == "behaviour" and rule.title == "Beacon" and len(calls) == 2
    assert "failed validation" in calls[1]


async def test_unrepairable_rule_stays_marked_invalid_and_is_not_exported(fake_store, llm_on, monkeypatch):
    calls, detection = _behaviour_setup(monkeypatch, ["title: broken", "title: still broken"])
    [rule] = await sigma.build_rules(_analysis(), "T1071.001", detection)
    assert rule.valid is False and rule.errors
    detection.sigma = [rule]
    assert sigma_yaml(ReportAnalysis(report_id="r", detections=[detection])) == ""


async def test_build_detections_reports_each_and_keeps_order(fake_store, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(detect, "_legacy_strategies", lambda tid: [])
    seen = []

    async def on_detection(d):
        seen.append(d.technique_id)

    a = _analysis(_ioc(1, "domain", "evil.example"))
    result = await detect.build_detections(a, on_detection)
    assert [d.technique_id for d in result] == ["T1071.001"] == seen
    assert result[0].sigma[0].valid
