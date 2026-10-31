"""Writes the real scoreboard to eval_runs. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 11.

Needs the real pipeline, loaded ATT&CK data, an LLM key and app/eval/ground_truth/*.json.
Usage: python scripts/run_eval.py [--dry-run]
  --dry-run  ingest and strip leakage only: no LLM calls, nothing saved
"""
import asyncio
import json
import logging
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
from app.eval.metrics import LEAKAGE_RULE, micro_average, score_report, strip_leakage  # noqa: E402
from app.eval.metrics import TACTIC_ID, TECHNIQUE_ID  # noqa: E402
from app.eval.store import save_eval  # noqa: E402
from app.llm import UNTRUSTED_RULE, LLMError, complete_json, provider_of, wrap_report  # noqa: E402
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


class _FailedCalls(logging.Handler):
    """Collects every failed LLM call during one pipeline run (llm.py logs each as a warning)."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


async def _run_trinetra(text: str, title: str) -> tuple[set[str], int]:
    """Accepted techniques and latency. A run where any LLM call failed is incomplete, so it raises:
    scoring it would count unverified behaviours as misses."""
    failed = _FailedCalls()
    logging.getLogger("app.llm").addHandler(failed)
    try:
        ids, latency = await _run_pipeline_once(text, title)
    finally:
        logging.getLogger("app.llm").removeHandler(failed)
    if failed.messages:
        raise RuntimeError(f"{len(failed.messages)} LLM call(s) failed during the pipeline run, so the result "
                           f"would be partial. First: {failed.messages[0][:250]}")
    return ids, latency


async def _run_pipeline_once(text: str, title: str) -> tuple[set[str], int]:
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


async def main(dry_run: bool = False) -> int:
    files = sorted(GROUND_TRUTH.glob("*.json"))
    if not files:
        print(f"No ground truth in {GROUND_TRUTH}; nothing to evaluate.")
        return 1
    if not settings.llm_enabled and not dry_run:
        print("No LLM API key is set; refusing to score mock output.")
        return 1

    db.init_db()
    per_report, skipped, baseline_pairs, trinetra_pairs = [], [], [], []
    baseline_ms, trinetra_ms = [], []
    for path in files:
        gt = json.loads(path.read_text())
        print(f"{path.stem}: {gt['title']}")
        truth = _to_v20(gt["techniques"])
        if gt.get("input"):  # a local report (the test report has no public URL)
            raw = (GROUND_TRUTH.parent / gt["input"]).read_text()
        else:
            raw = (await ingest(url=gt["url"], title=gt["title"])).text
        text = strip_leakage(raw)
        leaked = TECHNIQUE_ID.findall(text) + TACTIC_ID.findall(text)
        if leaked:
            raise RuntimeError(f"{path.stem}: IDs left after leakage removal: {leaked[:5]}")
        print(f"  {len(raw)} chars ingested, {len(text)} after leakage removal; truth {len(truth)} techniques")
        if dry_run:
            continue

        # A report that doesn't fit a provider's quota is skipped and reported, never scored partially.
        try:
            started = time.monotonic()
            baseline = await complete_json(BASELINE_SYSTEM, wrap_report(text), _Baseline, cache=False)
            baseline_latency = int((time.monotonic() - started) * 1000)
            trinetra_ids, latency = await _run_trinetra(text, gt["title"])
        except (LLMError, RuntimeError) as exc:
            reason = str(exc)[:400]
            print(f"  SKIPPED: {reason}")
            skipped.append({"report_id": path.stem, "title": gt["title"], "url": gt.get("url"), "reason": reason})
            continue
        baseline_ms.append(baseline_latency)
        trinetra_ms.append(latency)
        baseline_ids = {t.strip().upper() for t in baseline.techniques}

        baseline_pairs.append((truth, baseline_ids))
        trinetra_pairs.append((truth, trinetra_ids))
        per_report.append({"report_id": path.stem, "title": gt["title"], "url": gt.get("url"),
                           "answer_key": gt.get("answer_key", "ATT&CK technique tables in the advisory"),
                           "truth_count": len(truth), "dropped": gt.get("dropped", []),
                           "remapped": gt.get("remapped", []), "input_chars": len(text),
                           "baseline": score_report(truth, baseline_ids),
                           "trinetra": score_report(truth, trinetra_ids)})

    if dry_run:
        print("Dry run: nothing scored or saved.")
        return 0
    if not per_report:
        print("Every report was skipped; nothing saved.", json.dumps(skipped, indent=2))
        return 1
    scored = len(per_report)
    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(), "reports": scored,
        "models": {"extract": settings.llm_extract_model, "verify": settings.llm_verify_model},
        "providers": {"extract": provider_of(settings.llm_extract_model),
                      "verify": provider_of(settings.llm_verify_model)},
        "skipped": skipped,
        "leakage_rule": LEAKAGE_RULE,
        "baseline_method": "One LLM call (same extract model) asked to list every ATT&CK technique ID the "
                           "report describes. No retrieval and no verification.",
        "trinetra_method": "The full pipeline; only accepted, observed techniques count (predictions excluded).",
        "systems": [
            {"system": "baseline", **micro_average(baseline_pairs),
             "avg_latency_ms": sum(baseline_ms) // scored},
            {"system": "trinetra", **micro_average(trinetra_pairs),
             "avg_latency_ms": sum(trinetra_ms) // scored},
        ],
        "per_report": per_report,
    }
    save_eval(payload)
    print(json.dumps({k: payload[k] for k in ("models", "systems", "skipped")}, indent=2))
    db.close_db()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(dry_run="--dry-run" in sys.argv)))
