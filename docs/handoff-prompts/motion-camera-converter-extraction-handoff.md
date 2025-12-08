# Handoff: Motion Camera Converter Extraction

## Context

You are implementing a planned refactoring to extract two large converter functions from `motioneye/config.py` to `motioneye/config/camera/converters.py`.

**Read the full plan first**: `docs/plans/motion-camera-converter-extraction.md`

## Current State

- `config.py` is ~1,350 lines with two massive functions that should be in `converters.py`
- `converters.py` already exists with simpler converters (`main_ui_to_dict`, `main_dict_to_ui`, `simple_mjpeg_camera_*`)
- The codebase has already undergone partial refactoring - many other functions were extracted to submodules

## Your Task

Execute the migration plan to move:
1. `motion_camera_ui_to_dict` (config.py lines 229-792)
2. `motion_camera_dict_to_ui` (config.py lines 795-1320)
3. `_USED_MOTION_OPTIONS` constant (config.py lines 114-181)

## Implementation Steps

### Step 1: Create `constants.py`

Create `motioneye/config/camera/constants.py` with:
- `USED_MOTION_OPTIONS` set (copy from config.py lines 114-181)
- Keep the existing regex constants in converters.py (they're already there)

### Step 2: Modify `converters.py`

Add the two motion camera functions with dependency injection:

```python
def motion_camera_ui_to_dict(
    ui,
    prev_config=None,
    *,
    get_main_func,
    task_scheduler=None,
    translate=lambda x: x,
):
    """Convert camera UI config to Motion config dict."""
    # Copy implementation from config.py
    # Replace:
    #   get_main() -> get_main_func()
    #   _('...') -> translate('...')
    #   tasks.add(...) -> if task_scheduler: task_scheduler(...)
    pass

def motion_camera_dict_to_ui(
    data,
    *,
    get_action_commands_func,
):
    """Convert Motion config dict to camera UI format."""
    # Copy implementation from config.py
    # Replace:
    #   get_action_commands(data) -> get_action_commands_func(data)
    pass
```

**Required imports to add to converters.py**:
```python
import os
from errno import EEXIST
from re import match, sub
from shlex import split

from motioneye import meyectl, motionctl, settings, utils
from motioneye.controls import diskctl, smbctl, v4l2ctl

from .constants import USED_MOTION_OPTIONS
```

### Step 3: Update `config.py`

Replace the function bodies with thin wrappers:

```python
from motioneye.config.camera.converters import (
    motion_camera_ui_to_dict as _motion_camera_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_camera_dict_to_ui_impl,
)

def motion_camera_ui_to_dict(ui, prev_config=None):
    """Convert camera UI config to Motion config dict. Wrapper with injected deps."""
    from motioneye import tasks, uploadservices

    def _task_scheduler(delay, func, **kwargs):
        tasks.add(delay, func, **kwargs)

    return _motion_camera_ui_to_dict_impl(
        ui,
        prev_config,
        get_main_func=get_main,
        task_scheduler=_task_scheduler,
        translate=_,
    )

def motion_camera_dict_to_ui(data):
    """Convert Motion config dict to camera UI format. Wrapper with injected deps."""
    return _motion_camera_dict_to_ui_impl(
        data,
        get_action_commands_func=get_action_commands,
    )
```

Also:
- Remove `_USED_MOTION_OPTIONS` from config.py (it's now in constants.py)
- Update imports at top of config.py to import from converters
- Update the module docstring

### Step 4: Validate

Run these commands to verify:

```bash
# Syntax validation
python -m py_compile motioneye/config/camera/constants.py
python -m py_compile motioneye/config/camera/converters.py
python -m py_compile motioneye/config.py

# Import validation
python -c "from motioneye import config; print('config.py OK')"
python -c "from motioneye.config.camera import converters; print('converters.py OK')"
python -c "from motioneye.config.camera.constants import USED_MOTION_OPTIONS; print(f'constants.py OK: {len(USED_MOTION_OPTIONS)} options')"
```

## Critical Details

### The `_()` Translation Function

The `_()` function is installed globally by `meyectl.py` via `gettext.install()`. In the extracted function, we inject it as `translate` parameter. The wrapper in config.py passes `_` (which is in builtins after gettext.install).

### Side Effects to Preserve

1. **Directory creation** (line ~474 in original):
   ```python
   os.makedirs(data['target_dir'])
   ```
   Keep this inline - it's idempotent and necessary.

2. **Task scheduling** (lines ~494-501 in original):
   ```python
   tasks.add(0, uploadservices.update, ...)
   ```
   Use the injected `task_scheduler` callback. Check `if task_scheduler:` before calling.

3. **Mask file creation** (lines ~438, ~589 in original):
   ```python
   utils.build_editable_mask_file(...)
   ```
   Keep this as-is - it's already abstracted through utils.

### Import Considerations

In `converters.py`, you'll need these imports:
- `from motioneye import meyectl, motionctl, settings, utils`
- `from motioneye.controls import diskctl, smbctl, v4l2ctl`
- Standard library: `os`, `logging`, `re` (match, sub), `shlex` (split), `errno` (EEXIST)

Do NOT import `tasks` or `uploadservices` in converters.py - those come via the injected callback.

### Preserving the Public API

The callers in these files should NOT need modification:
- `handlers/config.py`
- `handlers/picture.py`
- `config/camera/crud.py`

They all call `config.motion_camera_*` functions, which are the wrappers.

## Testing

After implementation, the user will test on their Pi 5 with Camera Module 3 via SSH:

1. Syntax validation (you do this)
2. Import validation (you do this)
3. Functional testing on Pi 5 (user does this):
   - View camera config in web UI
   - Modify and save settings
   - Verify libcamera-specific features work

## Files to Create/Modify

| File | Action |
|------|--------|
| `motioneye/config/camera/constants.py` | CREATE |
| `motioneye/config/camera/converters.py` | MODIFY (add ~1100 lines) |
| `motioneye/config.py` | MODIFY (remove ~1100 lines, add wrappers) |

## Success Criteria

- All syntax checks pass
- All import validations pass
- `config.py` reduced from ~1,350 to ~300 lines
- `converters.py` expanded from ~235 to ~1,350 lines
- No changes needed to any caller files
