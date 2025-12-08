# Config.py Refactoring - Design Scratchpad

**Created**: 2024-12-07
**Last Updated**: 2024-12-07
**Status**: In Progress

---

## 1. Current State Analysis

### 1.1 Files and Line Counts

| Location | Lines | Status |
|----------|-------|--------|
| `config.py` (original) | 2,152 | Partially refactored |
| `config/__init__.py` | 151 | Complete |
| `config/adaptation.py` | 176 | Complete |
| `config/serialization.py` | 243 | Complete |
| `config/defaults.py` | 205 | Complete |
| `config/commands.py` | 117 | Complete |
| `config/extensions.py` | 210 | Complete |
| `config/backup.py` | 140 | Complete |
| `config/storage.py` | 494 | Complete |
| `config/camera/__init__.py` | 50 | Complete |
| `config/camera/crud.py` | 206 | Complete |
| `config/camera/converters.py` | 130 | Complete |
| `config/camera/types/__init__.py` | 17 | Placeholder |

### 1.2 Critical Issue: Code Duplication

The refactoring is **incomplete** because functions were extracted to new modules BUT the originals were NOT removed from `config.py`. This creates:

1. **Dual definitions** - Same functions exist in two places
2. **Cache conflicts** - Separate cache instances in each module
3. **Maintenance burden** - Changes must be made in multiple places
4. **Confusion** - Unclear which version is authoritative

**Evidence**: Comparing line-by-line:
- `config.py:172-235` duplicates `storage.py:61-133` (`get_main`)
- `config.py:238-285` duplicates `storage.py:136-189` (`set_main`)
- `config.py:1934-1976` duplicates `backup.py:36-88` (`backup`)
- ... and many more

### 1.3 Remaining Items in config.py

#### A. Duplicated Code (Ready to Remove)
| Component | Lines in config.py | Already in Module | Action |
|-----------|-------------------|-------------------|--------|
| `_ACTIONS` constant | 57-79 | commands.py | Remove |
| Global caches (6 total) | 81-87 | storage.py, extensions.py, commands.py | Remove |
| `additional_section` decorator | 164-165 | extensions.py | Remove |
| `additional_config` decorator | 168-169 | extensions.py | Remove |
| `get_main` | 172-235 | storage.py | Remove |
| `set_main` | 238-285 | storage.py | Remove |
| `get_camera_ids` | 288-329 | storage.py | Remove |
| `get_enabled_local_motion_cameras` | 332-338 | storage.py | Remove |
| `get_network_shares` | 341-363 | storage.py | Remove |
| `get_camera` | 366-452 | storage.py | Remove |
| `set_camera` | 455-527 | storage.py | Remove |
| `add_camera` | 530-635 | camera/crud.py | Remove |
| `rem_camera` | 638-666 | camera/crud.py | Remove |
| `input_sanity_check` | 750-757 | camera/converters.py | Remove |
| `simple_mjpeg_camera_ui_to_dict` | 1854-1872 | camera/converters.py | Remove |
| `simple_mjpeg_camera_dict_to_ui` | 1875-1895 | camera/converters.py | Remove |
| `get_action_commands` | 1898-1915 | commands.py | Remove |
| `get_monitor_command` | 1918-1927 | commands.py | Remove |
| `invalidate_monitor_commands` | 1930-1931 | commands.py | Remove |
| `backup` | 1934-1976 | backup.py | Remove |
| `restore` | 1979-2011 | backup.py | Remove |
| `invalidate` | 2014-2024 | storage.py | Remove |
| `get_additional_structure` | 2037-2088 | extensions.py | Remove |
| `_get_additional_config` | 2091-2116 | extensions.py | Remove |
| `_set_additional_config` | 2119-2152 | extensions.py | Remove |

**Estimated lines to remove**: ~1,400 lines

#### B. Code That Needs to Move (Not Yet Extracted)
| Component | Lines | Complexity | Dependencies |
|-----------|-------|------------|--------------|
| `main_ui_to_dict` | 669-714 (46 lines) | Low | settings, subprocess, hashlib |
| `main_dict_to_ui` | 717-747 (31 lines) | Low | Pure function |
| `motion_camera_ui_to_dict` | 760-1323 (564 lines) | HIGH | Many modules |
| `motion_camera_dict_to_ui` | 1326-1851 (526 lines) | HIGH | Many modules |

