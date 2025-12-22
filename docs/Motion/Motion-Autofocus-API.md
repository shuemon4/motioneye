# Motion Autofocus Controls - API Reference

**Date:** 2025-12-21
**Motion Version:** 4.7+ (with libcamera 0.5.2+)
**Target Hardware:** Raspberry Pi 5 with Camera Module v3 (IMX708)

---

## Overview

Motion now supports comprehensive autofocus (AF) controls for Raspberry Pi cameras via libcamera. This document provides AI-readable specifications for integrating autofocus features into MotionEye or other automation systems.

**Key Features:**
- ✅ Multiple AF modes (Manual, Auto, Continuous)
- ✅ Manual lens position control (dioptres)
- ✅ AF range and speed configuration
- ✅ Multi-window focus areas (up to 4 windows)
- ✅ Hot-reload via HTTP API (no restart required)
- ✅ Read-only status monitoring (AfState, AfPauseState)

---

## Configuration Parameters

### libcam_af_mode
**Type:** Integer
**Range:** 0-2
**Default:** 0 (Manual)
**Hot-reload:** Yes

Controls the autofocus operating mode.

**Values:**
- `0` = **Manual** - Fixed focus at specified lens position
- `1` = **Auto** - Single-shot autofocus (requires trigger)
- `2` = **Continuous** - Continuous autofocus tracking

**Configuration File:**
```conf
libcam_af_mode 2
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
```

**Use Cases:**
- Manual (0): Static surveillance, fixed distance subjects
- Auto (1): Controlled focus on demand, energy efficient
- Continuous (2): Motion tracking, variable distance subjects

---

### libcam_lens_position
**Type:** Float
**Range:** 0.0 - 15.0 dioptres
**Default:** 0.0 (infinity focus)
**Hot-reload:** Yes
**Constraint:** Only applies when `libcam_af_mode = 0` (Manual)

Sets the lens focus position in dioptres. Higher values focus closer.

**Dioptre to Distance Conversion:**
- `0.0` = Infinity (∞)
- `0.333` = 3 meters
- `0.5` = 2 meters
- `1.0` = 1 meter
- `2.0` = 0.5 meters (50cm)
- `10.0` = 0.1 meters (10cm - macro range)

**Configuration File:**
```conf
libcam_af_mode 0
libcam_lens_position 0.5
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=0"
curl "http://localhost:8080/1/config/set?libcam_lens_position=0.5"
```

**Important:** LensPosition is ignored when AF mode is Auto or Continuous.

---

### libcam_af_range
**Type:** Integer
**Range:** 0-2
**Default:** 0 (Normal)
**Hot-reload:** Yes

Limits the autofocus search range for faster focusing.

**Values:**
- `0` = **Normal** - Standard range (30cm to infinity)
- `1` = **Macro** - Close-up focus (10cm to 50cm)
- `2` = **Full** - Full range (10cm to infinity)

**Configuration File:**
```conf
libcam_af_mode 2
libcam_af_range 1
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_range=1"
```

**Use Cases:**
- Normal (0): Most surveillance scenarios
- Macro (1): Close-up monitoring (license plates, small objects)
- Full (2): Variable distance scenes, sacrifice speed for range

---

### libcam_af_speed
**Type:** Integer
**Range:** 0-1
**Default:** 0 (Normal)
**Hot-reload:** Yes

Controls autofocus speed priority.

**Values:**
- `0` = **Normal** - Balanced speed and accuracy
- `1` = **Fast** - Prioritize speed over accuracy

**Configuration File:**
```conf
libcam_af_mode 2
libcam_af_speed 1
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_speed=1"
```

**Use Cases:**
- Normal (0): General surveillance
- Fast (1): Tracking fast-moving objects

---

## Advanced Features

### Multi-Window Focus Areas

Control which areas of the frame are used for autofocus metering. Requires `AfMetering = 1` (Windows mode) in `libcam_params`.

**Format:** `x|y|width|height[;x|y|width|height;...]`
**Max Windows:** 4
**Coordinate Space:** ScalerCropMaximum (pixels)

**Configuration File:**
```conf
# Single center window
libcam_params AfMetering=1,AfWindows=800|450|320|180

# Multiple windows (left and right sides)
libcam_params AfMetering=1,AfWindows=100|100|200|200;1720|100|200|200
```

