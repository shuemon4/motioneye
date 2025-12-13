# RPi Camera RTSP Bridge Implementation Notes

> **Date**: 2025-12-12
> **Task**: Implementing RTSP bridge for RPi Camera support in MotionEye
> **Status**: ✅ COMPLETED

## Progress Tracking

### All Tasks Completed ✅
- [x] Renamed `libcamctl.py` to `rpicamctl.py`
- [x] Updated imports in `handlers/config.py`
- [x] Added `rpicam-vid` tool detection
- [x] Added `find_rpicam_tools()` function
- [x] Added `get_camera_modes()` function
- [x] Added backwards compatibility aliases
- [x] Created `rpicam_rtsp.py` RTSP bridge manager
- [x] Added RPICAM settings to `settings.py`
- [x] Added `is_rpicam_camera()` to `utils/__init__.py`
- [x] Updated `handlers/config.py` for rpicam protocol
- [x] Updated `server.py` for RTSP bridge lifecycle
- [x] Fixed `_dict_to_conf` list serialization bug
- [x] Tested on Raspberry Pi 5

## Architecture Notes

### RTSP Bridge Flow
```
rpicamctl.py        →  rpicam_rtsp.py       →  motion daemon
(detect cameras)       (manage rpicam-vid       (consumes RTSP
                        + mediamtx)              as netcam)
```

### mediamtx Auto-Download
- Download from GitHub releases on first use
- Stored in `settings.DATA_PATH/bin/`
- Architecture auto-detected (arm64 for RPi5)
- URL: `https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_{arch}.tar.gz`

### Key Design Decisions
1. **Singleton Pattern**: `RpicamRTSPBridge` class manages all streams
2. **Graceful Shutdown**: SIGTERM first, then SIGKILL after 5s timeout
3. **Auto-Restart**: Max 3 attempts on stream failure
4. **Port Handling**: Default 8554, try alternatives on conflict

## Files Modified
- `motioneye/controls/rpicamctl.py` - Camera detection (renamed from libcamctl.py)
- `motioneye/handlers/config.py` - Updated import

## Files To Create
- `motioneye/rpicam_rtsp.py` - RTSP bridge manager

## Testing Results

### Pi 5 Test Validation (2025-12-12)
```
✅ rpicam-vid command detected: rpicam-vid
✅ rpicam-hello command detected: rpicam-hello
✅ mediamtx installed successfully at /etc/motioneye/bin/mediamtx
✅ mediamtx RTSP server started on port 8554
✅ Motion daemon running with libcamera
✅ Camera stream working (129MB in 5 seconds)
```

### Camera Detected
```
Camera: imx708_wide_noir (Camera Module 3 Wide NoIR)
Resolution: 4608x2592 (max)
Modes: 1536x864, 2304x1296, 4608x2592 @ 30fps
```

### Bug Fixed During Testing
- **Issue**: `libcam_control_item` values were being written as individual characters
- **Root Cause**: `_dict_to_conf()` was iterating over strings char-by-char instead of list items
- **Fix**: Added type checking in `motioneye/config/serialization.py` to wrap strings in lists

## Testing Commands
```bash
# Deploy to Pi 5
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

# Install on Pi
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

# Restart service
ssh admin@192.168.1.176 "sudo systemctl restart motioneye"

# Check logs
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"

# Test stream
ssh admin@192.168.1.176 "curl -s --max-time 5 'http://localhost:7999/1/mjpg/stream' --output /tmp/stream.dat; file /tmp/stream.dat"
```
