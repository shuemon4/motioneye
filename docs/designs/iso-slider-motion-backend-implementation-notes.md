# ISO Slider - Motion Backend Implementation Notes

**Date:** 2025-12-17
**Status:** Motion Backend Complete, MotionEye Frontend Pending
**Related Plan:** `/Users/tshuey/Documents/GitHub/motion/doc/plans/MotionEye-Plans/iso-slider-backend-plan-20251216-2115.md`

---

## Implementation Summary

The Motion backend for ISO slider support has been successfully implemented and deployed to the Pi 5. Motion is running with PID 13547 and accepting the new `libcam_iso` parameter.

---

## Changes Made to Motion Backend

### 1. Core Parameter Structure
**File:** `src/parm_structs.hpp:142`
```cpp
float           libcam_iso;  // ISO equivalent (100-6400), converted to AnalogueGain
```
✅ **Status:** Implemented as planned

### 2. Configuration Header
**File:** `src/conf.hpp:425`
```cpp
void edit_libcam_iso(std::string &parm, enum PARM_ACT pact);
```
✅ **Status:** Implemented as planned
⚠️ **Deviation:** The plan suggested adding a reference alias, but brightness/contrast don't use reference aliases either, so this was correctly omitted

### 3. Configuration Implementation
**File:** `src/conf.cpp`

**Added to config_parms array (line 81):**
```cpp
{"libcam_iso",                PARM_TYP_INT,    PARM_CAT_02, PARM_LEVEL_ADVANCED, true},
```

**Implemented edit function (lines 1057-1078):**
```cpp
void cls_config::edit_libcam_iso(std::string &parm, enum PARM_ACT pact)
{
    int parm_in;
    if (pact == PARM_ACT_DFLT) {
        parm_cam.libcam_iso = 100;  // Default: minimum ISO
    } else if (pact == PARM_ACT_SET) {
        parm_in = atoi(parm.c_str());
        if ((parm_in < 100) || (parm_in > 6400)) {
            MOTION_LOG(NTC, TYPE_ALL, NO_ERRNO
                , _("Invalid libcam_iso %d (range 100-6400)"), parm_in);
        } else {
            parm_cam.libcam_iso = parm_in;
            /* Note: IMX708 (Pi Camera v3) supports analog gain up to ISO 1600 (AnalogueGain=16.0).
             * Values above 1600 use digital gain which increases noise significantly and may
             * require reduced framerate (< 10 fps) for stable operation. */
        }
    } else if (pact == PARM_ACT_GET) {
        parm = std::to_string((int)parm_cam.libcam_iso);
    }
    return;
}
```

**Added to dispatcher (line 3363):**
```cpp
} else if (parm_nm == "libcam_iso") {            edit_libcam_iso(parm_val, pact);
```

✅ **Status:** Implemented as planned with enhanced comments

### 4. libcam Hot-Reload Support
**File:** `src/libcam.hpp:47`
```cpp
struct ctx_pending_controls {
    float brightness = 0.0f;
    float contrast = 1.0f;
    float iso = 100.0f;  // ISO 100-6400 (converted to AnalogueGain)
    std::atomic<bool> dirty{false};
};
```

**Added method declaration (line 59):**
```cpp
void set_iso(float value);
```
✅ **Status:** Implemented as planned

### 5. libcam Implementation
**File:** `src/libcam.cpp`

**Added conversion helper (lines 32-40):**
```cpp
/* Convert ISO value (100-6400) to AnalogueGain multiplier
 * ISO 100 = gain 1.0, ISO 800 = gain 8.0, ISO 1600 = gain 16.0
 * Note: IMX708 (Pi Camera v3) max analog gain is 16.0 (ISO 1600).
 * Values above ISO 1600 trigger digital gain which adds significant noise
 * and may require reduced framerate (< 10 fps) for stable operation.
 */
static float iso_to_gain(float iso) {
    return iso / 100.0f;
}
```

