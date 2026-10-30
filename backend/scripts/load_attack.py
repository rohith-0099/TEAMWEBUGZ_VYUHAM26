"""CLI entry point for loading MITRE ATT&CK v20."""
from app.db import close_db, init_db
from app.attack.loader import load_attack


def main() -> None:
    try:
        init_db()
        load_attack()
    finally:
        close_db()


if __name__ == "__main__":
    main()
