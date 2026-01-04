# app/ui/tree/well_tree_widget.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QMenu, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout


@dataclass(frozen=True)
class WellTreeNodePayload:
    well_id: str
    node_key: str


class WellTreeWidget(QWidget):
    """
    UI-only Well Navigation Tree.

    Emits:
        node_clicked(well_id: str, node_key: str)
    """

    node_clicked = Signal(str, str)
    well_delete_requested = Signal(str, str)  # well_id, well_name

    _ROLE_NODE_KEY = Qt.UserRole + 101
    _ROLE_WELL_ID = Qt.UserRole + 102
    _ROLE_BASE_TEXT = Qt.UserRole + 103

    # Locked hole size display labels (must match project decision)
    _HOLE_SIZE_ITEMS = (
        ("HSE_26", '26" HSE'),
        ("HSE_17_1_2", '17 1/2" HSE'),
        ("HSE_12_1_4", '12 1/4" HSE'),
        ("HSE_8_1_2", '8 1/2" HSE'),
        ("HSE_6", '6" HSE'),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

        self._wells: List[dict] = []
        self._enabled_hole_sizes: Dict[str, Set[str]] = {}
        self._hole_items_by_well: Dict[Tuple[str, str], QTreeWidgetItem] = {}

    # --------------------------
    # Public API
    # --------------------------
    def set_wells(self, wells: Sequence[dict]) -> None:
        """
        Rebuild the tree from a well list.

        Expected well dict keys:
            - id (str)   # well_id TEXT (UUID)
            - name (str) # well_name
        """
        self._wells = list(wells)
        self._rebuild_tree()

    def set_enabled_hole_sizes(self, well_id: str, enabled_set: Sequence[str]) -> None:
        """
        Enable/disable hole section items for a specific well.
        """
        wid = (well_id or "").strip()
        if not wid:
            return
        self._enabled_hole_sizes[wid] = set(enabled_set or [])
        self._apply_enabled_state_for_well(wid)

    def clear(self) -> None:
        self._wells = []
        self.tree.clear()

    def current_well_id(self) -> str:
        item = self.tree.currentItem()
        if item is None:
            return ""
        return str(item.data(0, self._ROLE_WELL_ID) or "")

    def select_well_root(self, well_id: str) -> None:
        """
        Select the top-level WELL NAME node for the given well_id, if present.
        """
        target = (well_id or "").strip()
        if not target:
            return

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if str(item.data(0, self._ROLE_WELL_ID) or "") == target and item.data(
                0, self._ROLE_NODE_KEY
            ) == "WELL_NAME":
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return

    def expand_only_well(self, well_id: str) -> None:
        """
        Expand all nodes under the target well and collapse other wells.
        If the well_id is not found, collapses all and expands the first well if present.
        """
        target = (well_id or "").strip()
        found = False

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            is_target = str(item.data(0, self._ROLE_WELL_ID) or "") == target and item.data(
                0, self._ROLE_NODE_KEY
            ) == "WELL_NAME"
            if is_target:
                found = True
                self._set_expanded_recursive(item, True)
            else:
                item.setExpanded(False)

        if not found and self.tree.topLevelItemCount() > 0:
            first = self.tree.topLevelItem(0)
            self._set_expanded_recursive(first, True)
            self.tree.setCurrentItem(first)
            self.tree.scrollToItem(first)

    # --------------------------
    # Internals
    # --------------------------
    def _rebuild_tree(self) -> None:
        self.tree.clear()
        self._hole_items_by_well.clear()

        for w in self._wells:
            well_id = str(w.get("id", "")).strip()
            if not well_id:
                # Skip malformed rows
                continue

            well_name = str(w.get("name", "")).strip() or "WELL"

            # Top-level node: WELL NAME (label is actual well name)
            well_root = self._make_item(
                text=well_name,
                well_id=well_id,
                node_key="WELL_NAME",
            )
            self.tree.addTopLevelItem(well_root)

            # Subsections under the well name root
            self._add_standard_children(well_root, well_id)

            # Expand well root by default
            well_root.setExpanded(True)

        # Select first if available
        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _add_standard_children(self, well_root: QTreeWidgetItem, well_id: str) -> None:
        # WELL IDENTITY
        well_root.addChild(
            self._make_item(
                text="WELL IDENTITY",
                well_id=well_id,
                node_key="WELL_IDENTITY",
            )
        )

        # TRAJECTORY
        well_root.addChild(
            self._make_item(
                text="TRAJECTORY",
                well_id=well_id,
                node_key="TRAJECTORY",
            )
        )

        # HOLE SECTION (parent)
        hole_section = self._make_item(
            text="HOLE SECTION",
            well_id=well_id,
            node_key="HOLE_SECTION",
        )
        well_root.addChild(hole_section)

        # Hole size nodes (always present; enabled/disabled behavior is router-driven)
        for node_key, label in self._HOLE_SIZE_ITEMS:
            item = self._make_item(
                text=label,
                well_id=well_id,
                node_key=node_key,
            )
            hole_section.addChild(item)
            self._hole_items_by_well[(well_id, node_key)] = item

        hole_section.setExpanded(True)
        self._apply_enabled_state_for_well(well_id)

    def _apply_enabled_state_for_well(self, well_id: str) -> None:
        enabled = self._enabled_hole_sizes.get(well_id, set())
        for (wid, node_key), item in self._hole_items_by_well.items():
            if wid != well_id:
                continue
            is_enabled = node_key in enabled
            item.setDisabled(not is_enabled)
            base_text = str(item.data(0, self._ROLE_BASE_TEXT) or item.text(0)).lstrip("✓× ").strip()
            prefix = "✓ " if is_enabled else "× "
            item.setText(0, f"{prefix}{base_text}")
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            if is_enabled:
                item.setForeground(0, QBrush(QColor(25, 125, 55)))
            else:
                item.setForeground(0, QBrush(QColor(200, 0, 0)))

    def _set_expanded_recursive(self, item: QTreeWidgetItem, expanded: bool) -> None:
        item.setExpanded(expanded)
        for i in range(item.childCount()):
            self._set_expanded_recursive(item.child(i), expanded)

    def _make_item(self, text: str, well_id: str, node_key: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setData(0, self._ROLE_NODE_KEY, node_key)
        item.setData(0, self._ROLE_WELL_ID, str(well_id))
        item.setData(0, self._ROLE_BASE_TEXT, text)

        # UX: emphasize section nodes
        if node_key in {"WELL_IDENTITY", "TRAJECTORY", "HOLE_SECTION"}:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)

        return item

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        node_key = item.data(0, self._ROLE_NODE_KEY)
        well_id = item.data(0, self._ROLE_WELL_ID)

        if not node_key or not well_id:
            return

        self.node_clicked.emit(str(well_id), str(node_key))

    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return

        node_key = item.data(0, self._ROLE_NODE_KEY)
        well_id = item.data(0, self._ROLE_WELL_ID)
        well_name = item.text(0)

        if node_key != "WELL_NAME" or not well_id:
            return

        menu = QMenu(self.tree)
        act_delete = menu.addAction("Delete Well")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_delete:
            self.well_delete_requested.emit(str(well_id), str(well_name))