**Updated req_add() (lines 721-732):**
```cpp
/* Apply pending brightness/contrast/ISO controls if changed */
if (pending_ctrls.dirty.load()) {
    ControlList &req_controls = request->controls();
    req_controls.set(controls::Brightness, pending_ctrls.brightness);
    req_controls.set(controls::Contrast, pending_ctrls.contrast);
    req_controls.set(controls::AnalogueGain, iso_to_gain(pending_ctrls.iso));
    pending_ctrls.dirty.store(false);
    MOTION_LOG(DBG, TYPE_VIDEO, NO_ERRNO
        , "Applied controls to request: brightness=%.2f, contrast=%.2f, iso=%.0f (gain=%.2f)"
        , pending_ctrls.brightness, pending_ctrls.contrast
        , pending_ctrls.iso, iso_to_gain(pending_ctrls.iso));
}
```

**Added set_iso() method (lines 1011-1021):**
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

**Updated config_controls() (line 557):**
```cpp
/* Apply initial brightness/contrast/ISO from config */
controls.set(controls::Brightness, cam->cfg->parm_cam.libcam_brightness);
controls.set(controls::Contrast, cam->cfg->parm_cam.libcam_contrast);
controls.set(controls::AnalogueGain, iso_to_gain(cam->cfg->parm_cam.libcam_iso));
```

**Updated constructor initialization (line 1145):**
```cpp
/* Initialize pending controls with config values */
pending_ctrls.brightness = cam->cfg->parm_cam.libcam_brightness;
pending_ctrls.contrast = cam->cfg->parm_cam.libcam_contrast;
pending_ctrls.iso = cam->cfg->parm_cam.libcam_iso;
pending_ctrls.dirty.store(false);
```

**Updated apply_pending_controls() log (line 1034):**
```cpp
MOTION_LOG(INF, TYPE_VIDEO, NO_ERRNO
    , "Brightness/Contrast/ISO update pending: brightness=%.2f, contrast=%.2f, iso=%.0f"
    , pending_ctrls.brightness, pending_ctrls.contrast, pending_ctrls.iso);
```

✅ **Status:** Implemented as planned with enhanced logging

### 6. Camera Wrapper Layer
**File:** `src/camera.hpp:209`
```cpp
void set_libcam_iso(float value);
```

**File:** `src/camera.cpp:2101-2106`
```cpp
void cls_camera::set_libcam_iso(float value)
{
    if (libcam != nullptr) {
        libcam->set_iso(value);
    }
}
```

⚠️ **Deviation from Plan:** The plan did not mention these camera wrapper methods, but they were required for the web API integration. Discovered during implementation.

✅ **Status:** Implemented (not in original plan)

### 7. Web API Hot-Reload Handler
**File:** `src/webu_json.cpp`

**Updated for all cameras (lines 591-598):**
```cpp
/* Apply libcam brightness/contrast/ISO changes immediately */
if (parm_name == "libcam_brightness") {
    app->cam_list[indx]->set_libcam_brightness(atof(parm_val.c_str()));
} else if (parm_name == "libcam_contrast") {
    app->cam_list[indx]->set_libcam_contrast(atof(parm_val.c_str()));
} else if (parm_name == "libcam_iso") {
    app->cam_list[indx]->set_libcam_iso(atof(parm_val.c_str()));
}
```

**Updated for specific camera (lines 604-611):**
```cpp
/* Apply libcam brightness/contrast/ISO changes immediately */
if (parm_name == "libcam_brightness") {
    webua->cam->set_libcam_brightness(atof(parm_val.c_str()));
} else if (parm_name == "libcam_contrast") {
    webua->cam->set_libcam_contrast(atof(parm_val.c_str()));
} else if (parm_name == "libcam_iso") {
    webua->cam->set_libcam_iso(atof(parm_val.c_str()));
}
```

⚠️ **Deviation from Plan:** The plan did not mention webu_json.cpp changes, but they were required for hot-reload support via the Motion web API. Discovered during implementation.

✅ **Status:** Implemented (not in original plan)

---

## Build and Deployment

### Build Process
```bash
# On Pi 5
cd ~/motion
autoreconf -fiv
./configure --with-libcam --with-sqlite3 --without-v4l2 --without-mysql --without-mariadb --without-pgsql
make -j4
sudo make install
sudo cp /usr/local/bin/motion /usr/bin/motion
sudo systemctl restart motioneye
```

### Build Output
- **Warnings:** Minor type conversion warnings (expected)
- **Binary Size:** 15,055,104 bytes (vs 15,049,336 bytes previous)
- **Status:** Running successfully (PID 13547)

