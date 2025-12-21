# Camera Preset System Implementation Plan

**Date**: 2025-12-20 14:30
**Status**: Pending Review
**Prerequisites**: Motion 5.0 security integration complete (CSRF token implementation)

---

## Overview

Add a comprehensive camera preset system to MotionEye that allows users to save, load, rename, and delete camera configuration presets. The system will include AWB (Auto White Balance) as a new hot-reloadable parameter and support hybrid loading behavior where hot-reload settings apply immediately while others stage for review.

## User Requirements

**Preset Contents:**
- AutoFocus Mode (existing)
- AutoFocus Range (existing)
- Frame Rate (existing)
- Brightness (existing hot-reload)
- Contrast (existing hot-reload)
- Gain/ISO (existing hot-reload)
- AWB Mode (NEW - hot-reload)
- Extra Motion Options (existing)

**Behavior:**
- **Scope**: Global with per-camera storage - presets can be saved/loaded across cameras
- **Load**: Hybrid - hot-reload settings apply immediately, others stage for Apply
- **Management**: Delete, rename, overwrite protection

**AWB Modes**: Auto, Daylight, Cloudy, Tungsten, Fluorescent, Custom

---

## Implementation Strategy

### Phase 1: AWB Implementation (New Hot-Reload Parameter)

Follow the exact pattern used for Brightness/Contrast/ISO.

#### 1.1 Backend Changes

**File: `motioneye/config/camera/constants.py`**
- **Location**: Line 217 (after `libcam_iso`)
- **Action**: Add to `HOT_RELOAD_PARAMS` set:
  ```python
  'libcam_awb_mode',
  ```

**File: `motioneye/config/defaults.py`**
- **Location**: Around line 93 (in `_set_default_motion_camera()`)
- **Action**: Add default AWB value:
  ```python
  data.setdefault('libcam_awb_mode', 0)  # 0 = Auto
  ```

**File: `motioneye/config/camera/converters.py`**
- **Location 1**: Line 425 (after ISO in `motion_camera_ui_to_dict()`)
- **Action**: Add UI-to-config mapping:
  ```python
  data['libcam_awb_mode'] = int(ui.get('awb_mode', 0))
  ```

- **Location 2**: Line 994 (after ISO in `motion_camera_dict_to_ui()`)
- **Action**: Add config-to-UI mapping:
  ```python
  ui['awb_mode'] = int(data.get('libcam_awb_mode', 0))
  ```

**AWB Mode Mappings** (libcamera standard):
- 0: Auto
- 1: Tungsten (Incandescent)
- 2: Fluorescent
- 3: Indoor
- 4: Daylight
- 5: Cloudy
- 7: Custom

#### 1.2 Frontend Changes

**File: `motioneye/templates/partials/settings/_video_device.html`**
- **Location**: After line 110 (after Gain/ISO slider)
- **Action**: Add AWB dropdown control:
  ```html
  <tr class="settings-item libcam-only">
      <td class="settings-item-label">
          <span class="settings-item-label" data-i18n="White Balance">White Balance</span>
          <span class="hot-reload-badge" title="Changes apply instantly without restarting the camera">⚡ Live</span>
      </td>
      <td class="settings-item-value">
          <select class="styled device camera-config hot-reload" id="awbModeSelect">
              <option value="0" data-i18n="Auto">Auto</option>
              <option value="4" data-i18n="Daylight">Daylight</option>
              <option value="5" data-i18n="Cloudy">Cloudy</option>
              <option value="1" data-i18n="Tungsten">Tungsten</option>
              <option value="2" data-i18n="Fluorescent">Fluorescent</option>
              <option value="7" data-i18n="Custom">Custom</option>
          </select>
      </td>
      <td><span class="help-mark" data-i18n-title="Auto white balance mode. Changes apply instantly without restarting the camera." title="Auto white balance mode. Changes apply instantly without restarting the camera.">?</span></td>
  </tr>
  ```

