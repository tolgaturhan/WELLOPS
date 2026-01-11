# app/ui/dialogs/stabilizer_gauge_converter.py
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)


class StabilizerGaugeConverterDialog(QDialog):
    """
    Converts a stabilizer gauge from whole + numerator/denominator into decimal inches.
    Supports a "Without Stabilizer" shortcut that returns NONE.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Stabilizer Gauge Converter")
        self.setModal(True)

        self._result_text: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Select an option below...")
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        btn_without = QPushButton("Without Stabilizer")
        btn_without.clicked.connect(self._on_without)
        root.addWidget(btn_without)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.edt_whole = QLineEdit()
        self.edt_whole.setPlaceholderText("12")
        self.edt_whole.setValidator(QIntValidator(0, 999, self))
        self.edt_whole.setFixedWidth(60)

        self.edt_num = QLineEdit()
        self.edt_num.setPlaceholderText("1")
        self.edt_num.setValidator(QIntValidator(0, 999, self))
        self.edt_num.setFixedWidth(60)

        self.edt_den = QLineEdit()
        self.edt_den.setPlaceholderText("8")
        self.edt_den.setValidator(QIntValidator(1, 999, self))
        self.edt_den.setFixedWidth(60)

        row.addWidget(self.edt_whole)
        row.addWidget(self.edt_num)
        row.addWidget(QLabel("/"))
        row.addWidget(self.edt_den)
        row.addWidget(QLabel("inch"))
        row.addStretch(1)
        root.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_ok = QPushButton("OK")
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def result_text(self) -> Optional[str]:
        return self._result_text

    def _on_without(self) -> None:
        self._result_text = "NONE"
        self.accept()

    def _on_ok(self) -> None:
        whole = (self.edt_whole.text() or "").strip()
        num = (self.edt_num.text() or "").strip()
        den = (self.edt_den.text() or "").strip()
        if not whole or not num or not den:
            QMessageBox.warning(self, "Warning", "Please fill all stabilizer gauge fields.")
            return
        try:
            w = int(whole)
            n = int(num)
            d = int(den)
        except Exception:
            QMessageBox.warning(self, "Warning", "Please enter valid numbers.")
            return
        if d <= 0:
            QMessageBox.warning(self, "Warning", "Denominator must be greater than zero.")
            return

        value = w + (n / d)
        out = f"{value:.3f}".rstrip("0").rstrip(".")
        self._result_text = out
        self.accept()

