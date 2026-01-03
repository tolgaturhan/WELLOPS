from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.data import sections_repo

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)

from app.data.db import get_connection
from app.data import sections_repo
from app.core import rules
from app.ui.wizard.step1_well_identity import Step1WellIdentity
from app.ui.wizard.step2_trajectory import Step2Trajectory
from app.ui.wizard.step3_hole_program import Step3HoleProgram


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class WizardNewWell(QWidget):
    """
    Embedded New Well Wizard.

    IMPORTANT:
    - The well record is created by MainWindow (NewWellDialog -> INSERT wells).
    - This widget receives an existing well_id (and initial well_name).
    - This widget MUST NOT create a new well row.
    """

    well_created = Signal(str)  # well_id
    cancelled = Signal()

    def __init__(self, well_id: str, well_name: str, parent=None):
        super().__init__(parent)

        self.conn: sqlite3.Connection = get_connection()
        self.well_id: str = well_id
        self.initial_well_name: str = well_name

        self.current_step = 1

        self.layout = QVBoxLayout(self)

        # Steps
        self.step1 = Step1WellIdentity(well_id=self.well_id)
        self.step2 = Step2Trajectory(well_id=self.well_id)
        # IMPORTANT FIX: Step3 must know the well context (well_id is TEXT/UUID)
        self.step3 = Step3HoleProgram(well_id=self.well_id, enabled_node_keys=set())

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_next = QPushButton("Next")

        self.btn_cancel.clicked.connect(self.on_cancel)
        self.btn_next.clicked.connect(self.on_next)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_next)

        # Initial view
        self.layout.addWidget(self.step1)
        self.layout.addLayout(btn_row)

        # Prefill well name into Step1 if possible
        self._try_prefill_step1_well_name(self.initial_well_name)

    # ----------------------------
    # Navigation
    # ----------------------------
    def on_cancel(self) -> None:
        # MVP: do not auto-delete the draft well row on cancel.
        # (We can add cleanup later.)
        self.cancelled.emit()
        self.close()

    def on_next(self) -> None:
        try:
            if self.current_step == 1:
                self._handle_step1_next()
            elif self.current_step == 2:
                self._handle_step2_next()
            elif self.current_step == 3:
                self._handle_step3_next()
            else:
                raise RuntimeError(f"Invalid step: {self.current_step}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n\n{e}")

    def _handle_step1_next(self) -> None:
        # 1) Collect data from Step1
        step1_data = self._collect_step1_data()

        # 2) Hard validation via locked rules
        result = rules.validate_step1(step1_data)
        if not result.ok:
            # Show a compact error message
            msg = "Please fix Step 1 errors:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "Validation Error", msg)
            return

        now = iso_now()

        # 3) Update wells table with well_name (if edited in Step1)
        new_name = self._extract_well_name(step1_data) or self.initial_well_name

        with self.conn:
            self.conn.execute(
                """
                UPDATE wells
                SET well_name = ?, step1_done = 1, updated_at = ?
                WHERE well_id = ?
                """,
                (new_name, now, self.well_id),
            )

        # Materialize (or refresh) the per-well section tree after Step 1 is saved.
        # This uses Step1 context (e.g., well_type) to choose the correct template.
        try:
            sections_repo.ensure_section_tree(self.well_id, step1_data)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to build section tree after Step 1 save.\n\n"
                f"Details:\n{e}",
            )
            return

        # Move to Step2
        self._swap_step_widget(self.step1, self.step2)
        self.current_step = 2
        self.btn_next.setText("Next")

    def _handle_step2_next(self) -> None:
        step2_data = self._collect_step2_data()

        result = rules.validate_step2(step2_data)
        if not result.ok:
            msg = "Please fix Step 2 errors:\n\n" + "\n".join(result.errors)
            QMessageBox.warning(self, "Validation Error", msg)
            return

        now = iso_now()

        with self.conn:
            self.conn.execute(
                """
                UPDATE wells
                SET step2_done = 1, updated_at = ?
                WHERE well_id = ?
                """,
                (now, self.well_id),
            )

        # Move to Step3
        self._swap_step_widget(self.step2, self.step3)
        self.current_step = 3
        self.btn_next.setText("Finish")

    def _handle_step3_next(self) -> None:
        # MVP: Step3 is UI-only for now; mark done.
        now = iso_now()
        with self.conn:
            self.conn.execute(
                """
                UPDATE wells
                SET step3_done = 1, updated_at = ?
                WHERE well_id = ?
                """,
                (now, self.well_id),
            )

        self.well_created.emit(self.well_id)
        self.close()

    def closeEvent(self, event) -> None:
        try:
            if getattr(self, "conn", None) is not None:
                self.conn.close()
        except Exception:
            pass
        super().closeEvent(event)

    # ----------------------------
    # UI helpers
    # ----------------------------
    def _swap_step_widget(self, from_widget: QWidget, to_widget: QWidget) -> None:
        self.layout.removeWidget(from_widget)
        from_widget.setParent(None)
        self.layout.insertWidget(0, to_widget)

    def _collect_step1_data(self) -> Dict[str, Any]:
        """
        Collect Step1 form data using best-effort attribute access.
        """
        data: Dict[str, Any] = {}

        def _get_text(widget_names):
            for name in widget_names:
                w = getattr(self.step1, name, None)
                if w is None:
                    continue
                if hasattr(w, "text"):
                    try:
                        return w.text().strip()
                    except Exception:
                        pass
                if hasattr(w, "toPlainText"):
                    try:
                        return w.toPlainText().strip()
                    except Exception:
                        pass
            return ""

        def _get_combo(widget_names):
            for name in widget_names:
                w = getattr(self.step1, name, None)
                if w is None:
                    continue
                if hasattr(w, "currentText"):
                    try:
                        return w.currentText().strip()
                    except Exception:
                        pass
            return ""

        data["well_name"] = _get_text(
            ("edt_well_name", "edit_well_name", "well_name_input", "txt_well_name", "le_well_name")
        )
        data["well_type"] = _get_combo(("cmb_well_type", "combo_well_type", "cb_well_type"))
        data["province"] = _get_combo(("cmb_province", "combo_province", "cb_province"))
        data["rig_name"] = _get_combo(("cmb_rig_name", "combo_rig_name", "cb_rig_name"))
        data["operator"] = _get_combo(("cmb_operator", "combo_operator", "cb_operator"))
        data["field_name"] = _get_text(("edt_field_name", "edit_field_name", "le_field_name"))
        data["well_key"] = _get_text(("edt_well_key", "edit_well_key", "le_well_key"))

        raw = getattr(self.step1, "get_payload", None)
        if callable(raw):
            try:
                extra = raw()
                if isinstance(extra, dict):
                    data.update(extra)
            except Exception:
                pass

        return data

    def _collect_step2_data(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}

        raw = getattr(self.step2, "get_payload", None)
        if callable(raw):
            try:
                extra = raw()
                if isinstance(extra, dict):
                    data.update(extra)
            except Exception:
                pass

        return data

    def _extract_well_name(self, step1_data: Dict[str, Any]) -> Optional[str]:
        for key in ("well_name", "WELL_NAME", "name"):
            v = step1_data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _try_prefill_step1_well_name(self, name: str) -> None:
        """
        Best-effort injection of initial well name into Step1 without modifying Step1 code.
        """
        if not name:
            return

        # 1) Common method names
        for fn_name in ("set_well_name", "setWellName", "prefill_well_name", "prefillWellName"):
            fn = getattr(self.step1, fn_name, None)
            if callable(fn):
                try:
                    fn(name)
                    return
                except Exception:
                    pass

        # 2) Common widget attributes
        for attr in ("edt_well_name", "edit_well_name", "well_name_input", "txt_well_name", "le_well_name"):
            w = getattr(self.step1, attr, None)
            if w is not None and hasattr(w, "setText"):
                try:
                    w.setText(name)
                    return
                except Exception:
                    pass
