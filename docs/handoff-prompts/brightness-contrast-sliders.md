# MotionEye UI: Add Brightness/Contrast Sliders

## Context

The Motion daemon has been updated with hot-reloadable `libcam_brightness` and `libcam_contrast` parameters. These allow real-time adjustment of Pi Camera Module v3 brightness and contrast **without restarting the daemon or interrupting the video stream**.

**Motion Implementation Reference**: `/Users/tshuey/Documents/GitHub/motion/doc/plans/Hot-Brightness-Contrast-Hot-Adjustments.md`

## Your Task

Add brightness and contrast sliders to the MotionEye UI that leverage Motion's new hot-reload capability.

---

## Requirements

### 1. UI Placement
**Location**: Video Device section, immediately after "Frame Rate"

**Visual Layout**:
```
┌─────────────────────────────────────┐
│ Video Device                        │
├─────────────────────────────────────┤
│ Camera                 [Dropdown]   │
│ Resolution             [Dropdown]   │
│ Frame Rate             [Dropdown]   │
│ Brightness             [Slider]     │  ← NEW
│ Contrast               [Slider]     │  ← NEW
└─────────────────────────────────────┘
```

### 2. Slider Specifications

**Brightness Slider:**
- Label: "Brightness"
- Range: -1.0 to 1.0
- Default: 0.0 (neutral)
- Step: 0.1
- Display format: Show value as decimal (e.g., "0.3", "-0.5")
- Apply on: `mouseup` / `touchend` (slider release only, not during drag)

**Contrast Slider:**
- Label: "Contrast"
- Range: 0.0 to 32.0
- Default: 1.0 (neutral)
- Step: 0.1
- Display format: Show value as decimal (e.g., "1.5", "2.0")
- Apply on: `mouseup` / `touchend` (slider release only, not during drag)

### 3. Behavior Requirements

**Update Trigger:**
- **Do NOT** update on every slider movement (no continuous updates)
- **ONLY** update when user releases the slider (mouseup/touchend)
- This minimizes API calls and prevents spamming Motion with updates during drag

**API Integration:**
```javascript
// When slider is released:
PUT /config/<camera_id>/set/
{
  "libcam_brightness": "0.3",  // or current slider value
  "libcam_contrast": "1.5"     // or current slider value
}
```

**Visual Feedback:**
- Show current value next to slider during drag (live preview)
- After release, brief indicator that value was applied (e.g., checkmark, "Applied" text)
- No page reload or camera restart required
- Stream should remain visible and uninterrupted

**Error Handling:**
- If API call fails, revert slider to previous value
- Show error message: "Failed to update [brightness/contrast]"
- Log error to browser console with details

### 4. Visibility Conditions

**Show sliders ONLY when:**
- Camera uses libcamera (Pi Camera Module)
- Motion version ≥ 5.0.0 (has hot-reload support)

**Hide sliders when:**
- Camera uses V4L2 (USB cameras)
- Camera is network camera (netcam)
- Motion version < 5.0.0

**Detection Method:**
```javascript
// Check camera type from config
if (config.videoDevice && config.videoDevice.startsWith('/dev/video')) {
  // V4L2 camera - hide sliders
} else if (config.netcamUrl) {
  // Network camera - hide sliders
} else {
  // Assume libcamera - show sliders
}

// Check Motion version (if available from API)
if (motionVersion >= '5.0.0') {
  // Show sliders
}
```

### 5. Configuration Persistence

**Save to Config:**
- When slider is released and API call succeeds, update should persist in Motion's config file
- MotionEye should read these values on page load and set slider positions accordingly
- Values should survive MotionEye restart

**Initial Load:**
```javascript
// On page load, fetch current values from Motion config
GET /config/<camera_id>/list
// Response includes:
// {
//   "libcam_brightness": "0.0",
//   "libcam_contrast": "1.0",
//   ...
// }
// Set slider positions to these values
```

---

## Implementation Guide

### Step 1: UI Template (HTML/Jinja2)

Add slider controls to the camera configuration template:

```html
<!-- In camera config template, after Frame Rate -->
{% if camera.device_type == 'libcam' %}
<div class="form-group brightness-slider">
  <label for="brightness">Brightness</label>
  <div class="slider-container">
    <input type="range"
           id="brightness"
           class="slider"
           min="-1.0"
           max="1.0"
           step="0.1"
           value="{{ camera.libcam_brightness|default('0.0') }}">
    <span class="slider-value">{{ camera.libcam_brightness|default('0.0') }}</span>
  </div>
</div>

<div class="form-group contrast-slider">
  <label for="contrast">Contrast</label>
  <div class="slider-container">
    <input type="range"
           id="contrast"
           class="slider"
           min="0.0"
           max="32.0"
           step="0.1"
           value="{{ camera.libcam_contrast|default('1.0') }}">
    <span class="slider-value">{{ camera.libcam_contrast|default('1.0') }}</span>
  </div>
</div>
{% endif %}
```

