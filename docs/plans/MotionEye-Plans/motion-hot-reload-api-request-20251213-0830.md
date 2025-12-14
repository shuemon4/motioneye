# Motion 5.0 Hot Reload API Request

**Date**: 2025-12-13
**From**: MotionEye Development
**To**: Motion 5.0 Development
**Priority**: Enhancement Request

---

## Executive Summary

MotionEye currently restarts the entire Motion daemon for ALL configuration changes, causing a 2-5 second video stream interruption. Many settings (motion detection tuning, text overlays, event handlers) don't fundamentally require a daemon restart. We're requesting Motion 5.0 expose HTTP API endpoints to modify these parameters at runtime.

---

## The Problem

### Current User Experience

1. User adjusts motion detection sensitivity slider
2. User clicks "Apply"
3. Video stream goes black for 2-5 seconds
4. Motion daemon fully restarts
5. Stream resumes

**This happens for EVERY setting change**, even trivial ones like changing overlay text.

### Why MotionEye Does This

MotionEye has no way to dynamically update Motion's running configuration. The only options are:

1. **Full restart** - Write config to disk, stop daemon, start daemon
2. **Existing HTTP API** - Only supports: detection start/pause, snapshot trigger, status queries

There's no middle ground for "update this parameter without restarting."

---

## Existing Motion 5.0 HTTP Control API

Motion already exposes these endpoints at `http://127.0.0.1:{webcontrol_port}/{camera_id}/`:

### Currently Supported (No Restart Needed)

| Endpoint | Purpose |
|----------|---------|
| `/detection/status` | Query if motion detection is active |
| `/detection/start` | Enable motion detection |
| `/detection/pause` | Disable motion detection |
| `/action/snapshot` | Trigger manual snapshot |
| `/action/eventstart` | Manually trigger event start |
| `/action/eventend` | Manually trigger event end |
| `/config/list` | List current configuration |
| `/config/get?query={param}` | Get specific parameter value |

### NOT Currently Supported

| Desired Endpoint | Purpose |
|------------------|---------|
| `/config/set?{param}={value}` | **Set parameter at runtime** |

---

## Requested: Runtime Configuration API

### Proposed Endpoint

```
GET /config/set?{parameter}={value}
```

or

```
POST /config/set
Content-Type: application/x-www-form-urlencoded
{parameter}={value}
```

### Response Format

```json
{
  "status": "ok|error",
  "parameter": "threshold",
  "old_value": "1500",
  "new_value": "2000",
  "requires_restart": false
}
```

If a parameter cannot be changed at runtime:
```json
{
  "status": "error",
  "parameter": "width",
  "message": "Parameter requires daemon restart",
  "requires_restart": true
}
```

---

## Parameters Requested for Hot Reload

### Tier 1: Motion Detection (High Priority)

These are the most frequently adjusted settings. Users tune these while watching the live stream.

| Parameter | Type | Description | Current Default |
|-----------|------|-------------|-----------------|
| `threshold` | int | Pixels changed to trigger motion | 1500 |
| `threshold_maximum` | int | Max threshold (0=unlimited) | 0 |
| `threshold_tune` | bool | Auto-tune threshold | off |
| `noise_level` | int | Noise filtering level | 32 |
| `noise_tune` | bool | Auto-tune noise level | on |
| `despeckle_filter` | string | Despeckle filter string | EedDl |
| `minimum_motion_frames` | int | Frames before event triggers | 1 |
| `event_gap` | int | Seconds gap between events | 60 |
| `lightswitch_percent` | int | Light change % to ignore | 0 |
| `lightswitch_frames` | int | Frames to detect light change | 5 |

**Use Case**: User sees too many false positives, wants to increase threshold while watching stream to find optimal value.

### Tier 2: Text Overlays (Medium Priority)

| Parameter | Type | Description |
|-----------|------|-------------|
| `text_left` | string | Text on left side of frame |
| `text_right` | string | Text on right side of frame |
| `text_scale` | int | Text size (1-10) |
| `locate_motion_mode` | enum | off/on/preview - draw motion boxes |
| `locate_motion_style` | enum | box/redbox/cross/redcross |

**Use Case**: User wants to update camera name or timestamp format without stream interruption.

### Tier 3: Event Handlers (Lower Priority)

| Parameter | Type | Description |
|-----------|------|-------------|
| `on_event_start` | string | Command executed on motion start |
| `on_event_end` | string | Command executed on motion end |
| `on_motion_detected` | string | Command per motion frame |
| `on_movie_start` | string | Command when recording starts |
| `on_movie_end` | string | Command when recording ends |
| `on_picture_save` | string | Command after snapshot saved |

**Use Case**: User updates notification script path or parameters.

