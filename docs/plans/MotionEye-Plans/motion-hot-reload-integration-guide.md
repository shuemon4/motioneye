# Motion 5.0 Hot Reload API - MotionEye Integration Guide

**Date**: 2025-12-13
**Status**: READY FOR IMPLEMENTATION
**Motion Version**: 5.0 (built from latest master)
**Verified On**: Raspberry Pi 5, Camera Module v3

---

## Overview

Motion 5.0 now includes a hot-reload API that allows runtime configuration updates without daemon restart. This eliminates the 2-5 second video stream interruption users experience when adjusting detection sensitivity, text overlays, and other tunable parameters.

This document provides everything needed to integrate this capability into MotionEye.

---

## API Specification

### Endpoint

```
GET /{camera_id}/config/set?{parameter}={value}
```

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `camera_id` | int | Camera ID (1-N for specific camera, 0 for all cameras) |
| `parameter` | string | Motion parameter name |
| `value` | string | New value (URL encoded) |

### Response Format

**Success Response** (HTTP 200):
```json
{
  "status": "ok",
  "parameter": "threshold",
  "old_value": "1500",
  "new_value": "2000",
  "hot_reload": true
}
```

**Error - Requires Restart** (HTTP 200):
```json
{
  "status": "error",
  "parameter": "width",
  "old_value": "",
  "new_value": "1280",
  "hot_reload": false,
  "error": "Parameter requires daemon restart"
}
```

**Error - Unknown Parameter** (HTTP 200):
```json
{
  "status": "error",
  "parameter": "invalid_param",
  "old_value": "",
  "new_value": "123",
  "hot_reload": false,
  "error": "Unknown parameter"
}
```

### Example Requests

```bash
# Update motion detection threshold
curl 'http://localhost:7999/1/config/set?threshold=2000'

# Update text overlay (URL encode spaces as %20)
curl 'http://localhost:7999/1/config/set?text_left=Front%20Door%20Camera'

# Update all cameras at once
curl 'http://localhost:7999/0/config/set?event_gap=30'
```

---

## Hot-Reloadable Parameters

The following 72 parameters can be updated at runtime without restart:

### Motion Detection (Tier 1 - High Priority)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold` | int | 1500 | Pixels changed to trigger motion |
| `threshold_maximum` | int | 0 | Max threshold (0=unlimited) |
| `threshold_tune` | bool | off | Auto-tune threshold |
| `noise_level` | int | 32 | Noise filtering level |
| `noise_tune` | bool | on | Auto-tune noise level |
| `despeckle_filter` | string | EedDl | Despeckle filter string |
| `minimum_motion_frames` | int | 1 | Frames before event triggers |
| `event_gap` | int | 60 | Seconds gap between events |
| `lightswitch_percent` | int | 0 | Light change % to ignore |
| `lightswitch_frames` | int | 5 | Frames to detect light change |
| `static_object_time` | int | 0 | Seconds to ignore static objects |
| `smart_mask_speed` | int | 0 | Adaptive mask learning speed |
| `emulate_motion` | bool | off | Force motion detection (testing) |

### Text Overlays (Tier 2)

| Parameter | Type | Description |
|-----------|------|-------------|
| `text_left` | string | Text on left side of frame |
| `text_right` | string | Text on right side of frame |
| `text_scale` | int | Text size (1-10) |
| `text_changes` | bool | Show changed pixels count |
| `text_event` | string | Event text template |
| `locate_motion_mode` | enum | off/on/preview - draw motion boxes |
| `locate_motion_style` | enum | box/redbox/cross/redcross |

### Event Handlers (Tier 3)

| Parameter | Type | Description |
|-----------|------|-------------|
| `on_event_start` | string | Command on motion start |
| `on_event_end` | string | Command on motion end |
| `on_motion_detected` | string | Command per motion frame |
| `on_movie_start` | string | Command when recording starts |
| `on_movie_end` | string | Command when recording ends |
| `on_picture_save` | string | Command after snapshot saved |
| `on_action_user` | string | User-triggered action command |
| `on_area_detected` | string | Area detection command |
| `on_camera_found` | string | Camera connection established |
| `on_camera_lost` | string | Camera connection lost |
| `on_secondary_detect` | string | Secondary detection command |

