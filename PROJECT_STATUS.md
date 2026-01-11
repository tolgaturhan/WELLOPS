# Project Status

## Overview
- Scope: TPIC WellOps desktop app (PySide6).
- Current default flow: Directional Drilling only; other operation types are Under Construction.
- UI split: left well tree, right stacked pages.

## Operation Types
- Create New Well dialog now requires an Operation Type selection:
  - Directional Drilling
  - Underreamer
  - RSS
  - RSS with Underreamer
- Directional Drilling: full existing flow (Well Identity, Trajectory, Hole Program, Hole Section forms).
- Other types: only well root created; no sub-sections; right panel shows Under Construction message.
- Well tree label includes operation type: WELL_NAME (Operation Type).

## Navigation Flow
- Wizard flow removed for Directional Drilling.
- After Create New Well (Directional Drilling), Well Identity is auto-selected in the tree and opened.
- Cancel/Next wizard buttons are not used.

## UI Layout and Theme
- Minimum window size: 1024x768; initial size set to 1024x768.
- Light/Dark mode toggle in View menu; last theme persists via QSettings.
- Tree selection highlight in Light Mode matches Dark Mode.
- Well Identity form is wrapped in a group box: "WELL IDENTITY (Required)", with hints and buttons below (like Trajectory).
- Step 3 Hole Program Reset/Apply buttons left-aligned.
- Hole Section form Save button placed next to Validate Section.

## Well Tree Visual Rules
- Enabled hole sections: prefix "?", bold, RGB(25,125,55).
- Disabled hole sections: prefix "?", bold, RGB(200,0,0).

## Step 1 (Well Identity)
- Save button does NOT show "validation passed" message.
- On success: "Well Identity saved." and DB update.
- Notes in UI:
  - "All inputs are normalized to ASCII-only uppercase."
  - "The Field Name is auto-generated based on the entered Well Name."

## Step 2 (Trajectory)
- Save behavior mirrors Step 1 (no "validation passed" message).
- ACTUAL fields rule: if any ACTUAL field is filled, all ACTUAL fields become required; if all empty, save allowed.

## Step 3 (Hole Program / Hole Sections)
- Apply shows: "Hole Section Program saved."
- Disabling a hole section triggers warning and deletes all related data in DB.
- Cache cleared for disabled hole section widgets.

## Hole Section Form - Key Rules
- ASCII-only uppercase normalization applied to free-text fields; numeric rules preserved.
- DAY/NIGHT DD/MWD personnel fields expanded to 3 inputs each (12 total); at least one required.
- CASING OD/ID are required, selection-only.
- OPEN HOLE option added:
  - If OD = OPEN HOLE, ID list shows only OPEN HOLE.
  - If OD/ID are OPEN HOLE, CASING SHOE auto-sets to 0 (forced).
  - Otherwise CASING SHOE must be > 0.
- INFO SECTION TVD (METER) and SECTION MD (METER) are required.
- MUD TYPE is required; selection-only list.
- BIT section split into BIT-1 and BIT-2 side-by-side:
  - BIT-2 optional, but if brand selected then all BIT-2 fields become required.
  - Nozzle selections stored per bit using bit_index.
- Mud Motor split into MOTOR-1 and MOTOR-2:
  - MOTOR-2 optional; if any MOTOR-2 field filled, all MOTOR-2 fields required.
  - If DD Well Type = "Only Inclination", Mud Motor is not required.

## Time Analysis (Runs)
- TOTAL BRT renamed to BRT.
- Time Analysis redesigned with RUN-1, RUN-2, RUN-3, SECTION TOTAL columns.
- SECTION TOTAL auto-calculated as Run1 + Run2 + Run3.
- %EFF DRILLING auto-calculated as:
  - ([Total Drilling Time Run1 + Run2 + Run3] / [BRT Run1 + Run2 + Run3]) * 100
- Run-2 and Run-3 optional; if any field in a run is filled, all fields in that run are required.
- If Total Drilling Time and BRT are both 0, %EFF DRILLING shows 0.00 (not Auto).

## Database / Schema
- wells table: added operation_type.
- hole_section_data table: added run columns, BIT-1/BIT-2 fields, Mud Motor 1/2 fields, expanded personnel fields, etc.
- nozzle entries include bit_index.
- Legacy mapping: old TOTAL BRT maps into new BRT Run-1.
- Deleting/Disabling a hole section removes all related records.

## Date Picker UI
- Date picker uses a separate calendar icon button (dark: white icon, light: black icon).
- Calendar popup styled to match current theme.
- Last attempt to override prev/next arrows was reverted (currently default arrows).

## Notable Fixes
- Added missing QGridLayout import.
- Fixed draft well insert column count.
- Fixed Nozzle dialog accepted attribute usage.
- Added well tree node selection helper for auto-selecting specific nodes.

## Current State
- Directional Drilling flow is stable with the above UI/DB rules.
- Other operation types are placeholders (Under Construction), no sub-sections yet.
