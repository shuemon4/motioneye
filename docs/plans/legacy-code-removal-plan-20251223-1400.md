# Legacy Code Removal Plan

**Date**: 2025-12-23
**Author**: Claude Code
**Branch**: `feature/trixie-64bit-migration`
**Target**: Complete removal of all legacy code for 64-bit Pi OS

---

## Scope Definition

This fork targets **Raspberry Pi 4 and Pi 5 running 64-bit Raspberry Pi OS (Bookworm/Trixie)**. The following legacy support is being removed:

| Legacy Item | Reason for Removal |
|-------------|-------------------|
| MMAL camera interface | Not available on Pi 4+ with Bookworm/Trixie |
| h264_omx encoder | Not available on 64-bit OS |
| Motion < 5.0 compatibility | Motion 5.0+ required for libcamera |
| ARMv6/Pi 1/Pi Zero support | Targets Pi 4+ only |
| 32-bit architecture support | 64-bit OS only |

---

## Phase 1: Critical Bug Fix

**Priority**: HIGH
**Effort**: 15 minutes

### Task 1.1: Fix pictl.py camera_interface Default

**File**: `motioneye/controls/pictl.py`
**Line**: 92

**Current (Bug)**:
```python
'camera_interface': 'libcamera' if is_pi5 else 'mmal',
```

**Fix**:
```python
'camera_interface': 'libcamera',  # libcamera for all Pi 4+
```

**Rationale**: MMAL is not available on Pi 4 with Bookworm/Trixie. The `get_camera_interface()` function already returns `'libcamera'` correctly - this is just informational metadata that was inconsistent.

---

## Phase 2: Remove h264_omx Dead Code

**Priority**: MEDIUM
**Effort**: 30 minutes

### Task 2.1: Remove h264_omx Detection Function

**File**: `motioneye/motionctl.py`
**Lines**: 461-468

**Action**: Delete entire function

```python
# DELETE:
def has_h264_omx_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_omx' in codecs.get('h264', {}).get('encoders', set())
```

### Task 2.2: Remove h264_omx Template Parameter

**File**: `motioneye/handlers/main.py`
**Line**: 55

**Current**:
```python
has_h264_omx_support=motionctl.has_h264_omx_support(),
```

**Action**: Delete line entirely

### Task 2.3: Delete Backup Template File

**File**: `motioneye/templates/main.html.bak`

**Action**: Delete entire file

```bash
rm motioneye/templates/main.html.bak
```

---

## Phase 3: Remove Motion < 5.0 Compatibility Layer

**Priority**: MEDIUM
**Effort**: 2 hours

This is the largest phase. Motion 5.0+ is required for libcamera support, so all pre-5.0 code paths are dead code.

### Task 3.1: Remove Pre-5.0 Adaptation Mappings

**File**: `motioneye/config/adaptation.py`

**Lines to Delete**:
- Lines 47-61: `_MOTION_41_TO_43_OPTIONS_MAPPING`
- Lines 64-80: `_MOTION_43_TO_41_OPTIONS_MAPPING`
- Lines 83-132: `netcam_*` conversion functions (kept for 4.4→5.0)
- Lines 135-150: `_MOTION_43_TO_44_OPTIONS_MAPPING` and `_MOTION_44_TO_43_OPTIONS_MAPPING`

**Keep**:
- Lines 153-268: Motion 4.4→5.0 mappings (still needed for config migration)

