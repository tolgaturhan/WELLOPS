# app/data/wells_repo.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.data.db import get_connection


def iso_now() -> str:
    # UTC ISO 8601 (schema ile uyumlu: TEXT)
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uuid4_str() -> str:
    return str(uuid.uuid4())


def create_draft_well(well_name: str, operation_type: str | None = None) -> str:
    """
    Creates a new well row with status='DRAFT' and returns well_id (TEXT/UUID).

    Contract (project decision):
      - NewWellDialog collects canonical well_name
      - MainWindow creates DRAFT well row
      - WizardNewWell receives existing well_id and does not create well row
    """
    name = (well_name or "").strip()
    if not name:
        raise ValueError("well_name is required")

    now = iso_now()
    well_id = uuid4_str()

    op_type = (operation_type or "").strip() or None

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO wells (
              well_id,
              well_name,
              operation_type,
              status,
              step1_done,
              section_template_key,
              sections_version,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                well_id,
                name,
                op_type,
                "DRAFT",
                0,
                None,
                None,
                now,
                now,
            ),
        )

    return well_id


def list_wells(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns wells list for UI tree.

    Output dict keys (UI contract):
      - id: str (well_id)
      - name: str (well_name)
      - status: str
      - created_at: str
      - updated_at: str
    """
    sql = """
        SELECT well_id, well_name, operation_type, status, created_at, updated_at
        FROM wells
    """
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)

    sql += " ORDER BY created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "id": str(r["well_id"]),
            "name": str(r["well_name"]),
            "operation_type": str(r["operation_type"] or ""),
            "status": str(r["status"]),
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        }
        for r in rows
    ]


def get_well(well_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch single well by id. Useful for future wiring.
    """
    wid = (well_id or "").strip()
    if not wid:
        return None

    with get_connection() as conn:
        r = conn.execute(
            """
            SELECT well_id, well_name, operation_type, status, step1_done,
                   section_template_key, sections_version,
                   created_at, updated_at
            FROM wells
            WHERE well_id = ?
            """,
            (wid,),
        ).fetchone()

    if r is None:
        return None

    return {
        "id": str(r["well_id"]),
        "name": str(r["well_name"]),
        "operation_type": str(r["operation_type"] or ""),
        "status": str(r["status"]),
        "step1_done": int(r["step1_done"]),
        "section_template_key": r["section_template_key"],
        "sections_version": r["sections_version"],
        "created_at": str(r["created_at"]),
        "updated_at": str(r["updated_at"]),
    }


def delete_well(well_id: str) -> None:
    """
    Permanently deletes a well and all related section nodes.
    """
    wid = (well_id or "").strip()
    if not wid:
        raise ValueError("well_id is required")

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM well_section_nodes WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_hse_ticket WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_hse_nozzle WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_hole_section_data WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_hole_sections WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_trajectory WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM well_identity WHERE well_id = ?",
            (wid,),
        )
        conn.execute(
            "DELETE FROM wells WHERE well_id = ?",
            (wid,),
        )
