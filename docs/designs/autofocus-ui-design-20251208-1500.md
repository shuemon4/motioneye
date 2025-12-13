# Autofocus UI Controls Design Specification

**Date**: 2025-12-08
**Status**: Ready for Implementation
**Target**: Pi 5 + Pi Camera v3 (IMX708)

---

## Executive Summary

This design adds autofocus controls to the MotionEye web interface for Pi Camera v3 (IMX708). The backend infrastructure is **already implemented** in `converters.py` - this design covers only the frontend UI additions needed in `main.html` and `main.js`.

---

## Research Findings: Pi Camera v3 Autofocus

### libcamera Autofocus Controls

Based on Raspberry Pi documentation and libcamera API:

| Control | Values | Description |
|---------|--------|-------------|
| **AfMode** | 0=Manual, 1=Auto (single-shot), 2=Continuous | Autofocus operating mode |
| **AfRange** | 0=Normal, 1=Macro, 2=Full | Focus search range |
| **AfSpeed** | 0=Normal, 1=Fast | Autofocus speed |
| **AfMetering** | 0=Auto, 1=Windows | AF metering zones |
| **AfTrigger** | 0=Idle, 1=Start, 2=Cancel | Trigger single-shot AF |
| **LensPosition** | 0.0-15.0 dioptres | Manual focus position (reciprocal of focal distance in meters) |

### LensPosition Explained

The `LensPosition` value is measured in **dioptres** (1/meters):
- `0.0` = Infinity focus
- `0.5` = 2 meters
- `1.0` = 1 meter
- `2.0` = 0.5 meters (50cm)
- `5.0` = 0.2 meters (20cm)
- `10.0` = 0.1 meters (10cm - macro)

For Camera v3, typical range is 0.0 to ~10.0 dioptres.

### Key Constraints

1. **LensPosition only works when AfMode=0 (Manual)**
2. libcamera takes full control of focus - cannot be changed "behind its back"
3. Motion 5.0+ uses `libcam_control_item` directive for focus control
4. AfTrigger is transient and shouldn't be stored in config

---

## Existing Backend Infrastructure

The backend already handles autofocus controls (no changes needed):

### Camera Detection (`libcamctl.py:49-50`)
```python
_AUTOFOCUS_SENSORS = {'imx708'}
# Returns supports_autofocus: True for Camera v3
```

### UI → Motion Conversion (`converters.py:417-441`)
```python
if ui.get('supports_autofocus'):
    af_mode = ui.get('autofocus_mode', 2)
    af_range = ui.get('autofocus_range', 0)
    lens_pos = ui.get('lens_position', 0.0)

    data['@supports_autofocus'] = True
    data['@af_mode'] = af_mode
    data['@af_range'] = af_range
    data['@lens_position'] = lens_pos

    control_items = [f'AfMode={af_mode}', f'AfRange={af_range}']
    if af_mode == 0:  # Manual focus mode
        control_items.append(f'LensPosition={lens_pos}')
    data['libcam_control_item'] = control_items
```

### Motion → UI Conversion (`converters.py:979-984`)
```python
if data.get('@supports_autofocus'):
    ui['autofocus_mode'] = data.get('@af_mode', 2)
    ui['autofocus_range'] = data.get('@af_range', 0)
    ui['lens_position'] = data.get('@lens_position', 0.0)
    ui['supports_autofocus'] = True
```

---

## UI Design

### Control Layout

Add controls to the **Video Device** section after the Framerate slider (line 334 in main.html):

```
┌─────────────────────────────────────────────────────────┐
│ Video Device                                        [-] │
├─────────────────────────────────────────────────────────┤
│ Camera Name      [                    ]                 │
│ Camera Device    /dev/video0                            │
│ Camera Type      libcamera Camera                       │
│ ─────────────────────────────────────────────────────── │
│ Auto Brightness  [ ]                                    │
│ ─────────────────────────────────────────────────────── │
│ Video Resolution [1920x1080 ▼]                          │
│ Video Rotation   [0° ▼]                                 │
│ Framerate        [====●=====] 15                        │
│ ─────────────────────────────────────────────────────── │
│ Autofocus Mode   [Continuous ▼]         ← NEW          │
│ Autofocus Range  [Normal ▼]             ← NEW          │
│ Focus Position   [●=========] 0.0       ← NEW (manual) │
│ [Trigger Focus]                         ← NEW (auto)   │
│ ─────────────────────────────────────────────────────── │
│ Privacy Mask     [ ]                                    │
└─────────────────────────────────────────────────────────┘
```

### Control Specifications

#### 1. Autofocus Mode (`autofocusModeSelect`)
- **Type**: Dropdown (`<select>`)
- **ID**: `autofocusModeSelect`
- **Visibility**: Only when `supports_autofocus` is true
- **Options**:
  | Value | Label | Description |
  |-------|-------|-------------|
  | 0 | Manual | Fixed focus at specified position |
  | 1 | Auto (Single) | Focus once, then hold |
  | 2 | Continuous | Always tracking focus (default) |

