# RPi Camera RTSP Bridge - Implementation Summary

Implementation of native Raspberry Pi Camera support for motionEye using MediaMTX native rpiCamera source.

## Implementation Date
2025-12-05 (completed 2025-12-06)

## Status: WORKING ✅

Successfully tested on Raspberry Pi 5 with Camera Module 3 (IMX708 Wide NoIR).

## Overview

Successfully integrated RPi Camera Module 3 (and other libcamera-compatible cameras) into motionEye by:
1. Detecting cameras via `rpicam-hello --list-cameras` (or `libcamera-hello` on older systems)
2. Using MediaMTX's **native rpiCamera source** which directly interfaces with libcamera
3. Transparently presenting cameras as network cameras to the motion daemon
4. Providing seamless user experience through "RPi Camera" option in UI

## Key Implementation Detail: Native rpiCamera Source

**Critical Discovery**: MediaMTX has built-in native support for Raspberry Pi cameras via libcamera. This eliminates the need for:
- External `rpicam-vid` processes
- Complex stdout/stdin piping
- ffmpeg transcoding

The native `rpiCamera` source in MediaMTX directly accesses the camera hardware, producing a clean H.264 RTSP stream.

### MediaMTX Configuration
```yaml
paths:
  cam0:
    source: rpiCamera
    rpiCameraCamID: 0
    rpiCameraWidth: 1920
    rpiCameraHeight: 1080
    rpiCameraFPS: 30
    rpiCameraIDRPeriod: 30
    rpiCameraBitrate: 4000000
    rpiCameraProfile: main
    rpiCameraLevel: '4.1'
```

## Files Created

### `motioneye/controls/rpicamctl.py`
**Purpose**: Camera detection module following existing mmalctl.py pattern

**Key Functions**:
- `find_rpicam_tools()` - Locates rpicam-vid/rpicam-hello with legacy libcamera-* fallback
- `list_devices()` - Parses camera list from command output, returns [(device_id, device_name), ...]
- `get_camera_modes()` - Extracts supported resolutions/framerates for configuration
- `is_rpicam_available()` - Quick availability check for auto-detection

### `motioneye/rpicam_rtsp.py`
**Purpose**: RTSP bridge manager using MediaMTX native rpiCamera source

**Core Components**:

**Architecture Detection**: `_detect_architecture()`
- Detects 32-bit userspace on 64-bit kernel (critical for Pi5 with armhf OS)
- Uses `struct.calcsize('P')` to detect Python pointer size
- Properly selects armv7 binary for 32-bit userspace

**Dependency Management**: `_ensure_mediamtx()`
- Downloads mediamtx v1.9.3 from GitHub on first use
- Stores in `{MEDIA_PATH}/bin/mediamtx`
- Architecture-specific binary selection (armv7 for armhf userspace)

**RTSP Server**: `_start_mediamtx()` / `_stop_mediamtx()`
- Manages mediamtx RTSP server on port 8554
- Adds `/usr/sbin:/sbin` to PATH for ldconfig access
- Creates YAML config for native rpiCamera source
- Graceful shutdown with SIGTERM/SIGKILL timeout

**Stream Management**:
- `add_stream()` - Adds camera config and restarts mediamtx
- `remove_stream()` - Removes camera and updates config
- `get_stream_url()` - Returns rtsp://127.0.0.1:8554/camX URL

## Files Modified

### `motioneye/utils/__init__.py`
- Added `is_rpicam_camera(config)` function
- Updated `is_local_motion_camera()` to recognize rpicam cameras

### `motioneye/settings.py`
```python
RPICAM_RTSP_ENABLED = None  # Auto-detect
RPICAM_RTSP_PORT = 8554
RPICAM_DEFAULT_WIDTH = 1920
RPICAM_DEFAULT_HEIGHT = 1080
RPICAM_DEFAULT_FRAMERATE = 30
```

### `motioneye/handlers/config.py`
- Added `rpicamctl` import
- Added `elif proto == 'rpicam':` block for camera listing

