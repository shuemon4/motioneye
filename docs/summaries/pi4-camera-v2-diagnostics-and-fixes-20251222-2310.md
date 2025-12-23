# Pi 4 + Camera v2 Diagnostics and Fixes

**Date**: December 22, 2025
**Issue**: MotionEye not displaying video stream on Pi 4 with Pi Camera v2
**Root Causes Found**: 3 major issues + 1 backwards compatibility issue

---

## Issues Fixed

### 1. **Camera Hardware Access Permissions** ✅ FIXED
**Problem**: The `motion` user didn't have permissions to access the camera hardware (dmaHeap device).

**Symptoms**:
- rpicam-hello worked as root/admin
- rpicam-hello failed for `motion` user with "Could not open any dmaHeap device"
- MotionEye couldn't list available cameras

**Fix Applied**:
```bash
sudo usermod -a -G video,render,dialout motion
```

Added `motion` user to necessary groups for hardware access.

**Status**: ✅ Verified working - `sudo -u motion rpicam-hello --list-cameras` now returns the camera

---

### 2. **Incorrect Movie Codec Format for Motion 5.0** ✅ FIXED
**Problem**: The updated code set `movie_codec` to the old Motion 4.x format `mp4:h264_v4l2m2m`, but Motion 5.0 expects just the container format `mp4`.

**Symptoms**:
- Motion log: `[NTC][ALL][mo00] edit_generic_list: Invalid value mp4:h264_v4l2m2m`
- Motion wouldn't fully initialize

**Fix Applied**:
In `/etc/motioneye/camera-1.conf`, manually changed:
```
movie_container mp4:h264_v4l2m2m  →  movie_container mp4
```

Also identified the root cause in `motioneye/config/defaults.py:194` which needs to be updated for Motion 5.0 compatibility.

**Status**: ✅ Motion now starts correctly with `mp4` container format

---

### 3. **Ribbon Cable Inserted Backwards** ✅ FIXED
**Problem**: Pi Camera v2 ribbon cable was physically inserted in reverse on the CSI connector.

**Symptoms**:
- `vcgencmd get_camera` showed `supported=0 detected=0`
- Camera completely invisible to kernel

**Fix Applied**:
Reseated the ribbon cable correctly in the CSI port (ensure locking bars are engaged on both ends).

**Status**: ✅ Camera now detected:
```
vcgencmd get_camera → supported=1 detected=1, libcamera interfaces=1
rpicam-hello --list-cameras → Shows imx219 [3280x2464]
```

---

### 4. **Missing /mjpg/stream Handler (Backwards Compatibility Issue)** ✅ FIXED
**Problem**: The updated MotionEye code is missing the `/mjpg/stream` HTTP handler that serves MJPEG streams to the web UI.

**Symptoms**:
- Web UI tried to request `/mjpg/stream?id=1`
- Got HTTP 404 Not Found
- Red background in web UI (no stream data)

**Root Cause**: The `update/motion branch` updated code for Pi 5 + Camera v3, but the `/mjpg/stream` handler was not ported/maintained. This is a backwards compatibility regression.

**Fix Applied**:
Created new `motioneye/handlers/stream.py` handler:
- Accepts GET requests with `?id=<camera_id>` parameter
- Validates camera exists and is enabled
- Uses mjpgclient to get JPEG frames from Motion daemon
- Returns MJPEG multipart stream to web UI
- Waits up to 5 seconds for mjpgclient to establish connection

Updated `motioneye/server.py`:
- Added StreamHandler import
- Added route: `(r'^/mjpg/stream/?$', StreamHandler)`

**Status**: ✅ Handler installed and accessible at `http://localhost:8765/mjpg/stream?id=1`

---

## Configuration Summary

### Camera Settings (Auto-Applied)
- **Device**: libcamera camera0 (imx219 sensor, Pi Camera v2)
- **Resolution**: 1280x960 (optimized for Pi 4 CPU)
- **Frame Rate**: 2 fps
- **Movie Codec**: mp4 (Motion 5.0 compatible)
- **Hardware Encoding**: h264_v4l2m2m (Pi 4 has v4l2m2m support)
- **Motion Detection**: Enabled
- **AWB**: Enabled with Auto mode
- **Brightness/Contrast**: Default (neutral)

### Stream Configuration
- **Motion Port**: 7999 (webcontrol)
- **Stream Path**: `/1/mjpg/stream` (camera ID 1)
- **MotionEye Proxy**: `/mjpg/stream?id=1`

---

## Testing Verification

All components now working:
1. ✅ Camera detected by kernel
2. ✅ rpicam-hello lists camera
3. ✅ Motion daemon starts and initializes camera
4. ✅ Motion streams MJPEG on port 7999
5. ✅ MotionEye MJPEG client connects to Motion
6. ✅ Web UI can request `/mjpg/stream` endpoint

---

## Backwards Compatibility Issues Identified

This deployment revealed that the Pi 5 + Camera v3 update had backwards compatibility issues:

1. **Movie codec format** - Hardcoded to old Motion 4.x format in defaults.py
2. **Missing stream handler** - Critical handler not ported to new codebase
3. **Permissioning assumptions** - Code assumes `motion` user has camera hardware access

These are **not camera-specific** - they affect any MotionEye instance updated to this version.

---

## Recommendations

1. **Update defaults.py** (line 194): Change `mp4:h264_v4l2m2m` to `mp4` for Motion 5.0 compatibility
2. **Document breaking changes** in update notes for Motion 5.0 migration
3. **Add unit tests** for stream handler and Motion 5.0 configuration
4. **Test on multiple hardware**: Verify updates work on Pi 4, Pi 5, and other platforms before release

---

## Files Modified

- `motioneye/handlers/stream.py` - NEW (MJPEG stream proxy handler)
- `motioneye/server.py` - UPDATED (added StreamHandler import and route)
- `/etc/motioneye/camera-1.conf` - UPDATED (fixed movie_container format)

