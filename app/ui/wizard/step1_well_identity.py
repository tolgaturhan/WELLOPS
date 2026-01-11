from __future__ import annotations 

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QGroupBox,
    QSizePolicy,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QLabel,
    QPushButton,
    QMessageBox,
)

from app.data import identity_repo, sections_repo, wells_repo
from app.data.db import get_connection
from app.core import rules
from app.core.canonical import canonical_well_name, canonical_text, derive_field_name_from_well_key


class Step1WellIdentity(QWidget):
    """
    Wizard Step 1 UI:
    - Well Name (editable)
    - Well Key (read-only, auto)
    - Field Name (read-only, auto)
    - Operator (combo+editable)
    - Contractor (combo+editable)
    - Well Purpose (combo)
    - Well Type (combo)
    - Province (combo+editable)
    - Rig Name (combo+editable)
    - Notes (optional)
    """

    step1_saved = Signal(str)  # well_id

    def __init__(self, well_id: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._well_id: str = str(well_id).strip() if well_id is not None else ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        group = QGroupBox("WELL IDENTITY (Required)")
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.form = QFormLayout(group)
        self.form.setContentsMargins(12, 12, 12, 12)
        self.form.setHorizontalSpacing(12)
        self.form.setVerticalSpacing(8)
        root.addWidget(group)

        # Well Name
        self.well_name = QLineEdit()
        self.well_name.setPlaceholderText("Enter Well Name (e.g., YAPRAKLI-4, VARINCA-25S, DERECIK-1KS)")
        self.form.addRow("Well Name", self.well_name)

        # Well Key (auto)
        self.well_key = QLineEdit()
        self.well_key.setReadOnly(True)
        self.well_key.hide()

        # Field Name (auto)
        self.field_name = QLineEdit()
        self.field_name.setPlaceholderText("Automatically generated")
        self.field_name.setReadOnly(True)
        self.form.addRow("Field Name", self.field_name)

        # Operator (editable combo)
        self.operator = QComboBox()
        self.operator.addItem("Select or enter manually")
        self.operator.model().item(0).setEnabled(False)
        self.operator.setCurrentIndex(0)
        self.operator.setEditable(True)
        self.operator.addItems(["TPAO"])
        self.form.addRow("Operator", self.operator)

        # Contractor (editable combo) - initial list
        self.contractor = QComboBox()
        self.contractor.addItem("Select or enter manually")
        self.contractor.model().item(0).setEnabled(False)
        self.contractor.setCurrentIndex(0)
        self.contractor.setEditable(True)
        self.contractor.addItems(["AKSAN", "BORDRILL", "GYP", "HI-ENERGY", "OCEANMEC", "SOCAR", "TPIC", "VIKING"])
        self.form.addRow("Contractor", self.contractor)

        # Well Purpose
        self.well_purpose = QComboBox()
        self.well_purpose.addItem("Select from list")
        self.well_purpose.model().item(0).setEnabled(False)
        self.well_purpose.setCurrentIndex(0)
        self.well_purpose.addItems(["EXPLORATION", "APPRAISAL", "PRODUCTION", "OTHER"])
        self.well_purpose.setStyleSheet("QComboBox { padding-left: 6px; }")
        self.form.addRow("Well Purpose", self.well_purpose)

        # Well Type
        self.well_type = QComboBox()
        self.well_type.addItem("Select from list")
        self.well_type.model().item(0).setEnabled(False)
        self.well_type.setCurrentIndex(0)
        self.well_type.addItems(["OIL", "GAS", "GEOTHERMAL", "CARBON_DIOXIDE", "OTHER"])
        self.well_type.setStyleSheet("QComboBox { padding-left: 6px; }")
        self.form.addRow("Well Type", self.well_type)

        # DD Well Type
        self.dd_well_type = QComboBox()
        self.dd_well_type.addItem("Select from list")
        self.dd_well_type.model().item(0).setEnabled(False)
        self.dd_well_type.setCurrentIndex(0)
        self.dd_well_type.addItems(
            ["VERTICAL", "J-TYPE", "S-TYPE", "SIDE-TRACK", "HORIZONTAL", "PERFORMANCE", "ONLY INCLINATION"]
        )
        self.dd_well_type.setStyleSheet("QComboBox { padding-left: 6px; }")
        self.form.addRow("DD Well Type", self.dd_well_type)

        # Province (editable combo)
        self.province = QComboBox()
        self.province.addItem("Select or enter manually")
        self.province.model().item(0).setEnabled(False)
        self.province.setCurrentIndex(0)
        self.province.setEditable(True)
        self.province.addItems([
        "ADANA",
        "ADIYAMAN",
        "BATMAN",
        "BINGOL",
        "BITLIS",
        "EDIRNE",
        "ELAZIG",
        "GAZIANTEP",
        "HAKKARI",
        "ISTANBUL",
        "KAHRAMANMARAS",
        "KIRKLARELI",
        "MALATYA",
        "MARDIN",
        "MUS",
        "SIIRT",
        "SANLIURFA",
        "SIRNAK",
        "TEKIRDAG",
        "VAN",
        ])
        self.form.addRow("Province", self.province)


        # Rig Name (editable combo)
        self.rig_name = QComboBox()
        self.rig_name.addItem("Select or enter manually")
        self.rig_name.model().item(0).setEnabled(False)
        self.rig_name.setCurrentIndex(0)
        self.rig_name.setEditable(True)
        self.rig_name.addItems([
            "BD-1",
            "BD-2",
            "BD-4",
            "BD-5",
            "BD-6",
            "BD-7",
            "BD-11",
            "DM-1500",
            "F200-7",
            "F200-9",
            "F200-10",
            "F200-13",
            "F200-14",
            "F200-15",
            "F320-2",
            "F320-5",
            "F320-6",
            "F320-10",
            "HI-21",
            "KARAHAN",
            "KOCAYUSUF",
            "MR7000-2",
            "MR7000-3",
            "NAIMSULEYMANOGLU",
            "NAT80B-2",
            "NOV1500-1",
            "NOV1500-3",
            "NOV1500-4",
            "NOV1500-5",
            "NOV2000",
            "RIG I-8",
            "RIG I-27",
            "RIG-7",
            "RIG-8",
            "RIG-11",
            "RIG-12",
            "RIG-14",
            "RIG-15",
            "RIG-34",
            "SEYITONBASI",
            "TP1500-1",
            "TP1500-2",
            "TP1500-3",
            "TP-350",
            "ZJ40DBZ-1",
            "ZJ40DBZ-2",
            "ZJ40DZ",
            "ZJ50D",
            "ZJ50L",
        ])
        self.form.addRow("Rig Name", self.rig_name)


        # Notes (optional)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Optional field: You can write your opinions and notes here.")
        self.notes.setFixedHeight(80)
        self.form.addRow("Notes", self.notes)

        # Small hint label
        hint = QLabel(
        "- All inputs are normalized to ASCII-only uppercase.\n"
        "- The Field Name is auto-generated based on the entered Well Name.\n"
        )
        hint.setAlignment(Qt.AlignLeft)
        root.addWidget(hint)

        self.btn_validate = QPushButton("Validate Well Identity")
        self.btn_validate.clicked.connect(self._on_validate_clicked)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save_clicked)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self.btn_validate)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addStretch(1)
        root.addWidget(btn_row)
        root.addStretch(1)

        # Wire events
        self.well_name.textChanged.connect(self._on_well_name_changed)
        self.operator.lineEdit().textEdited.connect(self._on_operator_edited)
        self.contractor.lineEdit().textEdited.connect(self._on_contractor_edited)
        self.province.lineEdit().textEdited.connect(self._on_province_edited)
        self.rig_name.lineEdit().textEdited.connect(self._on_rig_edited)

        self._load_from_db()

    def _on_well_name_changed(self, _text: str) -> None:
        # Normalize live
        canon = canonical_well_name(self.well_name.text())
        if canon != self.well_name.text():
            cursor = self.well_name.cursorPosition()
            self.well_name.blockSignals(True)
            self.well_name.setText(canon)
            self.well_name.setCursorPosition(min(cursor, len(canon)))
            self.well_name.blockSignals(False)

        # Auto fields
        self.well_key.setText(canon)
        self.field_name.setText(derive_field_name_from_well_key(canon))

    def _normalize_combo_text(self, combo: QComboBox, normalizer) -> None:
        le = combo.lineEdit()
        if le is None:
            return
        canon = normalizer(le.text())
        if canon != le.text():
            cursor = le.cursorPosition()
            combo.blockSignals(True)
            le.setText(canon)
            le.setCursorPosition(min(cursor, len(canon)))
            combo.blockSignals(False)

    def _on_operator_edited(self, _text: str) -> None:
        self._normalize_combo_text(self.operator, canonical_text)

    def _on_contractor_edited(self, _text: str) -> None:
        self._normalize_combo_text(self.contractor, canonical_text)

    def _on_province_edited(self, _text: str) -> None:
        self._normalize_combo_text(self.province, canonical_text)

    def _on_rig_edited(self, _text: str) -> None:
        self._normalize_combo_text(self.rig_name, canonical_text)

    def _on_validate_clicked(self) -> None:
        self._validate_step1(show_success=True)

    def _on_save_clicked(self) -> None:
        self.save_to_db(show_message=True, emit_signal=True)

    def _validate_step1(self, *, show_success: bool) -> rules.ValidationResult:
        data = self.collect_data()
        result = rules.validate_step1(data)

        if result.ok:
            if show_success:
                QMessageBox.information(self, "Validation", "Well Identity validation passed. The form is ready to be saved.")
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
        result = self._validate_step1(show_success=False)
        if not result.ok:
            return False

        if not self._well_id:
            QMessageBox.warning(self, "Warning", "Well context is not set. Save was not applied.")
            return False

        data = self.collect_data()
        now = wells_repo.iso_now()
        new_name = (data.get("well_name") or "").strip()
        if not new_name:
            QMessageBox.warning(self, "Warning", "Well Name cannot be empty.")
            return False

        try:
            identity_repo.save_identity(self._well_id, data)
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE wells
                    SET well_name = ?, step1_done = 1, updated_at = ?
                    WHERE well_id = ?
                    """,
                    (new_name, now, self._well_id),
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Step 1.\n\nDetails:\n{e!r}")
            return False

        try:
            sections_repo.ensure_section_tree(self._well_id, data)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to build section tree after Step 1 save.\n\n"
                f"Details:\n{e!r}",
            )
            return False

        if emit_signal:
            self.step1_saved.emit(self._well_id)
        if show_message:
            QMessageBox.information(self, "Information", "Well Identity saved.")
        return True

    def set_well_id(self, well_id: str) -> None:
        self._well_id = str(well_id or "").strip()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        if not value:
            return
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if combo.isEditable():
            combo.setEditText(value)

    def _load_from_db(self) -> None:
        if not self._well_id:
            return
        row = identity_repo.get_identity(self._well_id)
        if not row:
            return

        self.well_name.blockSignals(True)
        self.well_name.setText(str(row.get("well_name") or ""))
        self.well_name.blockSignals(False)

        self.well_key.setText(str(row.get("well_key") or ""))
        self.field_name.setText(str(row.get("field_name") or ""))

        self._set_combo_value(self.operator, str(row.get("operator") or ""))
        self._set_combo_value(self.contractor, str(row.get("contractor") or ""))
        self._set_combo_value(self.well_purpose, str(row.get("well_purpose") or ""))
        self._set_combo_value(self.well_type, str(row.get("well_type") or ""))
        self._set_combo_value(self.dd_well_type, str(row.get("dd_well_type") or ""))
        self._set_combo_value(self.province, str(row.get("province") or ""))
        self._set_combo_value(self.rig_name, str(row.get("rig_name") or ""))

        self.notes.blockSignals(True)
        self.notes.setPlainText(str(row.get("notes") or ""))
        self.notes.blockSignals(False)

    def collect_data(self) -> dict:
        # Note: UUID will be generated later in DB layer.
        return {
            "well_name": self.well_name.text().strip(),
            "well_key": self.well_key.text().strip(),
            "field_name": self.field_name.text().strip(),
            "operator": canonical_text(self.operator.currentText()),
            "contractor": canonical_text(self.contractor.currentText()),
            "well_purpose": self.well_purpose.currentText(),
            "well_type": self.well_type.currentText(),
            "dd_well_type": self.dd_well_type.currentText(),
            "province": canonical_text(self.province.currentText()),
            "rig_name": canonical_text(self.rig_name.currentText()),
            "notes": canonical_text(self.notes.toPlainText()) if self.notes.toPlainText().strip() else "",
        }