#### C. Should Stay in config.py
| Item | Purpose | Lines |
|------|---------|-------|
| Imports | Re-exports from new modules | 36-53 |
| `_USED_MOTION_OPTIONS` | Motion config filtering | 89-156 |
| Note comments | Documentation | Various |

---

## 2. Dependency Analysis

### 2.1 External Dependencies for motion_camera_ui_to_dict

```python
# External modules
from motioneye import meyectl, motionctl, settings, tasks, uploadservices, utils

# Control modules
from motioneye.controls import diskctl, smbctl, v4l2ctl

# Translation function (localization)
_()  # Used for error messages
```

### 2.2 External Dependencies for motion_camera_dict_to_ui

```python
# Same external modules as ui_to_dict
from motioneye import meyectl, motionctl, settings, utils

# Control modules
from motioneye.controls import diskctl, smbctl, v4l2ctl

# Internal dependencies
from motioneye.config.commands import get_action_commands
```

### 2.3 Consumers of Converter Functions

From `handlers/config.py`:
- Line 109: `config.motion_camera_dict_to_ui(local_config)`
- Line 131: `config.simple_mjpeg_camera_dict_to_ui(local_config)`
- Line 138: `config.main_dict_to_ui(config.get_main())`
- Line 161: `config.motion_camera_ui_to_dict(ui_config, local_config)`
- Line 188: `config.simple_mjpeg_camera_ui_to_dict(ui_config, local_config)`
- Line 204: `config.main_ui_to_dict(ui_config)`
- Line 256-258: Both converter functions for credential updates
- Line 512: `config.motion_camera_dict_to_ui(local_config)`
- Line 539: `config.simple_mjpeg_camera_dict_to_ui(local_config)`
- Line 558: `config.add_camera(device_details)`
- Line 572: `config.motion_camera_dict_to_ui(camera_config)`
- Line 587: `config.simple_mjpeg_camera_dict_to_ui(camera_config)`

From `config.py` itself (internal):
- Line 615-617: `motion_camera_ui_to_dict(motion_camera_dict_to_ui(...))`
- Line 623-625: `simple_mjpeg_camera_ui_to_dict(simple_mjpeg_camera_dict_to_ui(...))`

---

## 3. Design Decisions Required

### 3.1 Function Injection Pattern in camera/crud.py

**Current Issue**: `add_camera` and `rem_camera` in `crud.py` use function injection:
```python
def add_camera(device_details, get_camera_ids_func, get_camera_func, set_camera_func,
               motion_camera_dict_to_ui_func, motion_camera_ui_to_dict_func,
               simple_mjpeg_camera_dict_to_ui_func, simple_mjpeg_camera_ui_to_dict_func,
               clear_cache_func):
```

**But** the original `config.py` has simpler versions that don't use injection!

**Decision Options**:
1. **Keep injection** - Maximum flexibility but complex API
2. **Remove injection** - Simpler API but circular import risk
3. **Hybrid** - Use module-level wiring at import time

**Recommendation**: Option 3 - Wire functions at module load

### 3.2 backup.py restore() Signature

**Current Issue**: Different signatures:
- Old: `restore(content)` - calls `invalidate()` directly
- New: `restore(content, invalidate_func=None)` - requires injection

**Decision**: Keep function injection, but make optional with sensible default

### 3.3 Converter Function Extraction Strategy

**Option A: Keep in config.py (simplest)**
- Pros: No circular imports, minimal changes
- Cons: config.py remains large (~600+ lines)

**Option B: Move to camera/converters.py**
- Pros: Better organization
- Cons: Complex dependency management required

**Option C: Create camera/types/ type-specific converters**
- Pros: Best separation of concerns
- Cons: Major refactoring, high risk

**Recommendation**: Phase approach
1. First: Remove duplicates, clean up config.py
2. Then: Move main_ui_to_dict/main_dict_to_ui (low risk)
3. Later: Consider Option C when test coverage exists

