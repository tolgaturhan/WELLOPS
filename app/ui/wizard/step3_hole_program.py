# app/ui/wizard/step3_hole_program.py
from __future__ import annotations

from typing import Optional, Set, Dict, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QSizePolicy,
)


class Step3HoleProgram(QWidget):
    """
    Step 3 (UI-only): Enable/Disable hole section sizes for the selected well.

    Behavior:
      - User checks which hole sizes are enabled.
      - Clicking "Apply" emits enabled_node_keys_changed(well_id, enabled_set).
      - No DB wiring.

    Router expectation (MainWindow):
      - HOLE_SECTION -> Step3HoleProgram
      - Clicking a hole size node:
          enabled -> HoleSectionForm
          disabled -> DisabledSectionPage message
    """

    enabled_node_keys_changed = Signal(str, object)  # (well_id, enabled_set)

    # Node keys MUST match WellTreeWidget/MainWindow
    _HOLE_ITEMS: Tuple[Tuple[str, str], ...] = (
        ("HSE_26", '26" HSE'),
        ("HSE_17_1_2", '17 1/2" HSE'),
        ("HSE_12_1_4", '12 1/4" HSE'),
        ("HSE_8_1_2", '8 1/2" HSE'),
        ("HSE_6", '6" HSE'),
    )

    def __init__(
        self,
        well_id: Optional[str] = None,
        enabled_node_keys: Optional[Set[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._well_id: str = str(well_id).strip() if well_id is not None else ""
        self._enabled: Set[str] = set(enabled_node_keys or set())

        self._checkboxes: Dict[str, QCheckBox] = {}

        self._build_ui()
        self._apply_initial_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("HOLE SECTION - Enable / Disable Sections")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title.setFont(title_font)
        title.setWordWrap(True)

        subtitle = QLabel(
            "Select which hole sizes are enabled for this well. Disabled sections will show a warning page when clicked."
        )
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)

        group = QGroupBox("Enabled Hole Sizes")
        g_layout = QVBoxLayout(group)
        g_layout.setContentsMargins(12, 12, 12, 12)
        g_layout.setSpacing(8)

        for node_key, label in self._HOLE_ITEMS:
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_checkbox_changed)
            self._checkboxes[node_key] = cb
            g_layout.addWidget(cb)

        root.addWidget(group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_apply.clicked.connect(self._on_apply_clicked)

        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_apply)

        root.addLayout(btn_row)
        root.addStretch(1)

    def _apply_initial_state(self) -> None:
        for node_key, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(node_key in self._enabled)
            cb.blockSignals(False)

        self._update_apply_enabled_state()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _current_enabled_set(self) -> Set[str]:
        enabled: Set[str] = set()
        for node_key, cb in self._checkboxes.items():
            if cb.isChecked():
                enabled.add(node_key)
        return enabled

    def _update_apply_enabled_state(self) -> None:
        changed = self._current_enabled_set() != self._enabled
        self.btn_apply.setEnabled(changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_checkbox_changed(self, _state: int) -> None:
        self._update_apply_enabled_state()

    def _on_apply_clicked(self) -> None:
        if not self._well_id:
            QMessageBox.warning(self, "Warning", "Well context is not set. Changes were not applied.")
            return

        enabled_now = self._current_enabled_set()

        # Update local snapshot
        self._enabled = set(enabled_now)

        # Emit to MainWindow (UI-only in-memory storage)
        self.enabled_node_keys_changed.emit(self._well_id, set(enabled_now))

        self._update_apply_enabled_state()

        # Saving is handled by the container via enabled_node_keys_changed.

    def _on_reset_clicked(self) -> None:
        # Reset UI back to last applied snapshot
        self._apply_initial_state()
