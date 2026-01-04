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
    if "bit1_brand" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit1_brand TEXT NULL")
    if "bit1_kind" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit1_kind TEXT NULL")
    if "bit1_type" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit1_type TEXT NULL")
    if "bit1_iadc" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit1_iadc TEXT NULL")
    if "bit1_serial" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit1_serial TEXT NULL")
    if "bit2_brand" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit2_brand TEXT NULL")
    if "bit2_kind" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit2_kind TEXT NULL")
    if "bit2_type" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit2_type TEXT NULL")
    if "bit2_iadc" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit2_iadc TEXT NULL")
    if "bit2_serial" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN bit2_serial TEXT NULL")
    if "mud_motor1_brand" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_brand TEXT NULL")
    if "mud_motor1_size" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_size TEXT NULL")
    if "mud_motor1_sleeve_stb_gauge_in" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_sleeve_stb_gauge_in REAL NULL")
    if "mud_motor1_bend_angle_deg" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_bend_angle_deg TEXT NULL")
    if "mud_motor1_lobe" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_lobe TEXT NULL")
    if "mud_motor1_stage" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_stage TEXT NULL")
    if "mud_motor1_ibs_gauge_in" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor1_ibs_gauge_in REAL NULL")
    if "mud_motor2_brand" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_brand TEXT NULL")
    if "mud_motor2_size" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_size TEXT NULL")
    if "mud_motor2_sleeve_stb_gauge_in" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_sleeve_stb_gauge_in REAL NULL")
    if "mud_motor2_bend_angle_deg" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_bend_angle_deg TEXT NULL")
    if "mud_motor2_lobe" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_lobe TEXT NULL")
    if "mud_motor2_stage" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_stage TEXT NULL")
    if "mud_motor2_ibs_gauge_in" not in existing:
        conn.execute("ALTER TABLE well_hole_section_data ADD COLUMN mud_motor2_ibs_gauge_in REAL NULL")

    personnel_cols = [
        "personnel_day_dd_1",
        "personnel_day_dd_2",
        "personnel_day_dd_3",
        "personnel_night_dd_1",
        "personnel_night_dd_2",
        "personnel_night_dd_3",
        "personnel_day_mwd_1",
        "personnel_day_mwd_2",
        "personnel_day_mwd_3",
        "personnel_night_mwd_1",
        "personnel_night_mwd_2",
        "personnel_night_mwd_3",
    ]
    for col in personnel_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE well_hole_section_data ADD COLUMN {col} TEXT NULL")

    ta_cols = [
        "ta_standby_time_hrs_run1",
        "ta_standby_time_hrs_run2",
        "ta_standby_time_hrs_run3",
        "ta_ru_time_hrs_run1",
        "ta_ru_time_hrs_run2",
        "ta_ru_time_hrs_run3",
        "ta_tripping_time_hrs_run1",
        "ta_tripping_time_hrs_run2",
        "ta_tripping_time_hrs_run3",
        "ta_circulation_time_hrs_run1",
        "ta_circulation_time_hrs_run2",
        "ta_circulation_time_hrs_run3",
        "ta_rotary_time_hrs_run1",
        "ta_rotary_time_hrs_run2",
        "ta_rotary_time_hrs_run3",
        "ta_rotary_meters_run1",
        "ta_rotary_meters_run2",
        "ta_rotary_meters_run3",
        "ta_sliding_time_hrs_run1",
        "ta_sliding_time_hrs_run2",
        "ta_sliding_time_hrs_run3",
        "ta_sliding_meters_run1",
        "ta_sliding_meters_run2",
        "ta_sliding_meters_run3",
        "ta_npt_due_to_rig_hrs_run1",
        "ta_npt_due_to_rig_hrs_run2",
        "ta_npt_due_to_rig_hrs_run3",
        "ta_npt_due_to_motor_hrs_run1",
        "ta_npt_due_to_motor_hrs_run2",
        "ta_npt_due_to_motor_hrs_run3",
        "ta_npt_due_to_mwd_hrs_run1",
        "ta_npt_due_to_mwd_hrs_run2",
        "ta_npt_due_to_mwd_hrs_run3",
        "ta_brt_hrs_run1",
        "ta_brt_hrs_run2",
        "ta_brt_hrs_run3",
    ]
    for col in ta_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE well_hole_section_data ADD COLUMN {col} REAL NULL")

    _ensure_nozzle_table(conn)


def _ensure_nozzle_table(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(well_hse_nozzle)").fetchall()
    if not rows:
        return
    existing = {row[1] for row in rows}
    if "bit_index" in existing:
        return

    conn.execute(
        """
        CREATE TABLE well_hse_nozzle_new (
          well_id TEXT NOT NULL,
          hole_key TEXT NOT NULL,
          bit_index INTEGER NOT NULL,
          line_no INTEGER NOT NULL,
          count INTEGER NOT NULL,
          size_32nds INTEGER NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY (well_id, hole_key, bit_index, line_no),
          FOREIGN KEY (well_id) REFERENCES wells(well_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO well_hse_nozzle_new
          (well_id, hole_key, bit_index, line_no, count, size_32nds, updated_at)
        SELECT well_id, hole_key, 1, line_no, count, size_32nds, updated_at
        FROM well_hse_nozzle
        """
    )
    conn.execute("DROP TABLE well_hse_nozzle")
    conn.execute("ALTER TABLE well_hse_nozzle_new RENAME TO well_hse_nozzle")
