# app/ui/hole_section_form.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, Any, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QComboBox,
    QDoubleSpinBox,
)

from app.core.rules.hole_section_rules import (
    validate_hole_section,
    MUD_MOTOR_BRANDS,
    MUD_MOTOR_SIZES,
    BEND_ANGLES_DEG,
    LOBE_LIST,
    STAGE_LIST,
    BIT_BRANDS,
    BIT_KINDS,
)
from app.core.hole_section_calcs import (
    NozzleLine,
    nozzle_summary,
    tfa_from_nozzles,
    total_drilling_time_hours,
    total_drilling_meters,
    mob_to_release_hours,
    eff_drilling_percent,
)

from app.ui.dialogs.nozzle_dialog import NozzleDialog
from app.ui.widgets.decimal_line_edit import DecimalLineEdit
from app.ui.widgets.time_hhmm_edit import TimeHHMMEdit
from app.ui.widgets.date_picker_line import DatePickerLine


@dataclass(frozen=True)
class _TicketRow:
    date_key: str
    price_key: str


class HoleSectionForm(QWidget):
    """
    Hole Section Form (UI-only).

    - Scrollable content
    - Validate Section: checks rules and shows errors without saving
    - Save: UI-only message (not wired to DB)
    """

    _HOLE_LABEL_BY_KEY: Dict[str, str] = {
        "HSE_26": '26” HSE',
        "HSE_17_1_2": '17 1/2” HSE',
        "HSE_12_1_4": '12 1/4” HSE',
        "HSE_8_1_2": '8 1/2” HSE',
        "HSE_6": '6” HSE',
    }

    _TICKET_ROWS: List[_TicketRow] = [
        _TicketRow("ticket_date_1", "ticket_price_usd_1"),
        _TicketRow("ticket_date_2", "ticket_price_usd_2"),
        _TicketRow("ticket_date_3", "ticket_price_usd_3"),
    ]

    def __init__(
        self,
        well_id: str,
        hole_node_key: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._well_id: str = str(well_id).strip()
        self._hole_node_key: str = str(hole_node_key).strip()

        # state for nozzle dialog
        self._nozzles: List[NozzleLine] = []

        # widget handles
        self._ticket_dates: Dict[str, DatePickerLine] = {}
        self._ticket_prices: Dict[str, QDoubleSpinBox] = {}

        self.cmb_mud_brand: Optional[QComboBox] = None
        self.cmb_mud_size: Optional[QComboBox] = None
        self.edt_sleeve_gauge: Optional[DecimalLineEdit] = None
        self.cmb_bend_angle: Optional[QComboBox] = None
        self.cmb_lobe: Optional[QComboBox] = None
        self.cmb_stage: Optional[QComboBox] = None
        self.edt_ibs_gauge: Optional[DecimalLineEdit] = None

        self.cmb_bit_brand: Optional[QComboBox] = None
        self.cmb_bit_kind: Optional[QComboBox] = None
        self.edt_bit_type: Optional[QLineEdit] = None
        self.edt_bit_iadc: Optional[QLineEdit] = None
        self.edt_bit_serial: Optional[QLineEdit] = None
        self.edt_nozzle_summary: Optional[QLineEdit] = None
        self.edt_tfa_in2: Optional[QLineEdit] = None

        self.edt_day_dd: Optional[QLineEdit] = None
        self.edt_night_dd: Optional[QLineEdit] = None
        self.edt_day_mwd: Optional[QLineEdit] = None
        self.edt_night_mwd: Optional[QLineEdit] = None

        self.edt_info_casing_shoe: Optional[QLineEdit] = None
        self.edt_info_casing_od_id: Optional[QLineEdit] = None
        self.edt_info_section_tvd: Optional[QLineEdit] = None
        self.edt_info_section_md: Optional[QLineEdit] = None
        self.edt_info_mud_type: Optional[QLineEdit] = None

        self.dp_call_out_date: Optional[DatePickerLine] = None
        self.edt_crew_mob_time: Optional[TimeHHMMEdit] = None

        self.edt_standby: Optional[DecimalLineEdit] = None
        self.edt_ru: Optional[DecimalLineEdit] = None
        self.edt_tripping: Optional[DecimalLineEdit] = None
        self.edt_circulation: Optional[DecimalLineEdit] = None

        self.edt_rotary_time: Optional[DecimalLineEdit] = None
        self.edt_rotary_m: Optional[DecimalLineEdit] = None
        self.edt_sliding_time: Optional[DecimalLineEdit] = None
        self.edt_sliding_m: Optional[DecimalLineEdit] = None

        self.edt_total_drilling_time: Optional[QLineEdit] = None
        self.edt_total_drilling_m: Optional[QLineEdit] = None

        self.edt_npt_rig: Optional[DecimalLineEdit] = None
        self.edt_npt_motor: Optional[DecimalLineEdit] = None
        self.edt_npt_mwd: Optional[DecimalLineEdit] = None

        self.dp_release_date: Optional[DatePickerLine] = None
        self.edt_release_time: Optional[TimeHHMMEdit] = None

        self.edt_mob_to_release: Optional[QLineEdit] = None

        self.edt_total_brt: Optional[DecimalLineEdit] = None
        self.edt_eff_drilling: Optional[QLineEdit] = None

        self.btn_validate: Optional[QPushButton] = None
        self.btn_save: Optional[QPushButton] = None

        self._build_ui()
        self._wire_live_calcs()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hole_label = self._HOLE_LABEL_BY_KEY.get(self._hole_node_key, self._hole_node_key)

        title = QLabel(f"Hole Section Form — {hole_label}")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        title.setFont(title_font)
        title.setWordWrap(True)

        context = QLabel(f"Well ID: {self._well_id}")
        context.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)

        root.addWidget(title)
        root.addWidget(context)
        root.addWidget(divider)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_ticket_group())
        layout.addWidget(self._build_mud_motor_group())
        layout.addWidget(self._build_bit_group())
        layout.addWidget(self._build_personnel_group())
        layout.addWidget(self._build_info_group())
        layout.addWidget(self._build_time_analysis_group())
        layout.addStretch(1)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        self.btn_validate = QPushButton("Validate Section")
        self.btn_validate.clicked.connect(self._on_validate_clicked)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self._on_save_clicked)

        btn_row.addWidget(self.btn_validate)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

    # --------------------------
    # Builders
    # --------------------------
    def _group_box(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        return box

    def _combo_with_placeholder(self, placeholder: str, items: List[str]) -> QComboBox:
        cmb = QComboBox()
        cmb.setEditable(False)
        cmb.addItem(placeholder)
        cmb.addItems(items)
        return cmb

    def _build_ticket_group(self) -> QGroupBox:
        box = self._group_box("TICKET")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        for row in self._TICKET_ROWS:
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(10)

            dp = DatePickerLine()
            dp.set_placeholder("Click to select date")
            dp.edit.setPlaceholderText("Click to select date")
            dp.btn.setToolTip("Select ticket date")

            price = QDoubleSpinBox()
            price.setDecimals(2)
            price.setMinimum(0.00)
            price.setMaximum(999999999.99)
            price.setPrefix("$ ")
            price.setSingleStep(10.00)
            price.setFixedWidth(160)

            self._ticket_dates[row.date_key] = dp
            self._ticket_prices[row.price_key] = price

            h.addWidget(dp, 1)
            h.addWidget(QLabel("PRICE (USD)"))
            h.addWidget(price)

            form.addRow("TICKET DATE", w)

        return box

    def _build_mud_motor_group(self) -> QGroupBox:
        box = self._group_box("MUD MOTOR")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.cmb_mud_brand = self._combo_with_placeholder("Select from list", list(MUD_MOTOR_BRANDS))
        self.cmb_mud_size = self._combo_with_placeholder("Select from list", list(MUD_MOTOR_SIZES))

        self.edt_sleeve_gauge = DecimalLineEdit()
        self.edt_sleeve_gauge.setPlaceholderText("e.g., 12.125")

        self.cmb_bend_angle = self._combo_with_placeholder("Select from list", list(BEND_ANGLES_DEG))

        # LOBE-STAGE: two combos in one row
        ls_widget = QWidget()
        ls_layout = QHBoxLayout(ls_widget)
        ls_layout.setContentsMargins(0, 0, 0, 0)
        ls_layout.setSpacing(10)

        self.cmb_lobe = self._combo_with_placeholder("Select from list", list(LOBE_LIST))
        self.cmb_stage = self._combo_with_placeholder("Select from list", list(STAGE_LIST))

        ls_layout.addWidget(QLabel("LOBE"))
        ls_layout.addWidget(self.cmb_lobe, 1)
        ls_layout.addWidget(QLabel("STAGE"))
        ls_layout.addWidget(self.cmb_stage, 1)

        self.edt_ibs_gauge = DecimalLineEdit()
        self.edt_ibs_gauge.setPlaceholderText("e.g., 11.937")
        self.edt_ibs_gauge.set_allow_empty(True)

        form.addRow("BRAND", self.cmb_mud_brand)
        form.addRow("SIZE", self.cmb_mud_size)
        form.addRow("SLEEVE STB GAUGE (IN)", self.edt_sleeve_gauge)
        form.addRow("BEND ANGLE (DEG)", self.cmb_bend_angle)
        form.addRow("LOBE-STAGE", ls_widget)
        form.addRow("IBS GAUGE (IN)", self.edt_ibs_gauge)

        return box

    def _build_bit_group(self) -> QGroupBox:
        box = self._group_box("BIT")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        # BRAND + (PDC/TRICONE) side-by-side
        brand_kind = QWidget()
        hk = QHBoxLayout(brand_kind)
        hk.setContentsMargins(0, 0, 0, 0)
        hk.setSpacing(10)

        self.cmb_bit_brand = self._combo_with_placeholder("Select from list", list(BIT_BRANDS))
        self.cmb_bit_kind = self._combo_with_placeholder("Select from list", list(BIT_KINDS))

        hk.addWidget(self.cmb_bit_brand, 2)
        hk.addWidget(self.cmb_bit_kind, 1)

        self.edt_bit_type = QLineEdit()
        self.edt_bit_type.setPlaceholderText("e.g., TKC66, TX36275")

        self.edt_bit_iadc = QLineEdit()
        self.edt_bit_iadc.setPlaceholderText("e.g., 517, 537G, M423")

        self.edt_bit_serial = QLineEdit()
        self.edt_bit_serial.setPlaceholderText("e.g., F310849, 5360463")

        # NOZZLE/TFA: nozzle summary (click to open dialog) + TFA read-only
        nt_widget = QWidget()
        nt_layout = QHBoxLayout(nt_widget)
        nt_layout.setContentsMargins(0, 0, 0, 0)
        nt_layout.setSpacing(10)

        self.edt_nozzle_summary = QLineEdit()
        self.edt_nozzle_summary.setReadOnly(True)
        self.edt_nozzle_summary.setPlaceholderText("Click to select nozzles")
        self.edt_nozzle_summary.setCursor(Qt.PointingHandCursor)
        # click handler
        self.edt_nozzle_summary.mousePressEvent = self._on_nozzle_clicked  # type: ignore[assignment]

        self.edt_tfa_in2 = QLineEdit()
        self.edt_tfa_in2.setReadOnly(True)
        self.edt_tfa_in2.setPlaceholderText("Auto")

        nt_layout.addWidget(self.edt_nozzle_summary, 2)
        nt_layout.addWidget(QLabel("TFA (IN²)"))
        nt_layout.addWidget(self.edt_tfa_in2, 1)

        form.addRow("BRAND / PDC-TRICONE", brand_kind)
        form.addRow("TYPE", self.edt_bit_type)
        form.addRow("IADC", self.edt_bit_iadc)
        form.addRow("SERIAL", self.edt_bit_serial)
        form.addRow("NOZZLE/TFA", nt_widget)

        return box

    def _build_personnel_group(self) -> QGroupBox:
        box = self._group_box("PERSONNEL")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.edt_day_dd = QLineEdit()
        self.edt_night_dd = QLineEdit()
        self.edt_day_mwd = QLineEdit()
        self.edt_night_mwd = QLineEdit()

        form.addRow("DAY DD", self.edt_day_dd)
        form.addRow("NIGHT DD", self.edt_night_dd)
        form.addRow("DAY MWD", self.edt_day_mwd)
        form.addRow("NIGHT MWD", self.edt_night_mwd)

        return box

    def _build_info_group(self) -> QGroupBox:
        box = self._group_box("INFO")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.edt_info_casing_shoe = QLineEdit()
        self.edt_info_casing_od_id = QLineEdit()
        self.edt_info_section_tvd = QLineEdit()
        self.edt_info_section_md = QLineEdit()
        self.edt_info_mud_type = QLineEdit()

        form.addRow("CASING SHOE", self.edt_info_casing_shoe)
        form.addRow("CASING OD/ID", self.edt_info_casing_od_id)
        form.addRow("SECTION TVD", self.edt_info_section_tvd)
        form.addRow("SECTION MD", self.edt_info_section_md)
        form.addRow("MUD TYPE", self.edt_info_mud_type)

        return box

    def _build_time_analysis_group(self) -> QGroupBox:
        box = self._group_box("TIME ANALYSIS")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.dp_call_out_date = DatePickerLine()
        self.dp_call_out_date.set_placeholder(
            "If the prev. sec. isn't released, select the day after the last invoice date."
        )

        self.edt_crew_mob_time = TimeHHMMEdit()
        self.edt_crew_mob_time.setPlaceholderText("e.g., 16:30, 24:00, 00:00")

        self.edt_standby = DecimalLineEdit()
        self.edt_standby.setPlaceholderText("e.g., 0, 12, 48, 107.85")

        self.edt_ru = DecimalLineEdit()
        self.edt_ru.setPlaceholderText("e.g., 0, 4.5, 7, 9.25")

        self.edt_tripping = DecimalLineEdit()
        self.edt_tripping.setPlaceholderText("e.g., 0, 4.5, 7, 9.25")

        self.edt_circulation = DecimalLineEdit()
        self.edt_circulation.setPlaceholderText("e.g., 0, 88, 93.75, 102.6")

        self.edt_rotary_time = DecimalLineEdit()
        self.edt_rotary_time.setPlaceholderText("e.g., 0, 189, 205.24, 246.7")

        self.edt_rotary_m = DecimalLineEdit()
        self.edt_rotary_m.setPlaceholderText("e.g., 0, 634.78, 725, 1204.6")

        self.edt_sliding_time = DecimalLineEdit()
        self.edt_sliding_time.setPlaceholderText("e.g., 0, 25, 54.6")

        self.edt_sliding_m = DecimalLineEdit()
        self.edt_sliding_m.setPlaceholderText("e.g., 0, 124, 167.5")

        # Derived totals (read-only)
        self.edt_total_drilling_time = QLineEdit()
        self.edt_total_drilling_time.setReadOnly(True)
        self.edt_total_drilling_time.setPlaceholderText("Auto")

        self.edt_total_drilling_m = QLineEdit()
        self.edt_total_drilling_m.setReadOnly(True)
        self.edt_total_drilling_m.setPlaceholderText("Auto")

        self.edt_npt_rig = DecimalLineEdit()
        self.edt_npt_rig.setPlaceholderText("e.g., 0, 16, 27.8")

        self.edt_npt_motor = DecimalLineEdit()
        self.edt_npt_motor.setPlaceholderText("e.g., 0, 16, 27.8")

        self.edt_npt_mwd = DecimalLineEdit()
        self.edt_npt_mwd.setPlaceholderText("e.g., 0, 16, 27.8")

        self.dp_release_date = DatePickerLine()
        self.dp_release_date.set_placeholder("Important: If not released, choose the latest invoice date")

        self.edt_release_time = TimeHHMMEdit()
        self.edt_release_time.setPlaceholderText("Important: If not released, use 00:00 as the time value.")

        self.edt_mob_to_release = QLineEdit()
        self.edt_mob_to_release.setReadOnly(True)
        self.edt_mob_to_release.setPlaceholderText("Auto")

        self.edt_total_brt = DecimalLineEdit()
        self.edt_total_brt.setPlaceholderText("e.g., 0, 180, 212.45, 370.5")

        self.edt_eff_drilling = QLineEdit()
        self.edt_eff_drilling.setReadOnly(True)
        self.edt_eff_drilling.setPlaceholderText("Auto")

        form.addRow("CALL OUT DATE", self.dp_call_out_date)
        form.addRow("CREW MOB TIME", self.edt_crew_mob_time)
        form.addRow("STANDBY TIME (HRS)", self.edt_standby)
        form.addRow("R/U TIME (HRS)", self.edt_ru)
        form.addRow("TRIPPING TIME (HRS)", self.edt_tripping)
        form.addRow("CIRCULATION TIME (HRS)", self.edt_circulation)

        form.addRow("ROTARY TIME (HRS)", self.edt_rotary_time)
        form.addRow("ROTARY (METER)", self.edt_rotary_m)
        form.addRow("SLIDING TIME (HRS)", self.edt_sliding_time)
        form.addRow("SLIDING (METER)", self.edt_sliding_m)

        form.addRow("TOTAL DRILLING TIME (HRS)", self.edt_total_drilling_time)
        form.addRow("TOTAL DRILLING (METER)", self.edt_total_drilling_m)

        form.addRow("NPT DUE TO RIG (HRS)", self.edt_npt_rig)
        form.addRow("NPT DUE TO MOTOR (HRS)", self.edt_npt_motor)
        form.addRow("NPT DUE TO MWD (HRS)", self.edt_npt_mwd)

        form.addRow("RELEASE DATE", self.dp_release_date)
        form.addRow("RELEASE TIME", self.edt_release_time)
        form.addRow("MOB TO RELEASE (HRS)", self.edt_mob_to_release)

        form.addRow("TOTAL BRT (HRS)", self.edt_total_brt)
        form.addRow("%EFF DRILLING", self.edt_eff_drilling)

        return box

    # ------------------------------------------------------------------
    # Nozzles dialog
    # ------------------------------------------------------------------
    def _on_nozzle_clicked(self, _event) -> None:
        dlg = NozzleDialog(initial_nozzles=self._nozzles, parent=self)
        if dlg.exec() == dlg.Accepted:
            res = dlg.get_result()
            if res is not None:
                self._nozzles = list(res.nozzles)
                self._sync_nozzle_fields()
                self._recompute_derived()

    def _sync_nozzle_fields(self) -> None:
        if self.edt_nozzle_summary is None or self.edt_tfa_in2 is None:
            return

        if not self._nozzles:
            self.edt_nozzle_summary.setText("")
            self.edt_tfa_in2.setText("")
            return

        self.edt_nozzle_summary.setText(nozzle_summary(self._nozzles))
        try:
            tfa = tfa_from_nozzles(self._nozzles)
            self.edt_tfa_in2.setText(f"{tfa:.4f}")
        except Exception:
            self.edt_tfa_in2.setText("")

    # ------------------------------------------------------------------
    # Live calculations
    # ------------------------------------------------------------------
    def _wire_live_calcs(self) -> None:
        # recompute totals & derived fields when any relevant input changes
        def hook(widget, signal_name: str) -> None:
            sig = getattr(widget, signal_name, None)
            if sig is not None:
                sig.connect(self._recompute_derived)

        # decimal edits
        for w in (
            self.edt_rotary_time, self.edt_sliding_time,
            self.edt_rotary_m, self.edt_sliding_m,
            self.edt_total_brt,
        ):
            if w is not None:
                hook(w, "normalized")

        # time edits
        for w in (self.edt_crew_mob_time, self.edt_release_time):
            if w is not None:
                hook(w, "normalized")

        # date pickers
        for w in (self.dp_call_out_date, self.dp_release_date):
            if w is not None:
                hook(w, "date_changed")

    def _recompute_derived(self) -> None:
        # TOTAL DRILLING TIME / METERS
        if self.edt_rotary_time and self.edt_sliding_time and self.edt_total_drilling_time:
            rt = self.edt_rotary_time.value_or_none()
            st = self.edt_sliding_time.value_or_none()
            if rt is not None and st is not None:
                self.edt_total_drilling_time.setText(f"{total_drilling_time_hours(rt, st):.2f}")
            else:
                self.edt_total_drilling_time.setText("")

        if self.edt_rotary_m and self.edt_sliding_m and self.edt_total_drilling_m:
            rm = self.edt_rotary_m.value_or_none()
            sm = self.edt_sliding_m.value_or_none()
            if rm is not None and sm is not None:
                self.edt_total_drilling_m.setText(f"{total_drilling_meters(rm, sm):.2f}")
            else:
                self.edt_total_drilling_m.setText("")

        # MOB TO RELEASE
        if self.dp_call_out_date and self.edt_crew_mob_time and self.dp_release_date and self.edt_release_time and self.edt_mob_to_release:
            co = self.dp_call_out_date.date_value()
            rt = self.dp_release_date.date_value()
            mob = self.edt_crew_mob_time.value_or_none()
            rel = self.edt_release_time.value_or_none()
            if co and rt and mob and rel:
                try:
                    mtr = mob_to_release_hours(co, mob, rt, rel)
                    self.edt_mob_to_release.setText(f"{mtr:.2f}")
                except Exception:
                    self.edt_mob_to_release.setText("")
            else:
                self.edt_mob_to_release.setText("")

        # %EFF DRILLING
        if self.edt_eff_drilling and self.edt_total_brt and self.edt_total_drilling_time:
            brt = self.edt_total_brt.value_or_none()
            try:
                dt = float(self.edt_total_drilling_time.text().strip()) if self.edt_total_drilling_time.text().strip() else 0.0
            except Exception:
                dt = 0.0
            if brt is None:
                self.edt_eff_drilling.setText("")
            else:
                self.edt_eff_drilling.setText(f"{eff_drilling_percent(dt, brt):.2f}")

    # ------------------------------------------------------------------
    # Data collection + validation
    # ------------------------------------------------------------------
    def _collect_section_data(self) -> Dict[str, Any]:
        # ticket is NOT validated, but we still collect it for future DB wiring
        ticket_dates: Dict[str, Optional[date]] = {
            k: w.date_value() for k, w in self._ticket_dates.items()
        }
        ticket_prices: Dict[str, float] = {
            k: float(w.value()) for k, w in self._ticket_prices.items()
        }

        def combo_value(cmb: Optional[QComboBox]) -> str:
            if cmb is None:
                return ""
            txt = cmb.currentText().strip()
            # placeholder logic: placeholder is first item "Select from list"
            if txt == "Select from list":
                return ""
            return txt

        data: Dict[str, Any] = {}

        # TICKET (UI-only)
        data.update(ticket_dates)
        data.update(ticket_prices)

        # MUD MOTOR (rules keys)
        data["mud_motor_brand"] = combo_value(self.cmb_mud_brand)
        data["mud_motor_size"] = combo_value(self.cmb_mud_size)
        data["mud_motor_sleeve_stb_gauge_in"] = self.edt_sleeve_gauge.text().strip() if self.edt_sleeve_gauge else ""
        data["mud_motor_bend_angle_deg"] = combo_value(self.cmb_bend_angle)
        data["mud_motor_lobe"] = combo_value(self.cmb_lobe)
        data["mud_motor_stage"] = combo_value(self.cmb_stage)
        data["mud_motor_ibs_gauge_in"] = self.edt_ibs_gauge.text().strip() if self.edt_ibs_gauge else ""

        # BIT
        data["bit_brand"] = combo_value(self.cmb_bit_brand)
        data["bit_kind"] = combo_value(self.cmb_bit_kind)
        data["bit_type"] = self.edt_bit_type.text().strip() if self.edt_bit_type else ""
        data["bit_iadc"] = self.edt_bit_iadc.text().strip() if self.edt_bit_iadc else ""
        data["bit_serial"] = self.edt_bit_serial.text().strip() if self.edt_bit_serial else ""
        data["bit_nozzles"] = list(self._nozzles)

        # PERSONNEL
        data["personnel_day_dd"] = self.edt_day_dd.text().strip() if self.edt_day_dd else ""
        data["personnel_night_dd"] = self.edt_night_dd.text().strip() if self.edt_night_dd else ""
        data["personnel_day_mwd"] = self.edt_day_mwd.text().strip() if self.edt_day_mwd else ""
        data["personnel_night_mwd"] = self.edt_night_mwd.text().strip() if self.edt_night_mwd else ""

        # INFO (kept UI-only; not validated by rules currently)
        data["info_casing_shoe"] = self.edt_info_casing_shoe.text().strip() if self.edt_info_casing_shoe else ""
        data["info_casing_od_id"] = self.edt_info_casing_od_id.text().strip() if self.edt_info_casing_od_id else ""
        data["info_section_tvd"] = self.edt_info_section_tvd.text().strip() if self.edt_info_section_tvd else ""
        data["info_section_md"] = self.edt_info_section_md.text().strip() if self.edt_info_section_md else ""
        data["info_mud_type"] = self.edt_info_mud_type.text().strip() if self.edt_info_mud_type else ""

        # TIME ANALYSIS (rules keys)
        data["ta_call_out_date"] = self.dp_call_out_date.date_value() if self.dp_call_out_date else None
        data["ta_crew_mob_time"] = self.edt_crew_mob_time.text().strip() if self.edt_crew_mob_time else ""

        data["ta_standby_time_hrs"] = self.edt_standby.text().strip() if self.edt_standby else ""
        data["ta_ru_time_hrs"] = self.edt_ru.text().strip() if self.edt_ru else ""
        data["ta_tripping_time_hrs"] = self.edt_tripping.text().strip() if self.edt_tripping else ""
        data["ta_circulation_time_hrs"] = self.edt_circulation.text().strip() if self.edt_circulation else ""

        data["ta_rotary_time_hrs"] = self.edt_rotary_time.text().strip() if self.edt_rotary_time else ""
        data["ta_rotary_meters"] = self.edt_rotary_m.text().strip() if self.edt_rotary_m else ""
        data["ta_sliding_time_hrs"] = self.edt_sliding_time.text().strip() if self.edt_sliding_time else ""
        data["ta_sliding_meters"] = self.edt_sliding_m.text().strip() if self.edt_sliding_m else ""

        data["ta_npt_due_to_rig_hrs"] = self.edt_npt_rig.text().strip() if self.edt_npt_rig else ""
        data["ta_npt_due_to_motor_hrs"] = self.edt_npt_motor.text().strip() if self.edt_npt_motor else ""
        data["ta_npt_due_to_mwd_hrs"] = self.edt_npt_mwd.text().strip() if self.edt_npt_mwd else ""

        data["ta_release_date"] = self.dp_release_date.date_value() if self.dp_release_date else None
        data["ta_release_time"] = self.edt_release_time.text().strip() if self.edt_release_time else ""

        data["ta_total_brt_hrs"] = self.edt_total_brt.text().strip() if self.edt_total_brt else ""

        return data

    def _apply_computed(self, computed: Dict[str, Any]) -> None:
        # times
        if self.edt_crew_mob_time and computed.get("ta_crew_mob_time_norm"):
            self.edt_crew_mob_time.setText(str(computed["ta_crew_mob_time_norm"]))
        if self.edt_release_time and computed.get("ta_release_time_norm"):
            self.edt_release_time.setText(str(computed["ta_release_time_norm"]))

        # totals
        if self.edt_total_drilling_time and computed.get("ta_total_drilling_time_hrs") is not None:
            self.edt_total_drilling_time.setText(f"{float(computed['ta_total_drilling_time_hrs']):.2f}")
        if self.edt_total_drilling_m and computed.get("ta_total_drilling_meters") is not None:
            self.edt_total_drilling_m.setText(f"{float(computed['ta_total_drilling_meters']):.2f}")

        # mob to release (hard required)
        if self.edt_mob_to_release:
            v = computed.get("ta_mob_to_release_hrs")
            self.edt_mob_to_release.setText(f"{float(v):.2f}" if v is not None else "")

        # eff drilling
        if self.edt_eff_drilling and computed.get("ta_eff_drilling_pct") is not None:
            self.edt_eff_drilling.setText(f"{float(computed['ta_eff_drilling_pct']):.2f}")

        # nozzle summary / tfa
        if computed.get("bit_nozzles") is not None:
            self._nozzles = list(computed["bit_nozzles"])
            self._sync_nozzle_fields()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_validate_clicked(self) -> None:
        data = self._collect_section_data()
        result = validate_hole_section(data)

        # Always apply computed values (even if errors exist) to help user see what’s wrong.
        self._apply_computed(result.computed)

        if result.ok:
            QMessageBox.information(self, "Information", "Validation passed. No issues found.")
            return

        msg = "Please fix the following issues:\n\n" + "\n".join(f"- {e}" for e in result.errors)
        QMessageBox.warning(self, "Validation Error", msg)

    def _on_save_clicked(self) -> None:
        # UI-only: no DB wiring yet.
        QMessageBox.information(self, "Information", "Saved (not yet wired to DB).")