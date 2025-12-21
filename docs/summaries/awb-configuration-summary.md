# AWB Controls and Camera Preset System - Implementation Summary

**Date**: 2025-12-20
**Plan Source**: `docs/plans/awb-and-preset-system-plan-20251220-1600.md`

---

## Overview

This implementation adds Auto White Balance (AWB) controls and a Camera Preset System to MotionEye for Raspberry Pi 5 with libcamera support (Motion 5.0+). Both features support hot-reload for immediate visual feedback without camera restart.

---

## Implementation Completed

### Phase 1: AWB Backend Implementation

**Files Modified:**

1. **`motioneye/config/camera/constants.py`**
   - Added AWB parameters to `USED_MOTION_OPTIONS` (lines 31-36)
   - Added AWB parameters to `HOT_RELOAD_PARAMS` (lines 224-229)

2. **`motioneye/config/defaults.py`**
   - Added AWB default values (lines 89-95):
     - `libcam_awb_enable`: True
     - `libcam_awb_mode`: 0 (Auto)
     - `libcam_awb_locked`: False
     - `libcam_colour_temp`: 0 (disabled)
     - `libcam_colour_gain_r`: 0.0 (auto)
     - `libcam_colour_gain_b`: 0.0 (auto)

3. **`motioneye/config/camera/converters.py`**
   - Added UI-to-Motion conversion (lines 426-432)
   - Added Motion-to-UI conversion (lines 1003-1009)

---

### Phase 2: AWB Frontend Implementation

**Files Modified:**

1. **`motioneye/templates/partials/settings/_video_device.html`**
   - Added White Balance section header (lines 111-119)
   - Added AWB Enable checkbox (lines 120-130)
   - Added AWB Mode dropdown (lines 131-150)
   - Added AWB Locked checkbox (lines 151-161)
   - Added Colour Temperature slider (lines 162-173)
   - Added Red Gain slider (lines 174-184)
   - Added Blue Gain slider (lines 185-195)
   - All controls have `libcam-only` class and `hot-reload` class

2. **`motioneye/static/js/main.js`**
   - Added AWB value reading in `cameraUi2Dict()` (lines 2081-2086)
   - Added AWB value setting in `dict2CameraUi()` (lines 2410-2416)
   - Updated `paramMap` in `applyHotReloadParameter()` (lines 5799-5805)
   - Added special handling for AWB checkboxes and select (lines 5818-5826)
   - Added AWB checkbox/select change handlers in `initHotReloadSliders()` (lines 5783-5791)

---

### Phase 3: Preset Storage System

**Files Created:**

1. **`motioneye/config/presets.py`** (new file)
   - `list_presets(camera_id)` - List all presets for a camera
   - `get_preset(camera_id, preset_id)` - Get a specific preset
   - `save_preset(camera_id, name, settings_dict, preset_id)` - Save/update a preset
   - `delete_preset(camera_id, preset_id)` - Delete a preset
   - `rename_preset(camera_id, preset_id, new_name)` - Rename a preset
   - `list_all_preset_names()` - List all preset names globally
   - `find_preset_by_name(name)` - Find preset by name across cameras

   **Preset Storage:**
   - Location: `/etc/motioneye/camera-{id}-presets.json`
   - Format: JSON with version, presets dict containing name, settings, created, modified

---

### Phase 4: Backend API Endpoints

**Files Modified:**

1. **`motioneye/handlers/config.py`**
   - Added `list_presets(camera_id)` method (lines 916-930)
   - Added `save_preset(camera_id)` method (lines 932-970)
   - Added `load_preset(camera_id)` method (lines 972-1009)
   - Added `delete_preset(camera_id)` method (lines 1011-1032)
   - Added `rename_preset(camera_id)` method (lines 1034-1062)
   - Updated `get()` dispatch to handle `list_presets` (lines 74-76)
   - Updated `post()` dispatch to handle `save`, `load`, `delete`, `rename` (lines 105-115)

