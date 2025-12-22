# HANDOFF: Autofocus Hot-Reload Integration

**Created:** 2025-12-21 17:45
**Priority:** High
**Estimated Effort:** ~100 lines across 5 files

---

## Mission

Migrate MotionEye's autofocus controls from the legacy `libcam_control_item` format to Motion 5.0's dedicated hot-reloadable `libcam_af_*` parameters. This enables instant focus changes without camera restart.

---

## Context

### What Was Done
1. Motion 5.0 was updated with new autofocus API (separate project)
2. Documentation created: `docs/Motion/Motion-Autofocus-API.md` and `docs/Motion/Motion-Autofocus-Quick-Reference.md`
3. Implementation plan created: `docs/plans/autofocus-integration-plan-20251221-1730.md`

### The Problem
MotionEye currently uses `libcam_control_item` format for autofocus:
```python
# Current (requires restart)
control_items.append(f'AfMode={af_mode}')
control_items.append(f'AfRange={af_range}')
```

Motion 5.0 now supports dedicated hot-reloadable parameters:
```python
# Target (instant changes)
data['libcam_af_mode'] = af_mode
data['libcam_af_range'] = af_range
data['libcam_af_speed'] = af_speed  # NEW
data['libcam_lens_position'] = lens_pos
```

### Reference Pattern
The AWB controls were recently migrated using the exact same pattern (commits cdff7532, a52cd6b8). Use those as a reference for implementation style.

---

## Implementation Tasks

Execute these in order:

### Task 1: Update Constants Registry
**File:** `motioneye/config/camera/constants.py`

1. Find the `USED_MOTION_OPTIONS` set (~lines 26-95) and add:
```python
'libcam_af_mode',
'libcam_lens_position',
'libcam_af_range',
'libcam_af_speed',
```

2. Find the `HOT_RELOAD_PARAMS` set (~lines 114-230) and add after the AWB params:
```python
# Autofocus controls (Motion 5.0+ hot-reloadable)
'libcam_af_mode',       # 0=Manual, 1=Auto, 2=Continuous
'libcam_lens_position', # 0.0-15.0 dioptres
'libcam_af_range',      # 0=Normal, 1=Macro, 2=Full
'libcam_af_speed',      # 0=Normal, 1=Fast
```

### Task 2: Update Defaults
**File:** `motioneye/config/defaults.py`

Find the autofocus defaults section (~lines 96-100) in `_set_default_motion_camera()` and add `@af_speed`:
```python
data['@af_mode'] = 2          # Continuous
data['@af_range'] = 0         # Normal
data['@af_speed'] = 0         # Normal speed (NEW)
data['@lens_position'] = 0.0  # Infinity
```

### Task 3: Migrate Converters
**File:** `motioneye/config/camera/converters.py`

**3a. Update UI-to-Motion conversion** (~lines 456-472 in `_camera_ui_to_motion()`):

Replace the `libcam_control_item` approach with dedicated parameters:
```python
# Autofocus controls - Motion 5.0+ has dedicated libcam_af_* parameters
if ui.get('supports_autofocus'):
    af_mode = int(ui.get('autofocus_mode', 2))
    af_range = int(ui.get('autofocus_range', 0))
    af_speed = int(ui.get('autofocus_speed', 0))  # NEW
    lens_pos = float(ui.get('lens_position', 0.0))

    # Store for UI persistence with @ prefix
    data['@af_mode'] = af_mode
    data['@af_range'] = af_range
    data['@af_speed'] = af_speed  # NEW
    data['@lens_position'] = lens_pos

    # Set dedicated libcam_af_* parameters (Motion 5.0+ hot-reloadable)
    data['libcam_af_mode'] = af_mode
    data['libcam_af_range'] = af_range
    data['libcam_af_speed'] = af_speed  # NEW
    data['libcam_lens_position'] = lens_pos

    # REMOVE the old libcam_control_item lines for AF
```

**3b. Update Motion-to-UI conversion** (~lines 1046-1071 in `_camera_motion_to_ui()`):

Add AF speed reading:
```python
if supports_af:
    ui['autofocus_mode'] = int(data.get('@af_mode', data.get('libcam_af_mode', 2)))
    ui['autofocus_range'] = int(data.get('@af_range', data.get('libcam_af_range', 0)))
    ui['autofocus_speed'] = int(data.get('@af_speed', data.get('libcam_af_speed', 0)))  # NEW
    ui['lens_position'] = float(data.get('@lens_position', data.get('libcam_lens_position', 0.0)))
    ui['supports_autofocus'] = True
```

