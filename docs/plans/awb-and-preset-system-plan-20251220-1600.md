# AWB Controls and Camera Preset System Implementation Plan

**Date**: 2025-12-20 16:00
**Status**: Ready for Implementation
**Prerequisites**: Motion 5.0 security integration complete (CSRF token implementation)
**Supersedes**: `camera-preset-system-plan-20251220-1430.md`

---

## Overview

This plan integrates the complete AWB (Auto White Balance) control system from Motion 5.0 with a camera preset management system. It corrects the mapping errors from the original plan and adds the 5 missing AWB parameters.

**Key Corrections from Original Plan:**
1. Added all 6 AWB parameters (was only 1)
2. Fixed AWB mode value mappings to match libcamera
3. Added missing Mode 6 (Cloudy)
4. Corrected function names to match codebase (`cameraUi2Dict`, not `configPanelToDict`)

---

## Part 1: Complete AWB Implementation

### Motion Backend Parameters (All 6)

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `libcam_awb_enable` | bool | true | true/false | Enable/disable auto white balance |
| `libcam_awb_mode` | int | 0 | 0-7 | AWB mode (see table below) |
| `libcam_awb_locked` | bool | false | true/false | Lock current white balance values |
| `libcam_colour_temp` | int | 0 | 0-10000 | Manual colour temperature in Kelvin (0=disabled) |
| `libcam_colour_gain_r` | float | 0.0 | 0.0-8.0 | Manual red channel gain (0=auto) |
| `libcam_colour_gain_b` | float | 0.0 | 0.0-8.0 | Manual blue channel gain (0=auto) |

### CORRECT AWB Mode Values (libcamera native)

| Value | Mode | Description |
|-------|------|-------------|
| 0 | Auto | Automatic white balance |
| 1 | Incandescent | Warm/tungsten lighting (~2700K) |
| 2 | Tungsten | Similar to incandescent |
| 3 | Fluorescent | Cool white fluorescent (~4000K) |
| 4 | Indoor | General indoor lighting |
| 5 | Daylight | Outdoor daylight (~5500K) |
| 6 | Cloudy | Overcast/cloudy (~6500K) |
| 7 | Custom | Use manual ColourGains/ColourTemperature |

---

## Phase 1: AWB Backend Implementation

### 1.1 Register Parameters in Constants

**File:** `motioneye/config/camera/constants.py`

**Location:** After line 30 (after `libcam_iso`)

**Add to `USED_MOTION_OPTIONS` set:**
```python
    'libcam_awb_enable',
    'libcam_awb_mode',
    'libcam_awb_locked',
    'libcam_colour_temp',
    'libcam_colour_gain_r',
    'libcam_colour_gain_b',
```

**Location:** After line 217 (after `libcam_iso` in `HOT_RELOAD_PARAMS`)

**Add to `HOT_RELOAD_PARAMS` set:**
```python
    'libcam_awb_enable',
    'libcam_awb_mode',
    'libcam_awb_locked',
    'libcam_colour_temp',
    'libcam_colour_gain_r',
    'libcam_colour_gain_b',
```

---

### 1.2 Set Default Values

**File:** `motioneye/config/defaults.py`

**Location:** After line 88 (after `libcam_iso` defaults in `_set_default_motion_camera()`)

**Add:**
```python
        # AWB defaults for libcamera (hot-reloadable in Motion 5.0+)
        data.setdefault('libcam_awb_enable', True)   # AWB enabled by default
        data.setdefault('libcam_awb_mode', 0)        # Auto mode
        data.setdefault('libcam_awb_locked', False)  # Not locked
        data.setdefault('libcam_colour_temp', 0)     # 0 = disabled (use AWB)
        data.setdefault('libcam_colour_gain_r', 0.0) # 0 = auto
        data.setdefault('libcam_colour_gain_b', 0.0) # 0 = auto
```

---

### 1.3 Add UI to Motion Converters

**File:** `motioneye/config/camera/converters.py`

#### Part A: UI to Motion Conversion

**Location:** After line 424 (after `libcam_iso` in UI-to-Motion section)

**Add:**
```python
            data['libcam_awb_enable'] = bool(ui.get('awb_enable', True))
            data['libcam_awb_mode'] = int(ui.get('awb_mode', 0))
            data['libcam_awb_locked'] = bool(ui.get('awb_locked', False))
            data['libcam_colour_temp'] = int(ui.get('colour_temp', 0))
            data['libcam_colour_gain_r'] = float(ui.get('colour_gain_r', 0.0))
            data['libcam_colour_gain_b'] = float(ui.get('colour_gain_b', 0.0))
```

#### Part B: Motion to UI Conversion

**Location:** After line 993 (after `iso` in Motion-to-UI section)

**Add:**
```python
        ui['awb_enable'] = bool(data.get('libcam_awb_enable', True))
        ui['awb_mode'] = int(data.get('libcam_awb_mode', 0))
        ui['awb_locked'] = bool(data.get('libcam_awb_locked', False))
        ui['colour_temp'] = int(data.get('libcam_colour_temp', 0))
        ui['colour_gain_r'] = float(data.get('libcam_colour_gain_r', 0.0))
        ui['colour_gain_b'] = float(data.get('libcam_colour_gain_b', 0.0))
```

---

## Phase 2: AWB Frontend Implementation

### 2.1 Add HTML UI Controls