### Capture Control

| Parameter | Type | Description |
|-----------|------|-------------|
| `pre_capture` | int | Frames before motion event |
| `post_capture` | int | Frames after motion event |
| `snapshot_interval` | int | Auto snapshot interval (seconds) |

### Picture Output

| Parameter | Type | Description |
|-----------|------|-------------|
| `picture_output` | enum | off/on/first/best/center |
| `picture_output_motion` | enum | Motion picture output mode |
| `picture_quality` | int | JPEG quality 1-100 |
| `picture_exif` | string | EXIF metadata text |
| `picture_filename` | string | Picture filename format |

### Movie Output

| Parameter | Type | Description |
|-----------|------|-------------|
| `movie_filename` | string | Movie filename format |
| `movie_bps` | int | Bitrate for movie encoding |
| `movie_quality` | int | Quality for movie encoding |
| `movie_max_time` | int | Max movie length (seconds) |
| `movie_extpipe_use` | bool | Use external pipe encoder |
| `movie_extpipe` | string | External pipe command |

### Timelapse

| Parameter | Type | Description |
|-----------|------|-------------|
| `timelapse_interval` | int | Timelapse capture interval |
| `timelapse_mode` | enum | Timelapse mode |
| `timelapse_fps` | int | Timelapse playback FPS |
| `timelapse_container` | enum | Timelapse container format |
| `timelapse_filename` | string | Timelapse filename format |

### Secondary Detection

| Parameter | Type | Description |
|-----------|------|-------------|
| `secondary_interval` | int | Secondary detection interval |
| `secondary_method` | enum | Secondary detection method |
| `secondary_params` | string | Secondary detection parameters |

### Streaming

| Parameter | Type | Description |
|-----------|------|-------------|
| `stream_preview_scale` | int | Preview stream scale % |
| `stream_preview_newline` | bool | Newline in stream header |
| `stream_preview_method` | enum | Preview method |
| `stream_preview_pps` | int | Preview pictures per second |
| `stream_quality` | int | Stream JPEG quality |
| `stream_grey` | bool | Greyscale stream |
| `stream_motion` | bool | Stream motion images |
| `stream_maxrate` | int | Max stream framerate |
| `stream_limit` | int | Connection limit (0=unlimited) |

### Device Settings

| Parameter | Type | Description |
|-----------|------|-------------|
| `device_name` | string | Display name for camera |
| `target_dir` | string | Output directory path |
| `watchdog_tmo` | int | Watchdog timeout |
| `watchdog_kill` | int | Watchdog kill timeout |
| `pause` | bool | Pause motion detection |

### PTZ Control

| Parameter | Type | Description |
|-----------|------|-------------|
| `ptz_auto_track` | bool | Auto-track motion |
| `ptz_wait` | int | Wait between PTZ commands |
| `ptz_move_track` | string | PTZ tracking command |
| `ptz_pan_left` | string | Pan left command |
| `ptz_pan_right` | string | Pan right command |
| `ptz_tilt_up` | string | Tilt up command |
| `ptz_tilt_down` | string | Tilt down command |
| `ptz_zoom_in` | string | Zoom in command |
| `ptz_zoom_out` | string | Zoom out command |

### SQL Database

| Parameter | Type | Description |
|-----------|------|-------------|
| `sql_event_start` | string | SQL on event start |
| `sql_event_end` | string | SQL on event end |
| `sql_movie_start` | string | SQL on movie start |
| `sql_movie_end` | string | SQL on movie end |
| `sql_pic_save` | string | SQL on picture save |

---

## Parameters That REQUIRE Restart

These parameters cannot be hot-reloaded and will return `"hot_reload": false`:

