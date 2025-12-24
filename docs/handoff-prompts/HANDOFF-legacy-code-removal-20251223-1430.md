# HANDOFF: Legacy Code Removal for MotionEye 64-bit Migration

**Date**: 2025-12-23
**Branch**: `feature/trixie-64bit-migration`
**Status**: Plan complete, ready for implementation

---

## Context

You are continuing work on a fork of MotionEye that targets **64-bit Raspberry Pi OS (Bookworm/Trixie) on Pi 4 and Pi 5 only**. A previous session completed initial migration work but left legacy code in the codebase. Your task is to remove all legacy code.

### What Was Already Done
- Deleted `motioneye/controls/mmalctl.py` (MMAL camera detection module)
- Deleted `motioneye/extra/motioneye.sysv` (SysV init script)
- Removed h264_omx options from UI templates
- Removed h264_omx codec mappings from `mediafiles.py`
- Updated UI to show "Local CSI Camera (libcamera)" instead of MMAL

### What Remains (Your Task)
Significant legacy code still exists. A comprehensive analysis is in `docs/analysis/legacy-code.md` and the implementation plan is in `docs/plans/legacy-code-removal-plan-20251223-1400.md`.

---

## Your Mission

Execute the 7-phase legacy code removal plan. Each phase should be a separate commit.

---

## Phase 1: Critical Bug Fix (15 min)

**File**: `motioneye/controls/pictl.py`
**Line**: 92

**Bug**: Returns `'mmal'` for Pi 4, but MMAL doesn't work on Pi 4 with Bookworm/Trixie.

**Fix**: Change line 92 from:
```python
'camera_interface': 'libcamera' if is_pi5 else 'mmal',
```
To:
```python
'camera_interface': 'libcamera',  # libcamera for all Pi 4+
```

**Commit**: `git commit -m "Fix pictl.py camera_interface to return libcamera for all Pi 4+"`

---

## Phase 2: Remove h264_omx Dead Code (30 min)

### 2.1 Delete h264_omx function
**File**: `motioneye/motionctl.py`
**Lines**: 461-468

Delete the entire `has_h264_omx_support()` function.

### 2.2 Remove template parameter
**File**: `motioneye/handlers/main.py`
**Line**: 55

Delete this line:
```python
has_h264_omx_support=motionctl.has_h264_omx_support(),
```

### 2.3 Delete backup template
```bash
rm motioneye/templates/main.html.bak
```

**Commit**: `git commit -m "Remove h264_omx dead code - not available on 64-bit OS"`

---

## Phase 3: Remove Motion <5.0 Compatibility (2 hrs)

This is the largest phase. Motion 5.0+ is required for libcamera.

### 3.1 Simplify adaptation.py
**File**: `motioneye/config/adaptation.py`

Delete all pre-5.0 mappings:
- Lines 27-45: `text_double`, `webcontrol_html_output`, `text_scale`, `webcontrol_interface` functions
- Lines 47-80: `_MOTION_41_TO_43_OPTIONS_MAPPING` and `_MOTION_43_TO_41_OPTIONS_MAPPING`
- Lines 83-150: `netcam_*` functions and `_MOTION_43_TO_44_OPTIONS_MAPPING`, `_MOTION_44_TO_43_OPTIONS_MAPPING`

Keep only Motion 5.0 mappings (lines 153-268).

Rename the mappings:
- `_MOTION_44_TO_50_OPTIONS_MAPPING` → `MOTION_50_OPTIONS_MAPPING`
- `_MOTION_50_TO_44_OPTIONS_MAPPING` → `MOTION_50_FROM_OPTIONS_MAPPING`

Update module docstring to reflect Motion 5.0 only.

### 3.2 Remove pre-5.0 defaults
**File**: `motioneye/config/defaults.py`
**Lines**: 145-150

Delete this entire block:
```python
# Motion 5.0 removed stream_port, stream_localhost, stream_auth_method
# Streams are now served via webcontrol interface
if not motionctl.is_motion_50():
    data.setdefault('stream_localhost', False)
    data.setdefault('stream_port', 9080 + camera_id)
    data.setdefault('stream_auth_method', 0)
```

### 3.3 Remove pre-5.0 MJPG client code
**File**: `motioneye/mjpgclient.py`
**Lines**: 339-360

Replace the `if/else` block with only Motion 5.0 code:
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

### 3.4 Search for and remove other is_motion_50() checks
```bash
grep -rn "is_motion_50()" motioneye/
```

Remove all conditionals, keep only Motion 5.0 code paths.

### 3.5 Add Motion 5.0 validation at startup
**File**: `motioneye/motionctl.py`

Add after `is_motion_50()` function:
```python
def validate_motion_version():
    """Ensure Motion 5.0+ is installed. Call at startup."""
    if not is_motion_50():
        raise RuntimeError(
            "Motion 5.0+ is required. Please upgrade Motion or use an older MotionEye version."
        )
```

**Commit**: `git commit -m "Remove Motion <5.0 compatibility layer - Motion 5.0+ now required"`

