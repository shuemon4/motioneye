# Motion Camera Capability Discovery Integration Plan

**Date:** 2025-12-22
**Status:** Draft
**Author:** Claude (AI Assistant)

---

## Executive Summary

Motion 5.0+ now exposes runtime camera capability discovery via `/status.json`, returning a `supportedControls` map that indicates which libcamera controls (AfMode, LensPosition, AwbEnable, etc.) the connected camera hardware actually supports. This allows MotionEye to dynamically show/hide UI controls based on actual camera capabilities, rather than relying on static detection or hardcoded assumptions.

**Key Benefits:**
- Eliminates hardcoded camera model assumptions
- Properly hides autofocus controls for cameras without AF hardware
- Future-proofs the UI for new camera types
- Reduces user confusion and support requests

---

## Current State Analysis

### What Already Works

1. **Autofocus Detection (Static):** `motioneye/controls/rpicamctl.py` calls `rpicam-hello --list-cameras` and checks for IMX708 sensor to determine `supports_autofocus` flag.

2. **UI Conditional Rendering:** `motioneye/static/js/main.js` uses `markHideIfNull()` to conditionally show/hide autofocus controls based on `dict['supports_autofocus']`.

3. **Hot-Reload Infrastructure:** `motioneye/handlers/config.py` and `motioneye/motionctl.py` already handle hot-reload for libcamera controls via POST to Motion's `/config/set` endpoint.

4. **CSRF Token Handling:** `motioneye/motionctl.py` already fetches and caches CSRF tokens from Motion's web interface.

### Gaps to Fill

1. **No `/status.json` Integration:** MotionEye does not fetch or cache Motion's `/status.json` response.

2. **Static Autofocus Detection:** Current AF detection is sensor-based (IMX708 check), not runtime capability-based.

3. **No `supportedControls` in UI Config:** The `motion_camera_dict_to_ui()` function doesn't pass `supportedControls` to the frontend.

4. **No Graceful Degradation for Non-libcamera:** When `/status.json` doesn't include `supportedControls` (older Motion or non-libcamera), MotionEye should fall back to showing all controls.

5. **`ignored` Array Not Handled:** Hot-reload responses may include an `ignored` array when controls aren't supported, which MotionEye doesn't process.

---

## Integration Approach

### Design Principles

1. **Minimal Invasiveness:** Reuse existing infrastructure (CSRF, hot-reload) where possible.
2. **Graceful Degradation:** If capability discovery fails or isn't available, fall back to current behavior.
3. **Cache Appropriately:** Camera capabilities don't change at runtime; cache per camera session.
4. **CPU Awareness:** Avoid unnecessary API calls; fetch capabilities once when camera settings are loaded.

### Architecture Decision

**Option A: Backend Fetches Capabilities**
MotionEye backend fetches `/status.json` and merges `supportedControls` into the UI config dict.

**Option B: Frontend Fetches Capabilities**
JavaScript fetches `/status.json` directly from Motion and updates UI visibility.

**Selected: Option A (Backend)**

Rationale:
- Consistent with existing pattern (all Motion API calls go through backend)
- Allows caching in Python (more efficient)
- Keeps sensitive Motion API URLs server-side
- Frontend already expects `supports_autofocus` in the config dict

---

## Implementation Plan

### Phase 1: Backend Capability Fetching (Core)

#### 1.1 Add `/status.json` Fetching to `motionctl.py`

**File:** `motioneye/motionctl.py`

Add new function to fetch camera capabilities:

```python
async def get_camera_capabilities(camera_id: int) -> dict:
    """
    Fetch camera capabilities from Motion's /status.json endpoint.

    Args:
        camera_id: MotionEye camera ID

    Returns:
        dict with supportedControls map, or empty dict if unavailable
    """
    if not is_motion_50() or not running():
        return {}

    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return {}

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/status.json'

    try:
        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )
        resp = await AsyncHTTPClient().fetch(request, raise_error=False)

        if resp.code != 200:
            logging.debug(f'status.json returned HTTP {resp.code}')
            return {}

        data = json.loads(resp.body.decode('utf-8'))
        cam_key = f'cam{motion_camera_id}'

        if cam_key in data.get('status', {}):
            return data['status'][cam_key].get('supportedControls', {})

        return {}

    except Exception as e:
        logging.debug(f'Failed to fetch camera capabilities: {e}')
        return {}
```

**Caching Strategy:**
Add module-level cache with camera_id key, invalidated on Motion restart:

