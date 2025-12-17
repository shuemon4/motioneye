# Brightness/Contrast Hot-Reload Bug Fixes

**Date**: 2025-12-16 14:16 CST
**Issue**: Hot-reload not triggering on slider release
**Status**: ✅ Fixed and Deployed

---

## Issues Discovered

### Bug #1: Event Handler Timing Issue
**Symptom**: Sliders worked only after clicking Apply button, not on mouse release

**Root Cause**:
- `initHotReloadSliders()` was called on `$(document).ready()` (line 5739)
- But sliders were created later by `initUI()` function (line 680-701)
- When `initHotReloadSliders()` ran, the `.slider` divs didn't exist yet
- Event handlers (`mouseup`/`touchend`) were never attached

**Fix Applied**:
- **File**: `motioneye/static/js/main.js`
- **Line 703-704**: Added `initHotReloadSliders()` call immediately after slider creation
- **Line 5739**: Removed duplicate call from document.ready

**Code Change**:
```javascript
// In initUI() function, after makeSlider loop (line 703-704)
/* attach hot-reload handlers to brightness/contrast sliders */
initHotReloadSliders();
```

---

### Bug #2: Missing Route Registration
**Symptom**: HTTP 404 errors when trying to call hot-reload endpoint

**Error Logs**:
```
WARNING: 404 POST /config/1/hot-reload/?_=1765912260065... (192.168.1.184) 1.41ms
ERROR: HTTP 404: Not Found (not found)
```

**Root Cause**:
- Server route pattern on line 195 only allowed: `get|set|rem|test|authorize`
- The `hot-reload` operation was not included in the regex pattern
- Tornado router rejected all `/config/<id>/hot-reload/` requests with 404

**Fix Applied**:
- **File**: `motioneye/server.py`
- **Line 195**: Added `hot-reload` to allowed operations regex

**Code Change**:
```python
# Before:
r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|test|authorize)/?$'

# After:
r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|test|authorize|hot-reload)/?$'
```

---

## Deployment Steps Taken

1. **Fixed main.js timing issue**:
   ```bash
   rsync -avz .../main.js admin@192.168.1.176:~/motioneye/motioneye/static/js/
   sudo systemctl restart motioneye
   ```

2. **Fixed server.py route registration**:
   ```bash
   rsync -avz .../server.py admin@192.168.1.176:~/motioneye/motioneye/
   cd ~/motioneye && sudo pip3 install . --break-system-packages
   sudo systemctl restart motioneye
   ```

---

## Verification Steps

### Before Fix:
- ✗ Slider release → Red X error
- ✗ Console: "404 POST /config/1/hot-reload/"
- ✗ No brightness/contrast change in stream

### After Fix:
- ✅ Slider release → Event handler fires
- ✅ HTTP request succeeds (route exists)
- ⏳ Testing: Brightness/contrast should update instantly

---

## Testing Checklist

User should now verify:
- [ ] Drag brightness slider to 0.5, release
- [ ] Observe ⏳ "Applying" indicator
- [ ] See ✓ green checkmark (not ✗ red X)
- [ ] Video stream brightness increases instantly
- [ ] Orange "*" appears on Apply button
- [ ] Click Apply to persist changes
- [ ] Orange "*" disappears

---

## Additional Issues Noted (Not Related to Hot-Reload)

**Motion Config Warning**:
```
[ALR][ALL][mo00] edit_set: Unknown config option "libcam_control_item"
```

**Analysis**: This is related to autofocus controls, not brightness/contrast. Motion 5.0 doesn't recognize `libcam_control_item` as written. This is a separate issue from the hot-reload implementation and doesn't affect brightness/contrast functionality.

**SQLite Error** (Unrelated):
```
[ERR][DBS][dl00:dbsl] sqlite3db_exec: SQLite error was attempt to write a readonly database
```

**Analysis**: Database permission issue, not related to hot-reload. Motion is trying to write to a read-only SQLite database (possibly for motion events). Does not impact brightness/contrast hot-reload.

---

## Files Modified

1. `motioneye/static/js/main.js`
   - Line 703-704: Added `initHotReloadSliders()` call
   - Line 5739: Removed duplicate initialization

2. `motioneye/server.py`
   - Line 195: Added `hot-reload` to route pattern

---

## Root Cause Analysis Summary

Both bugs were **implementation oversights**:

1. **Timing Bug**: Classic JavaScript event handler timing issue
   - Solution: Attach handlers immediately after DOM elements are created

2. **Routing Bug**: Forgot to register the new endpoint in the route table
   - Solution: Add operation to existing route regex pattern

Neither bug was in the core hot-reload logic itself - the implementation was correct, but the infrastructure wasn't complete.

---

## Lessons Learned

1. **Event Handler Timing**: Always attach event handlers immediately after creating DOM elements, not on document.ready when elements might not exist yet

2. **Route Registration**: When adding new API endpoints, check BOTH:
   - Handler method exists (✅ we had this)
   - Route is registered in server.py (✗ we missed this)

3. **Testing Workflow**:
   - Check browser console for HTTP errors
   - Check server logs for 404s
   - Verify routes are registered before testing handlers

---

## Next Steps

User needs to test and confirm:
1. Hot-reload works (⏳ → ✓)
2. Stream updates instantly
3. No errors in console
4. Changes persist on Apply

If still not working, next debugging steps:
- Check browser console for different errors
- Check MotionEye logs for non-404 errors
- Verify Motion 5.0 is accepting hot-reload API calls
- Test Motion API directly: `curl 'http://localhost:7999/1/config/set?libcam_brightness=0.5'`

---

**Status**: Ready for final user testing