**Simplified adaptation.py**:
```python
"""
Motion version compatibility adaptations.

Handles configuration directive mapping for Motion 5.0.
"""


def webcontrol_interface_to_50(v, data):
    """Convert integer webcontrol_interface to Motion 5.0 string."""
    mapping = {0: 'off', 1: 'default', 2: 'user'}
    return {'webcontrol_interface': mapping.get(int(v), 'default')}


def camera_name_to_device_name(v, data):
    """Rename camera_name to device_name for Motion 5.0."""
    return {'device_name': v}


# Legacy formats removed in Motion 5.0
_LEGACY_FORMAT_MAPPING = {
    'mpeg4': 'mp4',
    'msmpeg4': 'mp4',
    'swf': 'mp4',
    'flv': 'mp4',
    'ffv1': 'mkv',
    'ogg': 'mp4',
}


def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0."""
    container = _LEGACY_FORMAT_MAPPING.get(v, v)
    return {'movie_container': container}


def migrate_legacy_movie_container(v, data):
    """Migrate legacy movie_container values to Motion 5.0 compatible values."""
    return {'movie_container': _LEGACY_FORMAT_MAPPING.get(v, v)}


MOTION_50_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_to_50,
    'camera_name': camera_name_to_device_name,
    'movie_codec': movie_codec_to_container,
    'movie_container': migrate_legacy_movie_container,
    'stream_port': None,  # Removed in 5.0
    'stream_localhost': None,
    'stream_auth_method': None,
    'stream_authentication': None,
    'setup_mode': None,
}


# Motion 5.0 to internal option mappings
def webcontrol_interface_from_50(v, data):
    """Convert Motion 5.0 string webcontrol_interface to integer."""
    mapping = {'off': 0, 'default': 1, 'user': 2, 'simple': 1}
    if isinstance(v, int):
        return {'webcontrol_interface': v}
    return {'webcontrol_interface': mapping.get(str(v).lower(), 1)}


def device_name_to_camera_name(v, data):
    """Rename device_name to camera_name for internal use."""
    return {'camera_name': v}


def movie_container_to_codec(v, data):
    """Rename movie_container to movie_codec for internal use."""
    return {'movie_codec': v}


MOTION_50_FROM_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_from_50,
    'device_name': device_name_to_camera_name,
    'movie_container': movie_container_to_codec,
}


def adapt_config_directives(data, mapping):
    """
    Adapt configuration directives using the provided mapping.

    Transforms config dictionary keys/values according to the mapping rules.
    Supports both simple string mappings and callable transformers.
    If a mapping value is explicitly set to None, the config key is removed.

    Args:
        data: Configuration dictionary to transform (modified in place)
        mapping: Dictionary mapping old names to new names or transformer functions
    """
    for name in list(data.keys()):
        if name not in mapping:
            continue

        mapped = mapping[name]
        value = data.pop(name)

        if mapped is None:
            continue  # Remove the option

        if callable(mapped):
            data.update(mapped(value, data))
        else:
            data[mapped] = value
```

### Task 3.2: Remove Pre-5.0 Defaults

**File**: `motioneye/config/defaults.py`
**Lines**: 145-150

**Current**:
```python
# Motion 5.0 removed stream_port, stream_localhost, stream_auth_method
# Streams are now served via webcontrol interface
if not motionctl.is_motion_50():
    data.setdefault('stream_localhost', False)
    data.setdefault('stream_port', 9080 + camera_id)
    data.setdefault('stream_auth_method', 0)
```

**Action**: Delete entire block (Motion 5.0+ is now required)

### Task 3.3: Remove Pre-5.0 MJPG Client Path

**File**: `motioneye/mjpgclient.py`
**Lines**: 352-359

**Current**:
```python
if motionctl.is_motion_50():
    # Motion 5.0 code path
    ...
else:
    # Motion 4.x: Separate stream ports per camera
    port = camera_config['stream_port']
    if camera_config.get('stream_auth_method', 0) > 0:
        username, password = camera_config.get('stream_authentication', ':').split(':')
        auth_mode = (
            'digest' if camera_config.get('stream_auth_method') > 1 else 'basic'
        )
```

**Action**: Remove the `if/else` entirely, keep only Motion 5.0 code:

```python
# Motion 5.0: Streams via webcontrol interface
main_config = config.get_main()
port = main_config.get('webcontrol_port', settings.MOTION_CONTROL_PORT)
motion_camera_id = motionctl.camera_id_to_motion_camera_id(camera_id)
stream_path = f'/{motion_camera_id}/mjpg/stream'

# Auth is via webcontrol settings in Motion 5.0
if main_config.get('webcontrol_auth_method'):
    auth_str = main_config.get('webcontrol_authentication', ':')
    if ':' in auth_str:
        username, password = auth_str.split(':', 1)
    auth_mode = 'digest' if main_config.get('webcontrol_auth_method') == 'digest' else 'basic'
```

### Task 3.4: Remove is_motion_50() Checks

