# app/core/hole_section_rules.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from app.core.hole_section_calcs import (
    NozzleLine,
    eff_drilling_percent,
    mob_to_release_hours,
    normalize_hhmm,
    parse_decimal,
    tfa_from_nozzles,
    total_drilling_meters,
    total_drilling_time_hours,
)


# ---------------------------------------------------------------------
# Public option lists (single source of truth for combos)
# ---------------------------------------------------------------------
MUD_MOTOR_BRANDS: Tuple[str, ...] = (
    "NOV",
    "DYNOMAX",
    "SLB",
    "BAKER",
    "HALLIBURTON",
    "WEATHERFORD",
    "JEREH",
)

MUD_MOTOR_SIZES: Tuple[str, ...] = (
    '9 5/8" PDM',
    '9 1/2" PDM',
    '8" PDM',
    '7" PDM',
    '6 3/4" PDM',
    '5" PDM',
    '4 3/4" PDM',
)

BEND_ANGLES_DEG: Tuple[str, ...] = (
    "ZERO",
    "0.39",
    "0.78",
    "1.15",
    "1.50",
    "1.83",
    "2.12",
    "2.38",
    "2.60",
    "2.77",
    "2.89",
    "2.97",
    "3.00",
)

LOBE_LIST: Tuple[str, ...] = (
    "1/2",
    "2/3",
    "3/4",
    "4/5",
    "5/6",
    "6/7",
    "7/8",
    "8/9",
)

STAGE_LIST: Tuple[str, ...] = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "8.3",
)

BIT_BRANDS: Tuple[str, ...] = (
    "NOV",
    "SMITH",
    "BAKER",
    "HALLIBURTON",
    "WEATHERFORD",
    "ULTERA",
    "DBC",
    "VAREL",
    "NOVEL",
    "TECH DRILL",
    "DRILL STAR",
    "MATRIX",
    "TITAN",
    "GATES",
    "EASTERN",
    "LIBERTY",
)

BIT_KINDS: Tuple[str, ...] = (
    "PDC",
    "TRICONE",
    "BICENTER",
)

CASING_OD_OPTIONS: Tuple[str, ...] = (
    "OPEN HOLE",
    '7"',
    '8.625"',
    '9.625"',
    '10.750"',
    '11.750"',
    '13.375"',
    '16"',
    '20"',
)

CASING_ID_BY_OD: Dict[str, Tuple[str, ...]] = {
    "OPEN HOLE": ("OPEN HOLE",),
    '7"': ('6.184"', '6.276"', '6.366"'),
    '8.625"': ('7.921"', '8.097"'),
    '9.625"': ('8.755"', '8.835"', '8.921"'),
    '10.750"': ('9.660"', '9.850"'),
    '11.750"': ('10.772"', '10.920"'),
    '13.375"': ('12.100"', '12.347"'),
    '16"': ('14.868"', '15.124"'),
    '20"': ('18.730"',),
}

CASING_ID_OPTIONS: Tuple[str, ...] = tuple(
    sorted({item for items in CASING_ID_BY_OD.values() for item in items})
)

MUD_TYPE_OPTIONS: Tuple[str, ...] = (
    "AIR",
    "AERATED",
    "BENTONITE",
    "CaCl2 POLYMER",
    "FOAM",
    "GEL",
    "HIGH-TEMPERATURE GEOTHERMAL",
    "KCL-POLYMER",
    "LIGNOSULFONATE",
    "NaCl POLYMER",
    "OIL BASE",
    "PHPA",
    "POLYMER",
    "SPUD",
    "SYNTHETIC BASE",
)


# ---------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class HoleSectionValidationResult:
    ok: bool
    errors: List[str]
    computed: Dict[str, Any]


# ---------------------------------------------------------------------
# Helpers (robust parsing for UI-only stage)
# ---------------------------------------------------------------------
def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    return False


def _as_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _parse_date(v: Any) -> Optional[date]:
    """
    Accepts:
      - datetime.date
      - datetime.datetime
      - string in ISO 'YYYY-MM-DD'
      - string in 'dd.MM.yyyy'
    """
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # ISO
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            pass
        # dd.MM.yyyy
        try:
            return datetime.strptime(s, "%d.%m.%Y").date()
        except Exception:
            return None
    return None


