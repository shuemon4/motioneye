# Plan: Full Refactor of motioneye/config.py into Modular Structure

## Summary

The `config.py` file is 2,575 lines with 39 functions and 7 global caches. It handles motion configuration management for different camera types (V4L2, libcamera, MMAL, netcam, MJPEG). The file CAN and SHOULD be split for maintainability.

**Target Environment**: Raspberry Pi 5 + RaspberryPi OS Bookworm + Motion + MotionEye
**Scope**: Full refactoring (40-60 hours estimated)
**Testing**: No existing tests for config.py - tests will be created during refactoring

---

## Impact Analysis

### Files That Import config.py (20 files)
- `meyectl.py`, `monitor.py`, `mediafiles.py`, `motionctl.py`
- `mjpgclient.py`, `sendmail.py`, `sendtelegram.py`
- `server.py`, `wsswitch.py`
- `handlers/`: action.py, base.py, main.py, movie.py, movie_playback.py, relay_event.py
- `controls/`: tzctl.py, smbctl.py, wifictl.py

**Backward compatibility wrapper required** to avoid touching all 20 files initially.

---

## Problem Analysis

### Current Issues
- Monolithic file (2,575 lines) makes navigation difficult
- Two massive functions: `motion_camera_ui_to_dict` (565 lines) and `motion_camera_dict_to_ui` (525 lines)
- Global cache state scattered throughout module (7 globals)
- Tight coupling between I/O, conversion, and defaults
- No existing tests - difficult to verify refactoring correctness

### Key Insight
The code has **clear functional domains** despite being in one file. No circular dependencies exist, making refactoring safe.

---

## Recommended Module Structure

```
motioneye/
├── config/
│   ├── __init__.py          # Public API (re-exports)
│   ├── adaptation.py        # Motion version compatibility (4.1→4.3→4.4)
│   ├── serialization.py     # Config file format translation
│   ├── defaults.py          # Default configuration values
│   ├── storage.py           # I/O operations & caching
│   ├── extensions.py        # Plugin system
│   ├── commands.py          # Action/monitor command handling
│   ├── backup.py            # Backup/restore operations
│   └── camera/
│       ├── __init__.py
│       ├── crud.py          # Camera add/remove operations
│       ├── conversions.py   # UI ↔ config dispatcher
│       └── types/           # Per-camera-type converters
│           ├── __init__.py
│           ├── v4l2.py
│           ├── libcamera.py # Pi 5 cameras
│           ├── mmal.py      # Pi 4 and earlier
│           ├── netcam.py    # RTSP/RTMP/HTTP
│           └── mjpeg.py     # Simple MJPEG
└── config.py                # Legacy wrapper for compatibility
```

---

## Module Contents Summary

| Module | Lines | Key Functions | Independence |
|--------|-------|---------------|--------------|
| `adaptation.py` | ~130 | `adapt_config_directives`, version mappings | HIGH - Pure functions |
| `serialization.py` | ~170 | `_conf_to_dict`, `_dict_to_conf` | HIGH - Pure functions |
| `defaults.py` | ~150 | `_set_default_*` functions | MEDIUM |
| `storage.py` | ~350 | `get/set_main`, `get/set_camera`, caches | LOW - Core |
| `extensions.py` | ~155 | `additional_section/config`, hooks | MEDIUM |
| `commands.py` | ~35 | `get_action_commands`, `get_monitor_command` | MEDIUM |
| `backup.py` | ~80 | `backup`, `restore`, `invalidate` | MEDIUM |
| `camera/crud.py` | ~140 | `add_camera`, `rem_camera` | LOW - Orchestrates |
| `camera/conversions.py` | ~1200 | UI↔config translation | LOW - Split further |

---

## Implementation Phases

### Phase 1: Low-Risk Extractions (Recommended Start)

Extract these pure-function modules with no external dependencies:

1. **`config/adaptation.py`** (Lines 138-265)
   - All `_MOTION_*_OPTIONS_MAPPING` dictionaries
   - `adapt_config_directives` function
   - Version conversion helper functions

2. **`config/serialization.py`** (Lines 2131-2303)
   - `_value_to_python`, `_python_to_value`
   - `_conf_to_dict`, `_dict_to_conf`

3. **`config/defaults.py`** (Lines 2306-2456)
   - `_set_default_motion`
   - `_set_default_motion_camera`
   - `_set_default_simple_mjpeg_camera`

**Risk**: Minimal - These are pure functions with no shared state

### Phase 2: Support Modules