**File:** `motioneye/templates/partials/settings/_video_device.html`

**Location:** After line 110 (after the ISO/Gain slider, before Focus Position)

**Add:**
```html
    <!-- White Balance Section Header -->
    <tr class="settings-item">
        <td colspan="100"><div class="settings-item-separator"></div></td>
    </tr>
    <tr class="settings-item libcam-only">
        <td colspan="3" style="padding-top: 10px;">
            <span style="font-weight: bold; color: #ddd;" data-i18n="White Balance">White Balance</span>
        </td>
    </tr>

    <!-- AWB Enable -->
    <tr class="settings-item libcam-only">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Auto White Balance">Auto White Balance</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <input type="checkbox" class="styled device camera-config hot-reload" id="awbEnableSwitch">
        </td>
        <td><span class="help-mark" data-i18n-title="Enable automatic white balance adjustment. Disable to use manual colour temperature or gains." title="Enable automatic white balance adjustment. Disable to use manual colour temperature or gains.">?</span></td>
    </tr>

    <!-- AWB Mode -->
    <tr class="settings-item libcam-only" depends="awbEnable">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="AWB Mode">AWB Mode</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <select class="styled device camera-config hot-reload" id="awbModeSelect">
                <option value="0" data-i18n="Auto">Auto</option>
                <option value="1" data-i18n="Incandescent">Incandescent</option>
                <option value="2" data-i18n="Tungsten">Tungsten</option>
                <option value="3" data-i18n="Fluorescent">Fluorescent</option>
                <option value="4" data-i18n="Indoor">Indoor</option>
                <option value="5" data-i18n="Daylight">Daylight</option>
                <option value="6" data-i18n="Cloudy">Cloudy</option>
                <option value="7" data-i18n="Custom">Custom</option>
            </select>
        </td>
        <td><span class="help-mark" data-i18n-title="Select white balance mode: Auto adapts to lighting, presets optimize for specific light types (Incandescent ~2700K, Fluorescent ~4000K, Daylight ~5500K, Cloudy ~6500K), Custom uses manual settings." title="Select white balance mode: Auto adapts to lighting, presets optimize for specific light types (Incandescent ~2700K, Fluorescent ~4000K, Daylight ~5500K, Cloudy ~6500K), Custom uses manual settings.">?</span></td>
    </tr>

    <!-- AWB Locked -->
    <tr class="settings-item libcam-only" depends="awbEnable">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Lock White Balance">Lock White Balance</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <input type="checkbox" class="styled device camera-config hot-reload" id="awbLockedSwitch">
        </td>
        <td><span class="help-mark" data-i18n-title="Lock current white balance values to prevent automatic adjustments. Useful for consistent color across scenes." title="Lock current white balance values to prevent automatic adjustments. Useful for consistent color across scenes.">?</span></td>
    </tr>

    <!-- Colour Temperature (for Custom mode or AWB disabled) -->
    <tr class="settings-item libcam-only" depends="!awbEnable||awbMode=7" min="0" max="10000" snap="100" ticks="0|2700|4000|5500|6500|10000" decimals="0">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Colour Temperature (K)">Colour Temperature (K)</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <input type="text" class="range styled device camera-config hot-reload" id="colourTempSlider">
            <div class="slider-note" style="font-size: 0.85em; color: #999; margin-top: 2px;">* 0 = Auto, 2700K = Warm, 6500K = Cool</div>
        </td>
        <td><span class="help-mark" data-i18n-title="Manual colour temperature in Kelvin (0-10000). Set to 0 for automatic. Typical values: 2700K (incandescent), 4000K (fluorescent), 5500K (daylight), 6500K (cloudy). Requires AWB disabled or Custom mode." title="Manual colour temperature in Kelvin (0-10000). Set to 0 for automatic. Typical values: 2700K (incandescent), 4000K (fluorescent), 5500K (daylight), 6500K (cloudy). Requires AWB disabled or Custom mode.">?</span></td>
    </tr>

    <!-- Colour Gain Red -->
    <tr class="settings-item libcam-only" depends="!awbEnable||awbMode=7" min="0" max="8" snap="0" ticks="0|1|2|4|8" decimals="1">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Red Gain">Red Gain</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <input type="text" class="range styled device camera-config hot-reload" id="colourGainRSlider">
        </td>
        <td><span class="help-mark" data-i18n-title="Manual red channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add warmth. Requires AWB disabled or Custom mode." title="Manual red channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add warmth. Requires AWB disabled or Custom mode.">?</span></td>
    </tr>

    <!-- Colour Gain Blue -->
    <tr class="settings-item libcam-only" depends="!awbEnable||awbMode=7" min="0" max="8" snap="0" ticks="0|1|2|4|8" decimals="1">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Blue Gain">Blue Gain</span>
            <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
        </td>
        <td class="settings-item-value">
            <input type="text" class="range styled device camera-config hot-reload" id="colourGainBSlider">
        </td>
        <td><span class="help-mark" data-i18n-title="Manual blue channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add coolness. Requires AWB disabled or Custom mode." title="Manual blue channel gain multiplier (0.0-8.0). Set to 0.0 for automatic. Higher values add coolness. Requires AWB disabled or Custom mode.">?</span></td>
    </tr>
```

---

### 2.2 Add JavaScript Value Reading

**File:** `motioneye/static/js/main.js`

