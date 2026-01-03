from __future__ import annotations

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from app.core.canonical import canonical_well_name


class NewWellDialog(QDialog):
    """
    Collects Well Name before creating a DRAFT well.

    Rules:
    - Input is normalized using the same canonicalization logic as Step 1:
      ASCII-only + UPPERCASE (via canonical_well_name()).
    - OK is enabled only when the normalized name is non-empty.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("New Well")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Well Name"))

        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText(
            "Enter Well Name (e.g., YAPRAKLI-4, VARINCA-25S, DERECIK-1KS)"
        )
        self.edt_name.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.edt_name)

        hint = QLabel("Tip: Input will be normalized to ASCII-only uppercase. You can edit it later in Step 1.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setEnabled(False)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self._try_accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)

        layout.addLayout(btn_row)
        self.setLayout(layout)

        self.edt_name.setFocus(Qt.TabFocusReason)

    def well_name(self) -> str:
        """
        Returns the normalized well name (canonical form).
        """
        raw = (self.edt_name.text() or "").strip()
        return canonical_well_name(raw)

    def _on_text_changed(self, _text: str) -> None:
        # Live-normalize to match Step 1 behavior (ASCII-only uppercase).
        raw = self.edt_name.text() or ""
        cur = self.edt_name.cursorPosition()

        normalized = canonical_well_name(raw)

        if normalized != raw:
            # Prevent recursion on setText
            blocker = QSignalBlocker(self.edt_name)
            try:
                self.edt_name.setText(normalized)
                # Keep cursor position reasonable
                self.edt_name.setCursorPosition(min(cur, len(normalized)))
            finally:
                del blocker

        self.btn_ok.setEnabled(bool(normalized.strip()))

    def _try_accept(self) -> None:
        name = self.well_name()
        if not name:
            QMessageBox.warning(self, "Validation", "Well Name is required.")
            return

        # Ensure field reflects the canonical value at accept time
        if self.edt_name.text() != name:
            blocker = QSignalBlocker(self.edt_name)
            try:
                self.edt_name.setText(name)
            finally:
                del blocker

        self.accept()