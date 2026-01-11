# app/ui/hole_section_form.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
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
    QDialog,
    QAbstractSpinBox,
)

from app.core.canonical import canonical_text
from app.core.rules.hole_section_rules import (
    validate_hole_section,
    MUD_MOTOR_BRANDS,
    MUD_MOTOR_SIZES,
    BEND_ANGLES_DEG,
    LOBE_LIST,
    STAGE_LIST,
    BIT_BRANDS,
    BIT_KINDS,
    CASING_OD_OPTIONS,
    CASING_ID_BY_OD,
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

from app.data import hole_section_data_repo, identity_repo
from app.ui.dialogs.nozzle_dialog import NozzleDialog
from app.ui.widgets.decimal_line_edit import DecimalLineEdit
from app.ui.widgets.time_hhmm_edit import TimeHHMMEdit
from app.ui.widgets.date_picker_line import DatePickerLine
from app.ui.dialogs.stabilizer_gauge_converter import StabilizerGaugeConverterDialog


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
        "HSE_26": '26" HSE',
        "HSE_17_1_2": '17 1/2" HSE',
        "HSE_12_1_4": '12 1/4" HSE',
        "HSE_8_1_2": '8 1/2" HSE',
        "HSE_6": '6" HSE',
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

        # widget handles
        self._ticket_dates: Dict[str, DatePickerLine] = {}
        self._ticket_prices: Dict[str, QDoubleSpinBox] = {}

        self._mud_motor_widgets: Dict[int, Dict[str, Union[QComboBox, QLineEdit, DecimalLineEdit]]] = {}

        self._bit_widgets: Dict[int, Dict[str, QLineEdit | QComboBox]] = {}
        self._bit_nozzles: Dict[int, List[NozzleLine]] = {1: [], 2: []}

        self.edt_day_dd: List[QLineEdit] = []
        self.edt_night_dd: List[QLineEdit] = []
        self.edt_day_mwd: List[QLineEdit] = []
        self.edt_night_mwd: List[QLineEdit] = []

        self.edt_info_casing_shoe: Optional[DecimalLineEdit] = None
        self.cmb_info_casing_od: Optional[QComboBox] = None
        self.cmb_info_casing_id: Optional[QComboBox] = None
        self.edt_info_section_tvd: Optional[DecimalLineEdit] = None
        self.edt_info_section_md: Optional[DecimalLineEdit] = None
        self.cmb_info_mud_type: Optional[QComboBox] = None

        self.dp_call_out_date: Optional[DatePickerLine] = None
        self.edt_crew_mob_time: Optional[TimeHHMMEdit] = None
        self.dp_release_date: Optional[DatePickerLine] = None
        self.edt_release_time: Optional[TimeHHMMEdit] = None
        self.edt_mob_to_release: Optional[QLineEdit] = None

        self._ta_inputs: Dict[str, Dict[int, DecimalLineEdit]] = {}
        self._ta_totals: Dict[str, QLineEdit] = {}
        self._ta_auto_runs: Dict[str, Dict[int, QLineEdit]] = {}
        self._ta_auto_totals: Dict[str, QLineEdit] = {}

        self.btn_validate: Optional[QPushButton] = None
        self.btn_save: Optional[QPushButton] = None

        self._build_ui()
        self._wire_live_calcs()
        self._wire_text_normalization()
        self._load_from_db()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hole_label = self._HOLE_LABEL_BY_KEY.get(self._hole_node_key, self._hole_node_key)

        title = QLabel(f"Hole Section Form - {hole_label}")
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
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch(1)
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
            price.setButtonSymbols(QAbstractSpinBox.NoButtons)
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
        layout = QHBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        layout.addWidget(self._build_mud_motor_subgroup(1, "MUD MOTOR - 1"), 1)
        layout.addWidget(self._build_mud_motor_subgroup(2, "MUD MOTOR - 2"), 1)

        return box

    def _build_mud_motor_subgroup(self, motor_index: int, title: str) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        cmb_brand = self._combo_with_placeholder("Select from list", list(MUD_MOTOR_BRANDS))
        cmb_size = self._combo_with_placeholder("Select from list", list(MUD_MOTOR_SIZES))

        edt_sleeve_gauge = QLineEdit()
        edt_sleeve_gauge.setReadOnly(True)
        edt_sleeve_gauge.setPlaceholderText("Click to open stabilizer converter")
        edt_sleeve_gauge.setCursor(Qt.PointingHandCursor)
        edt_sleeve_gauge.mousePressEvent = (
            lambda event, le=edt_sleeve_gauge: self._open_stabilizer_converter(le, event)
        )  # type: ignore[assignment]

        cmb_bend_angle = self._combo_with_placeholder("Select from list", list(BEND_ANGLES_DEG))

        ls_widget = QWidget()
        ls_layout = QHBoxLayout(ls_widget)
        ls_layout.setContentsMargins(0, 0, 0, 0)
        ls_layout.setSpacing(10)

        cmb_lobe = self._combo_with_placeholder("Select from list", list(LOBE_LIST))
        cmb_stage = self._combo_with_placeholder("Select from list", list(STAGE_LIST))

        ls_layout.addWidget(QLabel("LOBE"))
        ls_layout.addWidget(cmb_lobe, 1)
        ls_layout.addWidget(QLabel("STAGE"))
        ls_layout.addWidget(cmb_stage, 1)

        edt_ibs_gauge = QLineEdit()
        edt_ibs_gauge.setReadOnly(True)
        edt_ibs_gauge.setPlaceholderText("Click to open stabilizer converter")
        edt_ibs_gauge.setCursor(Qt.PointingHandCursor)
        edt_ibs_gauge.mousePressEvent = (
            lambda event, le=edt_ibs_gauge: self._open_stabilizer_converter(le, event)
        )  # type: ignore[assignment]

        form.addRow("BRAND", cmb_brand)
        form.addRow("SIZE", cmb_size)
        form.addRow("SLEEVE STB GAUGE (INCH)", edt_sleeve_gauge)
        form.addRow("BEND ANGLE (DEG)", cmb_bend_angle)
        form.addRow("LOBE-STAGE", ls_widget)
        form.addRow("IBS GAUGE (INCH)", edt_ibs_gauge)

        self._mud_motor_widgets[motor_index] = {
            "cmb_brand": cmb_brand,
            "cmb_size": cmb_size,
            "edt_sleeve": edt_sleeve_gauge,
            "cmb_bend": cmb_bend_angle,
            "cmb_lobe": cmb_lobe,
            "cmb_stage": cmb_stage,
            "edt_ibs": edt_ibs_gauge,
        }

        return box

    def _build_bit_group(self) -> QGroupBox:
        box = self._group_box("BIT")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        layout.addWidget(self._build_bit_subgroup(1, "BIT - 1"), 1)
        layout.addWidget(self._build_bit_subgroup(2, "BIT - 2"), 1)

        return box

    def _build_bit_subgroup(self, bit_index: int, title: str) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        brand_kind = QWidget()
        hk = QHBoxLayout(brand_kind)
        hk.setContentsMargins(0, 0, 0, 0)
        hk.setSpacing(10)

        cmb_brand = self._combo_with_placeholder("Select from list", list(BIT_BRANDS))
        cmb_kind = self._combo_with_placeholder("Select from list", list(BIT_KINDS))

        hk.addWidget(cmb_brand, 2)
        hk.addWidget(cmb_kind, 1)

        edt_type = QLineEdit()
        edt_type.setPlaceholderText("e.g., TKC66, TX36275")

        edt_iadc = QLineEdit()
        edt_iadc.setPlaceholderText("e.g., 517, 537G, M423")

        edt_serial = QLineEdit()
        edt_serial.setPlaceholderText("e.g., F310849, 5360463")

        nt_widget = QWidget()
        nt_layout = QHBoxLayout(nt_widget)
        nt_layout.setContentsMargins(0, 0, 0, 0)
        nt_layout.setSpacing(10)

        edt_nozzle_summary = QLineEdit()
        edt_nozzle_summary.setReadOnly(True)
        edt_nozzle_summary.setPlaceholderText("Click to select nozzles")
        edt_nozzle_summary.setCursor(Qt.PointingHandCursor)
        edt_nozzle_summary.mousePressEvent = (
            lambda event, idx=bit_index: self._on_nozzle_clicked(idx, event)
        )  # type: ignore[assignment]

        edt_tfa_in2 = QLineEdit()
        edt_tfa_in2.setReadOnly(True)
        edt_tfa_in2.setPlaceholderText("Auto")

        nt_layout.addWidget(edt_nozzle_summary, 2)
        nt_layout.addWidget(QLabel("TFA (IN^2)"))
        nt_layout.addWidget(edt_tfa_in2, 1)

        form.addRow("BRAND / BIT TYPE", brand_kind)
        form.addRow("TYPE", edt_type)
        form.addRow("IADC", edt_iadc)
        form.addRow("SERIAL", edt_serial)
        form.addRow("NOZZLE/TFA", nt_widget)

        self._bit_widgets[bit_index] = {
            "cmb_brand": cmb_brand,
            "cmb_kind": cmb_kind,
            "edt_type": edt_type,
            "edt_iadc": edt_iadc,
            "edt_serial": edt_serial,
            "edt_nozzle_summary": edt_nozzle_summary,
            "edt_tfa_in2": edt_tfa_in2,
        }

        return box

    def _build_personnel_group(self) -> QGroupBox:
        box = self._group_box("PERSONNEL")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        form.addRow("DAY DD", self._build_personnel_row(self.edt_day_dd))
        form.addRow("NIGHT DD", self._build_personnel_row(self.edt_night_dd))
        form.addRow("DAY MWD", self._build_personnel_row(self.edt_day_mwd))
        form.addRow("NIGHT MWD", self._build_personnel_row(self.edt_night_mwd))

        return box

    def _build_personnel_row(self, bucket: List[QLineEdit]) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        placeholders = ["First Personnel", "Second Personnel", "Third Personnel"]
        for placeholder in placeholders:
            le = QLineEdit()
            le.setPlaceholderText(placeholder)
            bucket.append(le)
            layout.addWidget(le, 1)

        return widget

    def _build_info_group(self) -> QGroupBox:
        box = self._group_box("INFO")
        form = QFormLayout(box)
        form.setContentsMargins(12, 12, 12, 12)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.edt_info_casing_shoe = DecimalLineEdit()
        self.edt_info_section_tvd = DecimalLineEdit()
        self.edt_info_section_md = DecimalLineEdit()

        self.cmb_info_mud_type = QComboBox()
        self.cmb_info_mud_type.setEditable(False)
        self.cmb_info_mud_type.addItem("Select from list")
        self.cmb_info_mud_type.model().item(0).setEnabled(False)
        self.cmb_info_mud_type.setCurrentIndex(0)
        self.cmb_info_mud_type.addItems(
            [
                "AIR",
                "AERATED",
                "BENTONITE",
                "CaCl2 POLYMER",
                "FOAM",
                "GEL",
                "HIGH-TEMPERATURE GEOTHERMAL",
                "KCL-POLYMER",
                "LIGNOSULFONATE",
                "NaCl POLYMER",
                "OIL BASE",
                "PHPA",
                "POLYMER",
                "SPUD",
                "SYNTHETIC BASE",
            ]
        )

        form.addRow("CASING SHOE (METER)", self.edt_info_casing_shoe)
        form.addRow("CASING OD/ID (INCH)", self._build_casing_od_id_widget())
        form.addRow("SECTION TVD (METER)", self.edt_info_section_tvd)
        form.addRow("SECTION MD (METER)", self.edt_info_section_md)
        form.addRow("MUD TYPE", self.cmb_info_mud_type)

        return box

    def _build_casing_od_id_widget(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.cmb_info_casing_od = QComboBox()
        self.cmb_info_casing_od.setEditable(False)
        self.cmb_info_casing_od.addItem(" Select OD from list")
        self.cmb_info_casing_od.model().item(0).setEnabled(False)
        self.cmb_info_casing_od.setCurrentIndex(0)
        self.cmb_info_casing_od.addItems(list(CASING_OD_OPTIONS))

        self.cmb_info_casing_id = QComboBox()
        self.cmb_info_casing_id.setEditable(False)
        self.cmb_info_casing_id.addItem(" Select ID from list")
        self.cmb_info_casing_id.model().item(0).setEnabled(False)
        self.cmb_info_casing_id.setCurrentIndex(0)

        self.cmb_info_casing_od.currentTextChanged.connect(self._on_casing_od_changed)

        layout.addWidget(QLabel("OD"))
        layout.addWidget(self.cmb_info_casing_od, 1)
        layout.addWidget(QLabel("ID"))
        layout.addWidget(self.cmb_info_casing_id, 1)
        return widget

    def _on_casing_od_changed(self, od_value: str) -> None:
        if self.cmb_info_casing_id is None:
            return

        prev = self.cmb_info_casing_id.currentText()
        self.cmb_info_casing_id.blockSignals(True)
        self.cmb_info_casing_id.clear()
        self.cmb_info_casing_id.addItem(" Select ID from list")
        self.cmb_info_casing_id.model().item(0).setEnabled(False)
        for item in CASING_ID_BY_OD.get(od_value, ()):
            self.cmb_info_casing_id.addItem(item)
        self.cmb_info_casing_id.setCurrentIndex(0)
        if prev in CASING_ID_BY_OD.get(od_value, ()):
            idx = self.cmb_info_casing_id.findText(prev)
            if idx >= 0:
                self.cmb_info_casing_id.setCurrentIndex(idx)
        self.cmb_info_casing_id.blockSignals(False)

        self._sync_open_hole_casing_shoe()

    def _sync_open_hole_casing_shoe(self) -> None:
        if not self.cmb_info_casing_od or not self.cmb_info_casing_id or not self.edt_info_casing_shoe:
            return
        od = self.cmb_info_casing_od.currentText().strip()
        cid = self.cmb_info_casing_id.currentText().strip()
        if od == "OPEN HOLE" and cid == "OPEN HOLE":
            self.edt_info_casing_shoe.setText("0")

    def _build_time_analysis_group(self) -> QGroupBox:
        box = self._group_box("TIME ANALYSIS")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        header_labels = ["", "RUN - 1", "RUN - 2", "RUN - 3", "SECTION TOTAL"]
        for col, text in enumerate(header_labels):
            lbl = QLabel(text)
            if col > 0:
                font = lbl.font()
                font.setBold(True)
                lbl.setFont(font)
                lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, 0, col)

        row_idx = 1
        rows = [
            ("STANDBY TIME (HRS)", "ta_standby_time_hrs", "editable", "e.g., 0, 12, 48, 107.85"),
            ("R/U TIME (HRS)", "ta_ru_time_hrs", "editable", "e.g., 0, 4.5, 7, 9.25"),
            ("TRIPPING TIME (HRS)", "ta_tripping_time_hrs", "editable", "e.g., 0, 4.5, 7, 9.25"),
            ("CIRCULATION TIME (HRS)", "ta_circulation_time_hrs", "editable", "e.g., 0, 88, 93.75, 102.6"),
            ("ROTARY TIME (HRS)", "ta_rotary_time_hrs", "editable", "e.g., 0, 189, 205.24, 246.7"),
            ("ROTARY (METER)", "ta_rotary_meters", "editable", "e.g., 0, 634.78, 725, 1204.6"),
            ("SLIDING TIME (HRS)", "ta_sliding_time_hrs", "editable", "e.g., 0, 25, 54.6"),
            ("SLIDING (METER)", "ta_sliding_meters", "editable", "e.g., 0, 124, 167.5"),
            ("TOTAL DRILLING TIME (HRS)", "ta_total_drilling_time_hrs", "auto", ""),
            ("TOTAL DRILLING (METER)", "ta_total_drilling_meters", "auto", ""),
            ("NPT DUE TO RIG (HRS)", "ta_npt_due_to_rig_hrs", "editable", "e.g., 0, 16, 27.8"),
            ("NPT DUE TO MOTOR (HRS)", "ta_npt_due_to_motor_hrs", "editable", "e.g., 0, 16, 27.8"),
            ("NPT DUE TO MWD (HRS)", "ta_npt_due_to_mwd_hrs", "editable", "e.g., 0, 16, 27.8"),
            ("BRT (HRS)", "ta_brt_hrs", "editable", "e.g., 0, 180, 212.45, 370.5"),
            ("%EFF DRILLING", "ta_eff_drilling_pct", "auto", ""),
        ]

        for label, key, kind, placeholder in rows:
            grid.addWidget(QLabel(label), row_idx, 0)
            if kind == "editable":
                self._ta_inputs[key] = {}
                for run in (1, 2, 3):
                    edt = DecimalLineEdit()
                    edt.setPlaceholderText(placeholder)
                    self._ta_inputs[key][run] = edt
                    grid.addWidget(edt, row_idx, run)

                total = QLineEdit()
                total.setReadOnly(True)
                total.setPlaceholderText("Auto")
                self._ta_totals[key] = total
                grid.addWidget(total, row_idx, 4)
            else:
                self._ta_auto_runs[key] = {}
                for run in (1, 2, 3):
                    edt = QLineEdit()
                    edt.setReadOnly(True)
                    edt.setPlaceholderText("Auto")
                    self._ta_auto_runs[key][run] = edt
                    grid.addWidget(edt, row_idx, run)

                total = QLineEdit()
                total.setReadOnly(True)
                total.setPlaceholderText("Auto")
                self._ta_auto_totals[key] = total
                grid.addWidget(total, row_idx, 4)
            row_idx += 1

        layout.addLayout(grid)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft)

        self.dp_call_out_date = DatePickerLine()
        self.dp_call_out_date.set_placeholder(
            "If the prev. sec. isn't released, select the day after the last invoice date."
        )

        self.edt_crew_mob_time = TimeHHMMEdit()
        self.edt_crew_mob_time.setPlaceholderText("e.g., 16:30, 24:00, 00:00")

        self.dp_release_date = DatePickerLine()
        self.dp_release_date.set_placeholder("Important: If not released, choose the latest invoice date")

        self.edt_release_time = TimeHHMMEdit()
        self.edt_release_time.setPlaceholderText("Important: If not released, use 00:00 as the time value.")

        self.edt_mob_to_release = QLineEdit()
        self.edt_mob_to_release.setReadOnly(True)
        self.edt_mob_to_release.setPlaceholderText("Auto")

        form.addRow("CALL OUT DATE", self.dp_call_out_date)
        form.addRow("CREW MOB TIME", self.edt_crew_mob_time)
        form.addRow("RELEASE DATE", self.dp_release_date)
        form.addRow("RELEASE TIME", self.edt_release_time)
        form.addRow("MOB TO RELEASE (HRS)", self.edt_mob_to_release)

        layout.addLayout(form)

        return box

    # ------------------------------------------------------------------
    # Nozzles dialog
    # ------------------------------------------------------------------
    def _on_nozzle_clicked(self, bit_index: int, _event) -> None:
        current = self._bit_nozzles.get(bit_index, [])
        dlg = NozzleDialog(initial_nozzles=current, parent=self)
        if dlg.exec() == QDialog.Accepted:
            res = dlg.get_result()
            if res is not None:
                self._bit_nozzles[bit_index] = list(res.nozzles)
                self._sync_nozzle_fields(bit_index)
                self._recompute_derived()

    def _open_stabilizer_converter(self, target: QLineEdit, _event) -> None:
        dlg = StabilizerGaugeConverterDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            value = dlg.result_text()
            if value is not None:
                target.setText(value)

    def _sync_nozzle_fields(self, bit_index: int) -> None:
        widgets = self._bit_widgets.get(bit_index)
        if not widgets:
            return
        edt_nozzle_summary = widgets.get("edt_nozzle_summary")
        edt_tfa_in2 = widgets.get("edt_tfa_in2")
        if not isinstance(edt_nozzle_summary, QLineEdit) or not isinstance(edt_tfa_in2, QLineEdit):
            return

        nozzles = self._bit_nozzles.get(bit_index, [])
        if not nozzles:
            edt_nozzle_summary.setText("")
            edt_tfa_in2.setText("")
            return

        edt_nozzle_summary.setText(nozzle_summary(nozzles))
        try:
            tfa = tfa_from_nozzles(nozzles)
            edt_tfa_in2.setText(f"{tfa:.4f}")
        except Exception:
            edt_tfa_in2.setText("")

    # ------------------------------------------------------------------
    # Live calculations
    # ------------------------------------------------------------------
    def _wire_live_calcs(self) -> None:
        # recompute totals & derived fields when any relevant input changes
        def hook(widget, signal_name: str) -> None:
            sig = getattr(widget, signal_name, None)
            if sig is not None:
                sig.connect(self._recompute_derived)

        # decimal edits (runs)
        for fields in self._ta_inputs.values():
            for w in fields.values():
                hook(w, "normalized")

        # time edits
        for w in (self.edt_crew_mob_time, self.edt_release_time):
            if w is not None:
                hook(w, "normalized")

        # date pickers
        for w in (self.dp_call_out_date, self.dp_release_date):
            if w is not None:
                hook(w, "date_changed")

    def _wire_text_normalization(self) -> None:
        def canonical_text_live(raw: str) -> str:
            canon = canonical_text(raw)
            if raw and raw[-1].isspace() and canon:
                return canon + " "
            return canon

        def normalize_line_edit(le: Optional[QLineEdit]) -> None:
            if le is None or le.isReadOnly():
                return

            def _on_text_edited(_text: str) -> None:
                canon = canonical_text_live(le.text())
                if canon != le.text():
                    cursor = le.cursorPosition()
                    le.blockSignals(True)
                    le.setText(canon)
                    le.setCursorPosition(min(cursor, len(canon)))
                    le.blockSignals(False)

            le.textEdited.connect(_on_text_edited)

        for bit_index in (1, 2):
            widgets = self._bit_widgets.get(bit_index, {})
            for key in ("edt_type", "edt_iadc", "edt_serial"):
                le = widgets.get(key)
                if isinstance(le, QLineEdit):
                    normalize_line_edit(le)

        for le in (
            self.edt_info_section_tvd,
            self.edt_info_section_md,
        ):
            normalize_line_edit(le)

        for le in (
            self.edt_day_dd
            + self.edt_night_dd
            + self.edt_day_mwd
            + self.edt_night_mwd
        ):
            normalize_line_edit(le)

    def _recompute_derived(self) -> None:
        def run_value(key: str, run: int) -> Optional[float]:
            field = self._ta_inputs.get(key, {}).get(run)
            return field.value_or_none() if field else None

        def set_run_auto(key: str, run: int, value: Optional[float]) -> None:
            widget = self._ta_auto_runs.get(key, {}).get(run)
            if not widget:
                return
            widget.setText(f"{value:.2f}" if value is not None else "")

        def set_total(key: str, value: Optional[float]) -> None:
            widget = self._ta_totals.get(key) or self._ta_auto_totals.get(key)
            if not widget:
                return
            widget.setText(f"{value:.2f}" if value is not None else "")

        run_totals_time: Dict[int, Optional[float]] = {}
        run_totals_m: Dict[int, Optional[float]] = {}

        for run in (1, 2, 3):
            rt = run_value("ta_rotary_time_hrs", run)
            st = run_value("ta_sliding_time_hrs", run)
            if rt is not None and st is not None:
                run_totals_time[run] = total_drilling_time_hours(rt, st)
            else:
                run_totals_time[run] = None
            set_run_auto("ta_total_drilling_time_hrs", run, run_totals_time[run])

            rm = run_value("ta_rotary_meters", run)
            sm = run_value("ta_sliding_meters", run)
            if rm is not None and sm is not None:
                run_totals_m[run] = total_drilling_meters(rm, sm)
            else:
                run_totals_m[run] = None
            set_run_auto("ta_total_drilling_meters", run, run_totals_m[run])

        total_time = sum(v for v in run_totals_time.values() if v is not None) if any(
            v is not None for v in run_totals_time.values()
        ) else None
        total_m = sum(v for v in run_totals_m.values() if v is not None) if any(
            v is not None for v in run_totals_m.values()
        ) else None
        set_total("ta_total_drilling_time_hrs", total_time)
        set_total("ta_total_drilling_meters", total_m)

        # Section totals for editable rows
        for key, runs in self._ta_inputs.items():
            values = [runs[r].value_or_none() for r in (1, 2, 3) if runs.get(r)]
            if any(v is not None for v in values):
                total = sum(v for v in values if v is not None)
            else:
                total = None
            set_total(key, total)

        # %EFF DRILLING (per run + total)
        for run in (1, 2, 3):
            brt = run_value("ta_brt_hrs", run)
            dt = run_totals_time.get(run)
            if dt is not None and brt is not None:
                if brt == 0 and dt == 0:
                    set_run_auto("ta_eff_drilling_pct", run, 0.0)
                elif brt > 0:
                    set_run_auto("ta_eff_drilling_pct", run, eff_drilling_percent(dt, brt))
                else:
                    set_run_auto("ta_eff_drilling_pct", run, None)
            else:
                set_run_auto("ta_eff_drilling_pct", run, None)

        brt_total = sum(
            v for v in [run_value("ta_brt_hrs", 1), run_value("ta_brt_hrs", 2), run_value("ta_brt_hrs", 3)]
            if v is not None
        )
        if total_time is not None:
            if brt_total == 0 and total_time == 0:
                set_total("ta_eff_drilling_pct", 0.0)
            elif brt_total > 0:
                set_total("ta_eff_drilling_pct", eff_drilling_percent(total_time, brt_total))
            else:
                set_total("ta_eff_drilling_pct", None)
        else:
            set_total("ta_eff_drilling_pct", None)

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
        for motor_index in (1, 2):
            widgets = self._mud_motor_widgets.get(motor_index, {})
            cmb_brand = widgets.get("cmb_brand")
            cmb_size = widgets.get("cmb_size")
            edt_sleeve = widgets.get("edt_sleeve")
            cmb_bend = widgets.get("cmb_bend")
            cmb_lobe = widgets.get("cmb_lobe")
            cmb_stage = widgets.get("cmb_stage")
            edt_ibs = widgets.get("edt_ibs")

            data[f"mud_motor{motor_index}_brand"] = combo_value(cmb_brand) if isinstance(cmb_brand, QComboBox) else ""
            data[f"mud_motor{motor_index}_size"] = combo_value(cmb_size) if isinstance(cmb_size, QComboBox) else ""
            sleeve_txt = edt_sleeve.text().strip() if isinstance(edt_sleeve, QLineEdit) else ""
            sleeve_none = 1 if sleeve_txt.upper() == "NONE" else 0
            data[f"mud_motor{motor_index}_sleeve_stb_gauge_in"] = "" if sleeve_none else sleeve_txt
            data[f"mud_motor{motor_index}_sleeve_none"] = sleeve_none
            data[f"mud_motor{motor_index}_bend_angle_deg"] = combo_value(cmb_bend) if isinstance(cmb_bend, QComboBox) else ""
            data[f"mud_motor{motor_index}_lobe"] = combo_value(cmb_lobe) if isinstance(cmb_lobe, QComboBox) else ""
            data[f"mud_motor{motor_index}_stage"] = combo_value(cmb_stage) if isinstance(cmb_stage, QComboBox) else ""
            ibs_txt = edt_ibs.text().strip() if isinstance(edt_ibs, QLineEdit) else ""
            ibs_none = 1 if ibs_txt.upper() == "NONE" else 0
            data[f"mud_motor{motor_index}_ibs_gauge_in"] = "" if ibs_none else ibs_txt
            data[f"mud_motor{motor_index}_ibs_none"] = ibs_none

        # BIT 1 / BIT 2
        for bit_index in (1, 2):
            widgets = self._bit_widgets.get(bit_index, {})
            cmb_brand = widgets.get("cmb_brand")
            cmb_kind = widgets.get("cmb_kind")
            edt_type = widgets.get("edt_type")
            edt_iadc = widgets.get("edt_iadc")
            edt_serial = widgets.get("edt_serial")

            data[f"bit{bit_index}_brand"] = combo_value(cmb_brand) if isinstance(cmb_brand, QComboBox) else ""
            data[f"bit{bit_index}_kind"] = combo_value(cmb_kind) if isinstance(cmb_kind, QComboBox) else ""
            data[f"bit{bit_index}_type"] = (
                edt_type.text().strip() if isinstance(edt_type, QLineEdit) else ""
            )
            data[f"bit{bit_index}_iadc"] = (
                edt_iadc.text().strip() if isinstance(edt_iadc, QLineEdit) else ""
            )
            data[f"bit{bit_index}_serial"] = (
                edt_serial.text().strip() if isinstance(edt_serial, QLineEdit) else ""
            )
            data[f"bit{bit_index}_nozzles"] = list(self._bit_nozzles.get(bit_index, []))

        # PERSONNEL
        def collect_personnel(prefix: str, items: List[QLineEdit]) -> None:
            for idx, le in enumerate(items, start=1):
                key = f"{prefix}_{idx}"
                data[key] = le.text().strip()

        collect_personnel("personnel_day_dd", self.edt_day_dd)
        collect_personnel("personnel_night_dd", self.edt_night_dd)
        collect_personnel("personnel_day_mwd", self.edt_day_mwd)
        collect_personnel("personnel_night_mwd", self.edt_night_mwd)

        # INFO
        data["info_casing_shoe"] = self.edt_info_casing_shoe.text().strip() if self.edt_info_casing_shoe else ""
        if self.cmb_info_casing_od:
            od = self.cmb_info_casing_od.currentText().strip()
            if od in {"Select OD from list", "Select from list"}:
                od = ""
        else:
            od = ""
        if self.cmb_info_casing_id:
            cid = self.cmb_info_casing_id.currentText().strip()
            if cid in {"Select ID from list", "Select from list"}:
                cid = ""
        else:
            cid = ""
        if od == "OPEN HOLE" and cid == "OPEN HOLE" and self.edt_info_casing_shoe:
            self.edt_info_casing_shoe.setText("0")
            data["info_casing_shoe"] = "0"
        data["info_casing_od"] = od
        data["info_casing_id"] = cid
        data["info_section_tvd"] = self.edt_info_section_tvd.text().strip() if self.edt_info_section_tvd else ""
        data["info_section_md"] = self.edt_info_section_md.text().strip() if self.edt_info_section_md else ""
        if self.cmb_info_mud_type:
            mud_type = self.cmb_info_mud_type.currentText().strip()
            if mud_type == "Select from list":
                mud_type = ""
        else:
            mud_type = ""
        data["info_mud_type"] = mud_type

        # TIME ANALYSIS (rules keys)
        data["ta_call_out_date"] = self.dp_call_out_date.date_value() if self.dp_call_out_date else None
        data["ta_crew_mob_time"] = self.edt_crew_mob_time.text().strip() if self.edt_crew_mob_time else ""

        for key, runs in self._ta_inputs.items():
            for run, widget in runs.items():
                data[f"{key}_run{run}"] = widget.text().strip()

        data["ta_release_date"] = self.dp_release_date.date_value() if self.dp_release_date else None
        data["ta_release_time"] = self.edt_release_time.text().strip() if self.edt_release_time else ""

        data["dd_well_type"] = self._get_dd_well_type()

        return data

    def _get_dd_well_type(self) -> str:
        try:
            row = identity_repo.get_identity(self._well_id)
        except Exception:
            return ""
        if not row:
            return ""
        return str(row.get("dd_well_type") or "").strip()

    def _apply_computed(self, computed: Dict[str, Any]) -> None:
        # times
        if self.edt_crew_mob_time and computed.get("ta_crew_mob_time_norm"):
            self.edt_crew_mob_time.setText(str(computed["ta_crew_mob_time_norm"]))
        if self.edt_release_time and computed.get("ta_release_time_norm"):
            self.edt_release_time.setText(str(computed["ta_release_time_norm"]))

        # totals (run + section)
        for run in (1, 2, 3):
            tdt_key = f"ta_total_drilling_time_hrs_run{run}"
            tdm_key = f"ta_total_drilling_meters_run{run}"
            eff_key = f"ta_eff_drilling_pct_run{run}"
            if tdt_key in computed:
                widget = self._ta_auto_runs.get("ta_total_drilling_time_hrs", {}).get(run)
                if widget:
                    v = computed.get(tdt_key)
                    widget.setText(f"{float(v):.2f}" if v is not None else "")
            if tdm_key in computed:
                widget = self._ta_auto_runs.get("ta_total_drilling_meters", {}).get(run)
                if widget:
                    v = computed.get(tdm_key)
                    widget.setText(f"{float(v):.2f}" if v is not None else "")
            if eff_key in computed:
                widget = self._ta_auto_runs.get("ta_eff_drilling_pct", {}).get(run)
                if widget:
                    v = computed.get(eff_key)
                    widget.setText(f"{float(v):.2f}" if v is not None else "")

        total_time = computed.get("ta_total_drilling_time_hrs_total")
        total_m = computed.get("ta_total_drilling_meters_total")
        total_eff = computed.get("ta_eff_drilling_pct_total")
        if "ta_total_drilling_time_hrs" in self._ta_auto_totals:
            widget = self._ta_auto_totals.get("ta_total_drilling_time_hrs")
            if widget:
                widget.setText(f"{float(total_time):.2f}" if total_time is not None else "")
        if "ta_total_drilling_meters" in self._ta_auto_totals:
            widget = self._ta_auto_totals.get("ta_total_drilling_meters")
            if widget:
                widget.setText(f"{float(total_m):.2f}" if total_m is not None else "")
        if "ta_eff_drilling_pct" in self._ta_auto_totals:
            widget = self._ta_auto_totals.get("ta_eff_drilling_pct")
            if widget:
                widget.setText(f"{float(total_eff):.2f}" if total_eff is not None else "")

        # mob to release (hard required)
        if self.edt_mob_to_release:
            v = computed.get("ta_mob_to_release_hrs")
            self.edt_mob_to_release.setText(f"{float(v):.2f}" if v is not None else "")

        # nozzle summary / tfa
        for bit_index in (1, 2):
            key = f"bit{bit_index}_nozzles"
            if computed.get(key) is not None:
                self._bit_nozzles[bit_index] = list(computed[key])
                self._sync_nozzle_fields(bit_index)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_validate_clicked(self) -> None:
        self._validate_section(show_success=True)

    def _on_save_clicked(self) -> None:
        result = self._validate_section(show_success=False)
        if not result.ok:
            return

        data = self._collect_section_data()
        try:
            hole_section_data_repo.save_hole_section(self._well_id, self._hole_node_key, data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Hole Section.\n\nDetails:\n{e!r}")
            return

        QMessageBox.information(self, "Information", "Hole Section saved.")

    def _validate_section(self, *, show_success: bool):
        data = self._collect_section_data()
        result = validate_hole_section(data)

        # Always apply computed values (even if errors exist) to help user see what's wrong.
        self._apply_computed(result.computed)

        if result.ok:
            if show_success:
                QMessageBox.information(self, "Information", "Hole Section validation passed. The form is ready to be saved.")
            return result

        msg = "Please fix the following issues:\n\n" + "\n".join(f"- {e}" for e in result.errors)
        QMessageBox.warning(self, "Validation Error", msg)
        return result

    def _parse_date(self, value: object) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        s = str(value).strip()
        if not s:
            return None
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            pass
        try:
            return datetime.strptime(s, "%d.%m.%Y").date()
        except Exception:
            return None

    def _set_combo_value(self, combo: Optional[QComboBox], value: object) -> None:
        if combo is None:
            return
        s = str(value).strip() if value is not None else ""
        if not s:
            return
        idx = combo.findText(s)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if combo.isEditable():
            combo.setEditText(s)

    def _set_line_text(self, widget: Optional[QLineEdit], value: object) -> None:
        if widget is None:
            return
        s = "" if value is None else str(value)
        if s == "":
            return
        widget.setText(s)

    def _set_gauge_text(self, widget: Optional[QLineEdit], value: object, none_flag: object) -> None:
        if widget is None:
            return
        if none_flag in (1, "1", True):
            widget.setText("NONE")
            return
        if value is None:
            return
        widget.setText(str(value))

    def _set_decimal_text(self, widget: Optional[QLineEdit], value: object) -> None:
        if widget is None:
            return
        if value is None:
            return
        widget.setText(str(value))

    def _load_from_db(self) -> None:
        row = hole_section_data_repo.get_hole_section(self._well_id, self._hole_node_key)
        if not row:
            return

        # MUD MOTOR
        mm1 = {
            "brand": row.get("mud_motor1_brand") or row.get("mud_motor_brand"),
            "size": row.get("mud_motor1_size") or row.get("mud_motor_size"),
            "sleeve": row.get("mud_motor1_sleeve_stb_gauge_in") or row.get("mud_motor_sleeve_stb_gauge_in"),
            "sleeve_none": row.get("mud_motor1_sleeve_none"),
            "bend": row.get("mud_motor1_bend_angle_deg") or row.get("mud_motor_bend_angle_deg"),
            "lobe": row.get("mud_motor1_lobe") or row.get("mud_motor_lobe"),
            "stage": row.get("mud_motor1_stage") or row.get("mud_motor_stage"),
            "ibs": row.get("mud_motor1_ibs_gauge_in") or row.get("mud_motor_ibs_gauge_in"),
            "ibs_none": row.get("mud_motor1_ibs_none"),
        }
        mm2 = {
            "brand": row.get("mud_motor2_brand"),
            "size": row.get("mud_motor2_size"),
            "sleeve": row.get("mud_motor2_sleeve_stb_gauge_in"),
            "sleeve_none": row.get("mud_motor2_sleeve_none"),
            "bend": row.get("mud_motor2_bend_angle_deg"),
            "lobe": row.get("mud_motor2_lobe"),
            "stage": row.get("mud_motor2_stage"),
            "ibs": row.get("mud_motor2_ibs_gauge_in"),
            "ibs_none": row.get("mud_motor2_ibs_none"),
        }
        for motor_index, values in ((1, mm1), (2, mm2)):
            widgets = self._mud_motor_widgets.get(motor_index, {})
            self._set_combo_value(widgets.get("cmb_brand"), values["brand"])
            self._set_combo_value(widgets.get("cmb_size"), values["size"])
            self._set_gauge_text(widgets.get("edt_sleeve"), values["sleeve"], values.get("sleeve_none"))
            self._set_combo_value(widgets.get("cmb_bend"), values["bend"])
            self._set_combo_value(widgets.get("cmb_lobe"), values["lobe"])
            self._set_combo_value(widgets.get("cmb_stage"), values["stage"])
            self._set_gauge_text(widgets.get("edt_ibs"), values["ibs"], values.get("ibs_none"))

        # BIT
        bit1_brand = row.get("bit1_brand") or row.get("bit_brand")
        bit1_kind = row.get("bit1_kind") or row.get("bit_kind")
        bit1_type = row.get("bit1_type") or row.get("bit_type")
        bit1_iadc = row.get("bit1_iadc") or row.get("bit_iadc")
        bit1_serial = row.get("bit1_serial") or row.get("bit_serial")

        for bit_index, values in (
            (1, (bit1_brand, bit1_kind, bit1_type, bit1_iadc, bit1_serial)),
            (2, (row.get("bit2_brand"), row.get("bit2_kind"), row.get("bit2_type"), row.get("bit2_iadc"), row.get("bit2_serial"))),
        ):
            widgets = self._bit_widgets.get(bit_index, {})
            self._set_combo_value(widgets.get("cmb_brand"), values[0])
            self._set_combo_value(widgets.get("cmb_kind"), values[1])
            self._set_line_text(widgets.get("edt_type"), values[2])
            self._set_line_text(widgets.get("edt_iadc"), values[3])
            self._set_line_text(widgets.get("edt_serial"), values[4])

        # PERSONNEL
        def load_personnel(prefix: str, items: List[QLineEdit]) -> None:
            for idx, le in enumerate(items, start=1):
                key = f"{prefix}_{idx}"
                self._set_line_text(le, row.get(key))

        load_personnel("personnel_day_dd", self.edt_day_dd)
        load_personnel("personnel_night_dd", self.edt_night_dd)
        load_personnel("personnel_day_mwd", self.edt_day_mwd)
        load_personnel("personnel_night_mwd", self.edt_night_mwd)

        # INFO
        self._set_decimal_text(self.edt_info_casing_shoe, row.get("info_casing_shoe"))
        od_val = row.get("info_casing_od")
        id_val = row.get("info_casing_id")
        if (not od_val or not id_val) and row.get("info_casing_od_id"):
            raw = str(row.get("info_casing_od_id") or "")
            if "/" in raw:
                parts = [p.strip() for p in raw.split("/", 1)]
                if len(parts) == 2:
                    od_val = od_val or parts[0]
                    id_val = id_val or parts[1]
        if self.cmb_info_casing_od:
            self._set_combo_value(self.cmb_info_casing_od, od_val)
        if self.cmb_info_casing_id:
            self._on_casing_od_changed(str(od_val or ""))
            self._set_combo_value(self.cmb_info_casing_id, id_val)
        self._set_decimal_text(self.edt_info_section_tvd, row.get("info_section_tvd"))
        self._set_decimal_text(self.edt_info_section_md, row.get("info_section_md"))
        if self.cmb_info_mud_type:
            self._set_combo_value(self.cmb_info_mud_type, row.get("info_mud_type"))

        # TIME ANALYSIS
        if self.dp_call_out_date:
            self.dp_call_out_date.set_date(self._parse_date(row.get("ta_call_out_date")))
        if self.edt_crew_mob_time:
            self.edt_crew_mob_time.setText(str(row.get("ta_crew_mob_time") or ""))

        legacy_map = {
            "ta_standby_time_hrs": "ta_standby_time_hrs_run1",
            "ta_ru_time_hrs": "ta_ru_time_hrs_run1",
            "ta_tripping_time_hrs": "ta_tripping_time_hrs_run1",
            "ta_circulation_time_hrs": "ta_circulation_time_hrs_run1",
            "ta_rotary_time_hrs": "ta_rotary_time_hrs_run1",
            "ta_rotary_meters": "ta_rotary_meters_run1",
            "ta_sliding_time_hrs": "ta_sliding_time_hrs_run1",
            "ta_sliding_meters": "ta_sliding_meters_run1",
            "ta_npt_due_to_rig_hrs": "ta_npt_due_to_rig_hrs_run1",
            "ta_npt_due_to_motor_hrs": "ta_npt_due_to_motor_hrs_run1",
            "ta_npt_due_to_mwd_hrs": "ta_npt_due_to_mwd_hrs_run1",
            "ta_total_brt_hrs": "ta_brt_hrs_run1",
        }
        for legacy_key, run1_key in legacy_map.items():
            if not row.get(run1_key) and row.get(legacy_key) is not None:
                row[run1_key] = row.get(legacy_key)

        for key, runs in self._ta_inputs.items():
            for run, widget in runs.items():
                value = row.get(f"{key}_run{run}")
                self._set_decimal_text(widget, value)

        if self.dp_release_date:
            self.dp_release_date.set_date(self._parse_date(row.get("ta_release_date")))
        if self.edt_release_time:
            self.edt_release_time.setText(str(row.get("ta_release_time") or ""))

        self._recompute_derived()

        # TICKET ROWS
        for t in row.get("tickets", []):
            line_no = int(t.get("line_no", 0))
            if line_no <= 0:
                continue
            date_key = f"ticket_date_{line_no}"
            price_key = f"ticket_price_usd_{line_no}"
            if date_key in self._ticket_dates:
                self._ticket_dates[date_key].set_date(self._parse_date(t.get("ticket_date")))
            if price_key in self._ticket_prices and t.get("ticket_price_usd") is not None:
                try:
                    self._ticket_prices[price_key].setValue(float(t.get("ticket_price_usd")))
                except Exception:
                    pass

        # NOZZLES
        bit1_nozzles = row.get("bit1_nozzles", [])
        bit2_nozzles = row.get("bit2_nozzles", [])
        if bit1_nozzles:
            self._bit_nozzles[1] = list(bit1_nozzles)
            self._sync_nozzle_fields(1)
        if bit2_nozzles:
            self._bit_nozzles[2] = list(bit2_nozzles)
            self._sync_nozzle_fields(2)

        self._recompute_derived()