---

## Phase 4: Remove MMAL Code (45 min)

### 4.1 Remove is_mmal_camera function
**File**: `motioneye/utils/__init__.py`
**Lines**: 216-223

Delete entire function.

### 4.2 Remove mmalcam_name from is_local_motion_camera
**File**: `motioneye/utils/__init__.py`
**Line**: 201

Remove `or config.get('mmalcam_name')` from the return statement.

### 4.3 Remove MMAL protocol handling
**File**: `motioneye/handlers/config.py`

Find `elif proto in ('libcamera', 'mmal'):` and change to `elif proto == 'libcamera':`.

Remove any `utils.is_mmal_camera()` calls.

### 4.4 Remove MMAL from converters.py
**File**: `motioneye/config/camera/converters.py`

Search for "mmal" and remove all MMAL-related code:
```bash
grep -n "mmal" motioneye/config/camera/converters.py
```

### 4.5 Remove mmalcam_name from constants.py
**File**: `motioneye/config/camera/constants.py`
**Line**: 55

Remove `'mmalcam_name',` from `MOTION_41_CAMERA_PARAMS`.

### 4.6 Remove MMAL case from main.js
**File**: `motioneye/static/js/main.js`
**Lines**: 2581-2582

Delete:
```javascript
case 'mmal':
    prettyType = 'MMAL Camera (deprecated - migrated to libcamera)';
    break;
```

**Commit**: `git commit -m "Remove all MMAL camera support - libcamera only for Pi 4+"`

---

## Phase 5: Remove ARMv6/32-bit Support (30 min)

### 5.1 Simplify architecture detection
**File**: `motioneye/rpicam_rtsp.py`
**Lines**: 63-89

Replace `_detect_architecture()` with:
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

**Commit**: `git commit -m "Remove 32-bit architecture support - 64-bit only"`

---

## Phase 6: Clean Orphaned Translations (1 hr)

### 6.1 Find all MMAL translation strings
```bash
grep -rn "MMAL" motioneye/locale/
grep -rn "MMAL" motioneye/static/js/motioneye.*.json
```

### 6.2 Remove MMAL strings from all .po files
Edit each locale file to remove MMAL-related msgid/msgstr pairs.

### 6.3 Remove MMAL from JSON translation files
Edit each `motioneye.*.json` file to remove MMAL entries.

**Commit**: `git commit -m "Remove orphaned MMAL translation strings"`

---

## Phase 7: Update Documentation (30 min)

### 7.1 Update module docstrings
Update these files to remove references to Motion <5.0 and MMAL:
- `motioneye/motionctl.py`
- `motioneye/config/adaptation.py`
- `motioneye/config/defaults.py`

### 7.2 Update CLAUDE.md
Add requirements section noting Motion 5.0+ is required.

### 7.3 Update analysis document
Mark items as complete in `docs/analysis/legacy-code.md`.

**Commit**: `git commit -m "Update documentation to reflect Motion 5.0+ requirement"`

---

## Verification After Each Phase

Run these checks after each phase:

```bash
# No import errors
python3 -c 'import motioneye'

# Syntax check key files
python3 -m py_compile motioneye/motionctl.py
python3 -m py_compile motioneye/config/adaptation.py
python3 -m py_compile motioneye/mjpgclient.py
```

---

## Final Verification (On Pi)

**Before running these, ask user if Pi is powered on.**

```bash
# Deploy to Pi
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

# Install and restart
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"

# Check logs
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"

# Verify camera works
ssh admin@192.168.1.176 "curl -s --max-time 3 'http://localhost:7999/1/mjpg/stream' -o /tmp/test.dat && file /tmp/test.dat"
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `docs/analysis/legacy-code.md` | Detailed analysis of all legacy code |
| `docs/plans/legacy-code-removal-plan-20251223-1400.md` | Full implementation plan |
| `motioneye/controls/pictl.py` | Pi detection and camera interface |
| `motioneye/motionctl.py` | Motion daemon control |
| `motioneye/config/adaptation.py` | Motion version config mappings |
| `motioneye/config/defaults.py` | Default config values |
| `motioneye/mjpgclient.py` | MJPEG streaming client |
| `motioneye/utils/__init__.py` | Utility functions including camera type checks |
| `motioneye/handlers/config.py` | Config API handlers |
| `motioneye/static/js/main.js` | Frontend JavaScript |

---

## Important Notes

1. **Read files before editing** - Always use the Read tool first
2. **One phase per commit** - Easier to rollback if issues arise
3. **Test imports after each phase** - Catch syntax errors early
4. **Don't guess** - If unsure about a change, check the plan documents
5. **Pi testing optional but recommended** - Ask user before attempting SSH

---

## Expected Outcome

After completing all phases:
- No MMAL references in code (except historical comments in docs)
- No h264_omx references
- No Motion <5.0 code paths
- No 32-bit architecture support
- Clean, maintainable codebase targeting Pi 4/5 + 64-bit OS + Motion 5.0+