#### 2. Autofocus Range (`autofocusRangeSelect`)
- **Type**: Dropdown (`<select>`)
- **ID**: `autofocusRangeSelect`
- **Visibility**: Only when `supports_autofocus` is true AND `autofocus_mode != 0`
- **Options**:
  | Value | Label | Description |
  |-------|-------|-------------|
  | 0 | Normal | Standard focus range (default) |
  | 1 | Macro | Close-up focus range |
  | 2 | Full | Full lens travel range |

#### 3. Focus Position (`lensPositionSlider`)
- **Type**: Range slider
- **ID**: `lensPositionSlider`
- **Visibility**: Only when `autofocus_mode == 0` (Manual)
- **Range**: 0.0 to 10.0 dioptres
- **Step**: 0.1
- **Ticks**: `0|1|2|5|10` (Infinity, 1m, 50cm, 20cm, 10cm)
- **Display**: Show current value with distance equivalent

#### 4. Trigger Focus Button (`triggerFocusButton`) - Optional Enhancement
- **Type**: Button
- **ID**: `triggerFocusButton`
- **Visibility**: Only when `autofocus_mode == 1` (Auto/Single)
- **Action**: Triggers one-shot autofocus via API
- **Note**: This requires additional backend work (not in scope for Phase 1)

---

## Implementation Plan

### Phase 1: Core Controls (Minimal)

**Files to modify:**
1. `motioneye/templates/main.html` - Add HTML controls
2. `motioneye/static/js/main.js` - Wire up data binding

**Estimated effort:** 2-3 hours

#### 1.1 HTML Template Changes (`main.html`)

Insert after the framerate slider (line ~334), before the separator:

```html
<!-- Autofocus Controls (Camera v3) -->
<tr class="settings-item libcamera-only" af-supported="true">
    <td class="settings-item-label"><span class="settings-item-label">Autofocus Mode</span></td>
    <td class="settings-item-value">
        <select class="styled device camera-config" id="autofocusModeSelect">
            <option value="0">Manual</option>
            <option value="1">Auto (Single Shot)</option>
            <option value="2">Continuous</option>
        </select>
    </td>
    <td><span class="help-mark" title="select autofocus behavior: Manual for fixed focus, Auto for single-shot, Continuous for always tracking">?</span></td>
</tr>
<tr class="settings-item libcamera-only" af-supported="true" depends="autofocusMode!=0">
    <td class="settings-item-label"><span class="settings-item-label">Autofocus Range</span></td>
    <td class="settings-item-value">
        <select class="styled device camera-config" id="autofocusRangeSelect">
            <option value="0">Normal</option>
            <option value="1">Macro (Close-up)</option>
            <option value="2">Full Range</option>
        </select>
    </td>
    <td><span class="help-mark" title="select the focus search range: Normal for everyday use, Macro for close objects, Full for maximum range">?</span></td>
</tr>
<tr class="settings-item libcamera-only" af-supported="true" depends="autofocusMode=0" min="0" max="10" snap="0" ticks="0|1|2|5|10" decimals="1">
    <td class="settings-item-label"><span class="settings-item-label">Focus Position</span></td>
    <td class="settings-item-value"><input type="text" class="range styled device camera-config" id="lensPositionSlider"></td>
    <td><span class="help-mark" title="set manual focus position in dioptres (0=infinity, 1=1m, 2=50cm, 5=20cm, 10=10cm)">?</span></td>
</tr>
```

#### 1.2 JavaScript Changes (`main.js`)

**Add to `cameraUi2Dict()` (around line 1937, after framerate):**

```javascript
/* autofocus controls (libcamera Camera v3) */
'supports_autofocus': $('#deviceTypeEntry')[0].supportsAutofocus || false,
'autofocus_mode': parseInt($('#autofocusModeSelect').val()) || 2,
'autofocus_range': parseInt($('#autofocusRangeSelect').val()) || 0,
'lens_position': parseFloat($('#lensPositionSlider').val()) || 0.0,
```

**Add to `dict2CameraUi()` (around line 2248, after framerate):**

```javascript
/* autofocus controls (libcamera Camera v3) */
$('#deviceTypeEntry')[0].supportsAutofocus = dict['supports_autofocus'] || false;
$('#autofocusModeSelect').val(dict['autofocus_mode'] != null ? dict['autofocus_mode'] : 2);
markHideIfNull('autofocus_mode', 'autofocusModeSelect');
$('#autofocusRangeSelect').val(dict['autofocus_range'] != null ? dict['autofocus_range'] : 0);
markHideIfNull('autofocus_range', 'autofocusRangeSelect');
$('#lensPositionSlider').val(dict['lens_position'] != null ? dict['lens_position'] : 0.0);
markHideIfNull('lens_position', 'lensPositionSlider');
```

**Add libcamera type to the prettyType switch (around line 2204):**

```javascript
case 'libcamera':
    prettyType = 'libcamera Camera';
    break;
```

**Add visibility toggle for autofocus controls (in updateConfigUI or similar):**