**Files to search**: All `.py` files

```bash
grep -rn "is_motion_50()" motioneye/
```

**Action**: Remove all `if motionctl.is_motion_50():` conditionals and keep only the Motion 5.0 code path.

### Task 3.5: Consider Removing is_motion_50() Function

**File**: `motioneye/motionctl.py`
**Lines**: 453-458

**Decision**: Keep for version validation at startup, but it should always return `True`.

**Add validation** at service startup:
```python
def validate_motion_version():
    """Ensure Motion 5.0+ is installed."""
    if not is_motion_50():
        raise RuntimeError(
            "Motion 5.0+ is required for this version of MotionEye. "
            "Please upgrade Motion or use an older MotionEye version."
        )
```

---

## Phase 4: Remove MMAL Migration Code

**Priority**: LOW (but clean)
**Effort**: 45 minutes

**Decision Point**: Keep or remove MMAL migration code?

### Option A: Remove All MMAL Code (Recommended for Clean Fork)

Users with old MMAL configs must manually reconfigure cameras. This is the cleanest approach.

### Option B: Keep Migration Code (More User-Friendly)

Automatically migrate MMAL configs to libcamera on first load.

**Recommendation**: **Option A** - This is a fork targeting fresh Pi 4/5 installs. Old configs should be treated as unsupported.

### Task 4.1: Remove is_mmal_camera Function

**File**: `motioneye/utils/__init__.py`
**Lines**: 216-223

**Action**: Delete function

### Task 4.2: Remove mmalcam_name from is_local_motion_camera

**File**: `motioneye/utils/__init__.py`
**Line**: 201

**Current**:
```python
return bool(
    config.get('videodevice')
    or config.get('video_device')
    or config.get('netcam_url')
    or config.get('mmalcam_name')  # DELETE THIS
    or config.get('libcam_device')
)
```

**Action**: Remove `mmalcam_name` check

### Task 4.3: Remove MMAL Protocol Handling

**File**: `motioneye/handlers/config.py`
**Lines**: 529-536

**Current**:
```python
elif proto in ('libcamera', 'mmal'):
    # 'mmal' is accepted as alias for backwards compatibility
```

**Action**: Change to:
```python
elif proto == 'libcamera':
```

Remove all `mmal` references.

### Task 4.4: Remove MMAL from converters.py

**File**: `motioneye/config/camera/converters.py`

**Search and remove**:
```bash
grep -n "mmal" motioneye/config/camera/converters.py
```

Remove all MMAL migration logic.

### Task 4.5: Remove mmalcam_name from constants.py

**File**: `motioneye/config/camera/constants.py`
**Line**: 55

**Action**: Remove `'mmalcam_name'` from `MOTION_41_CAMERA_PARAMS`

### Task 4.6: Update main.js MMAL Case

**File**: `motioneye/static/js/main.js`
**Lines**: 2581-2582

**Current**:
```javascript
case 'mmal':
    prettyType = 'MMAL Camera (deprecated - migrated to libcamera)';
    break;
```

**Action**: Remove entire case - MMAL cameras will show as "Unknown" which is appropriate since they're unsupported.

---

## Phase 5: Remove ARMv6/32-bit Support

**Priority**: LOW
**Effort**: 30 minutes

### Task 5.1: Simplify Architecture Detection

**File**: `motioneye/rpicam_rtsp.py`
**Lines**: 63-89

**Current**:
```python
def _detect_architecture():
    machine = platform.machine().lower()
    bits = struct.calcsize('P') * 8

    if machine in ('aarch64', 'arm64', 'armv8l'):
        return 'arm64v8' if bits == 64 else 'armv7'
    elif machine.startswith('armv7') or machine.startswith('armv6') or machine == 'armhf':
        return 'armv7'
    # ...
```

**Simplified**:
```python
def _detect_architecture():
    """
    Detect system architecture for mediamtx binary download.

    Supports 64-bit ARM (Pi 4/5) and x86_64 only.
    """
    machine = platform.machine().lower()

    if machine in ('aarch64', 'arm64'):
        return 'arm64v8'
    elif machine in ('x86_64', 'amd64'):
        return 'amd64'
    else:
        raise RuntimeError(
            f"Unsupported architecture: {machine}. "
            "This version requires 64-bit ARM (Pi 4/5) or x86_64."
        )
```

