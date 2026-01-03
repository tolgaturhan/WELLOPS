from __future__ import annotations

from typing import Any, Dict, Optional

from . import ValidationResult


REQUIRED_FIELDS = [
    "kop_m",
    "tvd_planned_m",
    "md_planned_m",
    "max_inc_planned_deg",
    "azimuth_planned_deg",
    "max_dls_planned_deg_per_30m",
    "vs_planned_m",
    "dist_planned_m",
]

FIELD_LABELS = {
    "kop_m": "KOP (m)",
    "tvd_planned_m": "Planned Well TVD (m)",
    "md_planned_m": "Planned Well MD (m)",
    "max_inc_planned_deg": "Planned Max Inc (deg)",
    "azimuth_planned_deg": "Planned Azimuth (deg)",
    "max_dls_planned_deg_per_30m": "Planned Max DLS (deg/30m)",
    "vs_planned_m": "Planned VS (m)",
    "dist_planned_m": "Planned Dist to Plan (m)",
    "tvd_at_td_m": "Well TVD at TD (m)",
    "md_at_td_m": "Well MD at TD (m)",
    "inc_at_td_deg": "Inc at TD (deg)",
    "azimuth_at_td_deg": "Azimuth at TD (deg)",
    "max_dls_actual_deg_per_30m": "Max DLS (deg/30m)",
    "vs_at_td_m": "VS at TD (m)",
    "dist_at_td_m": "Dist to Plan at TD (m)",
}


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def validate_step2(data: Dict[str, Any]) -> ValidationResult:
    """
    Step 2 validation (locked rules):
    PLANNED (required):
    - kop_m >= 0
    - tvd_planned_m > 0
    - md_planned_m > 0
    - md_planned_m >= tvd_planned_m
    - max_inc_planned_deg BETWEEN 0 AND 180
    - azimuth_planned_deg BETWEEN 0 AND 360
    - max_dls_planned_deg_per_30m >= 0
    - vs_planned_m >= 0
    - dist_planned_m >= 0

    ACTUAL (optional, validate only if provided):
    - tvd_at_td_m IS NULL OR tvd_at_td_m > 0
    - md_at_td_m IS NULL OR md_at_td_m > 0
    - (md_at_td_m IS NULL OR tvd_at_td_m IS NULL) OR md_at_td_m >= tvd_at_td_m
    - inc_at_td_deg IS NULL OR inc_at_td_deg BETWEEN 0 AND 180
    - azimuth_at_td_deg IS NULL OR azimuth_at_td_deg BETWEEN 0 AND 360
    - max_dls_actual_deg_per_30m IS NULL OR max_dls_actual_deg_per_30m >= 0
    - vs_at_td_m IS NULL OR vs_at_td_m >= 0
    - dist_at_td_m IS NULL OR dist_at_td_m >= 0

    Messages are English only.
    """
    r = ValidationResult()

    # Required checks (non-empty)
    for field_name in REQUIRED_FIELDS:
        value = data.get(field_name, "")
        if value is None or str(value).strip() == "":
            label = FIELD_LABELS.get(field_name, field_name)
            r.add_field_error(field_name, f"{label} is required.")

    # Parse planned values (numeric)
    kop_m = _to_float(data.get("kop_m"))
    tvd_planned_m = _to_float(data.get("tvd_planned_m"))
    md_planned_m = _to_float(data.get("md_planned_m"))
    max_inc_planned_deg = _to_float(data.get("max_inc_planned_deg"))
    azimuth_planned_deg = _to_float(data.get("azimuth_planned_deg"))
    max_dls_planned = _to_float(data.get("max_dls_planned_deg_per_30m"))
    vs_planned_m = _to_float(data.get("vs_planned_m"))
    dist_planned_m = _to_float(data.get("dist_planned_m"))

    # Numeric validity for planned fields (only if present)
    def _require_number(field: str, val: Optional[float]) -> None:
        if str(data.get(field, "")).strip() != "" and val is None:
            r.add_field_error(field, f"{FIELD_LABELS.get(field, field)} must be a valid number.")

    _require_number("kop_m", kop_m)
    _require_number("tvd_planned_m", tvd_planned_m)
    _require_number("md_planned_m", md_planned_m)
    _require_number("max_inc_planned_deg", max_inc_planned_deg)
    _require_number("azimuth_planned_deg", azimuth_planned_deg)
    _require_number("max_dls_planned_deg_per_30m", max_dls_planned)
    _require_number("vs_planned_m", vs_planned_m)
    _require_number("dist_planned_m", dist_planned_m)

    # Planned checks
    if kop_m is not None and kop_m < 0:
        r.add_field_error("kop_m", "KOP (m) must be greater than or equal to 0.")
    if tvd_planned_m is not None and tvd_planned_m <= 0:
        r.add_field_error("tvd_planned_m", "Planned Well TVD (m) must be greater than 0.")
    if md_planned_m is not None and md_planned_m <= 0:
        r.add_field_error("md_planned_m", "Planned Well MD (m) must be greater than 0.")
    if md_planned_m is not None and tvd_planned_m is not None and md_planned_m < tvd_planned_m:
        r.add_field_error("md_planned_m", "Planned Well MD (m) must be greater than or equal to Planned Well TVD (m).")
    if max_inc_planned_deg is not None and not (0 <= max_inc_planned_deg <= 180):
        r.add_field_error("max_inc_planned_deg", "Planned Max Inc (deg) must be between 0 and 180.")
    if azimuth_planned_deg is not None and not (0 <= azimuth_planned_deg <= 360):
        r.add_field_error("azimuth_planned_deg", "Planned Azimuth (deg) must be between 0 and 360.")
    if max_dls_planned is not None and max_dls_planned < 0:
        r.add_field_error("max_dls_planned_deg_per_30m", "Planned Max DLS (deg/30m) must be greater than or equal to 0.")
    if vs_planned_m is not None and vs_planned_m < 0:
        r.add_field_error("vs_planned_m", "Planned VS (m) must be greater than or equal to 0.")
    if dist_planned_m is not None and dist_planned_m < 0:
        r.add_field_error("dist_planned_m", "Planned Dist to Plan (m) must be greater than or equal to 0.")

    # Actual (optional) numeric parsing
    tvd_at_td_m = _to_float(data.get("tvd_at_td_m"))
    md_at_td_m = _to_float(data.get("md_at_td_m"))
    inc_at_td_deg = _to_float(data.get("inc_at_td_deg"))
    azimuth_at_td_deg = _to_float(data.get("azimuth_at_td_deg"))
    max_dls_actual = _to_float(data.get("max_dls_actual_deg_per_30m"))
    vs_at_td_m = _to_float(data.get("vs_at_td_m"))
    dist_at_td_m = _to_float(data.get("dist_at_td_m"))

    # Numeric validity (actual) - only if provided
    def _optional_number(field: str, val: Optional[float]) -> None:
        if str(data.get(field, "")).strip() != "" and val is None:
            r.add_field_error(field, f"{FIELD_LABELS.get(field, field)} must be a valid number.")

    _optional_number("tvd_at_td_m", tvd_at_td_m)
    _optional_number("md_at_td_m", md_at_td_m)
    _optional_number("inc_at_td_deg", inc_at_td_deg)
    _optional_number("azimuth_at_td_deg", azimuth_at_td_deg)
    _optional_number("max_dls_actual_deg_per_30m", max_dls_actual)
    _optional_number("vs_at_td_m", vs_at_td_m)
    _optional_number("dist_at_td_m", dist_at_td_m)

    # Actual checks (only if value is present)
    if tvd_at_td_m is not None and tvd_at_td_m <= 0:
        r.add_field_error("tvd_at_td_m", "Well TVD at TD (m) must be greater than 0.")
    if md_at_td_m is not None and md_at_td_m <= 0:
        r.add_field_error("md_at_td_m", "Well MD at TD (m) must be greater than 0.")
    if md_at_td_m is not None and tvd_at_td_m is not None and md_at_td_m < tvd_at_td_m:
        r.add_field_error("md_at_td_m", "Well MD at TD (m) must be greater than or equal to Well TVD at TD (m).")
    if inc_at_td_deg is not None and not (0 <= inc_at_td_deg <= 180):
        r.add_field_error("inc_at_td_deg", "Inc at TD (deg) must be between 0 and 180.")
    if azimuth_at_td_deg is not None and not (0 <= azimuth_at_td_deg <= 360):
        r.add_field_error("azimuth_at_td_deg", "Azimuth at TD (deg) must be between 0 and 360.")
    if max_dls_actual is not None and max_dls_actual < 0:
        r.add_field_error("max_dls_actual_deg_per_30m", "Max DLS (deg/30m) must be greater than or equal to 0.")
    if vs_at_td_m is not None and vs_at_td_m < 0:
        r.add_field_error("vs_at_td_m", "VS at TD (m) must be greater than or equal to 0.")
    if dist_at_td_m is not None and dist_at_td_m < 0:
        r.add_field_error("dist_at_td_m", "Dist to Plan at TD (m) must be greater than or equal to 0.")

    return r