**File: `motioneye/static/js/main.js`**
- **Location**: Around line 5760 (in `applyHotReloadParameter()` function)
- **Action**: Add AWB to parameter map:
  ```javascript
  var paramMap = {
      'brightnessSlider': 'libcam_brightness',
      'contrastSlider': 'libcam_contrast',
      'isoSlider': 'libcam_iso',
      'awbModeSelect': 'libcam_awb_mode'  // NEW
  };
  ```

- **Location**: Around line 2063 (in `cameraUi2Dict()` function)
- **Action**: Add AWB to config dictionary:
  ```javascript
  if ($('#awbModeSelect').length) {
      dict['awb_mode'] = parseInt($('#awbModeSelect').val());
  }
  ```

- **Location**: Around line 2400 (in `dict2CameraUi()` function)
- **Action**: Add AWB to UI population:
  ```javascript
  if (dict['awb_mode'] !== undefined) {
      $('#awbModeSelect').val(dict['awb_mode'].toString());
  }
  ```

**File: `motioneye/static/css/main.css`**
- **Note**: No changes needed - existing hot-reload badge CSS applies automatically

---

### Phase 2: Preset Storage System

#### 2.1 Storage Design

**File Format**: JSON per camera
**Location**: `/etc/motioneye/camera-{id}-presets.json`

**Structure**:
```json
{
  "presets": {
    "bright-daylight": {
      "name": "Bright Daylight",
      "settings": {
        "autofocus_mode": 2,
        "autofocus_range": 0,
        "framerate": 30,
        "brightness": 0.2,
        "contrast": 1.2,
        "iso": 1.0,
        "awb_mode": 4,
        "extraOptions": ""
      },
      "created": "2025-12-20T14:30:00Z",
      "modified": "2025-12-20T14:30:00Z"
    }
  },
  "version": 1
}
```

**Global Preset Index** (optional): `/etc/motioneye/preset-index.json`
```json
{
  "presets": ["bright-daylight", "low-light", "indoor", "outdoor"],
  "version": 1
}
```

#### 2.2 Storage Module

**File: `motioneye/config/presets.py` (NEW FILE)**

Create new module with functions:
- `get_preset_file(camera_id)` - Get preset file path
- `load_presets(camera_id)` - Load all presets for a camera
- `save_presets(camera_id, presets_data)` - Save all presets
- `get_preset(camera_id, preset_id)` - Get specific preset
- `save_preset(camera_id, preset_id, name, settings)` - Save/update preset
- `delete_preset(camera_id, preset_id)` - Delete preset
- `rename_preset(camera_id, old_id, new_id, new_name)` - Rename preset
- `list_all_presets()` - List all preset IDs across all cameras

---

### Phase 3: Backend API Endpoints

**File: `motioneye/handlers/config.py`**

Add new handler methods (around line 906, after `hot_reload()` method):

1. **`list_presets(camera_id)`** - GET `/config/{camera_id}/presets/`
   - Returns camera presets and global preset list

2. **`save_preset(camera_id)`** - POST `/config/{camera_id}/presets/save`
   - Saves new preset or updates existing
   - Implements overwrite protection

3. **`load_preset(camera_id)`** - POST `/config/{camera_id}/presets/load`
   - Loads preset from camera or searches other cameras
   - Returns preset settings

4. **`delete_preset(camera_id)`** - POST `/config/{camera_id}/presets/delete`
   - Deletes preset by ID

5. **`rename_preset(camera_id)`** - POST `/config/{camera_id}/presets/rename`
   - Renames preset (updates ID and name)

**Add routes** (in `motioneye/server.py`):
```python
(r'^/config/(?P<camera_id>\d+)/presets/$', config.ConfigHandler, {'action': 'list_presets'}),
(r'^/config/(?P<camera_id>\d+)/presets/save$', config.ConfigHandler, {'action': 'save_preset'}),
(r'^/config/(?P<camera_id>\d+)/presets/load$', config.ConfigHandler, {'action': 'load_preset'}),
(r'^/config/(?P<camera_id>\d+)/presets/delete$', config.ConfigHandler, {'action': 'delete_preset'}),
(r'^/config/(?P<camera_id>\d+)/presets/rename$', config.ConfigHandler, {'action': 'rename_preset'}),
```

