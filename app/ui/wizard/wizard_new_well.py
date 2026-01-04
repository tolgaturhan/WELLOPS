from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
)

from app.data.db import get_connection
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
        enabled = set()
        try:
            from app.data.hole_sections_repo import get_enabled_hole_sizes  # type: ignore
            enabled = set(get_enabled_hole_sizes(self.well_id))
        except Exception:
            enabled = set()
        self.step3 = Step3HoleProgram(well_id=self.well_id, enabled_node_keys=enabled)
        self.step3.enabled_node_keys_changed.connect(self._on_hole_sections_changed)

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
        if not self.step1.save_to_db(show_message=False, emit_signal=False):
            return

        # Move to Step2
        self._swap_step_widget(self.step1, self.step2)
        self.current_step = 2
        self.btn_next.setText("Next")

    def _handle_step2_next(self) -> None:
        if not self.step2.save_to_db(show_message=False, emit_signal=False):
            return

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

    def _on_hole_sections_changed(self, well_id: str, enabled_set: set[str]) -> None:
        try:
            from app.data.hole_sections_repo import save_enabled_hole_sizes  # type: ignore
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save hole sections.\n\nDetails:\n{e!r}")
            return
        save_enabled_hole_sizes(well_id, enabled_set)
        QMessageBox.information(self, "Information", "Saved.")

    def _try_prefill_step1_well_name(self, name: str) -> None:
        """
        Best-effort injection of initial well name into Step1 without modifying Step1 code.
        """
        if not name:
            return
        try:
            if getattr(self.step1, "well_name", None) is not None:
                if self.step1.well_name.text().strip():
                    return
        except Exception:
            pass

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