**Web API:**
```bash
# Note: AfWindows is part of libcam_params, not hot-reloadable via individual API
# Must restart camera or use libcam_params parameter
```

**Use Cases:**
- Center window: Subject always in center
- Multiple windows: Track multiple subjects
- Edge windows: Ignore foreground distractions

---

### AF Trigger (Auto Mode Only)

When in Auto mode (`libcam_af_mode = 1`), trigger a focus scan programmatically.

**Method:** Call `trigger_libcam_af_scan()` via camera interface

**C++ API:**
```cpp
cam->trigger_libcam_af_scan();
```

**Python/MotionEye Integration:**
```python
# Via Motion web API - would require custom action endpoint
# Feature available in code, web endpoint TBD
```

---

## Read-Only Status Controls

These controls report camera state and **cannot be set** by the user.

### AfState
**Type:** Read-only Integer
**Values:**
- `0` = AfStateIdle - No autofocus activity
- `1` = AfStateScanning - Actively searching for focus
- `2` = AfStateFocused - Focus achieved
- `3` = AfStateFailed - Focus search failed

**Monitoring:**
```bash
# Not directly queryable via API (output-only control)
# Appears in Motion debug logs when enabled
```

### AfPauseState
**Type:** Read-only Integer
**Values:**
- `0` = AfPauseStateRunning - AF active
- `1` = AfPauseStatePausing - AF pausing
- `2` = AfPauseStatePaused - AF paused

**Warning:** Attempting to set these in `libcam_params` will generate a warning:
```
[WRN][VID] AfState is read-only (output control) - cannot be set
```

---

## HTTP API Reference

### Base URL
```
http://<motion_host>:<webcontrol_port>/<camera_id>/config/set
```

**Default:** `http://localhost:8080/1/config/set`

### Endpoint Parameters
- `<motion_host>`: Motion server IP/hostname
- `<webcontrol_port>`: Motion webcontrol_port (default 8080)
- `<camera_id>`: Camera number (1-based index)

### Set AF Mode
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=<value>"
```
**Parameters:**
- `value`: 0 (Manual), 1 (Auto), 2 (Continuous)

### Set Lens Position
```bash
curl "http://localhost:8080/1/config/set?libcam_lens_position=<value>"
```
**Parameters:**
- `value`: 0.0 to 15.0 (dioptres)

**Note:** Only effective when `libcam_af_mode=0`

### Set AF Range
```bash
curl "http://localhost:8080/1/config/set?libcam_af_range=<value>"
```
**Parameters:**
- `value`: 0 (Normal), 1 (Macro), 2 (Full)

### Set AF Speed
```bash
curl "http://localhost:8080/1/config/set?libcam_af_speed=<value>"
```
**Parameters:**
- `value`: 0 (Normal), 1 (Fast)

### Response Format
```json
{
  "status": "ok",
  "parameter": "libcam_af_mode",
  "value": "2"
}
```

**Errors:**
```json
{
  "status": "error",
  "message": "Invalid parameter value"
}
```

---

## Common Configuration Scenarios

### Scenario 1: Fixed Focus at 3 Meters
**Use Case:** Indoor hallway camera

```conf
libcam_af_mode 0
libcam_lens_position 0.333
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=0"
curl "http://localhost:8080/1/config/set?libcam_lens_position=0.333"
```

---

### Scenario 2: Continuous AF for Motion Detection
**Use Case:** Outdoor camera tracking moving subjects

```conf
libcam_af_mode 2
libcam_af_speed 1
libcam_af_range 0
```

**Web API:**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
curl "http://localhost:8080/1/config/set?libcam_af_speed=1"
curl "http://localhost:8080/1/config/set?libcam_af_range=0"
```

---

### Scenario 3: Macro Focus for License Plate Reading
**Use Case:** Close-up camera at parking entrance

```conf
libcam_af_mode 2
libcam_af_range 1
libcam_af_speed 0
```

**Configuration via libcam_params for focus window:**
```conf
libcam_params AfMetering=1,AfWindows=800|450|320|180
```

---

### Scenario 4: Energy-Efficient Auto Focus
**Use Case:** Battery-powered camera, focus on demand

```conf
libcam_af_mode 1
libcam_af_range 0
libcam_af_speed 0
```

