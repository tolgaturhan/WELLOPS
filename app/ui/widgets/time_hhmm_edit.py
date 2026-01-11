# app/ui/widgets/time_hhmm_edit.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit, QMessageBox

from app.core.hole_section_calcs import normalize_hhmm


class TimeHHMMEdit(QLineEdit):
    """
    Time input enforcing HH:MM (24-hour), with robust normalization.

    Requirements:
      - Accept user typing: "16:30", "1630", "16.30"
      - On editingFinished normalize to "16:30"
      - Disallow any other formats
      - Allow "24:00" and "00:00"

    Notes:
      - We normalize on editingFinished; until then, user can type.
      - Validation errors are raised in rules; here we provide best-effort UX guardrails.
    """

    normalized = Signal(str)

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)

        # Allow only digits and optional separator during typing. Final strictness via normalize_hhmm.
        # Examples allowed during typing: "1630", "16:30", "16.30", "0:0"
        rx = QRegularExpression(r"^[0-9]{0,4}([:\.][0-9]{0,2})?$")
        self.setValidator(QRegularExpressionValidator(rx, self))

        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setPlaceholderText("HH:MM")
        self.editingFinished.connect(self._normalize_now)

    def _normalize_now(self) -> None:
        raw = (self.text() or "").strip()
        if not raw:
            self.setText("")
            self.normalized.emit("")
            return

        try:
            out = normalize_hhmm(raw)
        except Exception:
            QMessageBox.warning(
                self,
                "Warning",
                "Please enter the time format as shown in the examples.\n"
                "Example: 00:25, 07:43, 12:48, 16:37.",
            )
            self.normalized.emit(raw)
            return

        self.setText(out)
        self.normalized.emit(out)

    def value_or_none(self) -> Optional[str]:
        s = (self.text() or "").strip()
        if not s:
            return None
        try:
            return normalize_hhmm(s)
        except Exception:
            return None
