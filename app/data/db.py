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
    _ensure_wells_columns(conn)
    _ensure_hole_section_columns(conn)
    conn.commit()


def _ensure_wells_columns(conn: sqlite3.Connection) -> None:
    """
    Adds missing columns to wells for existing DBs.
    """
    rows = conn.execute("PRAGMA table_info(wells)").fetchall()
    existing = {row[1] for row in rows}

    if "step2_done" not in existing:
        conn.execute("ALTER TABLE wells ADD COLUMN step2_done INTEGER NOT NULL DEFAULT 0")
    if "step3_done" not in existing:
        conn.execute("ALTER TABLE wells ADD COLUMN step3_done INTEGER NOT NULL DEFAULT 0")

    if "section_template_key" not in existing:
        conn.execute("ALTER TABLE wells ADD COLUMN section_template_key TEXT NULL")
    if "sections_version" not in existing:
        conn.execute("ALTER TABLE wells ADD COLUMN sections_version INTEGER NULL")


def _ensure_hole_section_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(well_hole_section_data)").fetchall()
    if not rows:
        return
    existing = {row[1] for row in rows}

    if "info_casing_od" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN info_casing_od TEXT NULL")
    if "info_casing_id" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN info_casing_id TEXT NULL")