4. **`config/commands.py`** (Lines 2002-2035)
5. **`config/extensions.py`** (Lines 267-272, 2459-2575)
6. **`config/backup.py`** (Lines 2038-2115)

### Phase 3: Core Refactoring

7. **`config/storage.py`** - Extract I/O with cache management
8. **`config/camera/crud.py`** - Extract CRUD operations

### Phase 4: Conversion Decomposition (Largest Effort)

9. Split `motion_camera_ui_to_dict` (565 lines) by camera type:
   - Each camera type becomes ~100-150 lines
   - Use strategy pattern or type-specific modules

10. Split `motion_camera_dict_to_ui` (525 lines) similarly

---

## Backward Compatibility Strategy

Keep `config.py` as a thin re-export wrapper:

```python
# motioneye/config.py (after refactoring)
"""Backward compatibility wrapper for config module."""
from motioneye.config import (
    get_main, set_main,
    get_camera, set_camera,
    get_camera_ids,
    add_camera, rem_camera,
    # ... all public functions
)
```

---

## Critical Files to Modify (After Extraction)

Files that import from `config.py`:
- `motioneye/handlers/config.py`
- `motioneye/handlers/main.py`
- `motioneye/motionctl.py`
- `motioneye/server.py`
- Various control modules

---

## Effort Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1 (Pure Functions) | 4-6 hours | Low |
| Phase 2 (Support Modules) | 4-6 hours | Low |
| Phase 3 (Core Refactoring) | 8-12 hours | Medium |
| Phase 4 (Conversions) | 16-24 hours | High |
| Testing & Validation | 8-12 hours | - |

**Total**: 40-60 hours for complete refactoring

---

## Quick Win Option

If full refactoring is too ambitious, extract only the cleanest modules:

1. `adaptation.py` - Zero dependencies
2. `serialization.py` - Zero dependencies
3. `defaults.py` - Minimal dependencies

This would reduce `config.py` by ~450 lines (17%) with minimal risk and immediate maintainability benefit.

---

## Detailed Implementation Steps

### Phase 1: Foundation & Pure Functions (Week 1)

#### Step 1.1: Create package structure
```bash
mkdir -p motioneye/config/camera/types
touch motioneye/config/__init__.py
touch motioneye/config/camera/__init__.py
touch motioneye/config/camera/types/__init__.py
```

#### Step 1.2: Extract adaptation.py (Lines 138-265)
- Move `_MOTION_41_TO_43_OPTIONS_MAPPING`
- Move `_MOTION_43_TO_41_OPTIONS_MAPPING`
- Move `_MOTION_43_TO_44_OPTIONS_MAPPING`
- Move `_MOTION_44_TO_43_OPTIONS_MAPPING`
- Move helper functions: `text_double`, `webcontrol_html_output`, `text_scale`, `webcontrol_interface`
- Move netcam param functions: `netcam_keepalive_params`, `netcam_tolerant_check_params`, `netcam_use_tcp_params`, `netcam_params`
- Move `adapt_config_directives`
- Create tests: `tests/test_config/test_adaptation.py`

#### Step 1.3: Extract serialization.py (Lines 2131-2303)
- Move `_value_to_python`, `_python_to_value`
- Move `_conf_to_dict`, `_dict_to_conf`
- Create tests: `tests/test_config/test_serialization.py`

#### Step 1.4: Extract defaults.py (Lines 2306-2456)
- Move `_set_default_motion`
- Move `_set_default_motion_camera`
- Move `_set_default_simple_mjpeg_camera`
- Create tests: `tests/test_config/test_defaults.py`

### Phase 2: Support Modules (Week 2)

#### Step 2.1: Extract commands.py (Lines 2002-2035)
- Move `_ACTIONS` constant
- Move `_monitor_command_cache` global
- Move `get_action_commands`, `get_monitor_command`, `invalidate_monitor_commands`
- Create tests

#### Step 2.2: Extract extensions.py (Lines 267-272, 2459-2575)
- Move globals: `_additional_section_funcs`, `_additional_config_funcs`, `_additional_structure_cache`
- Move decorators: `additional_section`, `additional_config`
- Move `get_additional_structure`, `_get_additional_config`, `_set_additional_config`
- Create tests

#### Step 2.3: Extract backup.py (Lines 2038-2115)
- Move `backup`, `restore`
- Create tests

### Phase 3: Core Storage (Week 3)

