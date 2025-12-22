# AWB Mutual Exclusivity Analysis - Scratchpad

**Date:** 2025-12-21
**Purpose:** Analyze gaps between Motion backend AWB updates and MotionEye implementation
**Status:** ✅ IMPLEMENTATION COMPLETE

---

## Implementation Progress

### Completed Changes (2025-12-21)

| Phase | File | Change | Status |
|-------|------|--------|--------|
| 1.1 | `defaults.py:92` | Added `@awb_locked` default | ✅ |
| 1.2 | `converters.py:429,437,447` | Added `awb_locked` to ui_to_dict | ✅ |
| 1.3 | `converters.py:1035-1039` | Added `awb_locked` to dict_to_ui | ✅ |
| 2.1 | `_video_device.html:150-160` | Added AWB Locked checkbox | ✅ |
| 3.1 | `main.js:2083` | Added `awb_locked` to cameraUiToDict | ✅ |
| 3.2 | `main.js:2413` | Added `awbLockedSwitch` to cameraDictToUi | ✅ |
| 3.3 | `main.js:5811` | Added `awbLockedSwitch` to paramMap | ✅ |
| 3.4 | `main.js:5826` | Added awbLockedSwitch to value conversion | ✅ |
| 3.5 | `main.js:5801-5834` | Added all hot-reload change handlers | ✅ |
| 3.6 | `main.js:5789-5798` | Added AWB mode clear logic | ✅ |

### Deployment & Testing (2025-12-21)

| Test | Result |
|------|--------|
| Python syntax check | ✅ Pass |
| Code sync to Pi 5 | ✅ Success |
| Package install | ✅ Success |
| Service restart | ✅ Running |
| @awb_locked in defaults.py | ✅ Verified |
| awb_locked in ui_to_dict | ✅ Verified |
| awb_locked in dict_to_ui | ✅ Verified |
| awbLockedSwitch in HTML | ✅ Present |
| awbLockedSwitch in paramMap | ✅ Present |
| Mutual exclusivity handlers | ✅ Present |
| AWB mode clear logic | ✅ Present |
| Camera config has @awb_locked | ✅ Verified |
| Camera config has libcam_awb_locked | ✅ Verified |
| Camera stream working | ✅ 39KB in 3s |

**Camera Config State:**
```
# @awb_enable off
# @awb_mode 0
# @awb_locked off
# @colour_temp 2700
# @colour_gain_r 0.0
# @colour_gain_b 0.0
libcam_awb_enable off
libcam_awb_mode 0
libcam_awb_locked off
libcam_colour_temp 2700
libcam_colour_gain_r 0.0
libcam_colour_gain_b 0.0
```

---

## Current Implementation State (Pre-Changes)

### Backend (Motion 5.0+) - Updated
Per `docs/designs/20251221-awb-mutual-exclusivity-update.md`:
1. **Mutual Exclusivity Rules**:
   - `awb_enable=true` → AWB preset modes active, manual controls ignored
   - `awb_enable=false` → Manual controls (temp OR gains) active
   - Setting `awb_mode` (0-6) → clears `colour_temp`, `colour_gain_r`, `colour_gain_b`
   - Setting `awb_mode=7` (Custom) → preserves manual values
   - Setting `colour_temp > 0` → clears both gains to 0
   - Setting either gain > 0 → clears `colour_temp` to 0

2. **Parameters (all hot-reloadable)**:
   - `libcam_awb_enable` (bool) - master switch
   - `libcam_awb_mode` (int 0-7) - AWB preset
   - `libcam_awb_locked` (bool) - freeze current WB
   - `libcam_colour_temp` (int 0-10000) - manual Kelvin
   - `libcam_colour_gain_r` (float 0.0-8.0) - red gain
   - `libcam_colour_gain_b` (float 0.0-8.0) - blue gain

---

## MotionEye Current State

### constants.py ✅
- `USED_MOTION_OPTIONS`: Contains all 6 AWB params
- `HOT_RELOAD_PARAMS`: Contains all 6 AWB params

### defaults.py ⚠️ PARTIAL
- Has `@awb_enable`, `@awb_mode`, `@colour_temp`, `@colour_gain_r`, `@colour_gain_b`
- **MISSING**: `@awb_locked` default