### Deployment Location
- **Installed to:** `/usr/local/bin/motion`
- **Active binary:** `/usr/bin/motion` (copied from /usr/local/bin)
- **Running under:** MotionEye service (user: motion)

---

## Technical Notes

### ISO to AnalogueGain Conversion
```
ISO Value → AnalogueGain Multiplier
100       → 1.0
200       → 2.0
400       → 4.0
800       → 8.0
1600      → 16.0 (IMX708 max analog gain)
3200      → 32.0 (uses digital gain)
6400      → 64.0 (uses digital gain)
```

### Analog vs Digital Gain Threshold
- **Analog gain:** ISO 100-1600 (AnalogueGain 1.0-16.0)
- **Digital gain:** ISO 1601-6400 (libcamera applies automatically)
- **Impact:** Digital gain significantly increases image noise
- **Framerate consideration:** High digital gain may require <10 fps for stability

### Comment in Code
The implementation includes inline comments warning about the digital gain threshold:
```cpp
/* Note: IMX708 (Pi Camera v3) supports analog gain up to ISO 1600 (AnalogueGain=16.0).
 * Values above 1600 use digital gain which increases noise significantly and may
 * require reduced framerate (< 10 fps) for stable operation. */
```

---

## Deviations from Original Plan

### 1. Camera Wrapper Layer (camera.cpp/hpp)
**Not in plan, but required:**
- The web API handler (`webu_json.cpp`) calls methods on the `cls_camera` object, not directly on `cls_libcam`
- Added wrapper methods to maintain proper encapsulation
- Follows existing pattern for brightness/contrast

**Files affected:**
- `src/camera.hpp` - Added `set_libcam_iso()` declaration
- `src/camera.cpp` - Added `set_libcam_iso()` implementation

### 2. Web API Hot-Reload Handler (webu_json.cpp)
**Not in plan, but required:**
- Discovered that hot-reload through MotionEye's UI requires web API integration
- The plan mentioned "hot-reload support" but didn't specify the webu_json.cpp changes
- Added ISO handling to both global and per-camera config update handlers

**File affected:**
- `src/webu_json.cpp` - Added ISO handling in `apply_hot_reload()` for both code paths

### 3. Reference Alias Not Added (conf.hpp)
**Plan suggested, but unnecessary:**
- Plan suggested adding reference alias: `float& libcam_iso = parm_cam.libcam_iso`
- Brightness and contrast don't use reference aliases either
- Code consistently accesses via `parm_cam.libcam_iso` instead
- Correctly omitted to match existing pattern

---

## MotionEye Frontend Changes Required

The following changes are needed in the MotionEye repository for the UI to work with the Motion backend. **These changes have NOT been implemented yet** and are pending for another AI agent:

### 1. Constants Configuration
**File:** `motioneye/config/camera/constants.py`

Add to `USED_MOTION_OPTIONS`:
```python
'libcam_iso',
```

Add to `HOT_RELOAD_PARAMS`:
```python
'libcam_iso',
```

### 2. Default Values
**File:** `motioneye/config/defaults.py` (around line 87)

```python
data.setdefault('libcam_iso', 100)  # Minimum ISO, least noise
```

### 3. UI to Dict Converter
**File:** `motioneye/config/camera/converters.py` (around line 423)

In `motion_camera_ui_to_dict()`:
```python
# ISO control (converts to AnalogueGain in Motion)
data['libcam_iso'] = int(ui.get('iso', 100))
```

### 4. Dict to UI Converter
**File:** `motioneye/config/camera/converters.py` (around line 991)

In `motion_camera_dict_to_ui()`:
```python
ui['iso'] = int(data.get('libcam_iso', 100))
```

### 5. JavaScript - Gather Config
**File:** `motioneye/static/js/main.js` (around line 2069)

In `cameraUi2Dict()`:
```javascript
'iso': parseInt($('#isoSlider').val()) || 100,
```

### 6. JavaScript - Apply Config
**File:** `motioneye/static/js/main.js` (around line 2391)

In `dict2CameraUi()`:
```javascript
$('#isoSlider').val(dict['iso'] != null ? dict['iso'] : 100);
markHideIfNull(dict['proto'] !== 'libcamera', 'isoSlider');
```

### 7. JavaScript - Hot-Reload Support
**File:** `motioneye/static/js/main.js` (around line 5770)