### Task 4: Update HTML Template
**File:** `motioneye/templates/partials/settings/_video_device.html`

**4a. Add `hot-reload` class** to existing AF controls (~lines 58-78):
- `autofocusModeSelect` - add `hot-reload` class
- `autofocusRangeSelect` - add `hot-reload` class
- `lensPositionSlider` - add `hot-reload` class

**4b. Add `libcam-only` class** to all AF controls if not already present

**4c. Add new AF Speed control** (insert after AF Range, before Lens Position):
```html
<!-- Autofocus Speed (depends on mode != Manual) -->
<tr class="settings-item libcam-only" depends="autofocusMode!=0">
    <td class="settings-item-label-container">
        <span class="settings-item-label" data-i18n="Autofocus Speed">Autofocus Speed</span>
    </td>
    <td class="settings-item-value">
        <select class="styled device camera-config hot-reload" id="autofocusSpeedSelect">
            <option value="0" data-i18n="Normal">Normal</option>
            <option value="1" data-i18n="Fast">Fast</option>
        </select>
    </td>
    <td><span class="help-mark" data-i18n-title="select autofocus speed; Fast prioritizes speed over accuracy for tracking moving subjects">?</span></td>
</tr>
```

### Task 5: Update JavaScript
**File:** `motioneye/static/js/main.js`

**5a. Update `configPanelToDict()`** (~line 2087-2090):
Add AF speed reading:
```javascript
'autofocus_speed': parseInt($('#autofocusSpeedSelect').val()) || 0,
```

**5b. Update `dictToConfigPanel()`** (~line 2417-2419):
Add AF speed setting:
```javascript
$('#autofocusSpeedSelect').val(dict['autofocus_speed'] != null ? dict['autofocus_speed'] : 0);
markHideIfNull(!dict['supports_autofocus'], 'autofocusSpeedSelect');
```

**5c. Add hot-reload parameter mapping** (~line 5852-5858):
Add after AWB mappings:
```javascript
// Autofocus hot-reload params (Motion 5.0+)
'autofocusModeSelect': 'libcam_af_mode',
'autofocusRangeSelect': 'libcam_af_range',
'autofocusSpeedSelect': 'libcam_af_speed',
'lensPositionSlider': 'libcam_lens_position'
```

---

## Validation

After implementation, verify:

1. **Syntax check all Python files:**
```bash
python -m py_compile motioneye/config/camera/constants.py
python -m py_compile motioneye/config/defaults.py
python -m py_compile motioneye/config/camera/converters.py
```

2. **Check for obvious JS errors** - ensure no syntax issues in main.js

3. **Review the changes match AWB pattern** - compare with existing AWB implementation for consistency

---

## Testing on Pi 5

**IMPORTANT: Ask user if Pi 5 is powered on before attempting connection.**

### Deploy and Test
```bash
# Sync code
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

# Install
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

# Restart service
ssh admin@192.168.1.176 "sudo systemctl restart motioneye"

# Check logs
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"
```

### Test Hot-Reload
1. Open MotionEye UI: `http://192.168.1.176:8765/`
2. Go to camera settings
3. Change AF Mode - should apply instantly without restart notification
4. Change AF Speed - should apply instantly
5. Change Lens Position (in Manual mode) - should apply instantly
6. Verify no HTTP 403/405 errors in Motion logs

---

## Completion

When all tasks are complete and tested:

1. **Create summary document:**
   Write a completion summary to `docs/summaries/autofocus-integration-summary-YYYYMMDD-HHMM.md` with:
   - What was changed
   - Files modified
   - Testing results
   - Any issues encountered and how they were resolved

2. **Commit changes** (if requested by user):
   - Stage all modified files
   - Commit with message describing the migration

---

## Reference Files

- **Plan:** `docs/plans/autofocus-integration-plan-20251221-1730.md`
- **Motion AF API:** `docs/Motion/Motion-Autofocus-API.md`
- **Quick Reference:** `docs/Motion/Motion-Autofocus-Quick-Reference.md`
- **AWB Pattern (reference):** Look at commits cdff7532, a52cd6b8 for migration pattern

---

## Key Constraints

1. **Follow existing patterns** - Match AWB implementation style exactly
2. **@ prefix for UI persistence** - Store UI values with @ prefix, Motion params without
3. **Hot-reload class required** - UI controls must have `hot-reload` class for instant updates
4. **libcam-only class** - AF controls only visible for libcamera cameras
5. **Depends attribute** - Lens position only shown when mode=0 (Manual)
6. **Remove legacy code** - Delete the `libcam_control_item` AF entries after migration
