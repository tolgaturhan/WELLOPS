# app/core/hole_section_calcs.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, List, Optional, Sequence, Tuple


# -----------------------------
# Time / Date parsing utilities
# -----------------------------
def normalize_hhmm(raw: str) -> str:
    """
    Normalizes user input to HH:MM (24h).
    Accepts examples:
      - "1630"  -> "16:30"
      - "16.30" -> "16:30"
      - "16:30" -> "16:30"
      - "0:0"   -> "00:00"
      - "2400"  -> "24:00" (allowed per your rule)
    Raises ValueError if invalid.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Time value is required.")

    s = s.replace(".", ":")
    s = s.replace(" ", "")

    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid time format.")
        hh_str, mm_str = parts[0], parts[1]
        if not hh_str.isdigit() or not mm_str.isdigit():
            raise ValueError("Invalid time format.")
        hh = int(hh_str)
        mm = int(mm_str)
    else:
        # digits-only, support 1-4 digits
        if not s.isdigit() or len(s) not in (1, 2, 3, 4):
            raise ValueError("Invalid time format.")
        if len(s) in (1, 2):
            # e.g. "1" -> 01:00, "01" -> 01:00
            hh = int(s)
            mm = 0
        elif len(s) == 3:
            # Prefer hour-first for HHO when last digit is 0 and HH is valid (e.g. "010" -> 01:00)
            hh_candidate = int(s[0:2])
            if s[2] == "0" and 0 <= hh_candidate <= 24:
                hh = hh_candidate
                mm = 0
            else:
                # Fallback: "930" -> 09:30
                hh = int(s[0:1])
                mm = int(s[1:3])
        else:
            hh = int(s[0:2])
            mm = int(s[2:4])

    # Special allowance: 24:00 is valid, but only with 00 minutes
    if hh == 24 and mm == 0:
        return "24:00"

    if not (0 <= hh <= 23):
        raise ValueError("Hour must be between 00 and 24.")
    if not (0 <= mm <= 59):
        raise ValueError("Minute must be between 00 and 59.")

    return f"{hh:02d}:{mm:02d}"


def hhmm_to_time(hhmm: str) -> time:
    """
    Converts HH:MM (including 24:00) into datetime.time.
    For 24:00, returns 00:00 and caller must treat as next-day rollover.
    """
    s = normalize_hhmm(hhmm)
    hh, mm = s.split(":")
    h = int(hh)
    m = int(mm)
    if h == 24 and m == 0:
        return time(0, 0)
    return time(h, m)


def parse_decimal(raw: str) -> float:
    """
    Parses a decimal number allowing comma or dot as separator.
    Examples:
      "108,6" -> 108.6
      "107.85" -> 107.85
      " 0 " -> 0.0
    Raises ValueError if invalid or empty.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError("Numeric value is required.")
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    # Allow leading +/-
    try:
        return float(s)
    except Exception as e:
        raise ValueError("Invalid numeric value.") from e


def format_decimal(value: float, decimals: int = 2) -> str:
    """
    Formats float with fixed decimals, trimming unnecessary trailing zeros is not required here.
    """
    return f"{value:.{decimals}f}"


# -----------------------------
# Ticket / Nozzle calculations
# -----------------------------
@dataclass(frozen=True)
class NozzleLine:
    count: int
    size_32nds: int  # nozzle size in 32nds of an inch (integer)


def nozzle_summary(lines: Sequence[NozzleLine]) -> str:
    """
    Example:
      [(5,9), (1,10)] -> "5x9, 1x10"
    """
    parts: List[str] = []
    for ln in lines:
        if ln.count <= 0 or ln.size_32nds <= 0:
            continue
        parts.append(f"{ln.count}x{ln.size_32nds}")
    return ", ".join(parts)


def tfa_from_nozzles(lines: Sequence[NozzleLine]) -> float:
    """
    Total Flow Area (TFA) in square inches using sizes given in 32nds of an inch.
    For each nozzle:
      diameter_in = size_32nds / 32.0
      area_in2 = pi * (diameter_in^2) / 4
    Total area = sum(area * count)

    Returns float (in^2).
    Raises ValueError if no valid nozzle lines.
    """
    valid = [ln for ln in lines if ln.count > 0 and ln.size_32nds > 0]
    if not valid:
        raise ValueError("Nozzle list is empty.")

    import math

    total = 0.0
    for ln in valid:
        d = ln.size_32nds / 32.0
        area = math.pi * (d * d) / 4.0
        total += area * ln.count

    return total


# -----------------------------
# Time analysis calculations
# -----------------------------
def total_drilling_time_hours(rotary_time_hrs: float, sliding_time_hrs: float) -> float:
    """
    TOTAL DRILLING TIME (HRS) = ROTARY TIME (HRS) + SLIDING TIME (HRS)
    """
    return float(rotary_time_hrs) + float(sliding_time_hrs)


def total_drilling_meters(rotary_m: float, sliding_m: float) -> float:
    """
    TOTAL DRILLING (METER) = ROTARY (METER) + SLIDING (METER)
    """
    return float(rotary_m) + float(sliding_m)


def mob_to_release_hours(
    call_out_date: date,
    crew_mob_time_hhmm: str,
    release_date: date,
    release_time_hhmm: str,
) -> float:
    """
    MOB TO RELEASE (HRS) computed from:
      (CALL OUT DATE + CREW MOB TIME) -> (RELEASE DATE + RELEASE TIME)

    Supports '24:00' meaning midnight of the next day for that time field.

    Raises ValueError if inputs invalid or if release < mob.
    """
    mob_hhmm = normalize_hhmm(crew_mob_time_hhmm)
    rel_hhmm = normalize_hhmm(release_time_hhmm)

    mob_time = hhmm_to_time(mob_hhmm)
    rel_time = hhmm_to_time(rel_hhmm)

    mob_dt = datetime.combine(call_out_date, mob_time)
    rel_dt = datetime.combine(release_date, rel_time)

    # Handle 24:00 rollovers
    if mob_hhmm == "24:00":
        mob_dt = mob_dt.replace(hour=0, minute=0)  # already 00:00
        mob_dt = mob_dt.fromtimestamp(mob_dt.timestamp() + 24 * 3600)

    if rel_hhmm == "24:00":
        rel_dt = rel_dt.replace(hour=0, minute=0)
        rel_dt = rel_dt.fromtimestamp(rel_dt.timestamp() + 24 * 3600)

    delta = rel_dt - mob_dt
    hours = delta.total_seconds() / 3600.0
    if hours < 0:
        raise ValueError("Release date/time must be after crew mobilization date/time.")

    return hours


def eff_drilling_percent(drilling_time_hrs: float, total_brt_hrs: float) -> float:
    """
    %EFF DRILLING = (DRILLING TIME / BRT TIME) x 100

    Edge cases:
      - drilling_time = 0, brt > 0 -> 0
      - drilling_time = 0, brt = 0 -> 0
      - brt = 0 -> 0 (avoid division by zero)
    """
    dt = float(drilling_time_hrs)
    brt = float(total_brt_hrs)

    if dt <= 0:
        return 0.0
    if brt <= 0:
        return 0.0

    return (dt / brt) * 100.0
