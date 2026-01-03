# app/ui/dialogs/nozzle_dialog.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QSpinBox,
    QHeaderView,
    QWidget,
    QAbstractItemView,
)

from app.core.hole_section_calcs import NozzleLine


@dataclass(frozen=True)
class NozzleDialogResult:
    nozzles: List[NozzleLine]


class NozzleDialog(QDialog):
    """
    UI-only dialog to build nozzle list used to compute TFA.

    Requirements implemented:
      - User can add nozzle lines.
      - Each line has COUNT and SIZE (32nds of an inch).
      - OK returns the list for section form.
      - Reopening dialog can preload previous nozzle list.

    Notes:
      - We intentionally keep it simple and deterministic.
      - Validation is strict: COUNT>=1, SIZE>=1 for included lines.
    """

    def __init__(self, initial_nozzles: Optional[Sequence[NozzleLine]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Nozzles")
        self.setModal(True)

        self._result: Optional[NozzleDialogResult] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        help_text = QLabel(
            "Add nozzle lines and specify COUNT and SIZE (32nds of an inch). "
            "Example: 5 nozzles of size 9 and 1 nozzle of size 10."
        )
        help_text.setWordWrap(True)
        root.addWidget(help_text)

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["COUNT", "SIZE (32nds)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table, 1)

        # Row controls
        row_controls = QHBoxLayout()
        self.btn_add = QPushButton("Add Line")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear")

        self.btn_add.clicked.connect(self._on_add_line)
        self.btn_remove.clicked.connect(self._on_remove_selected)
        self.btn_clear.clicked.connect(self._on_clear)

        row_controls.addWidget(self.btn_add)
        row_controls.addWidget(self.btn_remove)
        row_controls.addWidget(self.btn_clear)
        row_controls.addStretch(1)
        root.addLayout(row_controls)

        # Dialog buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok = QPushButton("OK")

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._on_ok)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)
        root.addLayout(btn_row)

        # preload
        if initial_nozzles:
            for ln in initial_nozzles:
                if ln.count > 0 and ln.size_32nds > 0:
                    self._append_line(count=ln.count, size_32nds=ln.size_32nds)
        if self.table.rowCount() == 0:
            self._append_line(count=1, size_32nds=9)

    # --------------------------
    # Public API
    # --------------------------
    def get_result(self) -> Optional[NozzleDialogResult]:
        return self._result

    # --------------------------
    # Internals: table row widgets
    # --------------------------
    def _append_line(self, *, count: int = 1, size_32nds: int = 9) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        # COUNT spinner
        sp_count = QSpinBox()
        sp_count.setMinimum(1)
        sp_count.setMaximum(99)
        sp_count.setValue(int(count))

        # SIZE spinner (32nds)
        sp_size = QSpinBox()
        sp_size.setMinimum(1)
        sp_size.setMaximum(40)  # typical nozzle sizes; adjust later if needed
        sp_size.setValue(int(size_32nds))

        self.table.setCellWidget(row, 0, sp_count)
        self.table.setCellWidget(row, 1, sp_size)

        # Select newly added row
        self.table.selectRow(row)

    def _read_lines(self) -> List[NozzleLine]:
        lines: List[NozzleLine] = []
        for row in range(self.table.rowCount()):
            w_count = self.table.cellWidget(row, 0)
            w_size = self.table.cellWidget(row, 1)

            if not isinstance(w_count, QSpinBox) or not isinstance(w_size, QSpinBox):
                continue

            c = int(w_count.value())
            s = int(w_size.value())

            if c <= 0 or s <= 0:
                continue

            lines.append(NozzleLine(count=c, size_32nds=s))

        return lines

    # --------------------------
    # Slots
    # --------------------------
    def _on_add_line(self) -> None:
        self._append_line(count=1, size_32nds=9)

    def _on_remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        if self.table.rowCount() > 0:
            self.table.selectRow(min(row, self.table.rowCount() - 1))

    def _on_clear(self) -> None:
        self.table.setRowCount(0)
        self._append_line(count=1, size_32nds=9)

    def _on_ok(self) -> None:
        lines = self._read_lines()
        if not lines:
            QMessageBox.warning(self, "Warning", "Please add at least one valid nozzle line (COUNT and SIZE).")
            return

        self._result = NozzleDialogResult(nozzles=lines)
        self.accept()