---

### Phase 4: Frontend UI Implementation

#### 4.1 HTML Structure

**File: `motioneye/templates/partials/settings/_video_device.html`**
- **Location**: After line 145 (after Extra Options textarea)

Add:
- Preset selector dropdown
- Load/Save/Manage buttons
- Save preset modal dialog (with overwrite warning)
- Manage presets modal dialog (with rename/delete)

#### 4.2 JavaScript Implementation

**File: `motioneye/static/js/main.js`**

Add preset management functions (around line 6000):
- `loadPresetList()` - Fetch and populate preset dropdown
- `loadPreset()` - Load selected preset
- `applyPresetSettings(settings)` - Apply with hybrid behavior
- `applyHotReloadSetting(key, value)` - Apply hot-reload setting immediately
- `savePreset()` - Show save dialog
- `confirmSavePreset(confirmOverwrite)` - Save preset with overwrite check
- `gatherPresetSettings()` - Collect current settings
- `managePresets()` - Show manage dialog
- `populatePresetManagementList()` - Populate preset list
- `renamePreset(presetId)` - Rename preset
- `deletePreset(presetId)` - Delete preset with confirmation

#### 4.3 CSS Styling

**File: `motioneye/static/css/main.css`**

Add modal dialog styles (around line 1600):
- `.modal-dialog` - Full-screen overlay
- `.modal-content` - Dialog box
- `.modal-body` - Content area
- `.modal-buttons` - Button container
- `.preset-row` - Preset list item
- `.button.small-button` - Small action buttons

---

## Implementation Order

### Step 1: AWB Implementation (1-2 hours)
1. Add `libcam_awb_mode` to constants.py
2. Add default in defaults.py
3. Add converters in converters.py (UI-to-config and config-to-UI)
4. Add UI dropdown in _video_device.html
5. Add JavaScript mapping in main.js
6. Test hot-reload functionality

**Testing Checkpoint**: AWB dropdown appears, changes apply instantly without restart

### Step 2: Preset Storage Backend (2-3 hours)
1. Create `motioneye/config/presets.py` module
2. Implement all storage functions
3. Test file creation and JSON read/write

**Testing Checkpoint**: Can manually create/read preset JSON files

### Step 3: Backend API (2-3 hours)
1. Add handler methods to config.py
2. Add routes to server.py
3. Test API endpoints with curl/Postman

**Testing Checkpoint**: All API endpoints return correct responses

### Step 4: Frontend UI (3-4 hours)
1. Add HTML controls to _video_device.html
2. Add modal dialogs
3. Implement JavaScript functions in main.js
4. Add CSS styling
5. Test all workflows: save, load, rename, delete

**Testing Checkpoint**: Complete preset workflow works end-to-end

### Step 5: Integration Testing (1-2 hours)
1. Test hybrid load behavior (hot-reload vs staged)
2. Test overwrite protection
3. Test global preset loading across cameras
4. Test edge cases (empty names, special characters)

### Step 6: Pi 5 Deployment Testing (1 hour)
1. Deploy to Pi 5 using rsync
2. Test AWB modes with real camera
3. Test preset save/load with actual camera
4. Verify hot-reload works correctly

---

## Critical Files to Modify

### Backend
1. `motioneye/config/camera/constants.py` - Add AWB to hot-reload params
2. `motioneye/config/defaults.py` - Add AWB default value
3. `motioneye/config/camera/converters.py` - Add AWB converters
4. `motioneye/config/presets.py` - NEW FILE - Preset storage module
5. `motioneye/handlers/config.py` - Add preset API handlers
6. `motioneye/server.py` - Add preset routes

### Frontend
7. `motioneye/templates/partials/settings/_video_device.html` - Add AWB dropdown and preset UI
8. `motioneye/static/js/main.js` - Add preset management JavaScript
9. `motioneye/static/css/main.css` - Add modal dialog styles

---

## Key Design Decisions

### Why Per-Camera JSON Files?
- Follows existing pattern (similar to prefs.json)
- Isolated per camera for easy backup/restore
- Simple file format, easy to debug
- Can be version-controlled or synced