#### Step 3.1: Extract storage.py (Lines 276-556)
- Move globals: `_main_config_cache`, `_camera_config_cache`, `_camera_ids_cache`
- Move `get_main`, `set_main`
- Move `get_camera`, `set_camera`, `get_camera_ids`
- Move `get_enabled_local_motion_cameras`, `get_network_shares`
- Move `invalidate`
- Import from adaptation, serialization, defaults, extensions
- Create comprehensive tests

### Phase 4: Camera CRUD (Week 4)

#### Step 4.1: Extract camera/crud.py (Lines 634-770)
- Move `add_camera`, `rem_camera`
- Import from storage, conversions
- Create tests

### Phase 5: Conversion Decomposition (Weeks 5-6)

#### Step 5.1: Create camera type converters
**`camera/types/base.py`** - Abstract base class:
```python
from abc import ABC, abstractmethod

class CameraConverter(ABC):
    @abstractmethod
    def ui_to_dict(self, ui: dict, prev_config: dict) -> dict:
        """Convert UI config to motion.conf format."""
        pass

    @abstractmethod
    def dict_to_ui(self, data: dict) -> dict:
        """Convert motion.conf format to UI config."""
        pass
```

#### Step 5.2: Extract V4L2 converter (~200 lines)
- Move V4L2-specific logic from `motion_camera_ui_to_dict` (lines 992-1024)
- Move V4L2-specific logic from `motion_camera_dict_to_ui` (lines 1602-1645)
- Create `camera/types/v4l2.py`

#### Step 5.3: Extract libcamera converter (~150 lines) - **Pi 5 Priority**
- Move libcamera logic from `motion_camera_ui_to_dict` (lines 995-1049)
- Move libcamera logic from `motion_camera_dict_to_ui` (lines 1568-1588)
- Create `camera/types/libcamera.py`
- Include autofocus handling for Camera v3

#### Step 5.4: Extract MMAL converter (~100 lines)
- Move MMAL logic
- Create `camera/types/mmal.py`

#### Step 5.5: Extract netcam converter (~150 lines)
- Move netcam/RTSP/RTMP logic
- Create `camera/types/netcam.py`

#### Step 5.6: Extract MJPEG converter (~50 lines)
- Move simple MJPEG logic
- Create `camera/types/mjpeg.py`

#### Step 5.7: Create dispatcher in camera/conversions.py
```python
from .types import v4l2, libcamera, mmal, netcam, mjpeg

def _get_converter(config):
    """Return appropriate converter for camera type."""
    if utils.is_v4l2_camera(config):
        return v4l2.V4L2Converter()
    elif utils.is_libcamera_device(config):
        return libcamera.LibcameraConverter()
    # ... etc

def motion_camera_ui_to_dict(ui, prev_config=None):
    """Main dispatcher to type-specific converters."""
    converter = _get_converter(prev_config)
    return converter.ui_to_dict(ui, prev_config)
```

### Phase 6: Integration & Cleanup (Week 7)

#### Step 6.1: Create public API in config/__init__.py
```python
"""Config module - backward compatible public API."""
from .storage import (
    get_main, set_main,
    get_camera, set_camera, get_camera_ids,
    get_enabled_local_motion_cameras, get_network_shares,
    invalidate
)
from .camera.crud import add_camera, rem_camera
from .camera.conversions import (
    main_ui_to_dict, main_dict_to_ui,
    motion_camera_ui_to_dict, motion_camera_dict_to_ui,
    simple_mjpeg_camera_ui_to_dict, simple_mjpeg_camera_dict_to_ui
)
from .commands import (
    get_action_commands, get_monitor_command, invalidate_monitor_commands
)
from .backup import backup, restore
from .extensions import (
    additional_section, additional_config, get_additional_structure
)
from .adaptation import adapt_config_directives
```

#### Step 6.2: Update original config.py as wrapper
```python
"""Backward compatibility wrapper - imports from config package."""
from motioneye.config import *  # Re-export all public API
```

#### Step 6.3: Run full test suite and manual testing on Pi 5

---

## Test Strategy

Create `tests/test_config/` directory with:
- `test_adaptation.py` - Version mapping tests
- `test_serialization.py` - Config file parsing tests
- `test_defaults.py` - Default value tests
- `test_storage.py` - Cache and I/O tests (use mocking)
- `test_commands.py` - Action command tests
- `test_camera/test_v4l2.py` - V4L2 conversion tests
- `test_camera/test_libcamera.py` - Pi 5 libcamera tests
- `test_camera/test_netcam.py` - Network camera tests

---

## Risk Mitigation