**Location:** After line 2080 (after `iso` in `cameraUi2Dict()` function)

**Add:**
```javascript
        'awb_enable': $('#awbEnableSwitch').is(':checked'),
        'awb_mode': parseInt($('#awbModeSelect').val()) || 0,
        'awb_locked': $('#awbLockedSwitch').is(':checked'),
        'colour_temp': parseInt($('#colourTempSlider').val()) || 0,
        'colour_gain_r': parseFloat($('#colourGainRSlider').val()) || 0.0,
        'colour_gain_b': parseFloat($('#colourGainBSlider').val()) || 0.0,
```

---

### 2.3 Add JavaScript Value Setting

**File:** `motioneye/static/js/main.js`

**Location:** After line 2403 (after ISO slider in dict2CameraUi/dictToConfigPanel)

**Add:**
```javascript
    // AWB Controls
    $('#awbEnableSwitch').prop('checked', dict['awb_enable'] != null ? dict['awb_enable'] : true); markHideIfNull(dict['proto'] !== 'libcamera', 'awbEnableSwitch');
    $('#awbModeSelect').val(dict['awb_mode'] != null ? dict['awb_mode'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'awbModeSelect');
    $('#awbLockedSwitch').prop('checked', dict['awb_locked'] != null ? dict['awb_locked'] : false); markHideIfNull(dict['proto'] !== 'libcamera', 'awbLockedSwitch');
    $('#colourTempSlider').val(dict['colour_temp'] != null ? dict['colour_temp'] : 0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourTempSlider');
    $('#colourGainRSlider').val(dict['colour_gain_r'] != null ? dict['colour_gain_r'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainRSlider');
    $('#colourGainBSlider').val(dict['colour_gain_b'] != null ? dict['colour_gain_b'] : 0.0); markHideIfNull(dict['proto'] !== 'libcamera', 'colourGainBSlider');
```

---

### 2.4 Add Hot-Reload Mappings

**File:** `motioneye/static/js/main.js`

**Location:** After line 5785 (in `applyHotReloadParameter()` function, after `isoSlider` mapping)

**Update the paramMap object:**
```javascript
    var paramMap = {
        'brightnessSlider': 'libcam_brightness',
        'contrastSlider': 'libcam_contrast',
        'isoSlider': 'libcam_iso',
        // AWB Controls
        'awbEnableSwitch': 'libcam_awb_enable',
        'awbModeSelect': 'libcam_awb_mode',
        'awbLockedSwitch': 'libcam_awb_locked',
        'colourTempSlider': 'libcam_colour_temp',
        'colourGainRSlider': 'libcam_colour_gain_r',
        'colourGainBSlider': 'libcam_colour_gain_b'
    };
```

---

### 2.5 Initialize Hot-Reload for New Controls

**File:** `motioneye/static/js/main.js`

**Location:** Where hot-reload event handlers are set up for sliders (around line 5760)

**Ensure the new controls have hot-reload bindings:**
```javascript
    // AWB checkbox and select hot-reload
    $('#awbEnableSwitch, #awbLockedSwitch').on('change', function() {
        applyHotReloadParameter($(this));
    });

    $('#awbModeSelect').on('change', function() {
        applyHotReloadParameter($(this));
    });
```

---

## Phase 3: Preset Storage System

### 3.1 Create Preset Storage Module

**File:** `motioneye/config/presets.py` (NEW FILE)