def _require_choice(value: Any, allowed: Sequence[str], field_label: str, errors: List[str]) -> str:
    s = _as_str(value)
    if not s:
        errors.append(f"{field_label} is required.")
        return ""
    if s not in allowed:
        errors.append(f"{field_label} must be selected from the list.")
        return ""
    return s


def _optional_choice(value: Any, allowed: Sequence[str], field_label: str, errors: List[str]) -> str:
    s = _as_str(value)
    if not s:
        return ""
    if s not in allowed:
        errors.append(f"{field_label} must be selected from the list.")
        return ""
    return s


def _require_text(value: Any, field_label: str, errors: List[str]) -> str:
    s = _as_str(value)
    if not s:
        errors.append(f"{field_label} is required.")
        return ""
    return s


def _require_decimal(
    value: Any,
    field_label: str,
    errors: List[str],
    *,
    min_value: Optional[float] = None,
    min_strict: bool = False,
    empty_msg: Optional[str] = None,
) -> Optional[float]:
    """
    Parses decimal allowing comma/dot.
    - If empty: pushes empty_msg or default required message.
    - If min_value provided:
        - min_strict True => value must be > min_value
        - else => value must be >= min_value
    """
    if _is_blank(value):
        errors.append(empty_msg or f"{field_label} is required.")
        return None
    try:
        x = parse_decimal(_as_str(value))
    except ValueError:
        errors.append(f"{field_label} must be a valid number.")
        return None

    if min_value is not None:
        if min_strict and not (x > min_value):
            errors.append(f"{field_label} must be greater than {min_value}.")
            return None
        if not min_strict and not (x >= min_value):
            errors.append(f"{field_label} must be {min_value} or greater.")
            return None

    return x


def _optional_decimal(value: Any, field_label: str, errors: List[str]) -> Optional[float]:
    if _is_blank(value):
        return None
    try:
        return parse_decimal(_as_str(value))
    except ValueError:
        errors.append(f"{field_label} must be a valid number.")
        return None


def _require_date(value: Any, field_label: str, errors: List[str], *, empty_msg: Optional[str] = None) -> Optional[date]:
    d = _parse_date(value)
    if d is None:
        errors.append(empty_msg or f"{field_label} is required.")
        return None
    return d


def _require_time_hhmm(value: Any, field_label: str, errors: List[str], *, empty_msg: Optional[str] = None) -> Optional[str]:
    if _is_blank(value):
        errors.append(empty_msg or f"{field_label} is required.")
        return None
    try:
        return normalize_hhmm(_as_str(value))
    except ValueError:
        errors.append(f"{field_label} must be in HH:MM format (24-hour).")
        return None


def _parse_nozzles(value: Any) -> List[NozzleLine]:
    """
    Accepts:
      - list[NozzleLine]
      - list[tuple(count, size_32nds)]
      - list[dict] with keys {count,size_32nds} or {count,size}
    """
    if value is None:
        return []

    if isinstance(value, list):
        out: List[NozzleLine] = []
        for item in value:
            if isinstance(item, NozzleLine):
                out.append(item)
                continue
            if isinstance(item, tuple) and len(item) == 2:
                try:
                    c = int(item[0])
                    s = int(item[1])
                    out.append(NozzleLine(count=c, size_32nds=s))
                except Exception:
                    continue
                continue
            if isinstance(item, dict):
                try:
                    c = int(item.get("count", 0))
                    s = int(item.get("size_32nds", item.get("size", 0)))
                    out.append(NozzleLine(count=c, size_32nds=s))
                except Exception:
                    continue
        return out

    return []