```python
_camera_capabilities_cache = {}

def invalidate_capabilities_cache():
    """Called when Motion restarts."""
    global _camera_capabilities_cache
    _camera_capabilities_cache = {}
```

Call `invalidate_capabilities_cache()` in `stop()` function.

#### 1.2 Update Config Handler to Fetch Capabilities

**File:** `motioneye/handlers/config.py`

Modify `get_config()` to fetch capabilities for local Motion cameras:

```python
@BaseHandler.auth(admin=True)
async def get_config(self, camera_id):
    # ... existing code ...

    if utils.is_local_motion_camera(local_config):
        ui_config = config.motion_camera_dict_to_ui(local_config)

        # Fetch runtime capabilities from Motion
        if motionctl.running():
            capabilities = await motionctl.get_camera_capabilities(camera_id)
            if capabilities:
                ui_config['supported_controls'] = capabilities

        return self.finish_json(ui_config)
```

### Phase 2: Frontend Capability Handling

#### 2.1 Update UI Visibility Logic

**File:** `motioneye/static/js/main.js`

Modify `dict2CameraUI()` to use `supported_controls` when available:

```javascript
function dict2CameraUI(dict) {
    // ... existing code ...

    // Use runtime capabilities if available, fall back to static detection
    var caps = dict['supported_controls'] || {};
    var supportsAF = caps['AfMode'] !== undefined ? caps['AfMode'] : dict['supports_autofocus'];
    var supportsLensPos = caps['LensPosition'] !== undefined ? caps['LensPosition'] : dict['supports_autofocus'];

    // Autofocus controls visibility
    $('#autofocusModeSelect').val(dict['autofocus_mode'] != null ? dict['autofocus_mode'] : 2);
    markHideIfNull(!supportsAF, 'autofocusModeSelect');

    $('#autofocusRangeSelect').val(dict['autofocus_range'] != null ? dict['autofocus_range'] : 0);
    markHideIfNull(!supportsAF, 'autofocusRangeSelect');

    $('#autofocusSpeedSelect').val(dict['autofocus_speed'] != null ? dict['autofocus_speed'] : 0);
    markHideIfNull(!supportsAF, 'autofocusSpeedSelect');

    $('#lensPositionSlider').val(dict['lens_position'] != null ? dict['lens_position'] : 0.0);
    markHideIfNull(!supportsLensPos, 'lensPositionSlider');

    // AWB controls visibility (could be extended similarly)
    var supportsAWB = caps['AwbEnable'] !== undefined ? caps['AwbEnable'] : (dict['proto'] === 'libcamera');
    // ... update AWB visibility based on supportsAWB ...
}
```

#### 2.2 Handle `ignored` Array in Hot-Reload Responses

**File:** `motioneye/static/js/main.js`

Update `applyHotReloadParameter()` to check for ignored controls:

```javascript
function applyHotReloadParameter($element) {
    // ... existing code ...

    ajax('POST', basePath + 'config/' + cameraId + '/hot-reload/', {
        parameter: paramName,
        value: value
    }, function(response) {
        if (response.success) {
            showHotReloadStatus(sliderId, 'success');

            // Check if control was actually ignored by Motion
            if (response.ignored && response.ignored.includes(paramName)) {
                showHotReloadStatus(sliderId, 'unsupported');
                console.warn('Control ignored by camera:', paramName);
            }
        } else {
            showHotReloadStatus(sliderId, 'error');
        }
    });
}
```

#### 2.3 Add "Unsupported" Status Indicator

**File:** `motioneye/static/css/main.css`

```css
.hot-reload-status.unsupported {
    color: #ff9800;  /* Orange warning color */
}

.hot-reload-status.unsupported::after {
    content: ' (unsupported)';
    font-size: 0.8em;
}
```

### Phase 3: Pass `ignored` from Motion to Frontend

#### 3.1 Update Hot-Reload Handler

**File:** `motioneye/handlers/config.py`

Modify `hot_reload()` to pass through `ignored` array:

```python
@BaseHandler.auth(admin=True)
async def hot_reload(self, camera_id):
    # ... existing code ...

    result = await motionctl.set_config_hot(camera_id, param_name, param_value)

    if result['success']:
        response = {
            'success': True,
            'hot_reload': result.get('hot_reload', True),
            'old_value': result.get('old_value', '')
        }
        # Include ignored array if present
        if result.get('ignored'):
            response['ignored'] = result['ignored']
        return self.finish_json(response)
```

#### 3.2 Update `set_config_hot()` to Extract `ignored`

