# app/ui/tree/well_tree_widget.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout


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

    _ROLE_NODE_KEY = Qt.UserRole + 101
    _ROLE_WELL_ID = Qt.UserRole + 102

    # Locked hole size display labels (must match project decision)
    _HOLE_SIZE_ITEMS = (
        ("HSE_26", '26” HSE'),
        ("HSE_17_1_2", '17 1/2” HSE'),
        ("HSE_12_1_4", '12 1/4” HSE'),
        ("HSE_8_1_2", '8 1/2” HSE'),
        ("HSE_6", '6” HSE'),
    )

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setExpandsOnDoubleClick(True)
        self.tree.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)

        self._wells: List[dict] = []

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

    def clear(self) -> None:
        self._wells = []
        self.tree.clear()

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

    # --------------------------
    # Internals
    # --------------------------
    def _rebuild_tree(self) -> None:
        self.tree.clear()

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
            hole_section.addChild(
                self._make_item(
                    text=label,
                    well_id=well_id,
                    node_key=node_key,
                )
            )

        hole_section.setExpanded(True)

    def _make_item(self, text: str, well_id: str, node_key: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text])
        item.setData(0, self._ROLE_NODE_KEY, node_key)
        item.setData(0, self._ROLE_WELL_ID, str(well_id))

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