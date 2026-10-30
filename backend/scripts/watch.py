"""CLI script for running autonomous intel watch. Owner: Backend Core.

Usage:
  python scripts/watch.py --once
  python scripts/watch.py --interval 1800
"""
from __future__ import annotations

import argparse
import sys
import time

from app.pipeline.watch import run_once


def main():
    parser = argparse.ArgumentParser(description="TRINETRA Autonomous Intel Watch")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=1800, help="Check interval in seconds (default 1800)")
    parser.add_argument("--api", type=str, default="http://localhost:8000/api", help="TRINETRA API base URL")

    args = parser.parse_args()

    if args.once:
        print("[Watch] Running single cycle...")
        triggered = run_once(api_base=args.api)
        print(f"[Watch] Triggered {len(triggered)} new reports: {triggered}")
        return

    print(f"[Watch] Starting recurring watch every {args.interval} seconds...")
    while True:
        try:
            triggered = run_once(api_base=args.api)
            if triggered:
                print(f"[Watch] Triggered {len(triggered)} reports: {triggered}")
        except Exception as e:
            print(f"[Watch] Error during watch cycle: {e}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

