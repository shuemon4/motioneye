# Hot Reload Implementation Analysis Scratchpad

**Date**: 2025-12-13
**Purpose**: Working notes for Motion 5.0 Hot Reload API Integration

---

## Summary of Available Documentation

1. **Integration Guide** (`motion-hot-reload-integration-guide.md`):
   - Complete API specification for Motion 5.0's `/config/set` endpoint
   - List of 72 hot-reloadable parameters
   - List of parameters requiring restart
   - Sample implementation code for MotionEye

2. **API Request** (`motion-hot-reload-api-request-20251213-0830.md`):
   - Original requirements document
   - Explains the user pain point (2-5 second stream interruption)
   - Tiered priority list of parameters

---

## Current MotionEye Architecture Analysis

### Key Files Affected

| File | Purpose | Changes Needed |
|------|---------|----------------|
| `motioneye/motionctl.py` | Motion daemon control | Add `set_config_hot()` and `apply_config_changes()` functions |
| `motioneye/handlers/config.py` | Config HTTP handlers | Modify `set_config()` to use hot reload where possible |
| `motioneye/config/camera/constants.py` | Shared constants | Add `HOT_RELOAD_PARAMS` and `RESTART_REQUIRED_PARAMS` sets |
| `motioneye/config/camera/converters.py` | UI ↔ Config conversion | Potentially add parameter mapping helpers |
| `motioneye/settings.py` | Global settings | Already has `MOTION_CONTROL_PORT` (7999) |

### Existing Motion Control Functions

From `motionctl.py`:

1. **`start()`** - Starts motion daemon (lines 82-149)
2. **`stop()`** - Stops motion daemon (lines 151-194)
3. **`running()`** - Checks if motion is running (lines 197-213)
4. **`get_motion_detection()`** - GET `/detection/status` (lines 220-245)
5. **`set_motion_detection()`** - GET `/detection/{pause|start}` (lines 248-282)
6. **`take_snapshot()`** - GET `/action/snapshot` (lines 285-308)
7. **`camera_id_to_motion_camera_id()`** - Translates IDs (lines 325-341)
8. **`is_motion_50()`** - Version check for 5.0+ (lines 375-380)

**Pattern observed**: Uses Tornado's `AsyncHTTPClient` for all Motion API calls.

### Current Config Apply Flow

From `handlers/config.py`:

1. `set_config()` method receives UI config (line 144)
2. Inner `set_camera_config()` function (line 155):
   - Gets local config
   - Converts UI to Motion dict via `config.motion_camera_ui_to_dict()`
   - Saves config via `config.set_camera()`
   - Signals restart needed (`on_finish(None, True)`)
3. `finish()` function (line 282):
   - If restart needed, calls `motionctl.stop()` then `motionctl.start()`

**Key insight**: The restart decision is currently binary - any camera config change triggers restart.

---

## Parameter Mapping Analysis

### MotionEye UI ↔ Motion Parameters

From `converters.py`, the mapping between UI names and Motion parameters:

| UI Parameter | Motion Parameter | Hot Reloadable? |
|--------------|------------------|-----------------|
| `frame_change_threshold` | `threshold` | YES |
| `max_frame_change_threshold` | `threshold_maximum` | YES |
| `auto_threshold_tuning` | `threshold_tune` | YES |
| `noise_level` | `noise_level` (scaled by 2.55) | YES |
| `auto_noise_detect` | `noise_tune` | YES |
| `despeckle_filter` | `despeckle_filter` | YES |
| `minimum_motion_frames` | `minimum_motion_frames` | YES |
| `event_gap` | `event_gap` | YES |
| `light_switch_detect` | `lightswitch_percent` | YES |
| `name` | `camera_name` / `text_left` | YES (text_left only) |
| `text_overlay` settings | `text_left`, `text_right`, `text_scale` | YES |
| `streaming_framerate` | `stream_maxrate` | YES |
| `streaming_quality` | `stream_quality` | YES |
| `image_quality` | `picture_quality` | YES |
| `movie_quality` | `movie_quality` | YES |
| `movie_file_name` | `movie_filename` | YES |
| `max_movie_length` | `movie_max_time` | YES |
| `resolution` | `width`, `height` | NO (restart) |
| `rotation` | `rotate` | NO (restart) |
| `movie_format` | `movie_codec`/`movie_container` | NO (restart) |
| `streaming_port` | `stream_port` | NO (restart) |

### Value Transformations

Some parameters require transformation between UI and Motion values:

1. **noise_level**: `round(ui_value * 2.55)` (UI 0-100 → Motion 0-255)
2. **threshold**: `ui_percent * width * height / 100` (percentage → pixel count)
3. **despeckle_filter**: Empty string if disabled, `EedDl` if enabled
4. **smart_mask_speed**: `11 - ui_sluggishness` (inverted scale)

