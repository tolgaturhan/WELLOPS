# app/ui/main_windows.py
from __future__ import annotations

from typing import Callable, Dict, Optional, Set, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QLabel,
    QStackedWidget,
    QMessageBox,
    QMenuBar,
)

from app.ui.tree.well_tree_widget import WellTreeWidget

# NOTE: wells_repo import is intentionally lazy (zip snapshot may omit app/data/wells_repo.py).

def _repo_list_wells():
    """Lazy import for wells repository (keeps UI import-safe)."""
    try:
        from app.data.wells_repo import list_wells  # type: ignore
        return list_wells
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.wells_repo.list_wells. "
            "Check project wiring (Snapshot 2026-01-03 notes repo missing)."
        ) from e


def _repo_create_draft_well():
    """Lazy import for wells repository (keeps UI import-safe)."""
    try:
        from app.data.wells_repo import create_draft_well  # type: ignore
        return create_draft_well
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.wells_repo.create_draft_well. "
            "Check project wiring (Snapshot 2026-01-03 notes repo missing)."
        ) from e


class _SimpleMessagePage(QWidget):
    """Small internal fallback page (English-only messages)."""

    def __init__(self, message: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(label)
        layout.addStretch(1)


class MainWindows(QMainWindow):
    """
    Main window:
      - Left: Well tree
      - Right: Router stack (single-router UX)
    """

    # Fixed list of hole node keys (tree nodes, not Step3 list items)
    _HOLE_NODE_KEYS: Set[str] = {
        "hole_section_26",
        "hole_section_17_5",
        "hole_section_12_25",
        "hole_section_8_5",
        "hole_section_6",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TPIC WellOps")

        # In-memory (UI-only) enabled hole sizes per well (KEY MUST BE str / well_id TEXT)
        self._enabled_hole_sizes: Dict[str, Set[str]] = {}

        # Cache widgets per (well_id, node_key) to preserve unsaved UI state
        self._widget_cache: Dict[Tuple[str, str], QWidget] = {}

        # Right panel stack
        self._stack = QStackedWidget()
        self._stack.setContentsMargins(0, 0, 0, 0)

        self._default_page = _SimpleMessagePage("Please select a subsection...")
        self._stack.addWidget(self._default_page)
        self._stack.setCurrentWidget(self._default_page)

        # Left tree
        self.well_tree = WellTreeWidget()
        self.well_tree.node_clicked.connect(self._on_tree_node_clicked)

        # Layout with splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.well_tree)
        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(splitter)
        self.setCentralWidget(container)

        # Menu
        self._build_menu()

        # Load wells
        self.reload_wells()

    # ----------------------------------------------------------------------------------
    # Menu
    # ----------------------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        menu_file = menubar.addMenu("File")

        self.act_new_well = QAction("Create New Well", self)
        self.act_new_well.triggered.connect(self._on_create_new_well)
        menu_file.addAction(self.act_new_well)

        self.act_reload = QAction("Reload Wells", self)
        self.act_reload.triggered.connect(self.reload_wells)
        menu_file.addAction(self.act_reload)

        menu_file.addSeparator()

        self.act_exit = QAction("Exit", self)
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

    # ----------------------------------------------------------------------------------
    # Wells list
    # ----------------------------------------------------------------------------------
    def reload_wells(self) -> None:
        try:
            wells = _repo_list_wells()()
            self.set_wells(wells)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to load wells.\n\nDetails:\n{e!r}")

    def set_wells(self, wells: list[dict]) -> None:
        """
        Expected dict keys from wells_repo.list_wells():
          - id: str (well_id)
          - name: str (well_name)
          - status: str
        """
        self.well_tree.set_wells(wells)

    # ----------------------------------------------------------------------------------
    # New Well Flow (FINAL)
    # ----------------------------------------------------------------------------------
    def _on_create_new_well(self) -> None:
        """
        FINAL flow:
          NewWellDialog -> creates DRAFT well -> opens WizardNewWell(well_id, well_name)
        """
        try:
            from app.ui.dialogs.new_well_dialog import NewWellDialog  # type: ignore
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                "NewWellDialog could not be loaded.\n\n"
                f"Details:\n{e!r}",
            )
            return

        dlg = NewWellDialog(self)
        if not dlg.exec():
            return

        # Get well name from dialog (supports both method- and attribute-based dialogs)
        well_name = ""

        getter = getattr(dlg, "get_well_name", None)
        if callable(getter):
            well_name = (getter() or "").strip()
        else:
            # Some dialogs expose the value as an attribute/property (e.g. dlg.well_name)
            val = getattr(dlg, "well_name", "")
            well_name = (val or "").strip()
        if not well_name:
            QMessageBox.warning(self, "Warning", "Well Name cannot be empty.")
            return

        # Create DRAFT well row (DB) -> returns well_id (TEXT)
        try:
            well_id = str(_repo_create_draft_well()(well_name))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create draft well.\n\nDetails:\n{e!r}")
            return

        # Refresh tree and select the well
        self.reload_wells()
        self.well_tree.select_well_by_id(well_id)

        # Open wizard on right panel
        wiz = self._create_wizard_new_well(well_id=well_id, well_name=well_name)
        self._show_widget(wiz)

    def _create_wizard_new_well(self, well_id: str, well_name: str):
        try:
            from app.ui.wizard.wizard_new_well import WizardNewWell  # type: ignore
        except Exception:
            return _SimpleMessagePage("WizardNewWell could not be loaded.")

        # Be tolerant for constructor signature differences
        try:
            return WizardNewWell(well_id=well_id, well_name=well_name)
        except TypeError:
            return WizardNewWell(well_id, well_name)

    # ----------------------------------------------------------------------------------
    # Router (single router UX)
    # ----------------------------------------------------------------------------------
    def _on_tree_node_clicked(self, well_id: str, node_key: str) -> None:
        # well_id is TEXT => force str (defensive)
        wid = str(well_id)

        # Cache key
        cache_key = (wid, node_key)

        # Return cached widget if exists
        if cache_key in self._widget_cache:
            self._show_widget(self._widget_cache[cache_key])
            return

        widget = self._route_create_widget(wid, node_key)
        self._widget_cache[cache_key] = widget
        self._show_widget(widget)

    def _route_create_widget(self, well_id: str, node_key: str) -> QWidget:
        # WELL NAME -> overview page message
        if node_key == "well_name":
            return self._try_create_well_overview_page()

        # Step pages
        if node_key == "well_identity":
            return self._try_create_step1_identity(well_id)

        if node_key == "trajectory":
            return self._try_create_step2_trajectory(well_id)

        if node_key == "hole_section":
            return self._try_create_step3_hole_program(well_id)

        # Hole section forms
        if node_key in self._HOLE_NODE_KEYS:
            enabled = self.is_hole_size_enabled(well_id, node_key)
            if not enabled:
                return self._try_create_disable_section_page(node_key)
            return self._try_create_hole_section_form(well_id, node_key)

        return _SimpleMessagePage("Unknown section.")

    def _show_widget(self, widget: QWidget) -> None:
        if self._stack.indexOf(widget) < 0:
            self._stack.addWidget(widget)
        self._stack.setCurrentWidget(widget)

    # ----------------------------------------------------------------------------------
    # Enabled hole sizes (UI-only)
    # ----------------------------------------------------------------------------------
    def set_enabled_hole_sizes(self, well_id: str, enabled_node_keys: Set[str]) -> None:
        self._enabled_hole_sizes[str(well_id)] = set(enabled_node_keys)

    def get_enabled_hole_sizes(self, well_id: str) -> Set[str]:
        return set(self._enabled_hole_sizes.get(str(well_id), set()))

    def is_hole_size_enabled(self, well_id: str, hole_node_key: str) -> bool:
        return hole_node_key in self.get_enabled_hole_sizes(well_id)

    # ----------------------------------------------------------------------------------
    # Widget factories (defensive imports)
    # ----------------------------------------------------------------------------------
    def _try_create_well_overview_page(self) -> QWidget:
        try:
            from app.ui.well_overview_page import WellOverviewPage  # type: ignore
            return WellOverviewPage()
        except Exception:
            return _SimpleMessagePage("Please select a subsection...")

    def _try_create_disable_section_page(self, hole_node_key: str) -> QWidget:
        try:
            from app.ui.disable_section_page import DisableSectionPage  # type: ignore
            return DisableSectionPage(hole_node_key=hole_node_key)
        except Exception:
            return _SimpleMessagePage("This section is disabled.")

    def _try_create_hole_section_form(self, well_id: str, hole_node_key: str) -> QWidget:
        try:
            from app.ui.hole_section_form import HoleSectionForm  # type: ignore
            return HoleSectionForm(well_id=well_id, hole_node_key=hole_node_key)
        except Exception:
            return _SimpleMessagePage("HoleSectionForm could not be loaded.")

    def _try_create_step1_identity(self, well_id: str) -> QWidget:
        try:
            from app.ui.wizard.step1_well_identity import Step1WellIdentity  # type: ignore
            try:
                return Step1WellIdentity(well_id=well_id)
            except TypeError:
                return Step1WellIdentity(well_id)
        except Exception:
            return _SimpleMessagePage("Step1WellIdentity could not be loaded.")

    def _try_create_step2_trajectory(self, well_id: str) -> QWidget:
        try:
            from app.ui.wizard.step2_trajectory import Step2Trajectory  # type: ignore
            try:
                return Step2Trajectory(well_id=well_id)
            except TypeError:
                return Step2Trajectory(well_id)
        except Exception:
            return _SimpleMessagePage("Step2Trajectory could not be loaded.")

    def _try_create_step3_hole_program(self, well_id: str) -> QWidget:
        try:
            from app.ui.wizard.step3_hole_program import Step3HoleProgram  # type: ignore

            enabled_now = self.get_enabled_hole_sizes(well_id)
            try:
                step3 = Step3HoleProgram(well_id=well_id, enabled_node_keys=enabled_now)
            except TypeError:
                try:
                    step3 = Step3HoleProgram(well_id=well_id)
                except TypeError:
                    step3 = Step3HoleProgram(well_id)

            if hasattr(step3, "enabled_node_keys_changed"):
                step3.enabled_node_keys_changed.connect(self._on_step3_enabled_changed)  # type: ignore[attr-defined]
            return step3
        except Exception:
            return _SimpleMessagePage("Step3HoleProgram could not be loaded.")

    def _on_step3_enabled_changed(self, well_id, enabled_node_keys) -> None:
        wid = str(well_id)
        try:
            enabled_set = set(enabled_node_keys)
        except Exception:
            enabled_set = set()

        enabled_set = {k for k in enabled_set if k in self._HOLE_NODE_KEYS}
        self.set_enabled_hole_sizes(wid, enabled_set)

# ---------------------------------------------------------------------
# Compatibility: app.main expects MainWindow symbol
# ---------------------------------------------------------------------
MainWindow = MainWindows