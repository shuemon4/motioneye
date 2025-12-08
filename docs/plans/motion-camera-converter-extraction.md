# Motion Camera Converter Extraction Plan

## Overview

Extract `motion_camera_ui_to_dict` (~564 lines) and `motion_camera_dict_to_ui` (~526 lines) from `motioneye/config.py` to `motioneye/config/camera/converters.py`.

These functions are core to MotionEye's operation - they translate between the web UI configuration format and Motion's configuration file format.

**Status**: Ready for implementation
**Risk Level**: Medium
**Estimated Lines Moved**: ~1,100 lines
**Target `config.py` size after**: ~800 lines (down from ~1,350)

---

## 1. Current State

### 1.1 Function Locations

| Function | Location | Lines |
|----------|----------|-------|
| `motion_camera_ui_to_dict` | `config.py:229-792` | 564 |
| `motion_camera_dict_to_ui` | `config.py:795-1320` | 526 |
| `_USED_MOTION_OPTIONS` | `config.py:114-181` | 68 |

### 1.2 Function Responsibilities

**`motion_camera_ui_to_dict`**:
- Converts web UI form data → Motion configuration dictionary
- Creates target directories on filesystem
- Schedules async upload service updates via `tasks.add()`
- Builds event command strings (email, telegram, webhook, custom commands)
- Handles camera-type-specific settings (resolution, video controls, autofocus)
- Validates input using regex patterns with localized error messages

**`motion_camera_dict_to_ui`**:
- Converts Motion configuration dictionary → web UI format
- Queries hardware for available resolutions and video controls
- Calculates disk usage
- Parses event command strings back to UI fields
- Retrieves action commands for the camera

### 1.3 Dependencies

| Category | `ui_to_dict` | `dict_to_ui` |
|----------|--------------|--------------|
| **Config Storage** | `get_main()` | - |
| **Config Commands** | - | `get_action_commands()` |
| **Settings** | `settings.SMB_SHARES` | `settings.SMB_SHARES` |
| **Tasks** | `tasks.add()` | - |
| **Upload Services** | `uploadservices.update` | - |
| **Utils** | `is_v4l2_camera`, `is_libcamera_device`, `is_mmal_camera`, `build_editable_mask_file`, `split_semicolon` | `is_net_camera`, `is_libcamera_device`, `is_mmal_camera`, `parse_editable_mask_file`, `split_semicolon`, `get_disk_usage`, `COMMON_RESOLUTIONS` |
| **Controls** | `smbctl.make_mount_point`, `diskctl.list_mounted_partitions` | `smbctl.make_mount_point`, `diskctl.list_mounted_partitions`, `diskctl.list_mounted_disks`, `v4l2ctl.list_resolutions`, `v4l2ctl.list_ctrls` |
| **Motion Control** | - | `motionctl.resolution_is_valid` |
| **MEyeCtl** | `meyectl.find_command()` | - |
| **Localization** | `_()` (gettext) | - |

### 1.4 Side Effects (Critical)

1. **Filesystem creation** (line 474):
   ```python
   os.makedirs(data['target_dir'])
   ```

2. **Async task scheduling** (lines 494-501):
   ```python
   tasks.add(0, uploadservices.update, ...)
   ```

3. **Mask file creation** (lines 438, 589):
   ```python
   utils.build_editable_mask_file(...)
   ```

### 1.5 Current Callers

| File | Function | Usage |
|------|----------|-------|
| `handlers/config.py:111` | `get_config` | `motion_camera_dict_to_ui(local_config)` |
| `handlers/config.py:163` | `set_config` | `motion_camera_ui_to_dict(ui_config, local_config)` |
| `handlers/config.py:258-261` | `set_main_config` | Both functions (round-trip for stream auth update) |
| `handlers/config.py:514` | `list_cameras` | `motion_camera_dict_to_ui(local_config)` |
| `handlers/config.py:574` | `get_camera_config` | `motion_camera_dict_to_ui(camera_config)` |
| `handlers/picture.py:230` | `get_picture` | `motion_camera_ui_to_dict(resp.remote_ui_config)` |
| `config/camera/crud.py:147-148` | `add_camera` | Both functions (passed as injected dependencies) |
| `config.py:203-204` | `add_camera` wrapper | Both functions (as arguments to `_add_camera_impl`) |

