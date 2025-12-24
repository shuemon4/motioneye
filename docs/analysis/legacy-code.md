# Legacy Code Analysis Report

**Date**: 2025-12-23
**Analyst**: Claude Code
**Branch**: `feature/trixie-64bit-migration`
**Purpose**: Identify all legacy code remaining after Trixie 64-bit migration

---

## Executive Summary

Despite the implementation summary in `docs/plans/trixie-64bit-implementation-plan-20251223-1030.md` stating that legacy code was removed, **significant legacy code remains** in the codebase. This analysis documents all legacy references found, categorized by type and priority for removal.

### Key Findings

| Category | Files Affected | Status | Priority |
|----------|----------------|--------|----------|
| MMAL Camera Support | 6 files | Partial removal | Medium |
| h264_omx Encoder | 3 files | Detection code remains | Low |
| Motion <5.0 Options | 8+ files | Full compatibility layer exists | Low |
| ARMv6/ARMv7 Architecture | 2 files | Still supported | Low |
| UI/Translation Strings | 20+ locale files | Orphaned strings | Low |

---

## Category 1: MMAL Camera Support

### Status: PARTIALLY REMOVED

The `mmalctl.py` module was deleted, but MMAL detection and migration code remains in multiple files.

### Remaining MMAL Code

#### 1. `motioneye/utils/__init__.py`
**Lines 216-223**: `is_mmal_camera()` function

```python
def is_mmal_camera(config):
    """
    Check if camera config uses legacy MMAL.

    Note: MMAL is deprecated on Pi 4+ / Trixie. This function is retained
    for migration of existing configs to libcamera.
    """
    return bool(config.get('mmalcam_name'))
```

**Line 201**: `mmalcam_name` check in `is_local_motion_camera()`

**Status**:  Intentionally retained for config migration
**Action**: Keep - required for backward compatibility

---

#### 2. `motioneye/handlers/config.py`
**Lines 529-536**: Protocol handler accepts 'mmal' as alias

```python
elif proto in ('libcamera', 'mmal'):
    # 'mmal' is accepted as alias for backwards compatibility
    ...
    if utils.is_mmal_camera(data):
        configured_devices.add(data['mmalcam_name'])
```

**Status**:   Active code path
**Action**: Consider logging deprecation warning when MMAL proto is used

---

#### 3. `motioneye/config/camera/converters.py`
**Line 389-391**: MMAL config migration logic

```python
elif utils.is_mmal_camera(prev_config):
    # Migrate legacy MMAL configs to libcamera
    proto = 'libcamera'
```

**Lines 1078-1079**: MMAL device name loading for UI display

**Status**:  Intentionally retained for config migration
**Action**: Keep - handles upgrade scenario

---

#### 4. `motioneye/config/camera/constants.py`
**Line 55**: `mmalcam_name` in `MOTION_41_CAMERA_PARAMS`

**Status**:   Defines parameter recognition
**Action**: Keep for config parsing, document as deprecated

---

#### 5. `motioneye/controls/pictl.py`
**Line 92**: Default `camera_interface` set to `'mmal'` for non-Pi5

```python
'camera_interface': 'libcamera' if is_pi5 else 'mmal',
```

**Status**: L BUG - Returns 'mmal' for Pi 4 model info
**Action**: **FIX REQUIRED** - Should return 'libcamera' for all Pi 4+

---

#### 6. `motioneye/static/js/main.js`
**Lines 2581-2582**: UI still handles MMAL camera type

```javascript
case 'mmal':
    prettyType = 'MMAL Camera (deprecated - migrated to libcamera)';
    break;
```

**Status**:  Shows deprecation message
**Action**: Keep for displaying legacy configs, already marked deprecated

---

## Category 2: h264_omx Encoder Support

### Status: PARTIALLY REMOVED

The encoder options were removed from UI and defaults, but detection code remains.

### Remaining h264_omx Code

#### 1. `motioneye/motionctl.py`
**Lines 461-468**: `has_h264_omx_support()` function still exists

```python
def has_h264_omx_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False
    return 'h264_omx' in codecs.get('h264', {}).get('encoders', set())
```

**Status**:   Function exists but is never meaningfully used
**Action**: Can be removed - no code uses the return value for decisions

---

#### 2. `motioneye/handlers/main.py`
**Line 55**: Still passes OMX support flag to template