### Tier 4: Mask Updates (Medium Priority)

| Parameter | Type | Description |
|-----------|------|-------------|
| `mask_file` | string | Path to motion mask PGM file |
| `mask_privacy` | string | Path to privacy mask PGM file |
| `smart_mask_speed` | int | Adaptive mask learning speed (0=off) |

**Use Case**: User draws new motion mask zones in UI, wants immediate application.

---

## Parameters That MUST Require Restart

We understand these fundamentally change the capture pipeline:

| Category | Parameters |
|----------|------------|
| **Device** | `videodevice`, `libcam_device`, `mmalcam_name`, `netcam_url` |
| **Resolution** | `width`, `height`, `framerate` |
| **Rotation** | `rotate` (requires buffer reallocation) |
| **Streaming** | `webcontrol_port`, `stream_port` |
| **Recording Format** | `movie_output`, `movie_codec`, `movie_container` |
| **Storage** | `target_dir` (affects file handles) |

MotionEye will continue restarting the daemon for these.

---

## Technical Considerations for Motion Implementation

### Thread Safety

Motion's configuration is accessed from multiple threads:
- Main loop (motion detection)
- Stream thread (MJPEG output)
- Event handler thread
- Watchdog thread

**Suggestion**: Use atomic operations or mutex for parameter updates. Most parameters are read once per frame, so brief locking is acceptable.

### Memory Considerations

- String parameters (`text_left`, `on_event_start`) require careful handling
- Suggest: Copy-on-write or double-buffering for string parameters
- Integer parameters can use atomic stores

### Persistence

Two options:
1. **Runtime only** - Parameter change lost on restart (MotionEye writes to disk separately)
2. **Write-through** - Also update config file (may cause I/O on embedded systems)

**Preference**: Runtime only. MotionEye already manages config file persistence.

### CPU Impact Concern

We want to ensure this doesn't add CPU overhead to the frame processing loop:

- **Avoid**: Checking for parameter updates every frame
- **Prefer**: Direct variable update via HTTP handler, frame loop reads latest value
- **Acceptable**: Minimal mutex around parameter reads (microseconds)

---

## MotionEye Integration Plan

Once Motion exposes `/config/set`, MotionEye will:

### 1. Categorize Settings

```python
# motioneye/config/camera/constants.py

HOT_RELOAD_PARAMS = {
    'threshold', 'threshold_maximum', 'threshold_tune',
    'noise_level', 'noise_tune', 'despeckle_filter',
    'minimum_motion_frames', 'event_gap',
    'lightswitch_percent', 'lightswitch_frames',
    'text_left', 'text_right', 'text_scale',
    'locate_motion_mode', 'locate_motion_style',
    'mask_file', 'mask_privacy', 'smart_mask_speed',
    'on_event_start', 'on_event_end', 'on_movie_end',
    'on_picture_save', 'on_motion_detected'
}

RESTART_REQUIRED_PARAMS = {
    'videodevice', 'libcam_device', 'width', 'height',
    'framerate', 'rotate', 'webcontrol_port', 'movie_output',
    'movie_codec', 'movie_container', 'target_dir', 'netcam_url'
}
```

### 2. Smart Apply Logic

```python
# motioneye/handlers/config.py

async def set_camera_config(camera_id, ui_config):
    old_config = get_current_config(camera_id)
    new_config = motion_camera_ui_to_dict(ui_config)

    changed_params = get_changed_params(old_config, new_config)

    hot_reload_changes = changed_params & HOT_RELOAD_PARAMS
    restart_changes = changed_params - HOT_RELOAD_PARAMS

    # Apply hot-reloadable changes via HTTP API
    for param in hot_reload_changes:
        await motionctl.set_config(camera_id, param, new_config[param])

    # Only restart if non-hot-reloadable settings changed
    needs_restart = len(restart_changes) > 0

    # Always persist to disk
    write_camera_config(camera_id, new_config)

    return needs_restart
```

### 3. New motionctl Function

```python
# motioneye/motionctl.py

async def set_config(camera_id: int, param: str, value: str) -> bool:
    """Set a Motion parameter at runtime via HTTP API."""
    motion_camera_id = get_motion_camera_id(camera_id)
    port = get_motion_control_port()

    url = f'http://127.0.0.1:{port}/{motion_camera_id}/config/set?{param}={value}'

    try:
        response = await http_client.get(url, timeout=5)
        return response.status == 200
    except Exception as e:
        logging.error(f'Failed to hot-reload {param}: {e}')
        return False
```

### 4. Frontend Feedback

