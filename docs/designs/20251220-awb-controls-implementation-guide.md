# AWB (Auto White Balance) Controls Implementation Guide

**Date:** 2025-12-20
**Status:** Implementation Guide for AI Assistant
**Related:** Motion backend AWB hot-reload implementation complete
**Motion Plan:** `/Users/tshuey/Documents/GitHub/motion/doc/plans/20251220-AWB-HotReload-Implementation.md`
**Motion Scratchpad:** `/Users/tshuey/Documents/GitHub/motion/doc/scratchpads/20251220-awb-hotreload-implementation.md`

---

## Overview

This guide provides instructions for an AI assistant (Claude Code) to implement UI controls in MotionEye for the 6 new AWB (Auto White Balance) parameters that have been added to the Motion backend.

The Motion backend now supports hot-reload (runtime changes without restart) for these AWB controls, matching the existing pattern for brightness/contrast/ISO.

---

## Motion Backend Parameters (Already Implemented)

The following parameters are now available in Motion with hot-reload support:

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `libcam_awb_enable` | bool | true | true/false | Enable/disable auto white balance |
| `libcam_awb_mode` | int | 0 | 0-7 | AWB mode (see table below) |
| `libcam_awb_locked` | bool | false | true/false | Lock current white balance values |
| `libcam_colour_temp` | int | 0 | 0-10000 | Manual colour temperature in Kelvin (0=disabled) |
| `libcam_colour_gain_r` | float | 0.0 | 0.0-8.0 | Manual red channel gain (0=auto) |
| `libcam_colour_gain_b` | float | 0.0 | 0.0-8.0 | Manual blue channel gain (0=auto) |

### AWB Mode Values (libcamera native)

| Value | Name | Description |
|-------|------|-------------|
| 0 | Auto | Automatic white balance |
| 1 | Incandescent | Warm/tungsten lighting (~2700K) |
| 2 | Tungsten | Similar to incandescent |
| 3 | Fluorescent | Cool white fluorescent (~4000K) |
| 4 | Indoor | General indoor lighting |
| 5 | Daylight | Outdoor daylight (~5500K) |
| 6 | Cloudy | Overcast/cloudy (~6500K) |
| 7 | Custom | Use manual ColourGains/ColourTemperature |

---

## MotionEye Architecture Overview

MotionEye uses a layered architecture to manage Motion configuration:

```
┌─────────────────────────────────────────────────────────┐
│  UI Layer (HTML Templates + JavaScript)                 │
│  - Video Device Settings Template                       │
│  - main.js (event handlers, validation, hot-reload)     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Python Backend Layer                                    │
│  - config/camera/converters.py (UI ↔ Motion format)     │
│  - config/camera/constants.py (parameter registry)      │
│  - config/defaults.py (default values)                  │
│  - motionctl.py (Motion API communication)              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Motion Daemon (C++)                                     │
│  - Hot-reload AWB parameters via web API                │
│  - Applies to libcamera requests without restart        │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Pattern Reference

MotionEye already implements brightness/contrast/ISO controls. The AWB implementation should follow the **exact same pattern**.

### Key Pattern Files
- **HTML Template:** `motioneye/templates/partials/settings/_video_device.html`
- **JavaScript:** `motioneye/static/js/main.js`
- **Constants:** `motioneye/config/camera/constants.py`
- **Converters:** `motioneye/config/camera/converters.py`
- **Defaults:** `motioneye/config/defaults.py`

---

## Step-by-Step Implementation Guide

### Step 1: Register Parameters in Constants

**File:** `motioneye/config/camera/constants.py`

**Action:** Add the 6 new AWB parameters to the `USED_MOTION_OPTIONS` set.

**Location:** After line 30 (after `libcam_iso`)

**Code to add:**
```python
    'libcam_awb_enable',
    'libcam_awb_mode',
    'libcam_awb_locked',
    'libcam_colour_temp',
    'libcam_colour_gain_r',
    'libcam_colour_gain_b',
```

**Reference pattern:** Lines 28-30 (brightness/contrast/iso)

---

### Step 2: Set Default Values

**File:** `motioneye/config/defaults.py`

**Action:** Add default values for the 6 AWB parameters.

**Location:** After line 88 (after `libcam_iso`)

**Code to add:**
```python
        data.setdefault('libcam_awb_enable', True)  # AWB enabled by default
        data.setdefault('libcam_awb_mode', 0)  # Auto mode
        data.setdefault('libcam_awb_locked', False)  # Not locked
        data.setdefault('libcam_colour_temp', 0)  # 0 = disabled (use AWB)
        data.setdefault('libcam_colour_gain_r', 0.0)  # 0 = auto
        data.setdefault('libcam_colour_gain_b', 0.0)  # 0 = auto