### Step 2: JavaScript Event Handlers

Attach mouseup/touchend handlers to sliders:

```javascript
// camera.js or appropriate UI module

function initBrightnessContrastSliders() {
  const brightnessSlider = document.getElementById('brightness');
  const contrastSlider = document.getElementById('contrast');

  if (!brightnessSlider || !contrastSlider) return;

  // Update displayed value during drag (live preview)
  brightnessSlider.addEventListener('input', function() {
    const valueDisplay = this.parentElement.querySelector('.slider-value');
    valueDisplay.textContent = this.value;
  });

  contrastSlider.addEventListener('input', function() {
    const valueDisplay = this.parentElement.querySelector('.slider-value');
    valueDisplay.textContent = this.value;
  });

  // Apply changes on slider release
  brightnessSlider.addEventListener('mouseup', function() {
    applyLibcamControl('libcam_brightness', this.value, this);
  });
  brightnessSlider.addEventListener('touchend', function() {
    applyLibcamControl('libcam_brightness', this.value, this);
  });

  contrastSlider.addEventListener('mouseup', function() {
    applyLibcamControl('libcam_contrast', this.value, this);
  });
  contrastSlider.addEventListener('touchend', function() {
    applyLibcamControl('libcam_contrast', this.value, this);
  });
}

function applyLibcamControl(paramName, value, sliderElement) {
  const cameraId = getCurrentCameraId(); // Your existing function
  const previousValue = sliderElement.dataset.previousValue || value;

  // Store current value in case we need to revert
  sliderElement.dataset.previousValue = value;

  // Show applying indicator
  showIndicator(sliderElement, 'applying');

  // Use Motion's hot-reload API
  const url = `/config/${cameraId}/set?${paramName}=${value}`;

  fetch(url, {
    method: 'GET',
    headers: {
      'X-Requested-With': 'XMLHttpRequest'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'ok' && data.hot_reload === true) {
      // Success - show checkmark briefly
      showIndicator(sliderElement, 'success');
      console.log(`Applied ${paramName}=${value}`);

      // Update MotionEye's config model
      updateCameraConfig(cameraId, paramName, value);
    } else {
      throw new Error(data.error || 'Hot reload failed');
    }
  })
  .catch(error => {
    console.error(`Failed to apply ${paramName}:`, error);

    // Revert slider to previous value
    sliderElement.value = previousValue;
    sliderElement.parentElement.querySelector('.slider-value').textContent = previousValue;

    // Show error indicator
    showIndicator(sliderElement, 'error');
    alert(`Failed to update ${paramName}: ${error.message}`);
  });
}

function showIndicator(element, type) {
  // Add visual feedback (checkmark, spinner, error icon, etc.)
  // Implementation depends on your UI framework
  const container = element.parentElement;
  const indicator = container.querySelector('.status-indicator') ||
                    document.createElement('span');
  indicator.className = 'status-indicator';

  if (type === 'applying') {
    indicator.innerHTML = '⏳'; // or spinner
  } else if (type === 'success') {
    indicator.innerHTML = '✓';
    setTimeout(() => indicator.innerHTML = '', 2000);
  } else if (type === 'error') {
    indicator.innerHTML = '✗';
    setTimeout(() => indicator.innerHTML = '', 3000);
  }

  if (!container.contains(indicator)) {
    container.appendChild(indicator);
  }
}

function updateCameraConfig(cameraId, paramName, value) {
  // Update MotionEye's internal config model
  // This ensures persistence across page reloads
  // Implementation depends on your config management

  const configUpdate = {};
  configUpdate[paramName] = value;

  // POST to MotionEye's config endpoint
  fetch(`/config/${cameraId}/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(configUpdate)
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initBrightnessContrastSliders);
```

### Step 3: Backend Integration (Python)

Update MotionEye backend to handle libcam_brightness and libcam_contrast:

```python
# In motioneye/config.py or camera config handler

def motion_camera_dict_to_ui(motion_dict):
    """Convert Motion config to UI-friendly format"""
    ui_dict = {
        # ... existing conversions ...
    }

    # Add libcam controls if present
    if 'libcam_brightness' in motion_dict:
        ui_dict['libcam_brightness'] = float(motion_dict['libcam_brightness'])

    if 'libcam_contrast' in motion_dict:
        ui_dict['libcam_contrast'] = float(motion_dict['libcam_contrast'])

    return ui_dict