```python
# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Camera preset storage and management.

Provides functions for saving, loading, and managing camera configuration presets.
Presets are stored per-camera in JSON files at /etc/motioneye/camera-{id}-presets.json
"""

import json
import logging
import os
import re
from datetime import datetime

from motioneye import settings

logger = logging.getLogger(__name__)

# Preset file location
PRESET_DIR = settings.CONF_PATH  # /etc/motioneye/


def _get_preset_file(camera_id):
    """Get the preset file path for a camera."""
    return os.path.join(PRESET_DIR, f'camera-{camera_id}-presets.json')


def _slugify(name):
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug


def _load_preset_file(camera_id):
    """Load presets from file, returning empty structure if not found."""
    filepath = _get_preset_file(camera_id)
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f'Failed to load presets for camera {camera_id}: {e}')

    return {'presets': {}, 'version': 1}


def _save_preset_file(camera_id, data):
    """Save presets to file."""
    filepath = _get_preset_file(camera_id)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f'Failed to save presets for camera {camera_id}: {e}')
        return False


def list_presets(camera_id):
    """List all presets for a camera."""
    data = _load_preset_file(camera_id)
    return [
        {'id': pid, 'name': pdata.get('name', pid), 'modified': pdata.get('modified')}
        for pid, pdata in data.get('presets', {}).items()
    ]


def get_preset(camera_id, preset_id):
    """Get a specific preset by ID."""
    data = _load_preset_file(camera_id)
    return data.get('presets', {}).get(preset_id)


def save_preset(camera_id, name, settings_dict, preset_id=None):
    """
    Save a preset. If preset_id is provided and exists, update it.
    Otherwise create a new preset with a generated ID.

    Returns: (preset_id, created) tuple
    """
    data = _load_preset_file(camera_id)
    now = datetime.utcnow().isoformat() + 'Z'

    if preset_id is None:
        preset_id = _slugify(name)

    # Check if this is a new preset or update
    created = preset_id not in data.get('presets', {})

    if 'presets' not in data:
        data['presets'] = {}

    data['presets'][preset_id] = {
        'name': name,
        'settings': settings_dict,
        'created': data['presets'].get(preset_id, {}).get('created', now),
        'modified': now
    }

    if _save_preset_file(camera_id, data):
        return (preset_id, created)
    return (None, False)


def delete_preset(camera_id, preset_id):
    """Delete a preset by ID. Returns True if deleted."""
    data = _load_preset_file(camera_id)
    if preset_id in data.get('presets', {}):
        del data['presets'][preset_id]
        return _save_preset_file(camera_id, data)
    return False


def rename_preset(camera_id, preset_id, new_name):
    """
    Rename a preset. Updates both the name and the ID (slug).
    Returns: new_preset_id or None if failed
    """
    data = _load_preset_file(camera_id)
    if preset_id not in data.get('presets', {}):
        return None

    new_id = _slugify(new_name)
    if new_id != preset_id and new_id in data['presets']:
        # New ID already exists
        return None

    preset = data['presets'].pop(preset_id)
    preset['name'] = new_name
    preset['modified'] = datetime.utcnow().isoformat() + 'Z'
    data['presets'][new_id] = preset

    if _save_preset_file(camera_id, data):
        return new_id
    return None


def list_all_preset_names():
    """
    List all unique preset names across all cameras.
    Used for global preset discovery.
    """
    all_presets = set()
    try:
        for filename in os.listdir(PRESET_DIR):
            if filename.startswith('camera-') and filename.endswith('-presets.json'):
                filepath = os.path.join(PRESET_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        for pdata in data.get('presets', {}).values():
                            all_presets.add(pdata.get('name', ''))
                except (json.JSONDecodeError, IOError):
                    continue
    except IOError:
        pass

    return sorted(list(all_presets))


def find_preset_by_name(name, exclude_camera_id=None):
    """
    Find a preset by name across all cameras.
    Returns (camera_id, preset_id, preset_data) or None.
    """
    target_slug = _slugify(name)
    try:
        for filename in os.listdir(PRESET_DIR):
            if filename.startswith('camera-') and filename.endswith('-presets.json'):
                # Extract camera ID from filename
                match = re.match(r'camera-(\d+)-presets\.json', filename)
                if not match:
                    continue
                cam_id = int(match.group(1))

                if exclude_camera_id is not None and cam_id == exclude_camera_id:
                    continue

                filepath = os.path.join(PRESET_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        for pid, pdata in data.get('presets', {}).items():
                            if pid == target_slug or _slugify(pdata.get('name', '')) == target_slug:
                                return (cam_id, pid, pdata)
                except (json.JSONDecodeError, IOError):
                    continue
    except IOError:
        pass

    return None
```

---

### 3.2 Preset Settings Schema

Settings included in presets:

```python
PRESET_SETTINGS = [
    # Autofocus (requires restart)
    'autofocus_mode',
    'autofocus_range',
    'lens_position',

    # Frame rate (requires restart)
    'framerate',

    # Hot-reload settings (apply immediately)
    'brightness',
    'contrast',
    'iso',
    'awb_enable',
    'awb_mode',
    'awb_locked',
    'colour_temp',
    'colour_gain_r',
    'colour_gain_b',

    # Extra options
    'extra_options',
]

HOT_RELOAD_PRESET_SETTINGS = [
    'brightness',
    'contrast',
    'iso',
    'awb_enable',
    'awb_mode',
    'awb_locked',
    'colour_temp',
    'colour_gain_r',
    'colour_gain_b',
]
```

---

## Phase 4: Backend API Endpoints

### 4.1 Add Preset Handler Methods

**File:** `motioneye/handlers/config.py`

**Location:** After line 873 (after `hot_reload()` method)

