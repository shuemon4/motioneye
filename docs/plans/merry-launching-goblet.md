# RPi Camera (rpicam) RTSP Bridge Integration Plan

> **Note**: This plan should be moved to `docs/plans/` in the project after implementation begins.

## Overview

Integrate native RPi Camera support into motionEye for RPi5 + Camera Module 3 via an automatic RTSP bridge. Uses the modern `rpicam-apps` tools (with `libcamera-apps` fallback for older systems). The camera will appear as "RPi Camera" in the UI with automatic stream setup.

## Architecture

```
rpicamctl.py        →  rpicam_rtsp.py       →  motion daemon
(detect cameras)       (manage rpicam-vid       (consumes RTSP
                        + mediamtx)              as netcam)
```

## Implementation Phases

### Phase 1: Detection Module
**New File: `motioneye/controls/rpicamctl.py`**

> **Note**: Named `rpicamctl.py` to match the official Raspberry Pi naming (rpicam-apps).
> The module handles both old (`libcamera-*`) and new (`rpicam-*`) command names.

```python
# Key functions (following mmalctl.py pattern):
def find_rpicam_tools() -> dict:
    """
    Locate rpicam-vid/rpicam-hello (preferred) or
    libcamera-vid/libcamera-hello (legacy fallback).
    Returns dict with paths: {'vid': path, 'hello': path}
    """

def list_devices() -> list[tuple]     # Parse rpicam-hello --list-cameras
def get_camera_modes(index) -> list   # Get supported resolutions/fps
def is_rpicam_available() -> bool     # Quick availability check
```

**Tool Detection Priority:**
1. `rpicam-vid` / `rpicam-hello` (Bookworm+, preferred)
2. `libcamera-vid` / `libcamera-hello` (Bullseye, legacy fallback)

### Phase 2: RTSP Bridge Manager
**New File: `motioneye/rpicam_rtsp.py`**

```python
class RpicamRTSPBridge:
    # Singleton managing all libcamera streams
    def start()           # Start mediamtx + rpicam-vid processes
    def stop()            # Graceful shutdown with SIGTERM/SIGKILL
    def add_stream()      # Add camera stream
    def remove_stream()   # Remove camera stream
    def get_stream_url()  # Get rtsp://localhost:8554/camX URL

# Module functions:
def start(), stop(), should_start(), is_running(), get_rtsp_url()
```

### Phase 3: Configuration Integration
**Modify: `motioneye/utils/__init__.py`**
- Add `is_rpicam_camera(config)` function

**Modify: `motioneye/settings.py`**
```python
# New settings:
RPICAM_RTSP_ENABLED = None  # Auto-detect
RPICAM_RTSP_PORT = 8554
RPICAM_DEFAULT_WIDTH = 1920
RPICAM_DEFAULT_HEIGHT = 1080
RPICAM_DEFAULT_FRAMERATE = 30
```

**Modify: `motioneye/handlers/config.py`**
- Add `elif proto == 'rpicam':` block in `list()` method (~line 479)
- Handle rpicam in `add_camera()` method

**Modify: `motioneye/config.py`**
- Add rpicam handling in `add_camera()`
- Add `rpicam_camera_dict_to_ui()` function
- Add `rpicam_camera_ui_to_dict()` function

### Phase 4: Server Integration
**Modify: `motioneye/server.py`**
- Import `rpicam_rtsp` module
- Call `rpicam_rtsp.start()` in startup sequence
- Call `rpicam_rtsp.stop()` in shutdown sequence
- Add health checker for RTSP bridge

### Phase 5: Dependencies & Auto-Download

**System requirements on RPi5:**
```bash
sudo apt install rpicam-apps
```

**mediamtx Auto-Download (in `rpicam_rtsp.py`):**
```python
def _ensure_mediamtx() -> str:
    """Download mediamtx if not present, return path to binary."""
    mediamtx_path = os.path.join(settings.DATA_PATH, 'bin', 'mediamtx')

    if os.path.exists(mediamtx_path):
        return mediamtx_path

    # Detect architecture (arm64, armv7, etc.)
    arch = _detect_architecture()

    # Download from GitHub releases
    url = f"https://github.com/bluenviron/mediamtx/releases/download/v1.9.3/mediamtx_v1.9.3_linux_{arch}.tar.gz"

    # Download, extract, set executable
    _download_and_extract(url, mediamtx_path)

    return mediamtx_path
```

- Downloads on first rpicam camera add
- Stored in `settings.DATA_PATH/bin/`
- Architecture auto-detected (arm64 for RPi5)

## Files to Create

| File | Purpose |
|------|---------|
| `motioneye/controls/rpicamctl.py` | Camera detection via rpicam-hello |
| `motioneye/rpicam_rtsp.py` | RTSP bridge process manager |

## Files to Modify

| File | Changes |
|------|---------|
| `motioneye/utils/__init__.py` | Add `is_rpicam_camera()` |
| `motioneye/settings.py` | Add rpicam settings |
| `motioneye/handlers/config.py` | Add `rpicam` protocol in `list()` (~line 479) |
| `motioneye/config.py` | Add rpicam camera handling |
| `motioneye/server.py` | Add RTSP bridge lifecycle |

## Process Flow

### Startup
1. Server starts → check `is_rpicam_available()`
2. Load camera configs → find enabled rpicam cameras
3. Start mediamtx RTSP server on port 8554
4. For each rpicam camera: start `rpicam-vid` publishing to RTSP
5. Configure motion daemon with `netcam_url=rtsp://localhost:8554/camX`
6. Start motion daemon

### Shutdown
1. Stop motion daemon
2. Send SIGTERM to rpicam-vid processes
3. Wait 5s, then SIGKILL if needed
4. Stop mediamtx

## User Experience

1. User opens motionEye web UI
2. Clicks "Add Camera"
3. Sees "RPi Camera" option with detected camera (uses rpicam)
4. Selects camera → automatic RTSP bridge setup
5. Camera stream appears in UI

## Error Handling

- Missing rpicam-apps: Disable rpicam option in UI
- mediamtx port conflict: Try alternative port
- Stream failure: Auto-restart (max 3 attempts)
- Camera disconnect: Log error, mark stream failed

## Testing Checklist

- [ ] Detection works on RPi5 with Camera Module 3
- [ ] RTSP stream starts successfully
- [ ] Motion daemon receives stream
- [ ] Live view works in browser
- [ ] Motion detection works
- [ ] Camera remove/re-add works
- [ ] Clean shutdown (no orphan processes)
- [ ] Reboot persistence
