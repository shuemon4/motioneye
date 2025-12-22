# AWB Mutual Exclusivity Implementation Plan

**Date:** 2025-12-21
**Design Reference:** `docs/designs/20251221-awb-mutual-exclusivity-update.md`
**Analysis Notes:** `docs/scratchpads/awb-mutual-exclusivity-analysis-20251221-1000.md`
**Status:** Ready for Implementation

---

## Overview

Motion 5.0 backend has been updated with full AWB hot-reload support and mutual exclusivity handling. This plan details the required MotionEye frontend changes to properly integrate with the updated backend.

### Key Requirements

1. **Add missing `awb_locked` control** - Full data flow from UI to Motion
2. **Implement mutual exclusivity logic** - Temperature and Gains are mutually exclusive
3. **Add hot-reload handlers** - For colour sliders and AWB locked
4. **UI synchronization** - Clear opposing values in UI when backend clears them

---

## Phase 1: Backend Data Flow

### 1.1 Update defaults.py

**File:** `motioneye/config/defaults.py`
**Location:** Line ~90 (in `_set_default_motion_camera` libcamera section)

**Changes:**
```python
# Current (line 89-94):
data.setdefault('@awb_enable', True)
data.setdefault('@awb_mode', 0)
data.setdefault('@colour_temp', 0)
data.setdefault('@colour_gain_r', 0.0)
data.setdefault('@colour_gain_b', 0.0)

# Add after @awb_mode:
data.setdefault('@awb_locked', False)   # Lock current WB values
```

### 1.2 Update converters.py - ui_to_dict

**File:** `motioneye/config/camera/converters.py`
**Location:** Line ~426-447 (libcamera AWB section in `motion_camera_ui_to_dict`)

**Changes:**
```python
# Current (line 427-438):
awb_enable = ui.get('awb_enable', True)
awb_mode = int(ui.get('awb_mode', 0))
colour_temp = int(ui.get('colour_temp', 0))
colour_gain_r = float(ui.get('colour_gain_r', 0.0))
colour_gain_b = float(ui.get('colour_gain_b', 0.0))

data['@awb_enable'] = awb_enable
data['@awb_mode'] = awb_mode
data['@colour_temp'] = colour_temp
data['@colour_gain_r'] = colour_gain_r
data['@colour_gain_b'] = colour_gain_b

# Add:
awb_locked = ui.get('awb_locked', False)
data['@awb_locked'] = awb_locked

# Current (line 440-447):
data['libcam_awb_enable'] = awb_enable
data['libcam_awb_mode'] = awb_mode
data['libcam_colour_temp'] = colour_temp
data['libcam_colour_gain_r'] = colour_gain_r
data['libcam_colour_gain_b'] = colour_gain_b

# Add:
data['libcam_awb_locked'] = awb_locked
```

### 1.3 Update converters.py - dict_to_ui

**File:** `motioneye/config/camera/converters.py`
**Location:** Line ~1023-1034 (libcamera AWB section in `motion_camera_dict_to_ui`)

**Changes:**
```python
# Current AWB reading (line 1024-1034):
# ... existing awb_enable, awb_mode, colour_temp, colour_gain_r, colour_gain_b ...

# Add after awb_mode reading (around line 1032):
ui['awb_locked'] = data.get('@awb_locked', data.get('libcam_awb_locked', False))
# Handle string/bool conversion for legacy format
if isinstance(ui['awb_locked'], str):
    ui['awb_locked'] = ui['awb_locked'].lower() in ('true', '1', 'on')
```

---

## Phase 2: UI Elements

### 2.1 Add AWB Locked Checkbox

**File:** `motioneye/templates/partials/settings/_video_device.html`
**Location:** After AWB Mode (around line 148), before Colour Temperature

**Add:**
```html
<!-- AWB Locked -->
<tr class="settings-item libcam-only" depends="awbEnable">
    <td class="settings-item-label">
        <span class="settings-item-label" data-i18n="Lock White Balance">Lock White Balance</span>
        <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
    </td>
    <td class="settings-item-value">
        <input type="checkbox" class="styled device camera-config hot-reload" id="awbLockedSwitch">
    </td>
    <td><span class="help-mark" data-i18n-title="Lock the current white balance values to prevent automatic adjustments. Useful when you've achieved the desired color and want to maintain it across changing lighting conditions." title="Lock the current white balance values to prevent automatic adjustments. Useful when you've achieved the desired color and want to maintain it across changing lighting conditions.">?</span></td>
</tr>
```