### converters.py ⚠️ PARTIAL
- **ui_to_dict**:
  - Has: `awb_enable`, `awb_mode`, `colour_temp`, `colour_gain_r`, `colour_gain_b`
  - **MISSING**: `awb_locked` handling
  - **MISSING**: `libcam_awb_locked` output

- **dict_to_ui**:
  - Has AWB control reading with legacy format migration
  - **MISSING**: `awb_locked` reading

### _video_device.html ⚠️ PARTIAL
- Has: AWB Enable switch, AWB Mode select, Colour Temp slider, Red/Blue Gain sliders
- **MISSING**: AWB Locked checkbox/switch

### main.js ⚠️ PARTIAL
- **cameraUiToDict** (line ~2078):
  - Has: awb_enable, awb_mode, colour_temp, colour_gain_r, colour_gain_b
  - **MISSING**: awb_locked

- **cameraDictToUi** (line ~2407):
  - Has: awbEnableSwitch, awbModeSelect, colourTempSlider, colourGainRSlider, colourGainBSlider
  - **MISSING**: awbLockedSwitch

- **Hot-reload handlers** (line ~5780):
  - Has: awbEnableSwitch, awbModeSelect change handlers
  - **MISSING**: awbLockedSwitch handler
  - **MISSING**: colourTempSlider, colourGainRSlider, colourGainBSlider handlers

- **paramMap** (line ~5802):
  - Has: awbEnableSwitch, awbModeSelect, colourTempSlider, colourGainRSlider, colourGainBSlider
  - **MISSING**: awbLockedSwitch

- **applyPresetSettings** (line ~6039):
  - Lists awb_locked in hotReloadSettings array
  - References awbLockedSwitch but **element doesn't exist in HTML**

---

## Critical Missing Features

### 1. AWB Locked Control
**Status**: Referenced in JS but not implemented in HTML or converters
- No `awbLockedSwitch` element in `_video_device.html`
- No `@awb_locked` default in `defaults.py`
- No `libcam_awb_locked` in converter output

### 2. Mutual Exclusivity UI Logic
**Status**: Not implemented
The design doc specifies UI should:
- Show/hide manual controls based on `awb_enable`
- Radio button selection between temp and gains methods
- Clear opposing values when one method is set

**Current implementation**:
- Uses `depends="!awbEnable"` in HTML for visibility
- No mutual exclusivity between temp and gains in JS
- No clearing logic when values change

### 3. Hot-Reload Handlers for Manual Controls
**Status**: Partial
- Sliders have hot-reload class but no explicit change handlers
- Missing mutual exclusivity clearing in hot-reload flow

---

## Gaps Summary

| Component | Gap | Priority |
|-----------|-----|----------|
| defaults.py | Missing `@awb_locked` | High |
| converters.py ui_to_dict | Missing `awb_locked`, `libcam_awb_locked` | High |
| converters.py dict_to_ui | Missing `awb_locked` | High |
| _video_device.html | Missing AWB Locked checkbox | High |
| main.js cameraUiToDict | Missing `awb_locked` | High |
| main.js cameraDictToUi | Missing awbLockedSwitch | High |
| main.js paramMap | Missing awbLockedSwitch mapping | High |
| main.js hot-reload | Missing mutual exclusivity logic | Medium |
| main.js handlers | Missing slider change handlers | Medium |

---

## Implementation Order

1. **Backend Data Flow** (defaults.py, converters.py)
   - Add `@awb_locked` default
   - Add `libcam_awb_locked` to ui_to_dict
   - Add `awb_locked` to dict_to_ui

2. **UI Elements** (_video_device.html)
   - Add AWB Locked checkbox

3. **Frontend Logic** (main.js)
   - Add awb_locked to cameraUiToDict
   - Add awbLockedSwitch to cameraDictToUi
   - Add awbLockedSwitch to paramMap
   - Add change handler for awbLockedSwitch
   - Add change handlers for colour sliders
   - Implement mutual exclusivity clearing logic

4. **Testing**
   - Verify hot-reload for all AWB params
   - Verify mutual exclusivity (temp vs gains)
   - Verify AWB lock functionality