### Why Hybrid Load Behavior?
- Hot-reload settings (brightness, contrast, ISO, AWB) benefit from instant feedback
- Structural settings (framerate, autofocus) should be reviewed before applying
- Gives user control while optimizing for quick adjustments

### Why Global Preset Index?
- Allows preset names to be shared across cameras
- Users can create "Daylight" preset on Camera 1, load on Camera 2
- Still stores per-camera for data integrity

### AWB Mode Mapping
Using standard libcamera AwbMode enum values for compatibility

---

## Dependencies on Motion 5.0 Security Integration

This plan builds on the Motion 5.0 security integration already completed:

**Existing CSRF Implementation** (in `motioneye/motionctl.py`):
- `_get_csrf_token()` - Retrieves and caches CSRF token from Motion
- `_post_with_csrf()` - Makes POST requests with automatic CSRF token and retry on 403
- `set_config_hot()` - Hot-reload mechanism using POST + CSRF

**AWB Hot-Reload Will Use**:
- Same `_post_with_csrf()` method for secure Motion API calls
- Same hot-reload pattern as brightness/contrast/ISO
- Existing CSRF token caching and retry logic

**Verification Required**:
- Confirm Motion 5.0 supports `libcam_awb_mode` as hot-reloadable parameter
- Verify libcamera AWB mode enum values match Motion's expectations
- Test CSRF token flow works with AWB parameter changes

---

## Testing Strategy

### Unit Tests
- Preset storage functions (load, save, delete, rename)
- AWB mode conversion
- Preset ID generation from names

### Integration Tests
- Full save/load workflow
- Hot-reload vs staged settings separation
- Overwrite protection
- Global preset loading

### Manual Testing on Pi 5
- AWB mode changes with real camera
- Preset workflow with actual camera settings
- Performance of hot-reload vs batch apply

---

## Risk Mitigation

### File Permissions
- Ensure `/etc/motioneye/` is writable by MotionEye process
- Handle permission errors gracefully

### JSON Corruption
- Wrap all file I/O in try/except
- Validate JSON structure on load
- Provide fallback to empty preset list

### Concurrent Access
- File-based storage is simple but not atomic
- Consider file locking for production use
- Current risk is low (single-user web interface)

### Preset Name Collisions
- Generate IDs from names (kebab-case)
- Implement overwrite protection
- Show clear warnings to user

### Motion API Compatibility
- Verify AWB parameter name with Motion 5.0 documentation
- Test that AWB is truly hot-reloadable (doesn't require restart)
- Confirm libcamera enum values match Motion's expectations

---

## Future Enhancements

1. **Import/Export Presets**: Allow users to download/upload preset JSON files
2. **Preset Categories**: Group presets by scenario (indoor, outdoor, night, etc.)
3. **Preset Scheduling**: Auto-load presets at certain times of day
4. **Preset Thumbnails**: Save a snapshot when creating preset for visual reference
5. **Preset Sharing**: Community preset repository
6. **Advanced AWB**: Custom AWB gains for manual white balance tuning

---

## Success Criteria

✅ AWB hot-reload works without camera restart
✅ Can save current settings as named preset
✅ Can load preset with hybrid behavior (hot-reload immediate, others staged)
✅ Can rename and delete presets
✅ Overwrite protection prevents accidental data loss
✅ Presets saved on one camera can be loaded on another
✅ UI integrates seamlessly with existing settings interface
✅ All changes tested on Raspberry Pi 5 with real camera

---

## Review Checklist

Before implementation, verify:
- [ ] Motion 5.0 CSRF integration is complete and tested
- [ ] AWB parameter name matches Motion 5.0 API
- [ ] AWB is confirmed as hot-reloadable in Motion 5.0
- [ ] libcamera AWB mode enum values are verified
- [ ] No conflicts with existing hot-reload parameters
- [ ] File permission handling is consistent with existing config files
- [ ] Route definitions don't conflict with existing endpoints
- [ ] JavaScript function names don't collide with existing code
