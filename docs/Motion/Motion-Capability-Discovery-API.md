# Motion Camera Capability Discovery - API Reference

**Date:** 2025-12-22
**Motion Version:** 5.0+ (with libcamera 0.5.2+)
**Target Hardware:** Raspberry Pi with any libcamera-supported camera

---

## Overview

Motion now implements runtime camera capability discovery via the libcamera `camera->controls()` API. This allows MotionEye (and other UIs) to determine which controls a specific camera supports **at runtime**, rather than hardcoding camera model assumptions.

**Key Features:**
- ✅ Runtime detection of supported controls (no hardcoding camera models)
- ✅ `supportedControls` map in `/status.json` response
- ✅ `ignored` array in hot-reload responses when controls aren't supported
- ✅ Warning logs when unsupported controls are attempted
- ✅ Graceful degradation (camera still works, unsupported controls silently skipped)

**Why This Matters:**
- Pi Camera v2 (IMX219): No autofocus hardware → AF controls should be hidden
- Pi Camera v3 (IMX708): Full autofocus → All AF controls available
- Third-party cameras: Unknown capabilities → Runtime discovery required

---

## API Endpoints

### GET /status.json

Returns camera status **including `supportedControls` map**.

**Request:**
```bash
curl "http://localhost:8080/status.json"
```

**Response (Pi Camera v3):**
```json
{
  "version": "5.0.0",
  "status": {
    "count": 1,
    "cam1": {
      "name": "Camera 1",
      "id": 1,
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "detecting": true,
      "pause": false,
      "supportedControls": {
        "AfMode": true,
        "LensPosition": true,
        "AfTrigger": true,
        "AfRange": true,
        "AfSpeed": true,
        "AfMetering": true,
        "ExposureTime": true,
        "ExposureValue": true,
        "AnalogueGain": true,
        "AeEnable": true,
        "AeMeteringMode": true,
        "AeConstraintMode": true,
        "AeExposureMode": true,
        "AwbEnable": true,
        "AwbMode": true,
        "AwbLocked": true,
        "ColourGains": true,
        "ColourTemperature": true,
        "Brightness": true,
        "Contrast": true,
        "Saturation": true,
        "Sharpness": true,
        "DigitalGain": true,
        "ScalerCrop": true
      }
    }
  }
}
```

**Response (Pi Camera v2 - No Autofocus):**
```json
{
  "supportedControls": {
    "AfMode": false,
    "LensPosition": false,
    "AfTrigger": false,
    "AfRange": false,
    "AfSpeed": false,
    "AfMetering": false,
    "ExposureTime": true,
    "AnalogueGain": true,
    "AwbEnable": true,
    "Brightness": true,
    "Contrast": true
  }
}
```

---

### GET /{camera_id}/config/set?{param}={value}

Hot-reload API now returns `ignored` array when controls aren't supported.

**Request (Setting AF mode on camera that supports it):**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
```

**Response (Success):**
```json
{
  "status": "ok",
  "parameter": "libcam_af_mode",
  "old_value": "0",
  "new_value": "2",
  "hot_reload": true
}
```

**Request (Setting AF mode on camera WITHOUT autofocus):**
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
```

**Response (Success with ignored):**
```json
{
  "status": "ok",
  "parameter": "libcam_af_mode",
  "old_value": "0",
  "new_value": "2",
  "hot_reload": true,
  "ignored": ["libcam_af_mode"]
}
```

**Important:** The API returns HTTP 200 even when controls are ignored. Check the `ignored` array to determine if the control was actually applied.

---

## Control Name Mapping

Motion config parameters map to libcamera controls:

| Motion Parameter | libcamera Control | `supportedControls` Key |
|-----------------|-------------------|-------------------------|
| `libcam_af_mode` | AfMode | `AfMode` |
| `libcam_lens_position` | LensPosition | `LensPosition` |
| `libcam_af_trigger` | AfTrigger | `AfTrigger` |
| `libcam_af_range` | AfRange | `AfRange` |
| `libcam_af_speed` | AfSpeed | `AfSpeed` |
| `libcam_brightness` | Brightness | `Brightness` |
| `libcam_contrast` | Contrast | `Contrast` |
| `libcam_iso` | AnalogueGain | `AnalogueGain` |
| `libcam_awb_enable` | AwbEnable | `AwbEnable` |
| `libcam_awb_mode` | AwbMode | `AwbMode` |
| `libcam_awb_locked` | AwbLocked | `AwbLocked` |
| `libcam_colour_temp` | ColourTemperature | `ColourTemperature` |
| `libcam_colour_gain_r` | ColourGains | `ColourGains` |
| `libcam_colour_gain_b` | ColourGains | `ColourGains` |

---

## MotionEye Integration Guide

### 1. Fetch Capabilities on Camera Load

When loading camera settings in MotionEye, fetch `/status.json` and extract `supportedControls`:

```python
import requests

def get_camera_capabilities(motion_url: str, camera_id: int) -> dict:
    """Fetch supported controls for a camera from Motion."""
    response = requests.get(f"{motion_url}/status.json", timeout=5)
    response.raise_for_status()

    status = response.json()
    cam_key = f"cam{camera_id}"

    if cam_key in status.get("status", {}):
        return status["status"][cam_key].get("supportedControls", {})

    return {}
```

### 2. Conditionally Show/Hide UI Elements

```python
def should_show_autofocus_section(capabilities: dict) -> bool:
    """Determine if autofocus UI section should be shown."""
    return capabilities.get("AfMode", False)

def should_show_manual_focus_slider(capabilities: dict) -> bool:
    """Determine if manual focus slider should be shown."""
    return capabilities.get("LensPosition", False)

def should_show_awb_controls(capabilities: dict) -> bool:
    """Determine if AWB controls should be shown."""
    return capabilities.get("AwbEnable", False)
```

### 3. UI Rendering Logic

```python
def render_camera_settings(camera_id: int, capabilities: dict):
    """Render camera settings based on capabilities."""

    # Always show these (universally supported)
    render_brightness_slider()
    render_contrast_slider()

    # Conditionally show autofocus section
    if capabilities.get("AfMode"):
        render_autofocus_mode_dropdown()  # Manual, Auto, Continuous

        if capabilities.get("AfRange"):
            render_focus_range_dropdown()  # Normal, Macro, Full

        if capabilities.get("AfSpeed"):
            render_focus_speed_dropdown()  # Normal, Fast

        if capabilities.get("AfTrigger"):
            render_trigger_focus_button()  # One-shot focus

    # Conditionally show manual focus (even if no AF)
    if capabilities.get("LensPosition"):
        render_lens_position_slider()  # 0.0 - 15.0 dioptres

    # Conditionally show AWB controls
    if capabilities.get("AwbEnable"):
        render_awb_toggle()

        if capabilities.get("AwbMode"):
            render_awb_mode_dropdown()

        if capabilities.get("ColourTemperature"):
            render_colour_temp_slider()
```

### 4. Handle Ignored Controls in Hot-Reload Response

```python
def apply_camera_setting(motion_url: str, camera_id: int,
                         param: str, value: str) -> tuple[bool, list]:
    """Apply a camera setting and return success + ignored list."""
    response = requests.get(
        f"{motion_url}/{camera_id}/config/set?{param}={value}",
        timeout=5
    )
    response.raise_for_status()

    result = response.json()
    success = result.get("status") == "ok"
    ignored = result.get("ignored", [])

    if ignored:
        # Log or display warning to user
        print(f"Warning: Controls ignored by camera: {ignored}")

    return success, ignored
```

---

## Camera Compatibility Matrix

| Camera Model | AfMode | LensPosition | AfTrigger | ExposureTime | AwbEnable |
|--------------|--------|--------------|-----------|--------------|-----------|
| Pi Camera v2 (IMX219) | ❌ | ❌ | ❌ | ✅ | ✅ |
| Pi Camera v3 (IMX708) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pi Camera v3 Wide | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pi HQ Camera (IMX477) | ❌ | ✅* | ❌ | ✅ | ✅ |
| Pi Global Shutter | ❌ | ❌ | ❌ | ✅ | ✅ |
| Arducam 64MP | ✅ | ✅ | ✅ | ✅ | ✅ |