1. **Incremental commits**: Each extraction is a separate commit
2. **Backward compatibility**: Original `config.py` becomes re-export wrapper
3. **Testing at each phase**: Tests written before/during each extraction
4. **Manual validation**: Test on actual Pi 5 after each phase
5. **Rollback plan**: Git tags at each phase boundary

---

## Success Criteria

- [ ] All 9 modules extracted and working
- [ ] Original `config.py` is < 50 lines (re-export wrapper)
- [ ] All 20 importing files work without modification
- [ ] Test coverage > 80% for new modules
- [ ] Pi 5 libcamera functionality verified
- [ ] No regression in camera add/remove/configure operations

---

## Implementation Progress

### Completed Work (2024-12-07)

#### Phase 1: Pure Function Modules - COMPLETED
| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| `config/__init__.py` | 150 | ✅ | Package with backward-compatible re-exports |
| `config/adaptation.py` | 175 | ✅ | Motion version mappings, `adapt_config_directives` |
| `config/serialization.py` | 242 | ✅ | `_conf_to_dict`, `_dict_to_conf`, value converters |
| `config/defaults.py` | 204 | ✅ | `_set_default_motion`, `_set_default_motion_camera`, `_set_default_simple_mjpeg_camera` |

#### Phase 2: Support Modules - COMPLETED
| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| `config/commands.py` | 104 | ✅ | `get_action_commands`, `get_monitor_command`, `invalidate_monitor_commands` |
| `config/extensions.py` | 192 | ✅ | `additional_section`, `additional_config`, `get_additional_structure` |
| `config/backup.py` | 126 | ✅ | `backup`, `restore` functions |

#### Phase 3: Core Storage - COMPLETED
| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| `config/storage.py` | 370 | ✅ | `get/set_main`, `get/set_camera`, cache management, `invalidate` |

#### Phase 4: Camera CRUD - COMPLETED
| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| `config/camera/__init__.py` | 49 | ✅ | Camera subpackage with re-exports |
| `config/camera/crud.py` | 189 | ✅ | `add_camera`, `rem_camera` (with function injection for dependencies) |

#### Phase 5: Camera Converters - PARTIAL
| Module | Lines | Status | Notes |
|--------|-------|--------|-------|
| `config/camera/converters.py` | 112 | ✅ | `input_sanity_check`, simple MJPEG converters, validation patterns |
| `config/camera/types/__init__.py` | 17 | ✅ | Placeholder for future type-specific converters |

**Note**: The large motion camera converter functions (`motion_camera_ui_to_dict`, `motion_camera_dict_to_ui`) remain in the main `config.py` file due to their extensive dependencies on multiple modules, settings, and external services. Extracting these requires significant additional work as noted in the original plan (16-24 hours, HIGH RISK).

### Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Original `config.py` | 2,575 lines | 2,152 lines | -423 lines (16.4%) |
| New `config/` package | 0 lines | 2,128 lines | +2,128 lines |
| Total modules extracted | 0 | 11 | +11 modules |

### Files Created
```
motioneye/config/
├── __init__.py          (150 lines) - Public API re-exports
├── adaptation.py        (175 lines) - Motion version mappings
├── serialization.py     (242 lines) - Config file parsing
├── defaults.py          (204 lines) - Default values
├── extensions.py        (192 lines) - Plugin system
├── commands.py          (104 lines) - Action commands
├── backup.py            (126 lines) - Backup/restore
├── storage.py           (370 lines) - Core I/O + caching
└── camera/
    ├── __init__.py      (49 lines)  - Subpackage
    ├── crud.py          (189 lines) - Add/remove cameras
    ├── converters.py    (112 lines) - Simple converters
    └── types/
        └── __init__.py  (17 lines)  - Future converters
```

### Remaining Work

1. **Complex Camera Converters** (Phase 5 completion):
   - `motion_camera_ui_to_dict` (565 lines) - needs decomposition by camera type
   - `motion_camera_dict_to_ui` (525 lines) - needs decomposition by camera type
   - `main_ui_to_dict` and `main_dict_to_ui` (smaller, but depend on above)

2. **Testing**:
   - Create `tests/test_config/` directory with unit tests
   - Run full integration tests on Raspberry Pi 5
   - Validate all camera types work correctly

3. **Final Cleanup**:
   - Convert `config.py` to thin re-export wrapper
   - Update imports in all 20 dependent files (optional with wrapper)

### Validation

All new modules pass Python syntax validation (`py_compile`). Full runtime testing requires the Raspberry Pi 5 environment due to Linux-specific dependencies (`fcntl`, etc.).
