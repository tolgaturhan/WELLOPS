from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.sections.repository import load_template


def iso_now() -> str:
    # UTC ISO 8601
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def uuid4_str() -> str:
    return str(uuid.uuid4())


# -----------------------------
# Template selection
# -----------------------------
def choose_template(step1_context: Dict[str, Any]) -> Tuple[str, int]:
    """
    Minimal template selection logic.
    Expand later using province/field/operator/etc. if needed.
    """
    wt = (step1_context.get("well_type") or "").strip().upper()
    if wt == "DD":
        return ("default_dd", 1)
    return ("default_generic", 1)


# -----------------------------
# Rules engine (minimal)
# -----------------------------
def apply_rules(template: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies template.rules to a deep-copied template object.
    Supported:
      - when: {field, op=equals, value}
      - then: [{action: enable/disable/select/deselect, target: node_key}]
    """
    t = copy.deepcopy(template)

    def match(cond: Dict[str, Any]) -> bool:
        field = cond.get("field")
        op = cond.get("op")
        value = cond.get("value")
        actual = context.get(field)
        if op == "equals":
            return actual == value
        return False

    def normalize_defaults(node: Dict[str, Any]) -> None:
        nt = node.get("node_type")
        if nt in ("SECTION", "ITEM"):
            node.setdefault("enabled", True)
        if nt == "SECTION":
            node.setdefault("selected", False)
        for ch in node.get("children", []) or []:
            normalize_defaults(ch)

    def set_node_flag(root: Dict[str, Any], target_key: str, action: str) -> None:
        stack = [root]
        while stack:
            n = stack.pop()
            if n.get("node_key") == target_key:
                if action == "enable":
                    n["enabled"] = True
                elif action == "disable":
                    n["enabled"] = False
                elif action == "select":
                    n["selected"] = True
                elif action == "deselect":
                    n["selected"] = False
                return
            stack.extend(n.get("children", []) or [])

    normalize_defaults(t["root"])

    for rule in t.get("rules", []) or []:
        if not match(rule.get("when", {})):
            continue
        for action in rule.get("then", []) or []:
            act = action.get("action")
            target = action.get("target")
            if act and target:
                set_node_flag(t["root"], target, act)

    return t


# -----------------------------
# DB helpers (sqlite3 compatible)
# Expect: conn is sqlite3.Connection (or anything with .execute and context manager)
# -----------------------------
def db_has_any_nodes(conn, well_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM well_section_nodes WHERE well_id = ? LIMIT 1",
        (well_id,),
    ).fetchone()
    return row is not None


def db_delete_nodes(conn, well_id: str) -> None:
    conn.execute("DELETE FROM well_section_nodes WHERE well_id = ?", (well_id,))


def db_get_well_sections_meta(conn, well_id: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT section_template_key, sections_version FROM wells WHERE well_id = ?",
        (well_id,),
    ).fetchone()
    if row is None:
        return None
    return {"section_template_key": row[0], "sections_version": row[1]}


def db_update_well_sections_meta(conn, well_id: str, template_key: str, version: int, now: str) -> None:
    conn.execute(
        """
        UPDATE wells
        SET section_template_key = ?, sections_version = ?, updated_at = ?
        WHERE well_id = ?
        """,
        (template_key, version, now, well_id),
    )


def db_insert_node(
    conn,
    *,
    node_id: str,
    well_id: str,
    parent_id: Optional[str],
    node_key: str,
    title: str,
    node_type: str,
    order_index: int,
    is_enabled: int,
    is_selected: int,
    is_completed: int,
    state_json: Optional[str],
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO well_section_nodes (
          node_id, well_id, parent_id, node_key, title, node_type, order_index,
          is_enabled, is_selected, is_completed, state_json,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id, well_id, parent_id, node_key, title, node_type, order_index,
            is_enabled, is_selected, is_completed, state_json,
            created_at, updated_at
        ),
    )


# -----------------------------
# Materialize tree into DB
# -----------------------------
def ensure_section_tree(conn, well_id: str, step1_context: Dict[str, Any]) -> None:
    """
    Idempotent behavior:
      - if well already has same template_key/version AND nodes exist -> do nothing
      - else: rebuild nodes for this well (MVP: delete+insert)
    """
    template_key, version = choose_template(step1_context)

    meta = db_get_well_sections_meta(conn, well_id)
    now = iso_now()

    if meta and meta.get("section_template_key") == template_key and meta.get("sections_version") == version:
        if db_has_any_nodes(conn, well_id):
            return

    raw = load_template(template_key, version)
    templ = apply_rules(raw, step1_context)

    with conn:  # transaction
        db_delete_nodes(conn, well_id)
        db_update_well_sections_meta(conn, well_id, template_key, version, now)
        _insert_node_recursive(conn, well_id, parent_id=None, node=templ["root"], now=now)


def _insert_node_recursive(conn, well_id: str, parent_id: Optional[str], node: Dict[str, Any], now: str) -> None:
    node_id = uuid4_str()
    node_key = node["node_key"]
    title = node["title"]
    node_type = node["node_type"]
    order_index = int(node.get("order", 0))

    is_enabled = 1
    is_selected = 0

    if node_type in ("SECTION", "ITEM"):
        is_enabled = 1 if node.get("enabled", True) else 0
    if node_type == "SECTION":
        is_selected = 1 if node.get("selected", False) else 0

    default_state = node.get("default_state")
    state_json_str = json.dumps(default_state, ensure_ascii=False) if default_state else None

    db_insert_node(
        conn,
        node_id=node_id,
        well_id=well_id,
        parent_id=parent_id,
        node_key=node_key,
        title=title,
        node_type=node_type,
        order_index=order_index,
        is_enabled=is_enabled,
        is_selected=is_selected,
        is_completed=0,
        state_json=state_json_str,
        created_at=now,
        updated_at=now,
    )

    for ch in node.get("children", []) or []:
        _insert_node_recursive(conn, well_id, parent_id=node_id, node=ch, now=now)


# -----------------------------
# UI actions
# -----------------------------
def set_section_selected(conn, well_id: str, node_key: str, selected: bool) -> None:
    now = iso_now()
    with conn:
        conn.execute(
            """
            UPDATE well_section_nodes
            SET is_selected = ?, updated_at = ?
            WHERE well_id = ? AND node_key = ? AND node_type = 'SECTION'
            """,
            (1 if selected else 0, now, well_id, node_key),
        )


def get_selected_sections(conn, well_id: str) -> List[str]:
    rows = conn.execute(
        """
        SELECT node_key
        FROM well_section_nodes
        WHERE well_id = ?
          AND node_type = 'SECTION'
          AND is_enabled = 1
          AND is_selected = 1
        ORDER BY order_index ASC
        """,
        (well_id,),
    ).fetchall()
    return [r[0] for r in rows]