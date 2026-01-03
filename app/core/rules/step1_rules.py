from __future__ import annotations

from typing import Any, Dict

from . import ValidationResult
from app.core.canonical import is_well_key_format_ok, canonical_text, canonical_well_name


REQUIRED_FIELDS = [
    "well_name",
    "operator",
    "contractor",
    "well_purpose",
    "well_type",
    "dd_well_type",
    "province",
    "rig_name",
]

FIELD_LABELS = {
    "well_name": "Well Name",
    "operator": "Operator",
    "contractor": "Contractor",
    "well_purpose": "Well Purpose",
    "well_type": "Well Type",
    "dd_well_type": "DD Well Type",
    "province": "Province",
    "rig_name": "Rig Name",
}

# Dummy / placeholder values that must be treated as EMPTY (canonicalized forms)
_INVALID_PLACEHOLDER_VALUES = {
    "SELECT OR ENTER MANUALLY",
    "SELECT FROM LIST",
    "AUTOMATICALLY GENERATED",
}


def validate_step1(data: Dict[str, Any]) -> ValidationResult:
    """
    Step 1 validation (locked rules):
    - Required fields must not be empty.
    - Dummy placeholder values are treated as empty.
    - Notes is optional (not validated here).
    - Messages are English only.
    """
    r = ValidationResult()

    for field_name in REQUIRED_FIELDS:
        raw_value = data.get(field_name, "")
        # Always treat placeholders as empty using canonicalization
        value_canon = canonical_text(raw_value)

        if value_canon == "" or value_canon in _INVALID_PLACEHOLDER_VALUES:
            label = FIELD_LABELS.get(field_name, field_name)
            r.add_field_error(field_name, f"{label} is required.")

    # Well Key format check (only if both provided)
    well_key = canonical_well_name(data.get("well_key", ""))
    well_name = canonical_well_name(data.get("well_name", ""))

    if well_name and well_key and not is_well_key_format_ok(well_key):
        r.add_field_error(
            "well_name",
            "Well Name must end with a dash followed by digits, optionally followed by letters or digits (e.g., YAPRAKLI-4, YAPRAKLI-4S, YAPRAKLI-4ST, YAPRAKLI-1K2).",
        )

    return r