```javascript
// Show user which settings will cause stream interruption
function willRequireRestart(changedSettings) {
    const restartParams = new Set([
        'resolution', 'framerate', 'rotation', 'device',
        'streaming_port', 'movie_format', 'storage_path'
    ]);
    return changedSettings.some(s => restartParams.has(s));
}

// UI indicator
if (willRequireRestart(changes)) {
    showWarning('This change will briefly interrupt the video stream');
} else {
    showInfo('Changes will apply without stream interruption');
}
```

---

## Alternative Solutions (If Full API Not Feasible)

### Alternative A: Config File Watcher

Motion watches config file for changes and reloads safe parameters.

**Pros**: Simple to implement in Motion
**Cons**: File I/O overhead, delayed application

### Alternative B: SIGHUP for Partial Reload

Send SIGHUP to reload "safe" parameters from config file without full restart.

**Pros**: Familiar Unix pattern
**Cons**: All-or-nothing, can't reload single parameter

### Alternative C: Shared Memory Interface

Motion reads certain parameters from shared memory, MotionEye writes updates there.

**Pros**: Zero-copy, very fast
**Cons**: Complex IPC, platform-specific

### Alternative D: Unix Socket with Config Commands

Motion listens on Unix socket for configuration commands.

**Pros**: Lower overhead than HTTP
**Cons**: Separate protocol to Motion's existing HTTP control

---

## Testing Plan

Once Motion implements the API, we'll validate:

1. **Functional**: Each Tier 1 parameter can be changed via API
2. **Stream Continuity**: Video stream maintains 30fps during parameter changes
3. **CPU Impact**: No measurable CPU increase from API endpoint
4. **Persistence**: Runtime changes don't corrupt config file
5. **Edge Cases**: Rapid successive changes, invalid values, concurrent requests

---

## Summary of Request

| Priority | Request | Impact |
|----------|---------|--------|
| **High** | `/config/set?{param}={value}` endpoint | Enables hot reload |
| **High** | Tier 1 params (motion detection) | Most user benefit |
| **Medium** | Tier 2 params (text overlays) | Convenience |
| **Medium** | Response with `requires_restart` flag | Clean degradation |
| **Low** | Tier 3/4 params | Nice to have |

---

## Contact

For questions about MotionEye's requirements or integration approach, this document serves as the specification. The MotionEye codebase is available for reference at the paths mentioned in the Integration Plan section.

---

## Appendix A: Current MotionEye Apply Flow

```
User clicks Apply
       │
       ▼
┌─────────────────────────┐
│ Frontend: doApply()     │
│ POST /config/0/set/     │
│ {camera configs as JSON}│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Backend: set_config()   │
│ - Validate config       │
│ - Convert UI → Motion   │
│ - Write to disk         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ motionctl.stop()        │◄── Stream interruption starts
│ - Kill motion process   │
│ - Wait for termination  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ motionctl.start()       │
│ - Launch motion daemon  │
│ - Wait for streams      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Return success to UI    │◄── Stream interruption ends
│ - Frontend refreshes    │    (2-5 seconds elapsed)
└─────────────────────────┘
```

## Appendix B: Proposed Hot Reload Flow

```
User clicks Apply
       │
       ▼
┌─────────────────────────┐
│ Frontend: doApply()     │
│ POST /config/0/set/     │
│ {camera configs as JSON}│
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Backend: set_config()   │
│ - Validate config       │
│ - Categorize changes    │
│ - Write to disk         │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐   ┌─────────────────┐
│ Hot     │   │ Restart         │
│ Reload  │   │ Required        │
│ Changes │   │ Changes         │
└────┬────┘   └────────┬────────┘
     │                 │
     ▼                 ▼
┌───────────────┐ ┌─────────────────┐
│ HTTP API:     │ │ motionctl.stop()│
│ /config/set   │ │ motionctl.start │
│ per parameter │ │ (full restart)  │
│               │ │                 │
│ NO STREAM     │ │ 2-5 sec         │
│ INTERRUPTION  │ │ interruption    │
└───────┬───────┘ └────────┬────────┘
        │                  │
        └───────┬──────────┘
                │
                ▼
┌─────────────────────────┐
│ Return success to UI    │
│ - Indicate if restarted │
└─────────────────────────┘
```

## Appendix C: Motion Source Code References

For the Motion developer reviewing this request, relevant source files:

| File | Purpose |
|------|---------|
| `src/webu.c` | HTTP webcontrol implementation |
| `src/webu_getact.c` | GET action handlers (detection, snapshot) |
| `src/conf.c` | Configuration loading and defaults |
| `src/motion.c` | Main loop, parameter access |
| `src/logger.c` | Logging system |

The existing `/detection/start` and `/detection/pause` endpoints in `webu_getact.c` demonstrate the pattern for runtime state changes.