---

## 2. Architecture

### 2.1 Strategy: Dependency Injection

Move functions to `converters.py` with explicit dependency injection:

```python
def motion_camera_ui_to_dict(
    ui: Dict[str, Any],
    prev_config: Optional[Dict[str, Any]] = None,
    *,
    get_main_func: Callable[[], Dict[str, Any]],
    task_scheduler: Optional[Callable[..., None]] = None,
    translate: Callable[[str], str] = lambda x: x,
) -> Dict[str, Any]:
    ...

def motion_camera_dict_to_ui(
    data: Dict[str, Any],
    *,
    get_action_commands_func: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    ...
```

### 2.2 File Structure

```
motioneye/config/
├── __init__.py
├── camera/
│   ├── __init__.py
│   ├── converters.py      # ← Expanded with motion camera converters
│   ├── crud.py            # Camera add/remove operations
│   └── constants.py       # ← NEW: Shared constants
```

### 2.3 Backward Compatibility

Thin wrappers in `config.py` preserve the public API:

```python
from motioneye.config.camera.converters import (
    motion_camera_ui_to_dict as _motion_camera_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_camera_dict_to_ui_impl,
)

def motion_camera_ui_to_dict(ui, prev_config=None):
    """Wrapper that injects dependencies."""
    return _motion_camera_ui_to_dict_impl(
        ui, prev_config,
        get_main_func=get_main,
        task_scheduler=lambda delay, func, **kw: tasks.add(delay, func, **kw),
        translate=_,
    )

def motion_camera_dict_to_ui(data):
    """Wrapper that injects dependencies."""
    return _motion_camera_dict_to_ui_impl(
        data,
        get_action_commands_func=get_action_commands,
    )
```

---

## 3. Implementation Steps

### Phase 1: Preparation (Low Risk)

#### Step 1.1: Create `constants.py`

Create `motioneye/config/camera/constants.py`:

```python
"""Shared constants for camera configuration converters."""

USED_MOTION_OPTIONS = {
    'auto_brightness',
    'despeckle_filter',
    # ... all 67 options from config.py:114-181
}
```

#### Step 1.2: Update `converters.py` imports

Add import from constants:
```python
from .constants import USED_MOTION_OPTIONS
```

### Phase 2: Function Extraction (Medium Risk)

#### Step 2.1: Extract `motion_camera_ui_to_dict`

1. Copy function to `converters.py`
2. Add parameters: `get_main_func`, `task_scheduler`, `translate`
3. Replace:
   - `get_main()` → `get_main_func()`
   - `_('...')` → `translate('...')`
   - `tasks.add(...)` → `if task_scheduler: task_scheduler(...)`
4. Add required imports at module level

#### Step 2.2: Extract `motion_camera_dict_to_ui`

1. Copy function to `converters.py`
2. Add parameter: `get_action_commands_func`
3. Replace: `get_action_commands(data)` → `get_action_commands_func(data)`
4. Add required imports at module level

#### Step 2.3: Create wrappers in `config.py`

Replace function bodies with wrapper implementations that inject dependencies.

### Phase 3: Validation

#### Step 3.1: Syntax validation
```bash
python -m py_compile motioneye/config/camera/converters.py
python -m py_compile motioneye/config/camera/constants.py
python -m py_compile motioneye/config.py
```

#### Step 3.2: Import validation
```python
from motioneye import config
assert hasattr(config, 'motion_camera_ui_to_dict')
assert hasattr(config, 'motion_camera_dict_to_ui')
```

#### Step 3.3: Functional testing (see Testing section)

### Phase 4: Cleanup

#### Step 4.1: Remove old code from `config.py`
- Remove `_USED_MOTION_OPTIONS` (moved to constants.py)
- Remove original function bodies (replaced with wrappers)

#### Step 4.2: Update module docstring
Update `config.py` docstring to reflect extraction.

---

## 4. Testing

### 4.1 Available Test Environment

