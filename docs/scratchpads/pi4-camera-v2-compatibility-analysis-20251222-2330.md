# Pi 4 + Camera v2 Compatibility Analysis

**Date**: 2025-12-22 23:30
**Purpose**: Analysis of potential gaps when running MotionEye (updated for Pi 5 + Camera v3) on Pi 4 with Camera v2

---

## Executive Summary

The codebase was updated specifically for Pi 5 + Camera v3 (libcamera/IMX708). While backward compatibility was preserved conceptually, several gaps exist for Pi 4 + Camera v2 (IMX219) operation:

### High Priority Issues

1. **libcamera on Pi 4 Bookworm not validated** - Code assumes if `rpicam-hello` exists, everything works
2. **MMAL fallback path untested** - Legacy path for Pi 4 on Bullseye may have regressions
3. **Configuration migration missing** - No upgrade path from MMAL → libcamera configs
4. **Error visibility poor** - All camera detection failures logged at DEBUG level only

### Medium Priority Issues

5. **Resolution defaults assume Camera v3** - 1920x1080 default may be inappropriate for v2
6. **Cache invalidation missing** - Tool detection caches never refresh after OS changes
7. **Stream port migration silent** - Motion 5.0 removes `stream_port`; old configs break silently

### Low Priority (Already Working)

- Sensor-specific autofocus detection (IMX219 correctly excluded)
- UI capability-based hiding (autofocus controls hidden for v2)
- Hardware codec detection (v4l2m2m vs OMX handled correctly)

---

## Detailed Findings

### 1. Camera Detection Paths

Three detection mechanisms exist:
- **libcamera** (rpicamctl.py) - Pi 5 or any Pi on Bookworm
- **MMAL** (mmalctl.py) - Pi 4 and earlier on Bullseye
- **V4L2** (v4l2ctl.py) - Generic USB cameras

**Decision logic** (`pictl.py:116-157`):
```python
if rpicamctl.is_rpicam_available():  # rpicam-hello exists?
    return 'libcamera'
elif get_pi_model():  # Is this a Pi?
    return 'mmal'
else:
    return 'v4l2'
```

**Gap**: No validation that libcamera actually works with the connected camera.

### 2. Sensor Handling

Sensors correctly mapped:
- `imx708` → Camera Module 3 (autofocus: YES)
- `imx219` → Camera Module 2 (autofocus: NO)

**Working correctly**: Autofocus UI hidden for Camera v2 users.

### 3. Configuration Type Detection

Camera type inferred from config fields:
- `libcam_device` → libcamera
- `mmalcam_name` → MMAL
- `videodevice` → V4L2
- `netcam_url` → Network

**Gap**: No migration logic when user upgrades OS (Bullseye → Bookworm).

### 4. Motion 5.0 Changes

Stream parameters removed in Motion 5.0:
- `stream_port` → Now via webcontrol
- `stream_localhost` → Removed
- `stream_auth_method` → Removed

**Gap**: Old configs silently drop these parameters.

### 5. Default Values

libcamera cameras get:
- Resolution: 1920x1080 (may be overkill for v2)
- libcam_brightness: 0.0
- libcam_contrast: 1.0
- libcam_iso: 100

**Gap**: No sensor-specific defaults (v2 vs v3).

---

## Test Matrix

| Platform | OS | Camera | Interface | Status |
|----------|-----|--------|-----------|--------|
| Pi 5 | Bookworm | v3 (IMX708) | libcamera | ✅ Tested |
| Pi 5 | Bookworm | v2 (IMX219) | libcamera | ❓ Unknown |
| Pi 4 | Bookworm | v3 (IMX708) | libcamera | ❓ Unknown |
| Pi 4 | Bookworm | v2 (IMX219) | libcamera | ❓ Unknown |
| Pi 4 | Bullseye | v2 (IMX219) | MMAL | ❓ Unknown |
| Pi 4 | Bullseye | v3 (IMX708) | MMAL | ❓ Unknown |

---

## Files Requiring Review/Updates

### Critical Files

1. **motioneye/controls/rpicamctl.py** (418 lines)
   - Camera enumeration and capability detection
   - Sensor name mapping
   - Lines 200-301: Device enumeration

2. **motioneye/controls/mmalctl.py** (52 lines)
   - MMAL fallback detection
   - vcgencmd dependency
   - Lines 28-52: Detection method

3. **motioneye/controls/pictl.py** (178 lines)
   - Platform detection
   - Interface selection logic
   - Lines 116-157: Decision tree

4. **motioneye/config/camera/crud.py** (~150 lines)
   - Camera add flow
   - Lines 106-121: libcamera vs MMAL setup

5. **motioneye/config/defaults.py** (~200 lines)
   - Default value assignment
   - Lines 187-201: Codec defaults
   - Resolution defaults

6. **motioneye/config/camera/converters.py** (1508 lines)
   - UI ↔ Motion config conversion
   - Lines 1038-1067: Autofocus detection

### Supporting Files

7. **motioneye/config/adaptation.py**
   - Motion version option mappings
   - Lines 199-209: Motion 5.0 removed options

8. **motioneye/config/camera/constants.py** (299 lines)
   - Hot-reload parameters
   - Capability to UI mappings

---

## Recommended Fixes

### Phase 1: Robustness

1. Add libcamera validation in `rpicamctl.py` - actually try to enumerate before declaring success
2. Improve error logging - upgrade DEBUG to WARNING for detection failures
3. Add cache invalidation hooks in `pictl.py` and `rpicamctl.py`

### Phase 2: Backwards Compatibility

4. Add MMAL config migration logic in `converters.py`
5. Add sensor-specific defaults in `defaults.py`
6. Validate Motion 5.0 stream port handling in `adaptation.py`

### Phase 3: Testing

7. Create test matrix for Pi 4 + Camera v2
8. Add integration tests for MMAL path
9. Document known limitations

---

## Questions for User

1. Is Pi 4 on Bookworm (libcamera) or Bullseye (MMAL) the priority?
2. Should we support configuration migration from old MotionEye versions?
3. What resolution should be default for Camera v2? (Current: 1920x1080)
