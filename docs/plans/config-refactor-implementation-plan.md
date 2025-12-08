# Config.py Refactoring - Implementation Plan

**Created**: 2024-12-07
**Approach**: Full Modularization
**API Pattern**: Function Injection (maintained)
**Testing**: Syntax Validation + Manual Pi Testing

---

## Executive Summary

This plan completes the refactoring of `motioneye/config.py` (2,152 lines) into a modular `config/` package. The work is divided into 4 phases with clear milestones and validation checkpoints.

**End Goal**:
- `config.py` becomes a thin wrapper (~50-100 lines) with only re-exports
- All logic lives in focused, maintainable modules under `config/`
- Full backward compatibility maintained for all 20 importing files

---

## Phase 1: Duplicate Removal (Low Risk)

**Objective**: Remove all duplicated code from `config.py` that already exists in extracted modules.

**Estimated Lines Removed**: ~1,400 lines
**Target config.py Size After**: ~750 lines

### Step 1.1: Remove Duplicate Constants and Caches

**Files to Modify**: `config.py`

**Remove**:
```python
# Lines 57-79: _ACTIONS constant (exists in commands.py)
# Lines 81-87: All global caches (exist in respective modules)
_main_config_cache = None
_camera_config_cache = {}
_camera_ids_cache = None
_additional_section_funcs = []
_additional_config_funcs = []
_additional_structure_cache = {}
_monitor_command_cache = {}
```

**Add Import**:
```python
from motioneye.config.commands import _ACTIONS
```

**Validation**: `python -m py_compile motioneye/config.py`

### Step 1.2: Remove Duplicate Decorators

**Remove from config.py**:
```python
# Lines 164-169
def additional_section(func):
    _additional_section_funcs.append(func)

def additional_config(func):
    _additional_config_funcs.append(func)
```

**Add Import**:
```python
from motioneye.config.extensions import additional_section, additional_config
```

### Step 1.3: Remove Duplicate Storage Functions

**Remove from config.py**:
- `get_main` (lines 172-235)
- `set_main` (lines 238-285)
- `get_camera_ids` (lines 288-329)
- `get_enabled_local_motion_cameras` (lines 332-338)
- `get_network_shares` (lines 341-363)
- `get_camera` (lines 366-452)
- `set_camera` (lines 455-527)
- `invalidate` (lines 2014-2024)

**Add Imports**:
```python
from motioneye.config.storage import (
    get_main, set_main, get_camera, set_camera, get_camera_ids,
    get_enabled_local_motion_cameras, get_network_shares, invalidate,
    clear_camera_cache,
)
```

### Step 1.4: Remove Duplicate Camera CRUD Functions

**Remove from config.py**:
- `add_camera` (lines 530-635)
- `rem_camera` (lines 638-666)

**Challenge**: The `config.py` version doesn't use function injection but the `crud.py` version does.

**Solution**: Create wrapper functions in config.py that call the injected versions:

```python
from motioneye.config.camera.crud import (
    add_camera as _add_camera_impl,
    rem_camera as _rem_camera_impl,
)

def add_camera(device_details):
    """Wrapper that provides required dependencies to crud.add_camera."""
    return _add_camera_impl(
        device_details,
        get_camera_ids_func=get_camera_ids,
        get_camera_func=get_camera,
        set_camera_func=set_camera,
        motion_camera_dict_to_ui_func=motion_camera_dict_to_ui,
        motion_camera_ui_to_dict_func=motion_camera_ui_to_dict,
        simple_mjpeg_camera_dict_to_ui_func=simple_mjpeg_camera_dict_to_ui,
        simple_mjpeg_camera_ui_to_dict_func=simple_mjpeg_camera_ui_to_dict,
        clear_cache_func=clear_camera_cache,
    )

def rem_camera(camera_id):
    """Wrapper that provides required dependencies to crud.rem_camera."""
    return _rem_camera_impl(
        camera_id,
        get_main_func=get_main,
        set_main_func=set_main,
        clear_cache_func=clear_camera_cache,
    )
```

### Step 1.5: Remove Duplicate Converter Functions

**Remove from config.py**:
- `input_sanity_check` (lines 750-757)
- `simple_mjpeg_camera_ui_to_dict` (lines 1854-1872)
- `simple_mjpeg_camera_dict_to_ui` (lines 1875-1895)