```

**Reference pattern:** Lines 86-88 (brightness/contrast/iso)

---

### Step 3: Add UI to Motion Converters

**File:** `motioneye/config/camera/converters.py`

#### Part 3A: UI to Motion Conversion

**Action:** Convert UI values to Motion backend format.

**Location:** After line 424 (in `_ui_to_motion_camera_dict` function, after `libcam_iso`)

**Code to add:**
```python
            data['libcam_awb_enable'] = bool(ui.get('awb_enable', True))
            data['libcam_awb_mode'] = int(ui.get('awb_mode', 0))
            data['libcam_awb_locked'] = bool(ui.get('awb_locked', False))
            data['libcam_colour_temp'] = int(ui.get('colour_temp', 0))
            data['libcam_colour_gain_r'] = float(ui.get('colour_gain_r', 0.0))
            data['libcam_colour_gain_b'] = float(ui.get('colour_gain_b', 0.0))
```

**Reference pattern:** Lines 422-424 (brightness/contrast/iso)

#### Part 3B: Motion to UI Conversion

**Action:** Convert Motion values to UI format.

**Location:** After line 993 (in `_motion_camera_dict_to_ui` function, after `iso`)

**Code to add:**
```python
        ui['awb_enable'] = bool(data.get('libcam_awb_enable', True))
        ui['awb_mode'] = int(data.get('libcam_awb_mode', 0))
        ui['awb_locked'] = bool(data.get('libcam_awb_locked', False))
        ui['colour_temp'] = int(data.get('libcam_colour_temp', 0))
        ui['colour_gain_r'] = float(data.get('libcam_colour_gain_r', 0.0))
        ui['colour_gain_b'] = float(data.get('libcam_colour_gain_b', 0.0))
```

**Reference pattern:** Lines 991-993 (brightness/contrast/iso)

---

### Step 4: Add HTML UI Controls

**File:** `motioneye/templates/partials/settings/_video_device.html`

**Action:** Add UI controls for the 6 AWB parameters.

**Location:** After the ISO slider section (around line 110)

**HTML to add:**

```html
<!-- White Balance Controls -->
<tr class="tr-separator device camera-config">
    <td colspan="3">
        <div style="border-top: 1px solid #444; margin: 10px 0;"></div>
        <span style="font-weight: bold; color: #ddd;" data-i18n="White Balance">White Balance</span>
    </td>
</tr>

<!-- AWB Enable -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Auto White Balance">Auto White Balance</span>
    </td>
    <td class="settings-item-value">
        <input type="checkbox" class="styled device camera-config hot-reload" id="awbEnableCheckbox">
    </td>
    <td><span class="help-mark" data-i18n-title="Enable automatic white balance adjustment. Disable to use manual colour temperature or gains." title="Enable automatic white balance adjustment. Disable to use manual colour temperature or gains.">?</span></td>
</tr>

<!-- AWB Mode -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="AWB Mode">AWB Mode</span>
    </td>
    <td class="settings-item-value">
        <select class="styled device camera-config hot-reload" id="awbModeSelect">
            <option value="0" data-i18n="Auto">Auto</option>
            <option value="1" data-i18n="Incandescent">Incandescent</option>
            <option value="2" data-i18n="Tungsten">Tungsten</option>
            <option value="3" data-i18n="Fluorescent">Fluorescent</option>
            <option value="4" data-i18n="Indoor">Indoor</option>
            <option value="5" data-i18n="Daylight">Daylight</option>
            <option value="6" data-i18n="Cloudy">Cloudy</option>
            <option value="7" data-i18n="Custom">Custom</option>
        </select>
    </td>
    <td><span class="help-mark" data-i18n-title="Select white balance mode: Auto adapts to lighting conditions, preset modes optimize for specific light types (Incandescent/Tungsten ~2700K, Fluorescent ~4000K, Daylight ~5500K, Cloudy ~6500K), Custom uses manual temperature/gains." title="Select white balance mode: Auto adapts to lighting conditions, preset modes optimize for specific light types (Incandescent/Tungsten ~2700K, Fluorescent ~4000K, Daylight ~5500K, Cloudy ~6500K), Custom uses manual temperature/gains.">?</span></td>
</tr>

