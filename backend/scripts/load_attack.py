"""CLI entry point for loading MITRE ATT&CK v20."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `app` imports from scripts/

from app.db import close_db, init_db  # noqa: E402
from app.attack.loader import load_attack  # noqa: E402


def main() -> None:
    try:
        init_db()
        load_attack()
    finally:
        close_db()


if __name__ == "__main__":
    main()