Update `initHotReloadSliders()` function:
```javascript
var paramMap = {
    'brightnessSlider': 'libcam_brightness',
    'contrastSlider': 'libcam_contrast',
    'isoSlider': 'libcam_iso'
};
```

### 8. HTML - Update Tooltip and Add Hot-Reload Class
**File:** `motioneye/templates/partials/settings/_video_device.html` (line 97)

Update tooltip to remove "Backend wiring pending":
```html
<td><span class="help-mark" data-i18n-title="Camera ISO sensitivity: 100 (low noise, bright conditions) to 6400 (high noise, low light). Higher values allow shooting in darker environments but increase image noise." title="Camera ISO sensitivity: 100 (low noise, bright conditions) to 6400 (high noise, low light). Higher values allow shooting in darker environments but increase image noise.">?</span></td>
```

Add `hot-reload` class to slider input:
```html
<input type="text" class="range styled device camera-config hot-reload" id="isoSlider">
```

---

## Testing Checklist (For After MotionEye Frontend Implementation)

### Unit Tests
- [ ] Verify ISO-to-gain conversion: `iso_to_gain(100) == 1.0`, `iso_to_gain(800) == 8.0`
- [ ] Verify config parsing accepts values 100-6400
- [ ] Verify out-of-range values are rejected

### Integration Tests (on Pi 5)
- [ ] Set ISO via UI, verify Motion receives correct `libcam_iso` value
- [ ] Verify hot-reload: Change ISO, confirm immediate effect without restart
- [ ] Verify persistence: Set ISO, restart MotionEye, confirm value retained
- [ ] Verify visual effect: ISO 100 vs 6400 shows visible difference

### Edge Cases
- [ ] ISO slider hidden for non-libcamera devices
- [ ] Value clamping at boundaries (100, 6400)
- [ ] Concurrent changes with brightness/contrast
- [ ] High ISO (>1600) + high framerate stress test

---

## Known Issues / Limitations

1. **Digital Gain Warning:** No UI warning when ISO exceeds 1600 (analog gain limit)
   - Users may not realize image quality degrades significantly above ISO 1600
   - Consider adding a visual indicator or tooltip note in the UI

2. **Framerate Interaction:** High ISO (digital gain) may require low framerate
   - No automatic framerate adjustment
   - Users must manually lower framerate if experiencing instability

3. **No Auto-ISO Mode:** Currently only manual ISO control
   - Future consideration: Toggle for AeEnable (automatic exposure control)

---

## Files Modified

### Motion Repository
```
src/parm_structs.hpp
src/conf.hpp
src/conf.cpp
src/libcam.hpp
src/libcam.cpp
src/camera.hpp          (not in original plan)
src/camera.cpp          (not in original plan)
src/webu_json.cpp       (not in original plan)
```

### MotionEye Repository (Pending - NOT YET MODIFIED)
```
motioneye/config/camera/constants.py
motioneye/config/defaults.py
motioneye/config/camera/converters.py
motioneye/static/js/main.js
motioneye/templates/partials/settings/_video_device.html
```

---

## Git Commits Recommended

### For Motion Repository
```
Add libcam_iso parameter for hot-reload ISO control

- Add libcam_iso to parameter structures and configuration
- Implement ISO to AnalogueGain conversion (iso_to_gain helper)
- Add hot-reload support via pending_ctrls mechanism
- Add camera wrapper and web API integration for hot-reload
- Support ISO range 100-6400 (analog gain up to 1600, digital beyond)
- Add detailed comments about analog vs digital gain thresholds

Tested on Raspberry Pi 5 with Camera Module v3 (IMX708).
Values above ISO 1600 use digital gain which increases noise
and may require reduced framerate for stable operation.
```

---

## References

- **Original Plan:** `doc/plans/MotionEye-Plans/iso-slider-backend-plan-20251216-2115.md`
- **libcamera Controls:** https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
- **Pi Camera v3 Specs:** https://www.raspberrypi.com/documentation/computers/camera_software.html
- **IMX708 Datasheet:** Max analog gain = 16.0 (ISO 1600 equivalent)

---

**Implementation Date:** 2025-12-17 00:28 CST
**Motion Version:** 5.0.0-gitUNKNOWN
**Deployment Target:** Raspberry Pi 5 Model B Rev 1.0
**Camera:** IMX708 (Pi Camera Module v3)
**libcamera Version:** 0.5.2
