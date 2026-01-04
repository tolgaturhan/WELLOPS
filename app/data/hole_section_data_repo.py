from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from app.data.db import get_connection
from app.core.hole_section_calcs import NozzleLine


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    s = str(value).strip()
    if not s:
        return None
    # accept dd.MM.yyyy
    try:
        return datetime.strptime(s, "%d.%m.%Y").date().isoformat()
    except Exception:
        pass
    # accept yyyy-mm-dd
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except Exception:
        return None


def get_hole_section(well_id: str, hole_key: str) -> Optional[Dict[str, Any]]:
    wid = (well_id or "").strip()
    hkey = (hole_key or "").strip()
    if not wid or not hkey:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM well_hole_section_data
            WHERE well_id = ? AND hole_key = ?
            """,
            (wid, hkey),
        ).fetchone()

        if not row:
            return None

        tickets = conn.execute(
            """
            SELECT line_no, ticket_date, ticket_price_usd
            FROM well_hse_ticket
            WHERE well_id = ? AND hole_key = ?
            ORDER BY line_no
            """,
            (wid, hkey),
        ).fetchall()

        nozzles = conn.execute(
            """
            SELECT line_no, count, size_32nds
            FROM well_hse_nozzle
            WHERE well_id = ? AND hole_key = ?
            ORDER BY line_no
            """,
            (wid, hkey),
        ).fetchall()

    data = {k: row[k] for k in row.keys()}
    data["tickets"] = [
        {
            "line_no": int(r["line_no"]),
            "ticket_date": r["ticket_date"],
            "ticket_price_usd": r["ticket_price_usd"],
        }
        for r in tickets
    ]
    data["nozzles"] = [
        NozzleLine(count=int(r["count"]), size_32nds=int(r["size_32nds"]))
        for r in nozzles
    ]

    return data


def save_hole_section(well_id: str, hole_key: str, data: Dict[str, Any]) -> None:
    wid = (well_id or "").strip()
    hkey = (hole_key or "").strip()
    if not wid or not hkey:
        raise ValueError("well_id and hole_key are required")

    now = iso_now()

    def _txt(key: str) -> str:
        return (data.get(key) or "").strip()

    payload = {
        "mud_motor_brand": _txt("mud_motor_brand"),
        "mud_motor_size": _txt("mud_motor_size"),
        "mud_motor_sleeve_stb_gauge_in": _to_float(data.get("mud_motor_sleeve_stb_gauge_in")),
        "mud_motor_bend_angle_deg": _txt("mud_motor_bend_angle_deg"),
        "mud_motor_lobe": _txt("mud_motor_lobe"),
        "mud_motor_stage": _txt("mud_motor_stage"),
        "mud_motor_ibs_gauge_in": _to_float(data.get("mud_motor_ibs_gauge_in")),
        "bit_brand": _txt("bit_brand"),
        "bit_kind": _txt("bit_kind"),
        "bit_type": _txt("bit_type"),
        "bit_iadc": _txt("bit_iadc"),
        "bit_serial": _txt("bit_serial"),
        "personnel_day_dd": _txt("personnel_day_dd"),
        "personnel_night_dd": _txt("personnel_night_dd"),
        "personnel_day_mwd": _txt("personnel_day_mwd"),
        "personnel_night_mwd": _txt("personnel_night_mwd"),
        "info_casing_shoe": _txt("info_casing_shoe"),
        "info_casing_od": _txt("info_casing_od"),
        "info_casing_id": _txt("info_casing_id"),
        "info_section_tvd": _txt("info_section_tvd"),
        "info_section_md": _txt("info_section_md"),
        "info_mud_type": _txt("info_mud_type"),
        "ta_call_out_date": _to_iso_date(data.get("ta_call_out_date")),
        "ta_crew_mob_time": _txt("ta_crew_mob_time"),
        "ta_standby_time_hrs": _to_float(data.get("ta_standby_time_hrs")),
        "ta_ru_time_hrs": _to_float(data.get("ta_ru_time_hrs")),
        "ta_tripping_time_hrs": _to_float(data.get("ta_tripping_time_hrs")),
        "ta_circulation_time_hrs": _to_float(data.get("ta_circulation_time_hrs")),
        "ta_rotary_time_hrs": _to_float(data.get("ta_rotary_time_hrs")),
        "ta_rotary_meters": _to_float(data.get("ta_rotary_meters")),
        "ta_sliding_time_hrs": _to_float(data.get("ta_sliding_time_hrs")),
        "ta_sliding_meters": _to_float(data.get("ta_sliding_meters")),
        "ta_npt_due_to_rig_hrs": _to_float(data.get("ta_npt_due_to_rig_hrs")),
        "ta_npt_due_to_motor_hrs": _to_float(data.get("ta_npt_due_to_motor_hrs")),
        "ta_npt_due_to_mwd_hrs": _to_float(data.get("ta_npt_due_to_mwd_hrs")),
        "ta_release_date": _to_iso_date(data.get("ta_release_date")),
        "ta_release_time": _txt("ta_release_time"),
        "ta_total_brt_hrs": _to_float(data.get("ta_total_brt_hrs")),
    }

    tickets = []
    for i in range(1, 4):
        date_key = f"ticket_date_{i}"
        price_key = f"ticket_price_usd_{i}"
        tickets.append(
            {
                "line_no": i,
                "ticket_date": _to_iso_date(data.get(date_key)),
                "ticket_price_usd": _to_float(data.get(price_key)),
            }
        )

    nozzles: List[NozzleLine] = list(data.get("bit_nozzles") or [])

    with get_connection() as conn:
        cur = conn.execute(
            """
            UPDATE well_hole_section_data
            SET
              mud_motor_brand = ?,
              mud_motor_size = ?,
              mud_motor_sleeve_stb_gauge_in = ?,
              mud_motor_bend_angle_deg = ?,
              mud_motor_lobe = ?,
              mud_motor_stage = ?,
              mud_motor_ibs_gauge_in = ?,
              bit_brand = ?,
              bit_kind = ?,
              bit_type = ?,
              bit_iadc = ?,
              bit_serial = ?,
              personnel_day_dd = ?,
              personnel_night_dd = ?,
              personnel_day_mwd = ?,
              personnel_night_mwd = ?,
              info_casing_shoe = ?,
              info_casing_od = ?,
              info_casing_id = ?,
              info_section_tvd = ?,
              info_section_md = ?,
              info_mud_type = ?,
              ta_call_out_date = ?,
              ta_crew_mob_time = ?,
              ta_standby_time_hrs = ?,
              ta_ru_time_hrs = ?,
              ta_tripping_time_hrs = ?,
              ta_circulation_time_hrs = ?,
              ta_rotary_time_hrs = ?,
              ta_rotary_meters = ?,
              ta_sliding_time_hrs = ?,
              ta_sliding_meters = ?,
              ta_npt_due_to_rig_hrs = ?,
              ta_npt_due_to_motor_hrs = ?,
              ta_npt_due_to_mwd_hrs = ?,
              ta_release_date = ?,
              ta_release_time = ?,
              ta_total_brt_hrs = ?,
              updated_at = ?
            WHERE well_id = ? AND hole_key = ?
            """,
            (
                payload["mud_motor_brand"],
                payload["mud_motor_size"],
                payload["mud_motor_sleeve_stb_gauge_in"],
                payload["mud_motor_bend_angle_deg"],
                payload["mud_motor_lobe"],
                payload["mud_motor_stage"],
                payload["mud_motor_ibs_gauge_in"],
                payload["bit_brand"],
                payload["bit_kind"],
                payload["bit_type"],
                payload["bit_iadc"],
                payload["bit_serial"],
                payload["personnel_day_dd"],
                payload["personnel_night_dd"],
                payload["personnel_day_mwd"],
                payload["personnel_night_mwd"],
                payload["info_casing_shoe"],
                payload["info_casing_od"],
                payload["info_casing_id"],
                payload["info_section_tvd"],
                payload["info_section_md"],
                payload["info_mud_type"],
                payload["ta_call_out_date"],
                payload["ta_crew_mob_time"],
                payload["ta_standby_time_hrs"],
                payload["ta_ru_time_hrs"],
                payload["ta_tripping_time_hrs"],
                payload["ta_circulation_time_hrs"],
                payload["ta_rotary_time_hrs"],
                payload["ta_rotary_meters"],
                payload["ta_sliding_time_hrs"],
                payload["ta_sliding_meters"],
                payload["ta_npt_due_to_rig_hrs"],
                payload["ta_npt_due_to_motor_hrs"],
                payload["ta_npt_due_to_mwd_hrs"],
                payload["ta_release_date"],
                payload["ta_release_time"],
                payload["ta_total_brt_hrs"],
                now,
                wid,
                hkey,
            ),
        )

        if cur.rowcount == 0:
            conn.execute(
                """
                INSERT INTO well_hole_section_data (
                  well_id,
                  hole_key,
                  mud_motor_brand,
                  mud_motor_size,
                  mud_motor_sleeve_stb_gauge_in,
                  mud_motor_bend_angle_deg,
                  mud_motor_lobe,
                  mud_motor_stage,
                  mud_motor_ibs_gauge_in,
                  bit_brand,
                  bit_kind,
                  bit_type,
                  bit_iadc,
                  bit_serial,
                  personnel_day_dd,
                  personnel_night_dd,
                  personnel_day_mwd,
                  personnel_night_mwd,
                  info_casing_shoe,
                  info_casing_od,
                  info_casing_id,
                  info_section_tvd,
                  info_section_md,
                  info_mud_type,
                  ta_call_out_date,
                  ta_crew_mob_time,
                  ta_standby_time_hrs,
                  ta_ru_time_hrs,
                  ta_tripping_time_hrs,
                  ta_circulation_time_hrs,
                  ta_rotary_time_hrs,
                  ta_rotary_meters,
                  ta_sliding_time_hrs,
                  ta_sliding_meters,
                  ta_npt_due_to_rig_hrs,
                  ta_npt_due_to_motor_hrs,
                  ta_npt_due_to_mwd_hrs,
                  ta_release_date,
                  ta_release_time,
                  ta_total_brt_hrs,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wid,
                    hkey,
                    payload["mud_motor_brand"],
                    payload["mud_motor_size"],
                    payload["mud_motor_sleeve_stb_gauge_in"],
                    payload["mud_motor_bend_angle_deg"],
                    payload["mud_motor_lobe"],
                    payload["mud_motor_stage"],
                    payload["mud_motor_ibs_gauge_in"],
                    payload["bit_brand"],
                    payload["bit_kind"],
                    payload["bit_type"],
                    payload["bit_iadc"],
                    payload["bit_serial"],
                    payload["personnel_day_dd"],
                    payload["personnel_night_dd"],
                    payload["personnel_day_mwd"],
                    payload["personnel_night_mwd"],
                    payload["info_casing_shoe"],
                    payload["info_casing_od"],
                    payload["info_casing_id"],
                    payload["info_section_tvd"],
                    payload["info_section_md"],
                    payload["info_mud_type"],
                    payload["ta_call_out_date"],
                    payload["ta_crew_mob_time"],
                    payload["ta_standby_time_hrs"],
                    payload["ta_ru_time_hrs"],
                    payload["ta_tripping_time_hrs"],
                    payload["ta_circulation_time_hrs"],
                    payload["ta_rotary_time_hrs"],
                    payload["ta_rotary_meters"],
                    payload["ta_sliding_time_hrs"],
                    payload["ta_sliding_meters"],
                    payload["ta_npt_due_to_rig_hrs"],
                    payload["ta_npt_due_to_motor_hrs"],
                    payload["ta_npt_due_to_mwd_hrs"],
                    payload["ta_release_date"],
                    payload["ta_release_time"],
                    payload["ta_total_brt_hrs"],
                    now,
                ),
            )

        conn.execute(
            "DELETE FROM well_hse_ticket WHERE well_id = ? AND hole_key = ?",
            (wid, hkey),
        )
        conn.execute(
            "DELETE FROM well_hse_nozzle WHERE well_id = ? AND hole_key = ?",
            (wid, hkey),
        )

        conn.executemany(
            """
            INSERT INTO well_hse_ticket (well_id, hole_key, line_no, ticket_date, ticket_price_usd, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (wid, hkey, t["line_no"], t["ticket_date"], t["ticket_price_usd"], now)
                for t in tickets
            ],
        )

        conn.executemany(
            """
            INSERT INTO well_hse_nozzle (well_id, hole_key, line_no, count, size_32nds, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (wid, hkey, i + 1, n.count, n.size_32nds, now)
                for i, n in enumerate(nozzles)
            ],
        )
