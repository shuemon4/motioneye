# Motion 5.0 Hot Reload Integration - Implementation Plan

**Date**: 2025-12-13
**Status**: READY FOR IMPLEMENTATION
**Priority**: High
**Estimated Complexity**: Medium

---

## Executive Summary

This plan details the implementation of Motion 5.0's hot-reload API in MotionEye, enabling runtime configuration updates without daemon restart. This eliminates the 2-5 second video stream interruption users experience when adjusting most camera settings.

---

## Prerequisites

- [x] Motion 5.0 hot-reload API implemented and tested
- [x] Integration guide created (`motion-hot-reload-integration-guide.md`)
- [x] MotionEye codebase analysis completed
- [x] Parameter mappings documented

---

## Implementation Phases

### Phase 1: Constants and Type Definitions

**Files**: `motioneye/config/camera/constants.py`

#### Task 1.1: Add Hot-Reload Parameter Set

Add the `HOT_RELOAD_PARAMS` set containing all 72 parameters that Motion 5.0 can update at runtime.

```python
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
```

#### Task 1.2: Add Restart-Required Parameter Set

Add the `RESTART_REQUIRED_PARAMS` set for parameters that always require daemon restart.

```python
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

---

### Phase 2: Motion Control Functions

**Files**: `motioneye/motionctl.py`

#### Task 2.1: Add Import Statements

Add necessary imports at the top of the file:

```python
import urllib.parse
import json
```

#### Task 2.2: Add `set_config_hot()` Function

Add a new async function to set a single Motion parameter via the hot-reload API.

```python
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

    # Check Motion version
    if not is_motion_50():
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Motion 5.0+ required for hot reload'
        }

    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return {
            'success': False,
            'hot_reload': False,
            'error': f'Could not find motion camera id for camera {camera_id}'
        }

    # URL encode the value
    encoded_value = urllib.parse.quote(str(value), safe='')
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set?{param}={encoded_value}'

    try:
        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )
        resp = await AsyncHTTPClient().fetch(request)

        if resp.code == 200:
            try:
                data = json.loads(resp.body.decode('utf-8'))

                if data.get('status') == 'ok' and data.get('hot_reload'):
                    logging.debug(f'Hot reload: {param}={value} on camera {camera_id}')
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
            except json.JSONDecodeError:
                # Fallback for non-JSON response (older API format)
                logging.debug(f'Hot reload (non-JSON): {param}={value} on camera {camera_id}')
                return {
                    'success': True,
                    'hot_reload': True,
                    'old_value': ''
                }
        else:
            return {
                'success': False,
                'hot_reload': False,
                'error': f'HTTP {resp.code}'
            }

    except Exception as e:
        logging.error(f'Failed to hot-reload {param}: {e}')
        return {
            'success': False,
            'hot_reload': False,
            'error': str(e)
        }
```

#### Task 2.3: Add `apply_config_changes()` Function

Add a function to intelligently apply configuration changes using hot-reload where possible.

```python
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

    # Find changed parameters (only Motion parameters, not @ prefixed MotionEye internal ones)
    all_params = set(old_config.keys()) | set(new_config.keys())
    motion_params = [p for p in all_params if not p.startswith('@')]

    for param in motion_params:
        old_val = old_config.get(param)
        new_val = new_config.get(param)

        # Skip unchanged parameters
        if old_val == new_val:
            continue

        # Skip None -> None
        if old_val is None and new_val is None:
            continue

        # Convert values to string for comparison (Motion API uses strings)
        old_str = str(old_val) if old_val is not None else ''
        new_str = str(new_val) if new_val is not None else ''

        if old_str == new_str:
            continue

        if param in HOT_RELOAD_PARAMS:
            # Try hot reload
            result = await set_config_hot(camera_id, param, new_str)

            if result['success']:
                hot_reloaded.append(param)
                logging.debug(f'Camera {camera_id}: Hot-reloaded {param}={new_str}')
            else:
                # Hot reload failed, will need restart
                restart_params.append(param)
                if result.get('error'):
                    errors.append(f"{param}: {result['error']}")
                logging.debug(f'Camera {camera_id}: {param} requires restart: {result.get("error")}')
        else:
            # Parameter requires restart
            restart_params.append(param)
            logging.debug(f'Camera {camera_id}: {param} requires restart (not in HOT_RELOAD_PARAMS)')

    return {
        'hot_reloaded': hot_reloaded,
        'needs_restart': len(restart_params) > 0,
        'restart_params': restart_params,
        'errors': errors
    }
