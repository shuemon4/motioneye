# Pi 5 LED Control Implementation Review

**Created:** 2025-12-16 22:35
**Plan Reviewed:** `docs/plans/pi5-led-control-plan-20251216-2227.md`

---

## Summary

Implementation is **mostly consistent** with the plan. The feature has been successfully implemented with proper platform detection, config persistence, and UI integration.

---

## Inconsistencies & Deviations

### 1. Config Storage Approach (Deviation from Plan)

**Plan specified (Step 4):**
```python
def _get_leds_disabled():
    return config.get_main().get('@_disablePi5Leds', False)

def _set_leds_disabled(value):
    set_leds_disabled(value)  # Apply sysfs changes
    main = config.get_main()
    main['@_disablePi5Leds'] = value
    config.set_main(main)  # Persist to config
```

**Actual implementation (ledctl.py:124-153):**
```python
def _get_leds_disabled():
    # Reads ACTUAL LED STATE from sysfs brightness values
    # Not from config storage
    try:
        with open(ACT_BRIGHTNESS, 'r') as f:
            act_brightness = int(f.read().strip())
        with open(PWR_BRIGHTNESS, 'r') as f:
            pwr_brightness = int(f.read().strip())
        return act_brightness == 0 and pwr_brightness == 0
    except Exception:
        return False

def _set_leds_disabled(disabled):
    # Only applies sysfs changes, does NOT persist to config
    return set_leds_disabled(disabled)
```

**Impact:**
- **Positive**: UI always reflects actual hardware state rather than stale config
- **Negative**: Config persistence relies entirely on the additional_config framework's automatic persistence (undocumented assumption)
- **Risk**: If the framework doesn't auto-persist, settings won't survive restart

**Status:** ⚠️ **Needs verification** - Confirm that `@additional_config` framework automatically persists bool values to main config with `@_` prefix.

---

### 2. Startup Application Logic (Minor inconsistency)

**Plan specified (Step 6):**
```python
# In server.py run() function, after start_motion() is called (~line 447)
from motioneye.controls import ledctl
if ledctl.is_supported():
    main_config = config.get_main()
    if main_config.get('@_disablePi5Leds', False):
        ledctl.set_leds_disabled(True)
        logging.info('LED control: LEDs disabled per saved config')
```

**Actual implementation (server.py:449-454):**
- Import is at top of file (line 36), not inline
- Logic is identical otherwise

**Impact:** None - proper placement, cleaner code organization

**Status:** ✅ **Better than planned**

---

### 3. Config Storage Key Name

**Plan referenced:** `@_disablePi5Leds`

**Issue:** The plan assumes the framework automatically adds `@_` prefix to the config function name (`disablePi5Leds` → `@_disablePi5Leds`).

**Actual behavior:** Unknown - needs verification that:
1. The `@additional_config` decorator handles persistence
2. The storage key matches what startup code expects

**Status:** ⚠️ **Needs runtime verification**

---

## Verification Checklist

To confirm implementation correctness:

- [ ] Toggle LED setting ON in UI → verify config file contains `@_disablePi5Leds: true`
- [ ] Restart MotionEye → verify LEDs remain off
- [ ] Toggle LED setting OFF → verify config updates to `false`
- [ ] Restart again → verify LEDs remain on
- [ ] Check logs for "LED control: LEDs disabled per saved config" at startup

---

## Files Modified (vs Plan)

| File | Plan Action | Actual Status |
|------|-------------|---------------|
| `motioneye/controls/ledctl.py` | **Create** | ✅ Created |
| `motioneye/server.py` | **Modify** - Import, startup logic | ✅ Modified (import at top) |
| `motioneye/templates/partials/settings/_general.html` | **Modify** - Move config loop | ✅ Modified |
| `docs/designs/LED-switch.md` | **Modify** - Add UI toggle note | ✅ Modified (user updated) |

---

## Additional Notes

### Sudoers Requirement

Plan specifies sudoers file at `/etc/sudoers.d/motioneye-leds`:
```
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
```

**Status:** ⚠️ **Not verified** - Check if this file exists on target Pi 5

### Implementation Quality

**Strengths:**
- Proper platform detection via `pictl.is_pi5()`
- Graceful degradation if sysfs unavailable
- Clean separation of concerns (ledctl module)
- Good error handling and logging

**Concerns:**
- Reliance on undocumented `@additional_config` persistence behavior
- `_get_leds_disabled()` reads hardware state instead of config (could cause UI/config drift)

---

## Recommendations

1. **Test persistence:** Verify config survives restart
2. **Document framework behavior:** Clarify how `@additional_config` handles persistence
3. **Consider hybrid approach:** Read from config first, fall back to hardware state
4. **Add sudoers check:** Log warning if sudoers file missing at startup
