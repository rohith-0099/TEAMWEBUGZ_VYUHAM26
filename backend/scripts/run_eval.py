"""Writes the real scoreboard to eval_runs. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 11.

Needs the real pipeline, loaded ATT&CK data, an LLM key and app/eval/ground_truth/*.json.
Usage: python scripts/run_eval.py
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `app` imports from scripts/

from app import db  # noqa: E402
from app.attack import store  # noqa: E402
from app.config import settings  # noqa: E402
from app.eval.metrics import micro_average, score_report, strip_leakage  # noqa: E402
from app.eval.store import save_eval  # noqa: E402
from app.llm import UNTRUSTED_RULE, complete_json, wrap_report  # noqa: E402
from app.pipeline.ingest import ingest  # noqa: E402
from app.pipeline.runner import run_pipeline  # noqa: E402

GROUND_TRUTH = Path(__file__).resolve().parent.parent / "app" / "eval" / "ground_truth"
BASELINE_SYSTEM = ("List every MITRE ATT&CK Enterprise technique ID the report describes. "
                   + UNTRUSTED_RULE)


class _Baseline(BaseModel):
    techniques: list[str]


def _to_v20(ids: list[str]) -> set[str]:
    current: set[str] = set()
    for tid in ids:
        if store.technique_exists(tid):
            current.add(tid)
            continue
        replacements = [r for r in store.get_revocation(tid) if store.technique_exists(r)]
        if not replacements:
            print(f"  dropped {tid}: not in v20 and no replacement")
        current.update(replacements)
    return current


async def _run_trinetra(text: str, title: str) -> tuple[set[str], int]:
    analysis_id = f"eval-{uuid4().hex[:8]}"
    await asyncio.to_thread(db.create_analysis, analysis_id, title, None)
    started = time.monotonic()
    await run_pipeline(analysis_id, {"url": None, "text": text, "pdf_bytes": None,
                                     "filename": None, "title": title})
    latency = int((time.monotonic() - started) * 1000)
    analysis = await asyncio.to_thread(db.get_analysis, analysis_id)
    if analysis.status != "done":
        raise RuntimeError(f"pipeline failed on {title}: {analysis.error}")
    return {t.technique_id for t in analysis.techniques if t.status == "accepted"}, latency


async def main() -> int:
    files = sorted(GROUND_TRUTH.glob("*.json"))
    if not files:
        print(f"No ground truth in {GROUND_TRUTH}; nothing to evaluate.")
        return 1
    if not settings.llm_api_key:
        print("LLM_API_KEY is empty; refusing to score mock output.")
        return 1

    db.init_db()
    per_report, baseline_pairs, trinetra_pairs = [], [], []
    baseline_ms, trinetra_ms = [], []
    for path in files:
        gt = json.loads(path.read_text())
        print(f"{path.stem}: {gt['title']}")
        truth = _to_v20(gt["techniques"])
        ingested = await ingest(url=gt["url"], title=gt["title"])
        text = strip_leakage(ingested.text)

        started = time.monotonic()
        baseline = await complete_json(BASELINE_SYSTEM, wrap_report(text), _Baseline, cache=False)
        baseline_ms.append(int((time.monotonic() - started) * 1000))
        baseline_ids = {t.strip().upper() for t in baseline.techniques}

        trinetra_ids, latency = await _run_trinetra(text, gt["title"])
        trinetra_ms.append(latency)

        baseline_pairs.append((truth, baseline_ids))
        trinetra_pairs.append((truth, trinetra_ids))
        per_report.append({"report_id": path.stem, "title": gt["title"], "url": gt["url"],
                           "baseline": score_report(truth, baseline_ids),
                           "trinetra": score_report(truth, trinetra_ids)})

    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(), "reports": len(files),
        "systems": [
            {"system": "baseline", **micro_average(baseline_pairs),
             "avg_latency_ms": sum(baseline_ms) // len(files)},
            {"system": "trinetra", **micro_average(trinetra_pairs),
             "avg_latency_ms": sum(trinetra_ms) // len(files)},
        ],
        "per_report": per_report,
    }
    save_eval(payload)
    print(json.dumps(payload["systems"], indent=2))
    db.close_db()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