**Add Imports**:
```python
from motioneye.config.camera.converters import (
    input_sanity_check,
    simple_mjpeg_camera_ui_to_dict,
)
```

**Note**: `simple_mjpeg_camera_dict_to_ui` uses function injection in the module version.
Create a wrapper:

```python
from motioneye.config.camera.converters import (
    simple_mjpeg_camera_dict_to_ui as _simple_mjpeg_camera_dict_to_ui_impl,
)

def simple_mjpeg_camera_dict_to_ui(data):
    """Wrapper that provides get_action_commands dependency."""
    return _simple_mjpeg_camera_dict_to_ui_impl(data, get_action_commands)
```

### Step 1.6: Remove Duplicate Command Functions

**Remove from config.py**:
- `get_action_commands` (lines 1898-1915)
- `get_monitor_command` (lines 1918-1927)
- `invalidate_monitor_commands` (lines 1930-1931)

**Add Imports**:
```python
from motioneye.config.commands import (
    get_action_commands, get_monitor_command, invalidate_monitor_commands,
)
```

### Step 1.7: Remove Duplicate Backup Functions

**Remove from config.py**:
- `backup` (lines 1934-1976)
- `restore` (lines 1979-2011)

**Add Imports**:
```python
from motioneye.config.backup import backup
from motioneye.config.backup import restore as _restore_impl

def restore(content):
    """Wrapper that provides invalidate dependency."""
    return _restore_impl(content, invalidate_func=invalidate)
```

### Step 1.8: Remove Duplicate Extension Functions

**Remove from config.py**:
- `get_additional_structure` (lines 2037-2088)
- `_get_additional_config` (lines 2091-2116)
- `_set_additional_config` (lines 2119-2152)

**Add Imports**:
```python
from motioneye.config.extensions import (
    get_additional_structure,
    _get_additional_config,
    _set_additional_config,
)
```

### Step 1.9: Validation Checkpoint

1. Run syntax validation:
   ```bash
   python -m py_compile motioneye/config.py
   python -m py_compile motioneye/config/__init__.py
   ```

2. Run import test:
   ```bash
   python -c "from motioneye import config; print(dir(config))"
   ```

3. Verify all 20 importing files compile:
   ```bash
   for f in motioneye/*.py motioneye/handlers/*.py motioneye/controls/*.py; do
       python -m py_compile "$f"
   done
   ```

---

## Phase 2: Main Converter Extraction (Low-Medium Risk)

**Objective**: Move `main_ui_to_dict` and `main_dict_to_ui` to `camera/converters.py`.

**Estimated Lines Moved**: ~80 lines
**Target config.py Size After**: ~650 lines

### Step 2.1: Analyze Dependencies

**main_ui_to_dict dependencies**:
- `settings.PASSWORD_HOOK`
- `subprocess.STDOUT`
- `hashlib.sha1`
- `utils.call_subprocess`

**main_dict_to_ui dependencies**:
- None (pure function)

### Step 2.2: Move Functions to camera/converters.py

Add to `config/camera/converters.py`:

```python
import hashlib
import subprocess
from motioneye import settings, utils


def main_ui_to_dict(ui):
    """
    Convert main configuration UI format to config dictionary.

    Handles admin/normal username/password conversion with SHA1 hashing.
    """
    data = {
        '@admin_username': ui['admin_username'],
        '@normal_username': ui['normal_username'],
    }

    def call_hook(u, p):
        if settings.PASSWORD_HOOK:
            env = {'MEYE_USERNAME': u, 'MEYE_PASSWORD': p}
            try:
                utils.call_subprocess(
                    settings.PASSWORD_HOOK, env=env, stderr=subprocess.STDOUT
                )
            except Exception as e:
                import logging
                logging.error(f'password hook exec failed: {e}')

    if ui.get('admin_password') is not None:
        if ui['admin_password']:
            data['@admin_password'] = hashlib.sha1(
                ui['admin_password'].encode('utf-8')
            ).hexdigest()
        else:
            data['@admin_password'] = ''
        call_hook(ui['admin_username'], ui['admin_password'])

    if ui.get('normal_password') is not None:
        data['@normal_password'] = ui['normal_password']
        call_hook(ui['normal_username'], ui['normal_password'])

    if ui.get('lang') is not None:
        data['@lang'] = ui['lang']

    # additional configs
    for name, value in list(ui.items()):
        if not name.startswith('_'):
            continue
        data['@' + name] = value

    return data


def main_dict_to_ui(data):
    """
    Convert main configuration dictionary to UI format.

    Masks passwords for security when sending to client.
    """
    ui = {
        'admin_username': data['@admin_username'],
        'normal_username': data['@normal_username'],
    }

    if data['@lang']:
        ui['lang'] = data['@lang']

    # don't transmit password (or its hash) to the client;
    # instead transmit an indication of password being set
    if data['@admin_password']:
        ui['admin_password'] = '*****'
    else:
        ui['admin_password'] = ''

    if data['@normal_password']:
        ui['normal_password'] = '*****'
    else:
        ui['normal_password'] = ''

    # additional configs
    for name, value in list(data.items()):
        if not name.startswith('@_'):
            continue
        ui[name[1:]] = value

    return ui
```

