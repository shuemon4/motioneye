# AWB Backend Update: Complete Implementation Guide

**Date:** 2025-12-21 (Updated)
**Status:** Motion Backend Updated - Ready for MotionEye Integration
**Motion Plan:** `motion/doc/plans/20251220-AWB-HotReload-Implementation.md`

---

## Summary

Motion backend now provides full AWB (Auto White Balance) hot-reload support with proper control interaction handling. This document provides complete implementation details for MotionEye UI integration.

---

## AWB Control Architecture

### Control Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│  libcam_awb_enable (master switch)                              │
│  ├── true: AWB algorithm active                                 │
│  │   └── libcam_awb_mode (0-7): Selects AWB preset             │
│  │       └── libcam_awb_locked: Freeze current WB values       │
│  │                                                              │
│  └── false: Manual WB control                                   │
│      ├── libcam_colour_temp (Kelvin method)                    │
│      │   OR                                                     │
│      └── libcam_colour_gain_r/b (Gains method)                 │
│          (mutually exclusive)                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Backend Behavior Rules

1. **AwbEnable controls mode**:
   - `awb_enable=true`: AWB preset modes active, manual controls ignored
   - `awb_enable=false`: Manual controls (temp or gains) active

2. **AwbMode clears manual controls** (except Custom):
   - Setting `awb_mode` to 0-6 clears `colour_temp`, `colour_gain_r`, `colour_gain_b`
   - Setting `awb_mode=7` (Custom) preserves manual values

3. **Temperature and Gains are mutually exclusive**:
   - Setting `colour_temp > 0` clears both gains to 0
   - Setting either gain > 0 clears `colour_temp` to 0

---

## Complete Parameter Reference

| Parameter | Type | Default | Range | Hot-Reload | Description |
|-----------|------|---------|-------|------------|-------------|
| `libcam_awb_enable` | bool | true | true/false | Yes | Master AWB switch |
| `libcam_awb_mode` | int | 0 | 0-7 | Yes | AWB preset mode |
| `libcam_awb_locked` | bool | false | true/false | Yes | Lock current WB values |
| `libcam_colour_temp` | int | 0 | 0-10000 | Yes | Manual Kelvin (0=disabled) |
| `libcam_colour_gain_r` | float | 0.0 | 0.0-8.0 | Yes | Manual red gain (0=auto) |
| `libcam_colour_gain_b` | float | 0.0 | 0.0-8.0 | Yes | Manual blue gain (0=auto) |

### AWB Mode Values

| Value | Name | Description | Approx Kelvin |
|-------|------|-------------|---------------|
| 0 | Auto | Automatic white balance | Varies |
| 1 | Incandescent | Warm/tungsten lighting | ~2700K |
| 2 | Tungsten | Similar to incandescent | ~3000K |
| 3 | Fluorescent | Cool white fluorescent | ~4000K |
| 4 | Indoor | General indoor lighting | ~4500K |
| 5 | Daylight | Outdoor daylight | ~5500K |
| 6 | Cloudy | Overcast/cloudy | ~6500K |
| 7 | Custom | Use manual ColourGains/ColourTemperature | N/A |

---

## API Endpoints

All endpoints support hot-reload (immediate effect, no restart required).

### Setting AWB Preset Mode

```bash
# Enable AWB and set to Daylight mode
curl -X POST "http://motion:7999/0/config/set?libcam_awb_enable=true&csrf_token=TOKEN"
curl -X POST "http://motion:7999/0/config/set?libcam_awb_mode=5&csrf_token=TOKEN"
# Backend clears: colour_temp=0, colour_gain_r=0, colour_gain_b=0
```

### Setting Manual Temperature

```bash
# Disable AWB, set colour temperature
curl -X POST "http://motion:7999/0/config/set?libcam_awb_enable=false&csrf_token=TOKEN"
curl -X POST "http://motion:7999/0/config/set?libcam_colour_temp=6500&csrf_token=TOKEN"
# Backend clears: colour_gain_r=0, colour_gain_b=0
```

### Setting Manual Gains

```bash
# Disable AWB, set manual gains
curl -X POST "http://motion:7999/0/config/set?libcam_awb_enable=false&csrf_token=TOKEN"
curl -X POST "http://motion:7999/0/config/set?libcam_colour_gain_r=1.5&csrf_token=TOKEN"
curl -X POST "http://motion:7999/0/config/set?libcam_colour_gain_b=1.2&csrf_token=TOKEN"
# Backend clears: colour_temp=0
```

### Lock Current White Balance

```bash
# Lock current values (works with AWB enabled or disabled)
curl -X POST "http://motion:7999/0/config/set?libcam_awb_locked=true&csrf_token=TOKEN"
```

---

## MotionEye UI Implementation

### Recommended UI Structure

