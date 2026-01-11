# app/ui/widgets/date_picker_line.py
from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal, QSize
from PySide6.QtGui import QPalette, QIcon, QPixmap
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
        self._apply_date_button_style()
        self._apply_calendar_style()

        qd = QDate.currentDate()
        if initial is not None:
            qd = QDate(initial.year, initial.month, initial.day)
        self.date_edit.setDate(qd)

        date_row = QHBoxLayout()
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.setSpacing(6)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self._calendar_btn)
        root.addLayout(date_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _apply_date_button_style(self) -> None:
        pal = self.palette()
        window = pal.color(QPalette.Window)
        is_light = (window.red() + window.green() + window.blue()) / 3 > 128
        if is_light:
            bg = "#ffffff"
            border = "#e1d9d7"
            icon = "#1f1f1f"
        else:
            bg = "#2b2b2b"
            border = "#3a3a3a"
            icon = "#ffffff"
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'>"
            f"<rect x='2' y='3' width='12' height='11' rx='1' ry='1' fill='none' stroke='{icon}' stroke-width='1'/>"
            f"<rect x='2' y='3' width='12' height='3' fill='{icon}'/>"
            f"<rect x='4' y='1' width='2' height='4' fill='{icon}'/>"
            f"<rect x='10' y='1' width='2' height='4' fill='{icon}'/>"
            "</svg>"
        )
        icon_pix = QPixmap()
        icon_pix.loadFromData(svg.encode("utf-8"))
        self._calendar_btn = QToolButton()
        self._calendar_btn.setCursor(Qt.PointingHandCursor)
        self._calendar_btn.setToolTip("Select date")
        self._calendar_btn.setIcon(QIcon(icon_pix))
        self._calendar_btn.setIconSize(QSize(14, 14))
        self._calendar_btn.setFixedSize(24, 22)
        self._calendar_btn.clicked.connect(self._open_calendar_popup)
        self._calendar_btn.setStyleSheet(
            "QToolButton {"
            f"background-color: {bg};"
            f"border: 1px solid {border};"
            "padding: 0;"
            "}"
            "QToolButton:hover {"
            f"background-color: {bg};"
            "}"
        )
        self.date_edit.setStyleSheet(
            "QDateEdit::drop-down {"
            "width: 0px;"
            "border: none;"
            "}"
            "QDateEdit::down-arrow {"
            "image: none;"
            "}"
        )

    def _apply_calendar_style(self) -> None:
        pal = self.palette()
        window = pal.color(QPalette.Window)
        is_light = (window.red() + window.green() + window.blue()) / 3 > 128
        if is_light:
            fg = "#1f1f1f"
            bg = "#ffffff"
            border = "#e1d9d7"
        else:
            fg = "#ffffff"
            bg = "#2b2b2b"
            border = "#3a3a3a"
        cal = self.date_edit.calendarWidget()
        if cal is None:
            return
        cal.setStyleSheet(
            "QCalendarWidget QWidget {"
            f"background-color: {bg};"
            f"color: {fg};"
            "}"
            "QCalendarWidget QToolButton {"
            f"color: {fg};"
            f"background-color: {bg};"
            f"border: 1px solid {border};"
            "}"
            "QCalendarWidget QToolButton:hover {"
            f"background-color: {bg};"
            "}"
            "QCalendarWidget QToolButton#qt_calendar_prevmonth,"
            "QCalendarWidget QToolButton#qt_calendar_nextmonth {"
            f"color: {fg};"
            "}"
            "QCalendarWidget QMenu {"
            f"background-color: {bg};"
            f"color: {fg};"
            f"border: 1px solid {border};"
            "}"
            "QCalendarWidget QSpinBox {"
            f"background-color: {bg};"
            f"color: {fg};"
            f"border: 1px solid {border};"
            "}"
        )

    def _open_calendar_popup(self) -> None:
        cal = self.date_edit.calendarWidget()
        if cal is None:
            return
        cal.setWindowFlags(Qt.Popup)
        pos = self.date_edit.mapToGlobal(self.date_edit.rect().bottomLeft())
        cal.move(pos)
        cal.show()
        cal.raise_()
        cal.setFocus()

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
        self.btn.setText("...")
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
