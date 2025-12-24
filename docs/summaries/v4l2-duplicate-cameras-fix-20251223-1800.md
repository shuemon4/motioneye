# V4L2 Camera Dropdown Duplicates - Fix Summary

**Date**: 2025-12-23 18:00
**Issue**: Camera dropdown showing 15 duplicate entries for system devices
**Status**: ✅ RESOLVED

---

## Problem

When adding a new V4L2 camera in MotionEye, the dropdown showed:
- 5 duplicate "bcm2835-codec-decode" entries
- 10 duplicate "bcm2835-isp" entries
- (Pi 5 would have shown 18x "pispbe", 8x "rp1-cfe", etc.)

These are NOT cameras - they are system hardware accelerators (video decoders, encoders, ISP).

---

## Root Cause

1. `v4l2ctl.list_devices()` returned every `/dev/videoX` device node as a separate camera
2. Hardware accelerators have multiple device nodes (e.g., bcm2835-isp has 10 nodes)
3. Each node was added to the camera list with the same name
4. No filtering existed for non-camera devices

---

## Solution Implemented

### Code Changes: `motioneye/controls/v4l2ctl.py`

1. **Added system device blocklist** (lines 40-49):
   ```python
   _NON_CAMERA_DEVICES = {
       'bcm2835-codec',      # Decoder/encoder
       'bcm2835-isp',        # Image signal processor
       'pispbe',             # Pi 5 ISP backend
       'rp1-cfe',            # Pi 5 camera frontend
       'rpi-hevc-dec',       # HEVC decoder
       'unicam',             # Camera interface
   }
   ```

2. **Added filtering function** (lines 52-70):
   ```python
   def _is_system_device(name):
       """Check if device is a system video processor, not a camera."""
       if not name:
           return True
       name_lower = name.lower()
       for prefix in _NON_CAMERA_DEVICES:
           if name_lower.startswith(prefix):
               return True
       return False
   ```

3. **Modified `list_devices()`** (lines 81-128):
   - Skip system devices
   - Deduplicate by camera name (keep first device only)
   - Added debug logging for filtered devices

---

## Testing Results

### Pi 4 (192.168.1.246)
**Before**: 15 duplicate entries
**After**: Empty list (no USB cameras connected)

```
DEBUG:root:skipping system device bcm2835-codec-decode: /dev/video10
DEBUG:root:skipping system device bcm2835-codec-decode: /dev/video11
...
DEBUG:root:skipping system device unicam: /dev/video0
DEBUG:root:skipping system device rpi-hevc-dec: /dev/video19
```

All 20 system devices correctly filtered out.

### Pi 5 (192.168.1.176)
**Before**: Would show 26+ duplicate entries
**After**: Empty list (no USB cameras connected)

```
DEBUG:root:skipping system device pispbe: /dev/video20
DEBUG:root:skipping system device pispbe: /dev/video21
...
DEBUG:root:skipping system device rp1-cfe: /dev/video0
DEBUG:root:skipping system device rpi-hevc-dec: /dev/video19
```

All 29 system devices correctly filtered out.

---

## Expected Behavior

### V4L2 Camera Dropdown (After Fix)
- **Empty** if no USB cameras connected
- Shows **only USB webcams** if connected (e.g., "USB Camera", device-specific names)
- **Never** shows system accelerators
- **Never** shows CSI cameras (those use libcamera/rpicam protocol)

### On Pi 4/5 with 64-bit OS
- **V4L2 protocol**: USB webcams only
- **libcamera/rpicam protocol**: CSI cameras (Pi Camera Module)
- Clear separation between protocols

---

## Files Modified

1. `/motioneye/controls/v4l2ctl.py`
   - Added `_NON_CAMERA_DEVICES` constant
   - Added `_is_system_device()` function
   - Modified `list_devices()` to filter and deduplicate

---

## Benefits

1. **Eliminates confusion**: Users no longer see meaningless duplicate entries
2. **Prevents errors**: Users can't accidentally select non-functional "cameras"
3. **Clean UI**: Dropdown only shows actual camera options
4. **Future-proof**: Blocklist can be extended for new hardware accelerators
5. **Efficient**: Deduplication prevents redundant entries even for valid cameras

---

## Related Documentation

- Plan: `docs/plans/v4l2-duplicate-cameras-fix-20251223-1745.md`
- Issue: Screenshot in `docs/troubleshooting/Screenshot 2025-12-23 at 4.33.10 PM.png`

---

## Deployment Status

- ✅ Pi 4 (192.168.1.246): Deployed and tested
- ✅ Pi 5 (192.168.1.176): Deployed and tested
- ✅ Code committed to `feature/trixie-64bit-migration` branch