```python
has_h264_omx_support=motionctl.has_h264_omx_support(),
```

**Status**:   Value passed but template doesn't use it (options removed)
**Action**: Can be removed - template no longer has OMX options

---

#### 3. `motioneye/templates/main.html.bak` (Backup file)
**Lines 876-877, 892-893**: Old OMX options in backup

**Status**: 9 Backup file only
**Action**: Delete backup file entirely

---

## Category 3: Motion <5.0 Compatibility

### Status: FULL COMPATIBILITY LAYER EXISTS

Significant code remains to support Motion versions before 5.0.

### Motion <5.0 Code Locations

#### 1. `motioneye/config/defaults.py`
**Lines 145-150**: Legacy stream options defaults

```python
# Motion 5.0 removed stream_port, stream_localhost, stream_auth_method
# These are only set for backwards compatibility with Motion < 5.0
data.setdefault('stream_port', 9080 + camera_id)
data.setdefault('stream_localhost', False)
data.setdefault('stream_auth_method', 0)
```

**Status**:   Active code for Motion <5.0
**Action**: Keep if supporting Motion 4.x, otherwise remove

---

#### 2. `motioneye/config/camera/constants.py`
**Lines 108-115**: `MOTION_50_REMOVED_PARAMS` set

```python
MOTION_50_REMOVED_PARAMS = {
    'stream_port',
    'stream_localhost',
    'stream_auth_method',
    'stream_authentication',
    'auto_brightness',
    'setup_mode',
}
```

**Status**:  Documentation of removed options
**Action**: Keep - useful for migration and validation

---

#### 3. `motioneye/config/adaptation.py`
**Lines 204-218**: Motion 4.x to 5.0 migration mappings

```python
'stream_port': None,  # Removed in 5.0
'stream_localhost': None,
'stream_auth_method': None,
'stream_authentication': None,
```

**Lines 48-61**: Motion 4.1 to 4.3 legacy ffmpeg_* mappings

```python
'ffmpeg_video_codec': 'movie_codec',
'ffmpeg_output_movies': 'movie_output',
```

**Status**:   Active migration code
**Action**: Keep for config compatibility

---

#### 4. `motioneye/config/camera/converters.py`
**Lines 322-332, 916-929**: Streaming config conversions with Motion <5.0 fallbacks

**Status**:   Active compatibility code
**Action**: Keep for now, mark as deprecated

---

#### 5. `motioneye/mjpgclient.py`
**Lines 339-360**: Version-specific streaming handling

```python
# Motion 5.0: Uses webcontrol_port
# Motion 4.x: Uses stream_port and stream_auth_method
```

**Status**:   Active branching code
**Action**: Keep if supporting Motion 4.x

---

## Category 4: Architecture/Platform Legacy Code

### Status: PARTIAL SUPPORT FOR OLD PLATFORMS

### Remaining Legacy Architecture Code

#### 1. `motioneye/rpicam_rtsp.py`
**Lines 76-79**: ARMv6/ARMv7 architecture detection

```python
if machine in ('aarch64', 'arm64', 'armv8l'):
    return 'arm64v8' if bits == 64 else 'armv7'
elif machine.startswith('armv7') or machine.startswith('armv6') or machine == 'armhf':
    return 'armv7'
```

**Status**:   Still detects armv6 (Pi 1/Zero)
**Action**: Low priority - doesn't affect Pi 4/5

---

#### 2. `motioneye/extra/linux_init`
**Lines 29-45**: Architecture detection for package downloads

**Status**:   Supports multiple architectures
**Action**: Already updated per plan, ARMv6-specific Pi prefix removed

---

#### 3. `motioneye/controls/pictl.py`
**Line 92**: Bug - Returns 'mmal' for non-Pi5 systems

```python
'camera_interface': 'libcamera' if is_pi5 else 'mmal',
```

**Status**: L BUG - Should return 'libcamera' for Pi 4 as well
**Action**: **FIX REQUIRED**

---

## Category 5: UI and Translation Orphans

### Status: ORPHANED STRINGS REMAIN

Multiple locale files contain MMAL-related translation strings that are no longer used in the UI.

### Orphaned Translation Files

