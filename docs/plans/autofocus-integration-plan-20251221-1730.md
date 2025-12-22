# MotionEye Autofocus Integration Plan

**Date:** 2025-12-21
**Target:** Migrate autofocus controls to Motion 5.0+ hot-reloadable API
**Status:** Ready for implementation

---

## Executive Summary

Motion 5.0 introduced dedicated hot-reloadable autofocus parameters (`libcam_af_*`), replacing the old `libcam_control_item` approach. MotionEye's current autofocus implementation uses the legacy format, requiring a camera restart for every focus adjustment. This plan migrates to the new API for instant focus changes.

**Key Benefits:**
- ✅ Hot-reload autofocus changes (no restart required)
- ✅ New AF Speed control for faster tracking
- ✅ Consistent pattern with AWB controls (already migrated)
- ✅ Improved user experience for focus adjustments

---

## Current State Analysis

### What Exists

| Component | Status | Location |
|-----------|--------|----------|
| AF Mode UI | ✅ Exists | `_video_device.html:58-78` |
| AF Range UI | ✅ Exists | `_video_device.html` (depends on mode) |
| Lens Position UI | ✅ Exists | `_video_device.html` (depends on mode=0) |
| AF Speed UI | ❌ Missing | Not implemented |
| Hot-reload class | ❌ Missing | Controls lack `hot-reload` class |
| JS configPanelToDict | ✅ Exists | `main.js:2087-2090` |
| JS dictToConfigPanel | ✅ Exists | `main.js:2417-2419` |
| JS hot-reload mapping | ❌ Missing | Not in `hotReloadParams` object |
| Python converters | ⚠️ Old format | Uses `libcam_control_item` |
| HOT_RELOAD_PARAMS | ❌ Missing | AF params not listed |

### Current Flow (Broken)

```
UI Change → configPanelToDict → converters.py (libcam_control_item) → Motion (requires restart)
```

### Target Flow (Hot-Reload)

```
UI Change → configPanelToDict → converters.py (libcam_af_*) → motionctl.set_config_hot() → Motion (instant)
```

---

## Implementation Plan

### Phase 1: Constants and Registry Updates

**File:** `motioneye/config/camera/constants.py`

**Task 1.1:** Add AF parameters to `USED_MOTION_OPTIONS` (lines ~26-95)

```python
# Add to USED_MOTION_OPTIONS set:
'libcam_af_mode',
'libcam_lens_position',
'libcam_af_range',
'libcam_af_speed',
```

**Task 1.2:** Add AF parameters to `HOT_RELOAD_PARAMS` (lines ~114-230)

```python
# Add to HOT_RELOAD_PARAMS set after AWB params:
'libcam_af_mode',       # Autofocus mode (0=Manual, 1=Auto, 2=Continuous)
'libcam_lens_position', # Focus distance in dioptres (0.0-15.0)
'libcam_af_range',      # AF range (0=Normal, 1=Macro, 2=Full)
'libcam_af_speed',      # AF speed (0=Normal, 1=Fast)
```

---

### Phase 2: Defaults Update

**File:** `motioneye/config/defaults.py`

**Task 2.1:** Update default values in `_set_default_motion_camera()` (~lines 96-100)

```python
# Autofocus defaults (@ prefix for UI persistence)
data['@af_mode'] = 2          # Default: Continuous
data['@af_range'] = 0         # Default: Normal
data['@af_speed'] = 0         # Default: Normal speed (NEW)
data['@lens_position'] = 0.0  # Default: Infinity focus
```

---

### Phase 3: Converters Migration

**File:** `motioneye/config/camera/converters.py`

**Task 3.1:** Update `_camera_ui_to_motion()` (lines ~456-472)

Replace legacy `libcam_control_item` approach with dedicated parameters:

```python
# Autofocus controls - Motion 5.0+ has dedicated libcam_af_* parameters
if ui.get('supports_autofocus'):
    af_mode = int(ui.get('autofocus_mode', 2))
    af_range = int(ui.get('autofocus_range', 0))
    af_speed = int(ui.get('autofocus_speed', 0))  # NEW
    lens_pos = float(ui.get('lens_position', 0.0))

    # Store for UI persistence with @ prefix
    data['@af_mode'] = af_mode
    data['@af_range'] = af_range
    data['@af_speed'] = af_speed  # NEW
    data['@lens_position'] = lens_pos

    # Set dedicated libcam_af_* parameters (Motion 5.0+ hot-reloadable)
    data['libcam_af_mode'] = af_mode
    data['libcam_af_range'] = af_range
    data['libcam_af_speed'] = af_speed  # NEW
    data['libcam_lens_position'] = lens_pos

    # REMOVE: Old libcam_control_item approach
    # control_items.append(f'AfMode={af_mode}')
    # control_items.append(f'AfRange={af_range}')
    # if af_mode == 0:
    #     control_items.append(f'LensPosition={lens_pos}')
```

