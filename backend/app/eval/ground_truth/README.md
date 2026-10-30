# Ground truth

One `<slug>.json` per CISA joint advisory, copied from the advisory's own ATT&CK tables:

    {"url": "https://www.cisa.gov/...", "title": "...", "techniques": ["T1566.001", "..."]}

Never adjust these to improve a score. `scripts/run_eval.py` maps old IDs to v20 and reports
any it has to drop.
