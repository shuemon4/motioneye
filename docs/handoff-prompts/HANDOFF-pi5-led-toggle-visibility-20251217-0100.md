# HANDOFF: Pi 5 LED Toggle Visibility Bug Investigation

**Created:** 2025-12-17 01:00
**Status:** Ready for execution
**Investigation Plan:** `docs/analysis/pi5-LED-bug-investigation.md`
**Context:** LED control feature fully implemented but toggle hidden in browser

---

## Background

The Pi 5 LED control feature was successfully implemented and deployed:
- ✅ **Code deployed:** `motioneye/controls/ledctl.py` installed on Pi 5
- ✅ **Sudoers configured:** `/etc/sudoers.d/motioneye-leds` in place and working
- ✅ **Functional backend:** Direct Python calls to `ledctl.set_leds_disabled()` work perfectly
- ✅ **Server HTML rendering:** Toggle appears in HTML source (`curl` shows it)
- ✅ **Module imported:** `ledctl` imported in `server.py:36`, decorator registered

**However:** The toggle is **invisible in the browser** due to JavaScript hiding it with `display: none`.

---

## Problem Summary

**What user sees:** No LED toggle in General Settings (after Backup/Restore buttons)

**Actual state:**
- Element EXISTS in DOM: `$('#disablePi5LedsSwitch').length` = 1
- Element is HIDDEN: `.css('display')` = "none"
- Hide flag: `_hideNull = true` (others false)

**Root cause:** JavaScript's `markHideIfNull()` function hides the element because the config value `_disablePi5Leds` is missing or null in the AJAX response from `/config/main/get/`.

---

## Investigation Findings

### User Confirmation (via browser console)

1. Logged in as admin: `isAdmin()` returns `true`
2. Additional configs exist: `$('.settings-item.additional-config').length` ≥ 1
3. LED toggle exists: `$('#disablePi5LedsSwitch').length` = 1
4. Element hidden: `$('#disablePi5LedsSwitch').parents('tr:eq(0)').is(':visible')` = false
5. Display CSS: `$('#disablePi5LedsSwitch').parents('tr:eq(0)').css('display')` = "none"
6. Hide flags: `{hideNull: true, hideLogic: false, hideMinimized: false}`

### Technical Analysis

**Expected flow:**
1. `config.get_main()` → calls `_get_additional_config()` → calls `_get_leds_disabled()` → stores in `main_config['@_disablePi5Leds']`
2. `main_dict_to_ui()` → copies `@_disablePi5Leds` to `ui['_disablePi5Leds']`
3. JSON response includes `_disablePi5Leds: false`
4. JavaScript sees value and doesn't hide element

**What's happening:**
- `_disablePi5Leds` is missing/null in JSON response
- JavaScript treats it as undefined
- `markHideIfNull()` sets `_hideNull = true`
- Element hidden with `display: none`

---

## Your Task

Execute the investigation plan in `docs/analysis/pi5-LED-bug-investigation.md` to diagnose and fix the issue.

### Phase 1: Diagnostic Verification (Start Here)

**Goal:** Confirm whether `_disablePi5Leds` appears in the JSON response from `/config/main/get/`

**Action 1:** Check the config API response directly

```bash
ssh admin@192.168.1.176 "curl -s 'http://localhost:8765/config/main/get/' | python3 -m json.tool" | grep -i led
```

**Expected:** Should find `"_disablePi5Leds": false` (or true)
**If missing:** Proceed to diagnostic logging

**Action 2:** Add diagnostic logging to trace the value

Add logging to `motioneye/config/extensions.py` in `_get_additional_config()` function (around line 140):

```python
# After line 141: get_func_values = collections.OrderedDict((f, f(*args)) for f in get_funcs)
logging.debug(f'Additional config getter results: {dict(get_func_values)}')

# After line 161: data['@_' + name] = get_func_values.get(config['get'])
logging.debug(f"Set additional config: @_{name} = {data.get('@_' + name)}")
```

Add logging to `motioneye/controls/ledctl.py` in `_get_leds_disabled()` (line 135):

```python
disabled = act_brightness == 0 and pwr_brightness == 0
logging.debug(f'LED state: ACT={act_brightness}, PWR={pwr_brightness}, disabled={disabled}')
return disabled
```

**Action 3:** Deploy and test

```bash
# Sync code
rsync -avz --exclude='.git' --exclude='__pycache__' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

# Install
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

# Restart with logging
ssh admin@192.168.1.176 "sudo systemctl restart motioneye && sleep 3 && sudo journalctl -u motioneye -n 100 --no-pager | grep -i led"
```

**Action 4:** Trigger config load and check logs

```bash
# Access the config endpoint to trigger getter
ssh admin@192.168.1.176 "curl -s 'http://localhost:8765/config/main/get/' > /dev/null"

# Check logs for diagnostic output
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager | grep -E '(LED|additional config|disablePi5)'"
```

---

### Phase 2: Implement Fix (Based on Findings)

