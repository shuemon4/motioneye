# HANDOFF: Config.py Refactoring Completion

**Date**: 2024-12-07
**Project**: motionEye
**Task**: Complete refactoring of `motioneye/config.py` into modular `config/` package

---

## Quick Context

The `config.py` refactoring is ~50% complete. Functions were extracted to new modules BUT originals were NOT removed, creating ~1,400 lines of duplicate code. Your job is to complete this refactoring.

**Key Documents**:
- `docs/scratchpads/config-refactor-design.md` - Analysis and design notes
- `docs/scratchpads/config-refactor-implementation-plan.md` - Detailed implementation steps
- `docs/analysis/config-refactor-review.md` - Original analysis report
- `docs/plans/refactor-config.md` - Original refactoring plan

---

## User Requirements

1. **Approach**: Full modularization
2. **API Pattern**: Keep function injection pattern (don't change to simpler API)
3. **Testing**: Syntax validation (`py_compile`) + Manual Pi 5 testing

---

## Current State

| File | Lines | Status |
|------|-------|--------|
| `config.py` | 2,152 | Has duplicates - needs cleanup |
| `config/__init__.py` | 151 | Complete |
| `config/adaptation.py` | 176 | Complete |
| `config/serialization.py` | 243 | Complete |
| `config/defaults.py` | 205 | Complete |
| `config/commands.py` | 117 | Complete |
| `config/extensions.py` | 210 | Complete |
| `config/backup.py` | 140 | Complete |
| `config/storage.py` | 494 | Complete |
| `config/camera/crud.py` | 206 | Complete (uses function injection) |
| `config/camera/converters.py` | 130 | Partial - missing main converters |
| `config/camera/types/__init__.py` | 17 | Placeholder only |

---

## 4-Phase Execution Plan

### Phase 1: Remove Duplicates (4-6 hours, LOW RISK)

**Goal**: Remove ~1,400 lines of duplicated code from `config.py`

**Steps**:

1. **Remove duplicate constants/caches** (lines 57-87):
   - `_ACTIONS` → import from `config.commands`
   - All 6 global caches → they exist in respective modules

2. **Remove duplicate decorators** (lines 164-169):
   - `additional_section`, `additional_config` → import from `config.extensions`

3. **Remove duplicate storage functions** (lines 172-527, 2014-2024):
   - `get_main`, `set_main`, `get_camera`, `set_camera`, `get_camera_ids`
   - `get_enabled_local_motion_cameras`, `get_network_shares`, `invalidate`
   - → import from `config.storage`

4. **Replace `add_camera`/`rem_camera`** (lines 530-666):
   - Create wrappers that call `config.camera.crud` with injected dependencies
   - Example wrapper:
   ```python
   from motioneye.config.camera.crud import add_camera as _add_camera_impl

   def add_camera(device_details):
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
   ```

5. **Remove duplicate converters** (lines 750-757, 1854-1895):
   - `input_sanity_check`, `simple_mjpeg_camera_*` → import from `config.camera.converters`
   - Note: `simple_mjpeg_camera_dict_to_ui` needs wrapper (uses function injection)

6. **Remove duplicate commands** (lines 1898-1931):
   - `get_action_commands`, `get_monitor_command`, `invalidate_monitor_commands`
   - → import from `config.commands`

7. **Remove duplicate backup** (lines 1934-2011):
   - `backup` → import directly
   - `restore` → create wrapper that provides `invalidate_func`

8. **Remove duplicate extensions** (lines 2037-2152):
   - `get_additional_structure`, `_get_additional_config`, `_set_additional_config`
   - → import from `config.extensions`

**Validate after Phase 1**:
```bash
python -m py_compile motioneye/config.py
python -c "from motioneye import config; print('OK')"
```

---

### Phase 2: Move Main Converters (2-3 hours, LOW RISK)

**Goal**: Move `main_ui_to_dict` and `main_dict_to_ui` to `config/camera/converters.py`

**Steps**:

1. Copy `main_ui_to_dict` (lines 669-714) to `config/camera/converters.py`
   - Add imports: `hashlib`, `subprocess`, `settings`, `utils`

2. Copy `main_dict_to_ui` (lines 717-747) to `config/camera/converters.py`
   - Pure function, no new imports needed

3. Remove from `config.py`, add imports

4. Update `config/__init__.py` exports

**Validate**: Same as Phase 1

---

### Phase 3: Extract Motion Camera Converters (12-16 hours, HIGH RISK)

**Goal**: Move `motion_camera_ui_to_dict` (564 lines) and `motion_camera_dict_to_ui` (526 lines)

**Strategy**: Type-based converters using strategy pattern

**Create new files**:

1. `config/camera/types/base.py` - Abstract base class
2. `config/camera/types/v4l2.py` - V4L2 camera converter
3. `config/camera/types/libcamera.py` - Pi 5 libcamera converter
4. `config/camera/types/mmal.py` - MMAL converter
5. `config/camera/types/netcam.py` - Network camera converter

**Update** `config/camera/types/__init__.py` with dispatcher:
```python
def get_converter(config):
    if utils.is_v4l2_camera(config):
        return V4L2Converter()
    elif utils.is_libcamera_device(config):
        return LibcameraConverter()
    # etc.
```

**Key dependencies to handle**:
- `_()` translation function from `meyectl`
- `_USED_MOTION_OPTIONS` set - move to types module
- Multiple control modules: `diskctl`, `smbctl`, `v4l2ctl`
- External modules: `meyectl`, `motionctl`, `settings`, `tasks`, `uploadservices`, `utils`

**Validate**: Test each camera type on Pi 5

---

### Phase 4: Final Cleanup (2-3 hours, LOW RISK)

**Goal**: `config.py` becomes thin wrapper (~80 lines)

**Final structure**:
- All imports from `config` package
- Wrapper functions for injection-based APIs
- No logic, only re-exports

---

## Critical Files to Understand

1. **`handlers/config.py`** - Main consumer of config functions
   - Uses: `motion_camera_dict_to_ui`, `motion_camera_ui_to_dict`
   - Uses: `simple_mjpeg_camera_dict_to_ui`, `main_dict_to_ui`, `main_ui_to_dict`
   - Uses: `add_camera`, `rem_camera`, `backup`, `restore`

2. **`config/camera/crud.py`** - Uses function injection pattern
   - `add_camera(device_details, get_camera_ids_func, get_camera_func, ...)`
   - `rem_camera(camera_id, get_main_func, set_main_func, clear_cache_func)`

3. **`config/backup.py`** - Different signature
   - Old: `restore(content)`
   - New: `restore(content, invalidate_func=None)`

---

## Validation Commands

```bash
# Syntax validation
python -m py_compile motioneye/config.py
python -m py_compile motioneye/config/__init__.py
python -m py_compile motioneye/config/camera/converters.py

# Import test
python -c "from motioneye import config; print(dir(config))"

# All files
for f in motioneye/*.py motioneye/handlers/*.py motioneye/controls/*.py; do
    python -m py_compile "$f"
done
```

---

## 20 Files That Import config

These must continue to work after refactoring:

1. `meyectl.py`
2. `monitor.py`
3. `mediafiles.py`
4. `motionctl.py`
5. `mjpgclient.py`
6. `sendmail.py`
7. `sendtelegram.py`
8. `server.py`
9. `wsswitch.py`
10. `handlers/action.py`
11. `handlers/base.py`
12. `handlers/config.py`
13. `handlers/main.py`
14. `handlers/movie.py`
15. `handlers/movie_playback.py`
16. `handlers/relay_event.py`
17. `controls/tzctl.py`
18. `controls/smbctl.py`
19. `controls/wifictl.py`

---

## Risk Mitigation

1. **Git commit after each phase** - Easy rollback
2. **Syntax validation after every change**
3. **Don't change logic** - Pure refactoring only
4. **Wrappers maintain original signatures** - No breaking changes

---

## Questions to Ask User If Stuck

1. "Should I proceed with Phase X?"
2. "I found [issue]. Which approach do you prefer: A or B?"
3. "The validation failed with [error]. Should I investigate or rollback?"

---

## Success Criteria

- [ ] `config.py` is ~80 lines (wrapper only)
- [ ] All 20 importing files compile without errors
- [ ] Syntax validation passes for all files
- [ ] Manual Pi 5 testing confirms cameras work

---

## Start Here

Begin with **Phase 1, Step 1**: Remove duplicate `_ACTIONS` constant and global caches from `config.py`.

Read `config.py` first to understand current state, then systematically remove duplicates while adding imports.
