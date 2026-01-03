# app/ui/widgets/date_picker_line.py
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QToolButton,
    QHBoxLayout,
    QWidget,
    QDateEdit,
    QSizePolicy,
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QLabel,
)


class _DatePickerDialog(QDialog):
    """
    Minimal date picker dialog:
      - Shows today's date highlighted by Qt calendar widget inside QDateEdit popup.
      - OK/Cancel buttons.
    """

    def __init__(self, initial: Optional[date] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        lbl = QLabel("Select a date:")
        root.addWidget(lbl)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        qd = QDate.currentDate()
        if initial is not None:
            qd = QDate(initial.year, initial.month, initial.day)
        self.date_edit.setDate(qd)

        root.addWidget(self.date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_date(self) -> date:
        qd = self.date_edit.date()
        return date(qd.year(), qd.month(), qd.day())


class DatePickerLine(QWidget):
    """
    Click-only date picker line.

    Requirements:
      - No manual typing.
      - Clicking opens a date selection dialog.
      - Defaults to today's date highlighted by Qt.
      - After OK, the line displays the selected date.
      - Clicking again reopens dialog with current value preselected.

    Emits:
      - date_changed(date|None)
      - text_changed(str) (formatted "dd.MM.yyyy" or empty)
    """

    date_changed = Signal(object)  # date | None
    text_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._value: Optional[date] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit()
        self.edit.setReadOnly(True)
        self.edit.setPlaceholderText("Click to select date")
        self.edit.setCursor(Qt.PointingHandCursor)
        self.edit.setFocusPolicy(Qt.StrongFocus)

        self.btn = QToolButton()
        self.btn.setText("…")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setToolTip("Select date")

        layout.addWidget(self.edit, 1)
        layout.addWidget(self.btn)

        # Interactions
        self.edit.mousePressEvent = self._on_click  # type: ignore[assignment]
        self.btn.clicked.connect(self._open_dialog)

    # -------------------------
    # Public API
    # -------------------------
    def set_placeholder(self, text: str) -> None:
        self.edit.setPlaceholderText(text)

    def set_date(self, d: Optional[date]) -> None:
        self._value = d
        self._sync_text(emit=True)

    def date_value(self) -> Optional[date]:
        return self._value

    def text_value(self) -> str:
        return self.edit.text()

    # -------------------------
    # Internal
    # -------------------------
    def _format(self, d: date) -> str:
        return d.strftime("%d.%m.%Y")

    def _sync_text(self, *, emit: bool) -> None:
        if self._value is None:
            self.edit.setText("")
            if emit:
                self.date_changed.emit(None)
                self.text_changed.emit("")
            return

        txt = self._format(self._value)
        self.edit.setText(txt)
        if emit:
            self.date_changed.emit(self._value)
            self.text_changed.emit(txt)

    def _on_click(self, _event) -> None:
        self._open_dialog()

    def _open_dialog(self) -> None:
        dlg = _DatePickerDialog(initial=self._value, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._value = dlg.selected_date()
            self._sync_text(emit=True)