def motion_camera_ui_to_dict(ui_dict):
    """Convert UI format to Motion config"""
    motion_dict = {
        # ... existing conversions ...
    }

    # Add libcam controls if present
    if 'libcam_brightness' in ui_dict:
        motion_dict['libcam_brightness'] = str(ui_dict['libcam_brightness'])

    if 'libcam_contrast' in ui_dict:
        motion_dict['libcam_contrast'] = str(ui_dict['libcam_contrast'])

    return motion_dict
```

### Step 4: CSS Styling

Add styles for the sliders:

```css
/* In camera.css or main stylesheet */

.brightness-slider, .contrast-slider {
  margin: 15px 0;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider {
  flex: 1;
  height: 6px;
  background: #ddd;
  outline: none;
  border-radius: 3px;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  background: #4CAF50;
  border-radius: 50%;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  background: #4CAF50;
  border-radius: 50%;
  cursor: pointer;
  border: none;
}

.slider-value {
  min-width: 50px;
  text-align: right;
  font-family: monospace;
  font-size: 14px;
  color: #333;
}

.status-indicator {
  margin-left: 10px;
  font-size: 18px;
}
```

---

## Testing Checklist

### Functional Testing
- [ ] Sliders appear in Video Device section for libcamera devices
- [ ] Sliders hidden for V4L2/USB cameras
- [ ] Sliders hidden for network cameras
- [ ] Brightness range: -1.0 to 1.0, default 0.0
- [ ] Contrast range: 0.0 to 32.0, default 1.0
- [ ] Value updates during drag (live preview)
- [ ] API call triggers only on mouseup/touchend
- [ ] Video stream does NOT restart when adjusting sliders
- [ ] Success indicator shows after successful update
- [ ] Error indicator shows on failed update
- [ ] Slider reverts to previous value on error

### Integration Testing
- [ ] Initial values loaded from Motion config on page load
- [ ] Values persist across MotionEye restart
- [ ] Multiple cameras: each camera's sliders work independently
- [ ] Touch devices: sliders work with finger drag + release

### Edge Cases
- [ ] Rapid slider adjustments (multiple releases in quick succession)
- [ ] Network disconnection during update
- [ ] Motion daemon restart during slider use
- [ ] Invalid values (should be prevented by slider constraints)

### Performance
- [ ] No API calls during slider drag (only on release)
- [ ] No perceptible latency in video stream
- [ ] CPU usage stable during adjustments

---

## Motion API Reference

**Hot-Reload Endpoint:**
```
GET /config/set?{parameter}={value}
```

**Response Format:**
```json
{
  "status": "ok",
  "parameter": "libcam_brightness",
  "old_value": "0.0",
  "new_value": "0.3",
  "hot_reload": true
}
```

**Error Response:**
```json
{
  "status": "error",
  "parameter": "libcam_brightness",
  "error": "Parameter requires daemon restart",
  "hot_reload": false
}
```

**Config List Endpoint:**
```
GET /config/list
```

Returns all current config values including `libcam_brightness` and `libcam_contrast`.

---

## Success Criteria

When complete, users should be able to:

1. ✅ See brightness and contrast sliders for Pi Camera devices
2. ✅ Drag sliders and see live value preview
3. ✅ Release slider to apply change
4. ✅ Observe **immediate** brightness/contrast change in video stream
5. ✅ **No stream interruption** (no black screen, no reconnection)
6. ✅ Values persist across MotionEye restarts

---

## Additional Notes

- **Performance**: The Motion implementation uses atomic operations with minimal CPU overhead (~1-2 nanoseconds per frame). Slider updates are safe to perform frequently.
- **Thread Safety**: Motion handles thread synchronization internally via atomic dirty flags. MotionEye just needs to call the API endpoint.
- **Compatibility**: Motion 5.0.0+ required. Consider adding version check in MotionEye to hide sliders on older Motion versions.

---

## Questions?

Refer to the full Motion implementation details at:
`/Users/tshuey/Documents/GitHub/motion/doc/plans/Hot-Brightness-Contrast-Hot-Adjustments.md`

This document includes:
- Technical design decisions
- Thread safety implementation
- API compatibility notes (libcamera 0.5.2)
- CPU impact analysis
- Testing procedures for Motion daemon

Good luck with the MotionEye UI implementation! 🚀
