from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QVBoxLayout,
    QSizePolicy,
)

from app.core import rules
from app.data import trajectory_repo


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

    ACTUAL (Optional)
    - Well TVD at TD (m)
    - Well MD at TD (m)
    - Inc at TD (deg)
    - Azimuth at TD (deg)
    - Max DLS (deg/30m)
    - VS at TD (m)
    - Dist to Plan at TD (m)
    """

    _NUMERIC_ALLOWED = re.compile(r"[^0-9.\-]+")

    step2_saved = Signal(str)  # well_id

    def __init__(self, well_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._well_id: str = str(well_id).strip() if well_id is not None else ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        planned_group = QGroupBox("PLANNED (Required)")
        planned_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
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

        actual_group = QGroupBox("ACTUAL (Optional)")
        actual_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
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

        hint = QLabel(
            "- Fields accept digits, dot, and minus only.\n"
            "- The ACTUAL field is optional. Please return and complete it once the section is finished.\n"
            )
        hint.setAlignment(Qt.AlignLeft)
        root.addWidget(hint)

        self.btn_validate = QPushButton("Validate Trajectory")
        self.btn_validate.clicked.connect(self._on_validate_clicked)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save_clicked)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_validate)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch(1)
        root.addLayout(btn_row)
        root.addStretch(1)

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

        self._load_from_db()

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
        self._validate_step2(show_success=True)

    def _on_save_clicked(self) -> None:
        self.save_to_db(show_message=True, emit_signal=True)

    def _validate_step2(self, *, show_success: bool) -> rules.ValidationResult:
        data = self.collect_data()
        result = rules.validate_step2(data)

        if result.ok:
            if show_success:
                QMessageBox.information(self, "Validation", "Trajectory validation passed. The form is ready to be saved.")
            return result

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
        return result

    def save_to_db(self, *, show_message: bool, emit_signal: bool) -> bool:
        result = self._validate_step2(show_success=False)
        if not result.ok:
            return False

        if not self._well_id:
            QMessageBox.warning(self, "Warning", "Well context is not set. Save was not applied.")
            return False

        data = self.collect_data()
        try:
            trajectory_repo.save_trajectory(self._well_id, data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Step 2.\n\nDetails:\n{e!r}")
            return False

        if emit_signal:
            self.step2_saved.emit(self._well_id)
        if show_message:
            QMessageBox.information(self, "Information", "Trajectory saved.")
        return True

    def set_well_id(self, well_id: str) -> None:
        self._well_id = str(well_id or "").strip()

    def _set_line_text(self, le: QLineEdit, value: object) -> None:
        if value is None:
            return
        txt = str(value)
        if txt == "":
            return
        le.setText(txt)

    def _load_from_db(self) -> None:
        if not self._well_id:
            return
        row = trajectory_repo.get_trajectory(self._well_id)
        if not row:
            return

        self._set_line_text(self.kop_m, row.get("kop_m"))
        self._set_line_text(self.tvd_planned_m, row.get("tvd_planned_m"))
        self._set_line_text(self.md_planned_m, row.get("md_planned_m"))
        self._set_line_text(self.max_inc_planned_deg, row.get("max_inc_planned_deg"))
        self._set_line_text(self.azimuth_planned_deg, row.get("azimuth_planned_deg"))
        self._set_line_text(self.max_dls_planned_deg_per_30m, row.get("max_dls_planned_deg_per_30m"))
        self._set_line_text(self.vs_planned_m, row.get("vs_planned_m"))
        self._set_line_text(self.dist_planned_m, row.get("dist_planned_m"))

        self._set_line_text(self.tvd_at_td_m, row.get("tvd_at_td_m"))
        self._set_line_text(self.md_at_td_m, row.get("md_at_td_m"))
        self._set_line_text(self.inc_at_td_deg, row.get("inc_at_td_deg"))
        self._set_line_text(self.azimuth_at_td_deg, row.get("azimuth_at_td_deg"))
        self._set_line_text(self.max_dls_actual_deg_per_30m, row.get("max_dls_actual_deg_per_30m"))
        self._set_line_text(self.vs_at_td_m, row.get("vs_at_td_m"))
        self._set_line_text(self.dist_at_td_m, row.get("dist_at_td_m"))

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