**Add:**
```python
    async def list_presets(self, camera_id):
        """GET /config/{camera_id}/presets/ - List all presets for a camera."""
        from motioneye.config import presets

        camera_id = int(camera_id)
        preset_list = presets.list_presets(camera_id)
        all_names = presets.list_all_preset_names()

        self.finish_json({
            'presets': preset_list,
            'global_names': all_names
        })

    async def save_preset(self, camera_id):
        """POST /config/{camera_id}/presets/save - Save a new preset or update existing."""
        from motioneye.config import presets

        camera_id = int(camera_id)
        data = self.get_json()

        name = data.get('name', '').strip()
        settings_dict = data.get('settings', {})
        preset_id = data.get('preset_id')  # Optional, for updates
        force_overwrite = data.get('force_overwrite', False)

        if not name:
            self.finish_json({'error': 'Preset name is required'}, status_code=400)
            return

        # Check for existing preset with same name
        existing = presets.get_preset(camera_id, presets._slugify(name))
        if existing and not preset_id and not force_overwrite:
            self.finish_json({
                'error': 'exists',
                'message': f'Preset "{name}" already exists',
                'preset_id': presets._slugify(name)
            }, status_code=409)
            return

        result_id, created = presets.save_preset(camera_id, name, settings_dict, preset_id)

        if result_id:
            self.finish_json({
                'preset_id': result_id,
                'created': created
            })
        else:
            self.finish_json({'error': 'Failed to save preset'}, status_code=500)

    async def load_preset(self, camera_id):
        """POST /config/{camera_id}/presets/load - Load a preset."""
        from motioneye.config import presets

        camera_id = int(camera_id)
        data = self.get_json()
        preset_id = data.get('preset_id')
        preset_name = data.get('name')  # Alternative: search by name

        preset_data = None
        source_camera = camera_id

        # Try local camera first
        if preset_id:
            preset_data = presets.get_preset(camera_id, preset_id)

        # If not found and name provided, search globally
        if not preset_data and preset_name:
            result = presets.find_preset_by_name(preset_name)
            if result:
                source_camera, preset_id, preset_data = result

        if not preset_data:
            self.finish_json({'error': 'Preset not found'}, status_code=404)
            return

        self.finish_json({
            'preset_id': preset_id,
            'name': preset_data.get('name'),
            'settings': preset_data.get('settings', {}),
            'source_camera': source_camera
        })

    async def delete_preset(self, camera_id):
        """POST /config/{camera_id}/presets/delete - Delete a preset."""
        from motioneye.config import presets

        camera_id = int(camera_id)
        data = self.get_json()
        preset_id = data.get('preset_id')

        if not preset_id:
            self.finish_json({'error': 'preset_id is required'}, status_code=400)
            return

        if presets.delete_preset(camera_id, preset_id):
            self.finish_json({'deleted': True})
        else:
            self.finish_json({'error': 'Preset not found'}, status_code=404)

    async def rename_preset(self, camera_id):
        """POST /config/{camera_id}/presets/rename - Rename a preset."""
        from motioneye.config import presets

        camera_id = int(camera_id)
        data = self.get_json()
        preset_id = data.get('preset_id')
        new_name = data.get('new_name', '').strip()

        if not preset_id or not new_name:
            self.finish_json({'error': 'preset_id and new_name are required'}, status_code=400)
            return

        new_id = presets.rename_preset(camera_id, preset_id, new_name)

        if new_id:
            self.finish_json({
                'old_id': preset_id,
                'new_id': new_id,
                'new_name': new_name
            })
        else:
            self.finish_json({'error': 'Failed to rename preset'}, status_code=500)
```

---

### 4.2 Add Routes

**File:** `motioneye/server.py`

**Location:** After line 199 (after existing config routes)

**Add:**
```python
    (r'^/config/(?P<camera_id>\d+)/presets/?$', ConfigHandler, {'op': 'list_presets'}),
    (r'^/config/(?P<camera_id>\d+)/presets/save$', ConfigHandler, {'op': 'save_preset'}),
    (r'^/config/(?P<camera_id>\d+)/presets/load$', ConfigHandler, {'op': 'load_preset'}),
    (r'^/config/(?P<camera_id>\d+)/presets/delete$', ConfigHandler, {'op': 'delete_preset'}),
    (r'^/config/(?P<camera_id>\d+)/presets/rename$', ConfigHandler, {'op': 'rename_preset'}),
```

---

### 4.3 Update ConfigHandler Dispatch

**File:** `motioneye/handlers/config.py`

**Location:** In the `get()` and `post()` methods, add dispatch for new operations.

In `async def get()`:
```python
        elif op == 'list_presets':
            return await self.list_presets(camera_id)
```

In `async def post()`:
```python
        elif op == 'save_preset':
            return await self.save_preset(camera_id)
        elif op == 'load_preset':
            return await self.load_preset(camera_id)
        elif op == 'delete_preset':
            return await self.delete_preset(camera_id)
        elif op == 'rename_preset':
            return await self.rename_preset(camera_id)
```

---

## Phase 5: Frontend Preset UI

### 5.1 Add Preset UI Controls to HTML

**File:** `motioneye/templates/partials/settings/_video_device.html`

**Location:** After the Extra Options row (around line 145)

**Add:**
```html
    <!-- Preset Management Section -->
    <tr class="settings-item">
        <td colspan="100"><div class="settings-item-separator"></div></td>
    </tr>
    <tr class="settings-item libcam-only">
        <td class="settings-item-label">
            <span class="settings-item-label" data-i18n="Camera Presets">Camera Presets</span>
        </td>
        <td class="settings-item-value" style="display: flex; gap: 8px; align-items: center;">
            <select class="styled" id="presetSelect" style="flex: 1;">
                <option value="" data-i18n="Select a preset...">Select a preset...</option>
            </select>
            <div class="button small-button" id="loadPresetButton" data-i18n="Load">Load</div>
            <div class="button small-button" id="savePresetButton" data-i18n="Save">Save</div>
            <div class="button small-button" id="managePresetsButton" data-i18n="Manage">Manage</div>
        </td>
        <td><span class="help-mark" data-i18n-title="Save and load camera configuration presets. Hot-reload settings (brightness, contrast, ISO, AWB) apply immediately; other settings stage for review." title="Save and load camera configuration presets. Hot-reload settings (brightness, contrast, ISO, AWB) apply immediately; other settings stage for review.">?</span></td>
    </tr>
```

---

### 5.2 Add Preset Modal Dialogs

**File:** `motioneye/templates/main.html`

**Location:** Before closing `</body>` tag (with other modal dialogs)