### Step 2.3: Update config.py Imports

**Remove from config.py**:
- `main_ui_to_dict` function (lines 669-714)
- `main_dict_to_ui` function (lines 717-747)

**Add Import**:
```python
from motioneye.config.camera.converters import main_ui_to_dict, main_dict_to_ui
```

### Step 2.4: Update config/__init__.py Exports

Add to `__all__` and imports:
```python
from motioneye.config.camera.converters import (
    input_sanity_check,
    simple_mjpeg_camera_ui_to_dict,
    main_ui_to_dict,
    main_dict_to_ui,
)
```

### Step 2.5: Validation Checkpoint

Same as Phase 1 Step 1.9.

---

## Phase 3: Motion Camera Converter Extraction (High Risk)

**Objective**: Extract `motion_camera_ui_to_dict` and `motion_camera_dict_to_ui` using a type-based strategy pattern.

**Estimated Lines Moved**: ~1,100 lines
**Target config.py Size After**: ~100 lines (wrapper only)

### Step 3.1: Create Base Converter Interface

Create `config/camera/types/base.py`:

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class CameraConverter(ABC):
    """Base class for camera type-specific converters."""

    @abstractmethod
    def ui_to_dict(self, ui: Dict[str, Any], prev_config: Dict[str, Any]) -> Dict[str, Any]:
        """Convert UI configuration to motion.conf format."""
        pass

    @abstractmethod
    def dict_to_ui(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert motion.conf format to UI configuration."""
        pass

    def _build_common_ui_to_dict(self, ui: Dict[str, Any], data: Dict[str, Any]) -> None:
        """Build common fields shared by all camera types."""
        # Implementation moved from motion_camera_ui_to_dict
        pass

    def _build_common_dict_to_ui(self, data: Dict[str, Any], ui: Dict[str, Any]) -> None:
        """Build common fields shared by all camera types."""
        # Implementation moved from motion_camera_dict_to_ui
        pass
```

### Step 3.2: Extract Common Code

Analyze `motion_camera_ui_to_dict` (564 lines) for code that:
1. Is common to ALL camera types
2. Is specific to V4L2 cameras
3. Is specific to libcamera cameras
4. Is specific to MMAL cameras
5. Is specific to netcam cameras

**Common code** (~400 lines):
- Device name/enabled
- Storage settings
- Text overlay
- Streaming settings
- Still images
- Movies
- Motion detection
- Working schedule
- Event handlers (email, telegram, webhook)
- Additional configs
- Extra motion options

**Type-specific code** (~160 lines):
- V4L2: `vid_control_params`, resolution from device
- libcamera: `libcam_buffer_count`, autofocus controls
- MMAL: Resolution handling
- netcam: URL handling, RTSP/RTMP detection

### Step 3.3: Create Type-Specific Converters

Create files:
- `config/camera/types/v4l2.py`
- `config/camera/types/libcamera.py`
- `config/camera/types/mmal.py`
- `config/camera/types/netcam.py`

Each implements `CameraConverter` interface.

### Step 3.4: Create Dispatcher

Update `config/camera/types/__init__.py`:

```python
from motioneye import utils
from .base import CameraConverter
from .v4l2 import V4L2Converter
from .libcamera import LibcameraConverter
from .mmal import MMALConverter
from .netcam import NetcamConverter


def get_converter(config: dict) -> CameraConverter:
    """Return appropriate converter for camera type."""
    if utils.is_v4l2_camera(config):
        return V4L2Converter()
    elif utils.is_libcamera_device(config):
        return LibcameraConverter()
    elif utils.is_mmal_camera(config):
        return MMALConverter()
    else:
        return NetcamConverter()


def motion_camera_ui_to_dict(ui, prev_config=None):
    """Main dispatcher to type-specific converters."""
    converter = get_converter(prev_config or {})
    return converter.ui_to_dict(ui, prev_config)


def motion_camera_dict_to_ui(data, get_main_func, get_action_commands_func):
    """Main dispatcher to type-specific converters."""
    converter = get_converter(data)
    return converter.dict_to_ui(data, get_main_func, get_action_commands_func)
```

### Step 3.5: Update config.py

**Remove**:
- `motion_camera_ui_to_dict` (lines 760-1323)
- `motion_camera_dict_to_ui` (lines 1326-1851)
- `_USED_MOTION_OPTIONS` (moved to types module)

**Add wrappers**:
```python
from motioneye.config.camera.types import (
    motion_camera_ui_to_dict as _motion_camera_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_camera_dict_to_ui_impl,
)

def motion_camera_ui_to_dict(ui, prev_config=None):
    """Public API maintaining backward compatibility."""
    return _motion_camera_ui_to_dict_impl(ui, prev_config)

def motion_camera_dict_to_ui(data):
    """Public API maintaining backward compatibility."""
    return _motion_camera_dict_to_ui_impl(
        data,
        get_main_func=get_main,
        get_action_commands_func=get_action_commands,
    )
```

### Step 3.6: Validation Checkpoint

1. Syntax validation for all new files
2. Import validation
3. Manual testing on Pi 5 with each camera type

---

## Phase 4: Final Cleanup (Low Risk)

**Objective**: Clean up config.py to be a minimal wrapper.

**Target config.py Size After**: ~50-100 lines

### Step 4.1: Finalize config.py Structure

Final `config.py`:

```python
# Copyright header...

"""
Backward compatibility wrapper for config module.

All functionality has been extracted to motioneye.config package.
This module re-exports the public API for backward compatibility.
"""

# Re-export all public symbols from config package
from motioneye.config import (
    # Storage
    get_main, set_main, get_camera, set_camera, get_camera_ids,
    get_enabled_local_motion_cameras, get_network_shares, invalidate,
    clear_camera_cache,

    # Converters
    main_ui_to_dict, main_dict_to_ui,
    simple_mjpeg_camera_ui_to_dict,
    input_sanity_check,

    # Adaptation
    adapt_config_directives,
    _MOTION_41_TO_43_OPTIONS_MAPPING,
    _MOTION_43_TO_41_OPTIONS_MAPPING,
    _MOTION_43_TO_44_OPTIONS_MAPPING,
    _MOTION_44_TO_43_OPTIONS_MAPPING,

    # Serialization
    _value_to_python, _python_to_value, _conf_to_dict, _dict_to_conf,

    # Defaults
    _set_default_motion, _set_default_motion_camera, _set_default_simple_mjpeg_camera,

    # Extensions
    additional_section, additional_config, get_additional_structure,
    _get_additional_config, _set_additional_config,

    # Commands
    get_action_commands, get_monitor_command, invalidate_monitor_commands,

    # Backup
    backup,
)

# Import implementation functions that need wrappers
from motioneye.config.backup import restore as _restore_impl
from motioneye.config.camera.crud import (
    add_camera as _add_camera_impl,
    rem_camera as _rem_camera_impl,
)
from motioneye.config.camera.converters import (
    simple_mjpeg_camera_dict_to_ui as _simple_mjpeg_dict_to_ui_impl,
)
from motioneye.config.camera.types import (
    motion_camera_ui_to_dict as _motion_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_dict_to_ui_impl,
)


def add_camera(device_details):
    """Add a new camera to the configuration."""
    return _add_camera_impl(
        device_details,
        get_camera_ids_func=get_camera_ids,
        get_camera_func=get_camera,
        set_camera_func=set_camera,
        motion_camera_dict_to_ui_func=motion_camera_dict_to_ui,
        motion_camera_ui_to_dict_func=motion_camera_ui_to_dict,
        simple_mjpeg_camera_dict_to_ui_func=simple_mjpeg_camera_dict_to_ui,
        simple_mjpeg_camera_ui_to_dict_func=simple_mjpeg_camera_ui_to_dict,
        clear_cache_func=clear_camera_cache,
    )


def rem_camera(camera_id):
    """Remove a camera from the configuration."""
    return _rem_camera_impl(
        camera_id,
        get_main_func=get_main,
        set_main_func=set_main,
        clear_cache_func=clear_camera_cache,
    )


def restore(content):
    """Restore configuration from backup."""
    return _restore_impl(content, invalidate_func=invalidate)


def simple_mjpeg_camera_dict_to_ui(data):
    """Convert simple MJPEG camera config to UI format."""
    return _simple_mjpeg_dict_to_ui_impl(data, get_action_commands)


def motion_camera_ui_to_dict(ui, prev_config=None):
    """Convert motion camera UI format to config dictionary."""
    return _motion_ui_to_dict_impl(ui, prev_config)


def motion_camera_dict_to_ui(data):
    """Convert motion camera config dictionary to UI format."""
    return _motion_dict_to_ui_impl(data, get_main, get_action_commands)
```

### Step 4.2: Update config/__init__.py

Ensure all public symbols are properly exported for both:
- Direct imports from `motioneye.config`
- Imports from `motioneye.config.submodule`

### Step 4.3: Final Validation

1. **Syntax validation** for all files in `config/` and `config.py`
2. **Import test** from all 20 consuming files
3. **Manual Pi 5 testing**:
   - Add V4L2 camera
   - Add libcamera (Camera Module 3)
   - Add network camera (RTSP)
   - Add simple MJPEG camera
   - Configure each camera type
   - Backup and restore
   - Check all camera operations work

---

## Final Directory Structure

```
motioneye/
├── config.py                    # Thin wrapper (~80 lines)
└── config/
    ├── __init__.py              # Package exports (~180 lines)
    ├── adaptation.py            # Motion version compatibility (~176 lines)
    ├── serialization.py         # Config file parsing (~243 lines)
    ├── defaults.py              # Default values (~205 lines)
    ├── extensions.py            # Plugin system (~210 lines)
    ├── commands.py              # Action commands (~117 lines)
    ├── backup.py                # Backup/restore (~140 lines)
    ├── storage.py               # Core I/O (~494 lines)
    └── camera/
        ├── __init__.py          # Camera subpackage (~60 lines)
        ├── crud.py              # Add/remove cameras (~206 lines)
        ├── converters.py        # Simple converters (~210 lines)
        └── types/
            ├── __init__.py      # Dispatcher (~80 lines)
            ├── base.py          # Base class (~150 lines)
            ├── v4l2.py          # V4L2 converter (~180 lines)
            ├── libcamera.py     # Libcamera converter (~150 lines)
            ├── mmal.py          # MMAL converter (~120 lines)
            └── netcam.py        # Network camera (~180 lines)
```

**Total Lines**: ~2,700 lines (across 15 files vs. 2,152 in single file)
**Average File Size**: ~180 lines (much more maintainable)

---

## Risk Mitigation

1. **Commit after each phase** - Easy rollback if issues found
2. **Syntax validation** - Run after every file change
3. **Incremental testing** - Test each camera type after Phase 3
4. **Backward compatibility** - All wrappers maintain original function signatures
5. **No behavior changes** - Pure refactoring, no logic modifications

---

## Timeline Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Duplicate Removal | 4-6 hours | Low |
| Phase 2: Main Converters | 2-3 hours | Low |
| Phase 3: Motion Converters | 12-16 hours | High |
| Phase 4: Final Cleanup | 2-3 hours | Low |
| Testing & Validation | 4-6 hours | - |
| **Total** | **24-34 hours** | - |

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Keep function injection | User preference, avoids circular imports |
| Type-based strategy pattern | Clean separation for different camera types |
| Wrappers in config.py | Maintains backward compatibility for all consumers |
| Phase-based approach | Lower risk, easy rollback points |