2. **`motioneye/server.py`**
   - Added preset list route: `/config/{camera_id}/presets/` (lines 199-203)
   - Added preset action routes: `/config/{camera_id}/presets/{op}/` (lines 204-207)

---

### Phase 5: Frontend Preset UI

**Files Modified:**

1. **`motioneye/templates/partials/settings/_video_device.html`**
   - Added Camera Presets section (lines 231-248)
   - Preset select dropdown
   - Load, Save, Manage buttons

2. **`motioneye/static/js/main.js`**
   - Added preset functions (lines 5977-6323):
     - `initPresets()` - Initialize event handlers
     - `refreshPresetList(callback)` - Load preset list from server
     - `loadSelectedPreset()` - Load and apply selected preset
     - `applyPresetSettings(settings)` - Apply preset settings to UI
     - `showSavePresetDialog()` - Show save preset modal
     - `saveCurrentPreset(name, forceOverwrite)` - Save current settings
     - `showManagePresetsDialog()` - Show preset management modal
     - `showRenamePresetDialog(id, name)` - Show rename modal
     - `renamePreset(id, newName)` - Rename a preset
     - `confirmDeletePreset(id, name)` - Confirm deletion
     - `deletePreset(id)` - Delete a preset

3. **`motioneye/static/css/main.css`**
   - Added preset styles (lines 1521-1601)
   - Small button styling
   - Preset list container and items
   - Preset actions buttons
   - Modal dialog styling

---

## AWB Mode Reference

| Mode | Value | Description | Color Temp |
|------|-------|-------------|------------|
| Auto | 0 | Automatic adjustment | Varies |
| Incandescent | 1 | Warm indoor lighting | ~2700K |
| Tungsten | 2 | Very warm lighting | ~2500K |
| Fluorescent | 3 | Office lighting | ~4000K |
| Indoor | 4 | General indoor | ~3500K |
| Daylight | 5 | Outdoor sunny | ~5500K |
| Cloudy | 6 | Overcast outdoor | ~6500K |
| Custom | 7 | Manual colour temp/gains | User defined |

---

## Testing Requirements

### On Raspberry Pi 5:

1. **Deploy and restart:**
   ```bash
   rsync -avz --exclude='.git' /path/to/motioneye/ admin@PI_IP:~/motioneye/
   ssh admin@PI_IP "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"
   ```

2. **Test AWB Controls:**
   - Open MotionEye web interface
   - Navigate to Video Device settings
   - Verify White Balance section appears (libcamera only)
   - Toggle AWB Enable and observe stream
   - Change AWB Mode and observe color changes
   - Test manual controls (Colour Temp, Red/Blue Gain) when AWB disabled or Custom mode

3. **Test Preset System:**
   - Click "Save" to create a preset
   - Adjust settings, then select preset and click "Load"
   - Verify hot-reload settings apply immediately
   - Click "Manage" to rename/delete presets

4. **Verify Hot-Reload:**
   - Check logs for CSRF token retrieval
   - Observe "Applying" indicator on slider change
   - Verify changes apply without camera restart

---

## Known Limitations

1. AWB controls only visible for libcamera devices (Pi Camera v3)
2. Preset colour temperature requires AWB disabled or Custom mode
3. Some preset settings (framerate, autofocus) require Apply to take effect

---

## Files Changed Summary

| File | Type | Changes |
|------|------|---------|
| `config/camera/constants.py` | Modified | AWB params in USED_MOTION_OPTIONS, HOT_RELOAD_PARAMS |
| `config/defaults.py` | Modified | AWB default values |
| `config/camera/converters.py` | Modified | UI-to-Motion and Motion-to-UI conversions |
| `config/presets.py` | New | Preset storage module |
| `handlers/config.py` | Modified | Preset API endpoints |
| `server.py` | Modified | Preset routes |
| `templates/partials/settings/_video_device.html` | Modified | AWB and preset HTML controls |
| `static/js/main.js` | Modified | AWB and preset JavaScript functions |
| `static/css/main.css` | Modified | Preset UI styles |