<!-- AWB Locked -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Lock White Balance">Lock White Balance</span>
    </td>
    <td class="settings-item-value">
        <input type="checkbox" class="styled device camera-config hot-reload" id="awbLockedCheckbox">
    </td>
    <td><span class="help-mark" data-i18n-title="Lock current white balance values to prevent automatic adjustments. Useful for consistent color across scenes." title="Lock current white balance values to prevent automatic adjustments. Useful for consistent color across scenes.">?</span></td>
</tr>

<!-- Colour Temperature -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Colour Temperature (K)">Colour Temperature (K)</span>
    </td>
    <td class="settings-item-value">
        <input type="text" class="range styled device camera-config hot-reload" id="colourTempSlider">
        <div class="slider-note" style="font-size: 0.85em; color: #999; margin-top: 2px;">* 0 = Auto, 2700K = Warm, 6500K = Cool</div>
    </td>
    <td><span class="help-mark" data-i18n-title="Manual colour temperature in Kelvin (0-10000). Set to 0 for automatic. Typical values: 2700K (incandescent), 4000K (fluorescent), 5500K (daylight), 6500K (cloudy). Requires AWB disabled." title="Manual colour temperature in Kelvin (0-10000). Set to 0 for automatic. Typical values: 2700K (incandescent), 4000K (fluorescent), 5500K (daylight), 6500K (cloudy). Requires AWB disabled.">?</span></td>
</tr>

<!-- Colour Gain Red -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Red Gain">Red Gain</span>
    </td>
    <td class="settings-item-value">
        <input type="text" class="range styled device camera-config hot-reload" id="colourGainRSlider">
    </td>
    <td><span class="help-mark" data-i18n-title="Manual red channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add warmth. Requires AWB disabled. Changes apply instantly." title="Manual red channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add warmth. Requires AWB disabled. Changes apply instantly.">?</span></td>
</tr>

<!-- Colour Gain Blue -->
<tr class="device camera-config">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Blue Gain">Blue Gain</span>
    </td>
    <td class="settings-item-value">
        <input type="text" class="range styled device camera-config hot-reload" id="colourGainBSlider">
    </td>
    <td><span class="help-mark" data-i18n-title="Manual blue channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add coolness. Requires AWB disabled. Changes apply instantly." title="Manual blue channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add coolness. Requires AWB disabled. Changes apply instantly.">?</span></td>
</tr>
```

**Reference pattern:** Lines 86-110 (brightness/contrast/iso sliders)

**Notes:**
- All controls have class `hot-reload` for instant updates
- All controls have class `device camera-config` for visibility toggling
- Help marks (`?`) provide user guidance
- Sliders use `type="text" class="range"` pattern (MotionEye slider framework)

---

### Step 5: Add JavaScript Value Reading

**File:** `motioneye/static/js/main.js`

**Action:** Read AWB values from UI controls when saving configuration.

**Location:** In the `configPanelToDict` function, after line 2080 (after `iso`)

**Code to add:**
```javascript
        'awb_enable': $('#awbEnableCheckbox').is(':checked'),
        'awb_mode': parseInt($('#awbModeSelect').val()) || 0,
        'awb_locked': $('#awbLockedCheckbox').is(':checked'),
        'colour_temp': parseInt($('#colourTempSlider').val()) || 0,
        'colour_gain_r': parseFloat($('#colourGainRSlider').val()) || 0.0,
        'colour_gain_b': parseFloat($('#colourGainBSlider').val()) || 0.0,
