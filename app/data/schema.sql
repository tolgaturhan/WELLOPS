-- ============================
-- TPIC WellOps Database Schema
-- ============================

-- ----------------------------
-- Wells (Core Entity)
-- ----------------------------
CREATE TABLE IF NOT EXISTS wells (
  well_id TEXT PRIMARY KEY,

  -- identity
  well_name TEXT NOT NULL,

  -- lifecycle
  status TEXT NOT NULL,                -- DRAFT | ACTIVE | ARCHIVED
  step1_done INTEGER NOT NULL DEFAULT 0,
  step2_done INTEGER NOT NULL DEFAULT 0,
  step3_done INTEGER NOT NULL DEFAULT 0,

  -- section system
  section_template_key TEXT NULL,
  sections_version INTEGER NULL,

  -- audit
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wells_status ON wells(status);
CREATE INDEX IF NOT EXISTS idx_wells_name ON wells(well_name);

-- ----------------------------
-- Well Identity (Step 1)
-- ----------------------------
CREATE TABLE IF NOT EXISTS well_identity (
  well_id TEXT PRIMARY KEY,
  well_name TEXT NOT NULL,
  well_key TEXT NULL,
  field_name TEXT NULL,
  operator TEXT NULL,
  contractor TEXT NULL,
  well_purpose TEXT NULL,
  well_type TEXT NULL,
  dd_well_type TEXT NULL,
  province TEXT NULL,
  rig_name TEXT NULL,
  notes TEXT NULL,
  updated_at TEXT NOT NULL,

  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);

-- ----------------------------
-- Well Trajectory (Step 2)
-- ----------------------------
CREATE TABLE IF NOT EXISTS well_trajectory (
  well_id TEXT PRIMARY KEY,

  kop_m REAL NOT NULL,
  tvd_planned_m REAL NOT NULL,
  md_planned_m REAL NOT NULL,
  max_inc_planned_deg REAL NOT NULL,
  azimuth_planned_deg REAL NOT NULL,
  max_dls_planned_deg_per_30m REAL NOT NULL,
  vs_planned_m REAL NOT NULL,
  dist_planned_m REAL NOT NULL,

  tvd_at_td_m REAL NULL,
  md_at_td_m REAL NULL,
  inc_at_td_deg REAL NULL,
  azimuth_at_td_deg REAL NULL,
  max_dls_actual_deg_per_30m REAL NULL,
  vs_at_td_m REAL NULL,
  dist_at_td_m REAL NULL,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,

  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);


-- ----------------------------
-- WellOps Sections Tree
-- ----------------------------
CREATE TABLE IF NOT EXISTS well_section_nodes (
  node_id TEXT PRIMARY KEY,
  well_id TEXT NOT NULL,

  parent_id TEXT NULL,
  node_key TEXT NOT NULL,
  title TEXT NOT NULL,
  node_type TEXT NOT NULL,             -- GROUP | SECTION | ITEM
  order_index INTEGER NOT NULL,

  is_enabled INTEGER NOT NULL DEFAULT 1,
  is_selected INTEGER NOT NULL DEFAULT 0,
  is_completed INTEGER NOT NULL DEFAULT 0,

  state_json TEXT NULL,

  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,

  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_well
  ON well_section_nodes(well_id);

CREATE INDEX IF NOT EXISTS idx_nodes_parent
  ON well_section_nodes(well_id, parent_id, order_index);

CREATE UNIQUE INDEX IF NOT EXISTS uq_nodes_well_nodekey
  ON well_section_nodes(well_id, node_key);

-- ----------------------------
-- Hole Section Enablement
-- ----------------------------
CREATE TABLE IF NOT EXISTS well_hole_sections (
  well_id TEXT NOT NULL,
  node_key TEXT NOT NULL,
  is_enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL,

  PRIMARY KEY (well_id, node_key),
  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);


-- ----------------------------
-- Hole Section Data
-- ----------------------------
CREATE TABLE IF NOT EXISTS well_hole_section_data (
  well_id TEXT NOT NULL,
  hole_key TEXT NOT NULL,

  mud_motor_brand TEXT NULL,
  mud_motor_size TEXT NULL,
  mud_motor_sleeve_stb_gauge_in REAL NULL,
  mud_motor_bend_angle_deg TEXT NULL,
  mud_motor_lobe TEXT NULL,
  mud_motor_stage TEXT NULL,
  mud_motor_ibs_gauge_in REAL NULL,

  bit_brand TEXT NULL,
  bit_kind TEXT NULL,
  bit_type TEXT NULL,
  bit_iadc TEXT NULL,
  bit_serial TEXT NULL,

  personnel_day_dd TEXT NULL,
  personnel_night_dd TEXT NULL,
  personnel_day_mwd TEXT NULL,
  personnel_night_mwd TEXT NULL,

  info_casing_shoe TEXT NULL,
  info_casing_od TEXT NULL,
  info_casing_id TEXT NULL,
  info_section_tvd TEXT NULL,
  info_section_md TEXT NULL,
  info_mud_type TEXT NULL,

  ta_call_out_date TEXT NULL,
  ta_crew_mob_time TEXT NULL,
  ta_standby_time_hrs REAL NULL,
  ta_ru_time_hrs REAL NULL,
  ta_tripping_time_hrs REAL NULL,
  ta_circulation_time_hrs REAL NULL,
  ta_rotary_time_hrs REAL NULL,
  ta_rotary_meters REAL NULL,
  ta_sliding_time_hrs REAL NULL,
  ta_sliding_meters REAL NULL,
  ta_npt_due_to_rig_hrs REAL NULL,
  ta_npt_due_to_motor_hrs REAL NULL,
  ta_npt_due_to_mwd_hrs REAL NULL,
  ta_release_date TEXT NULL,
  ta_release_time TEXT NULL,
  ta_total_brt_hrs REAL NULL,

  updated_at TEXT NOT NULL,

  PRIMARY KEY (well_id, hole_key),
  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);

CREATE INDEX IF NOT EXISTS idx_hse_data_well
  ON well_hole_section_data(well_id);

CREATE TABLE IF NOT EXISTS well_hse_ticket (
  well_id TEXT NOT NULL,
  hole_key TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  ticket_date TEXT NULL,
  ticket_price_usd REAL NULL,
  updated_at TEXT NOT NULL,

  PRIMARY KEY (well_id, hole_key, line_no),
  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);

CREATE TABLE IF NOT EXISTS well_hse_nozzle (
  well_id TEXT NOT NULL,
  hole_key TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  count INTEGER NOT NULL,
  size_32nds INTEGER NOT NULL,
  updated_at TEXT NOT NULL,

  PRIMARY KEY (well_id, hole_key, line_no),
  FOREIGN KEY (well_id) REFERENCES wells(well_id)
);
