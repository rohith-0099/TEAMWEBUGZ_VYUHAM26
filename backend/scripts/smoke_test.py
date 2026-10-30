"""End-to-end check: POST sample text, follow /events to pipeline:done, GET the analysis.

Usage: python scripts/smoke_test.py   (exit code != 0 on failure)
Owner: Lead. Only needs httpx, so it also runs outside the container.
"""
import json
import os
import sys

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
TIMEOUT_S = 180
STAGES = ["ingest", "guard", "ioc", "ioc_role", "behaviours", "retrieve", "verify", "link",
          "migrate", "tie", "flow", "detect", "memory", "export"]
SAMPLE_TEXT = ("The operators sent spearphishing emails, ran an encoded PowerShell command and "
               "beaconed to hxxp://evil[.]example/gate.php before encrypting files. " * 3)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=TIMEOUT_S) as client:
        response = client.post("/api/analyses", json={"text": SAMPLE_TEXT, "title": "Smoke test"})
        if response.status_code != 202:
            fail(f"POST /api/analyses returned {response.status_code}: {response.text}")
        analysis_id = response.json()["id"]
        print(f"analysis {analysis_id} started")

        done: dict[str, int] = {}
        errors: list[str] = []
        finished = None
        with client.stream("GET", f"/api/analyses/{analysis_id}/events") as stream:
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):])
                stage, status = event["stage"], event["status"]
                if stage == "pipeline" and status in ("done", "error"):
                    finished = event
                    break
                if status == "done":
                    done[stage] = event["elapsed_ms"]
                    print(f"  {stage:<11} done at {event['elapsed_ms']:>6} ms")
                elif status == "error":
                    errors.append(f"{stage}: {event['data']}")

        if finished is None:
            fail("event stream ended without pipeline:done")
        if finished["status"] == "error":
            fail(f"pipeline error: {finished['data']}")
        if errors:
            fail(f"stage errors: {errors}")
        missing = [s for s in STAGES if s not in done]
        if missing:
            fail(f"stages never reached done: {missing}")

        analysis = client.get(f"/api/analyses/{analysis_id}").json()
        if analysis["status"] != "done":
            fail(f"final status is {analysis['status']}")
        accepted = [t for t in analysis["techniques"] if t["status"] == "accepted"]
        for t in accepted:  # the golden rule: every accepted technique is proven by the source text
            evidence = t["evidence"]
            if evidence is None or analysis["text"][evidence["start"]:evidence["end"]] != evidence["quote"]:
                fail(f"{t['technique_id']} has evidence that is not in the report")
        print(f"OK: {len(done)}/{len(STAGES)} stages done | title={analysis['title']!r} | "
              f"iocs={len(analysis['iocs'])} behaviours={len(analysis['behaviours'])} "
              f"techniques={len(accepted)} accepted/{len(analysis['techniques'])} total "
              f"predictions={len(analysis['predictions'])} detections={len(analysis['detections'])} "
              f"alerts={len(analysis['memory_alerts'])} migrations={len(analysis['migrations'])}")


if __name__ == "__main__":
    main()
