# Autofocus Hot-Reload Integration Summary

**Completed:** 2025-12-21 21:50
**Task Duration:** ~15 minutes

---

## Summary

Successfully migrated MotionEye's autofocus controls from the legacy `libcam_control_item` format to Motion 5.0's dedicated hot-reloadable `libcam_af_*` parameters. This enables instant focus changes without camera restart.

---

## Files Modified

### 1. `motioneye/config/camera/constants.py`
- Added `libcam_af_mode`, `libcam_af_range`, `libcam_af_speed`, `libcam_lens_position` to `USED_MOTION_OPTIONS`
- Added all four AF params to `HOT_RELOAD_PARAMS` with documentation comments

### 2. `motioneye/config/defaults.py`
- Added `@af_speed` default (0 = Normal speed) alongside existing AF defaults

### 3. `motioneye/config/camera/converters.py`
- **UI-to-Motion (`_camera_ui_to_motion`)**: Replaced `libcam_control_item` AF entries with dedicated `libcam_af_*` parameters
- **Motion-to-UI (`_camera_motion_to_ui`)**: Added `autofocus_speed` reading with fallback to `libcam_af_speed`
- Removed legacy `control_items.append(f'AfMode=...')` code block

### 4. `motioneye/templates/partials/settings/_video_device.html`
- Added `hot-reload` class and `libcam-only` class to `autofocusModeSelect`
- Added `hot-reload` class and `libcam-only` class to `autofocusRangeSelect`
- Added new `autofocusSpeedSelect` control with `hot-reload` and `libcam-only` classes
- Added `hot-reload` class and `libcam-only` class to `lensPositionSlider`
- Added "Live" badge to all AF controls

### 5. `motioneye/static/js/main.js`
- **`configPanelToDict()`**: Added `autofocus_speed` reading
- **`dictToConfigPanel()`**: Added `autofocusSpeedSelect` value setting and visibility handling
- **Hot-reload parameter mapping**: Added AF params to `paramMap` object
- **Preset loading**: Added `autofocus_speed` case and updated all AF cases to use `applyHotReloadParameter()`
- **Preset saving**: Added `autofocus_speed` to settings object

---

## New Feature: Autofocus Speed

Added a new "Autofocus Speed" dropdown with two options:
- **Normal (0)**: Standard autofocus speed - more accurate
- **Fast (1)**: Prioritizes speed over accuracy - better for tracking moving subjects

This control appears between AF Range and Lens Position, and is only visible when AF Mode is not Manual.

---

## Testing Checklist

1. [ ] Deploy to Pi 5 using rsync
2. [ ] Restart motioneye service
3. [ ] Open UI at http://192.168.1.176:8765/
4. [ ] Verify AF Mode changes apply instantly (no restart notification)
5. [ ] Verify AF Range changes apply instantly
6. [ ] Verify new AF Speed control appears and changes apply instantly
7. [ ] Verify Lens Position changes apply instantly in Manual mode
8. [ ] Check Motion logs for no HTTP 403/405 errors

---

## Pattern Followed

Implementation followed the AWB migration pattern (commits cdff7532, a52cd6b8):
- `@` prefixed keys for UI persistence
- Dedicated `libcam_*` parameters for Motion 5.0+
- `hot-reload` CSS class for instant UI updates
- `libcam-only` CSS class for libcamera-specific visibility
- Hot-reload badge ("Live") for user clarity