### `motioneye/config.py`
- Added rpicam handling in `add_camera()` function
- Stores rpicam_id and rpicam_index metadata
- Calls `rpicam_rtsp.add_stream()` to start RTSP bridge

### `motioneye/server.py`
- Import and initialize `rpicam_rtsp` module
- Call `start()` at startup, `stop()` at shutdown

### `motioneye/motionctl.py`
- Start RTSP streams for existing rpicam cameras on motion start

### `motioneye/static/js/main.js`
- Added 'rpicam' option to camera type dropdown
- Added rpicam handling in UI logic

## Architecture Flow

### Camera Addition
```
User → Add Camera → Select "RPi Camera"
  ↓
rpicamctl.list_devices() → Detects IMX708
  ↓
User selects camera → config.add_camera(proto='rpicam')
  ↓
rpicam_rtsp.add_stream() → Creates mediamtx YAML config
  ↓
mediamtx starts with native rpiCamera source
  ↓
libcamera detects camera, starts H.264 encoding
  ↓
RTSP stream available at rtsp://127.0.0.1:8554/cam0
  ↓
motion daemon consumes stream via netcam_url
```

## Issues Resolved

### 1. ldconfig not found
**Error**: `ldconfig failed: exec: "ldconfig": executable file not found in $PATH`
**Fix**: Add `/usr/sbin:/sbin` to PATH when launching mediamtx

### 2. 32-bit vs 64-bit Architecture Mismatch
**Error**: `the operating system is 32-bit, you need the 32-bit server version`
**Cause**: Pi5 kernel is 64-bit (aarch64) but userspace is 32-bit (armhf)
**Fix**: Use `struct.calcsize('P')` to detect actual pointer size, download armv7 binary

### 3. rpicam-vid Piping Failures
**Error**: Various errors with stdout piping, tcp sources
**Solution**: Abandoned rpicam-vid approach entirely, used MediaMTX native rpiCamera source

## Testing Status

### Verified ✅
- [x] Detection works on RPi5 with Camera Module 3
- [x] RTSP stream starts successfully
- [x] Motion daemon receives stream
- [x] Live view works in browser
- [x] Code implementation complete
- [x] All phases integrated

### Pending Testing
- [ ] Motion detection functionality
- [ ] Camera remove/re-add works
- [ ] Clean shutdown (no orphan processes)
- [ ] Reboot persistence
- [ ] Testing on older systems (Bullseye with libcamera-apps)

## Dependencies

### System Requirements
```bash
# Bookworm (newer)
sudo apt install rpicam-apps

# Bullseye (older)
sudo apt install libcamera-apps
```

### Automatically Downloaded
- **mediamtx v1.9.3** - Downloaded on first rpicam camera add
- Stored in: `{MEDIA_PATH}/bin/mediamtx`
- Architecture: armv7 for 32-bit userspace, arm64v8 for 64-bit
- Size: ~15MB compressed

## Known Limitations

1. **Fixed stream parameters**: Currently uses settings defaults (1920x1080@30fps)
2. **Single camera per index**: Each rpicam index can only be used once
3. **RTSP port conflict**: If port 8554 is in use, bridge won't start
4. **32-bit userspace required**: MediaMTX rpiCamera needs matching userspace architecture

## Compatibility

- **Raspberry Pi 5**: Tested and working (armhf OS)
- **Raspberry Pi 4/3**: Should work with libcamera-apps fallback
- **Camera Modules**: IMX708 tested, should work with IMX219, OV5647, etc.
- **OS Versions**: Bookworm (rpicam-*), Bullseye (libcamera-*)

## Notes

- The implementation uses MediaMTX's native libcamera integration, not external processes
- RPi cameras are treated as network cameras internally (RTSP)
- The `@proto = 'rpicam'` metadata allows special handling while using standard netcam path
- Auto-detection ensures zero-config experience when tools are available
- PATH must include `/usr/sbin:/sbin` for mediamtx to find ldconfig