```
┌─ White Balance ─────────────────────────────────────────────────┐
│                                                                  │
│  [✓] Auto White Balance                                         │
│                                                                  │
│  Mode: [Auto          ▼]                                        │
│         (Auto, Incandescent, Tungsten, Fluorescent,             │
│          Indoor, Daylight, Cloudy, Custom)                      │
│                                                                  │
│  [ ] Lock White Balance                                         │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  Manual Controls (only visible when AWB disabled)               │
│                                                                  │
│  ○ Colour Temperature                                           │
│    Temperature: [========|====] 6500K                           │
│                                                                  │
│  ○ Manual Gains                                                 │
│    Red Gain:   [=====|=======] 1.50                             │
│    Blue Gain:  [======|======] 1.20                             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### UI Visibility Rules

```javascript
// Pseudo-code for visibility logic
function updateAWBVisibility(config) {
    const awbEnabled = config.libcam_awb_enable;

    // Always visible
    show('libcam_awb_enable');
    show('libcam_awb_mode');
    show('libcam_awb_locked');

    // Only show manual controls when AWB is disabled
    setVisible('manual_controls_section', !awbEnabled);

    // Within manual controls, show based on which method is active
    const usingTemp = config.libcam_colour_temp > 0;
    const usingGains = config.libcam_colour_gain_r > 0 || config.libcam_colour_gain_b > 0;

    // Radio button selection for manual method
    setChecked('manual_temp_radio', usingTemp);
    setChecked('manual_gains_radio', usingGains || (!usingTemp && !usingGains));
}
```

### Hot-Reload Handler Updates

```javascript
// Handle mutual exclusivity in UI when backend clears values
function handleAWBHotReload(paramName, value) {
    // When AWB mode changes (except Custom), clear manual control displays
    if (paramName === 'libcam_awb_mode' && value !== 7) {
        setSliderValue('libcam_colour_temp', 0);
        setSliderValue('libcam_colour_gain_r', 0);
        setSliderValue('libcam_colour_gain_b', 0);
    }

    // When temperature set, clear gains display
    if (paramName === 'libcam_colour_temp' && parseFloat(value) > 0) {
        setSliderValue('libcam_colour_gain_r', 0);
        setSliderValue('libcam_colour_gain_b', 0);
    }

    // When gains set, clear temperature display
    if ((paramName === 'libcam_colour_gain_r' || paramName === 'libcam_colour_gain_b')
        && parseFloat(value) > 0) {
        setSliderValue('libcam_colour_temp', 0);
    }

    // Update visibility based on awb_enable
    if (paramName === 'libcam_awb_enable') {
        updateManualControlsVisibility(value === 'true' || value === '1');
    }
}
```

### Config Converters

Add to `motioneye/config/camera/converters.py`:

```python
# UI to Motion conversion
def _ui_to_motion_awb(ui_config):
    """Convert UI AWB settings to Motion config."""
    motion_config = {}

    motion_config['libcam_awb_enable'] = 'true' if ui_config.get('@awb_enable', True) else 'false'
    motion_config['libcam_awb_mode'] = str(ui_config.get('@awb_mode', 0))
    motion_config['libcam_awb_locked'] = 'true' if ui_config.get('@awb_locked', False) else 'false'
    motion_config['libcam_colour_temp'] = str(ui_config.get('@colour_temp', 0))
    motion_config['libcam_colour_gain_r'] = str(ui_config.get('@colour_gain_r', 0.0))
    motion_config['libcam_colour_gain_b'] = str(ui_config.get('@colour_gain_b', 0.0))

    return motion_config

# Motion to UI conversion
def _motion_to_ui_awb(motion_config):
    """Convert Motion AWB settings to UI config."""
    ui_config = {}

    ui_config['@awb_enable'] = motion_config.get('libcam_awb_enable', 'true') == 'true'
    ui_config['@awb_mode'] = int(motion_config.get('libcam_awb_mode', 0))
    ui_config['@awb_locked'] = motion_config.get('libcam_awb_locked', 'false') == 'true'
    ui_config['@colour_temp'] = int(motion_config.get('libcam_colour_temp', 0))
    ui_config['@colour_gain_r'] = float(motion_config.get('libcam_colour_gain_r', 0.0))
    ui_config['@colour_gain_b'] = float(motion_config.get('libcam_colour_gain_b', 0.0))

    return ui_config
```

---

## Files to Modify in MotionEye

| File | Changes |
|------|---------|
| `config/camera/constants.py` | Add 6 AWB params to USED_MOTION_OPTIONS |
| `config/defaults.py` | Add default values for AWB parameters |
| `config/camera/converters.py` | Add UI↔Motion conversions |
| `templates/partials/settings/_video_device.html` | Add AWB UI controls |
| `static/js/main.js` | Add value read/write, hot-reload handlers |

---

## Testing Checklist

### Hot-Reload Tests
- [ ] Change AWB mode while streaming → immediate color shift
- [ ] Toggle AWB enable → manual controls appear/disappear
- [ ] Set colour temperature → gains show as 0
- [ ] Set gains → temperature shows as 0
- [ ] Lock WB → values freeze

### Interaction Tests
- [ ] AWB enabled + change mode → stream color changes
- [ ] AWB disabled + set temp → stream responds
- [ ] AWB disabled + set gains → stream responds
- [ ] Switch from temp to gains → temp clears
- [ ] Switch from gains to temp → gains clear

### Edge Cases
- [ ] Set AWB mode to Custom (7) → manual controls preserved
- [ ] Set gain_r only → gain_b can be set independently
- [ ] Values persist across MotionEye restart
- [ ] Values persist across Motion restart

---

## Bug Fixes Applied in Motion

1. **webu_json.cpp:637** - Fixed wrong variable reference (used `libcam_colour_gain_r` instead of `_b`)

2. **libcam.cpp set_awb_mode()** - Now clears manual controls when switching to preset modes (0-6)

3. **libcam.cpp req_add()** - Manual controls only applied when `awb_enable=false`

4. **libcam.cpp config_controls()** - AWB controls now set at camera startup

---

## Reference: Existing Implementation Patterns

Follow the existing patterns for `libcam_brightness`, `libcam_contrast`, and `libcam_iso`:

- **HTML Template**: See brightness/contrast slider implementations in `_video_device.html`
- **JavaScript**: See hot-reload handling in `main.js` (search for `libcam_brightness`)
- **Constants**: See USED_MOTION_OPTIONS in `constants.py`
- **Converters**: See existing libcam parameter handling in `converters.py`

The AWB implementation guide at `docs/designs/20251220-awb-controls-implementation-guide.md` provides additional step-by-step details.