| File Pattern | Line Numbers | Content |
|--------------|--------------|---------|
| `motioneye/locale/*/LC_MESSAGES/motioneye.js.po` | 331-399 (varies) | "Local MMAL Camera" translations |
| `motioneye/static/js/motioneye.*.json` | Various | MMAL camera labels |

**Languages Affected**: en, es, de, fr, ca, cs, pl, it, nl, ja, ko, tr, zh, el, and 10+ others

**Status**:   Orphaned - not displayed but included in bundles
**Action**: Low priority - can be cleaned up in future PR

---

## Category 6: Streaming Port UI Element

### Status: POTENTIALLY OBSOLETE

#### `motioneye/templates/partials/settings/_video_streaming.html`
**Lines 28-31**: Streaming Port configuration field

```html
<tr class="settings-item" min="1024" max="65535" depends="videoStreamingEnabled" required="true">
    <td class="settings-item-label"><span class="settings-item-label" data-i18n="Streaming Port">Streaming Port</span></td>
    <td class="settings-item-value"><input type="text" class="styled streaming camera-config" id="streamingPortEntry"></td>
```

**Status**:   Motion 5.0 removed `stream_port` - UI element may be non-functional
**Action**: Investigate if this field has any effect in Motion 5.0+

---

## Recommended Actions

### High Priority (Bugs)

1. **Fix pictl.py line 92**: Change `'mmal'` default to `'libcamera'` for all Pi 4+ systems

### Medium Priority (Code Cleanup)

2. **Remove h264_omx dead code**:
   - Delete `has_h264_omx_support()` from `motionctl.py`
   - Remove `has_h264_omx_support` parameter from `handlers/main.py`
   - Delete `main.html.bak` backup file

3. **Add deprecation logging**:
   - Log warning when MMAL camera configs are detected
   - Log warning when Motion <5.0 options are used

### Low Priority (Technical Debt)

4. **Clean up orphaned translations**: Remove MMAL strings from locale files

5. **Document Motion version requirements**: Update README to specify Motion 5.0+ required

6. **Remove Motion <5.0 code paths** (if Motion 5.0+ is hard requirement):
   - `config/defaults.py` stream_* defaults
   - `mjpgclient.py` version branching
   - `config/adaptation.py` pre-5.0 mappings

---

## Summary

The Trixie 64-bit migration is **functionally complete** but not **fully cleaned up**. The system works correctly on Pi 4+ with libcamera, but legacy code paths remain that could cause confusion or maintenance burden.

### What Was Successfully Removed
-  `mmalctl.py` module (MMAL device detection)
-  `motioneye.sysv` (SysV init script)
-  h264_omx UI options from templates
-  h264_omx codec mappings from `mediafiles.py`
-  h264_omx fallback from `defaults.py`
-  ARMv6-specific Pi detection from `linux_init`

### What Remains
-   MMAL config migration code (intentional)
-   h264_omx detection functions (dead code)
-   Motion <5.0 compatibility layer (active)
-   Orphaned MMAL translation strings
- L Bug: pictl.py returns 'mmal' for Pi 4 model info

---

## Appendix: File-by-File Reference

| File | Lines | Legacy Type | Status |
|------|-------|-------------|--------|
| `controls/pictl.py` | 92 | MMAL default | L Bug |
| `controls/pictl.py` | 25, 103, 123 | MMAL comments | 9 Docs only |
| `utils/__init__.py` | 201, 216-223 | MMAL detection |  Migration |
| `handlers/config.py` | 529-536 | MMAL protocol |   Compat |
| `config/camera/converters.py` | 389-391, 1078 | MMAL migration |  Migration |
| `config/camera/constants.py` | 55 | MMAL param |   Compat |
| `static/js/main.js` | 2581-2582 | MMAL UI type |  Deprecated |
| `motionctl.py` | 461-468 | h264_omx detect |   Dead code |
| `handlers/main.py` | 55 | h264_omx flag |   Dead code |
| `config/defaults.py` | 145-150 | stream_* opts |   Motion <5.0 |
| `config/adaptation.py` | 48-61, 204-218 | Motion compat |   Migration |
| `mjpgclient.py` | 339-360 | Motion version |   Branching |
| `rpicam_rtsp.py` | 76-79 | ARMv6/v7 | 9 Fallback |
| `locale/*/motioneye.js.po` | Various | MMAL strings |   Orphaned |