**Add:**
```html
<!-- Save Preset Modal -->
<div id="savePresetModal" class="modal-overlay" style="display: none;">
    <div class="modal-dialog">
        <div class="modal-header">
            <span data-i18n="Save Preset">Save Preset</span>
        </div>
        <div class="modal-body">
            <div class="form-group">
                <label data-i18n="Preset Name:">Preset Name:</label>
                <input type="text" id="savePresetNameInput" class="styled" placeholder="My Preset">
            </div>
            <div id="savePresetOverwriteWarning" class="warning-message" style="display: none;">
                <span data-i18n="A preset with this name already exists. Overwrite?">A preset with this name already exists. Overwrite?</span>
            </div>
        </div>
        <div class="modal-buttons">
            <div class="button" id="savePresetConfirmButton" data-i18n="Save">Save</div>
            <div class="button" id="savePresetCancelButton" data-i18n="Cancel">Cancel</div>
        </div>
    </div>
</div>

<!-- Manage Presets Modal -->
<div id="managePresetsModal" class="modal-overlay" style="display: none;">
    <div class="modal-dialog" style="width: 400px;">
        <div class="modal-header">
            <span data-i18n="Manage Presets">Manage Presets</span>
        </div>
        <div class="modal-body">
            <div id="presetList" class="preset-list">
                <!-- Preset items will be inserted here -->
            </div>
            <div id="noPresetsMessage" class="info-message" style="display: none;">
                <span data-i18n="No presets saved yet.">No presets saved yet.</span>
            </div>
        </div>
        <div class="modal-buttons">
            <div class="button" id="managePresetsCloseButton" data-i18n="Close">Close</div>
        </div>
    </div>
</div>
```

---

### 5.3 Add JavaScript Preset Functions

**File:** `motioneye/static/js/main.js`

**Location:** After hot-reload functions (around line 5800)