*IMX477 supports manual focus via lens adapter, not autofocus

**Important:** Don't hardcode this table! Always use runtime capability discovery via `/status.json`. Third-party cameras and future models may have different capabilities.

---

## Motion Log Messages

Motion logs capability information at startup:

**Pi Camera v3 (with AF):**
```
[NTC] Camera capability discovery: 42 controls available
[NTC]   Autofocus (AfMode): SUPPORTED
[NTC]   Manual focus (LensPosition): SUPPORTED
[NTC]   Focus trigger (AfTrigger): SUPPORTED
[NTC]   Focus range (AfRange): SUPPORTED
[NTC]   Focus speed (AfSpeed): SUPPORTED
[NTC]   Exposure control: SUPPORTED
[NTC]   Analogue gain (ISO): SUPPORTED
[NTC]   Auto white balance: SUPPORTED
```

**Pi Camera v2 (no AF):**
```
[NTC] Camera capability discovery: 38 controls available
[NTC]   Autofocus (AfMode): not available
[NTC]   Manual focus (LensPosition): not available
[NTC]   Exposure control: SUPPORTED
[NTC]   Analogue gain (ISO): SUPPORTED
[NTC]   Auto white balance: SUPPORTED
```

**When unsupported control is set:**
```
[WRN] libcam_af_mode ignored: camera does not support autofocus
[WRN] libcam_lens_position ignored: camera does not support manual focus
```

---

## Error Handling

### Control Not Supported

**Behavior:** Motion accepts the config/API call but ignores the unsupported control.

**Detection:**
1. Check `ignored` array in hot-reload response
2. Check Motion logs for `[WRN] ... ignored:` messages
3. Pre-check `supportedControls` before showing UI elements

### Camera Not Using libcamera

**Behavior:** `supportedControls` will be absent from `/status.json` response.

**Detection:**
```python
def is_libcamera_camera(status_response: dict, camera_id: int) -> bool:
    """Check if camera is using libcamera (has capability discovery)."""
    cam_key = f"cam{camera_id}"
    cam_status = status_response.get("status", {}).get(cam_key, {})
    return "supportedControls" in cam_status
```

**Handling:** For non-libcamera cameras (V4L2, network), show all controls and let the user discover what works.

---

## Best Practices

1. **Always fetch capabilities before rendering settings UI**
   - Call `/status.json` when camera settings page loads
   - Cache capabilities (they don't change during runtime)

2. **Hide unsupported controls, don't just disable them**
   - Users shouldn't see autofocus options on cameras without AF
   - Reduces confusion and support requests

3. **Check `ignored` array after hot-reload calls**
   - Even if you pre-check capabilities, verify the control was applied
   - Handle edge cases (camera reconnect, config mismatch)

4. **Don't hardcode camera model assumptions**
   - Third-party modules may have different capabilities
   - Future cameras may add/remove features
   - Always use runtime discovery

5. **Graceful fallback for older Motion versions**
   - If `supportedControls` is missing, show all controls
   - Older Motion versions don't have capability discovery

---

## Version History

| Motion Version | Capability Discovery Feature |
|---------------|------------------------------|
| < 5.0 | Not available - all controls blindly set |
| 5.0+ | Full capability discovery via `/status.json` |
| 5.0+ | `ignored` array in hot-reload responses |

---

## Related Documentation

- [Motion-Autofocus-API.md](./Motion-Autofocus-API.md) - Detailed autofocus controls
- [Motion-Autofocus-Quick-Reference.md](./Motion-Autofocus-Quick-Reference.md) - Quick reference for AF
- [Motion Implementation Plan](../../../motion/doc/plans/20251222-1400-Camera-Capability-Discovery.md) - Full implementation details
