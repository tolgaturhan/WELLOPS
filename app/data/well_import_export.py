# app/data/well_import_export.py
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.data.db import DB_PATH, SCHEMA_PATH, SCHEMA_VERSION, get_connection


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def _get_meta(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute(
        "SELECT meta_value FROM app_meta WHERE meta_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return ""
    return str(row["meta_value"] or "")


def _ensure_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
          meta_key TEXT PRIMARY KEY,
          meta_value TEXT NOT NULL
        )
        """
    )
    row = conn.execute(
        "SELECT meta_value FROM app_meta WHERE meta_key = 'schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO app_meta (meta_key, meta_value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )


def _fetch_rows(
    conn: sqlite3.Connection, table: str, where: str, params: Tuple[Any, ...]
) -> List[Dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table} WHERE {where}", params).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def _insert_rows(
    conn: sqlite3.Connection, table: str, rows: Iterable[Dict[str, Any]]
) -> None:
    rows = list(rows)
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    conn.executemany(sql, [[r.get(c) for c in cols] for r in rows])


def export_well_to_db(well_id: str, dest_path: str) -> None:
    wid = (well_id or "").strip()
    if not wid:
        raise ValueError("well_id is required")

    out_path = Path(dest_path)
    if out_path.exists():
        raise ValueError("Export file already exists. Please choose another path.")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with get_connection() as src, _open_db(out_path) as dst:
        dst.executescript(schema_sql)
        _ensure_meta(dst)
        dst.execute(
            "UPDATE app_meta SET meta_value = ? WHERE meta_key = ?",
            (SCHEMA_VERSION, "schema_version"),
        )

        tables = [
            "wells",
            "well_identity",
            "well_trajectory",
            "well_section_nodes",
            "well_hole_sections",
            "well_hole_section_data",
            "well_hse_ticket",
            "well_hse_nozzle",
        ]

        for table in tables:
            src_cols = set(_table_columns(src, table))
            dst_cols = _table_columns(dst, table)
            cols = [c for c in dst_cols if c in src_cols]
            if not cols:
                continue
            rows = _fetch_rows(src, table, "well_id = ?", (wid,))
            if not rows:
                continue
            filtered = [{k: r.get(k) for k in cols} for r in rows]
            _insert_rows(dst, table, filtered)

        dst.commit()


def import_well_from_db(src_path: str) -> Tuple[str, str]:
    path = Path(src_path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {src_path}")

    with _open_db(path) as src:
        _ensure_meta(src)
        wells_rows = src.execute("SELECT * FROM wells").fetchall()
        if len(wells_rows) != 1:
            raise ValueError("Import file must contain exactly one well.")
        src_well = {k: wells_rows[0][k] for k in wells_rows[0].keys()}

        src_well_id = str(src_well.get("well_id") or "")
        src_well_name = str(src_well.get("well_name") or "").strip()
        if not src_well_name:
            raise ValueError("Imported well has no name.")

        with get_connection() as dst:
            _ensure_meta(dst)
            row = dst.execute(
                "SELECT well_id FROM wells WHERE well_name = ?",
                (src_well_name,),
            ).fetchone()
            if row is None:
                new_id = str(uuid.uuid4())
                _insert_new_well(dst, new_id, src_well)
                _copy_well_data(src, dst, src_well_id, new_id, merge=False)
                dst.commit()
                return new_id, src_well_name

            dest_well_id = str(row["well_id"])
            _merge_well(dst, dest_well_id, src_well)
            _copy_well_data(src, dst, src_well_id, dest_well_id, merge=True)
            dst.commit()
            return dest_well_id, src_well_name


def preview_import(src_path: str) -> Dict[str, Any]:
    path = Path(src_path)
    if not path.exists():
        raise FileNotFoundError(f"Import file not found: {src_path}")

    with _open_db(path) as src, get_connection() as dst:
        _ensure_meta(src)
        _ensure_meta(dst)
        src_schema = _get_meta(src, "schema_version")
        dst_schema = _get_meta(dst, "schema_version")

        wells_rows = src.execute("SELECT * FROM wells").fetchall()
        if len(wells_rows) != 1:
            raise ValueError("Import file must contain exactly one well.")
        src_well = {k: wells_rows[0][k] for k in wells_rows[0].keys()}
        src_well_id = str(src_well.get("well_id") or "")
        src_well_name = str(src_well.get("well_name") or "").strip()
        if not src_well_name:
            raise ValueError("Imported well has no name.")

        dest_row = dst.execute(
            "SELECT well_id FROM wells WHERE well_name = ?",
            (src_well_name,),
        ).fetchone()
        has_existing = dest_row is not None
        dest_well_id = str(dest_row["well_id"]) if dest_row else ""

        summary = {
            "well_name": src_well_name,
            "has_existing": has_existing,
            "src_schema_version": src_schema,
            "dst_schema_version": dst_schema,
            "schema_mismatch": bool(src_schema and dst_schema and src_schema != dst_schema),
            "identity_fill": 0,
            "identity_conflict": 0,
            "trajectory_actual_replace": False,
            "trajectory_actual_src_md": None,
            "trajectory_actual_dest_md": None,
            "hole_section_fill": 0,
            "hole_section_conflict": 0,
            "hole_sections_new": 0,
            "tickets_new": 0,
            "nozzles_new": 0,
            "section_nodes_new": 0,
        }

        if not has_existing:
            return summary

        _preview_identity(src, dst, src_well_id, dest_well_id, summary)
        _preview_trajectory(src, dst, src_well_id, dest_well_id, summary)
        _preview_section_nodes(src, dst, src_well_id, dest_well_id, summary)
        _preview_hole_sections(src, dst, src_well_id, dest_well_id, summary)
        _preview_hole_section_data(src, dst, src_well_id, dest_well_id, summary)
        _preview_tickets(src, dst, src_well_id, dest_well_id, summary)
        _preview_nozzles(src, dst, src_well_id, dest_well_id, summary)

        return summary


def create_backup() -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"wellops_backup_{now}.db"
    backup_path.write_bytes(Path(DB_PATH).read_bytes())
    return str(backup_path)


def _insert_new_well(conn: sqlite3.Connection, new_id: str, src_well: Dict[str, Any]) -> None:
    now = iso_now()
    conn.execute(
        """
        INSERT INTO wells (
          well_id,
          well_name,
          operation_type,
          status,
          step1_done,
          step2_done,
          step3_done,
          section_template_key,
          sections_version,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            src_well.get("well_name"),
            src_well.get("operation_type"),
            src_well.get("status") or "DRAFT",
            int(src_well.get("step1_done") or 0),
            int(src_well.get("step2_done") or 0),
            int(src_well.get("step3_done") or 0),
            src_well.get("section_template_key"),
            src_well.get("sections_version"),
            src_well.get("created_at") or now,
            src_well.get("updated_at") or now,
        ),
    )


