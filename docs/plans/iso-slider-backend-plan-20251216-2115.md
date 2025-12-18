# ISO Slider Backend Implementation Plan

**Created:** 2025-12-16 21:15
**Status:** Ready for Implementation
**UI Element:** `#isoSlider` (already added to `_video_device.html`)

---

## Executive Summary

This plan details the backend implementation for the ISO slider control in MotionEye, targeting Raspberry Pi 5 with Pi Camera v3 (IMX708). The implementation follows the established pattern used for brightness and contrast controls, leveraging Motion 5.0's libcamera integration.

---

## Research Findings

### libcamera ISO Control

libcamera does **not** use traditional ISO values directly. Instead, it uses **AnalogueGain** (a multiplier):

| ISO Equivalent | AnalogueGain Value |
|---------------|-------------------|
| 100           | 1.0               |
| 200           | 2.0               |
| 400           | 4.0               |
| 800           | 8.0               |
| 1600          | 16.0 (Pi Camera v3 max analog) |
| 3200          | Uses digital gain  |
| 6400          | Uses digital gain  |

**Key Points:**
- Pi Camera v3 (IMX708) max **analog gain** = 16.0 (equivalent to ~ISO 1600)
- Beyond ISO 1600, libcamera applies **digital gain** automatically
- The `AnalogueGain` control accepts a float multiplier (1.0 = ISO 100)
- Digital gain cannot be set directly by the user in libcamera

