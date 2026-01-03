from __future__ import annotations

import re
import unicodedata
from typing import Final


# Characters that should be treated as word separators and normalized.
_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[#/\\]+")

# Any character that is NOT A-Z, 0-9, space, dash, dot, underscore will be removed.
_ALLOWED: Final[re.Pattern[str]] = re.compile(r"[^A-Z0-9 ._-]+")

# Collapse multiple spaces/dashes.
_MULTI_SPACE: Final[re.Pattern[str]] = re.compile(r"\s+")
_MULTI_DASH: Final[re.Pattern[str]] = re.compile(r"-{2,}")


def _strip_diacritics(text: str) -> str:
    """
    Remove diacritics from unicode text.
    Example: 'Bülent' -> 'Bulent'
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def to_ascii_upper(text: object) -> str:
    """
    Convert input to ASCII-only uppercase.
    - Strips leading/trailing whitespace
    - Normalizes Turkish dotted/dotless i
    - Removes diacritics (NFKD)
    """
    if text is None:
        return ""

    s = str(text).strip()
    if not s:
        return ""

    # Replace Turkish dotted/dotless i before uppercasing to avoid surprises
    # Note: keep this before diacritics stripping for edge cases.
    s = s.replace("ı", "i").replace("İ", "I").replace("i̇", "i")

    s = _strip_diacritics(s)
    s = s.upper()
    return s


def canonical_text(text: object) -> str:
    """
    Canonical text for general fields (Operator/Contractor/Province/Rig/etc.)

    Rules (v0.1):
    - ASCII-only uppercase
    - Replace separator chars (#, /, \\) with dash
    - Normalize whitespace
    - Remove disallowed characters
    - Normalize dash spacing: "A - B" -> "A-B"
    - Collapse multiple dashes
    - Trim
    """
    s = to_ascii_upper(text)
    if not s:
        return ""

    # Normalize separators to dash early
    s = _SEPARATORS.sub("-", s)

    # Normalize whitespace
    s = _MULTI_SPACE.sub(" ", s).strip()

    # Remove anything not allowed
    s = _ALLOWED.sub("", s)

    # Normalize dashes spacing: "A - B" -> "A-B"
    s = s.replace(" - ", "-").replace("- ", "-").replace(" -", "-")

    # Collapse multiple dashes
    s = _MULTI_DASH.sub("-", s)

    return s.strip()


def canonical_well_name(text: object) -> str:
    """
    Canonical well name input (v0.1).
    Currently identical to canonical_text.
    """
    return canonical_text(text)


def derive_field_name_from_well_key(well_key: str) -> str:
    """
    FIELD (auto) = Well Key without the trailing '-<digits>[A-Z0-9]*' suffix.
    If suffix not present, returns full well_key (canonicalized).
    """
    s = canonical_well_name(well_key)
    if not s:
        return ""

    m = re.fullmatch(r"(.*?)(-\d+[A-Z0-9]*)", s)
    if m:
        return m.group(1).strip()

    return s


def is_well_key_format_ok(well_key: str) -> bool:
    """
    v0.1: Well Key must end with '-<digits>[A-Z0-9]*'.
    Example OK: YAPRAKLI-4
    """
    s = canonical_well_name(well_key)
    if not s:
        return False
    return re.fullmatch(r".*-\d+[A-Z0-9]*", s) is not None