# Handoff Prompt: Pi 5 LED Control Implementation

**Created:** 2025-12-16 23:50
**Context:** Implement UI toggle for controlling Raspberry Pi 5 LEDs
**Plan Document:** `docs/plans/pi5-led-control-plan-20251216-2227.md`
**Design Document:** `docs/designs/LED-switch.md`

---

## Task Overview

Implement a General Settings toggle in the MotionEye UI that allows users to disable/enable the Raspberry Pi 5's power and activity LEDs without requiring a reboot. The feature should:

- Only appear on Pi 5 hardware
- Persist across restarts
- Apply changes immediately via sysfs
- Use the established additional-config pattern

---

## Implementation Checklist

Follow the plan in `docs/plans/pi5-led-control-plan-20251216-2227.md` step by step:

### 1. Create LED Control Module

**File:** `motioneye/controls/ledctl.py`

Create a new module with:
- Constants for LED sysfs paths (`/sys/class/leds/ACT`, `/sys/class/leds/PWR`)
- `is_supported()` - checks `pictl.is_pi5()` and verifies sysfs paths exist
- `set_leds_disabled(disabled: bool)` - applies LED state using `sudo tee` subprocess
- `_get_leds_disabled()` - reads from `config.get_main().get('@_disablePi5Leds', False)`
- `_set_leds_disabled(value)` - applies sysfs change AND updates main config
- `@additional_config` decorator function `disablePi5Leds()` - returns config dict or None

**Reference implementations:**
- `motioneye/controls/tzctl.py:127-145` (timeZone additional config pattern)
- `docs/designs/LED-switch.md` (sysfs commands for LED control)

**Key details:**
- Use `echo VALUE | sudo tee PATH > /dev/null` pattern for sysfs writes
- Off: set trigger to `none`, then brightness to `0`
- On: set trigger to `mmc0` (ACT) and `default-on` (PWR)
- Return success/failure for error handling

### 2. Register Module on Startup

**File:** `motioneye/server.py`

Add import near line 36 (with other controls):
```python
from motioneye.controls import smbctl, v4l2ctl, ledctl
```

This ensures the `@additional_config` decorator runs and registers the config item.

### 3. Apply LED State at Startup

**File:** `motioneye/server.py`

In the `run()` function, after `start_motion()` call (~line 447), add:
```python
# Apply LED state if configured
from motioneye.controls import ledctl
if ledctl.is_supported():
    main_config = config.get_main()
    if main_config.get('@_disablePi5Leds', False):
        ledctl.set_leds_disabled(True)
        logging.info('LED control: LEDs disabled per saved config')
```

### 4. Update UI Template

**File:** `motioneye/templates/partials/settings/_general.html`

Move the additional config rendering loop to the end (after Restore button):
- Currently at lines 37-39, move to after line 84
- Add separator before the loop (copy pattern from line 40)
- Add separator after the loop
- Final structure:
  ```
  ... existing rows ...
  </tr>
  <tr class="settings-item">
      <td colspan="100"><div class="settings-item-separator"></div></td>
  </tr>
  {% for config in main_sections.get('general', {}).get('configs', []) %}
      {{config_item(config)}}
  {% endfor %}
  <tr class="settings-item">
      <td colspan="100"><div class="settings-item-separator"></div></td>
  </tr>
  ```

### 5. Update Documentation

**File:** `docs/designs/LED-switch.md`

Add a note at the top recommending the new UI toggle as the preferred method, with the manual script approach as an alternative for advanced users.

---

## Testing Checklist

**Before testing - Ask user if Pi 5 is powered on!**

### Deployment to Pi 5
```bash
# Sync code
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

# Install
ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

# Restart service
ssh admin@192.168.1.176 "sudo systemctl restart motioneye"

# Check logs
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"
```

### Functional Testing

1. **UI Visibility**
   - Open MotionEye UI: `http://192.168.1.176:8765/`
   - Navigate to General Settings
   - Verify "Disable Raspberry Pi LEDs" toggle appears after Backup/Restore buttons
   - Verify toggle has separators before and after

2. **Toggle Off (Disable LEDs)**
   - Enable the toggle
   - Click Apply
   - Verify LEDs turn off immediately
   - SSH verify: `ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/brightness && cat /sys/class/leds/PWR/brightness"`
   - Should both return `0`
   - Verify triggers: `ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/trigger && cat /sys/class/leds/PWR/trigger"`
   - Should both show `none`

3. **Toggle On (Enable LEDs)**
   - Disable the toggle
   - Click Apply
   - Verify LEDs turn back on
   - SSH verify triggers: should show `[mmc0]` and `[default-on]`

4. **Persistence Test**
   - Enable toggle (LEDs off)
   - Restart MotionEye: `ssh admin@192.168.1.176 "sudo systemctl restart motioneye"`
   - Check logs for "LED control: LEDs disabled per saved config"
   - Verify LEDs remain off after restart

### Error Cases

5. **Permission Test** (if sudoers not configured)
   - Verify error message in UI or logs if sudo fails
   - Confirm feature is hidden if `is_supported()` returns False

---

## Prerequisites Verified

✅ **Sudoers file exists**: `/etc/sudoers.d/motioneye-leds`
```
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
```

✅ **Platform**: Raspberry Pi 5 + Pi Camera v3
✅ **Design validated**: Manual LED control tested and working per `docs/designs/LED-switch.md`

---

## Expected Outcomes

After successful implementation:

1. New file created: `motioneye/controls/ledctl.py` (~150 lines)
2. Three files modified:
   - `motioneye/server.py` (2 small additions)
   - `motioneye/templates/partials/settings/_general.html` (moved loop + separators)
   - `docs/designs/LED-switch.md` (added UI note)
3. UI shows new toggle in General Settings (Pi 5 only)
4. LEDs can be controlled without reboot
5. Setting persists across restarts

---

## Key Code Patterns to Follow

### Additional Config Pattern
See `motioneye/controls/tzctl.py:127-145` for the exact pattern:
```python
from motioneye.config import additional_config

@additional_config
def disablePi5Leds():
    if not is_supported():
        return None

    return {
        'label': 'Disable Raspberry Pi LEDs',
        'description': 'turns off the red power and green activity LEDs immediately (no reboot required)',
        'type': 'bool',
        'section': 'general',
        'get': _get_leds_disabled,
        'set': _set_leds_disabled,
    }
```

### Sysfs Write Pattern
See `docs/designs/LED-switch.md:63-66` for validated commands:
```python
# Disable LEDs
subprocess.run('echo none | sudo tee /sys/class/leds/ACT/trigger > /dev/null', shell=True)
subprocess.run('echo 0 | sudo tee /sys/class/leds/ACT/brightness > /dev/null', shell=True)
# Repeat for PWR
```

---

## Notes

- No translation files need updating - label/description are in English only for now
- No JavaScript changes required - additional config system handles serialization automatically
- The `@_` prefix for config keys is added automatically by the additional config system
- Feature is completely invisible on non-Pi5 hardware due to `is_supported()` check

---

## Questions to Ask Before Starting

1. Is the Pi 5 at 192.168.1.176 powered on and accessible?
2. Should I run the deployment commands, or do you want to review the code first?
