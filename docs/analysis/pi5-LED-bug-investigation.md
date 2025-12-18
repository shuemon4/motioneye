# Fix LED Toggle Visibility Issue - Diagnostic and Solution Plan

## Problem Summary

**Symptom:** "Disable Raspberry Pi LEDs" toggle exists in HTML but is hidden with `display: none` in the browser.

**Root Cause:** JavaScript marks the element with `_hideNull = true` because the config value `_disablePi5Leds` is missing/null in the AJAX response from `/config/main/get/`.

## Investigation Findings

### Confirmed Facts

1. ✅ **Element exists in DOM:** `$('#disablePi5LedsSwitch').length` returns 1
2. ✅ **Element is hidden:** `.css('display')` returns "none"
3. ✅ **Hide flag set:** `hideNull: true, hideLogic: false, hideMinimized: false`
4. ✅ **Server HTML includes toggle:** `curl http://localhost:8765/` shows the checkbox
5. ✅ **Additional config registered:** `_additional_config_funcs` contains `disablePi5Leds`
6. ✅ **Logged in as admin:** `isAdmin()` returns `true`

### Code Flow Analysis

**Server-side (Config GET):**
```
1. ConfigHandler.get_config() [config.py:143]
   → calls config.main_dict_to_ui(config.get_main())

2. config.get_main() [storage.py:131]
   → calls _get_additional_config(main_config)
   → should populate main_config['@_disablePi5Leds']

3. _get_additional_config() [extensions.py:129-162]
   → calls registered getter functions
   → stores results in data['@_' + name]

4. main_dict_to_ui() [converters.py:226-230]
   → copies all '@_*' keys to UI dict as '_*'
   → ui['_disablePi5Leds'] = data['@_disablePi5Leds']
```

**Client-side (Config Load):**
```
1. fetch Current config [main.js:3494-3609]
   → AJAX GET to /config/main/get/
   → receives JSON response
   → calls dict2MainUi(data)

2. dict2MainUi() [main.js:1995-2061]
   → processes additional configs (lines 2026-2058)
   → for 'disablePi5LedsSwitch', extracts name and looks up dict['_disablePi5Leds']
   → sets checkbox: control[0].checked = dict['_disablePi5Leds']
   → calls markHideIfNull('_disablePi5Leds', 'disablePi5LedsSwitch')

3. markHideIfNull() [main.js:1996-2010]
   → checks: dict['_disablePi5Leds'] == null
   → if null/undefined, sets element._hideNull = true

4. updateConfigUI() [main.js:1624-1879]
   → hides elements where _hideNull || _hideLogic || _hideMinimized is true
```

### Diagnostic Hypothesis

The value `_disablePi5Leds` is **not present in the JSON response** from `/config/main/get/`, causing JavaScript to see it as `undefined`, which triggers `hideNull = true`.

**Possible causes:**
1. `_get_leds_disabled()` getter function not being called
2. Getter returns a value but it's filtered out during serialization
3. Key is present but value is explicitly `null` in Python
4. Exception during getter execution silently caught

## Solution Plan

### Phase 1: Verify Config API Response

**Goal:** Confirm whether `_disablePi5Leds` is in the JSON response

**Actions:**
1. Add logging to `_get_additional_config()` to verify it's being called and what it stores
2. Add logging to `main_dict_to_ui()` to verify it copies the value
3. Check the actual JSON response from `/config/main/get/` endpoint

**Files to modify:**
- `motioneye/config/extensions.py` (add debug logging)
- `motioneye/config/camera/converters.py` (add debug logging)

**Test:**
```bash
# Check server logs while accessing the UI
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -f" &

# Access the config endpoint directly
ssh admin@192.168.1.176 "curl -s 'http://localhost:8765/config/main/get/' | python3 -m json.tool | grep -A2 -B2 'disablePi5Leds'"
```

### Phase 2: Fix Based on Diagnosis

**Scenario A: Value is False and being filtered**

Some JSON serializers skip `false` boolean values.

**Fix:** Modify `_get_leds_disabled()` to return explicit boolean, ensure JSON serialization preserves it.

**Files:**
- `motioneye/controls/ledctl.py:124-138`

**Change:**
```python
# Ensure return value is explicitly bool, not None or other falsy value
return bool(act_brightness == 0 and pwr_brightness == 0)
```

---

