from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.data.db import get_connection


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    return float(s)


def save_trajectory(well_id: str, data: Dict[str, Any]) -> None:
    """
    Inserts or updates well trajectory data for Step 2.
    """
    wid = (well_id or "").strip()
    if not wid:
        raise ValueError("well_id is required")

    now = iso_now()

    kop_m = _to_float(data.get("kop_m"))
    tvd_planned_m = _to_float(data.get("tvd_planned_m"))
    md_planned_m = _to_float(data.get("md_planned_m"))
    max_inc_planned_deg = _to_float(data.get("max_inc_planned_deg"))
    azimuth_planned_deg = _to_float(data.get("azimuth_planned_deg"))
    max_dls_planned_deg_per_30m = _to_float(data.get("max_dls_planned_deg_per_30m"))
    vs_planned_m = _to_float(data.get("vs_planned_m"))
    dist_planned_m = _to_float(data.get("dist_planned_m"))

    tvd_at_td_m = _to_float(data.get("tvd_at_td_m"))
    md_at_td_m = _to_float(data.get("md_at_td_m"))
    inc_at_td_deg = _to_float(data.get("inc_at_td_deg"))
    azimuth_at_td_deg = _to_float(data.get("azimuth_at_td_deg"))
    max_dls_actual_deg_per_30m = _to_float(data.get("max_dls_actual_deg_per_30m"))
    vs_at_td_m = _to_float(data.get("vs_at_td_m"))
    dist_at_td_m = _to_float(data.get("dist_at_td_m"))

    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE well_trajectory
            SET
              kop_m = ?,
              tvd_planned_m = ?,
              md_planned_m = ?,
              max_inc_planned_deg = ?,
              azimuth_planned_deg = ?,
              max_dls_planned_deg_per_30m = ?,
              vs_planned_m = ?,
              dist_planned_m = ?,
              tvd_at_td_m = ?,
              md_at_td_m = ?,
              inc_at_td_deg = ?,
              azimuth_at_td_deg = ?,
              max_dls_actual_deg_per_30m = ?,
              vs_at_td_m = ?,
              dist_at_td_m = ?,
              updated_at = ?
            WHERE well_id = ?
            """,
            (
                kop_m,
                tvd_planned_m,
                md_planned_m,
                max_inc_planned_deg,
                azimuth_planned_deg,
                max_dls_planned_deg_per_30m,
                vs_planned_m,
                dist_planned_m,
                tvd_at_td_m,
                md_at_td_m,
                inc_at_td_deg,
                azimuth_at_td_deg,
                max_dls_actual_deg_per_30m,
                vs_at_td_m,
                dist_at_td_m,
                now,
                wid,
            ),
        )

        if cur.rowcount == 0:
            conn.execute(
                """
                INSERT INTO well_trajectory (
                  well_id,
                  kop_m,
                  tvd_planned_m,
                  md_planned_m,
                  max_inc_planned_deg,
                  azimuth_planned_deg,
                  max_dls_planned_deg_per_30m,
                  vs_planned_m,
                  dist_planned_m,
                  tvd_at_td_m,
                  md_at_td_m,
                  inc_at_td_deg,
                  azimuth_at_td_deg,
                  max_dls_actual_deg_per_30m,
                  vs_at_td_m,
                  dist_at_td_m,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wid,
                    kop_m,
                    tvd_planned_m,
                    md_planned_m,
                    max_inc_planned_deg,
                    azimuth_planned_deg,
                    max_dls_planned_deg_per_30m,
                    vs_planned_m,
                    dist_planned_m,
                    tvd_at_td_m,
                    md_at_td_m,
                    inc_at_td_deg,
                    azimuth_at_td_deg,
                    max_dls_actual_deg_per_30m,
                    vs_at_td_m,
                    dist_at_td_m,
                    now,
                    now,
                ),
            )
