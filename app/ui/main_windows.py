# app/ui/main_windows.py
from __future__ import annotations

from typing import Callable, Dict, Optional, Set, Tuple

from PySide6.QtCore import Qt, QSettings
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
    QApplication,
)


def _repo_list_wells():
    """Lazy import for wells repository (keeps UI import-safe)."""
    try:
        from app.data.wells_repo import list_wells  # type: ignore
        return list_wells
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.wells_repo.list_wells. "
            "Check project wiring."
        ) from e


def _repo_create_draft_well():
    """Lazy import for wells repository (keeps UI import-safe)."""
    try:
        from app.data.wells_repo import create_draft_well  # type: ignore
        return create_draft_well
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.wells_repo.create_draft_well. "
            "Check project wiring."
        ) from e


def _repo_delete_well():
    """Lazy import for wells repository (keeps UI import-safe)."""
    try:
        from app.data.wells_repo import delete_well  # type: ignore
        return delete_well
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.wells_repo.delete_well. "
            "Check project wiring."
        ) from e


def _repo_get_enabled_hole_sizes():
    """Lazy import for hole sections repository (keeps UI import-safe)."""
    try:
        from app.data.hole_sections_repo import get_enabled_hole_sizes  # type: ignore
        return get_enabled_hole_sizes
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.hole_sections_repo.get_enabled_hole_sizes. "
            "Check project wiring."
        ) from e


def _repo_save_enabled_hole_sizes():
    """Lazy import for hole sections repository (keeps UI import-safe)."""
    try:
        from app.data.hole_sections_repo import save_enabled_hole_sizes  # type: ignore
        return save_enabled_hole_sizes
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "Repository module not available: app.data.hole_sections_repo.save_enabled_hole_sizes. "
            "Check project wiring."
        ) from e