**File:** `motioneye/motionctl.py`

```python
async def set_config_hot(camera_id: int, param: str, value: str) -> dict:
    # ... existing code ...

    if resp.code == 200:
        try:
            data = json.loads(resp.body.decode('utf-8'))

            if data.get('status') == 'ok' and data.get('hot_reload'):
                result = {
                    'success': True,
                    'hot_reload': True,
                    'old_value': data.get('old_value', '')
                }
                # Pass through ignored array
                if data.get('ignored'):
                    result['ignored'] = data['ignored']
                return result
```

### Phase 4: Extend to All Capability-Dependent Controls

#### 4.1 Control Mapping Table

Create a mapping in constants to link supportedControls keys to UI elements:

**File:** `motioneye/config/camera/constants.py`

```python
# Maps Motion supportedControls keys to MotionEye UI element IDs
CAPABILITY_TO_UI_ELEMENT = {
    'AfMode': ['autofocusModeSelect', 'autofocusRangeSelect', 'autofocusSpeedSelect'],
    'LensPosition': ['lensPositionSlider'],
    'AfTrigger': ['triggerAutofocusButton'],
    'AfRange': ['autofocusRangeSelect'],
    'AfSpeed': ['autofocusSpeedSelect'],
    'AwbEnable': ['awbEnableSwitch', 'awbModeSelect', 'awbLockedSwitch'],
    'ColourTemperature': ['colourTempSlider'],
    'ColourGains': ['colourGainRSlider', 'colourGainBSlider'],
    'Brightness': ['brightnessSlider'],
    'Contrast': ['contrastSlider'],
    'AnalogueGain': ['isoSlider'],
}
```

#### 4.2 Generalize Frontend Visibility Logic

**File:** `motioneye/static/js/main.js`

```javascript
var CAPABILITY_TO_UI_ELEMENT = {
    'AfMode': ['autofocusModeSelect', 'autofocusRangeSelect', 'autofocusSpeedSelect'],
    'LensPosition': ['lensPositionSlider'],
    'AfTrigger': ['triggerAutofocusButton'],
    // ... etc
};

function applyCapabilityVisibility(supportedControls) {
    if (!supportedControls || Object.keys(supportedControls).length === 0) {
        return; // No capability info, show all (graceful degradation)
    }

    for (var capKey in CAPABILITY_TO_UI_ELEMENT) {
        var isSupported = supportedControls[capKey] === true;
        var elements = CAPABILITY_TO_UI_ELEMENT[capKey];

        elements.forEach(function(elementId) {
            markHideIfNull(!isSupported, elementId);
        });
    }
}
```

---

## Testing Plan

### Unit Tests

1. **`test_get_camera_capabilities`**: Mock Motion `/status.json` response, verify parsing
2. **`test_capabilities_cache_invalidation`**: Verify cache clears on Motion restart
3. **`test_ignored_array_passthrough`**: Verify `ignored` array flows from Motion to frontend

### Integration Tests

1. **Pi Camera v3 (IMX708)**: Verify all AF controls shown, functioning
2. **Pi Camera v2 (IMX219)**: Verify AF controls hidden, AWB controls shown
3. **HQ Camera (IMX477)**: Verify LensPosition shown (manual focus), AF controls hidden
4. **Motion Restart**: Verify capabilities re-fetched after daemon restart

### Manual Test Script

```bash
# Test on Pi 5 with Camera v3
ssh admin@192.168.1.176

# Check Motion capabilities endpoint directly
curl -s http://localhost:7999/status.json | jq '.status.cam1.supportedControls'

# Restart MotionEye and verify UI
sudo systemctl restart motioneye
sleep 5

# Check logs for capability fetching
sudo journalctl -u motioneye -n 20 | grep -i "capabilit\|supported"
```

---

## Rollback Plan

If issues arise:
1. Remove capability fetching call from `get_config()`
2. Frontend will fall back to static `supports_autofocus` detection
3. No data loss; only UI visibility affected

---

## Migration Notes

### Backward Compatibility

- **Motion < 5.0:** `supportedControls` won't exist in `/status.json`; fall back to static detection
- **Existing Cameras:** No config migration needed; capability detection is runtime only
- **Non-libcamera Cameras:** `supportedControls` will be absent; show all controls (current behavior)

### Future Considerations

1. **Per-Control Value Ranges:** Motion could expose min/max values for each control
2. **Capability Change Events:** WebSocket notification when camera reconnects with different hardware
3. **Third-Party Camera Support:** As more cameras are tested, add to compatibility matrix

