# AWB & Preset System Implementation Scratchpad

**Date**: 2025-12-20 17:00
**Plan Source**: `docs/plans/awb-and-preset-system-plan-20251220-1600.md`
**Status**: COMPLETED

---

## Implementation Progress

### Phase 1: AWB Backend
- [x] constants.py - USED_MOTION_OPTIONS (lines 31-36)
- [x] constants.py - HOT_RELOAD_PARAMS (lines 224-229)
- [x] defaults.py - AWB default values (lines 89-95)
- [x] converters.py - UI to Motion conversion (lines 426-432)
- [x] converters.py - Motion to UI conversion (lines 1003-1009)

### Phase 2: AWB Frontend
- [x] _video_device.html - AWB controls (lines 111-195)
- [x] main.js - cameraUi2Dict() additions (lines 2081-2086)
- [x] main.js - dict2CameraUi() additions (lines 2410-2416)
- [x] main.js - hot-reload mappings (lines 5799-5805)
- [x] main.js - event handlers (lines 5783-5791, 5818-5826)

### Phase 3: Preset Backend
- [x] Create presets.py module (new file)
- [x] All preset functions implemented

### Phase 4: Backend API
- [x] config.py - handler methods (lines 916-1062)
- [x] server.py - routes (lines 199-207)
- [x] config.py - dispatch updates (lines 74-76, 105-115)

### Phase 5: Frontend Preset UI
- [x] _video_device.html - preset controls (lines 231-248)
- [x] main.js - preset functions (lines 5977-6323)
- [x] main.css - styles (lines 1521-1601)
- Note: Modals created dynamically in JavaScript, not in HTML

---

## Key File Locations (validated)

- constants.py: AWB in USED_MOTION_OPTIONS (lines 31-36), HOT_RELOAD_PARAMS (lines 224-229)
- defaults.py: AWB defaults (lines 89-95)
- converters.py: UI→Motion (lines 426-432), Motion→UI (lines 1003-1009)
- _video_device.html: AWB (lines 111-195), Presets (lines 231-248)
- main.js:
  - cameraUi2Dict(): AWB (lines 2081-2086)
  - dict2CameraUi(): AWB (lines 2410-2416)
  - hot-reload: paramMap (lines 5795-5826)
  - preset functions: lines 5977-6323

---

## Notes

- AWB controls use `depends` attribute for conditional visibility based on awbEnable and awbMode
- Route pattern uses simpler ops (save, load, delete, rename) not prefixed versions
- Presets stored per-camera in JSON files at /etc/motioneye/
- Hot-reload applies immediately; non-hot-reload settings staged in UI

---

## Verification

All Python files compile successfully:
- motioneye/config/camera/constants.py
- motioneye/config/defaults.py
- motioneye/config/camera/converters.py
- motioneye/config/presets.py
- motioneye/handlers/config.py
- motioneye/server.py

---

## Summary Document

Created: `docs/summaries/awb-configuration-summary.md`

