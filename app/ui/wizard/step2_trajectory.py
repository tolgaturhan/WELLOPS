from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QVBoxLayout,
)

from app.core import rules


class Step2Trajectory(QWidget):
    """
    Wizard Step 2 UI: Well Trajectory (Plan vs Actual)

    PLANNED (Required)
    - KOP (m)
    - Planned Well TVD (m)
    - Planned Well MD (m)
    - Planned Max Inc (deg)
    - Planned Azimuth (deg)
    - Planned Max DLS (deg/30m)
    - Planned VS (m)
    - Planned Dist to Plan (m)

    ACTUAL (Optional, later)
    - Well TVD at TD (m)
    - Well MD at TD (m)
    - Inc at TD (deg)
    - Azimuth at TD (deg)
    - Max DLS (deg/30m)
    - VS at TD (m)
    - Dist to Plan at TD (m)
    """

    _NUMERIC_ALLOWED = re.compile(r"[^0-9.\-]+")

    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout()
        self.setLayout(root)

        planned_group = QGroupBox("PLANNED (Required)")
        planned_form = QFormLayout()
        planned_group.setLayout(planned_form)
        root.addWidget(planned_group)

        # PLANNED fields (required)
        self.kop_m = QLineEdit()
        self.kop_m.setPlaceholderText("e.g., 450.0")
        planned_form.addRow("KOP (m)", self.kop_m)

        self.tvd_planned_m = QLineEdit()
        self.tvd_planned_m.setPlaceholderText("e.g., 2850.0")
        planned_form.addRow("Planned Well TVD (m)", self.tvd_planned_m)

        self.md_planned_m = QLineEdit()
        self.md_planned_m.setPlaceholderText("e.g., 3200.0")
        planned_form.addRow("Planned Well MD (m)", self.md_planned_m)

        self.max_inc_planned_deg = QLineEdit()
        self.max_inc_planned_deg.setPlaceholderText("0 to 180")
        planned_form.addRow("Planned Max Inc (deg)", self.max_inc_planned_deg)

        self.azimuth_planned_deg = QLineEdit()
        self.azimuth_planned_deg.setPlaceholderText("0 to 360")
        planned_form.addRow("Planned Azimuth (deg)", self.azimuth_planned_deg)

        self.max_dls_planned_deg_per_30m = QLineEdit()
        self.max_dls_planned_deg_per_30m.setPlaceholderText("e.g., 3.0")
        planned_form.addRow("Planned Max DLS (deg/30m)", self.max_dls_planned_deg_per_30m)

        self.vs_planned_m = QLineEdit()
        self.vs_planned_m.setPlaceholderText("e.g., 850.0")
        planned_form.addRow("Planned VS (m)", self.vs_planned_m)

        self.dist_planned_m = QLineEdit()
        self.dist_planned_m.setPlaceholderText("e.g., 1200.0")
        planned_form.addRow("Planned Dist to Plan (m)", self.dist_planned_m)

        actual_group = QGroupBox("ACTUAL (Optional, later)")
        actual_form = QFormLayout()
        actual_group.setLayout(actual_form)
        root.addWidget(actual_group)

        # ACTUAL fields (optional)
        self.tvd_at_td_m = QLineEdit()
        self.tvd_at_td_m.setPlaceholderText("e.g., 2840.0")
        actual_form.addRow("Well TVD at TD (m)", self.tvd_at_td_m)

        self.md_at_td_m = QLineEdit()
        self.md_at_td_m.setPlaceholderText("e.g., 3190.0")
        actual_form.addRow("Well MD at TD (m)", self.md_at_td_m)

        self.inc_at_td_deg = QLineEdit()
        self.inc_at_td_deg.setPlaceholderText("0 to 180")
        actual_form.addRow("Inc at TD (deg)", self.inc_at_td_deg)

        self.azimuth_at_td_deg = QLineEdit()
        self.azimuth_at_td_deg.setPlaceholderText("0 to 360")
        actual_form.addRow("Azimuth at TD (deg)", self.azimuth_at_td_deg)

        self.max_dls_actual_deg_per_30m = QLineEdit()
        self.max_dls_actual_deg_per_30m.setPlaceholderText("e.g., 3.5")
        actual_form.addRow("Max DLS (deg/30m)", self.max_dls_actual_deg_per_30m)

        self.vs_at_td_m = QLineEdit()
        self.vs_at_td_m.setPlaceholderText("e.g., 840.0")
        actual_form.addRow("VS at TD (m)", self.vs_at_td_m)

        self.dist_at_td_m = QLineEdit()
        self.dist_at_td_m.setPlaceholderText("e.g., 1185.0")
        actual_form.addRow("Dist to Plan at TD (m)", self.dist_at_td_m)

        hint = QLabel("Numeric fields accept digits, dot, and minus only.")
        hint.setAlignment(Qt.AlignLeft)
        root.addWidget(hint)

        self.btn_validate = QPushButton("Validate Step 2")
        self.btn_validate.clicked.connect(self._on_validate_clicked)
        root.addWidget(self.btn_validate)

        # Wire numeric normalization
        numeric_fields = [
            self.kop_m,
            self.tvd_planned_m,
            self.md_planned_m,
            self.max_inc_planned_deg,
            self.azimuth_planned_deg,
            self.max_dls_planned_deg_per_30m,
            self.vs_planned_m,
            self.dist_planned_m,
            self.tvd_at_td_m,
            self.md_at_td_m,
            self.inc_at_td_deg,
            self.azimuth_at_td_deg,
            self.max_dls_actual_deg_per_30m,
            self.vs_at_td_m,
            self.dist_at_td_m,
        ]
        for le in numeric_fields:
            le.textEdited.connect(lambda _t, _le=le: self._normalize_numeric(_le))

    def _normalize_numeric(self, le: QLineEdit) -> None:
        s = le.text()
        if not s:
            return

        s2 = s.replace(",", ".")
        s2 = self._NUMERIC_ALLOWED.sub("", s2)

        if s2 != s:
            cursor = le.cursorPosition()
            le.blockSignals(True)
            le.setText(s2)
            le.setCursorPosition(min(cursor, len(s2)))
            le.blockSignals(False)

    def _on_validate_clicked(self) -> None:
        data = self.collect_data()
        result = rules.validate_step2(data)

        if result.ok:
            QMessageBox.information(self, "Validation", "Step 2 is valid.")
            return

        lines = []
        for _field, msg in result.field_errors.items():
            lines.append(f"- {msg}")
        for msg in result.errors:
            lines.append(f"- {msg}")

        QMessageBox.warning(
            self,
            "Validation Error",
            "Please fix the following issues:\n\n" + "\n".join(lines),
        )

    def collect_data(self) -> dict:
        return {
            "kop_m": self.kop_m.text().strip(),
            "tvd_planned_m": self.tvd_planned_m.text().strip(),
            "md_planned_m": self.md_planned_m.text().strip(),
            "max_inc_planned_deg": self.max_inc_planned_deg.text().strip(),
            "azimuth_planned_deg": self.azimuth_planned_deg.text().strip(),
            "max_dls_planned_deg_per_30m": self.max_dls_planned_deg_per_30m.text().strip(),
            "vs_planned_m": self.vs_planned_m.text().strip(),
            "dist_planned_m": self.dist_planned_m.text().strip(),
            "tvd_at_td_m": self.tvd_at_td_m.text().strip(),
            "md_at_td_m": self.md_at_td_m.text().strip(),
            "inc_at_td_deg": self.inc_at_td_deg.text().strip(),
            "azimuth_at_td_deg": self.azimuth_at_td_deg.text().strip(),
            "max_dls_actual_deg_per_30m": self.max_dls_actual_deg_per_30m.text().strip(),
            "vs_at_td_m": self.vs_at_td_m.text().strip(),
            "dist_at_td_m": self.dist_at_td_m.text().strip(),
        }