---

## Files Modified

| File | Changes |
|------|---------|
| `motioneye/motionctl.py` | Add `get_camera_capabilities()`, caching, invalidation |
| `motioneye/handlers/config.py` | Fetch capabilities in `get_config()`, pass `ignored` in `hot_reload()` |
| `motioneye/static/js/main.js` | `dict2CameraUI()` uses capabilities, handle `ignored` array |
| `motioneye/static/css/main.css` | Add `.unsupported` status styling |
| `motioneye/config/camera/constants.py` | Add `CAPABILITY_TO_UI_ELEMENT` mapping |

---

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Backend Capability Fetching | 2-3 hours | Low |
| Phase 2: Frontend Capability Handling | 2-3 hours | Low |
| Phase 3: `ignored` Passthrough | 1 hour | Low |
| Phase 4: Generalize Controls | 2 hours | Low |
| Testing | 2-3 hours | Medium (hardware dependent) |

**Total: ~10-12 hours**

---

## Decision Points Requiring User Input

1. **Cache TTL:** Should capabilities be cached indefinitely per session, or should there be a refresh interval?
   - Recommendation: Indefinite cache, invalidated only on Motion restart

2. **UI for Unsupported Controls:** Should unsupported controls be:
   - Hidden completely (current plan)
   - Shown but disabled with tooltip
   - Shown with warning icon
   - Recommendation: Hidden completely (matches spec)

3. **Fallback Behavior:** When capabilities unavailable, should we:
   - Show all controls (current plan)
   - Show only universally-supported controls
   - Show controls based on static detection
   - Recommendation: Show all controls (graceful degradation)

---

## Approval Checklist