**Note:** The `depends="awbEnable"` makes this visible only when AWB is enabled, matching the design where locking makes sense for AWB mode.

---

## Phase 3: Frontend Logic (main.js)

### 3.1 Update cameraUiToDict

**File:** `motioneye/static/js/main.js`
**Location:** Line ~2081-2085

**Change:**
```javascript
// Current:
'awb_enable': $('#awbEnableSwitch').is(':checked'),
'awb_mode': parseInt($('#awbModeSelect').val()) || 0,
'colour_temp': parseInt($('#colourTempSlider').val()) || 0,
'colour_gain_r': parseFloat($('#colourGainRSlider').val()) || 0.0,
'colour_gain_b': parseFloat($('#colourGainBSlider').val()) || 0.0,

// Add after awb_mode:
'awb_locked': $('#awbLockedSwitch').is(':checked'),
```

### 3.2 Update cameraDictToUi

**File:** `motioneye/static/js/main.js`
**Location:** Line ~2410-2414

**Change:**
```javascript
// Current:
$('#awbEnableSwitch').prop('checked', dict['awb_enable'] != null ? dict['awb_enable'] : true); markHideIfNull(dict['proto'] !== 'libcamera', 'awbEnableSwitch');
$('#awbModeSelect').val(dict['awb_mode'] != null ? dict['awb_mode'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'awbModeSelect');
$('#colourTempSlider').val(dict['colour_temp'] != null ? dict['colour_temp'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourTempSlider');
$('#colourGainRSlider').val(dict['colour_gain_r'] != null ? dict['colour_gain_r'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainRSlider');
$('#colourGainBSlider').val(dict['colour_gain_b'] != null ? dict['colour_gain_b'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainBSlider');

// Add after awbModeSelect:
$('#awbLockedSwitch').prop('checked', dict['awb_locked'] != null ? dict['awb_locked'] : false); markHideIfNull(dict['proto'] !== 'libcamera', 'awbLockedSwitch');
```

### 3.3 Update paramMap

**File:** `motioneye/static/js/main.js`
**Location:** Line ~5803-5811

**Change:**
```javascript
// Current:
var paramMap = {
    'brightnessSlider': 'libcam_brightness',
    'contrastSlider': 'libcam_contrast',
    'isoSlider': 'libcam_iso',
    'awbEnableSwitch': 'libcam_awb_enable',
    'awbModeSelect': 'libcam_awb_mode',
    'colourTempSlider': 'libcam_colour_temp',
    'colourGainRSlider': 'libcam_colour_gain_r',
    'colourGainBSlider': 'libcam_colour_gain_b'
};

// Add awbLockedSwitch:
var paramMap = {
    'brightnessSlider': 'libcam_brightness',
    'contrastSlider': 'libcam_contrast',
    'isoSlider': 'libcam_iso',
    'awbEnableSwitch': 'libcam_awb_enable',
    'awbModeSelect': 'libcam_awb_mode',
    'awbLockedSwitch': 'libcam_awb_locked',
    'colourTempSlider': 'libcam_colour_temp',
    'colourGainRSlider': 'libcam_colour_gain_r',
    'colourGainBSlider': 'libcam_colour_gain_b'
};
```

### 3.4 Update Value Conversion in applyHotReloadParameter

**File:** `motioneye/static/js/main.js`
**Location:** Line ~5823 (after the awbEnableSwitch case)

**Change:**
```javascript
// Current (around line 5823):
} else if (sliderId === 'awbEnableSwitch') {
    // Boolean for AWB enable
    value = $slider.is(':checked') ? 'true' : 'false';
} else if (sliderId === 'awbModeSelect' || sliderId === 'colourTempSlider') {

// Add awbLockedSwitch:
} else if (sliderId === 'awbEnableSwitch' || sliderId === 'awbLockedSwitch') {
    // Boolean for AWB enable/locked
    value = $slider.is(':checked') ? 'true' : 'false';
} else if (sliderId === 'awbModeSelect' || sliderId === 'colourTempSlider') {
```

### 3.5 Add Hot-Reload Change Handlers

**File:** `motioneye/static/js/main.js`
**Location:** Line ~5783 (in the AWB handlers section)