### Task 5.2: Remove 32-bit from linux_init (if still present)

**File**: `motioneye/extra/linux_init`

**Verify** no ARMv6/ARMv7-specific code remains.

---

## Phase 6: Clean Up Orphaned Translations

**Priority**: LOW
**Effort**: 1 hour

### Task 6.1: Remove MMAL Translation Strings

**Files**: `motioneye/locale/*/LC_MESSAGES/motioneye.js.po`

**Search**:
```bash
grep -rn "MMAL" motioneye/locale/
```

**Action**: Remove all MMAL-related translation entries from all locale files.

### Task 6.2: Remove MMAL from JSON Translation Files

**Files**: `motioneye/static/js/motioneye.*.json`

**Search**:
```bash
grep -rn "MMAL" motioneye/static/js/
```

---

## Phase 7: Update Constants and Documentation

**Priority**: LOW
**Effort**: 30 minutes

### Task 7.1: Update MOTION_50_REMOVED_PARAMS

**File**: `motioneye/config/camera/constants.py`
**Lines**: 108-115

**Decision**: Keep for reference, but consider renaming to `LEGACY_PARAMS` since Motion 5.0 is now the minimum.

### Task 7.2: Update Module Docstrings

**Files to update**:
- `motioneye/motionctl.py` - Remove references to Motion < 5.0
- `motioneye/config/adaptation.py` - Update module docstring
- `motioneye/config/defaults.py` - Remove legacy comments
- `motioneye/controls/pictl.py` - Already updated

### Task 7.3: Update CLAUDE.md

Add note that Motion 5.0+ is required:

```markdown
## Requirements

- **Motion 5.0+** (required for libcamera support)
- **Raspberry Pi 4 or Pi 5**
- **64-bit Raspberry Pi OS** (Bookworm or Trixie)
```

---

## Implementation Order

Execute phases in this order to minimize risk:

1. **Phase 1** (Bug Fix) - Immediate fix
2. **Phase 2** (h264_omx) - Low risk, dead code
3. **Phase 4** (MMAL) - Medium risk, affects config loading
4. **Phase 3** (Motion <5.0) - High impact, many files
5. **Phase 5** (Architecture) - Low risk
6. **Phase 6** (Translations) - Cosmetic
7. **Phase 7** (Documentation) - Final polish

---

## Testing Checklist

After each phase, verify:

- [ ] `python3 -c 'import motioneye'` - No import errors
- [ ] Service starts: `sudo systemctl restart motioneye`
- [ ] Camera detection works: Check logs for "libcamera" interface
- [ ] Streaming works: Test MJPEG stream in browser
- [ ] Recording works: Trigger motion and verify video file created
- [ ] UI loads without errors

---

## Rollback Strategy

Each phase should be a separate commit for easy rollback:

```bash
# View commits
git log --oneline -10

# Rollback specific phase
git revert <commit-hash>

# Or hard reset to before changes
git reset --hard HEAD~N
```

---

## Summary

| Phase | Effort | Risk | Files Modified |
|-------|--------|------|----------------|
| 1: Bug Fix | 15 min | Low | 1 |
| 2: h264_omx | 30 min | Low | 3 |
| 3: Motion <5.0 | 2 hrs | Medium | 5-8 |
| 4: MMAL | 45 min | Medium | 6 |
| 5: Architecture | 30 min | Low | 2 |
| 6: Translations | 1 hr | None | 20+ |
| 7: Documentation | 30 min | None | 4 |

**Total Estimated Effort**: 5-6 hours

---

## Files to Delete

```bash
# Dead files
rm motioneye/templates/main.html.bak
rm motioneye/controls/__pycache__/mmalctl.cpython-*.pyc  # if present
```

---

## Post-Implementation Validation

1. **Fresh Install Test**: Install on clean Pi 5 with no prior config
2. **Camera Test**: Add libcamera camera, verify streaming and recording
3. **Performance Test**: Verify no regression in CPU usage
4. **Error Handling**: Attempt to add MMAL camera (should fail gracefully)
5. **Log Review**: Check logs for any legacy warnings or errors
