"""Read-only query adapter for local DuckDB samples or Zetaris JDBC."""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_SAMPLE_CONNECTION = None


def _is_sample_mode() -> bool:
    return os.getenv("SAMPLE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def validate_read_query(sql: str) -> str:
    sql = sql.strip()
    # Permit one SELECT/WITH statement and a single optional trailing semicolon.
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    if (not re.match(r"^(SELECT|WITH)\b", sql, re.I) or ";" in sql or
            re.search(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|CALL|COPY|ATTACH|DETACH)\b", sql, re.I)):
        raise ValueError("Only one read-only SELECT/WITH statement is allowed")
    return sql


def run_query(sql: str, params=None) -> list[dict]:
    global _SAMPLE_CONNECTION
    sql = validate_read_query(sql)
    if _is_sample_mode():
        from whytrace.sample_data import get_connection
        if _SAMPLE_CONNECTION is None:
            _SAMPLE_CONNECTION = get_connection()
        cur = _SAMPLE_CONNECTION.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    import jaydebeapi  # optional dependency, loaded only for real mode
    required = ["ZETARIS_JDBC_URL", "ZETARIS_USERNAME", "ZETARIS_PASSWORD", "ZETARIS_JDBC_JAR"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing Zetaris configuration: " + ", ".join(missing))
    conn = jaydebeapi.connect(
        "com.zetaris.jdbc.Driver", os.environ["ZETARIS_JDBC_URL"],
        [os.environ["ZETARIS_USERNAME"], os.environ["ZETARIS_PASSWORD"]],
        os.environ["ZETARIS_JDBC_JAR"],
    )
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()
