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

---

# Motion 5.0.0 Changes - Integration Reference

> **Last Updated**: 2025-12-12
> **Motion Version**: 5.0.0

This section documents the changes made to Motion that may affect MotionEye integration. These changes are relevant when updating MotionEye to work with Motion 5.0.0 on Raspberry Pi 5.

## Summary of Motion 5.0.0 Changes

Motion 5.0.0 includes two major feature sets:

1. **Raspberry Pi 5 + Camera Module v3 (IMX708) Native Support**
2. **Configuration System Refactor for Performance Optimization**

---

## 1. Pi 5 + Camera v3 Support

### 1.1 libcamera Changes

**StreamRole Change:**
- Motion now uses `StreamRole::VideoRecording` instead of `StreamRole::Viewfinder`
- This is required for Pi 5's PiSP (Pi Image Signal Processor) to properly initialize the ISP pipeline

**Multi-Buffer Support:**
- Motion now supports configurable buffer counts for libcamera
- Default: 4 buffers (configurable 2-8)
- Fixes pipeline stalls that occurred with single-buffer mode on Pi 5

**Camera Filtering:**
- Motion now filters out USB cameras (UVC devices) from CSI camera detection
- Pi cameras are identified by their device tree path (e.g., `/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a`)
- USB cameras are excluded by checking for "usb" or "uvc" in the camera ID

**Camera Selection:**
- Support for `camera0`, `camera1`, etc. index-based selection
- Support for model-based selection (e.g., "imx708")
- Auto-detection with `auto` or `camera0` as default

### 1.2 New Configuration Parameter

**`libcam_buffer_count`**
- Type: Integer
- Default: 4
- Range: 2-8
- Purpose: Controls the number of frame buffers for libcamera capture
- Usage: Higher values improve stability on Pi 5, may increase memory usage

```
# Example in motion.conf
libcam_buffer_count 4
```

### 1.3 Encoding Notes for Pi 5

**Important**: Pi 5 does **NOT** have hardware H.264 encoding.

- Motion falls back to software encoding (`libx264`) on Pi 5
- `h264_v4l2m2m` codec is NOT available on Pi 5
- CPU usage estimates:
  - 1920x1080 @ 30fps: 30-50% single core
  - 1280x720 @ 30fps: 15-25% single core
  - 640x480 @ 30fps: 5-10% single core

**Recommendation**: For multi-camera setups on Pi 5, consider 720p resolution to manage CPU load.

**New Parameter**: `movie_encoder_preset` for H.264 encoding optimization.

---

## 2. Configuration System Refactor

### 2.1 Architecture Changes

Motion's configuration system has been significantly refactored for better performance:

**New Files:**
| File | Purpose |
|------|---------|
| `src/parm_registry.hpp/cpp` | O(1) parameter lookup via hash map |
| `src/parm_structs.hpp` | Scoped parameter structures |
| `src/conf_file.hpp/cpp` | Separated file I/O operations |

**Performance Improvements:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Parameter lookup | O(n) ~5μs | O(1) <100ns | 50x faster |
| Camera config memory | ~8KB | ~3KB | 60% smaller |
| parms_copy() time | ~500μs | ~10μs | 50x faster |

### 2.2 Parameter Organization

Parameters are now organized into scoped structures:

**`ctx_parm_app`** (38 members) - Application-level parameters:
- System: `daemon`, `pid_file`, `log_file`, `log_level`, etc.
- Web control: `webcontrol_port`, `webcontrol_localhost`, `webcontrol_parms`, etc.
- Database: `database_type`, `database_dbname`, `database_host`, etc.
- SQL: `sql_query`, `sql_event_start`, `sql_event_end`, etc.

**`ctx_parm_cam`** (117 members) - Camera parameters:
- Detection (hot path): `threshold`, `despeckle_filter`, `smart_mask_speed`, `lightswitch_*`, etc.
- Source: `libcam_device`, `libcam_params`, `libcam_buffer_count`, `v4l2_*`, `netcam_*`
- Image: `width`, `height`, `rotate`, `flip_axis`
- Output: `movie_output`, `movie_container`, `movie_quality`, `picture_*`
- Timing: `watchdog_tmo`, `event_gap`, `pre_capture`, `post_capture`

**`ctx_parm_snd`** (5 members) - Sound parameters:
- `snd_device`, `snd_params`, `snd_window`, `snd_show`, `snd_alerts`

