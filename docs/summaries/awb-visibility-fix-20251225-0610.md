# AWB Manual Mode Visibility Fix

**Date:** 2025-12-25 06:10
**Issue:** When AWB is first turned off, both Temperature and Red/Blue Gain controls were visible
**Status:** ✅ Fixed and deployed

---

## Problem Description

When a user toggled AWB (Auto White Balance) off for the first time in the Video Device settings:
- Both the Temperature slider AND the Red/Blue Gain sliders became visible
- The toggle showed "Temperature" selected
- Only the Temperature control should have been visible
- The Gain controls should have been hidden by default

---

## Root Cause Analysis

### Dependency System Behavior

The HTML template uses `depends="!awbEnable"` on both control groups:
- `tr.wb-temp-control` (Temperature slider)
- `tr.wb-gains-control` (Red/Blue gain sliders)

When AWB was toggled off:
1. The `awbEnableSwitch` change handler fired (main.js:6057)
2. `applyHotReloadParameter()` was called to send the change to the backend
3. **BUT** `updateConfigUI()` was never triggered
4. The dependency system (`depends="!awbEnable"`) made both control groups visible
5. `initWbModeFromValues()` was never called to apply mode-based visibility

### Missing Handler

Most switches that control visibility have this pattern:
```javascript
$('#videoDeviceEnabledSwitch').change(updateConfigUI);
$('#autofocusModeSelect').change(updateConfigUI);
```

But `awbEnableSwitch` only had a hot-reload handler:
```javascript
$('#awbEnableSwitch').on('change', function() {
    applyHotReloadParameter($(this));
    // Missing: visibility update!
});
```

---

## Solution

Added a call to `initWbModeFromValues()` after the hot-reload parameter is applied:

**File:** `motioneye/static/js/main.js:6057-6063`

```javascript
// AWB checkbox and select hot-reload handlers
$('#awbEnableSwitch').on('change', function() {
    applyHotReloadParameter($(this));
    // When AWB is toggled, ensure WB mode visibility is updated
    if (typeof initWbModeFromValues === 'function') {
        initWbModeFromValues();
    }
});
```

### How This Works

1. User toggles AWB off
2. `applyHotReloadParameter()` sends the change to Motion backend
3. `initWbModeFromValues()` is called:
   - Checks current Temperature and Gain values
   - Determines which mode should be active (default: temperature)
   - Calls `updateWbModeVisibility()` to show/hide the appropriate controls
   - Updates the toggle button UI

---

## Testing

### Deployment
```bash
# Sync JavaScript to Pi 5
rsync -avz /Users/tshuey/Documents/GitHub/motioneye/motioneye/static/js/main.js \
  admin@192.168.1.176:~/motioneye/motioneye/static/js/

# Restart service
ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
```

### Expected Behavior After Fix

1. **Initial Load**: When opening settings with AWB disabled:
   - ✅ Only Temperature or Gains visible (based on values)
   - ✅ Toggle button shows correct selection

2. **Toggle AWB Off**: When turning AWB off for first time:
   - ✅ Only Temperature slider visible (default mode)
   - ✅ Red/Blue Gain sliders hidden
   - ✅ Toggle shows "Temperature" active

3. **Switch Mode**: When clicking "Gains" toggle:
   - ✅ Temperature slider hidden
   - ✅ Red/Blue Gain sliders shown
   - ✅ Values cleared appropriately

---

## Related Functions

### `initWbModeFromValues()` (main.js:6171)
- Determines mode based on current Temperature/Gain values
- Updates toggle button UI
- Calls `updateWbModeVisibility()`

### `updateWbModeVisibility(mode)` (main.js:6161)
- Shows/hides temperature vs gains controls
- Called by mode toggle and init function

### `updateConfigUI()` (main.js:1882)
- Processes HTML `depends` attributes
- Shows/hides controls based on dependencies
- Does NOT handle mutual exclusivity within a group

---

## Files Modified

| File | Lines | Change |
|------|-------|--------|
| `motioneye/static/js/main.js` | 6057-6063 | Added `initWbModeFromValues()` call to AWB enable handler |

---

## Impact

- **User Experience**: No more confusion when toggling AWB off
- **Backend**: No changes required (backend mutual exclusivity already working)
- **Performance**: Minimal - one additional function call on toggle
- **Compatibility**: No breaking changes

---

## Notes

- This fix only affects the UI visibility logic
- Backend mutual exclusivity (Motion 5.0) was already implemented correctly
- The dependency system (`depends` attribute) works as designed for show/hide
- Mode-based mutual exclusivity requires explicit JavaScript handling