| Category | Parameters |
|----------|------------|
| **System** | `daemon`, `pid_file`, `log_level`, `log_file`, `log_type_str` |
| **Device** | `libcam_device`, `libcam_options`, `v4l2_device`, `v4l2_params`, `netcam_url`, `netcam_params`, `netcam_high_url`, `netcam_userpass` |
| **Resolution** | `width`, `height`, `framerate`, `rotate`, `flip_axis` |
| **Ports** | `webcontrol_port`, `webcontrol_ipv6`, `webcontrol_localhost`, `webcontrol_parms`, `webcontrol_interface`, `webcontrol_auth_method`, `webcontrol_authentication`, `webcontrol_tls`, `webcontrol_cert`, `webcontrol_key`, `webcontrol_header_params`, `webcontrol_cors_header` |
| **Streaming Ports** | `stream_port`, `stream_localhost`, `stream_tls`, `stream_cors_header`, `stream_authentication` |
| **Recording Format** | `movie_output`, `movie_output_motion`, `movie_container`, `movie_codec`, `movie_passthrough`, `movie_retain` |
| **Storage** | `database_type`, `database_dbname`, `database_host`, `database_port`, `database_user`, `database_password`, `database_busy_timeout` |
| **Masks (File)** | `mask_file`, `mask_privacy` (require PGM file reload) |
| **Audio** | `sound_device`, `sound_params`, `sound_trigger`, `sound_alerts`, `sound_window`, `sound_show`, `sound_file` |
| **Pipes** | `video_pipe`, `video_pipe_motion`, `extpipe_use`, `extpipe` |

---

## Implementation Guide for MotionEye

### 1. Constants Definition

Create or update `motioneye/config/camera/constants.py`:

```python
"""Motion parameter classification for hot reload support."""

# Parameters that can be updated at runtime without daemon restart
HOT_RELOAD_PARAMS = {
    # Motion Detection (Tier 1 - most frequently adjusted)
    'threshold',
    'threshold_maximum',
    'threshold_tune',
    'noise_level',
    'noise_tune',
    'despeckle_filter',
    'minimum_motion_frames',
    'event_gap',
    'lightswitch_percent',
    'lightswitch_frames',
    'static_object_time',
    'smart_mask_speed',
    'emulate_motion',

    # Text Overlays (Tier 2)
    'text_left',
    'text_right',
    'text_scale',
    'text_changes',
    'text_event',
    'locate_motion_mode',
    'locate_motion_style',

    # Event Handlers (Tier 3)
    'on_event_start',
    'on_event_end',
    'on_motion_detected',
    'on_movie_start',
    'on_movie_end',
    'on_picture_save',
    'on_action_user',
    'on_area_detected',
    'on_camera_found',
    'on_camera_lost',
    'on_secondary_detect',

    # Capture Control
    'pre_capture',
    'post_capture',
    'snapshot_interval',

    # Picture Output
    'picture_output',
    'picture_output_motion',
    'picture_quality',
    'picture_exif',
    'picture_filename',

    # Movie Settings (runtime adjustable)
    'movie_filename',
    'movie_bps',
    'movie_quality',
    'movie_max_time',
    'movie_extpipe_use',
    'movie_extpipe',

    # Timelapse
    'timelapse_interval',
    'timelapse_mode',
    'timelapse_fps',
    'timelapse_container',
    'timelapse_filename',

    # Secondary Detection
    'secondary_interval',
    'secondary_method',
    'secondary_params',

    # Streaming (safe subset)
    'stream_preview_scale',
    'stream_preview_newline',
    'stream_preview_method',
    'stream_preview_pps',
    'stream_quality',
    'stream_grey',
    'stream_motion',
    'stream_maxrate',
    'stream_limit',

    # Device Settings (safe subset)
    'device_name',
    'target_dir',
    'watchdog_tmo',
    'watchdog_kill',
    'pause',

    # PTZ Control
    'ptz_auto_track',
    'ptz_wait',
    'ptz_move_track',
    'ptz_pan_left',
    'ptz_pan_right',
    'ptz_tilt_up',
    'ptz_tilt_down',
    'ptz_zoom_in',
    'ptz_zoom_out',

    # SQL Database
    'sql_event_start',
    'sql_event_end',
    'sql_movie_start',
    'sql_movie_end',
    'sql_pic_save',
}

# Parameters that always require daemon restart
RESTART_REQUIRED_PARAMS = {
    # System
    'daemon', 'pid_file', 'log_level', 'log_file', 'log_type_str',

    # Device
    'libcam_device', 'libcam_options', 'v4l2_device', 'v4l2_params',
    'netcam_url', 'netcam_params', 'netcam_high_url', 'netcam_userpass',

    # Resolution
    'width', 'height', 'framerate', 'rotate', 'flip_axis',

    # Webcontrol
    'webcontrol_port', 'webcontrol_ipv6', 'webcontrol_localhost',
    'webcontrol_parms', 'webcontrol_interface', 'webcontrol_auth_method',
    'webcontrol_authentication', 'webcontrol_tls', 'webcontrol_cert',
    'webcontrol_key', 'webcontrol_header_params', 'webcontrol_cors_header',

    # Streaming
    'stream_port', 'stream_localhost', 'stream_tls',
    'stream_cors_header', 'stream_authentication',

    # Recording
    'movie_output', 'movie_output_motion', 'movie_container',
    'movie_codec', 'movie_passthrough', 'movie_retain',

    # Database
    'database_type', 'database_dbname', 'database_host',
    'database_port', 'database_user', 'database_password',
    'database_busy_timeout',

    # Masks (file-based)
    'mask_file', 'mask_privacy',

    # Audio
    'sound_device', 'sound_params', 'sound_trigger',
    'sound_alerts', 'sound_window', 'sound_show', 'sound_file',

    # Pipes
    'video_pipe', 'video_pipe_motion', 'extpipe_use', 'extpipe',
}
```