### 2.3 API Compatibility

**Backward Compatible:**
- All existing `->cfg->parameter` access patterns are preserved
- Configuration files remain compatible (same parameter names)
- Web UI parameter editing unchanged

**New Methods (for future use):**
```cpp
// O(1) scoped copy operations
void copy_app(const cls_config *src);  // Copy app parameters only
void copy_cam(const cls_config *src);  // Copy camera parameters only
void copy_snd(const cls_config *src);  // Copy sound parameters only
```

### 2.4 File I/O Separation

File I/O operations are now handled by `cls_config_file`:
- `init()` - Initialize configuration file paths
- `process()` - Parse configuration file
- `cmdline()` - Parse command-line arguments
- `parms_log()` - Log parameter values
- `parms_write()` - Write configuration to file

---

## 3. MotionEye Integration Considerations

### 3.1 Configuration Generation

When MotionEye generates `motion.conf` for Pi 5 cameras:

```python
# Required for Pi 5 + Camera Module v3
config['libcam_buffer_count'] = 4  # New parameter in Motion 5.0.0

# Camera device selection
config['libcam_device'] = 'camera0'  # or 'auto', 'imx708', etc.

# Recommended settings for Pi 5 performance
config['width'] = 1280   # 720p recommended for multi-camera
config['height'] = 720
config['framerate'] = 30
```

### 3.2 Detection Compatibility

Motion 5.0.0's camera filtering may affect MotionEye's camera detection:
- USB cameras (UVC) are now excluded from libcamera listing
- CSI cameras (Camera Module 3, etc.) are properly detected
- Camera IDs are based on device tree paths, not simple indices

### 3.3 Web UI Parameter Mapping

The parameter organization hasn't changed names, but MotionEye should be aware:
- All 182 parameters remain accessible via web control
- Parameter lookup is now O(1) instead of O(n)
- No changes needed to existing motionctl.py parameter handling

### 3.4 Build Requirements

For building Motion 5.0.0 on Pi 5:

```bash
# Dependencies
sudo apt install libcamera-dev libcamera-tools libjpeg-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libmicrohttpd-dev libsqlite3-dev autoconf automake libtool pkgconf

# Recommended build configuration
./configure \
  --with-libcam \
  --with-sqlite3 \
  --without-v4l2 \
  --without-mysql \
  --without-mariadb \
  --without-pgsql

make -j4
sudo make install
```

---

## 4. Migration Notes for MotionEye

### 4.1 Updating motionctl.py

No changes required for parameter handling, but consider:

1. **Add `libcam_buffer_count`** to the list of configurable parameters
2. **Update camera detection** to handle the new filtering behavior
3. **Add Pi 5 recommendations** for resolution/framerate in the UI

### 4.2 Config File Generation

Update `config.py` to include:

```python
# For libcamera cameras on Pi 5
if is_pi5 and camera_type == 'libcam':
    motion_config['libcam_buffer_count'] = 4
```

### 4.3 Error Handling

Motion 5.0.0 provides more specific error messages for camera issues:
- "No Pi cameras found" - No CSI cameras detected
- "Camera index X not found (have Y cameras)" - Invalid camera selection
- "Camera 'X' not found" - Invalid model name

Update error handling in MotionEye to display these messages appropriately.

---

## 5. Reference: New/Changed Motion Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `libcam_buffer_count` | int | 4 | Number of libcamera frame buffers (2-8) |
| `movie_encoder_preset` | string | - | H.264 encoder preset for performance tuning |

---

## 6. Reference: Motion Source Files Changed

### New Files
- `src/parm_registry.hpp` - Parameter registry header
- `src/parm_registry.cpp` - Parameter registry implementation
- `src/parm_structs.hpp` - Scoped parameter structures
- `src/conf_file.hpp` - Config file I/O header
- `src/conf_file.cpp` - Config file I/O implementation

### Modified Files
- `src/libcam.cpp` - Pi 5 + Camera v3 support
- `src/libcam.hpp` - Multi-buffer support structures
- `src/conf.cpp` - Registry integration, scoped copies
- `src/conf.hpp` - Scoped parameter struct members
- `src/Makefile.am` - New source files

### Unchanged Files (Preserved)
- `src/alg.cpp` - Motion detection algorithm
- `src/alg.hpp` - Algorithm interface
- `src/alg_sec.cpp` - Secondary detection methods