```

**Reference pattern:** Lines 2078-2080 (brightness/contrast/iso)

---

### Step 6: Add JavaScript Value Setting

**File:** `motioneye/static/js/main.js`

**Action:** Set AWB values in UI controls when loading configuration.

**Location:** In the `dictToConfigPanel` function, after line 2403 (after ISO slider)

**Code to add:**
```javascript
    $('#awbEnableCheckbox').prop('checked', dict['awb_enable'] != null ? dict['awb_enable'] : true); markHideIfNull(dict['proto'] !== 'libcamera', 'awbEnableCheckbox');
    $('#awbModeSelect').val(dict['awb_mode'] != null ? dict['awb_mode'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'awbModeSelect');
    $('#awbLockedCheckbox').prop('checked', dict['awb_locked'] != null ? dict['awb_locked'] : false); markHideIfNull(dict['proto'] !== 'libcamera', 'awbLockedCheckbox');
    $('#colourTempSlider').val(dict['colour_temp'] != null ? dict['colour_temp'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourTempSlider');
    $('#colourGainRSlider').val(dict['colour_gain_r'] != null ? dict['colour_gain_r'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainRSlider');
    $('#colourGainBSlider').val(dict['colour_gain_b'] != null ? dict['colour_gain_b'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainBSlider');
```

**Reference pattern:** Lines 2401-2403 (brightness/contrast/iso sliders)

**Notes:**
- `markHideIfNull(dict['proto'] !== 'libcamera', ...)` hides controls for non-libcamera devices
- Default values match those in `defaults.py`

---

### Step 7: Initialize Sliders

**File:** `motioneye/static/js/main.js`

**Action:** Initialize slider controls with ranges and step values.

**Location:** Search for where brightness/contrast/iso sliders are initialized (likely in a `configPanelInit` or similar function)

**Pattern to find:**
```javascript
$('#brightnessSlider').range({...});
$('#contrastSlider').range({...});
$('#isoSlider').range({...});
```

**Code to add after ISO slider initialization:**
```javascript
    $('#colourTempSlider').range({
        min: 0,
        max: 10000,
        step: 100,
        value: 0
    });

    $('#colourGainRSlider').range({
        min: 0.0,
        max: 8.0,
        step: 0.1,
        value: 0.0
    });

    $('#colourGainBSlider').range({
        min: 0.0,
        max: 8.0,
        step: 0.1,
        value: 0.0
    });
```

**Notes:**
- Colour temperature uses 100K steps for easier adjustment
- Gain sliders use 0.1 steps for fine control
- If slider initialization is not found, these may be auto-initialized from HTML attributes

---

### Step 8: Add Hot-Reload Mappings

**File:** `motioneye/static/js/main.js`

**Action:** Map UI control IDs to Motion parameter names for hot-reload.

**Location:** Search for the hot-reload mapping object (around line 5783)

**Pattern to find:**
```javascript
{
    'brightnessSlider': 'libcam_brightness',
    'contrastSlider': 'libcam_contrast',
    'isoSlider': 'libcam_iso',
```

**Code to add:**
```javascript
    'awbEnableCheckbox': 'libcam_awb_enable',
    'awbModeSelect': 'libcam_awb_mode',
    'awbLockedCheckbox': 'libcam_awb_locked',
    'colourTempSlider': 'libcam_colour_temp',
    'colourGainRSlider': 'libcam_colour_gain_r',
    'colourGainBSlider': 'libcam_colour_gain_b',
```

**Reference pattern:** Lines 5783-5785 (brightness/contrast/iso)

**Notes:**
- This enables instant updates when controls change
- No camera restart required for AWB adjustments
- Hot-reload handled automatically by MotionEye framework

---

## Testing Checklist

After implementation, verify the following:

### Functional Tests

- [ ] **UI Controls Visible:** AWB controls appear in Video Device settings for libcamera cameras
- [ ] **UI Controls Hidden:** AWB controls hidden for V4L2/network cameras
- [ ] **Default Values:** New libcamera camera shows correct defaults (AWB enabled, mode 0, etc.)
- [ ] **Save/Load:** AWB settings persist across MotionEye restarts
- [ ] **Hot-Reload:** Changing AWB controls updates live stream without camera restart

### AWB Mode Tests

Test each AWB mode with visual verification:

- [ ] **Mode 0 (Auto):** Adapts to room lighting
- [ ] **Mode 1 (Incandescent):** Compensates for warm tungsten bulbs
- [ ] **Mode 5 (Daylight):** Optimized for outdoor/natural light
- [ ] **Mode 7 (Custom):** Allows manual colour temp/gains

### Manual Control Tests

- [ ] **Disable AWB:** Uncheck "Auto White Balance", enable manual controls
- [ ] **Colour Temperature:** Slider adjusts image warmth/coolness (2700K-6500K range)
- [ ] **Red Gain:** Slider adds warmth to image
- [ ] **Blue Gain:** Slider adds coolness to image
- [ ] **Lock WB:** Lock checkbox freezes current white balance

### Edge Cases

- [ ] **Invalid Values:** UI prevents out-of-range values
- [ ] **Network Latency:** Hot-reload works over network connections
- [ ] **Multiple Cameras:** Each camera maintains independent AWB settings
- [ ] **Config Migration:** Existing configs load without errors

---

## Common Implementation Pitfalls

### 1. Proto Check Missing
**Problem:** AWB controls appear for V4L2 cameras
**Solution:** Ensure all controls use `markHideIfNull(dict['proto'] !== 'libcamera', ...)`

### 2. Type Conversion Errors
**Problem:** JavaScript sends string "0" instead of integer 0
**Solution:** Use `parseInt()`, `parseFloat()`, or appropriate conversion

### 3. Hot-Reload Mapping Incomplete
**Problem:** Changes require camera restart
**Solution:** Verify all 6 controls added to hot-reload mapping object

### 4. Slider Initialization Missing
**Problem:** Sliders don't respond to input
**Solution:** Add `.range()` initialization for colour_temp/gains sliders

### 5. Default Value Mismatch
**Problem:** UI shows different defaults than Motion backend
**Solution:** Ensure consistency between:
- `defaults.py` (Python defaults)
- `main.js` value setting (JavaScript fallbacks)
- Motion backend defaults (C++ code)

---

## Success Criteria

Implementation is complete when:

1. ✅ All 6 AWB parameters appear in UI for libcamera cameras
2. ✅ All 6 parameters hidden for non-libcamera cameras
3. ✅ AWB mode dropdown shows all 8 modes (0-7)
4. ✅ Colour temperature slider range: 0-10000K
5. ✅ Gain sliders range: 0.0-8.0
6. ✅ Hot-reload works: changes apply instantly without restart
7. ✅ Settings persist across MotionEye restarts
8. ✅ Visual verification: AWB modes produce expected color shifts
9. ✅ Manual controls work when AWB disabled
10. ✅ No JavaScript console errors

---

## File Summary

Files to modify (7 total):

| File | Changes | Lines |
|------|---------|-------|
| `config/camera/constants.py` | Add 6 parameters to USED_MOTION_OPTIONS | ~6 |
| `config/defaults.py` | Add 6 default values | ~6 |
| `config/camera/converters.py` | Add UI↔Motion conversions (2 locations) | ~12 |
| `templates/partials/settings/_video_device.html` | Add 6 UI controls | ~80 |
| `static/js/main.js` - Value Reading | Add 6 value reads in configPanelToDict | ~6 |
| `static/js/main.js` - Value Setting | Add 6 value sets in dictToConfigPanel | ~6 |
| `static/js/main.js` - Slider Init | Initialize 3 sliders | ~15 |
| `static/js/main.js` - Hot-Reload | Add 6 hot-reload mappings | ~6 |

**Total:** ~137 lines added across 4 files (3 Python, 1 HTML, 1 JavaScript)

---

## Additional Resources

- **Motion AWB Implementation Plan:** `/Users/tshuey/Documents/GitHub/motion/doc/plans/20251220-AWB-HotReload-Implementation.md`
- **Motion Implementation Notes:** `/Users/tshuey/Documents/GitHub/motion/doc/scratchpads/20251220-awb-hotreload-implementation.md`
- **ISO Implementation Reference:** `/Users/tshuey/Documents/GitHub/motioneye/docs/designs/iso-slider-motion-backend-implementation-notes.md`
- **libcamera AWB Documentation:** https://libcamera.org/api-html/controls_8h.html

---

## Notes for AI Assistant

### Pattern Adherence
- **Follow existing patterns exactly** - MotionEye has consistent patterns for libcam controls
- **Reference brightness/contrast/ISO** - these are perfect templates for AWB implementation
- **Maintain consistency** - use same naming conventions, indentation, comment style

### Hot-Reload Functionality
- All AWB controls must have `class="hot-reload"` in HTML
- Hot-reload mapping in main.js enables instant updates
- Motion backend already supports hot-reload for all AWB parameters

### UI/UX Considerations
- **AWB Enable checkbox** - master switch for auto vs manual
- **AWB Mode dropdown** - preset lighting modes for convenience
- **Colour Temp slider** - manual Kelvin adjustment when AWB off
- **Gain sliders** - fine-grained manual control when AWB off
- **Lock checkbox** - freeze current WB for scene consistency

### Testing Strategy
1. Implement all code changes first
2. Restart MotionEye service
3. Open browser console for error checking
4. Test each control individually
5. Verify hot-reload with live stream visible
6. Test persistence by restarting MotionEye

### Questions to Ask User
Before implementation, clarify:
- Should AWB mode show icons/colors for visual feedback?
- Should colour temp slider show Kelvin value in real-time?
- Should there be presets for common colour temperatures (2700K, 5500K, 6500K)?
- Should gain sliders be linked (maintain ratio when one changes)?

---

*This guide is designed to be comprehensive yet focused, providing all necessary context for successful implementation while maintaining consistency with existing MotionEye patterns.*