```

#### Task 2.4: Add `is_hot_reload_available()` Function

Add a function to check if hot-reload API is available (for caching/validation).

```python
async def is_hot_reload_available() -> bool:
    """
    Check if Motion's hot reload API is available.

    Returns:
        True if Motion 5.0+ with hot reload API is running
    """
    if not is_motion_50():
        return False

    if not running():
        return False

    try:
        # Test with a safe parameter query
        url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/0/config/list'
        request = HTTPRequest(
            url,
            connect_timeout=2,
            request_timeout=2,
        )
        resp = await AsyncHTTPClient().fetch(request)
        return resp.code == 200
    except:
        return False
```

---

### Phase 3: Config Handler Integration

**Files**: `motioneye/handlers/config.py`

#### Task 3.1: Modify `set_camera_config()` Inner Function

The key change is in the `set_camera_config()` inner function within `set_config()` method. Currently at line 155, it always signals `on_finish(None, True)` for local motion cameras, indicating restart is needed.

**Current code** (lines 155-167):
```python
async def set_camera_config(camera_id, ui_config, on_finish):
    logging.debug(f'setting config for camera {camera_id}...')

    if camera_id not in camera_ids:
        raise HTTPError(404, 'no such camera')

    local_config = config.get_camera(camera_id)
    if utils.is_local_motion_camera(local_config):
        local_config = config.motion_camera_ui_to_dict(ui_config, local_config)

        config.set_camera(camera_id, local_config)

        on_finish(None, True)  # (no error, motion needs restart)
```

**Modified code**:
```python
async def set_camera_config(camera_id, ui_config, on_finish):
    logging.debug(f'setting config for camera {camera_id}...')

    if camera_id not in camera_ids:
        raise HTTPError(404, 'no such camera')

    local_config = config.get_camera(camera_id)
    if utils.is_local_motion_camera(local_config):
        # Get old config before update
        old_motion_config = dict(local_config)

        # Convert UI to new Motion config
        new_motion_config = config.motion_camera_ui_to_dict(ui_config, local_config)

        # Try to apply changes using hot-reload where possible
        needs_restart = True  # Default to restart for safety

        if motionctl.is_motion_50() and motionctl.running():
            try:
                result = await motionctl.apply_config_changes(
                    camera_id, old_motion_config, new_motion_config
                )

                if result['hot_reloaded']:
                    logging.info(
                        f'Camera {camera_id}: Hot-reloaded {len(result["hot_reloaded"])} parameters: '
                        f'{", ".join(result["hot_reloaded"][:5])}{"..." if len(result["hot_reloaded"]) > 5 else ""}'
                    )

                needs_restart = result['needs_restart']

                if result['restart_params']:
                    logging.info(
                        f'Camera {camera_id}: Restart needed for: '
                        f'{", ".join(result["restart_params"][:5])}{"..." if len(result["restart_params"]) > 5 else ""}'
                    )

            except Exception as e:
                logging.error(f'Hot-reload failed for camera {camera_id}: {e}')
                needs_restart = True  # Fall back to restart on error

        # Always persist to disk
        config.set_camera(camera_id, new_motion_config)

        on_finish(None, needs_restart)
```

---

### Phase 4: UI Parameter Mapping

**Files**: `motioneye/config/camera/converters.py`

#### Task 4.1: Add UI-to-Motion Parameter Mapping Helper

Add a helper to map UI parameter names to Motion parameter names for frontend use.

```python
# Mapping from UI parameter names to Motion parameter names
UI_TO_MOTION_PARAMS = {
    'frame_change_threshold': 'threshold',
    'max_frame_change_threshold': 'threshold_maximum',
    'auto_threshold_tuning': 'threshold_tune',
    'noise_level': 'noise_level',
    'auto_noise_detect': 'noise_tune',
    'despeckle_filter': 'despeckle_filter',
    'minimum_motion_frames': 'minimum_motion_frames',
    'event_gap': 'event_gap',
    'light_switch_detect': 'lightswitch_percent',
    'text_scale': 'text_scale',
    'streaming_framerate': 'stream_maxrate',
    'streaming_quality': 'stream_quality',
    'streaming_motion': 'stream_motion',
    'image_quality': 'picture_quality',
    'movie_quality': 'movie_quality',
    'movie_file_name': 'movie_filename',
    'max_movie_length': 'movie_max_time',
    'pre_capture': 'pre_capture',
    'post_capture': 'post_capture',
    'snapshot_interval': 'snapshot_interval',
    # Parameters that require restart
    'resolution': ['width', 'height'],  # Special: maps to two params
    'rotation': 'rotate',
    'movie_format': 'movie_codec',
    'streaming_port': 'stream_port',
}