### 2. Motion Control Function

Add to `motioneye/motionctl.py`:

```python
import urllib.parse
import aiohttp
import logging

async def set_config_hot(camera_id: int, param: str, value: str) -> dict:
    """
    Set a Motion parameter at runtime via hot reload API.

    Args:
        camera_id: MotionEye camera ID
        param: Motion parameter name
        value: New value for the parameter

    Returns:
        dict with keys:
            - success: bool
            - hot_reload: bool (True if applied without restart)
            - old_value: str (previous value, if available)
            - error: str (error message, if failed)
    """
    from motioneye.config.camera.constants import HOT_RELOAD_PARAMS

    # Early check - if not in our known hot-reload list, don't try
    if param not in HOT_RELOAD_PARAMS:
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Parameter requires daemon restart'
        }

    motion_camera_id = get_motion_camera_id(camera_id)
    port = get_motion_control_port()

    # URL encode the value
    encoded_value = urllib.parse.quote(str(value), safe='')
    url = f'http://127.0.0.1:{port}/{motion_camera_id}/config/set?{param}={encoded_value}'

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get('status') == 'ok' and data.get('hot_reload'):
                        logging.info(f'Hot reload: {param}={value} on camera {camera_id}')
                        return {
                            'success': True,
                            'hot_reload': True,
                            'old_value': data.get('old_value', '')
                        }
                    else:
                        # Motion reported the parameter needs restart
                        return {
                            'success': False,
                            'hot_reload': False,
                            'error': data.get('error', 'Parameter requires daemon restart')
                        }
                else:
                    return {
                        'success': False,
                        'hot_reload': False,
                        'error': f'HTTP {response.status}'
                    }

    except aiohttp.ClientError as e:
        logging.error(f'Failed to hot-reload {param}: {e}')
        return {
            'success': False,
            'hot_reload': False,
            'error': str(e)
        }
    except Exception as e:
        logging.error(f'Unexpected error hot-reloading {param}: {e}')
        return {
            'success': False,
            'hot_reload': False,
            'error': str(e)
        }


async def apply_config_changes(camera_id: int, old_config: dict, new_config: dict) -> dict:
    """
    Intelligently apply configuration changes using hot reload where possible.

    Args:
        camera_id: MotionEye camera ID
        old_config: Previous Motion configuration dict
        new_config: New Motion configuration dict

    Returns:
        dict with keys:
            - hot_reloaded: list of param names that were hot-reloaded
            - needs_restart: bool (True if any changes require restart)
            - restart_params: list of param names that need restart
            - errors: list of error messages
    """
    from motioneye.config.camera.constants import HOT_RELOAD_PARAMS

    hot_reloaded = []
    restart_params = []
    errors = []

    # Find changed parameters
    all_params = set(old_config.keys()) | set(new_config.keys())

    for param in all_params:
        old_val = old_config.get(param)
        new_val = new_config.get(param)

        # Skip unchanged parameters
        if old_val == new_val:
            continue

        # Skip None -> None
        if old_val is None and new_val is None:
            continue

        if param in HOT_RELOAD_PARAMS:
            # Try hot reload
            result = await set_config_hot(camera_id, param, str(new_val) if new_val else '')

            if result['success']:
                hot_reloaded.append(param)
            else:
                # Hot reload failed, will need restart
                restart_params.append(param)
                if result.get('error'):
                    errors.append(f"{param}: {result['error']}")
        else:
            # Parameter requires restart
            restart_params.append(param)

    return {
        'hot_reloaded': hot_reloaded,
        'needs_restart': len(restart_params) > 0,
        'restart_params': restart_params,
        'errors': errors
    }
```