**Add:**
```javascript
/* Preset Management */

var presetCache = {};

function loadPresetList() {
    var cameraId = $('#cameraSelect').val();
    if (!cameraId) return;

    $.ajax({
        type: 'GET',
        url: '/config/' + cameraId + '/presets/',
        success: function(data) {
            presetCache = {};
            var $select = $('#presetSelect');
            $select.find('option:gt(0)').remove();

            (data.presets || []).forEach(function(preset) {
                presetCache[preset.id] = preset;
                $select.append($('<option>').val(preset.id).text(preset.name));
            });
        },
        error: function() {
            showErrorMessage('Failed to load presets');
        }
    });
}

function gatherPresetSettings() {
    return {
        'autofocus_mode': parseInt($('#autofocusModeSelect').val()) || 2,
        'autofocus_range': parseInt($('#autofocusRangeSelect').val()) || 0,
        'lens_position': parseFloat($('#lensPositionSlider').val()) || 0.0,
        'framerate': parseInt($('#framerateSlider').val()) || 2,
        'brightness': parseFloat($('#brightnessSlider').val()) || 0.0,
        'contrast': parseFloat($('#contrastSlider').val()) || 1.0,
        'iso': Math.round((parseFloat($('#isoSlider').val()) || 1.0) * 100),
        'awb_enable': $('#awbEnableSwitch').is(':checked'),
        'awb_mode': parseInt($('#awbModeSelect').val()) || 0,
        'awb_locked': $('#awbLockedSwitch').is(':checked'),
        'colour_temp': parseInt($('#colourTempSlider').val()) || 0,
        'colour_gain_r': parseFloat($('#colourGainRSlider').val()) || 0.0,
        'colour_gain_b': parseFloat($('#colourGainBSlider').val()) || 0.0,
        'extra_options': $('#extraOptionsEntry').val() || ''
    };
}

function applyPresetSettings(settings) {
    var hotReloadSettings = ['brightness', 'contrast', 'iso', 'awb_enable', 'awb_mode',
                             'awb_locked', 'colour_temp', 'colour_gain_r', 'colour_gain_b'];
    var needsRestart = false;

    // Apply all settings to UI
    if (settings.autofocus_mode !== undefined) {
        $('#autofocusModeSelect').val(settings.autofocus_mode);
        needsRestart = true;
    }
    if (settings.autofocus_range !== undefined) {
        $('#autofocusRangeSelect').val(settings.autofocus_range);
        needsRestart = true;
    }
    if (settings.lens_position !== undefined) {
        $('#lensPositionSlider').val(settings.lens_position);
    }
    if (settings.framerate !== undefined) {
        $('#framerateSlider').val(settings.framerate);
        needsRestart = true;
    }
    if (settings.brightness !== undefined) {
        $('#brightnessSlider').val(settings.brightness);
    }
    if (settings.contrast !== undefined) {
        $('#contrastSlider').val(settings.contrast);
    }
    if (settings.iso !== undefined) {
        $('#isoSlider').val((settings.iso / 100).toFixed(1));
    }
    if (settings.awb_enable !== undefined) {
        $('#awbEnableSwitch').prop('checked', settings.awb_enable);
    }
    if (settings.awb_mode !== undefined) {
        $('#awbModeSelect').val(settings.awb_mode);
    }
    if (settings.awb_locked !== undefined) {
        $('#awbLockedSwitch').prop('checked', settings.awb_locked);
    }
    if (settings.colour_temp !== undefined) {
        $('#colourTempSlider').val(settings.colour_temp);
    }
    if (settings.colour_gain_r !== undefined) {
        $('#colourGainRSlider').val(settings.colour_gain_r);
    }
    if (settings.colour_gain_b !== undefined) {
        $('#colourGainBSlider').val(settings.colour_gain_b);
    }
    if (settings.extra_options !== undefined) {
        $('#extraOptionsEntry').val(settings.extra_options);
        needsRestart = true;
    }

    // Apply hot-reload settings immediately
    hotReloadSettings.forEach(function(key) {
        if (settings[key] !== undefined) {
            var elementId = {
                'brightness': 'brightnessSlider',
                'contrast': 'contrastSlider',
                'iso': 'isoSlider',
                'awb_enable': 'awbEnableSwitch',
                'awb_mode': 'awbModeSelect',
                'awb_locked': 'awbLockedSwitch',
                'colour_temp': 'colourTempSlider',
                'colour_gain_r': 'colourGainRSlider',
                'colour_gain_b': 'colourGainBSlider'
            }[key];

            if (elementId) {
                applyHotReloadParameter($('#' + elementId));
            }
        }
    });

    // Update UI to show changes are pending
    updateConfigUI();

    if (needsRestart) {
        showMessage('Some settings require applying changes to take effect.');
    }
}

function showSavePresetModal() {
    $('#savePresetNameInput').val('');
    $('#savePresetOverwriteWarning').hide();
    $('#savePresetModal').show();
    $('#savePresetNameInput').focus();
}

function hideSavePresetModal() {
    $('#savePresetModal').hide();
}

function savePreset(forceOverwrite) {
    var cameraId = $('#cameraSelect').val();
    var name = $('#savePresetNameInput').val().trim();

    if (!name) {
        showErrorMessage('Please enter a preset name');
        return;
    }

    var settings = gatherPresetSettings();

    $.ajax({
        type: 'POST',
        url: '/config/' + cameraId + '/presets/save',
        contentType: 'application/json',
        data: JSON.stringify({
            name: name,
            settings: settings,
            force_overwrite: forceOverwrite || false
        }),
        success: function(data) {
            hideSavePresetModal();
            loadPresetList();
            showMessage('Preset "' + name + '" saved successfully');
        },
        error: function(xhr) {
            var resp = xhr.responseJSON || {};
            if (resp.error === 'exists') {
                $('#savePresetOverwriteWarning').show();
            } else {
                showErrorMessage(resp.message || 'Failed to save preset');
            }
        }
    });
}

function loadPreset() {
    var cameraId = $('#cameraSelect').val();
    var presetId = $('#presetSelect').val();

    if (!presetId) {
        showErrorMessage('Please select a preset to load');
        return;
    }

    $.ajax({
        type: 'POST',
        url: '/config/' + cameraId + '/presets/load',
        contentType: 'application/json',
        data: JSON.stringify({preset_id: presetId}),
        success: function(data) {
            applyPresetSettings(data.settings);
            showMessage('Preset "' + data.name + '" loaded');
        },
        error: function() {
            showErrorMessage('Failed to load preset');
        }
    });
}

function showManagePresetsModal() {
    var cameraId = $('#cameraSelect').val();

    $.ajax({
        type: 'GET',
        url: '/config/' + cameraId + '/presets/',
        success: function(data) {
            var $list = $('#presetList').empty();
            var presets = data.presets || [];

            if (presets.length === 0) {
                $('#noPresetsMessage').show();
            } else {
                $('#noPresetsMessage').hide();
                presets.forEach(function(preset) {
                    var $row = $('<div class="preset-row">');
                    $row.append($('<span class="preset-name">').text(preset.name));

                    var $actions = $('<div class="preset-actions">');
                    $actions.append($('<div class="button small-button">').text('Rename').click(function() {
                        renamePreset(preset.id, preset.name);
                    }));
                    $actions.append($('<div class="button small-button">').text('Delete').click(function() {
                        deletePreset(preset.id, preset.name);
                    }));
                    $row.append($actions);

                    $list.append($row);
                });
            }

            $('#managePresetsModal').show();
        }
    });
}

function hideManagePresetsModal() {
    $('#managePresetsModal').hide();
}

function renamePreset(presetId, currentName) {
    var newName = prompt('Enter new name for preset:', currentName);
    if (!newName || newName.trim() === currentName) return;

    var cameraId = $('#cameraSelect').val();

    $.ajax({
        type: 'POST',
        url: '/config/' + cameraId + '/presets/rename',
        contentType: 'application/json',
        data: JSON.stringify({
            preset_id: presetId,
            new_name: newName.trim()
        }),
        success: function() {
            showManagePresetsModal(); // Refresh the list
            loadPresetList(); // Refresh dropdown
            showMessage('Preset renamed successfully');
        },
        error: function() {
            showErrorMessage('Failed to rename preset');
        }
    });
}

function deletePreset(presetId, name) {
    if (!confirm('Delete preset "' + name + '"? This cannot be undone.')) return;

    var cameraId = $('#cameraSelect').val();

    $.ajax({
        type: 'POST',
        url: '/config/' + cameraId + '/presets/delete',
        contentType: 'application/json',
        data: JSON.stringify({preset_id: presetId}),
        success: function() {
            showManagePresetsModal(); // Refresh the list
            loadPresetList(); // Refresh dropdown
            showMessage('Preset deleted');
        },
        error: function() {
            showErrorMessage('Failed to delete preset');
        }
    });
}

/* Preset Event Handlers */
$(document).ready(function() {
    $('#loadPresetButton').click(loadPreset);
    $('#savePresetButton').click(showSavePresetModal);
    $('#managePresetsButton').click(showManagePresetsModal);

    $('#savePresetConfirmButton').click(function() {
        var overwrite = $('#savePresetOverwriteWarning').is(':visible');
        savePreset(overwrite);
    });
    $('#savePresetCancelButton').click(hideSavePresetModal);
    $('#managePresetsCloseButton').click(hideManagePresetsModal);

    // Load presets when camera changes
    $('#cameraSelect').on('change', loadPresetList);
});
```

