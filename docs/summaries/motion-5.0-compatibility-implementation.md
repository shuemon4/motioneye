# Motion 5.0 Compatibility Implementation Summary

## Overview

This document summarizes the implementation of Motion 5.0 compatibility in MotionEye. Motion 5.0 introduced several breaking changes that required updates to MotionEye's configuration handling and MJPG streaming.

## Breaking Changes in Motion 5.0

1. **`stream_port` removed** - Streams now served via webcontrol interface
2. **`webcontrol_interface`** - Changed from integer (0,1,2) to string ("off","default","user","simple")
3. **Stream URLs changed** - From `http://host:stream_port/` to `http://host:webcontrol_port/{cam_id}/stream`
4. **Parameter renames**:
   - `camera_name` → `device_name`
   - `movie_codec` → `movie_container`
5. **Parameters removed**:
   - `stream_localhost`
   - `stream_auth_method`
   - `stream_authentication`
   - `auto_brightness` (UI toggle also removed from MotionEye due to poor functionality)
   - `setup_mode`

## Files Modified

### 1. `motioneye/motionctl.py` (lines 375-380)

Added `is_motion_50()` function to detect Motion version 5.0 or later:

```python
def is_motion_50():
    """Check if Motion version is 5.0 or later."""
    binary, version = find_motion()
    if not binary:
        return False
    return update.compare_versions(version, '5.0') >= 0
```

### 2. `motioneye/config/adaptation.py` (lines 153-238)

Added Motion 4.4→5.0 conversion functions:

- `webcontrol_interface_to_50()` - converts integer → string webcontrol_interface
- `camera_name_to_device_name()` - renames camera_name → device_name
- `movie_codec_to_container()` - renames movie_codec → movie_container

Added mapping dictionaries:

- `_MOTION_44_TO_50_OPTIONS_MAPPING` - forward mapping with `None` values for removed options
- `_MOTION_50_TO_44_OPTIONS_MAPPING` - reverse mapping for reading Motion 5.0 configs

Updated `adapt_config_directives()` to handle `None` mappings (removes keys from config).

### 3. `motioneye/config/defaults.py` (lines 47-54, 91-131)

Conditional defaults based on Motion version:

- `webcontrol_interface`: string `'default'` for 5.0, integer `1` for 4.x
- Skip setting deprecated options (`setup_mode`, `stream_port`, `stream_localhost`, `stream_auth_method`) for Motion 5.0
- Note: `auto_brightness` removed entirely from MotionEye (UI and backend)

### 4. `motioneye/mjpgclient.py` (lines 45-52, 167-191, 234-262, 319-368)

Major refactoring for Motion 5.0 stream URL support:

- Added `stream_path` parameter to `MjpgClient.__init__()`
- Updated `_on_connect()` to use configurable `_stream_path` in HTTP requests
- Updated authentication handlers to use `_stream_path` for digest auth
- Refactored `get_jpg()` to determine port and stream path based on Motion version:
  - **Motion 5.0**: Uses `webcontrol_port` with `/{motion_camera_id}/stream` path
  - **Motion 4.x**: Uses per-camera `stream_port` with `/` path

### 5. `motioneye/config/storage.py` (lines 31-39, 126-129, 156-165, 370-373, 413-422)

Updated configuration I/O:

- Added imports for Motion 5.0 mappings
- `get_main()` and `get_camera()`: Apply Motion 5.0→4.4 adaptation when reading configs
- `set_main()` and `set_camera()`: Apply Motion 4.4→5.0 adaptation when writing configs

### 6. `motioneye/config/camera/constants.py` (lines 88-102)

Added constant sets for documentation:

```python
MOTION_50_PARAMS = {
    'device_name',      # Renamed from camera_name
    'movie_container',  # Renamed from movie_codec
}

MOTION_50_REMOVED_PARAMS = {
    'stream_port',
    'stream_localhost',
    'stream_auth_method',
    'stream_authentication',
    'auto_brightness',  # Also removed from MotionEye UI/backend
    'setup_mode',
}
```

## Testing

### Existing Tests
All 14 existing pytest tests pass.

### Custom Verification Tests
The following were verified:

1. **Version detection**: `is_motion_50()` correctly identifies Motion 5.0+ versions
2. **webcontrol_interface conversions**: Bidirectional integer↔string conversion
3. **Parameter name conversions**: camera_name↔device_name, movie_codec↔movie_container
4. **Config adaptation**: Deprecated options correctly removed during adaptation
5. **MjpgClient**: stream_path parameter works correctly

## Backward Compatibility

All changes are gated by `is_motion_50()` checks, ensuring:

- Motion 4.x installations continue to work unchanged
- Stream ports per camera still used for Motion 4.x
- Integer webcontrol_interface values still used for Motion 4.x
- Existing camera_name and movie_codec parameters preserved for Motion 4.x

## Deployment Testing Checklist

For Pi 5 testing with Motion 5.0:

- [ ] MotionEye web UI loads at `http://pi5-motioneye:8765`
- [ ] Camera is detected and listed
- [ ] Live stream displays in web UI
- [ ] No "Unknown config option" errors in motion.log
- [ ] Snapshot button works
- [ ] Motion detection toggle works
- [ ] Recording creates valid video files

## Related Documentation

- Design doc: `/docs/designs/config-refactor-design.md`
- Breaking changes: `/docs/Update-Motion-MotionEye.md`
- Integration guide: `/docs/MotionEye-Integration-Guide.md`
- Handoff prompt: `/docs/handoff-prompts/motion-5.0-compatibility.md`