### 3. Config Handler Integration

Update the config apply logic in `motioneye/handlers/config.py`:

```python
async def set_camera_config(camera_id: int, ui_config: dict) -> dict:
    """
    Apply camera configuration with smart hot-reload support.

    Returns:
        dict with keys:
            - success: bool
            - restarted: bool (True if daemon was restarted)
            - hot_reloaded: list of params updated without restart
            - message: str
    """
    from motioneye.motionctl import apply_config_changes, restart_camera

    # Get current config
    old_motion_config = get_current_motion_config(camera_id)

    # Convert UI config to Motion config format
    new_motion_config = motion_camera_ui_to_dict(ui_config)

    # Apply changes intelligently
    result = await apply_config_changes(camera_id, old_motion_config, new_motion_config)

    # Always persist to disk (MotionEye manages config files)
    write_camera_config(camera_id, new_motion_config)

    # Restart only if necessary
    if result['needs_restart']:
        logging.info(
            f'Camera {camera_id}: Restarting for parameters: {result["restart_params"]}'
        )
        await restart_camera(camera_id)

        return {
            'success': True,
            'restarted': True,
            'hot_reloaded': result['hot_reloaded'],
            'message': f'Applied {len(result["hot_reloaded"])} settings instantly, '
                       f'restarted for {len(result["restart_params"])} settings'
        }
    else:
        logging.info(
            f'Camera {camera_id}: Hot-reloaded {len(result["hot_reloaded"])} parameters'
        )
        return {
            'success': True,
            'restarted': False,
            'hot_reloaded': result['hot_reloaded'],
            'message': f'Applied {len(result["hot_reloaded"])} settings without restart'
        }
```

### 4. Frontend Integration (Optional)

Add user feedback about which changes require restart:

```javascript
// motioneye/static/js/config.js

const HOT_RELOAD_PARAMS = new Set([
    'threshold', 'threshold_maximum', 'noise_level', 'event_gap',
    'text_left', 'text_right', 'text_scale',
    'on_event_start', 'on_event_end', 'on_picture_save',
    // ... add more as needed
]);

const RESTART_REQUIRED_PARAMS = new Set([
    'resolution', 'framerate', 'rotation', 'device',
    'streaming_port', 'movie_format', 'storage_path'
]);

function willRequireRestart(changedSettings) {
    return changedSettings.some(s => !HOT_RELOAD_PARAMS.has(s));
}

function updateApplyButtonHint(changedSettings) {
    const applyBtn = document.querySelector('.apply-button');
    const hint = document.querySelector('.apply-hint');

    if (changedSettings.length === 0) {
        hint.textContent = '';
        return;
    }

    if (willRequireRestart(changedSettings)) {
        hint.textContent = 'Will briefly interrupt video stream';
        hint.classList.add('warning');
    } else {
        hint.textContent = 'Will apply without stream interruption';
        hint.classList.remove('warning');
    }
}
```

---

## Testing

### Manual Verification

Use the included test script on the Pi running Motion:

```bash
# Located at: motion/scripts/test_hot_reload.sh
./scripts/test_hot_reload.sh localhost 7999 1
```

Expected output:
```
Testing hot reload API on localhost:7999 (camera 1)
============================================

Connectivity test... PASS

Testing hot-reloadable parameters:
threshold=2000... PASS
noise_level=32... PASS
text_left=TestCam... PASS
...

Testing non-hot-reloadable parameters (should fail):
width=640... PASS (correctly rejected)
height=480... PASS (correctly rejected)
...

============================================
Results: 15/15 tests passed
```

### Integration Test Script

Create a test for MotionEye integration:

```python
# tests/test_hot_reload_integration.py

import pytest
import aiohttp
from motioneye.motionctl import set_config_hot, apply_config_changes

@pytest.mark.asyncio
async def test_hot_reload_threshold():
    """Test hot-reloading the threshold parameter."""
    result = await set_config_hot(camera_id=1, param='threshold', value='2500')
    assert result['success'] is True
    assert result['hot_reload'] is True

@pytest.mark.asyncio
async def test_restart_required_for_width():
    """Test that width parameter requires restart."""
    result = await set_config_hot(camera_id=1, param='width', value='1280')
    assert result['success'] is False
    assert result['hot_reload'] is False

@pytest.mark.asyncio
async def test_mixed_config_changes():
    """Test applying a mix of hot-reloadable and restart-required changes."""
    old_config = {'threshold': '1500', 'width': '1920'}
    new_config = {'threshold': '2000', 'width': '1280'}

    result = await apply_config_changes(camera_id=1, old_config=old_config, new_config=new_config)

    assert 'threshold' in result['hot_reloaded']
    assert 'width' in result['restart_params']
    assert result['needs_restart'] is True
```

---

## Flow Diagrams

### Current Flow (Before Integration)

```
User clicks Apply
       |
       v
+-------------------------+
| All settings written    |
| to config file          |
+------------+------------+
             |
             v
+-------------------------+
| Motion daemon stopped   |<-- Stream interruption starts
| Motion daemon started   |
+------------+------------+
             |
             v
+-------------------------+
| Stream resumes          |<-- 2-5 seconds elapsed
+-------------------------+
```

### New Flow (After Integration)

```
User clicks Apply
       |
       v
+-------------------------+
| Categorize changes      |
| (hot-reload vs restart) |
+------------+------------+
             |
     +-------+-------+
     |               |
     v               v
+----------+   +-----------+
| Hot      |   | Restart   |
| Reload   |   | Required  |
| Changes  |   | Changes   |
+----+-----+   +-----+-----+
     |               |
     v               v
+-----------+  +-----------+
| HTTP API  |  | Stop/Start|
| /config/  |  | daemon    |
| set       |  |           |
|           |  | 2-5 sec   |
| INSTANT   |  | delay     |
+-----------+  +-----------+
     |               |
     +-------+-------+
             |
             v
+-------------------------+
| Config persisted to disk|
| Success returned to UI  |
+-------------------------+
```

---

## Notes

### Thread Safety

Motion's hot-reload implementation uses direct variable assignment:
- Integer/boolean parameters: Atomic on modern architectures
- String parameters: Brief inconsistency possible (one frame max)

This matches Motion's existing behavior during config file updates.

### Persistence

The hot-reload API is **runtime only**. MotionEye must continue writing config to disk for persistence across daemon restarts. The flow is:

1. Hot-reload API updates Motion's running state
2. MotionEye writes the same values to the config file
3. Both are now in sync

### Error Handling

If hot-reload fails for any reason:
1. MotionEye should fall back to full restart
2. Log the failure for debugging
3. User experience is no worse than current behavior

### Motion Version Compatibility

This API requires Motion 5.0 built from the latest master branch (commit 1d537be or later). Check for API availability:

```python
async def is_hot_reload_available() -> bool:
    """Check if Motion supports hot reload API."""
    try:
        url = f'http://127.0.0.1:{port}/1/config/set?threshold=1500'
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status == 200
    except:
        return False
```

---

## Summary

| What Changed | Where |
|-------------|-------|
| New API endpoint | `GET /{cam}/config/set?{param}={value}` |
| 72 hot-reloadable params | Detection, overlays, scripts, etc. |
| JSON response format | `{status, parameter, old_value, new_value, hot_reload}` |
| Motion version required | 5.0 (master branch, commit 1d537be+) |

### Benefits

- **No stream interruption** for ~40% of common setting changes
- **Instant feedback** when tuning motion detection
- **Better UX** for text overlay edits
- **Backward compatible** - falls back to restart if needed

---

## Contact

For questions about the Motion API implementation, refer to:
- `motion/doc/plans/MotionEye-Plans/hot-reload-implementation-plan.md`
- `motion/doc/scratchpads/hot-reload-implementation-progress.md`

For MotionEye integration questions, this document serves as the specification.