**Sources:**
- [Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [libcamera Controls Reference](https://libcamera.org/api-html/namespacelibcamera_1_1controls.html)
- [Raspberry Pi Forums - Gain Discussion](https://forums.raspberrypi.com/viewtopic.php?t=346873)

### Motion 5.0 Integration

Motion already supports `AnalogueGain` via `libcam_params`:
```
libcam_params AnalogueGain=4.0
```

The existing `libcam.cpp:381-382` shows the implementation:
```cpp
if (pname == "AnalogueGain") {
    controls.set(controls::AnalogueGain, mtof(pvalue));
}
```

---

## Implementation Architecture

### Option A: Use Existing `libcam_params` (Minimal Changes)
Pass ISO as `AnalogueGain=X.X` through `libcam_params`.

**Pros:** No Motion changes required
**Cons:** No hot-reload support, requires daemon restart

### Option B: Add Dedicated `libcam_iso` Parameter (Recommended)
Add a new parameter following the brightness/contrast pattern with hot-reload support.

**Pros:** Hot-reload support, consistent UX with brightness/contrast
**Cons:** Requires changes to both Motion and MotionEye

---

## Recommended Implementation: Option B

### Phase 1: Motion Changes (Local Motion Repo)

#### 1.1 Add `libcam_iso` to Parameter Structures

**File:** `/Users/tshuey/Documents/GitHub/motion/src/parm_structs.hpp`

Add after line 141 (`libcam_contrast`):
```cpp
float           libcam_iso;  // ISO equivalent (100-6400), converted to AnalogueGain
```

#### 1.2 Add Configuration Parameter

**File:** `/Users/tshuey/Documents/GitHub/motion/src/conf.hpp`

Add reference alias (after `libcam_contrast` around line 157):
```cpp
float&          libcam_iso              = parm_cam.libcam_iso;
```

Add edit function declaration (after `edit_libcam_contrast` around line 424):
```cpp
void edit_libcam_iso(std::string &parm, enum PARM_ACT pact);
```

#### 1.3 Implement Configuration Handling

**File:** `/Users/tshuey/Documents/GitHub/motion/src/conf.cpp`

Add to `config_parms[]` array:
```cpp
{"libcam_iso",          PARM_TYP_INT,  PARM_CAT_02,  PARM_LEVEL_LIMITED, true},
```

Implement `edit_libcam_iso()`:
```cpp
void cls_config::edit_libcam_iso(std::string &parm, enum PARM_ACT pact)
{
    int parm_in;
    if (pact == PARM_ACT_DFLT) {
        libcam_iso = 100;  // Default: minimum ISO
    } else if (pact == PARM_ACT_SET) {
        parm_in = atoi(parm.c_str());
        if ((parm_in < 100) || (parm_in > 6400)) {
            MOTION_LOG(NTC, TYPE_ALL, NO_ERRNO, _("Invalid libcam_iso %d"), parm_in);
        } else {
            libcam_iso = parm_in;
        }
    } else if (pact == PARM_ACT_GET) {
        parm = std::to_string(libcam_iso);
    }
    return;
}
```

#### 1.4 Update libcam Hot-Reload Support

**File:** `/Users/tshuey/Documents/GitHub/motion/src/libcam.hpp`

Update `ctx_pending_controls` struct:
```cpp
struct ctx_pending_controls {
    float brightness = 0.0f;
    float contrast = 1.0f;
    float iso = 100.0f;  // ISO 100-6400
    std::atomic<bool> dirty{false};
};
```

Add method declaration in `cls_libcam`:
```cpp
void set_iso(float value);
```

**File:** `/Users/tshuey/Documents/GitHub/motion/src/libcam.cpp`

Add conversion helper (near top of file):
```cpp
/* Convert ISO value (100-6400) to AnalogueGain multiplier */
static float iso_to_gain(float iso) {
    return iso / 100.0f;  // ISO 100 = gain 1.0, ISO 800 = gain 8.0
}
```

Update `req_add()` to include ISO:
```cpp
int cls_libcam::req_add(Request *request)
{
    int retcd;

    if (pending_ctrls.dirty.load()) {
        ControlList &req_controls = request->controls();
        req_controls.set(controls::Brightness, pending_ctrls.brightness);
        req_controls.set(controls::Contrast, pending_ctrls.contrast);
        req_controls.set(controls::AnalogueGain, iso_to_gain(pending_ctrls.iso));
        pending_ctrls.dirty.store(false);
        MOTION_LOG(DBG, TYPE_VIDEO, NO_ERRNO
            , "Applied controls: brightness=%.2f, contrast=%.2f, iso=%.0f (gain=%.2f)"
            , pending_ctrls.brightness, pending_ctrls.contrast
            , pending_ctrls.iso, iso_to_gain(pending_ctrls.iso));
    }

    retcd = camera->queueRequest(request);
    return retcd;
}
```

Add `set_iso()` method:
```cpp
void cls_libcam::set_iso(float value)
{
    #ifdef HAVE_LIBCAM
        pending_ctrls.iso = value;
        pending_ctrls.dirty.store(true);
        MOTION_LOG(DBG, TYPE_VIDEO, NO_ERRNO
            , "Hot-reload: ISO set to %.0f (gain=%.2f)", value, iso_to_gain(value));
    #else
        (void)value;
    #endif
}
```

Update initial config application (in `config_controls()`):
```cpp
controls.set(controls::Brightness, cam->cfg->parm_cam.libcam_brightness);
controls.set(controls::Contrast, cam->cfg->parm_cam.libcam_contrast);
controls.set(controls::AnalogueGain, iso_to_gain(cam->cfg->parm_cam.libcam_iso));
```

---

### Phase 2: MotionEye Changes

#### 2.1 Update Constants

**File:** `motioneye/config/camera/constants.py`

Add to `USED_MOTION_OPTIONS`:
```python
'libcam_iso',
```

Add to `HOT_RELOAD_PARAMS`:
```python
'libcam_iso',
```

#### 2.2 Update Defaults

**File:** `motioneye/config/defaults.py`

Add after `libcam_contrast` default (around line 87):
```python
data.setdefault('libcam_iso', 100)  # Minimum ISO, least noise
```

#### 2.3 Update UI-to-Dict Converter

**File:** `motioneye/config/camera/converters.py`

In `motion_camera_ui_to_dict()`, add after contrast handling (around line 423):
```python
# ISO control (converts to AnalogueGain in Motion)
data['libcam_iso'] = int(ui.get('iso', 100))
```

#### 2.4 Update Dict-to-UI Converter

**File:** `motioneye/config/camera/converters.py`

In `motion_camera_dict_to_ui()`, add after contrast (around line 991):
```python
ui['iso'] = int(data.get('libcam_iso', 100))
```

#### 2.5 Update JavaScript - Gather Config

**File:** `motioneye/static/js/main.js`

In `cameraUi2Dict()` (around line 2069), add:
```javascript
'iso': parseInt($('#isoSlider').val()) || 100,
```

#### 2.6 Update JavaScript - Apply Config

**File:** `motioneye/static/js/main.js`

In `dict2CameraUi()` (around line 2391), add:
```javascript
$('#isoSlider').val(dict['iso'] != null ? dict['iso'] : 100);
markHideIfNull(dict['proto'] !== 'libcamera', 'isoSlider');
```

#### 2.7 Add Hot-Reload Support

**File:** `motioneye/static/js/main.js`

Update `initHotReloadSliders()` function (around line 5770):
```javascript
var paramMap = {
    'brightnessSlider': 'libcam_brightness',
    'contrastSlider': 'libcam_contrast',
    'isoSlider': 'libcam_iso'
};
```

#### 2.8 Update HTML Tooltip

**File:** `motioneye/templates/partials/settings/_video_device.html`

Update the ISO slider tooltip (line 97) to remove "Backend wiring pending":
```html
<td><span class="help-mark" data-i18n-title="Camera ISO sensitivity: 100 (low noise, bright conditions) to 6400 (high noise, low light). Higher values allow shooting in darker environments but increase image noise." title="Camera ISO sensitivity: 100 (low noise, bright conditions) to 6400 (high noise, low light). Higher values allow shooting in darker environments but increase image noise.">?</span></td>
```

Add `hot-reload` class to the slider input:
```html
<input type="text" class="range styled device camera-config hot-reload" id="isoSlider">
```

---

## Testing Plan

### Unit Tests
1. Verify ISO-to-gain conversion: `iso_to_gain(100) == 1.0`, `iso_to_gain(800) == 8.0`
2. Verify config parsing accepts values 100-6400
3. Verify out-of-range values are rejected

### Integration Tests (on Pi 5)
1. Set ISO via UI, verify Motion receives correct `libcam_iso` value
2. Verify hot-reload: Change ISO, confirm immediate effect without restart
3. Verify persistence: Set ISO, restart MotionEye, confirm value retained
4. Verify visual effect: ISO 100 vs 6400 shows visible difference

### Edge Cases
1. ISO slider hidden for non-libcamera devices
2. Value clamping at boundaries (100, 6400)
3. Concurrent changes with brightness/contrast

---

## File Change Summary

### Motion Repository (`/Users/tshuey/Documents/GitHub/motion/`)
| File | Changes |
|------|---------|
| `src/parm_structs.hpp` | Add `libcam_iso` field |
| `src/conf.hpp` | Add reference alias + edit function declaration |
| `src/conf.cpp` | Add parameter definition + edit function implementation |
| `src/libcam.hpp` | Add `iso` to pending_ctrls + `set_iso()` declaration |
| `src/libcam.cpp` | Add `iso_to_gain()`, update `req_add()`, add `set_iso()` |

### MotionEye Repository (`/Users/tshuey/Documents/GitHub/motioneye/`)
| File | Changes |
|------|---------|
| `motioneye/config/camera/constants.py` | Add to USED_MOTION_OPTIONS + HOT_RELOAD_PARAMS |
| `motioneye/config/defaults.py` | Add default value |
| `motioneye/config/camera/converters.py` | Add UI-to-dict + dict-to-UI conversion |
| `motioneye/static/js/main.js` | Add gather/apply + hot-reload handler |
| `motioneye/templates/partials/settings/_video_device.html` | Update tooltip, add hot-reload class |

---

## Deployment Order

1. **Motion first:** Build and install updated Motion on Pi 5
2. **MotionEye second:** Deploy MotionEye changes
3. **Test:** Verify end-to-end functionality

---

## Rollback Plan

If issues arise:
1. Motion: Revert to previous build (ISO parameter will be ignored)
2. MotionEye: UI slider will be non-functional but won't break other features
3. Both changes are additive; existing functionality is preserved

---

## Future Considerations

- **Auto-ISO Mode:** Could add toggle for automatic gain control (libcamera's default AeEnable)
- **Exposure Time:** Similar pattern could add shutter speed control
- **Gain Limits:** Could expose min/max analog gain as advanced settings