**Add after existing handlers:**
```javascript
// AWB checkbox and select hot-reload handlers
$('#awbEnableSwitch').on('change', function() {
    applyHotReloadParameter($(this));
});

$('#awbModeSelect').on('change', function() {
    applyHotReloadParameter($(this));
});

// ADD: AWB Locked handler
$('#awbLockedSwitch').on('change', function() {
    applyHotReloadParameter($(this));
});

// ADD: Colour control handlers with mutual exclusivity
$('#colourTempSlider').on('change', function() {
    var value = parseFloat($(this).val()) || 0;
    if (value > 0) {
        // Mutual exclusivity: clear gains when setting temperature
        $('#colourGainRSlider').val(0);
        $('#colourGainBSlider').val(0);
    }
    applyHotReloadParameter($(this));
});

$('#colourGainRSlider').on('change', function() {
    var value = parseFloat($(this).val()) || 0;
    if (value > 0) {
        // Mutual exclusivity: clear temperature when setting gains
        $('#colourTempSlider').val(0);
    }
    applyHotReloadParameter($(this));
});

$('#colourGainBSlider').on('change', function() {
    var value = parseFloat($(this).val()) || 0;
    if (value > 0) {
        // Mutual exclusivity: clear temperature when setting gains
        $('#colourTempSlider').val(0);
    }
    applyHotReloadParameter($(this));
});
```

### 3.6 Add AWB Mode Clear Logic

**File:** `motioneye/static/js/main.js`
**Location:** Line ~5787 (in the awbModeSelect handler)

**Change:**
```javascript
// Current:
$('#awbModeSelect').on('change', function() {
    applyHotReloadParameter($(this));
});

// Replace with:
$('#awbModeSelect').on('change', function() {
    var mode = parseInt($(this).val()) || 0;
    // When changing to a preset mode (0-6), backend clears manual controls
    // Sync UI to match backend behavior
    if (mode !== 7) {  // 7 = Custom mode preserves manual values
        $('#colourTempSlider').val(0);
        $('#colourGainRSlider').val(0);
        $('#colourGainBSlider').val(0);
    }
    applyHotReloadParameter($(this));
});
```

---

## Phase 4: Testing

### 4.1 Unit Tests

Verify data flow:
- `awb_locked` flows from UI → config dict → Motion config
- `awb_locked` flows from Motion config → config dict → UI
- Boolean type handling for `awb_locked` in both directions

### 4.2 Integration Tests

Test on Pi 5:

1. **AWB Locked Toggle**
   - Enable AWB, verify awbLockedSwitch appears
   - Toggle lock, verify hot-reload to Motion
   - Check logs for CSRF + POST to `/config/set?libcam_awb_locked=true`

2. **Mutual Exclusivity - Temp vs Gains**
   - Disable AWB
   - Set colour_temp to 5000K → verify gains show as 0
   - Set gain_r to 1.5 → verify colour_temp shows as 0
   - Set gain_b to 1.2 → verify colour_temp still 0

3. **AWB Mode Clearing**
   - Disable AWB, set colour_temp to 6500K
   - Enable AWB, change mode to Daylight → verify temp/gains clear in UI
   - Change to Custom mode (7) → set gains → change to Auto → verify clears

4. **Persistence**
   - Set various AWB values
   - Restart MotionEye service
   - Verify values restored
   - Restart Motion daemon
   - Verify values restored

### 4.3 Edge Cases

- Set gain_r only → verify gain_b can be set independently
- Toggle AWB enable rapidly → verify no race conditions
- Set extreme values (temp=10000, gains=8.0) → verify accepted

---

## Files Modified Summary

| File | Type | Changes |
|------|------|---------|
| `motioneye/config/defaults.py` | Python | Add `@awb_locked` default |
| `motioneye/config/camera/converters.py` | Python | Add awb_locked to ui_to_dict and dict_to_ui |
| `motioneye/templates/partials/settings/_video_device.html` | HTML | Add AWB Locked checkbox row |
| `motioneye/static/js/main.js` | JavaScript | Multiple: cameraUiToDict, cameraDictToUi, paramMap, handlers, mutual exclusivity |

---

## Rollback Plan

If issues arise:
1. Revert file changes in order: main.js → _video_device.html → converters.py → defaults.py
2. Motion backend is backward compatible - will ignore missing `libcam_awb_locked`
3. Existing camera configs without `@awb_locked` will use default (false)

---

## Success Criteria

- [ ] AWB Locked checkbox visible when AWB enabled
- [ ] Toggling AWB Locked sends hot-reload request to Motion
- [ ] Setting colour_temp > 0 clears gains in UI
- [ ] Setting any gain > 0 clears colour_temp in UI
- [ ] Changing AWB mode (0-6) clears manual controls in UI
- [ ] All AWB values persist across MotionEye restart
- [ ] All AWB values persist across Motion restart
- [ ] No console errors in browser
- [ ] No errors in MotionEye logs