def ui_param_requires_restart(ui_param: str) -> bool:
    """
    Check if a UI parameter change will require daemon restart.

    Args:
        ui_param: The UI parameter name (from frontend)

    Returns:
        True if changing this parameter requires restart
    """
    from motioneye.config.camera.constants import RESTART_REQUIRED_PARAMS, HOT_RELOAD_PARAMS

    motion_param = UI_TO_MOTION_PARAMS.get(ui_param)

    if motion_param is None:
        # Unknown mapping - assume restart needed for safety
        return True

    if isinstance(motion_param, list):
        # Multiple Motion params - restart if any require it
        return any(p in RESTART_REQUIRED_PARAMS or p not in HOT_RELOAD_PARAMS for p in motion_param)

    return motion_param in RESTART_REQUIRED_PARAMS or motion_param not in HOT_RELOAD_PARAMS
```

---

### Phase 5: Testing

**Files**: New test files

#### Task 5.1: Create Unit Tests

Create `tests/test_hot_reload.py`:

```python
"""Tests for Motion 5.0 hot-reload integration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from motioneye.config.camera.constants import HOT_RELOAD_PARAMS, RESTART_REQUIRED_PARAMS


class TestParameterClassification:
    """Test parameter classification constants."""

    def test_hot_reload_params_not_empty(self):
        """HOT_RELOAD_PARAMS should contain parameters."""
        assert len(HOT_RELOAD_PARAMS) > 0

    def test_restart_required_params_not_empty(self):
        """RESTART_REQUIRED_PARAMS should contain parameters."""
        assert len(RESTART_REQUIRED_PARAMS) > 0

    def test_no_overlap(self):
        """Hot-reload and restart-required sets should not overlap."""
        overlap = HOT_RELOAD_PARAMS & RESTART_REQUIRED_PARAMS
        assert len(overlap) == 0, f"Parameters in both sets: {overlap}"

    def test_threshold_is_hot_reloadable(self):
        """Threshold should be hot-reloadable."""
        assert 'threshold' in HOT_RELOAD_PARAMS

    def test_width_requires_restart(self):
        """Width should require restart."""
        assert 'width' in RESTART_REQUIRED_PARAMS

    def test_text_left_is_hot_reloadable(self):
        """Text overlay should be hot-reloadable."""
        assert 'text_left' in HOT_RELOAD_PARAMS


class TestSetConfigHot:
    """Test set_config_hot function."""

    @pytest.mark.asyncio
    async def test_rejects_non_hot_reload_param(self):
        """Should reject parameters not in HOT_RELOAD_PARAMS."""
        from motioneye import motionctl

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            result = await motionctl.set_config_hot(1, 'width', '1920')

        assert result['success'] is False
        assert result['hot_reload'] is False
        assert 'restart' in result['error'].lower()

    @pytest.mark.asyncio
    async def test_rejects_old_motion_version(self):
        """Should reject if Motion < 5.0."""
        from motioneye import motionctl

        with patch.object(motionctl, 'is_motion_50', return_value=False):
            result = await motionctl.set_config_hot(1, 'threshold', '2000')

        assert result['success'] is False
        assert 'Motion 5.0' in result['error']


class TestApplyConfigChanges:
    """Test apply_config_changes function."""

    @pytest.mark.asyncio
    async def test_identifies_changed_params(self):
        """Should correctly identify changed parameters."""
        from motioneye import motionctl

        old_config = {'threshold': '1500', 'width': '1920', '@enabled': True}
        new_config = {'threshold': '2000', 'width': '1920', '@enabled': True}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = {'success': True, 'hot_reload': True, 'old_value': '1500'}

                result = await motionctl.apply_config_changes(1, old_config, new_config)

        assert 'threshold' in result['hot_reloaded']
        assert result['needs_restart'] is False

    @pytest.mark.asyncio
    async def test_mixed_changes(self):
        """Should handle mix of hot-reload and restart-required changes."""
        from motioneye import motionctl

        old_config = {'threshold': '1500', 'width': '1920'}
        new_config = {'threshold': '2000', 'width': '1280'}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = {'success': True, 'hot_reload': True, 'old_value': '1500'}

                result = await motionctl.apply_config_changes(1, old_config, new_config)

        assert 'threshold' in result['hot_reloaded']
        assert 'width' in result['restart_params']
        assert result['needs_restart'] is True
```

#### Task 5.2: Integration Test Script

Create `scripts/test_hot_reload_integration.sh`:

```bash
#!/bin/bash
# Integration test for Motion 5.0 hot-reload on Pi 5

set -e

PI_HOST="${1:-192.168.1.176}"
PI_USER="${2:-admin}"

echo "Testing hot-reload integration on $PI_HOST"
echo "=========================================="

# Check Motion is running
echo -n "Checking Motion status... "
ssh $PI_USER@$PI_HOST "pgrep -x motion > /dev/null" && echo "OK" || { echo "FAILED - Motion not running"; exit 1; }

# Check Motion version
echo -n "Checking Motion version... "
VERSION=$(ssh $PI_USER@$PI_HOST "motion -h 2>&1 | grep -oP 'Version \K[0-9.]+'")
echo "$VERSION"

if [[ ! "$VERSION" =~ ^5\. ]]; then
    echo "ERROR: Motion 5.0+ required, found $VERSION"
    exit 1
fi

# Test hot-reload API endpoint
echo -n "Testing hot-reload API... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=1500'" 2>/dev/null)
if echo "$RESPONSE" | grep -q "status"; then
    echo "OK"
else
    echo "FAILED - Response: $RESPONSE"
    exit 1
fi

# Test threshold change
echo -n "Testing threshold hot-reload... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=2000'")
if echo "$RESPONSE" | grep -q '"hot_reload": true\|"hot_reload":true'; then
    echo "OK"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Test width change (should fail/require restart)
echo -n "Testing width (should require restart)... "
RESPONSE=$(ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?width=1280'")
if echo "$RESPONSE" | grep -q '"hot_reload": false\|"hot_reload":false\|requires\|restart'; then
    echo "OK (correctly rejected)"
else
    echo "WARNING - Response: $RESPONSE"
fi

# Reset threshold
ssh $PI_USER@$PI_HOST "curl -s 'http://localhost:7999/1/config/set?threshold=1500'" > /dev/null

echo ""
echo "=========================================="
echo "Integration tests completed"
```

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `motioneye/config/camera/constants.py` | MODIFY | Add `HOT_RELOAD_PARAMS` and `RESTART_REQUIRED_PARAMS` sets |
| `motioneye/motionctl.py` | MODIFY | Add `set_config_hot()`, `apply_config_changes()`, `is_hot_reload_available()` |
| `motioneye/handlers/config.py` | MODIFY | Update `set_camera_config()` to use hot-reload |
| `motioneye/config/camera/converters.py` | MODIFY | Add `UI_TO_MOTION_PARAMS` and `ui_param_requires_restart()` |
| `tests/test_hot_reload.py` | NEW | Unit tests for hot-reload functionality |
| `scripts/test_hot_reload_integration.sh` | NEW | Integration test script for Pi 5 |

---

## Deployment Checklist

### Pre-Deployment

- [ ] Run unit tests locally
- [ ] Verify Motion 5.0 is installed on Pi 5
- [ ] Backup current MotionEye installation

### Deployment Steps

1. Sync code to Pi 5:
   ```bash
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
     /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/
   ```

2. Install updated package:
   ```bash
   ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"
   ```

3. Restart MotionEye service:
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
   ```

4. Run integration tests:
   ```bash
   ./scripts/test_hot_reload_integration.sh 192.168.1.176
   ```

### Post-Deployment Validation

- [ ] Access MotionEye UI at http://192.168.1.176:8765/
- [ ] Change motion detection threshold - verify no stream interruption
- [ ] Change resolution - verify stream briefly interrupts (expected)
- [ ] Check logs for hot-reload success messages
- [ ] Verify settings persist after Motion restart

---

## Rollback Plan

If issues are encountered:

1. Stop MotionEye:
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl stop motioneye"
   ```

2. Reinstall previous version:
   ```bash
   ssh admin@192.168.1.176 "cd ~/motioneye-backup && sudo pip3 install . --break-system-packages"
   ```

3. Restart MotionEye:
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl start motioneye"
   ```

---

## Future Enhancements

### Phase 6 (Optional): Frontend Improvements

1. Add visual indicator for settings that require restart
2. Show "Applied without restart" vs "Restarted" message
3. Add real-time parameter validation

### Phase 7 (Optional): Performance Optimization

1. Batch multiple hot-reload calls into single request (if Motion supports)
2. Cache hot-reload availability check
3. Parallel hot-reload for independent parameters

---

## Technical Notes

### Thread Safety

Motion's hot-reload API handles thread safety internally. MotionEye makes sequential HTTP calls for each parameter change.

### Error Recovery

If hot-reload fails mid-operation:
1. Failed parameters are added to `restart_params`
2. Successful changes remain applied
3. Full restart handles the remaining changes

### Config Persistence

The hot-reload API only affects runtime state. MotionEye always writes to disk to ensure persistence across Motion restarts.

---

## References

- `docs/plans/MotionEye-Plans/motion-hot-reload-integration-guide.md` - Full API specification
- `docs/plans/MotionEye-Plans/motion-hot-reload-api-request-20251213-0830.md` - Original requirements
- `docs/scratchpads/hot-reload-implementation-analysis-20251213-1830.md` - Analysis notes

---

## Implementation Summary

### Completed: 2025-12-13

**Status**: ✅ ALL PHASES COMPLETE

### Phase 1: Constants and Type Definitions ✅
- Added `HOT_RELOAD_PARAMS` set (81 parameters) to `motioneye/config/camera/constants.py`
- Added `RESTART_REQUIRED_PARAMS` set (61 parameters)
- Verified no overlap between sets

### Phase 2: Motion Control Functions ✅
- Added imports: `json`, `urllib.parse` to `motioneye/motionctl.py`
- Implemented `set_config_hot()` async function for single parameter hot-reload
- Implemented `apply_config_changes()` async function for intelligent bulk changes
- Implemented `is_hot_reload_available()` async function for capability check

### Phase 3: Config Handler Integration ✅
- Modified `set_camera_config()` in `motioneye/handlers/config.py`
- Saves old config before conversion for change detection
- Calls `motionctl.apply_config_changes()` when Motion 5.0 is running
- Logs hot-reloaded and restart-required parameters
- Falls back to restart on any error

### Phase 4: UI Parameter Mapping ✅
- Added `UI_TO_MOTION_PARAMS` dictionary to `motioneye/config/camera/converters.py`
- Implemented `ui_param_requires_restart()` helper function

### Phase 5: Testing ✅
- Created comprehensive unit tests in `tests/test_hot_reload.py`
  - 23 test methods across 4 test classes
  - All tests passing
- Created integration test script `scripts/test_hot_reload_integration.sh`

### Test Results
```
tests/test_hot_reload.py: 23 passed in 0.08s
```

### Files Modified
| File | Change |
|------|--------|
| `motioneye/config/camera/constants.py` | Added HOT_RELOAD_PARAMS, RESTART_REQUIRED_PARAMS |
| `motioneye/motionctl.py` | Added set_config_hot, apply_config_changes, is_hot_reload_available |
| `motioneye/handlers/config.py` | Modified set_camera_config to use hot-reload |
| `motioneye/config/camera/converters.py` | Added UI_TO_MOTION_PARAMS, ui_param_requires_restart |

### Files Created
| File | Purpose |
|------|---------|
| `tests/test_hot_reload.py` | Unit tests for hot-reload functionality |
| `scripts/test_hot_reload_integration.sh` | Integration test script for Pi 5 |

### Next Steps
- Deploy to Pi 5 for integration testing
- Run integration test script
- Validate via MotionEye web interface
