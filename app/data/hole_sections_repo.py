from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Set

from app.data.db import get_connection


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_enabled_hole_sizes(well_id: str) -> Set[str]:
    wid = (well_id or "").strip()
    if not wid:
        return set()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT node_key
            FROM well_hole_sections
            WHERE well_id = ? AND is_enabled = 1
            """,
            (wid,),
        ).fetchall()

    return {str(r["node_key"]) for r in rows}


def save_enabled_hole_sizes(well_id: str, enabled_set: Iterable[str]) -> None:
    wid = (well_id or "").strip()
    if not wid:
        raise ValueError("well_id is required")

    now = iso_now()
    enabled = {str(k) for k in enabled_set if str(k).strip()}

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM well_hole_sections WHERE well_id = ?",
            (wid,),
        )
        if enabled:
            conn.executemany(
                """
                INSERT INTO well_hole_sections (well_id, node_key, is_enabled, updated_at)
                VALUES (?, ?, 1, ?)
                """,
                [(wid, node_key, now) for node_key in sorted(enabled)],
            )
