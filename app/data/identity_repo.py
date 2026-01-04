from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.data.db import get_connection


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_identity(well_id: str) -> Optional[Dict[str, Any]]:
    wid = (well_id or "").strip()
    if not wid:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT well_id, well_name, well_key, field_name, operator, contractor,
                   well_purpose, well_type, dd_well_type, province, rig_name, notes,
                   updated_at
            FROM well_identity
            WHERE well_id = ?
            """,
            (wid,),
        ).fetchone()

    if not row:
        return None

    return {k: row[k] for k in row.keys()}


def save_identity(well_id: str, data: Dict[str, Any]) -> None:
    wid = (well_id or "").strip()
    if not wid:
        raise ValueError("well_id is required")

    now = iso_now()

    payload = {
        "well_name": (data.get("well_name") or "").strip(),
        "well_key": (data.get("well_key") or "").strip(),
        "field_name": (data.get("field_name") or "").strip(),
        "operator": (data.get("operator") or "").strip(),
        "contractor": (data.get("contractor") or "").strip(),
        "well_purpose": (data.get("well_purpose") or "").strip(),
        "well_type": (data.get("well_type") or "").strip(),
        "dd_well_type": (data.get("dd_well_type") or "").strip(),
        "province": (data.get("province") or "").strip(),
        "rig_name": (data.get("rig_name") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
    }

    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE well_identity
            SET
              well_name = ?,
              well_key = ?,
              field_name = ?,
              operator = ?,
              contractor = ?,
              well_purpose = ?,
              well_type = ?,
              dd_well_type = ?,
              province = ?,
              rig_name = ?,
              notes = ?,
              updated_at = ?
            WHERE well_id = ?
            """,
            (
                payload["well_name"],
                payload["well_key"],
                payload["field_name"],
                payload["operator"],
                payload["contractor"],
                payload["well_purpose"],
                payload["well_type"],
                payload["dd_well_type"],
                payload["province"],
                payload["rig_name"],
                payload["notes"],
                now,
                wid,
            ),
        )

        if cur.rowcount == 0:
            conn.execute(
                """
                INSERT INTO well_identity (
                  well_id,
                  well_name,
                  well_key,
                  field_name,
                  operator,
                  contractor,
                  well_purpose,
                  well_type,
                  dd_well_type,
                  province,
                  rig_name,
                  notes,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wid,
                    payload["well_name"],
                    payload["well_key"],
                    payload["field_name"],
                    payload["operator"],
                    payload["contractor"],
                    payload["well_purpose"],
                    payload["well_type"],
                    payload["dd_well_type"],
                    payload["province"],
                    payload["rig_name"],
                    payload["notes"],
                    now,
                ),
            )