Once you've identified the root cause from Phase 1, apply the appropriate fix:

#### Scenario A: Value is False but Missing from JSON

**If logs show:** Getter is called, returns `False`, but value missing from JSON response

**Fix:** Issue is likely in JSON serialization or the getter not being in the `get_funcs` set

Check `motioneye/config/camera/converters.py` `main_dict_to_ui()` function (lines 226-230). Add logging:

```python
# In main_dict_to_ui(), after line 230
for name, value in list(data.items()):
    if not name.startswith('@_'):
        continue
    logging.debug(f"Copying additional config to UI: {name} -> {name[1:]} = {value}")
    ui[name[1:]] = value
```

#### Scenario B: Getter Not Being Called

**If logs show:** No LED state logs, getter never called

**Fix:** Decorator registration issue or `is_supported()` returning False

Verify:
```bash
ssh admin@192.168.1.176 "python3 -c '
from motioneye.controls import ledctl
from motioneye.config.extensions import _additional_config_funcs

print(\"is_supported:\", ledctl.is_supported())
print(\"Functions registered:\", len(_additional_config_funcs))
for func in _additional_config_funcs:
    result = func()
    if result:
        print(f\"  - {result.get(\"name\")}: has_getter={result.get(\"get\") is not None}\")
'"
```

#### Scenario C: JavaScript Treats False as Null

**If logs show:** Value is in JSON as `false` but JS still hides it

**Fix:** Modify `motioneye/static/js/main.js` `markHideIfNull()` function (line 1999):

```javascript
// OLD:
var hideNull = (field === true) || (typeof field == 'string' && dict[field] == null);

// NEW:
var value = (typeof field == 'string') ? dict[field] : null;
var hideNull = (field === true) || (value === null || value === undefined);
```

---

### Phase 3: Test and Verify

After implementing the fix:

1. **Deploy changes:**
   ```bash
   rsync -avz --exclude='.git' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/
   ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"
   ```

2. **Verify JSON response:**
   ```bash
   ssh admin@192.168.1.176 "curl -s 'http://localhost:8765/config/main/get/' | python3 -c 'import sys, json; d=json.load(sys.stdin); print(\"_disablePi5Leds:\", d.get(\"_disablePi5Leds\", \"MISSING\"))'"
   ```

3. **Verify in browser:**
   - Clear browser cache completely
   - Open MotionEye settings
   - Check console: `$('#disablePi5LedsSwitch').parents('tr:eq(0)').is(':visible')`
   - Should return `true`

4. **Test functionality:**
   - Click the toggle
   - Verify LEDs turn off immediately
   - Check state: `ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/brightness /sys/class/leds/PWR/brightness"`
   - Both should be `0` when disabled

---

## Quick Workaround (If Needed)

While investigating, user can manually show the toggle in browser console:

```javascript
var row = $('#disablePi5LedsSwitch').parents('tr:eq(0)')[0];
row._hideNull = false;
$(row).show();
```

This makes it usable immediately but doesn't fix the root cause.

---

## Environment Details

- **Pi 5 IP:** 192.168.1.176
- **SSH user:** admin (passwordless key configured)
- **MotionEye service:** systemd unit `motioneye`
- **Config location:** `/etc/motioneye/motioneye.conf`
- **Web interface:** `http://192.168.1.176:8765/`
- **Sudoers file:** `/etc/sudoers.d/motioneye-leds` (already configured ✅)

---

## Key Files

**Investigation:**
- `motioneye/config/extensions.py:129-162` - `_get_additional_config()`
- `motioneye/config/camera/converters.py:193-232` - `main_dict_to_ui()`
- `motioneye/controls/ledctl.py:124-173` - Getter and config registration
- `motioneye/handlers/config.py:105-144` - Config API handler

**Potential fixes:**
- `motioneye/controls/ledctl.py` - Add logging, ensure bool return
- `motioneye/static/js/main.js:1996-2010` - Fix `markHideIfNull()`
- `motioneye/config/extensions.py` - Add diagnostic logging

---

## Success Criteria

- [ ] Identified why `_disablePi5Leds` is missing from JSON response
- [ ] Implemented appropriate fix based on diagnosis
- [ ] Toggle visible in browser without manual intervention
- [ ] Toggle functionality works (LEDs respond to clicks)
- [ ] Fix documented in investigation file
- [ ] Changes committed to git

---

## Notes

- Backend LED control already works perfectly when called directly
- Sudoers permissions already configured and verified
- Issue is purely in the server→client config data flow
- Most likely culprit: getter function not being called or value being filtered

---

## Next Steps After Fix

Once the bug is resolved:
1. Document findings in `docs/analysis/pi5-LED-bug-investigation.md`
2. Remove diagnostic logging (or leave at debug level)
3. Create summary in `docs/summaries/`
4. Update main completion document if needed

---

**Start with Phase 1, Action 1** - check the JSON response. Everything else follows from what you find there.
