"""Evaluation results. Owner: Lead. See team/05_LEAD_ARCHITECT.md section 11."""
from psycopg.types.json import Jsonb

from app import db


def save_eval(payload: dict) -> None:
    with db.pool.connection() as conn:
        conn.execute("INSERT INTO eval_runs (payload) VALUES (%s)", (Jsonb(payload),))


def latest_eval() -> dict | None:
    """The newest EvalResponse, or None until run_eval.py has really been run."""
    with db.pool.connection() as conn:
        row = conn.execute("SELECT payload FROM eval_runs ORDER BY ran_at DESC, id DESC LIMIT 1").fetchone()
    return row["payload"] if row else None
