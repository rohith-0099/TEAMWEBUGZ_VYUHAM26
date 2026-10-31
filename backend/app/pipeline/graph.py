"""The LangGraph pipeline. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 3.

START → ingest → guard → {ioc, behaviours}
ioc → ioc_role ; behaviours → retrieve → verify
ioc → vulns (NVD + CISA KEV lookups, in parallel with the LLM stages)
[ioc_role, verify] → link → migrate → {tie, detect, memory}
tie → flow ; [flow, detect, memory, vulns] → brief → export → END

Every node is wrapped by stage(), which publishes SSE events, records timings and saves.
Nodes mutate the shared ReportAnalysis and write distinct fields, so parallel branches
never conflict. LangGraph runs in supersteps, so ioc has always finished before verify
starts and verify can read the IOCs. The runner sets status="done" and publishes
pipeline:done after END.
"""
import asyncio
import logging
import operator
import random
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app import db
from app.config import settings
from app.events import publish
from app.llm import begin_usage
from app.models import ImageInfo, Behaviour, Candidate, Detection, Evidence, ReportAnalysis, TechniqueMatch
from app.pipeline.behaviours import extract_behaviours
from app.pipeline.brief import build_briefing
from app.pipeline.detect import build_detections
from app.pipeline.flow import build_flow
from app.pipeline.guard import scan
from app.pipeline.ingest import IngestResult, ingest
from app.pipeline.ioc import extract_iocs
from app.pipeline.ocr import apply_ocr_trust, block_spans
from app.pipeline.ioc_role import label_roles
from app.pipeline.link import link_iocs
from app.pipeline.memory import write_memory
from app.pipeline.migrate import migrate
from app.pipeline.notify import notify
from app.pipeline.retrieve import explicit_ids, retrieve_candidates
from app.pipeline.tie import predict
from app.pipeline.verify import enforce_golden_rule, verify_all
from app.pipeline.vulns import enrich_cves

log = logging.getLogger(__name__)

SAVE_INTERVAL_S = 0.5


class State(TypedDict, total=False):
    analysis_id: str
    input: dict
    analysis: ReportAnalysis
    ingest_result: IngestResult  # not "ingest": LangGraph forbids a key named like a node
    candidates: dict[str, list[Candidate]]
    explicit: list[tuple[str, Evidence]]
    done: Annotated[list[str], operator.add]  # reducer: parallel nodes both append


_last_save: dict[str, float] = {}


async def _save_throttled(analysis: ReportAnalysis) -> None:
    now = time.monotonic()
    if now - _last_save.get(analysis.report_id, 0) < SAVE_INTERVAL_S:
        return
    _last_save[analysis.report_id] = now
    # Snapshot first: parallel stages keep mutating the live object during the save.
    await asyncio.to_thread(db.save_analysis, analysis.model_copy(deep=True))


# A stage body returns (done_data for the SSE event, extra state updates).
StageResult = tuple[dict, dict[str, Any]]


def stage(name: str, core: bool = False):
    """Wraps a node: started/done/error events + timing + save.

    A failing core stage aborts the pipeline; any other continues with empty output.
    """
    def decorator(fn: Callable[[State], Awaitable[StageResult]]):
        @wraps(fn)
        async def node(state: State) -> dict:
            analysis_id, analysis = state["analysis_id"], state["analysis"]
            await publish(analysis_id, name, "started")
            started = time.monotonic()
            usage = begin_usage()
            try:
                if not settings.llm_enabled:
                    # Offline mock mode is instant, so this keeps the UI animation visible.
                    await asyncio.sleep(random.uniform(0.3, 1.0))
                done_data, updates = await fn(state)
            except Exception as exc:
                log.exception("stage %s failed for %s", name, analysis_id)
                await publish(analysis_id, name, "error", {"message": str(exc)})
                if core:
                    raise
                return {"done": [name]}
            analysis.timings_ms[name] = int((time.monotonic() - started) * 1000)
            if usage.calls or usage.cached:
                log.info("stage %s: calls=%d cached=%d tokens_in=%d tokens_out=%d", name, usage.calls,
                         usage.cached, usage.prompt_tokens, usage.completion_tokens)
            if usage.errors:  # the stage finished, but some of its LLM calls failed: say which and why
                done_data = {**(done_data or {}), "llm_errors": usage.errors[:5], "llm_error_count": len(usage.errors)}
            await publish(analysis_id, name, "done", done_data)
            await _save_throttled(analysis)
            return {"done": [name], **updates}
        return node
    return decorator


def _dump(items: list) -> list[dict]:
    return [item.model_dump(mode="json") for item in items]


@stage("ingest", core=True)
async def ingest_node(state: State) -> StageResult:
    a = state["analysis"]

    async def on_image(info: dict) -> None:
        await publish(a.report_id, "ingest", "progress", {"image": info})

    result = await ingest(**state["input"], on_image=on_image)
    a.title, a.source_url = result.title, result.source_url
    a.published_at, a.text = result.published_at, result.text
    a.ocr_status = result.ocr_status
    spans = {n: (start, end) for n, start, end in block_spans(a.text)}
    a.images = [ImageInfo(**info, start=spans.get(info["index"], (None, None))[0],
                          end=spans.get(info["index"], (None, None))[1]) for info in result.images]
    return ({"title": a.title, "source_url": a.source_url,
             "published_at": a.published_at.isoformat() if a.published_at else None,
             "chars": len(a.text), "images": _dump(a.images), "ocr_status": a.ocr_status},
            {"ingest_result": result})