**Task 3.2:** Update `_camera_motion_to_ui()` (lines ~1046-1071)

```python
# Autofocus controls for Camera v3 (imx708)
supports_af = data.get('@supports_autofocus')
if supports_af is None:
    # ... existing detection logic ...
    pass

if supports_af:
    # Read from @ storage with fallback to Motion params
    ui['autofocus_mode'] = int(data.get('@af_mode', data.get('libcam_af_mode', 2)))
    ui['autofocus_range'] = int(data.get('@af_range', data.get('libcam_af_range', 0)))
    ui['autofocus_speed'] = int(data.get('@af_speed', data.get('libcam_af_speed', 0)))  # NEW
    ui['lens_position'] = float(data.get('@lens_position', data.get('libcam_lens_position', 0.0)))
    ui['supports_autofocus'] = True
```

---

### Phase 4: HTML Template Update

**File:** `motioneye/templates/partials/settings/_video_device.html`

**Task 4.1:** Add `hot-reload` class to existing AF controls

Update Autofocus Mode select (around line 64):
```html
<select class="styled device camera-config hot-reload" id="autofocusModeSelect">
```

Update Autofocus Range select:
```html
<select class="styled device camera-config hot-reload" id="autofocusRangeSelect">
```

Update Lens Position slider:
```html
<input type="text" class="range styled device camera-config hot-reload" id="lensPositionSlider">
```

**Task 4.2:** Add new AF Speed control (after AF Range, before Lens Position)

```html
<!-- Autofocus Speed (depends on mode != Manual) -->
<tr class="settings-item libcam-only" depends="autofocusMode!=0">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Autofocus Speed">Autofocus Speed</span>
    </td>
    <td class="settings-item-value">
        <select class="styled device camera-config hot-reload" id="autofocusSpeedSelect">
            <option value="0" data-i18n="Normal">Normal</option>
            <option value="1" data-i18n="Fast">Fast</option>
        </select>
    </td>
    <td><span class="help-mark" data-i18n-title="select autofocus speed; Fast prioritizes speed over accuracy for tracking moving subjects">?</span></td>
</tr>
```

**Task 4.3:** Add `libcam-only` class to all AF controls

Ensure all AF controls have the `libcam-only` class so they only appear for libcamera cameras.

---

### Phase 5: JavaScript Updates

**File:** `motioneye/static/js/main.js`

**Task 5.1:** Update `configPanelToDict()` (~line 2087-2090)

```javascript
'supports_autofocus': $('#autofocusModeSelect').parents('tr:eq(0)')[0] && !$('#autofocusModeSelect').parents('tr:eq(0)')[0]._hideNull,
'autofocus_mode': parseInt($('#autofocusModeSelect').val()) || 2,
'autofocus_range': parseInt($('#autofocusRangeSelect').val()) || 0,
'autofocus_speed': parseInt($('#autofocusSpeedSelect').val()) || 0,  // NEW
'lens_position': parseFloat($('#lensPositionSlider').val()) || 0.0,
```

**Task 5.2:** Update `dictToConfigPanel()` (~line 2417-2419)

```javascript
$('#autofocusModeSelect').val(dict['autofocus_mode'] != null ? dict['autofocus_mode'] : 2);
markHideIfNull(!dict['supports_autofocus'], 'autofocusModeSelect');
$('#autofocusRangeSelect').val(dict['autofocus_range'] != null ? dict['autofocus_range'] : 0);
markHideIfNull(!dict['supports_autofocus'], 'autofocusRangeSelect');
$('#autofocusSpeedSelect').val(dict['autofocus_speed'] != null ? dict['autofocus_speed'] : 0);  // NEW
markHideIfNull(!dict['supports_autofocus'], 'autofocusSpeedSelect');
$('#lensPositionSlider').val(dict['lens_position'] != null ? dict['lens_position'] : 0.0);
markHideIfNull(!dict['supports_autofocus'], 'lensPositionSlider');
```

