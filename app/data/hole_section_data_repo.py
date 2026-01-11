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


def _to_float_or_none_token(value: Any) -> Optional[float | str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.upper() == "NONE":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None





def _to_int_flag(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    s = str(value).strip().lower()
    if s in ("1", "true", "yes", "y"):
        return 1
    return 0


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
            SELECT bit_index, line_no, count, size_32nds
            FROM well_hse_nozzle
            WHERE well_id = ? AND hole_key = ?
            ORDER BY bit_index, line_no
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
    bit1_nozzles: List[NozzleLine] = []
    bit2_nozzles: List[NozzleLine] = []
    for r in nozzles:
        line = NozzleLine(count=int(r["count"]), size_32nds=int(r["size_32nds"]))
        if int(r["bit_index"]) == 2:
            bit2_nozzles.append(line)
        else:
            bit1_nozzles.append(line)
    data["bit1_nozzles"] = bit1_nozzles
    data["bit2_nozzles"] = bit2_nozzles

    return data


def save_hole_section(well_id: str, hole_key: str, data: Dict[str, Any]) -> None:
    wid = (well_id or "").strip()
    hkey = (hole_key or "").strip()
    if not wid or not hkey:
        raise ValueError("well_id and hole_key are required")

    now = iso_now()

    def _txt(key: str) -> str:
        return (data.get(key) or "").strip()

    def _pick(*keys: str) -> Any:
        for key in keys:
            val = data.get(key)
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
                continue
            return val
        return None

    mm1_brand = _txt("mud_motor1_brand") or _txt("mud_motor_brand")
    mm1_size = _txt("mud_motor1_size") or _txt("mud_motor_size")
    mm1_sleeve_none = _to_int_flag(data.get("mud_motor1_sleeve_none"))
    mm1_sleeve = None if mm1_sleeve_none else _to_float_or_none_token(_pick("mud_motor1_sleeve_stb_gauge_in", "mud_motor_sleeve_stb_gauge_in"))
    mm1_bend = _txt("mud_motor1_bend_angle_deg") or _txt("mud_motor_bend_angle_deg")
    mm1_lobe = _txt("mud_motor1_lobe") or _txt("mud_motor_lobe")
    mm1_stage = _txt("mud_motor1_stage") or _txt("mud_motor_stage")
    mm1_ibs_none = _to_int_flag(data.get("mud_motor1_ibs_none"))
    mm1_ibs = None if mm1_ibs_none else _to_float_or_none_token(_pick("mud_motor1_ibs_gauge_in", "mud_motor_ibs_gauge_in"))

    payload = {
        "mud_motor1_brand": mm1_brand,
        "mud_motor1_size": mm1_size,
        "mud_motor1_sleeve_stb_gauge_in": mm1_sleeve,
        "mud_motor1_sleeve_none": mm1_sleeve_none,
        "mud_motor1_bend_angle_deg": mm1_bend,
        "mud_motor1_lobe": mm1_lobe,
        "mud_motor1_stage": mm1_stage,
        "mud_motor1_ibs_gauge_in": mm1_ibs,
        "mud_motor1_ibs_none": mm1_ibs_none,
        "mud_motor2_brand": _txt("mud_motor2_brand"),
        "mud_motor2_size": _txt("mud_motor2_size"),
        "mud_motor2_sleeve_stb_gauge_in": (None if _to_int_flag(data.get("mud_motor2_sleeve_none")) else _to_float_or_none_token(data.get("mud_motor2_sleeve_stb_gauge_in"))),
        "mud_motor2_sleeve_none": _to_int_flag(data.get("mud_motor2_sleeve_none")),
        "mud_motor2_bend_angle_deg": _txt("mud_motor2_bend_angle_deg"),
        "mud_motor2_lobe": _txt("mud_motor2_lobe"),
        "mud_motor2_stage": _txt("mud_motor2_stage"),
        "mud_motor2_ibs_gauge_in": (None if _to_int_flag(data.get("mud_motor2_ibs_none")) else _to_float_or_none_token(data.get("mud_motor2_ibs_gauge_in"))),
        "mud_motor2_ibs_none": _to_int_flag(data.get("mud_motor2_ibs_none")),
        "mud_motor_brand": mm1_brand,
        "mud_motor_size": mm1_size,
        "mud_motor_sleeve_stb_gauge_in": mm1_sleeve,
        "mud_motor_bend_angle_deg": mm1_bend,
        "mud_motor_lobe": mm1_lobe,
        "mud_motor_stage": mm1_stage,
        "mud_motor_ibs_gauge_in": mm1_ibs,
        "bit1_brand": _txt("bit1_brand"),
        "bit1_kind": _txt("bit1_kind"),
        "bit1_type": _txt("bit1_type"),
        "bit1_iadc": _txt("bit1_iadc"),
        "bit1_serial": _txt("bit1_serial"),
        "bit2_brand": _txt("bit2_brand"),
        "bit2_kind": _txt("bit2_kind"),
        "bit2_type": _txt("bit2_type"),
        "bit2_iadc": _txt("bit2_iadc"),
        "bit2_serial": _txt("bit2_serial"),
        "bit_brand": _txt("bit1_brand"),
        "bit_kind": _txt("bit1_kind"),
        "bit_type": _txt("bit1_type"),
        "bit_iadc": _txt("bit1_iadc"),
        "bit_serial": _txt("bit1_serial"),
        "personnel_day_dd_1": _txt("personnel_day_dd_1"),
        "personnel_day_dd_2": _txt("personnel_day_dd_2"),
        "personnel_day_dd_3": _txt("personnel_day_dd_3"),
        "personnel_night_dd_1": _txt("personnel_night_dd_1"),
        "personnel_night_dd_2": _txt("personnel_night_dd_2"),
        "personnel_night_dd_3": _txt("personnel_night_dd_3"),
        "personnel_day_mwd_1": _txt("personnel_day_mwd_1"),
        "personnel_day_mwd_2": _txt("personnel_day_mwd_2"),
        "personnel_day_mwd_3": _txt("personnel_day_mwd_3"),
        "personnel_night_mwd_1": _txt("personnel_night_mwd_1"),
        "personnel_night_mwd_2": _txt("personnel_night_mwd_2"),
        "personnel_night_mwd_3": _txt("personnel_night_mwd_3"),
        "info_casing_shoe": _txt("info_casing_shoe"),
        "info_casing_od": _txt("info_casing_od"),
        "info_casing_id": _txt("info_casing_id"),
        "info_section_tvd": _txt("info_section_tvd"),
        "info_section_md": _txt("info_section_md"),
        "info_mud_type": _txt("info_mud_type"),
        "ta_call_out_date": _to_iso_date(data.get("ta_call_out_date")),
        "ta_crew_mob_time": _txt("ta_crew_mob_time"),
        "ta_standby_time_hrs_run1": _to_float(_pick("ta_standby_time_hrs_run1", "ta_standby_time_hrs")),
        "ta_standby_time_hrs_run2": _to_float(data.get("ta_standby_time_hrs_run2")),
        "ta_standby_time_hrs_run3": _to_float(data.get("ta_standby_time_hrs_run3")),
        "ta_ru_time_hrs_run1": _to_float(_pick("ta_ru_time_hrs_run1", "ta_ru_time_hrs")),
        "ta_ru_time_hrs_run2": _to_float(data.get("ta_ru_time_hrs_run2")),
        "ta_ru_time_hrs_run3": _to_float(data.get("ta_ru_time_hrs_run3")),
        "ta_tripping_time_hrs_run1": _to_float(_pick("ta_tripping_time_hrs_run1", "ta_tripping_time_hrs")),
        "ta_tripping_time_hrs_run2": _to_float(data.get("ta_tripping_time_hrs_run2")),
        "ta_tripping_time_hrs_run3": _to_float(data.get("ta_tripping_time_hrs_run3")),
        "ta_circulation_time_hrs_run1": _to_float(_pick("ta_circulation_time_hrs_run1", "ta_circulation_time_hrs")),
        "ta_circulation_time_hrs_run2": _to_float(data.get("ta_circulation_time_hrs_run2")),
        "ta_circulation_time_hrs_run3": _to_float(data.get("ta_circulation_time_hrs_run3")),
        "ta_rotary_time_hrs_run1": _to_float(_pick("ta_rotary_time_hrs_run1", "ta_rotary_time_hrs")),
        "ta_rotary_time_hrs_run2": _to_float(data.get("ta_rotary_time_hrs_run2")),
        "ta_rotary_time_hrs_run3": _to_float(data.get("ta_rotary_time_hrs_run3")),
        "ta_rotary_meters_run1": _to_float(_pick("ta_rotary_meters_run1", "ta_rotary_meters")),
        "ta_rotary_meters_run2": _to_float(data.get("ta_rotary_meters_run2")),
        "ta_rotary_meters_run3": _to_float(data.get("ta_rotary_meters_run3")),
        "ta_sliding_time_hrs_run1": _to_float(_pick("ta_sliding_time_hrs_run1", "ta_sliding_time_hrs")),
        "ta_sliding_time_hrs_run2": _to_float(data.get("ta_sliding_time_hrs_run2")),
        "ta_sliding_time_hrs_run3": _to_float(data.get("ta_sliding_time_hrs_run3")),
        "ta_sliding_meters_run1": _to_float(_pick("ta_sliding_meters_run1", "ta_sliding_meters")),
        "ta_sliding_meters_run2": _to_float(data.get("ta_sliding_meters_run2")),
        "ta_sliding_meters_run3": _to_float(data.get("ta_sliding_meters_run3")),
        "ta_npt_due_to_rig_hrs_run1": _to_float(_pick("ta_npt_due_to_rig_hrs_run1", "ta_npt_due_to_rig_hrs")),
        "ta_npt_due_to_rig_hrs_run2": _to_float(data.get("ta_npt_due_to_rig_hrs_run2")),
        "ta_npt_due_to_rig_hrs_run3": _to_float(data.get("ta_npt_due_to_rig_hrs_run3")),
        "ta_npt_due_to_motor_hrs_run1": _to_float(_pick("ta_npt_due_to_motor_hrs_run1", "ta_npt_due_to_motor_hrs")),
        "ta_npt_due_to_motor_hrs_run2": _to_float(data.get("ta_npt_due_to_motor_hrs_run2")),
        "ta_npt_due_to_motor_hrs_run3": _to_float(data.get("ta_npt_due_to_motor_hrs_run3")),
        "ta_npt_due_to_mwd_hrs_run1": _to_float(_pick("ta_npt_due_to_mwd_hrs_run1", "ta_npt_due_to_mwd_hrs")),
        "ta_npt_due_to_mwd_hrs_run2": _to_float(data.get("ta_npt_due_to_mwd_hrs_run2")),
        "ta_npt_due_to_mwd_hrs_run3": _to_float(data.get("ta_npt_due_to_mwd_hrs_run3")),
        "ta_brt_hrs_run1": _to_float(_pick("ta_brt_hrs_run1", "ta_total_brt_hrs")),
        "ta_brt_hrs_run2": _to_float(data.get("ta_brt_hrs_run2")),
        "ta_brt_hrs_run3": _to_float(data.get("ta_brt_hrs_run3")),
        "ta_release_date": _to_iso_date(data.get("ta_release_date")),
        "ta_release_time": _txt("ta_release_time"),
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

    bit1_nozzles: List[NozzleLine] = list(data.get("bit1_nozzles") or [])
    bit2_nozzles: List[NozzleLine] = list(data.get("bit2_nozzles") or [])

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
              mud_motor1_brand = ?,
              mud_motor1_size = ?,
              mud_motor1_sleeve_stb_gauge_in = ?,
              mud_motor1_sleeve_none = ?,
              mud_motor1_bend_angle_deg = ?,
              mud_motor1_lobe = ?,
              mud_motor1_stage = ?,
              mud_motor1_ibs_gauge_in = ?,
              mud_motor1_ibs_none = ?,
              mud_motor2_brand = ?,
              mud_motor2_size = ?,
              mud_motor2_sleeve_stb_gauge_in = ?,
              mud_motor2_sleeve_none = ?,
              mud_motor2_bend_angle_deg = ?,
              mud_motor2_lobe = ?,
              mud_motor2_stage = ?,
              mud_motor2_ibs_gauge_in = ?,
              mud_motor2_ibs_none = ?,
              bit_brand = ?,
              bit_kind = ?,
              bit_type = ?,
              bit_iadc = ?,
              bit_serial = ?,
              bit1_brand = ?,
              bit1_kind = ?,
              bit1_type = ?,
              bit1_iadc = ?,
              bit1_serial = ?,
              bit2_brand = ?,
              bit2_kind = ?,
              bit2_type = ?,
              bit2_iadc = ?,
              bit2_serial = ?,
              personnel_day_dd_1 = ?,
              personnel_day_dd_2 = ?,
              personnel_day_dd_3 = ?,
              personnel_night_dd_1 = ?,
              personnel_night_dd_2 = ?,
              personnel_night_dd_3 = ?,
              personnel_day_mwd_1 = ?,
              personnel_day_mwd_2 = ?,
              personnel_day_mwd_3 = ?,
              personnel_night_mwd_1 = ?,
              personnel_night_mwd_2 = ?,
              personnel_night_mwd_3 = ?,
              info_casing_shoe = ?,
              info_casing_od = ?,
              info_casing_id = ?,
              info_section_tvd = ?,
              info_section_md = ?,
              info_mud_type = ?,
              ta_call_out_date = ?,
              ta_crew_mob_time = ?,
              ta_standby_time_hrs_run1 = ?,
              ta_standby_time_hrs_run2 = ?,
              ta_standby_time_hrs_run3 = ?,
              ta_ru_time_hrs_run1 = ?,
              ta_ru_time_hrs_run2 = ?,
              ta_ru_time_hrs_run3 = ?,
              ta_tripping_time_hrs_run1 = ?,
              ta_tripping_time_hrs_run2 = ?,
              ta_tripping_time_hrs_run3 = ?,
              ta_circulation_time_hrs_run1 = ?,
              ta_circulation_time_hrs_run2 = ?,
              ta_circulation_time_hrs_run3 = ?,
              ta_rotary_time_hrs_run1 = ?,
              ta_rotary_time_hrs_run2 = ?,
              ta_rotary_time_hrs_run3 = ?,
              ta_rotary_meters_run1 = ?,
              ta_rotary_meters_run2 = ?,
              ta_rotary_meters_run3 = ?,
              ta_sliding_time_hrs_run1 = ?,
              ta_sliding_time_hrs_run2 = ?,
              ta_sliding_time_hrs_run3 = ?,
              ta_sliding_meters_run1 = ?,
              ta_sliding_meters_run2 = ?,
              ta_sliding_meters_run3 = ?,
              ta_npt_due_to_rig_hrs_run1 = ?,
              ta_npt_due_to_rig_hrs_run2 = ?,
              ta_npt_due_to_rig_hrs_run3 = ?,
              ta_npt_due_to_motor_hrs_run1 = ?,
              ta_npt_due_to_motor_hrs_run2 = ?,
              ta_npt_due_to_motor_hrs_run3 = ?,
              ta_npt_due_to_mwd_hrs_run1 = ?,
              ta_npt_due_to_mwd_hrs_run2 = ?,
              ta_npt_due_to_mwd_hrs_run3 = ?,
              ta_brt_hrs_run1 = ?,
              ta_brt_hrs_run2 = ?,
              ta_brt_hrs_run3 = ?,
              ta_release_date = ?,
              ta_release_time = ?,
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
                payload["mud_motor1_brand"],
                payload["mud_motor1_size"],
                payload["mud_motor1_sleeve_stb_gauge_in"],
                payload["mud_motor1_sleeve_none"],
                payload["mud_motor1_bend_angle_deg"],
                payload["mud_motor1_lobe"],
                payload["mud_motor1_stage"],
                payload["mud_motor1_ibs_gauge_in"],
                payload["mud_motor1_ibs_none"],
                payload["mud_motor2_brand"],
                payload["mud_motor2_size"],
                payload["mud_motor2_sleeve_stb_gauge_in"],
                payload["mud_motor2_sleeve_none"],
                payload["mud_motor2_bend_angle_deg"],
                payload["mud_motor2_lobe"],
                payload["mud_motor2_stage"],
                payload["mud_motor2_ibs_gauge_in"],
                payload["mud_motor2_ibs_none"],
                payload["bit_brand"],
                payload["bit_kind"],
                payload["bit_type"],
                payload["bit_iadc"],
                payload["bit_serial"],
                payload["bit1_brand"],
                payload["bit1_kind"],
                payload["bit1_type"],
                payload["bit1_iadc"],
                payload["bit1_serial"],
                payload["bit2_brand"],
                payload["bit2_kind"],
                payload["bit2_type"],
                payload["bit2_iadc"],
                payload["bit2_serial"],
                payload["personnel_day_dd_1"],
                payload["personnel_day_dd_2"],
                payload["personnel_day_dd_3"],
                payload["personnel_night_dd_1"],
                payload["personnel_night_dd_2"],
                payload["personnel_night_dd_3"],
                payload["personnel_day_mwd_1"],
                payload["personnel_day_mwd_2"],
                payload["personnel_day_mwd_3"],
                payload["personnel_night_mwd_1"],
                payload["personnel_night_mwd_2"],
                payload["personnel_night_mwd_3"],
                payload["info_casing_shoe"],
                payload["info_casing_od"],
                payload["info_casing_id"],
                payload["info_section_tvd"],
                payload["info_section_md"],
                payload["info_mud_type"],
                payload["ta_call_out_date"],
                payload["ta_crew_mob_time"],
                payload["ta_standby_time_hrs_run1"],
                payload["ta_standby_time_hrs_run2"],
                payload["ta_standby_time_hrs_run3"],
                payload["ta_ru_time_hrs_run1"],
                payload["ta_ru_time_hrs_run2"],
                payload["ta_ru_time_hrs_run3"],
                payload["ta_tripping_time_hrs_run1"],
                payload["ta_tripping_time_hrs_run2"],
                payload["ta_tripping_time_hrs_run3"],
                payload["ta_circulation_time_hrs_run1"],
                payload["ta_circulation_time_hrs_run2"],
                payload["ta_circulation_time_hrs_run3"],
                payload["ta_rotary_time_hrs_run1"],
                payload["ta_rotary_time_hrs_run2"],
                payload["ta_rotary_time_hrs_run3"],
                payload["ta_rotary_meters_run1"],
                payload["ta_rotary_meters_run2"],
                payload["ta_rotary_meters_run3"],
                payload["ta_sliding_time_hrs_run1"],
                payload["ta_sliding_time_hrs_run2"],
                payload["ta_sliding_time_hrs_run3"],
                payload["ta_sliding_meters_run1"],
                payload["ta_sliding_meters_run2"],
                payload["ta_sliding_meters_run3"],
                payload["ta_npt_due_to_rig_hrs_run1"],
                payload["ta_npt_due_to_rig_hrs_run2"],
                payload["ta_npt_due_to_rig_hrs_run3"],
                payload["ta_npt_due_to_motor_hrs_run1"],
                payload["ta_npt_due_to_motor_hrs_run2"],
                payload["ta_npt_due_to_motor_hrs_run3"],
                payload["ta_npt_due_to_mwd_hrs_run1"],
                payload["ta_npt_due_to_mwd_hrs_run2"],
                payload["ta_npt_due_to_mwd_hrs_run3"],
                payload["ta_brt_hrs_run1"],
                payload["ta_brt_hrs_run2"],
                payload["ta_brt_hrs_run3"],
                payload["ta_release_date"],
                payload["ta_release_time"],
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
                  mud_motor1_brand,
                  mud_motor1_size,
                  mud_motor1_sleeve_stb_gauge_in,
                  mud_motor1_sleeve_none,
                  mud_motor1_bend_angle_deg,
                  mud_motor1_lobe,
                  mud_motor1_stage,
                  mud_motor1_ibs_gauge_in,
                  mud_motor1_ibs_none,
                  mud_motor2_brand,
                  mud_motor2_size,
                  mud_motor2_sleeve_stb_gauge_in,
                  mud_motor2_sleeve_none,
                  mud_motor2_bend_angle_deg,
                  mud_motor2_lobe,
                  mud_motor2_stage,
                  mud_motor2_ibs_gauge_in,
                  mud_motor2_ibs_none,
                  bit_brand,
                  bit_kind,
                  bit_type,
                  bit_iadc,
                  bit_serial,
                  bit1_brand,
                  bit1_kind,
                  bit1_type,
                  bit1_iadc,
                  bit1_serial,
                  bit2_brand,
                  bit2_kind,
                  bit2_type,
                  bit2_iadc,
                  bit2_serial,
                  personnel_day_dd_1,
                  personnel_day_dd_2,
                  personnel_day_dd_3,
                  personnel_night_dd_1,
                  personnel_night_dd_2,
                  personnel_night_dd_3,
                  personnel_day_mwd_1,
                  personnel_day_mwd_2,
                  personnel_day_mwd_3,
                  personnel_night_mwd_1,
                  personnel_night_mwd_2,
                  personnel_night_mwd_3,
                  info_casing_shoe,
                  info_casing_od,
                  info_casing_id,
                  info_section_tvd,
                  info_section_md,
                  info_mud_type,
                  ta_call_out_date,
                  ta_crew_mob_time,
                  ta_standby_time_hrs_run1,
                  ta_standby_time_hrs_run2,
                  ta_standby_time_hrs_run3,
                  ta_ru_time_hrs_run1,
                  ta_ru_time_hrs_run2,
                  ta_ru_time_hrs_run3,
                  ta_tripping_time_hrs_run1,
                  ta_tripping_time_hrs_run2,
                  ta_tripping_time_hrs_run3,
                  ta_circulation_time_hrs_run1,
                  ta_circulation_time_hrs_run2,
                  ta_circulation_time_hrs_run3,
                  ta_rotary_time_hrs_run1,
                  ta_rotary_time_hrs_run2,
                  ta_rotary_time_hrs_run3,
                  ta_rotary_meters_run1,
                  ta_rotary_meters_run2,
                  ta_rotary_meters_run3,
                  ta_sliding_time_hrs_run1,
                  ta_sliding_time_hrs_run2,
                  ta_sliding_time_hrs_run3,
                  ta_sliding_meters_run1,
                  ta_sliding_meters_run2,
                  ta_sliding_meters_run3,
                  ta_npt_due_to_rig_hrs_run1,
                  ta_npt_due_to_rig_hrs_run2,
                  ta_npt_due_to_rig_hrs_run3,
                  ta_npt_due_to_motor_hrs_run1,
                  ta_npt_due_to_motor_hrs_run2,
                  ta_npt_due_to_motor_hrs_run3,
                  ta_npt_due_to_mwd_hrs_run1,
                  ta_npt_due_to_mwd_hrs_run2,
                  ta_npt_due_to_mwd_hrs_run3,
                  ta_brt_hrs_run1,
                  ta_brt_hrs_run2,
                  ta_brt_hrs_run3,
                  ta_release_date,
                  ta_release_time,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    payload["mud_motor1_brand"],
                    payload["mud_motor1_size"],
                    payload["mud_motor1_sleeve_stb_gauge_in"],
                    payload["mud_motor1_sleeve_none"],
                    payload["mud_motor1_bend_angle_deg"],
                    payload["mud_motor1_lobe"],
                    payload["mud_motor1_stage"],
                    payload["mud_motor1_ibs_gauge_in"],
                    payload["mud_motor1_ibs_none"],
                    payload["mud_motor2_brand"],
                    payload["mud_motor2_size"],
                    payload["mud_motor2_sleeve_stb_gauge_in"],
                    payload["mud_motor2_sleeve_none"],
                    payload["mud_motor2_bend_angle_deg"],
                    payload["mud_motor2_lobe"],
                    payload["mud_motor2_stage"],
                    payload["mud_motor2_ibs_gauge_in"],
                    payload["mud_motor2_ibs_none"],
                    payload["bit_brand"],
                    payload["bit_kind"],
                    payload["bit_type"],
                    payload["bit_iadc"],
                    payload["bit_serial"],
                    payload["bit1_brand"],
                    payload["bit1_kind"],
                    payload["bit1_type"],
                    payload["bit1_iadc"],
                    payload["bit1_serial"],
                    payload["bit2_brand"],
                    payload["bit2_kind"],
                    payload["bit2_type"],
                    payload["bit2_iadc"],
                    payload["bit2_serial"],
                    payload["personnel_day_dd_1"],
                    payload["personnel_day_dd_2"],
                    payload["personnel_day_dd_3"],
                    payload["personnel_night_dd_1"],
                    payload["personnel_night_dd_2"],
                    payload["personnel_night_dd_3"],
                    payload["personnel_day_mwd_1"],
                    payload["personnel_day_mwd_2"],
                    payload["personnel_day_mwd_3"],
                    payload["personnel_night_mwd_1"],
                    payload["personnel_night_mwd_2"],
                    payload["personnel_night_mwd_3"],
                    payload["info_casing_shoe"],
                    payload["info_casing_od"],
                    payload["info_casing_id"],
                    payload["info_section_tvd"],
                    payload["info_section_md"],
                    payload["info_mud_type"],
                    payload["ta_call_out_date"],
                    payload["ta_crew_mob_time"],
                    payload["ta_standby_time_hrs_run1"],
                    payload["ta_standby_time_hrs_run2"],
                    payload["ta_standby_time_hrs_run3"],
                    payload["ta_ru_time_hrs_run1"],
                    payload["ta_ru_time_hrs_run2"],
                    payload["ta_ru_time_hrs_run3"],
                    payload["ta_tripping_time_hrs_run1"],
                    payload["ta_tripping_time_hrs_run2"],
                    payload["ta_tripping_time_hrs_run3"],
                    payload["ta_circulation_time_hrs_run1"],
                    payload["ta_circulation_time_hrs_run2"],
                    payload["ta_circulation_time_hrs_run3"],
                    payload["ta_rotary_time_hrs_run1"],
                    payload["ta_rotary_time_hrs_run2"],
                    payload["ta_rotary_time_hrs_run3"],
                    payload["ta_rotary_meters_run1"],
                    payload["ta_rotary_meters_run2"],
                    payload["ta_rotary_meters_run3"],
                    payload["ta_sliding_time_hrs_run1"],
                    payload["ta_sliding_time_hrs_run2"],
                    payload["ta_sliding_time_hrs_run3"],
                    payload["ta_sliding_meters_run1"],
                    payload["ta_sliding_meters_run2"],
                    payload["ta_sliding_meters_run3"],
                    payload["ta_npt_due_to_rig_hrs_run1"],
                    payload["ta_npt_due_to_rig_hrs_run2"],
                    payload["ta_npt_due_to_rig_hrs_run3"],
                    payload["ta_npt_due_to_motor_hrs_run1"],
                    payload["ta_npt_due_to_motor_hrs_run2"],
                    payload["ta_npt_due_to_motor_hrs_run3"],
                    payload["ta_npt_due_to_mwd_hrs_run1"],
                    payload["ta_npt_due_to_mwd_hrs_run2"],
                    payload["ta_npt_due_to_mwd_hrs_run3"],
                    payload["ta_brt_hrs_run1"],
                    payload["ta_brt_hrs_run2"],
                    payload["ta_brt_hrs_run3"],
                    payload["ta_release_date"],
                    payload["ta_release_time"],
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
            INSERT INTO well_hse_nozzle (well_id, hole_key, bit_index, line_no, count, size_32nds, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (wid, hkey, 1, i + 1, n.count, n.size_32nds, now)
                for i, n in enumerate(bit1_nozzles)
            ]
            + [
                (wid, hkey, 2, i + 1, n.count, n.size_32nds, now)
                for i, n in enumerate(bit2_nozzles)
            ],
        )


def delete_hole_section(well_id: str, hole_key: str) -> None:
    wid = (well_id or "").strip()
    hkey = (hole_key or "").strip()
    if not wid or not hkey:
        return

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM well_hse_nozzle WHERE well_id = ? AND hole_key = ?",
            (wid, hkey),
        )
        conn.execute(
            "DELETE FROM well_hse_ticket WHERE well_id = ? AND hole_key = ?",
            (wid, hkey),
        )
        conn.execute(
            "DELETE FROM well_hole_section_data WHERE well_id = ? AND hole_key = ?",
            (wid, hkey),
        )
