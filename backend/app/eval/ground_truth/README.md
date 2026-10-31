# Ground truth

One `<slug>.json` per report. IDs are copied from the report's own ATT&CK technique tables and
never adjusted to improve a score.

    {
      "url": "https://www.cisa.gov/...",      // null for a local report
      "title": "...",
      "input": "samples/<file>.txt",          // optional: read this file instead of fetching url
      "answer_key": "...",                    // optional: where the answers come from
      "techniques": ["T1566.001", "..."],     // mapped to ATT&CK v20
      "dropped": [],                          // table IDs with no v20 equivalent
      "remapped": ["T1070.001->T1685.005"]    // optional: revoked IDs replaced by their v20 successor
    }

`scripts/run_eval.py` cuts ATT&CK tables, appendices and reference sections from the input and
deletes every remaining technique/tactic ID before scoring (`app/eval/metrics.py: strip_leakage`).
`--dry-run` checks ingestion and leakage removal without any LLM call.