---

### 5.4 Add CSS Styles

**File:** `motioneye/static/css/main.css`

**Location:** After existing modal styles (around line 1600)

**Add:**
```css
/* Preset Management Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-dialog {
    background: #333;
    border-radius: 8px;
    padding: 20px;
    min-width: 300px;
    max-width: 90%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.modal-header {
    font-size: 1.2em;
    font-weight: bold;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #555;
}

.modal-body {
    margin-bottom: 20px;
}

.modal-buttons {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
}

.form-group {
    margin-bottom: 15px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    color: #ccc;
}

.form-group input {
    width: 100%;
    box-sizing: border-box;
}

.warning-message {
    background: #553300;
    border: 1px solid #aa6600;
    color: #ffcc00;
    padding: 10px;
    border-radius: 4px;
    margin-top: 10px;
}

.info-message {
    color: #999;
    text-align: center;
    padding: 20px;
}

.preset-list {
    max-height: 300px;
    overflow-y: auto;
}

.preset-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px;
    border-bottom: 1px solid #444;
}

.preset-row:last-child {
    border-bottom: none;
}

.preset-name {
    flex: 1;
}

.preset-actions {
    display: flex;
    gap: 5px;
}

.button.small-button {
    padding: 4px 8px;
    font-size: 0.85em;
}
```

---

## Implementation Order

### Step 1: AWB Backend (30 min)
1. Add 6 AWB params to `USED_MOTION_OPTIONS` in constants.py
2. Add 6 AWB params to `HOT_RELOAD_PARAMS` in constants.py
3. Add defaults in defaults.py
4. Add converters in converters.py (both directions)

### Step 2: AWB Frontend (45 min)
1. Add HTML controls in _video_device.html
2. Add value reading in cameraUi2Dict()
3. Add value setting in dict2CameraUi()
4. Add hot-reload mappings and event handlers

**Checkpoint:** Test AWB controls work with hot-reload

### Step 3: Preset Backend (1 hour)
1. Create `motioneye/config/presets.py`
2. Add handler methods to config.py
3. Add routes to server.py
4. Update handler dispatch

**Checkpoint:** Test API endpoints with curl

### Step 4: Preset Frontend (1.5 hours)
1. Add preset UI controls to _video_device.html
2. Add modal dialogs to main.html
3. Add JavaScript functions to main.js
4. Add CSS styles

**Checkpoint:** Test full preset workflow

### Step 5: Integration Testing (30 min)
1. Test hybrid load behavior
2. Test overwrite protection
3. Test on Pi 5 with real camera

---

## Files to Modify Summary

| File | Changes |
|------|---------|
| `motioneye/config/camera/constants.py` | Add 6 AWB params to both sets |
| `motioneye/config/defaults.py` | Add 6 AWB default values |
| `motioneye/config/camera/converters.py` | Add AWB UI↔Motion conversions |
| `motioneye/config/presets.py` | **NEW FILE** - Preset storage module |
| `motioneye/handlers/config.py` | Add 5 preset handler methods |
| `motioneye/server.py` | Add 5 preset routes |
| `motioneye/templates/partials/settings/_video_device.html` | Add AWB controls + preset UI |
| `motioneye/templates/main.html` | Add modal dialogs |
| `motioneye/static/js/main.js` | Add AWB + preset JavaScript |
| `motioneye/static/css/main.css` | Add modal/preset styles |

---

## Testing Checklist

### AWB Controls
- [ ] All 6 AWB controls visible for libcamera cameras
- [ ] AWB controls hidden for V4L2/network cameras
- [ ] AWB Mode dropdown shows all 8 modes (0-7) with correct labels
- [ ] Hot-reload works: changes apply instantly without restart
- [ ] Colour temp/gain controls show/hide based on AWB enable state
- [ ] Settings persist across MotionEye restarts

### Preset System
- [ ] Can save current settings as named preset
- [ ] Can load preset with hybrid behavior (hot-reload immediate, others staged)
- [ ] Can rename presets
- [ ] Can delete presets
- [ ] Overwrite protection works (warns before overwriting)
- [ ] Presets saved on one camera can be searched globally

### Pi 5 Deployment
- [ ] Deploy via rsync
- [ ] AWB modes produce expected color shifts
- [ ] Presets save and load correctly
- [ ] Hot-reload performance acceptable

---

## Success Criteria

1. All 6 AWB parameters appear in UI for libcamera cameras
2. All 6 parameters hidden for non-libcamera cameras
3. AWB mode dropdown shows all 8 modes (0-7) with CORRECT libcamera values
4. Colour temperature slider range: 0-10000K
5. Gain sliders range: 0.0-8.0
6. Hot-reload works: changes apply instantly without restart
7. Presets can be saved, loaded, renamed, deleted
8. Hybrid load applies hot-reload settings immediately
9. Settings persist across MotionEye restarts
10. Visual verification: AWB modes produce expected color shifts