- **Hardware**: Raspberry Pi 5 + Camera Module 3 (libcamera)
- **Access**: SSH to Pi 5
- **Limitation**: Only libcamera can be tested directly; V4L2, MMAL, and netcam must be validated via code review and syntax checks

### 4.2 Syntax Validation (All Platforms)

```bash
# Run from project root
python -m py_compile motioneye/config/camera/constants.py
python -m py_compile motioneye/config/camera/converters.py
python -m py_compile motioneye/config.py
python -m py_compile motioneye/handlers/config.py
```

### 4.3 Import Validation (All Platforms)

```python
# test_imports.py
from motioneye import config
from motioneye.config.camera import converters
from motioneye.config.camera.constants import USED_MOTION_OPTIONS

# Verify public API
assert callable(config.motion_camera_ui_to_dict)
assert callable(config.motion_camera_dict_to_ui)
assert callable(converters.motion_camera_ui_to_dict)
assert callable(converters.motion_camera_dict_to_ui)
assert len(USED_MOTION_OPTIONS) > 60

print("All imports validated successfully")
```

### 4.4 Pi 5 Functional Testing (SSH)

**Pre-requisites**:
1. MotionEye running on Pi 5
2. Camera Module 3 connected and working
3. SSH access to Pi 5

**Test Procedure**:

1. **Start MotionEye** (if not running):
   ```bash
   sudo systemctl restart motioneye
   ```

2. **View camera config** (tests `motion_camera_dict_to_ui`):
   - Open web UI: `http://<pi-ip>:8765`
   - Click on camera to view settings
   - Verify all settings display correctly:
     - Device name, enabled status
     - Resolution dropdown populated
     - Streaming settings visible
     - Motion detection settings visible
     - Working schedule settings visible

3. **Modify and save camera config** (tests `motion_camera_ui_to_dict`):
   - Change camera name
   - Toggle motion detection on/off
   - Modify text overlay settings
   - Click Apply
   - Verify settings saved (refresh page, check values persist)

4. **Test libcamera-specific features**:
   - Verify resolution list is correct
   - If Camera v3 (imx708): test autofocus mode changes
   - Verify buffer count setting

5. **Test notifications** (if configured):
   - Enable email/telegram/webhook notification
   - Save config
   - Verify event command strings generated correctly in motion config

6. **Test storage settings**:
   - Change root directory
   - Verify directory created on filesystem
   - Check motion.conf has correct `target_dir`

7. **Test round-trip integrity**:
   - Note all current settings
   - Save config (no changes)
   - Refresh page
   - Verify all settings unchanged

### 4.5 Code Review Validation (For Untestable Camera Types)

For V4L2, MMAL, and netcam paths that cannot be directly tested:

1. **Verify conditional branches preserved**:
   - `if utils.is_v4l2_camera(prev_config):` path unchanged
   - `elif utils.is_mmal_camera(prev_config):` path unchanged
   - `else:  # netcam` path unchanged

2. **Verify hardware query calls unchanged**:
   - `v4l2ctl.list_resolutions()` call preserved
   - `v4l2ctl.list_ctrls()` call preserved

3. **Verify RTSP/RTMP netcam handling**:
   - Resolution parsing for RTSP cameras
   - Width/height defaults for MJPEG netcams

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import cycle | Medium | High | Lazy imports for tasks/uploadservices |
| `_()` translation unavailable | Low | High | Inject with fallback identity function |
| Side effects not triggered | Medium | High | Explicit callback injection, functional tests |
| V4L2/MMAL/netcam regression | Low | High | Code review, preserve all conditional branches |
| Performance regression | Low | Low | No changes to hot paths |

---

## 6. Rollback Plan

If issues discovered after deployment:

1. **Immediate rollback**: `git revert <commit-hash>`
2. **No data migration needed**: Configuration files unchanged
3. **Partial rollback**: Can revert individual steps if needed

---

## 7. Success Criteria

- [ ] All syntax checks pass
- [ ] All import validations pass
- [ ] Pi 5 + Camera v3 functional tests pass
- [ ] `config.py` reduced to ~800 lines
- [ ] `converters.py` contains both motion camera functions
- [ ] Public API unchanged (no caller modifications needed)
- [ ] No new warnings in server logs
