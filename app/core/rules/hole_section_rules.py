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
    # MUD MOTOR (required combos + required numeric)
    # -------------------------------------------------
    computed["mud_motor_brand"] = _require_choice(data.get("mud_motor_brand"), MUD_MOTOR_BRANDS, "MUD MOTOR / BRAND", errors)
    computed["mud_motor_size"] = _require_choice(data.get("mud_motor_size"), MUD_MOTOR_SIZES, "MUD MOTOR / SIZE", errors)

    # Sleeve STB GAUGE (required, editable number)
    sleeve = _require_decimal(
        data.get("mud_motor_sleeve_stb_gauge_in"),
        "MUD MOTOR / SLEEVE STB GAUGE (IN)",
        errors,
        empty_msg='MUD MOTOR / SLEEVE STB GAUGE (IN) is required (e.g., 12.125).',
    )
    computed["mud_motor_sleeve_stb_gauge_in"] = sleeve

    computed["mud_motor_bend_angle_deg"] = _require_choice(
        data.get("mud_motor_bend_angle_deg"),
        BEND_ANGLES_DEG,
        "MUD MOTOR / BEND ANGLE (DEG)",
        errors,
    )

    # Lobe & Stage (two required combos)
    computed["mud_motor_lobe"] = _require_choice(data.get("mud_motor_lobe"), LOBE_LIST, "MUD MOTOR / LOBE", errors)
    computed["mud_motor_stage"] = _require_choice(data.get("mud_motor_stage"), STAGE_LIST, "MUD MOTOR / STAGE", errors)

    # IBS GAUGE optional numeric
    computed["mud_motor_ibs_gauge_in"] = _optional_decimal(data.get("mud_motor_ibs_gauge_in"), "MUD MOTOR / IBS GAUGE (IN)", errors)

    # -------------------------------------------------
    # BIT (brand + kind combos, plus required fields)
    # -------------------------------------------------
    computed["bit_brand"] = _require_choice(data.get("bit_brand"), BIT_BRANDS, "BIT / BRAND", errors)
    computed["bit_kind"] = _require_choice(data.get("bit_kind"), BIT_KINDS, "BIT / PDC/TRICONE", errors)

    computed["bit_type"] = _require_text(
        data.get("bit_type"),
        "BIT / TYPE",
        errors,
    )

    # IADC optional text (no strict format requested)
    computed["bit_iadc"] = _as_str(data.get("bit_iadc"))

    computed["bit_serial"] = _require_text(
        data.get("bit_serial"),
        "BIT / SERIAL",
        errors,
    )

    # Nozzles required via dialog; TFA auto computed
    nozzles = _parse_nozzles(data.get("bit_nozzles"))
    if not nozzles:
        errors.append("BIT / NOZZLES are required. Please select nozzles to calculate TFA.")
    else:
        try:
            computed["bit_tfa_in2"] = tfa_from_nozzles(nozzles)
        except ValueError:
            errors.append("BIT / NOZZLES are invalid. Please reselect nozzles.")
            computed["bit_tfa_in2"] = None

        # The summary string is UI convenience (not required, but useful)
        try:
            from app.core.hole_section_calcs import nozzle_summary
            computed["bit_nozzle_summary"] = nozzle_summary(nozzles)
        except Exception:
            computed["bit_nozzle_summary"] = ""

    computed["bit_nozzles"] = nozzles

    # -------------------------------------------------
    # PERSONNEL (not required, but at least one must be filled)
    # -------------------------------------------------
    day_dd = _as_str(data.get("personnel_day_dd"))
    night_dd = _as_str(data.get("personnel_night_dd"))
    day_mwd = _as_str(data.get("personnel_day_mwd"))
    night_mwd = _as_str(data.get("personnel_night_mwd"))

    if not (day_dd or night_dd or day_mwd or night_mwd):
        errors.append("PERSONNEL: At least one of DAY DD, NIGHT DD, DAY MWD, NIGHT MWD must be provided.")

    computed["personnel_day_dd"] = day_dd
    computed["personnel_night_dd"] = night_dd
    computed["personnel_day_mwd"] = day_mwd
    computed["personnel_night_mwd"] = night_mwd

    # -------------------------------------------------
    # TIME ANALYSIS (required dates/times, numeric rules, derived fields)
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

    standby = _require_decimal(
        data.get("ta_standby_time_hrs"),
        "TIME ANALYSIS / STANDBY TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=True,
        empty_msg="TIME ANALYSIS / STANDBY TIME (HRS) is required and must be greater than 0.",
    )

    ru = _require_decimal(
        data.get("ta_ru_time_hrs"),
        "TIME ANALYSIS / R/U TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / R/U TIME (HRS).',
    )

    tripping = _require_decimal(
        data.get("ta_tripping_time_hrs"),
        "TIME ANALYSIS / TRIPPING TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / TRIPPING TIME (HRS).',
    )

    circulation = _require_decimal(
        data.get("ta_circulation_time_hrs"),
        "TIME ANALYSIS / CIRCULATION TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / CIRCULATION TIME (HRS).',
    )

    rotary_time = _require_decimal(
        data.get("ta_rotary_time_hrs"),
        "TIME ANALYSIS / ROTARY TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / ROTARY TIME (HRS).',
    )

    rotary_m = _require_decimal(
        data.get("ta_rotary_meters"),
        "TIME ANALYSIS / ROTARY (METER)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / ROTARY (METER).',
    )

    sliding_time = _require_decimal(
        data.get("ta_sliding_time_hrs"),
        "TIME ANALYSIS / SLIDING TIME (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / SLIDING TIME (HRS).',
    )

    sliding_m = _require_decimal(
        data.get("ta_sliding_meters"),
        "TIME ANALYSIS / SLIDING (METER)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / SLIDING (METER).',
    )

    npt_rig = _require_decimal(
        data.get("ta_npt_due_to_rig_hrs"),
        "TIME ANALYSIS / NPT DUE TO RIG (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / NPT DUE TO RIG (HRS).',
    )

    npt_motor = _require_decimal(
        data.get("ta_npt_due_to_motor_hrs"),
        "TIME ANALYSIS / NPT DUE TO MOTOR (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / NPT DUE TO MOTOR (HRS).',
    )

    npt_mwd = _require_decimal(
        data.get("ta_npt_due_to_mwd_hrs"),
        "TIME ANALYSIS / NPT DUE TO MWD (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / NPT DUE TO MWD (HRS).',
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

    total_brt = _require_decimal(
        data.get("ta_total_brt_hrs"),
        "TIME ANALYSIS / TOTAL BRT (HRS)",
        errors,
        min_value=0.0,
        min_strict=False,
        empty_msg='0 or a greater number is required for TIME ANALYSIS / TOTAL BRT (HRS).',
    )

    # Derived: TOTAL DRILLING TIME & METERS
    if rotary_time is not None and sliding_time is not None:
        computed["ta_total_drilling_time_hrs"] = total_drilling_time_hours(rotary_time, sliding_time)
    else:
        computed["ta_total_drilling_time_hrs"] = None

    if rotary_m is not None and sliding_m is not None:
        computed["ta_total_drilling_meters"] = total_drilling_meters(rotary_m, sliding_m)
    else:
        computed["ta_total_drilling_meters"] = None

    # Derived: MOB TO RELEASE (HRS)
    mtr = None
    if call_out_date and crew_mob_time and release_date and release_time:
        try:
            mtr = mob_to_release_hours(call_out_date, crew_mob_time, release_date, release_time)
            computed["ta_mob_to_release_hrs"] = mtr
        except ValueError:
            computed["ta_mob_to_release_hrs"] = None
            errors.append("MOB TO RELEASE is blank. Please verify all date and time inputs.")
    else:
        computed["ta_mob_to_release_hrs"] = None
        # This is a hard requirement per your spec:
        errors.append("MOB TO RELEASE is blank. Please verify all date and time inputs.")

    # Derived: %EFF DRILLING
    if computed.get("ta_total_drilling_time_hrs") is not None and total_brt is not None:
        computed["ta_eff_drilling_pct"] = eff_drilling_percent(
            float(computed["ta_total_drilling_time_hrs"]),
            float(total_brt),
        )
    else:
        computed["ta_eff_drilling_pct"] = 0.0

    # Also pass normalized crew/release times back (UI convenience)
    if crew_mob_time:
        computed["ta_crew_mob_time_norm"] = crew_mob_time
    if release_time:
        computed["ta_release_time_norm"] = release_time

    ok = len(errors) == 0
    return HoleSectionValidationResult(ok=ok, errors=errors, computed=computed)