---

## Implementation Considerations

### 1. Version Detection

Motion 5.0 is required. Use existing `is_motion_50()` function.

```python
if not motionctl.is_motion_50():
    # Fall back to full restart for older Motion versions
    return needs_full_restart()
```

### 2. API Availability Check

The integration guide suggests checking if the API is available:

```python
async def is_hot_reload_available() -> bool:
    """Check if Motion supports hot reload API."""
    try:
        url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/1/config/set?threshold=1500'
        request = HTTPRequest(url, connect_timeout=2, request_timeout=2)
        resp = await AsyncHTTPClient().fetch(request)
        return resp.code == 200
    except:
        return False
```

### 3. Response Parsing

Motion returns JSON with status information:

```json
{
  "status": "ok",
  "parameter": "threshold",
  "old_value": "1500",
  "new_value": "2000",
  "hot_reload": true
}
```

Need to parse this and handle `"hot_reload": false` cases.

### 4. Error Handling Strategy

1. **API call fails** → Fall back to full restart
2. **Parameter rejected** → Add to restart list
3. **Partial success** → Hot-reload what worked, restart for failures

### 5. Config Persistence

The hot-reload API is runtime-only. MotionEye must still:
1. Write config to disk (for persistence across restarts)
2. Keep runtime and disk in sync

---

## UI/UX Considerations

### Frontend Feedback

Could add visual feedback to indicate which changes require restart:

1. Mark settings that will cause stream interruption
2. Show message on Apply button: "Will apply without stream interruption" vs "Will briefly interrupt stream"

### Response Enhancement

Modify `set_config()` response to include:

```json
{
  "success": true,
  "restarted": false,
  "hot_reloaded": ["threshold", "noise_level", "text_left"],
  "message": "Applied 3 settings without restart"
}
```

---

## Testing Strategy

### Unit Tests

1. Test parameter classification (hot-reload vs restart)
2. Test value transformations
3. Test error handling paths

### Integration Tests

1. Verify hot-reload applies threshold change
2. Verify stream continuity during hot-reload
3. Verify full restart for width/height change
4. Verify mixed changes (some hot-reload, some restart)

### Manual Validation on Pi 5

1. SSH to Pi and monitor Motion logs
2. Change threshold via UI, verify no restart
3. Change resolution via UI, verify restart occurs
4. Monitor stream for interruption during changes

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| API not available (older Motion) | Check version, fall back to restart |
| Hot-reload fails mid-operation | Track partial success, restart if needed |
| Race conditions during config apply | Apply changes sequentially |
| Persistence out of sync with runtime | Always write to disk before/after hot-reload |
| Breaking existing functionality | Extensive testing, gradual rollout |

---

## Dependencies

### Python Packages (already present)

- `tornado` (AsyncHTTPClient, IOLoop) - already in use
- `logging` - already in use
- `urllib.parse` (quote) - already in use

### No New Dependencies Required

The implementation uses existing libraries and patterns from the codebase.

---

## Open Questions

1. **Should we cache hot-reload capability?**
   - First call checks if API exists
   - Cache result for session lifetime
   - Clear cache on Motion restart

2. **Batch vs Individual Parameter Updates?**
   - Motion API supports one parameter per request
   - Could batch with multiple concurrent requests
   - Or sequential for simplicity/reliability

3. **Frontend changes scope?**
   - Minimal: Just improve response handling
   - Medium: Add "will restart" indicators
   - Full: Real-time parameter validation

---

## Related Files to Review

- [ ] `motioneye/static/js/main.js` - Frontend Apply logic
- [ ] `motioneye/remote.py` - Remote camera handling (may need updates)
- [ ] `tests/` - Check for existing config tests

---

## Notes on Motion 5.0 Parameter Changes

From the background bash output, Motion 5.0 has renamed some parameters:

```
[ALR][ALL][mo00] edit_set_depr: "movie_codec" replaced with "movie_container" after version 5.0.0
```

This affects:
- `movie_codec` → `movie_container` (for container format)
- `camera_name` → `device_name` (for camera naming)

The `constants.py` already has `MOTION_50_PARAMS` and `MOTION_50_REMOVED_PARAMS` sets to handle this.

---

## Implementation Priority

1. **Phase 1**: Core hot-reload infrastructure
   - Add constants (parameter sets)
   - Add `set_config_hot()` function
   - Add `apply_config_changes()` function

2. **Phase 2**: Config handler integration
   - Modify `set_camera_config()` to use hot-reload
   - Handle error cases and fallback

3. **Phase 3**: Testing and validation
   - Unit tests
   - Integration tests on Pi 5

4. **Phase 4**: Frontend enhancements (optional)
   - Add restart indicators
   - Improve user feedback