# ---------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------
def validate_hole_section(section_data: Dict[str, Any]) -> HoleSectionValidationResult:
    """
    Validates Hole Section Form according to your specification.

    Notes:
      - Ticket section is NOT required (no validation enforced).
      - English-only messages.
      - Returns computed derived fields in `computed` so UI can populate read-only boxes.
    """
    errors: List[str] = []
    computed: Dict[str, Any] = {}

    data = section_data or {}

    # -------------------------------------------------
    # MUD MOTOR-1 (required) + MUD MOTOR-2 (optional)
    # If DD Well Type is ONLY INCLINATION, MUD MOTOR-1 is optional.
    # -------------------------------------------------
    mm1_brand_raw = data.get("mud_motor1_brand") or data.get("mud_motor_brand")
    mm1_size_raw = data.get("mud_motor1_size") or data.get("mud_motor_size")
    mm1_sleeve_raw = data.get("mud_motor1_sleeve_stb_gauge_in") or data.get("mud_motor_sleeve_stb_gauge_in")
    mm1_bend_raw = data.get("mud_motor1_bend_angle_deg") or data.get("mud_motor_bend_angle_deg")
    mm1_lobe_raw = data.get("mud_motor1_lobe") or data.get("mud_motor_lobe")
    mm1_stage_raw = data.get("mud_motor1_stage") or data.get("mud_motor_stage")
    mm1_ibs_raw = data.get("mud_motor1_ibs_gauge_in") or data.get("mud_motor_ibs_gauge_in")

    dd_well_type = _as_str(data.get("dd_well_type"))
    mm1_optional = dd_well_type == "ONLY INCLINATION"

    if mm1_optional and _is_blank(mm1_brand_raw) and _is_blank(mm1_size_raw) and _is_blank(mm1_sleeve_raw) and _is_blank(mm1_bend_raw) and _is_blank(mm1_lobe_raw) and _is_blank(mm1_stage_raw) and _is_blank(mm1_ibs_raw):
        computed["mud_motor1_brand"] = ""
        computed["mud_motor1_size"] = ""
        computed["mud_motor1_sleeve_stb_gauge_in"] = None
        computed["mud_motor1_bend_angle_deg"] = ""
        computed["mud_motor1_lobe"] = ""
        computed["mud_motor1_stage"] = ""
        computed["mud_motor1_ibs_gauge_in"] = None
    else:
        computed["mud_motor1_brand"] = _require_choice(mm1_brand_raw, MUD_MOTOR_BRANDS, "MUD MOTOR-1 / BRAND", errors)
        computed["mud_motor1_size"] = _require_choice(mm1_size_raw, MUD_MOTOR_SIZES, "MUD MOTOR-1 / SIZE", errors)

        sleeve = _require_decimal(
            mm1_sleeve_raw,
            "MUD MOTOR-1 / SLEEVE STB GAUGE (IN)",
            errors,
            empty_msg='MUD MOTOR-1 / SLEEVE STB GAUGE (IN) is required (e.g., 12.125).',
        )
        computed["mud_motor1_sleeve_stb_gauge_in"] = sleeve

        computed["mud_motor1_bend_angle_deg"] = _require_choice(
            mm1_bend_raw,
            BEND_ANGLES_DEG,
            "MUD MOTOR-1 / BEND ANGLE (DEG)",
            errors,
        )

        computed["mud_motor1_lobe"] = _require_choice(mm1_lobe_raw, LOBE_LIST, "MUD MOTOR-1 / LOBE", errors)
        computed["mud_motor1_stage"] = _require_choice(mm1_stage_raw, STAGE_LIST, "MUD MOTOR-1 / STAGE", errors)

        computed["mud_motor1_ibs_gauge_in"] = _optional_decimal(mm1_ibs_raw, "MUD MOTOR-1 / IBS GAUGE (IN)", errors)

    mm2_brand_raw = _as_str(data.get("mud_motor2_brand"))
    mm2_size_raw = _as_str(data.get("mud_motor2_size"))
    mm2_sleeve_raw = data.get("mud_motor2_sleeve_stb_gauge_in")
    mm2_bend_raw = _as_str(data.get("mud_motor2_bend_angle_deg"))
    mm2_lobe_raw = _as_str(data.get("mud_motor2_lobe"))
    mm2_stage_raw = _as_str(data.get("mud_motor2_stage"))
    mm2_ibs_raw = data.get("mud_motor2_ibs_gauge_in")

    mm2_has_other = any([mm2_size_raw, mm2_bend_raw, mm2_lobe_raw, mm2_stage_raw, _as_str(mm2_sleeve_raw), _as_str(mm2_ibs_raw)])
    if mm2_brand_raw or mm2_has_other:
        if not mm2_brand_raw:
            errors.append("MUD MOTOR-2 / BRAND is required when MUD MOTOR-2 fields are provided.")
        computed["mud_motor2_brand"] = _require_choice(mm2_brand_raw, MUD_MOTOR_BRANDS, "MUD MOTOR-2 / BRAND", errors)
        computed["mud_motor2_size"] = _require_choice(mm2_size_raw, MUD_MOTOR_SIZES, "MUD MOTOR-2 / SIZE", errors)

        sleeve2 = _require_decimal(
            mm2_sleeve_raw,
            "MUD MOTOR-2 / SLEEVE STB GAUGE (IN)",
            errors,
            empty_msg='MUD MOTOR-2 / SLEEVE STB GAUGE (IN) is required (e.g., 12.125).',
        )
        computed["mud_motor2_sleeve_stb_gauge_in"] = sleeve2

        computed["mud_motor2_bend_angle_deg"] = _require_choice(
            mm2_bend_raw,
            BEND_ANGLES_DEG,
            "MUD MOTOR-2 / BEND ANGLE (DEG)",
            errors,
        )
        computed["mud_motor2_lobe"] = _require_choice(mm2_lobe_raw, LOBE_LIST, "MUD MOTOR-2 / LOBE", errors)
        computed["mud_motor2_stage"] = _require_choice(mm2_stage_raw, STAGE_LIST, "MUD MOTOR-2 / STAGE", errors)
        computed["mud_motor2_ibs_gauge_in"] = _optional_decimal(mm2_ibs_raw, "MUD MOTOR-2 / IBS GAUGE (IN)", errors)
    else:
        computed["mud_motor2_brand"] = ""
        computed["mud_motor2_size"] = ""
        computed["mud_motor2_sleeve_stb_gauge_in"] = None
        computed["mud_motor2_bend_angle_deg"] = ""
        computed["mud_motor2_lobe"] = ""
        computed["mud_motor2_stage"] = ""
        computed["mud_motor2_ibs_gauge_in"] = None

    # -------------------------------------------------
    # BIT-1 (required) + BIT-2 (optional)
    # -------------------------------------------------
    bit1_brand_raw = data.get("bit1_brand") or data.get("bit_brand")
    bit1_kind_raw = data.get("bit1_kind") or data.get("bit_kind")
    bit1_type_raw = data.get("bit1_type") or data.get("bit_type")
    bit1_iadc_raw = data.get("bit1_iadc") or data.get("bit_iadc")
    bit1_serial_raw = data.get("bit1_serial") or data.get("bit_serial")
    bit1_nozzles = _parse_nozzles(data.get("bit1_nozzles") or data.get("bit_nozzles"))

    computed["bit1_brand"] = _require_choice(bit1_brand_raw, BIT_BRANDS, "BIT-1 / BRAND", errors)
    computed["bit1_kind"] = _require_choice(bit1_kind_raw, BIT_KINDS, "BIT-1 / PDC/TRICONE", errors)
    computed["bit1_type"] = _require_text(bit1_type_raw, "BIT-1 / TYPE", errors)
    computed["bit1_iadc"] = _as_str(bit1_iadc_raw)
    computed["bit1_serial"] = _require_text(bit1_serial_raw, "BIT-1 / SERIAL", errors)

    if not bit1_nozzles:
        errors.append("BIT-1 / NOZZLES are required. Please select nozzles to calculate TFA.")
    else:
        try:
            computed["bit1_tfa_in2"] = tfa_from_nozzles(bit1_nozzles)
        except ValueError:
            errors.append("BIT-1 / NOZZLES are invalid. Please reselect nozzles.")
            computed["bit1_tfa_in2"] = None

        try:
            from app.core.hole_section_calcs import nozzle_summary
            computed["bit1_nozzle_summary"] = nozzle_summary(bit1_nozzles)
        except Exception:
            computed["bit1_nozzle_summary"] = ""

    computed["bit1_nozzles"] = bit1_nozzles

    bit2_brand_raw = _as_str(data.get("bit2_brand"))
    bit2_kind_raw = _as_str(data.get("bit2_kind"))
    bit2_type_raw = _as_str(data.get("bit2_type"))
    bit2_iadc_raw = _as_str(data.get("bit2_iadc"))
    bit2_serial_raw = _as_str(data.get("bit2_serial"))
    bit2_nozzles = _parse_nozzles(data.get("bit2_nozzles"))

    bit2_has_other = any([bit2_kind_raw, bit2_type_raw, bit2_iadc_raw, bit2_serial_raw]) or bool(bit2_nozzles)
    if bit2_brand_raw or bit2_has_other:
        if not bit2_brand_raw:
            errors.append("BIT-2 / BRAND is required when BIT-2 fields are provided.")
        computed["bit2_brand"] = _require_choice(bit2_brand_raw, BIT_BRANDS, "BIT-2 / BRAND", errors)
        computed["bit2_kind"] = _require_choice(bit2_kind_raw, BIT_KINDS, "BIT-2 / PDC/TRICONE", errors)
        computed["bit2_type"] = _require_text(bit2_type_raw, "BIT-2 / TYPE", errors)
        computed["bit2_iadc"] = bit2_iadc_raw
        computed["bit2_serial"] = _require_text(bit2_serial_raw, "BIT-2 / SERIAL", errors)

        if not bit2_nozzles:
            errors.append("BIT-2 / NOZZLES are required. Please select nozzles to calculate TFA.")
        else:
            try:
                computed["bit2_tfa_in2"] = tfa_from_nozzles(bit2_nozzles)
            except ValueError:
                errors.append("BIT-2 / NOZZLES are invalid. Please reselect nozzles.")
                computed["bit2_tfa_in2"] = None

            try:
                from app.core.hole_section_calcs import nozzle_summary
                computed["bit2_nozzle_summary"] = nozzle_summary(bit2_nozzles)
            except Exception:
                computed["bit2_nozzle_summary"] = ""
    else:
        computed["bit2_brand"] = ""
        computed["bit2_kind"] = ""
        computed["bit2_type"] = ""
        computed["bit2_iadc"] = ""
        computed["bit2_serial"] = ""

    computed["bit2_nozzles"] = bit2_nozzles

    # -------------------------------------------------
    # PERSONNEL (not required, but at least one must be filled)
    # -------------------------------------------------
    personnel_keys = [
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
    personnel_vals = [_as_str(data.get(k)) for k in personnel_keys]
    if not any(personnel_vals):
        errors.append(
            "PERSONNEL: At least one of DAY DD, NIGHT DD, DAY MWD, NIGHT MWD must be provided."
        )

    for k, v in zip(personnel_keys, personnel_vals):
        computed[k] = v

    # -------------------------------------------------
    # INFO (casing OD/ID required)
    # -------------------------------------------------
    casing_od = _require_choice(
        data.get("info_casing_od"),
        CASING_OD_OPTIONS,
        "INFO / CASING OD",
        errors,
    )
    casing_id = _require_choice(
        data.get("info_casing_id"),
        CASING_ID_OPTIONS,
        "INFO / CASING ID",
        errors,
    )
    if casing_od and casing_id:
        allowed_ids = CASING_ID_BY_OD.get(casing_od, ())
        if casing_id not in allowed_ids:
            errors.append("INFO / CASING ID is not valid for the selected CASING OD.")

    if casing_od and casing_id:
        if casing_od == "OPEN HOLE" and casing_id == "OPEN HOLE":
            computed["info_casing_shoe"] = 0.0
        else:
            computed["info_casing_shoe"] = _require_decimal(
                data.get("info_casing_shoe"),
                "INFO / CASING SHOE (METER)",
                errors,
                min_value=0.0,
                min_strict=True,
                empty_msg="INFO / CASING SHOE (METER) is required and must be greater than 0.",
            )
    else:
        computed["info_casing_shoe"] = _require_decimal(
            data.get("info_casing_shoe"),
            "INFO / CASING SHOE (METER)",
            errors,
            min_value=0.0,
            min_strict=True,
            empty_msg="INFO / CASING SHOE (METER) is required and must be greater than 0.",
        )

    computed["info_mud_type"] = _require_choice(
        data.get("info_mud_type"),
        MUD_TYPE_OPTIONS,
        "INFO / MUD TYPE",
        errors,
    )

    computed["info_section_tvd"] = _require_decimal(
        data.get("info_section_tvd"),
        "INFO / SECTION TVD (METER)",
        errors,
        min_value=0.0,
        min_strict=True,
        empty_msg="INFO / SECTION TVD (METER) is required and must be greater than 0.",
    )
    computed["info_section_md"] = _require_decimal(
        data.get("info_section_md"),
        "INFO / SECTION MD (METER)",
        errors,
        min_value=0.0,
        min_strict=True,
        empty_msg="INFO / SECTION MD (METER) is required and must be greater than 0.",
    )

    # -------------------------------------------------
    # TIME ANALYSIS (runs + derived fields)
    # -------------------------------------------------
    call_out_date = _require_date(
        data.get("ta_call_out_date"),
        "TIME ANALYSIS / CALL OUT DATE",
        errors,
        empty_msg=(
            "TIME ANALYSIS / CALL OUT DATE is required. "
            "If the prev. sec. isn't released, select the day after the last invoice date."
        ),
    )
    crew_mob_time = _require_time_hhmm(
        data.get("ta_crew_mob_time"),
        "TIME ANALYSIS / CREW MOB TIME",
        errors,
        empty_msg="TIME ANALYSIS / CREW MOB TIME is required (e.g., 16:30, 24:00, 00:00).",
    )

    release_date = _require_date(
        data.get("ta_release_date"),
        "TIME ANALYSIS / RELEASE DATE",
        errors,
        empty_msg="TIME ANALYSIS / RELEASE DATE is required. Important: If not released, choose the latest invoice date.",
    )
    release_time = _require_time_hhmm(
        data.get("ta_release_time"),
        "TIME ANALYSIS / RELEASE TIME",
        errors,
        empty_msg="TIME ANALYSIS / RELEASE TIME is required. Important: If not released, use 00:00 as the time value.",
    )

    run_fields = [
        ("ta_standby_time_hrs", "STANDBY TIME (HRS)", 0.0, True, "TIME ANALYSIS / STANDBY TIME (HRS) is required and must be greater than 0."),
        ("ta_ru_time_hrs", "R/U TIME (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / R/U TIME (HRS)."),
        ("ta_tripping_time_hrs", "TRIPPING TIME (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / TRIPPING TIME (HRS)."),
        ("ta_circulation_time_hrs", "CIRCULATION TIME (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / CIRCULATION TIME (HRS)."),
        ("ta_rotary_time_hrs", "ROTARY TIME (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / ROTARY TIME (HRS)."),
        ("ta_rotary_meters", "ROTARY (METER)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / ROTARY (METER)."),
        ("ta_sliding_time_hrs", "SLIDING TIME (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / SLIDING TIME (HRS)."),
        ("ta_sliding_meters", "SLIDING (METER)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / SLIDING (METER)."),
        ("ta_npt_due_to_rig_hrs", "NPT DUE TO RIG (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / NPT DUE TO RIG (HRS)."),
        ("ta_npt_due_to_motor_hrs", "NPT DUE TO MOTOR (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / NPT DUE TO MOTOR (HRS)."),
        ("ta_npt_due_to_mwd_hrs", "NPT DUE TO MWD (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / NPT DUE TO MWD (HRS)."),
        ("ta_brt_hrs", "BRT (HRS)", 0.0, False, "0 or a greater number is required for TIME ANALYSIS / BRT (HRS)."),
    ]

    def _run_value(key: str, run: int) -> Any:
        if run == 1:
            return data.get(f"{key}_run1") if data.get(f"{key}_run1") is not None else data.get(key)
        return data.get(f"{key}_run{run}")

    def _run_has_any(run: int) -> bool:
        for key, _label, _min, _strict, _msg in run_fields:
            if not _is_blank(_run_value(key, run)):
                return True
        return False

    run_values: Dict[int, Dict[str, Optional[float]]] = {1: {}, 2: {}, 3: {}}
    for run in (1, 2, 3):
        required = run == 1 or _run_has_any(run)
        for key, label, min_value, min_strict, empty_msg in run_fields:
            raw = _run_value(key, run)
            field_label = f"TIME ANALYSIS / {label} (RUN-{run})"
            if required:
                run_values[run][key] = _require_decimal(
                    raw,
                    field_label,
                    errors,
                    min_value=min_value,
                    min_strict=min_strict,
                    empty_msg=empty_msg.replace("TIME ANALYSIS / ", f"TIME ANALYSIS / ").replace(label, f"{label} (RUN-{run})"),
                )
            else:
                run_values[run][key] = _optional_decimal(raw, field_label, errors)

    # Derived: TOTAL DRILLING TIME & METERS per run + section total
    total_drilling_time_runs: Dict[int, Optional[float]] = {}
    total_drilling_m_runs: Dict[int, Optional[float]] = {}
    for run in (1, 2, 3):
        rt = run_values[run].get("ta_rotary_time_hrs")
        st = run_values[run].get("ta_sliding_time_hrs")
        if rt is not None and st is not None:
            total_drilling_time_runs[run] = total_drilling_time_hours(rt, st)
        else:
            total_drilling_time_runs[run] = None

        rm = run_values[run].get("ta_rotary_meters")
        sm = run_values[run].get("ta_sliding_meters")
        if rm is not None and sm is not None:
            total_drilling_m_runs[run] = total_drilling_meters(rm, sm)
        else:
            total_drilling_m_runs[run] = None

        computed[f"ta_total_drilling_time_hrs_run{run}"] = total_drilling_time_runs[run]
        computed[f"ta_total_drilling_meters_run{run}"] = total_drilling_m_runs[run]

    total_drilling_time_total = sum(v for v in total_drilling_time_runs.values() if v is not None) if any(
        v is not None for v in total_drilling_time_runs.values()
    ) else None
    total_drilling_m_total = sum(v for v in total_drilling_m_runs.values() if v is not None) if any(
        v is not None for v in total_drilling_m_runs.values()
    ) else None

    computed["ta_total_drilling_time_hrs_total"] = total_drilling_time_total
    computed["ta_total_drilling_meters_total"] = total_drilling_m_total

    # Derived: MOB TO RELEASE (HRS)
    if call_out_date and crew_mob_time and release_date and release_time:
        try:
            mtr = mob_to_release_hours(call_out_date, crew_mob_time, release_date, release_time)
            computed["ta_mob_to_release_hrs"] = mtr
        except ValueError:
            computed["ta_mob_to_release_hrs"] = None
            errors.append("MOB TO RELEASE is blank. Please verify all date and time inputs.")
    else:
        computed["ta_mob_to_release_hrs"] = None
        errors.append("MOB TO RELEASE is blank. Please verify all date and time inputs.")

    # Derived: %EFF DRILLING
    for run in (1, 2, 3):
        brt = run_values[run].get("ta_brt_hrs")
        tdt = total_drilling_time_runs[run]
        if tdt is not None and brt is not None:
            if brt == 0 and tdt == 0:
                computed[f"ta_eff_drilling_pct_run{run}"] = 0.0
            elif brt > 0:
                computed[f"ta_eff_drilling_pct_run{run}"] = eff_drilling_percent(float(tdt), float(brt))
            else:
                computed[f"ta_eff_drilling_pct_run{run}"] = None
        else:
            computed[f"ta_eff_drilling_pct_run{run}"] = None

    brt_total = sum(v for v in (run_values[1].get("ta_brt_hrs"), run_values[2].get("ta_brt_hrs"), run_values[3].get("ta_brt_hrs")) if v is not None)
    if total_drilling_time_total is not None:
        if brt_total == 0 and total_drilling_time_total == 0:
            computed["ta_eff_drilling_pct_total"] = 0.0
        elif brt_total > 0:
            computed["ta_eff_drilling_pct_total"] = eff_drilling_percent(float(total_drilling_time_total), float(brt_total))
        else:
            computed["ta_eff_drilling_pct_total"] = None
    else:
        computed["ta_eff_drilling_pct_total"] = None

    if crew_mob_time:
        computed["ta_crew_mob_time_norm"] = crew_mob_time
    if release_time:
        computed["ta_release_time_norm"] = release_time

    ok = len(errors) == 0
    return HoleSectionValidationResult(ok=ok, errors=errors, computed=computed)