**Scenario B: Getter not being called due to registration issue**

The decorator may not be preserving the function or it's being filtered out.

**Fix:** Verify function is in `_additional_config_funcs` at runtime and being called.

**Files:**
- `motioneye/config/extensions.py:102-122`

**Add logging:**
```python
for func in _additional_config_funcs:
    result = func()
    if not result:
        continue

    logging.debug(f"additional config item: {result['name']}")  # Already exists
    logging.debug(f"  - has getter: {result.get('get') is not None}")  # ADD THIS
```

---

**Scenario C: Exception in getter silently caught**

The getter tries to read sysfs but fails silently, returns False, but somewhere the False gets treated as null.

**Fix:** Add explicit logging in `_get_leds_disabled()` and ensure it returns proper boolean.

**Files:**
- `motioneye/controls/ledctl.py:124-138`

**Change:**
```python
def _get_leds_disabled() -> bool:
    """Get the current LED state from sysfs."""
    try:
        with open(ACT_BRIGHTNESS, 'r') as f:
            act_brightness = int(f.read().strip())
        with open(PWR_BRIGHTNESS, 'r') as f:
            pwr_brightness = int(f.read().strip())

        disabled = act_brightness == 0 and pwr_brightness == 0
        logging.debug(f'LED state: ACT={act_brightness}, PWR={pwr_brightness}, disabled={disabled}')
        return disabled
    except Exception as e:
        logging.warning(f'Failed to read LED state from sysfs: {e}')  # Change to warning
        return False
```

---

**Scenario D: Python False equals JavaScript null/undefined**

JSON serialization works but JavaScript comparison fails.

**Fix:** Modify `markHideIfNull()` to handle boolean false explicitly.

**Files:**
- `motioneye/static/js/main.js:1996-2010`

**Change:**
```javascript
function markHideIfNull(field, elemId) {
    var elem = $('#' + elemId);
    var sectionDiv = elem.parents('div.settings-section-title:eq(0)');

    // Check if value is null/undefined, but NOT false (false is valid)
    var value = (typeof field == 'string') ? dict[field] : null;
    var hideNull = (field === true) || (value === null || value === undefined);

    // Rest of function...
}
```

### Phase 3: Workaround - Manual Un-hide

**Quick workaround for immediate use:**

User can run this in browser console to manually show the toggle:

```javascript
// Find and show the LED toggle
var row = $('#disablePi5LedsSwitch').parents('tr:eq(0)')[0];
row._hideNull = false;
$(row).show();
```

This doesn't fix the root cause but makes it usable immediately.

### Phase 4: Permanent Fix Implementation

Based on diagnostic results from Phase 1, implement the appropriate fix from Phase 2.

**Testing checklist after fix:**
1. Restart MotionEye service
2. Clear browser cache completely
3. Open settings page
4. Verify `_disablePi5Leds` in JSON response: `curl http://localhost:8765/config/main/get/ | grep disablePi5Leds`
5. Verify element visibility: `$('#disablePi5LedsSwitch').parents('tr:eq(0)').is(':visible')`
6. Verify hide flags: `$('#disablePi5LedsSwitch').parents('tr:eq(0)')[0]._hideNull` should be `false`
7. Test toggle functionality: click checkbox, verify LEDs change state

## Files to Examine/Modify

### Investigation:
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/config/extensions.py` (lines 129-162)
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/config/camera/converters.py` (lines 193-232)
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/controls/ledctl.py` (lines 124-173)
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/handlers/config.py` (lines 105-144)

### Potential fixes:
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/controls/ledctl.py` - Add logging, ensure proper bool return
- `/Users/tshuey/Documents/GitHub/motioneye/motioneye/static/js/main.js` - Fix `markHideIfNull()` to handle boolean false

## Next Steps

1. **Diagnostic logging:** Add logging to trace the value through the entire flow
2. **Check JSON response:** Verify what the endpoint actually returns
3. **Implement fix:** Based on findings, apply appropriate solution
4. **Test thoroughly:** Ensure toggle appears and functions correctly
5. **Document:** Update implementation notes with findings

## Expected Outcome

After fix:
- `_disablePi5Leds: false` (or `true`) appears in `/config/main/get/` JSON response
- JavaScript correctly interprets the boolean value
- `hideNull` remains `false`
- Toggle is visible in the UI
- Clicking toggle successfully changes LED state