class _SimpleMessagePage(QWidget):
    def __init__(self, message: str):
        super().__init__()
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    """
    Main window that hosts:
      - Left: well tree
      - Right: stacked pages
      - Menu: Create New Well
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("TPIC WellOps")
        self._settings = QSettings("TPIC", "WellOps")
        self._current_theme = self._settings.value("ui/theme", "dark")

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

        self._init_ui()
        self._apply_theme(self._current_theme)

    # ----------------------------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------------------------
    def _init_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal, self)

        from app.ui.tree.well_tree_widget import WellTreeWidget  # type: ignore
        self.well_tree = WellTreeWidget(self)
        splitter.addWidget(self.well_tree)

        splitter.addWidget(self._stack)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 9)

        container = QWidget(self)
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(splitter)
        self.setCentralWidget(container)

        # IMPORTANT: WellTreeWidget emits node_clicked (well_id, node_key)
        self.well_tree.node_clicked.connect(self._on_tree_node_clicked)
        self.well_tree.well_delete_requested.connect(self._on_well_delete_requested)

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
        menu_view = menubar.addMenu("View")

        self.act_new_well = QAction("Create New Well", self)
        self.act_new_well.triggered.connect(self._on_create_new_well)
        menu_file.addAction(self.act_new_well)

        self.act_reload = QAction("Reload", self)
        self.act_reload.triggered.connect(self.reload_wells)
        menu_file.addAction(self.act_reload)

        menu_file.addSeparator()

        self.act_exit = QAction("Exit", self)
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

        self.act_dark_mode = QAction("Dark Mode", self)
        self.act_dark_mode.triggered.connect(lambda: self._apply_theme("dark"))
        menu_view.addAction(self.act_dark_mode)

        self.act_light_mode = QAction("Light Mode", self)
        self.act_light_mode.triggered.connect(lambda: self._apply_theme("light"))
        menu_view.addAction(self.act_light_mode)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme = (theme or "dark").lower()
        if theme == "light":
            app.setStyleSheet(
                """
                QWidget { background-color: #f6f3f2; color: #1f1f1f; }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #ffffff; color: #1f1f1f; border: 1px solid #e1d9d7;
                }
                QComboBox QAbstractItemView { background-color: #ffffff; color: #1f1f1f; }
                QGroupBox { border: 1px solid #e1d9d7; margin-top: 10px; }
                QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px 0 3px; }
                QMenuBar, QMenu { background-color: #f6f3f2; color: #1f1f1f; }
                QMenu::item:selected { background-color: #efe9e7; }
                QTreeWidget { background-color: #ffffff; color: #1f1f1f; }
                QHeaderView::section { background-color: #ffffff; color: #1f1f1f; }
                QPushButton { background-color: #ffffff; color: #1f1f1f; border: 1px solid #e1d9d7; padding: 4px 8px; }
                QPushButton:hover { background-color: #f1ecea; }
                """
            )
        else:
            app.setStyleSheet(
                """
                QWidget { background-color: #1f1f1f; color: #e6e6e6; }
                QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #2b2b2b; color: #e6e6e6; border: 1px solid #3a3a3a;
                }
                QComboBox QAbstractItemView { background-color: #2b2b2b; color: #e6e6e6; }
                QGroupBox { border: 1px solid #3a3a3a; margin-top: 10px; }
                QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px 0 3px; }
                QMenuBar, QMenu { background-color: #1f1f1f; color: #e6e6e6; }
                QMenu::item:selected { background-color: #2d2d2d; }
                QTreeWidget { background-color: #2b2b2b; color: #e6e6e6; }
                QHeaderView::section { background-color: #2b2b2b; color: #e6e6e6; }
                QPushButton { background-color: #2b2b2b; color: #e6e6e6; border: 1px solid #3a3a3a; padding: 4px 8px; }
                QPushButton:hover { background-color: #333333; }
                """
            )
        self._current_theme = theme
        self._settings.setValue("ui/theme", theme)

    # ----------------------------------------------------------------------------------
    # Wells list
    # ----------------------------------------------------------------------------------
    def reload_wells(self) -> None:
        try:
            wells = _repo_list_wells()()
            self.set_wells(wells)
            self._apply_last_well_expand()
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
        self._load_enabled_hole_sizes(wells)
        for w in wells:
            wid = str(w.get("id", "")).strip()
            if not wid:
                continue
            enabled = self._enabled_hole_sizes.get(wid, set())
            self.well_tree.set_enabled_hole_sizes(wid, enabled)

    def _load_enabled_hole_sizes(self, wells: list[dict]) -> None:
        self._enabled_hole_sizes.clear()
        for w in wells:
            wid = str(w.get("id", "")).strip()
            if not wid:
                continue
            try:
                enabled = set(_repo_get_enabled_hole_sizes()(wid))
            except Exception:
                enabled = set()
            self._enabled_hole_sizes[wid] = enabled

    def _apply_last_well_expand(self) -> None:
        last_well_id = str(self._settings.value("last_well_id", "") or "")
        self.well_tree.expand_only_well(last_well_id)

    # ----------------------------------------------------------------------------------
    # Stack helper
    # ----------------------------------------------------------------------------------
    def _show_widget(self, w: QWidget) -> None:
        idx = self._stack.indexOf(w)
        if idx == -1:
            self._stack.addWidget(w)
            idx = self._stack.indexOf(w)
        self._stack.setCurrentIndex(idx)

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
            # FIX: dlg.well_name can be a method (callable)
            if callable(val):
                val = val()
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
        # FIX: WellTreeWidget API is select_well_root (not select_well_by_id)
        self.well_tree.select_well_root(well_id)

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
    # Router (single router UX) - keep as-is in your snapshot
    # ----------------------------------------------------------------------------------
    def _on_tree_node_clicked(self, well_id: str, node_key: str) -> None:
        wid = str(well_id)

        if node_key.startswith("HSE_") and not self._is_hole_section_enabled(wid, node_key):
            self._show_widget(
                _SimpleMessagePage(
                    "This hole section is disabled. Enable it in HOLE SECTION and click Apply."
                )
            )
            return

        cache_key = (wid, node_key)

        if cache_key in self._widget_cache:
            self._show_widget(self._widget_cache[cache_key])
            return

        w = self._route_node_to_widget(wid, node_key)
        self._widget_cache[cache_key] = w
        self._show_widget(w)

    def _route_node_to_widget(self, well_id: str, node_key: str) -> QWidget:
        if node_key == "WELL_NAME":
            try:
                from app.ui.well_overview_page import WellOverviewPage  # type: ignore
            except Exception:
                return _SimpleMessagePage("WellOverviewPage could not be loaded.")

            return WellOverviewPage()

        if node_key == "WELL_IDENTITY":
            try:
                from app.ui.wizard.step1_well_identity import Step1WellIdentity  # type: ignore
            except Exception:
                return _SimpleMessagePage("Well Identity page could not be loaded.")

            w = Step1WellIdentity(well_id=well_id)
            w.step1_saved.connect(self._on_step1_saved)
            return w

        if node_key == "TRAJECTORY":
            try:
                from app.ui.wizard.step2_trajectory import Step2Trajectory  # type: ignore
            except Exception:
                return _SimpleMessagePage("Trajectory page could not be loaded.")

            return Step2Trajectory(well_id=well_id)

        if node_key == "HOLE_SECTION":
            try:
                from app.ui.wizard.step3_hole_program import Step3HoleProgram  # type: ignore
            except Exception:
                return _SimpleMessagePage("Hole Section setup page could not be loaded.")

            enabled = self._enabled_hole_sizes.get(well_id, set())
            w = Step3HoleProgram(well_id=well_id, enabled_node_keys=enabled)
            w.enabled_node_keys_changed.connect(self._on_enabled_hole_sizes_changed)
            return w

        if node_key.startswith("HSE_"):
            try:
                from app.ui.hole_section_form import HoleSectionForm  # type: ignore
            except Exception:
                return _SimpleMessagePage("Hole Section form could not be loaded.")

            return HoleSectionForm(well_id=well_id, hole_node_key=node_key)

        return _SimpleMessagePage(f"Route not implemented for: {node_key}")

    def _on_step1_saved(self, well_id: str) -> None:
        self.reload_wells()
        self.well_tree.select_well_root(str(well_id))

    def _is_hole_section_enabled(self, well_id: str, node_key: str) -> bool:
        enabled = self._enabled_hole_sizes.get(str(well_id).strip(), set())
        return node_key in enabled

    def _on_enabled_hole_sizes_changed(self, well_id: str, enabled_set: Set[str]) -> None:
        wid = str(well_id).strip()
        if not wid:
            return

        enabled = set(enabled_set or set())
        self._enabled_hole_sizes[wid] = enabled
        try:
            _repo_save_enabled_hole_sizes()(wid, enabled)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save hole section settings.\n\nDetails:\n{e!r}",
            )
            return
        self.well_tree.set_enabled_hole_sizes(wid, self._enabled_hole_sizes[wid])
        QMessageBox.information(self, "Information", "Saved.")

        # Drop cached widgets for disabled hole sections to avoid stale access.
        for key in list(self._widget_cache.keys()):
            if key[0] == wid and key[1].startswith("HSE_") and key[1] not in enabled_set:
                del self._widget_cache[key]

    def _on_well_delete_requested(self, well_id: str, well_name: str) -> None:
        wid = str(well_id).strip()
        if not wid:
            return

        name = (well_name or "").strip() or "this well"
        msg = (
            f"Are you sure you want to delete '{name}'?\n\n"
            "This will permanently remove the well and all related data."
        )
        res = QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return

        try:
            _repo_delete_well()(wid)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete well.\n\nDetails:\n{e!r}")
            return

        self._enabled_hole_sizes.pop(wid, None)
        for key in list(self._widget_cache.keys()):
            if key[0] == wid:
                del self._widget_cache[key]

        self.reload_wells()

    def closeEvent(self, event) -> None:
        try:
            current_well_id = self.well_tree.current_well_id()
            if current_well_id:
                self._settings.setValue("last_well_id", current_well_id)
        except Exception:
            pass
        super().closeEvent(event)
