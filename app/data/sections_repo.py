# app/data/sections_repo.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.data.db import get_connection
from app.sections import builder


class NodeFlags(TypedDict, total=False):
    node_key: str
    title: str
    node_type: str
    parent_id: Optional[str]
    order_index: int
    is_enabled: bool
    is_selected: bool
    is_completed: bool


def ensure_section_tree(well_id: str, step1_context: Dict[str, Any]) -> None:
    """
    Builds/materializes the per-well section tree in DB using builder.ensure_section_tree().
    Must be called AFTER Step1 is validated & saved (needs well_type etc).
    """
    conn = get_connection()
    try:
        builder.ensure_section_tree(conn, str(well_id), step1_context)
    finally:
        conn.close()


def set_section_selected(well_id: str, node_key: str, selected: bool) -> None:
    """Persists selection for a SECTION node."""
    conn = get_connection()
    try:
        builder.set_section_selected(conn, str(well_id), str(node_key), bool(selected))
    finally:
        conn.close()


def get_selected_sections(well_id: str) -> List[str]:
    """Returns selected + enabled SECTION node_keys ordered by order_index."""
    conn = get_connection()
    try:
        return builder.get_selected_sections(conn, str(well_id))
    finally:
        conn.close()


def get_node_flags(well_id: str, node_key: str) -> Optional[NodeFlags]:
    """
    Reads node flags directly from DB. Useful for router decisions.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT node_key, title, node_type, parent_id, order_index,
                   is_enabled, is_selected, is_completed
            FROM well_section_nodes
            WHERE well_id = ? AND node_key = ?
            """,
            (str(well_id), str(node_key)),
        ).fetchone()

        if not row:
            return None

        return NodeFlags(
            node_key=row["node_key"],
            title=row["title"],
            node_type=row["node_type"],
            parent_id=row["parent_id"],
            order_index=int(row["order_index"]),
            is_enabled=bool(row["is_enabled"]),
            is_selected=bool(row["is_selected"]),
            is_completed=bool(row["is_completed"]),
        )
    finally:
        conn.close()


def is_section_selected(well_id: str, node_key: str) -> bool:
    """True if node exists and is_enabled=1 and is_selected=1 for SECTION nodes."""
    flags = get_node_flags(well_id, node_key)
    if not flags:
        return False
    if flags.get("node_type") != "SECTION":
        return False
    return bool(flags.get("is_enabled", False) and flags.get("is_selected", False))