**Task 5.3:** Add hot-reload parameter mapping (~line 5852-5858)

```javascript
// Autofocus hot-reload params (Motion 5.0+)
'autofocusModeSelect': 'libcam_af_mode',
'autofocusRangeSelect': 'libcam_af_range',
'autofocusSpeedSelect': 'libcam_af_speed',
'lensPositionSlider': 'libcam_lens_position'
```

---

### Phase 6: Validation and Edge Cases

**Task 6.1:** Mutual Exclusivity Logic

The UI already handles this via `depends` attribute:
- `depends="autofocusMode!=0"` - Show AF Range when NOT Manual
- `depends="autofocusMode!=0"` - Show AF Speed when NOT Manual
- `depends="autofocusMode=0"` - Show Lens Position when Manual

**Task 6.2:** Python Validation (in converters.py)

```python
def _validate_af_params(af_mode, af_range, af_speed, lens_pos):
    """Validate autofocus parameters before sending to Motion."""
    assert af_mode in [0, 1, 2], f"Invalid AF mode: {af_mode}"
    assert af_range in [0, 1, 2], f"Invalid AF range: {af_range}"
    assert af_speed in [0, 1], f"Invalid AF speed: {af_speed}"
    assert 0.0 <= lens_pos <= 15.0, f"Lens position out of range: {lens_pos}"
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `motioneye/config/camera/constants.py` | Add 4 AF params to USED_MOTION_OPTIONS and HOT_RELOAD_PARAMS |
| `motioneye/config/defaults.py` | Add `@af_speed` default |
| `motioneye/config/camera/converters.py` | Migrate from libcam_control_item to libcam_af_* |
| `motioneye/templates/partials/settings/_video_device.html` | Add hot-reload class, add AF Speed control |
| `motioneye/static/js/main.js` | Add AF Speed handling, add hot-reload mapping |

---

## Testing Checklist

### Unit Tests
- [ ] AF mode values validated (0, 1, 2)
- [ ] AF range values validated (0, 1, 2)
- [ ] AF speed values validated (0, 1)
- [ ] Lens position range validated (0.0-15.0)
- [ ] UI to Motion conversion produces correct params
- [ ] Motion to UI conversion reads correct values

### Integration Tests (Pi 5)
- [ ] AF mode changes take effect without restart
- [ ] AF range changes take effect without restart
- [ ] AF speed changes take effect without restart
- [ ] Lens position changes take effect without restart
- [ ] Lens position control disabled when mode ≠ Manual
- [ ] Continuous AF tracks moving objects
- [ ] Fast AF speed improves tracking performance
- [ ] Legacy configs migrate correctly

### UI Tests
- [ ] AF controls visible only for libcamera cameras
- [ ] AF controls visible only when camera supports autofocus
- [ ] AF Speed dropdown appears after selecting Auto or Continuous mode
- [ ] Lens Position slider appears only when Manual mode selected
- [ ] Hot-reload feedback shown to user

---

## Rollback Plan

If issues arise:
1. Revert converters.py to use `libcam_control_item` format
2. Remove AF params from HOT_RELOAD_PARAMS
3. Remove `hot-reload` class from HTML controls
4. Camera restarts will be required for AF changes (original behavior)

---

## Implementation Order

1. **constants.py** - Add params to registries (enables hot-reload infrastructure)
2. **defaults.py** - Add AF speed default
3. **converters.py** - Migrate to new param format
4. **_video_device.html** - Add hot-reload class, add AF Speed control
5. **main.js** - Add JS handling for AF Speed, add hot-reload mapping
6. **Test on Pi 5** - Verify all AF changes work without restart

---

## Estimated Effort

| Phase | Description | Complexity |
|-------|-------------|------------|
| Phase 1 | Constants registry | Low |
| Phase 2 | Defaults update | Low |
| Phase 3 | Converters migration | Medium |
| Phase 4 | HTML template | Low |
| Phase 5 | JavaScript updates | Medium |
| Phase 6 | Testing | Medium |

**Total:** ~100 lines of code changes across 5 files

---

## References

- Motion Autofocus API: `docs/Motion/Motion-Autofocus-API.md`
- Motion Quick Reference: `docs/Motion/Motion-Autofocus-Quick-Reference.md`
- AWB Migration Pattern: Recent commits (cdff7532, a52cd6b8)
- libcamera Controls: https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