```javascript
/* Show/hide autofocus controls based on camera support */
if (dict['supports_autofocus']) {
    $('tr[af-supported="true"]').show();
} else {
    $('tr[af-supported="true"]').hide();
}

/* Show/hide lens position based on AF mode */
$('#autofocusModeSelect').change(function() {
    updateConfigUI();
});
```

### Phase 2: Enhanced UX (Optional)

**Additional features:**
1. Focus position display with distance equivalent ("0.5 dioptres ≈ 2m")
2. Trigger Focus button for single-shot mode
3. Visual focus indicator (if Motion provides feedback)
4. Preset focus positions (Infinity, 1m, 50cm, Macro)

### Phase 3: Translations

Add to translation files:
- "Autofocus Mode" / "Aŭtofokusa Reĝimo"
- "Autofocus Range" / "Aŭtofokusa Amplekso"
- "Focus Position" / "Fokusa Pozicio"
- "Manual" / "Mana"
- "Continuous" / "Daŭra"
- etc.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
├─────────────────────────────────────────────────────────────────┤
│  main.html                    main.js                           │
│  ┌──────────────────┐        ┌─────────────────────┐           │
│  │ autofocusModeSelect │←────→│ cameraUi2Dict()     │           │
│  │ autofocusRangeSelect│      │ dict2CameraUi()     │           │
│  │ lensPositionSlider │       └─────────┬───────────┘           │
│  └──────────────────┘                   │                       │
└─────────────────────────────────────────┼───────────────────────┘
                                          │ JSON API
                                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                          BACKEND                                 │
├─────────────────────────────────────────────────────────────────┤
│  handlers/config.py           config/camera/converters.py       │
│  ┌─────────────────┐         ┌────────────────────────┐         │
│  │ GET /config/{id}│←───────→│ motion_camera_dict_to_ui()│      │
│  │ POST /config/{id}│        │ motion_camera_ui_to_dict()│      │
│  └─────────────────┘         └────────────┬───────────┘         │
└───────────────────────────────────────────┼─────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MOTION CONFIG                              │
├─────────────────────────────────────────────────────────────────┤
│  /etc/motioneye/camera-1.conf                                   │
│  ┌─────────────────────────────────────────────┐               │
│  │ libcam_control_item AfMode=2                │               │
│  │ libcam_control_item AfRange=0               │               │
│  │ libcam_control_item LensPosition=0.0        │ (manual only) │
│  └─────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MOTION DAEMON                              │
├─────────────────────────────────────────────────────────────────┤
│  motion → libcamera → Camera v3 (IMX708) lens driver            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Testing Checklist

### Unit Testing
- [ ] Verify `cameraUi2Dict()` correctly reads autofocus values
- [ ] Verify `dict2CameraUi()` correctly populates autofocus controls
- [ ] Verify controls hidden for non-autofocus cameras
- [ ] Verify lens position hidden when not in manual mode

### Integration Testing
- [ ] GET `/api/config/1/get` returns `autofocus_mode`, `autofocus_range`, `lens_position`
- [ ] POST `/api/config/1/set` accepts and stores autofocus values
- [ ] Motion config file includes correct `libcam_control_item` directives
- [ ] Camera restarts with new focus settings applied

### Hardware Testing (Pi 5 + Camera v3)
- [ ] Continuous mode: focus tracks moving objects
- [ ] Manual mode: focus stays at set position
- [ ] LensPosition values produce expected focal distances
- [ ] Auto mode: single-shot focus works on scene

### Edge Cases
- [ ] V4L2 camera: autofocus controls hidden
- [ ] Network camera: autofocus controls hidden
- [ ] MMAL camera: autofocus controls hidden
- [ ] Camera v2 (imx219): autofocus controls hidden
- [ ] Mode switch: lens position shows/hides correctly
- [ ] Default values applied for new cameras

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Focus position values incorrect | Low | Medium | Test on real hardware, document dioptre values |
| Controls shown for wrong camera | Low | Low | Backend already filters by sensor type |
| Motion doesn't apply settings | Low | High | Verify libcam_control_item format in Motion 5.0 docs |
| UI state inconsistent | Medium | Low | Add proper initialization in dict2CameraUi |

---

## References

- [Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [libcamera Controls Namespace](https://libcamera.org/api-html/namespacelibcamera_1_1controls.html)
- [Arducam IMX708 Documentation](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/12MP-IMX708/)
- [Jeff Geerling: Camera Module 3 Review](https://www.jeffgeerling.com/blog/2023/raspberry-pis-camera-module-3-adds-autofocus-and-new-sony-sensor)

---

## Appendix: Motion 5.0 libcam_control_item Format

Motion 5.0 accepts autofocus controls via the `libcam_control_item` directive:

```conf
# /etc/motioneye/camera-1.conf
libcam_device camera0
libcam_control_item AfMode=2
libcam_control_item AfRange=0
# Only for manual mode (AfMode=0):
libcam_control_item LensPosition=0.5
```

Multiple `libcam_control_item` lines are supported (one per control).