**Trigger focus when motion detected:**
```python
# Python pseudo-code for MotionEye integration
def on_motion_detected():
    motion_client.trigger_af_scan(camera_id=1)
```

---

## MotionEye Integration Guidelines

### Configuration UI Mapping

**Recommended UI Elements:**

1. **AF Mode Dropdown**
   ```
   Label: "Autofocus Mode"
   Options:
     - Manual (Fixed Focus)
     - Auto (On Demand)
     - Continuous (Tracking)
   Default: Manual
   ```

2. **Lens Position Slider** (visible when AF Mode = Manual)
   ```
   Label: "Focus Distance"
   Range: 0.0 - 15.0
   Display: Convert dioptres to distance
     - 0.0 → "Infinity"
     - 0.333 → "3 meters"
     - 0.5 → "2 meters"
     - 1.0 → "1 meter"
     - 2.0 → "50 cm"
     - 10.0 → "10 cm"
   Default: 0.0
   ```

3. **AF Range Dropdown**
   ```
   Label: "Focus Range"
   Options:
     - Normal (30cm - ∞)
     - Macro (10cm - 50cm)
     - Full (10cm - ∞)
   Default: Normal
   ```

4. **AF Speed Toggle**
   ```
   Label: "Fast Autofocus"
   Type: Checkbox
   Default: Off
   ```

### State Management

**On Camera Start:**
1. Read current AF parameters from Motion config
2. Initialize UI elements with current values
3. Disable lens_position controls if AF mode ≠ Manual

**On Parameter Change:**
1. Validate parameter range
2. Send HTTP API request to Motion
3. Update UI to reflect new state
4. Show success/error notification

**Mutual Exclusivity:**
- When AF Mode changes to Auto or Continuous, disable lens position control
- When AF Mode changes to Manual, enable lens position control

### Error Handling

**Common Errors:**
```python
# Example error handling in MotionEye
def set_af_mode(camera_id, mode):
    try:
        response = requests.get(
            f"http://localhost:8080/{camera_id}/config/set",
            params={"libcam_af_mode": mode},
            timeout=5
        )
        if response.status_code == 200:
            return {"success": True, "mode": mode}
        else:
            return {"success": False, "error": "Invalid response"}
    except requests.Timeout:
        return {"success": False, "error": "Motion server timeout"}
    except requests.ConnectionError:
        return {"success": False, "error": "Cannot connect to Motion"}
```

**User Feedback:**
- ✅ Success: "Autofocus mode set to Continuous"
- ❌ Error: "Failed to update autofocus: Motion server not responding"
- ⚠️  Warning: "Lens position ignored (AF mode is not Manual)"

---

## Validation and Testing

### Parameter Validation

```python
def validate_af_mode(value):
    return value in [0, 1, 2]

def validate_lens_position(value):
    return 0.0 <= value <= 15.0

def validate_af_range(value):
    return value in [0, 1, 2]

def validate_af_speed(value):
    return value in [0, 1]
```

### Testing Checklist

- [ ] AF mode changes take effect without restart
- [ ] Lens position control disabled when mode ≠ Manual
- [ ] Lens position adjustments visible in camera output
- [ ] Continuous AF tracks moving objects
- [ ] AF range limits focus appropriately
- [ ] Fast AF speed improves tracking
- [ ] Multi-window AF focuses on specified areas
- [ ] Read-only controls generate warnings if set

---

## Backward Compatibility

**Legacy libcam_params syntax still works:**
```conf
# Old style (still supported)
libcam_params AfMode=2,AfRange=2,AfSpeed=1

# New style (preferred)
libcam_af_mode 2
libcam_af_range 2
libcam_af_speed 1
```

**Migration Strategy:**
1. Detect if Motion supports new AF parameters (version check)
2. Use new hot-reload API if available
3. Fall back to libcam_params if older Motion version
4. Document migration path for users

---

## Performance Considerations

**Resource Impact:**
- Manual mode: **Minimal** - No AF processing
- Auto mode: **Low** - AF only on trigger
- Continuous mode: **Moderate** - Constant AF processing

**Recommendations:**
- Use Manual mode when subjects at fixed distance
- Use Continuous mode only when necessary
- Limit AF windows to reduce processing
- Use Fast speed only for fast-moving subjects

---

## Troubleshooting

