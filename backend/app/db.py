"""Postgres access: plain functions, plain SQL. Owner: Backend Core. See team/03_BACKEND_CORE.md.

Functions are sync; call them from async code via asyncio.to_thread.
"""
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from app.config import settings
from app.models import ReportAnalysis


def _configure(conn):
    # The vector type exists because init_db runs schema.sql before opening the pool.
    register_vector(conn)
    conn.commit()  # the pool rejects connections left inside a transaction


pool = ConnectionPool(settings.database_url, min_size=1, max_size=10,
                      kwargs={"row_factory": dict_row}, configure=_configure, open=False)


def init_db() -> None:
    sql = (Path(__file__).parent.parent / "db" / "schema.sql").read_text()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute(sql)
    pool.open(wait=True)


def close_db() -> None:
    pool.close()


def create_analysis(analysis_id: str, title: str, source_url: str | None) -> None:
    # result starts as a valid ReportAnalysis so GET works before the first stage saves.
    initial = ReportAnalysis(report_id=analysis_id, title=title, source_url=source_url)
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO analyses (id, title, source_url, result) VALUES (%s, %s, %s, %s)",
            (analysis_id, title, source_url, Jsonb(initial.model_dump(mode="json"))),
        )


def save_analysis(a: ReportAnalysis) -> None:
    with pool.connection() as conn:
        conn.execute(
            """UPDATE analyses SET title=%s, source_url=%s, published_at=%s, status=%s,
                   updated_at=now(), result=%s WHERE id=%s""",
            (a.title, a.source_url, a.published_at, a.status,
             Jsonb(a.model_dump(mode="json")), a.report_id),
        )


def get_analysis(analysis_id: str) -> ReportAnalysis | None:
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT result, created_at FROM analyses WHERE id=%s", (analysis_id,)
        ).fetchone()
    if row is None:
        return None
    a = ReportAnalysis.model_validate(row["result"])
    a.created_at = a.created_at or row["created_at"]
    return a


def list_analyses(limit: int = 50) -> list[dict]:
    """AnalysisListItem shape (contracts §8), newest first."""
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT id, title, source_url, published_at, created_at, status, result
               FROM analyses ORDER BY created_at DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    items = []
    for r in rows:
        result = r["result"]
        items.append({
            "report_id": r["id"],
            "title": r["title"],
            "source_url": r["source_url"],
            "published_at": r["published_at"],
            "created_at": r["created_at"],
            "status": r["status"],
            "counts": {
                "iocs": sum(1 for i in result.get("iocs", []) if not i.get("filtered_reason")),
                "techniques": sum(1 for t in result.get("techniques", []) if t.get("status") == "accepted"),
                "alerts": len(result.get("memory_alerts", [])),
            },
        })
    return items


def add_feedback(analysis_id: str, target_type: str, target_id: str, verdict: str,
                 note: str | None) -> None:
    with pool.connection() as conn:
        conn.execute(
            """INSERT INTO feedback (analysis_id, target_type, target_id, verdict, note)
               VALUES (%s, %s, %s, %s, %s)""",
            (analysis_id, target_type, target_id, verdict, note),
        )


def attack_technique_count() -> int:
    with pool.connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM attack_techniques").fetchone()["n"]
