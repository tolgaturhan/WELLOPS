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