def _merge_well(conn: sqlite3.Connection, well_id: str, src_well: Dict[str, Any]) -> None:
    row = conn.execute(
        """
        SELECT operation_type, status, step1_done, step2_done, step3_done,
               section_template_key, sections_version
        FROM wells WHERE well_id = ?
        """,
        (well_id,),
    ).fetchone()
    if row is None:
        return
    now = iso_now()
    conn.execute(
        """
        UPDATE wells
        SET operation_type = COALESCE(NULLIF(operation_type, ''), ?),
            status = COALESCE(NULLIF(status, ''), ?),
            step1_done = ?,
            step2_done = ?,
            step3_done = ?,
            section_template_key = COALESCE(NULLIF(section_template_key, ''), ?),
            sections_version = COALESCE(sections_version, ?),
            updated_at = ?
        WHERE well_id = ?
        """,
        (
            src_well.get("operation_type"),
            src_well.get("status"),
            max(int(row["step1_done"]), int(src_well.get("step1_done") or 0)),
            max(int(row["step2_done"]), int(src_well.get("step2_done") or 0)),
            max(int(row["step3_done"]), int(src_well.get("step3_done") or 0)),
            src_well.get("section_template_key"),
            src_well.get("sections_version"),
            now,
            well_id,
        ),
    )


