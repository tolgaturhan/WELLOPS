from __future__ import annotations

import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "wellops.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """
    Returns a SQLite connection and ensures schema is applied.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    _ensure_schema(conn)

    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Applies schema.sql once (idempotent because schema uses IF NOT EXISTS).
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema.sql not found: {SCHEMA_PATH}")

    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Runs all CREATE TABLE/INDEX statements
    conn.executescript(sql)
    conn.commit()