@stage("guard")
async def guard_node(state: State) -> StageResult:
    a = state["analysis"]
    a.injection_flags = await scan(state["ingest_result"].raw_text, a.text)
    if a.injection_flags:
        worst = a.injection_flags[0]
        await notify("injection_detected", {"report_id": a.report_id, "title": a.title,
                                            "technique_id": worst.technique_id,
                                            "flags": len(a.injection_flags)})
    return {"flags": _dump(a.injection_flags)}, {}


@stage("ioc", core=True)
async def ioc_node(state: State) -> StageResult:
    a = state["analysis"]
    a.iocs = extract_iocs(a.text, state["ingest_result"].publisher_domain)
    apply_ocr_trust(a.iocs, a.text)  # indicators seen only in image text are flagged for verification
    return {"iocs": _dump(a.iocs)}, {}


@stage("ioc_role")
async def ioc_role_node(state: State) -> StageResult:
    a = state["analysis"]
    a.iocs = await label_roles(a.text, a.iocs)
    return {"iocs": _dump(a.iocs)}, {}


@stage("behaviours", core=True)
async def behaviours_node(state: State) -> StageResult:
    a = state["analysis"]

    async def on_behaviour(b: Behaviour) -> None:
        await publish(a.report_id, "behaviours", "progress", {"behaviour": b.model_dump(mode="json")})

    a.behaviours = await extract_behaviours(a.text, on_behaviour)
    return {"count": len(a.behaviours)}, {}


@stage("retrieve", core=True)
async def retrieve_node(state: State) -> StageResult:
    a = state["analysis"]
    candidates = retrieve_candidates(a.behaviours)
    updates = {"candidates": candidates, "explicit": explicit_ids(a.text)}
    return {"candidates": sum(len(c) for c in candidates.values())}, updates


@stage("verify", core=True)
async def verify_node(state: State) -> StageResult:
    a = state["analysis"]

    async def on_result(t: TechniqueMatch) -> None:
        await publish(a.report_id, "verify", "progress", {"technique": t.model_dump(mode="json")})

    a.techniques = await verify_all(a.text, a.behaviours, state["candidates"], a.iocs,
                                    state["explicit"], on_result)
    accepted = sum(1 for t in a.techniques if t.status == "accepted")
    return {"accepted": accepted, "rejected": len(a.techniques) - accepted}, {}


@stage("link", core=True)
async def link_node(state: State) -> StageResult:
    a = state["analysis"]
    a.iocs, a.techniques = link_iocs(a.iocs, a.techniques, a.text)
    return {"techniques": _dump(a.techniques), "iocs": _dump(a.iocs)}, {}


@stage("migrate")
async def migrate_node(state: State) -> StageResult:
    a = state["analysis"]
    a.migrations = migrate(a.text, a.techniques)
    return {"migrations": _dump(a.migrations)}, {}


@stage("tie")
async def tie_node(state: State) -> StageResult:
    a = state["analysis"]
    observed = sorted({t.technique_id for t in a.techniques if t.status == "accepted"})
    a.predictions = predict(observed)
    return {"predictions": _dump(a.predictions)}, {}


@stage("flow")
async def flow_node(state: State) -> StageResult:
    a = state["analysis"]
    a.flow = build_flow(a.techniques, a.predictions)
    return {"flow": a.flow.model_dump(mode="json")}, {}


@stage("detect")
async def detect_node(state: State) -> StageResult:
    a = state["analysis"]

    async def on_detection(d: Detection) -> None:
        await publish(a.report_id, "detect", "progress", {"detection": d.model_dump(mode="json")})

    a.detections = await build_detections(a, on_detection)
    return {"count": len(a.detections)}, {}


@stage("memory")
async def memory_node(state: State) -> StageResult:
    a = state["analysis"]
    a.memory_alerts = await write_memory(a)
    return {"alerts": _dump(a.memory_alerts)}, {}


@stage("vulns")
async def vulns_node(state: State) -> StageResult:
    a = state["analysis"]
    a.vulnerabilities = await enrich_cves(a.iocs)
    return {"vulnerabilities": _dump(a.vulnerabilities)}, {}


@stage("brief")
async def brief_node(state: State) -> StageResult:
    a = state["analysis"]
    a.briefing = await build_briefing(a)
    return {"briefing": a.briefing.model_dump(mode="json") if a.briefing else None}, {}


@stage("export")
async def export_node(state: State) -> StageResult:
    if demoted := enforce_golden_rule(state["analysis"]):
        log.error("golden rule demoted %d accepted techniques in %s", demoted, state["analysis_id"])
    _last_save.pop(state["analysis_id"], None)
    return {"formats": ["stix", "navigator", "sigma", "flow"]}, {}


def build_graph():
    graph = StateGraph(State)
    nodes = {"ingest": ingest_node, "guard": guard_node, "ioc": ioc_node, "ioc_role": ioc_role_node,
             "behaviours": behaviours_node, "retrieve": retrieve_node, "verify": verify_node,
             "link": link_node, "migrate": migrate_node, "tie": tie_node, "flow": flow_node,
             "detect": detect_node, "memory": memory_node, "vulns": vulns_node, "brief": brief_node,
             "export": export_node}
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "guard")
    graph.add_edge("guard", "ioc")
    graph.add_edge("guard", "behaviours")
    graph.add_edge("ioc", "ioc_role")
    graph.add_edge("ioc", "vulns")
    graph.add_edge("behaviours", "retrieve")
    graph.add_edge("retrieve", "verify")
    graph.add_edge(["ioc_role", "verify"], "link")
    graph.add_edge("link", "migrate")
    graph.add_edge("migrate", "tie")
    graph.add_edge("migrate", "detect")
    graph.add_edge("migrate", "memory")
    graph.add_edge("tie", "flow")
    graph.add_edge(["flow", "detect", "memory", "vulns"], "brief")
    graph.add_edge("brief", "export")
    graph.add_edge("export", END)
    return graph.compile()


pipeline = build_graph()
