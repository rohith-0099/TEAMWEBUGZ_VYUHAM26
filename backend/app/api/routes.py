"""All REST routes from contracts §8. Owner: Backend Core. See team/03_BACKEND_CORE.md Step 5."""
import asyncio
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app import db
from app.attack.store import get_technique_detail, list_tactics
from app.eval.store import latest_eval
from app.events import event_stream
from app.exports.flow_json import attack_flow_json
from app.exports.navigator import build_navigator_layer
from app.exports.sigma_export import sigma_yaml
from app.exports.stix import build_stix_bundle
from app.models import ReportAnalysis, Telemetry
from app.pipeline.detect import readiness
from app.pipeline.geo import geo_points
from app.pipeline.memory import get_graph
from app.pipeline.runner import start_analysis
from app.pipeline.simulate import simulate
from app.pipeline.verify import enforce_golden_rule
from app.sources import GLOSSARY, RULES, SOURCES

router = APIRouter()

MAX_PDF_BYTES = 20 * 1024 * 1024


class FeedbackRequest(BaseModel):
    target_type: Literal["technique", "ioc"]
    target_id: str
    verdict: Literal["accept", "reject"]
    note: str | None = None


class SimulateRequest(BaseModel):
    blocked_node_ids: list[str]


class ReadinessRequest(BaseModel):
    telemetry: list[Telemetry]


async def _get_or_404(analysis_id: str) -> ReportAnalysis:
    analysis = await asyncio.to_thread(db.get_analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, f"Analysis {analysis_id} not found")
    enforce_golden_rule(analysis)  # also covers analyses stored by older code
    return analysis


@router.get("/health")
async def health():
    count = await asyncio.to_thread(db.attack_technique_count)
    return {"ok": True, "attack_loaded": count > 0, "techniques": count}


@router.post("/analyses", status_code=202)
async def create_analysis(request: Request):
    url = text = pdf_bytes = filename = title = None
    if request.headers.get("content-type", "").startswith("multipart/"):
        form = await request.form()
        file = form.get("file")
        if file is None or isinstance(file, str):
            raise HTTPException(422, "Multipart requests need a 'file' field")
        filename = file.filename
        if not (filename or "").lower().endswith(".pdf"):
            raise HTTPException(422, "Only PDF uploads are supported")
        pdf_bytes = await file.read()
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise HTTPException(422, "PDF is larger than 20 MB")
    else:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(422, "Body must be JSON or multipart") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "Body must be a JSON object")
        url, text, title = body.get("url"), body.get("text"), body.get("title")
    if sum(1 for source in (url, text, pdf_bytes) if source) != 1:
        raise HTTPException(422, "Provide exactly one of url, text or file")
    return {"id": await start_analysis(url, text, pdf_bytes, filename, title)}


@router.get("/analyses")
async def list_all():
    return await asyncio.to_thread(db.list_analyses)


@router.get("/analyses/{analysis_id}")
async def get_one(analysis_id: str):
    return await _get_or_404(analysis_id)


@router.get("/analyses/{analysis_id}/events")
async def events(analysis_id: str):
    await _get_or_404(analysis_id)

    async def gen():
        async for event in event_stream(analysis_id):
            yield {"data": json.dumps(event, default=str)}

    return EventSourceResponse(gen(), ping=15)


@router.post("/analyses/{analysis_id}/feedback")
async def feedback(analysis_id: str, body: FeedbackRequest):
    await _get_or_404(analysis_id)
    await asyncio.to_thread(db.add_feedback, analysis_id, body.target_type, body.target_id,
                            body.verdict, body.note)
    return {"ok": True}


@router.post("/analyses/{analysis_id}/simulate")
async def simulate_route(analysis_id: str, body: SimulateRequest):
    return simulate(await _get_or_404(analysis_id), body.blocked_node_ids)


@router.post("/analyses/{analysis_id}/readiness")
async def readiness_route(analysis_id: str, body: ReadinessRequest):
    return readiness(await _get_or_404(analysis_id), list(body.telemetry))


@router.get("/analyses/{analysis_id}/export/{fmt}")
async def export(analysis_id: str, fmt: Literal["stix", "navigator", "sigma", "flow"],
                 include_predicted: bool = False):
    analysis = await _get_or_404(analysis_id)
    if analysis.status != "done":
        raise HTTPException(409, "Analysis is not finished yet")
    if fmt == "sigma":
        content, media_type, ext = sigma_yaml(analysis), "application/x-yaml", "yml"
    else:
        if fmt == "stix":
            payload = build_stix_bundle(analysis)
        elif fmt == "navigator":
            payload = build_navigator_layer(analysis, include_predicted)
        else:
            payload = attack_flow_json(analysis)
        content, media_type, ext = json.dumps(payload, indent=2), "application/json", "json"
    headers = {"Content-Disposition": f'attachment; filename="trinetra-{analysis_id}-{fmt}.{ext}"'}
    return Response(content, media_type=media_type, headers=headers)


@router.get("/analyses/{analysis_id}/geo")
async def geo(analysis_id: str):
    return geo_points(await _get_or_404(analysis_id))


@router.get("/graph")
async def graph(at: datetime | None = None, limit: int = 2000):
    return await asyncio.to_thread(get_graph, at, limit)


@router.get("/sources")
async def sources():
    return {"sources": SOURCES, "rules": RULES, "glossary": GLOSSARY}


@router.get("/attack/tactics")
async def tactics():
    return list_tactics()


@router.get("/attack/techniques/{technique_id}")
async def technique(technique_id: str):
    detail = get_technique_detail(technique_id)
    if detail is None:
        raise HTTPException(404, f"Technique {technique_id} not found")
    return detail


@router.get("/eval")
async def evaluation():
    result = await asyncio.to_thread(latest_eval)
    if result is None:
        raise HTTPException(404, "No evaluation has been run yet")
    return result