def _copy_well_data(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    *,
    merge: bool,
) -> None:
    _merge_identity(src, dst, src_well_id, dest_well_id, merge)
    _merge_trajectory(src, dst, src_well_id, dest_well_id, merge)
    _merge_section_nodes(src, dst, src_well_id, dest_well_id, merge)
    _merge_hole_sections(src, dst, src_well_id, dest_well_id)
    _merge_hole_section_data(src, dst, src_well_id, dest_well_id, merge)
    _merge_tickets(src, dst, src_well_id, dest_well_id, merge)
    _merge_nozzles(src, dst, src_well_id, dest_well_id, merge)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _preview_identity(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    src_row = src.execute(
        "SELECT * FROM well_identity WHERE well_id = ?",
        (src_well_id,),
    ).fetchone()
    dest_row = dst.execute(
        "SELECT * FROM well_identity WHERE well_id = ?",
        (dest_well_id,),
    ).fetchone()
    if src_row is None or dest_row is None:
        return
    for key in src_row.keys():
        if key in ("well_id", "well_name"):
            continue
        src_val = src_row[key]
        dest_val = dest_row[key]
        if _is_blank(dest_val) and not _is_blank(src_val):
            summary["identity_fill"] += 1
        elif not _is_blank(dest_val) and not _is_blank(src_val) and str(dest_val) != str(src_val):
            summary["identity_conflict"] += 1


def _preview_trajectory(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    src_row = src.execute(
        "SELECT * FROM well_trajectory WHERE well_id = ?",
        (src_well_id,),
    ).fetchone()
    dest_row = dst.execute(
        "SELECT * FROM well_trajectory WHERE well_id = ?",
        (dest_well_id,),
    ).fetchone()
    if src_row is None or dest_row is None:
        return
    src_md = src_row["md_at_td_m"]
    dest_md = dest_row["md_at_td_m"]
    summary["trajectory_actual_src_md"] = src_md
    summary["trajectory_actual_dest_md"] = dest_md
    if src_md is None:
        return
    if dest_md is None or float(src_md) > float(dest_md):
        summary["trajectory_actual_replace"] = True


def _preview_section_nodes(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    rows = _fetch_rows(src, "well_section_nodes", "well_id = ?", (src_well_id,))
    for r in rows:
        node_key = r.get("node_key")
        if not node_key:
            continue
        exists = dst.execute(
            "SELECT 1 FROM well_section_nodes WHERE well_id = ? AND node_key = ?",
            (dest_well_id, node_key),
        ).fetchone()
        if exists is None:
            summary["section_nodes_new"] += 1


def _preview_hole_sections(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    rows = _fetch_rows(src, "well_hole_sections", "well_id = ?", (src_well_id,))
    for r in rows:
        node_key = r.get("node_key")
        if not node_key:
            continue
        exists = dst.execute(
            "SELECT 1 FROM well_hole_sections WHERE well_id = ? AND node_key = ?",
            (dest_well_id, node_key),
        ).fetchone()
        if exists is None:
            summary["hole_sections_new"] += 1


def _preview_hole_section_data(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    rows = _fetch_rows(src, "well_hole_section_data", "well_id = ?", (src_well_id,))
    if not rows:
        return
    cols = _table_columns(dst, "well_hole_section_data")
    for r in rows:
        hole_key = r.get("hole_key")
        if not hole_key:
            continue
        dest = dst.execute(
            "SELECT * FROM well_hole_section_data WHERE well_id = ? AND hole_key = ?",
            (dest_well_id, hole_key),
        ).fetchone()
        if dest is None:
            filled = sum(1 for c in cols if c not in ("well_id", "hole_key", "updated_at") and not _is_blank(r.get(c)))
            summary["hole_section_fill"] += filled
            continue
        for c in cols:
            if c in ("well_id", "hole_key", "updated_at"):
                continue
            src_val = r.get(c)
            dest_val = dest[c]
            if _is_blank(dest_val) and not _is_blank(src_val):
                summary["hole_section_fill"] += 1
            elif not _is_blank(dest_val) and not _is_blank(src_val) and str(dest_val) != str(src_val):
                summary["hole_section_conflict"] += 1


def _preview_tickets(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    rows = _fetch_rows(src, "well_hse_ticket", "well_id = ?", (src_well_id,))
    for r in rows:
        hole_key = r.get("hole_key")
        line_no = r.get("line_no")
        if not hole_key or line_no is None:
            continue
        dest = dst.execute(
            """
            SELECT 1 FROM well_hse_ticket
            WHERE well_id = ? AND hole_key = ? AND line_no = ?
            """,
            (dest_well_id, hole_key, line_no),
        ).fetchone()
        if dest is None:
            summary["tickets_new"] += 1


def _preview_nozzles(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    summary: Dict[str, Any],
) -> None:
    rows = _fetch_rows(src, "well_hse_nozzle", "well_id = ?", (src_well_id,))
    for r in rows:
        hole_key = r.get("hole_key")
        bit_index = r.get("bit_index")
        line_no = r.get("line_no")
        if not hole_key or bit_index is None or line_no is None:
            continue
        dest = dst.execute(
            """
            SELECT 1 FROM well_hse_nozzle
            WHERE well_id = ? AND hole_key = ? AND bit_index = ? AND line_no = ?
            """,
            (dest_well_id, hole_key, bit_index, line_no),
        ).fetchone()
        if dest is None:
            summary["nozzles_new"] += 1


def _merge_identity(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    row = src.execute(
        "SELECT * FROM well_identity WHERE well_id = ?",
        (src_well_id,),
    ).fetchone()
    if row is None:
        return
    src_row = {k: row[k] for k in row.keys()}

    dest_row = dst.execute(
        "SELECT * FROM well_identity WHERE well_id = ?",
        (dest_well_id,),
    ).fetchone()

    if dest_row is None:
        cols = [c for c in src_row.keys() if c != "well_id"]
        payload = {c: src_row.get(c) for c in cols}
        payload["well_id"] = dest_well_id
        _insert_rows(dst, "well_identity", [payload])
        return

    if not merge:
        return

    updates = {}
    for key, value in src_row.items():
        if key in ("well_id", "well_name"):
            continue
        if _is_blank(dest_row[key]) and not _is_blank(value):
            updates[key] = value

    if updates:
        set_sql = ", ".join([f"{k} = ?" for k in updates.keys()])
        dst.execute(
            f"UPDATE well_identity SET {set_sql} WHERE well_id = ?",
            tuple(updates.values()) + (dest_well_id,),
        )


def _merge_trajectory(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    src_row = src.execute(
        "SELECT * FROM well_trajectory WHERE well_id = ?",
        (src_well_id,),
    ).fetchone()
    if src_row is None:
        return
    src_row = {k: src_row[k] for k in src_row.keys()}

    dest_row = dst.execute(
        "SELECT * FROM well_trajectory WHERE well_id = ?",
        (dest_well_id,),
    ).fetchone()

    if dest_row is None:
        cols = [c for c in src_row.keys() if c != "well_id"]
        payload = {c: src_row.get(c) for c in cols}
        payload["well_id"] = dest_well_id
        _insert_rows(dst, "well_trajectory", [payload])
        return

    if not merge:
        return

    dest_row = {k: dest_row[k] for k in dest_row.keys()}
    planned_cols = [
        "kop_m",
        "tvd_planned_m",
        "md_planned_m",
        "max_inc_planned_deg",
        "azimuth_planned_deg",
        "max_dls_planned_deg_per_30m",
        "vs_planned_m",
        "dist_planned_m",
    ]
    actual_cols = [
        "tvd_at_td_m",
        "md_at_td_m",
        "inc_at_td_deg",
        "azimuth_at_td_deg",
        "max_dls_actual_deg_per_30m",
        "vs_at_td_m",
        "dist_at_td_m",
    ]

    updates: Dict[str, Any] = {}
    for col in planned_cols:
        if dest_row.get(col) is None and src_row.get(col) is not None:
            updates[col] = src_row.get(col)

    src_md = src_row.get("md_at_td_m")
    dest_md = dest_row.get("md_at_td_m")
    pick_src = False
    if dest_md is None and src_md is not None:
        pick_src = True
    elif src_md is not None and dest_md is not None and float(src_md) > float(dest_md):
        pick_src = True

    if pick_src:
        for col in actual_cols:
            updates[col] = src_row.get(col)

    if updates:
        updates["updated_at"] = iso_now()
        set_sql = ", ".join([f"{k} = ?" for k in updates.keys()])
        dst.execute(
            f"UPDATE well_trajectory SET {set_sql} WHERE well_id = ?",
            tuple(updates.values()) + (dest_well_id,),
        )


def _merge_section_nodes(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    rows = _fetch_rows(src, "well_section_nodes", "well_id = ?", (src_well_id,))
    if not rows:
        return

    if not merge:
        new_rows = []
        for r in rows:
            r = dict(r)
            r["well_id"] = dest_well_id
            new_rows.append(r)
        _insert_rows(dst, "well_section_nodes", new_rows)
        return

    for r in rows:
        node_key = r.get("node_key")
        if not node_key:
            continue
        dest = dst.execute(
            "SELECT * FROM well_section_nodes WHERE well_id = ? AND node_key = ?",
            (dest_well_id, node_key),
        ).fetchone()
        if dest is None:
            node_id = r.get("node_id")
            if node_id:
                exists = dst.execute(
                    "SELECT 1 FROM well_section_nodes WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if exists:
                    r["node_id"] = str(uuid.uuid4())
            r["well_id"] = dest_well_id
            _insert_rows(dst, "well_section_nodes", [r])
            continue

        updates = {}
        for flag in ("is_enabled", "is_selected", "is_completed"):
            if int(dest[flag]) == 0 and int(r.get(flag) or 0) == 1:
                updates[flag] = 1
        if _is_blank(dest["state_json"]) and not _is_blank(r.get("state_json")):
            updates["state_json"] = r.get("state_json")
        if updates:
            updates["updated_at"] = iso_now()
            set_sql = ", ".join([f"{k} = ?" for k in updates.keys()])
            dst.execute(
                f"UPDATE well_section_nodes SET {set_sql} WHERE well_id = ? AND node_key = ?",
                tuple(updates.values()) + (dest_well_id, node_key),
            )


def _merge_hole_sections(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
) -> None:
    rows = _fetch_rows(src, "well_hole_sections", "well_id = ?", (src_well_id,))
    if not rows:
        return
    for r in rows:
        node_key = r.get("node_key")
        if not node_key:
            continue
        exists = dst.execute(
            "SELECT 1 FROM well_hole_sections WHERE well_id = ? AND node_key = ?",
            (dest_well_id, node_key),
        ).fetchone()
        if exists:
            dst.execute(
                "UPDATE well_hole_sections SET is_enabled = 1 WHERE well_id = ? AND node_key = ?",
                (dest_well_id, node_key),
            )
        else:
            dst.execute(
                """
                INSERT INTO well_hole_sections (well_id, node_key, is_enabled, updated_at)
                VALUES (?, ?, 1, ?)
                """,
                (dest_well_id, node_key, iso_now()),
            )


def _merge_hole_section_data(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    rows = _fetch_rows(src, "well_hole_section_data", "well_id = ?", (src_well_id,))
    if not rows:
        return

    cols = _table_columns(dst, "well_hole_section_data")
    for r in rows:
        hole_key = r.get("hole_key")
        if not hole_key:
            continue
        dest = dst.execute(
            "SELECT * FROM well_hole_section_data WHERE well_id = ? AND hole_key = ?",
            (dest_well_id, hole_key),
        ).fetchone()
        if dest is None:
            payload = {c: r.get(c) for c in cols if c in r}
            payload["well_id"] = dest_well_id
            payload["hole_key"] = hole_key
            _insert_rows(dst, "well_hole_section_data", [payload])
            continue

        if not merge:
            continue

        updates = {}
        for c in cols:
            if c in ("well_id", "hole_key", "updated_at"):
                continue
            if _is_blank(dest[c]) and not _is_blank(r.get(c)):
                updates[c] = r.get(c)
        if updates:
            updates["updated_at"] = iso_now()
            set_sql = ", ".join([f"{k} = ?" for k in updates.keys()])
            dst.execute(
                f"UPDATE well_hole_section_data SET {set_sql} WHERE well_id = ? AND hole_key = ?",
                tuple(updates.values()) + (dest_well_id, hole_key),
            )


def _merge_tickets(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    rows = _fetch_rows(src, "well_hse_ticket", "well_id = ?", (src_well_id,))
    if not rows:
        return
    for r in rows:
        hole_key = r.get("hole_key")
        line_no = r.get("line_no")
        if not hole_key or line_no is None:
            continue
        dest = dst.execute(
            """
            SELECT 1 FROM well_hse_ticket
            WHERE well_id = ? AND hole_key = ? AND line_no = ?
            """,
            (dest_well_id, hole_key, line_no),
        ).fetchone()
        if dest is None:
            r = dict(r)
            r["well_id"] = dest_well_id
            _insert_rows(dst, "well_hse_ticket", [r])
        elif not merge:
            continue


def _merge_nozzles(
    src: sqlite3.Connection,
    dst: sqlite3.Connection,
    src_well_id: str,
    dest_well_id: str,
    merge: bool,
) -> None:
    rows = _fetch_rows(src, "well_hse_nozzle", "well_id = ?", (src_well_id,))
    if not rows:
        return
    for r in rows:
        hole_key = r.get("hole_key")
        bit_index = r.get("bit_index")
        line_no = r.get("line_no")
        if not hole_key or bit_index is None or line_no is None:
            continue
        dest = dst.execute(
            """
            SELECT 1 FROM well_hse_nozzle
            WHERE well_id = ? AND hole_key = ? AND bit_index = ? AND line_no = ?
            """,
            (dest_well_id, hole_key, bit_index, line_no),
        ).fetchone()
        if dest is None:
            r = dict(r)
            r["well_id"] = dest_well_id
            _insert_rows(dst, "well_hse_nozzle", [r])
        elif not merge:
            continue