- [ ] User confirms approach (Backend fetches, not Frontend)
- [ ] User confirms cache strategy (indefinite until Motion restart)
- [ ] User confirms UI behavior (hide unsupported, don't disable)
- [ ] User confirms fallback (show all when unavailable)

---

## Agent 4 Work Log: CSS and Constants Changes

**Status:** Completed
**Date:** 2025-12-22
**Files Modified:**
- motioneye/static/css/main.css
- motioneye/config/camera/constants.py

### Changes Made:

1. **CSS Unsupported Status Indicator** (`motioneye/static/css/main.css`, lines 1492-1499)
   - Added `.hot-reload-status.unsupported` class with orange color (#ff9800)
   - Added `::after` pseudo-element that appends ' (unsupported)' text at 0.8em font size
   - Positioned immediately after `.hot-reload-status.error` style for consistency
   - Follows existing pattern of inline-block status indicators with color-coded semantics

2. **Capability Mapping Constant** (`motioneye/config/camera/constants.py`, lines 284-298)
   - Added `CAPABILITY_TO_UI_ELEMENT` dictionary mapping Motion `supportedControls` keys to UI element IDs
   - Organized by control category:
     - Autofocus: AfMode, LensPosition, AfTrigger, AfRange, AfSpeed
     - White Balance: AwbEnable, ColourTemperature, ColourGains
     - Image Quality: Brightness, Contrast, AnalogueGain
   - Placed after `RESTART_REQUIRED_PARAMS` for logical grouping with other parameter mappings
   - Includes comprehensive docstring explaining purpose

### Notes:

- CSS changes are ready for Phase 2.3 frontend integration (status indicator display)
- Constants mapping provides reference documentation and will be mirrored in JavaScript for phase 4.1 generalized visibility logic
- Both changes follow existing code style and conventions
- No functionality changes yet; these are foundational pieces for Phase 2.3 and Phase 4.1 implementation

---

## Agent 2 Work Log: handlers/config.py Changes

**Status:** Completed
**Date:** 2025-12-22
**Files Modified:** motioneye/handlers/config.py

### Changes Made:

1. **Updated `get_config()` method** (lines 121-139)
   - Added capability fetching for local Motion cameras
   - After calling `config.motion_camera_dict_to_ui()`, added check: `if motionctl.running()`
   - Calls `await motionctl.get_camera_capabilities(camera_id)` to fetch runtime capabilities
   - If capabilities dict is non-empty, adds `ui_config['supported_controls'] = capabilities`
   - Respects existing control flow; return statement unchanged
   - Gracefully handles when Motion not running (returns empty dict, no UI impact)

2. **Updated `hot_reload()` method** (lines 922-941)
   - Modified success response building to include `ignored` array when present
   - Changed from inline dict construction to multi-step approach:
     - Build base response with `success`, `hot_reload`, `old_value`
     - Check for `ignored` key in result from `motionctl.set_config_hot()`
     - Add to response dict if present: `response['ignored'] = result['ignored']`
   - Added explanatory comment: "Include ignored array if present (controls not supported by camera)"
   - Error response path unchanged

### Implementation Notes:

- `motionctl` already imported at line 35 (no changes needed)
- Both changes are async-aware and follow existing patterns in file
- Error handling preserved; new code only adds data, doesn't change error paths
- Capability fetching is non-blocking (returns empty dict on any error)
- `ignored` array passthrough is conditional; only added if present in Motion response

### Ready For:

- Phase 1.2: Backend capability fetching via `get_config()`
- Phase 3.1: Pass-through of `ignored` array in hot-reload responses
- Frontend integration will handle null/empty cases gracefully (existing pattern)

---

## Agent 1 Work Log: motionctl.py Changes

**Status:** Completed
**Date:** 2025-12-22
**Files Modified:** motioneye/motionctl.py

### Changes Made:

1. **Camera Capabilities Cache** (`motioneye/motionctl.py`, line 54)
   - Added module-level dictionary `_camera_capabilities_cache = {}` to store capabilities keyed by camera_id
   - Placed after `_csrf_token_cache` definition for logical grouping with other module-level caches
   - Includes inline comment documenting purpose: "(camera_id -> supportedControls dict)"

2. **Cache Invalidation Function** (`motioneye/motionctl.py`, lines 95-98)
   - Added `invalidate_capabilities_cache()` function that clears cached capabilities on Motion restart
   - Uses standard global pattern consistent with existing cache management code
   - Includes docstring explaining when/why the cache is cleared
   - Placed immediately after `find_motion()` for logical grouping with other cache management functions

3. **Cache Invalidation Call in stop()** (`motioneye/motionctl.py`, lines 177-178)
   - Added call to `invalidate_capabilities_cache()` at the beginning of Motion shutdown
   - Placed before CSRF token cache invalidation for logical flow
   - Includes inline comment explaining the invalidation purpose
   - Ensures fresh capabilities are fetched after Motion restarts

4. **get_camera_capabilities() Async Function** (`motioneye/motionctl.py`, lines 278-327)
   - New async function to fetch camera capabilities from Motion's `/status.json` endpoint
   - Implements caching with camera_id as key
   - Returns empty dict if Motion not running, camera_id invalid, or fetch fails
   - Handles HTTP error responses gracefully
   - Parses JSON response and extracts `supportedControls` from Motion's status structure
   - Includes comprehensive docstring with Args and Returns documentation
   - Placed after `get_motion_detection()` for logical grouping with other Motion status API calls
   - Includes exception handling with debug logging for troubleshooting

5. **Update set_config_hot() to Extract ignored Array** (`motioneye/motionctl.py`, lines 904-912)
   - Modified successful hot-reload response handling to include `ignored` array if present
   - Changed return statement from direct dict to intermediate variable `result`
   - Added conditional check: `if data.get('ignored'): result['ignored'] = data['ignored']`
   - Maintains backward compatibility (ignored array only included if present in Motion response)
   - Allows downstream handlers and frontend to process unsupported controls

### Implementation Details:

**Cache Invalidation Flow:**
- When `stop()` is called: `invalidate_capabilities_cache()` clears the global dict
- When Motion restarts via `start()`: First `get_camera_capabilities()` call fetches fresh data
- Cache persists for the lifetime of Motion's current session

**Error Handling:**
- Network errors, JSON parsing errors, and missing status keys all return empty dict
- Calling code can treat empty dict as "no capability info available" and fall back to static detection
- Debug logging enables troubleshooting without raising exceptions

**Backward Compatibility:**
- Motion < 5.0 or non-libcamera setups will return empty `supportedControls` (handled gracefully)
- Empty capabilities dict is treated same as `None` in frontend (show all controls)

### Notes:

- All changes follow existing code style: async/await patterns, exception handling, logging conventions
- Minimal changes to existing code (only addition to `stop()` function)
- Imports (`json`, `HTTPRequest`, `AsyncHTTPClient`) already present in file
- Function signatures and error handling consistent with similar functions (`get_motion_detection()`, `take_snapshot()`)
- Ready for Phase 1.2 (config handler integration) in next iteration

---

## Agent 3 Work Log: main.js Changes

**Status:** Completed
**Date:** 2025-12-22
**Files Modified:** motioneye/static/js/main.js

### Changes Made:

1. **Added CAPABILITY_TO_UI_ELEMENT Constant** (lines 85-98)
   - Global constant mapping Motion `supportedControls` keys to UI element IDs
   - Maps 11 capability types to their corresponding UI controls:
     - AfMode → autofocus mode/range/speed selects (3 elements)
     - LensPosition → lens position slider (1 element)
     - AfTrigger → trigger autofocus button (1 element)
     - AfRange → autofocus range select (1 element) [redundant with AfMode, preserved for clarity]
     - AfSpeed → autofocus speed select (1 element) [redundant with AfMode, preserved for clarity]
     - AwbEnable → AWB enable switch, mode select, locked switch (3 elements)
     - ColourTemperature → colour temp slider (1 element)
     - ColourGains → colour gain R/B sliders (2 elements)
     - Brightness → brightness slider (1 element)
     - Contrast → contrast slider (1 element)
     - AnalogueGain → ISO slider (1 element)
   - Placed after `cameraVisibility` and before `initIntersectionObserver()` for logical organization

2. **Added applyCapabilityVisibility() Function** (lines 100-117)
   - New helper function to apply capability-based visibility to UI elements
   - Takes `supportedControls` dict parameter (or null/empty dict)
   - Implements graceful degradation: if no capability info provided, shows all controls
   - Iterates through CAPABILITY_TO_UI_ELEMENT mapping
   - For each capability key, checks if it's supported (value === true)
   - Calls `markHideIfNull(!isSupported, elementId)` for each mapped UI element
   - Enables bulk visibility updates based on Motion's reported capabilities (Phase 4.2)

3. **Updated dict2CameraUI() Autofocus Section** (lines 2458-2466)
   - Replaced direct use of `dict['supports_autofocus']` with runtime capability detection
   - Added comment explaining fallback strategy
   - Extracts `supported_controls` dict from config (or empty dict if not present)
   - Creates `supportsAF` variable: uses `caps['AfMode']` if available, else falls back to `dict['supports_autofocus']`
   - Creates `supportsLensPos` variable: uses `caps['LensPosition']` if available, else falls back to `dict['supports_autofocus']`
   - Updated all autofocus control visibility calls to use these variables instead of direct `dict['supports_autofocus']`
   - Preserves existing value-setting logic; only changes visibility determination

4. **Added applyCapabilityVisibility() Call in dict2CameraUI()** (line 2786)
   - Added call at end of `dict2CameraUI()` function, before closing brace
   - Passes `dict['supported_controls']` to apply capability-based visibility
   - Placed after `initWbModeFromValues()` call for proper execution order
   - Enables Phase 2.1/2.2 generalized capability-to-UI mapping

5. **Updated applyHotReloadParameter() Response Handler** (lines 6043-6061)
   - Added check for `response.ignored` array when hot-reload succeeds
   - If control appears in `ignored` array, shows 'unsupported' status instead of 'success'
   - Logs warning: "Control ignored by camera (not supported)"
   - Preserves all existing success/error handling logic
   - Enables Phase 4.2 handling of unsupported controls in hot-reload responses

6. **Updated showHotReloadStatus() for 'unsupported' Status** (lines 6086, 6104-6112)
   - Added 'unsupported' to removeClass() call (line 6086) to properly clear previous status
   - Added new else-if branch for `status === 'unsupported'` (lines 6104-6112)
   - Shows '⊘' (circled slash) symbol to indicate control not supported by camera
   - Adds 'unsupported' CSS class for styling (orange color per Phase 2.3 CSS definition)
   - Auto-hides after 3 seconds like error status
   - Provides user feedback when control is requested but camera doesn't support it

### Implementation Notes:

- All changes follow existing code style: var declarations, jQuery usage, comment conventions
- Graceful degradation on every level:
  - If `supported_controls` missing from dict → shows all controls
  - If `ignored` array missing from response → treats as normal success
  - If Motion running older version → no `supported_controls` → falls back to `supports_autofocus`
- Backward compatible: existing `supports_autofocus` flag still used as fallback
- Error handling preserves existing patterns; new code only adds data, doesn't change error flows
- Console logging added for debugging without breaking functionality

### Ready For:

- Phase 2.1: Capability-based UI visibility driven by runtime Motion data
- Phase 2.2: Autofocus controls properly hidden/shown based on actual hardware
- Phase 4.2: Hot-reload responses properly handle unsupported controls
- Frontend integration complete; pairs with backend changes from Agents 1-2
