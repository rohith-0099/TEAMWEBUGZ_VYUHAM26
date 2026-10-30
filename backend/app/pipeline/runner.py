"""Starts analyses in the background. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 3."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app import db
from app.events import publish
from app.models import ReportAnalysis
from app.pipeline.graph import pipeline
from app.pipeline.notify import notify

_tasks: set[asyncio.Task] = set()  # strong refs, otherwise tasks can be garbage collected


async def start_analysis(url: str | None, text: str | None, pdf_bytes: bytes | None,
                         filename: str | None, title: str | None) -> str:
    """Creates the analysis, runs the pipeline in the background and returns its id at once."""
    analysis_id = uuid4().hex[:12]
    await asyncio.to_thread(db.create_analysis, analysis_id, title or "", url)
    # Open the channel now: a client that connects to /events immediately sees a live stream.
    await publish(analysis_id, "pipeline", "started")
    pipeline_input = {"url": url, "text": text, "pdf_bytes": pdf_bytes,
                      "filename": filename, "title": title}
    task = asyncio.create_task(run_pipeline(analysis_id, pipeline_input))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return analysis_id


async def run_pipeline(analysis_id: str, pipeline_input: dict) -> None:
    analysis = ReportAnalysis(report_id=analysis_id, title=pipeline_input["title"] or "",
                              source_url=pipeline_input["url"],
                              created_at=datetime.now(timezone.utc))
    try:
        await pipeline.ainvoke({"analysis_id": analysis_id, "input": pipeline_input,
                                "analysis": analysis, "done": []})
    except Exception as exc:  # core stage failed, or a bug in the graph itself
        analysis.status = "error"
        analysis.error = str(exc)
        await asyncio.to_thread(db.save_analysis, analysis)
        await publish(analysis_id, "pipeline", "error", {"message": str(exc)})
        return
    analysis.status = "done"
    await asyncio.to_thread(db.save_analysis, analysis)
    await publish(analysis_id, "pipeline", "done", {"report_id": analysis_id})
    await notify("analysis_done", {"report_id": analysis_id, "title": analysis.title})