---

## 4. Questions for User

1. **Immediate cleanup vs. full extraction?**
   - Option A: Remove duplicates only (minimal risk, ~1,400 lines removed)
   - Option B: Also move main converters (low risk, +80 lines moved)
   - Option C: Full Phase 5 extraction (high risk, complete modularization)

2. **Function injection pattern acceptance?**
   - Some extracted modules use function injection to avoid circular imports
   - Is this acceptable, or should we find alternative patterns?

3. **Testing requirements?**
   - What level of testing is expected before changes are considered complete?
   - Is manual testing on Pi 5 sufficient, or are automated tests required?

4. **Backward compatibility requirements?**
   - Should `config.py` remain as a thin wrapper forever?
   - Or can we eventually update all 20 importing files?

---

## 5. Implementation Notes

### 5.1 Import Order for New Modules

The `config/__init__.py` must maintain proper import order to avoid circular imports:

1. adaptation (pure functions, no deps)
2. serialization (pure functions, no deps)
3. defaults (pure functions, minimal deps)
4. extensions (depends on settings)
5. commands (depends on settings)
6. backup (depends on settings, powerctl)
7. storage (depends on 1-4)
8. camera/converters (depends on commands for dict_to_ui)

### 5.2 Cache Management

Current cache locations:
- `storage.py`: `_main_config_cache`, `_camera_config_cache`, `_camera_ids_cache`
- `extensions.py`: `_additional_structure_cache`
- `commands.py`: `_monitor_command_cache`
- `config.py`: DUPLICATES of all above (problem!)

After cleanup: Only the module-level caches should exist.

### 5.3 Translation Function (_)

The `motion_camera_ui_to_dict` function uses `_()` for localization:
```python
deviceNameFailMessage = _('Device names are only allowed...')
```

This is defined in `meyectl.py` and must be imported if converters are moved.

---

## 6. Risk Assessment

| Action | Risk | Mitigation |
|--------|------|------------|
| Remove duplicate functions | LOW | Functions already exist in modules |
| Remove duplicate caches | LOW | Cache behavior unchanged |
| Move main converters | LOW | Simple functions, few deps |
| Move motion converters | HIGH | Many dependencies, complex logic |
| Update crud.py API | MEDIUM | Need to update callers |
| Update backup.py API | MEDIUM | Need to update callers |

---

## 7. Progress Tracking

### Phase 1: Immediate Cleanup
- [ ] Remove duplicate functions from config.py
- [ ] Remove duplicate caches from config.py
- [ ] Update imports in config.py to use new modules
- [ ] Verify all 20 importing files still work

### Phase 2: Main Converters
- [ ] Move `main_ui_to_dict` to camera/converters.py
- [ ] Move `main_dict_to_ui` to camera/converters.py
- [ ] Update config/__init__.py exports

### Phase 3: Wiring Cleanup (Optional)
- [ ] Simplify crud.py function injection
- [ ] Standardize backup.py signature
- [ ] Consider camera/types/ structure

---

## 8. Open Questions & Notes

- **Q**: Is there a test suite I should be running?
- **Q**: What's the deployment process for changes?
- **Q**: Are there any performance requirements to consider?

---

## 9. Appendix: File Dependencies Graph

```
config.py
├── imports from: meyectl, motionctl, settings, tasks, uploadservices, utils
├── imports from: diskctl, pictl, smbctl, v4l2ctl, powerctl
├── imports from: config.adaptation, config.serialization, config.defaults
└── consumed by: 20 files across motioneye/

config/storage.py
├── imports from: motionctl, settings, utils
├── imports from: config.adaptation, config.serialization
├── imports from: config.defaults, config.extensions
└── consumed by: config/__init__.py

config/camera/crud.py
├── imports from: settings, utils, pictl, v4l2ctl
├── imports from: config.defaults
└── consumed by: config/camera/__init__.py

config/backup.py
├── imports from: settings, utils, powerctl
└── consumed by: config/__init__.py, config.py (duplicate)
```