### Issue: Lens position has no effect
**Cause:** AF mode is not Manual
**Solution:** Set `libcam_af_mode = 0` before adjusting lens position

### Issue: Autofocus too slow
**Cause:** Normal speed, wide range
**Solution:** Set `libcam_af_speed = 1` and limit range

### Issue: Focus keeps hunting
**Cause:** Low light, low contrast scene
**Solution:** Switch to Manual mode, set fixed focus

### Issue: Warning about AfState/AfPauseState
**Cause:** Attempting to set read-only controls
**Solution:** Remove from libcam_params, these are output-only

---

## Reference Implementation

### Python MotionEye Integration Example

```python
class MotionAutofocusControl:
    def __init__(self, motion_host, camera_id, webcontrol_port=8080):
        self.base_url = f"http://{motion_host}:{webcontrol_port}/{camera_id}/config/set"

    def set_mode(self, mode):
        """
        Set autofocus mode
        mode: 0 (Manual), 1 (Auto), 2 (Continuous)
        """
        if mode not in [0, 1, 2]:
            raise ValueError("Invalid AF mode")
        return self._set_param("libcam_af_mode", mode)

    def set_lens_position(self, dioptres):
        """
        Set lens position in dioptres (0.0 - 15.0)
        Only effective when mode = Manual
        """
        if not 0.0 <= dioptres <= 15.0:
            raise ValueError("Lens position out of range")
        return self._set_param("libcam_lens_position", dioptres)

    def set_range(self, range_mode):
        """
        Set AF range
        range_mode: 0 (Normal), 1 (Macro), 2 (Full)
        """
        if range_mode not in [0, 1, 2]:
            raise ValueError("Invalid AF range")
        return self._set_param("libcam_af_range", range_mode)

    def set_speed(self, speed):
        """
        Set AF speed
        speed: 0 (Normal), 1 (Fast)
        """
        if speed not in [0, 1]:
            raise ValueError("Invalid AF speed")
        return self._set_param("libcam_af_speed", speed)

    def _set_param(self, param, value):
        """Internal: Send parameter to Motion API"""
        import requests
        try:
            response = requests.get(
                self.base_url,
                params={param: value},
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error setting {param}: {e}")
            return False

    @staticmethod
    def dioptres_to_distance(dioptres):
        """Convert dioptres to human-readable distance"""
        if dioptres == 0:
            return "Infinity"
        distance_m = 1.0 / dioptres
        if distance_m >= 1.0:
            return f"{distance_m:.1f} meters"
        else:
            return f"{distance_m * 100:.0f} cm"

# Usage example
af = MotionAutofocusControl("192.168.1.176", camera_id=1)

# Set continuous AF for motion tracking
af.set_mode(2)  # Continuous
af.set_speed(1)  # Fast
af.set_range(0)  # Normal

# Set manual focus at 2 meters
af.set_mode(0)  # Manual
af.set_lens_position(0.5)  # 2 meters
```

---

## Appendix: Motion Log Messages

**Successful AF Control Application:**
```
[DBG][VID] Hot-reload: AF mode set to 2 (Continuous)
[DBG][VID] Applied controls: brightness=0.00, contrast=1.00, iso=100, awb_enable=true, awb_mode=0, af_mode=2, lens_pos=0.00
```

**Lens Position Change:**
```
[DBG][VID] Hot-reload: Lens position set to 0.50 dioptres (focus at 2.00m)
```

**AF Range Change:**
```
[DBG][VID] Hot-reload: AF range set to 1 (Macro)
```

**Read-Only Control Warning:**
```
[WRN][VID] AfState is read-only (output control) - cannot be set
```

---

## Version History

**v1.0 - 2025-12-21**
- Initial implementation
- Manual, Auto, Continuous AF modes
- Lens position control (0-15 dioptres)
- AF range and speed configuration
- Multi-window focus areas
- Hot-reload HTTP API
- Read-only status monitoring

---

## Credits

**Implementation:** Claude Code
**Testing:** Raspberry Pi 5 + Camera Module v3 (IMX708)
**libcamera Version:** 0.5.2
**Motion Version:** 4.7+

**Related Documentation:**
- Motion Implementation Plan: `doc/plans/20251221-autofocus-implementation-plan.md`
- libcamera Controls: https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
