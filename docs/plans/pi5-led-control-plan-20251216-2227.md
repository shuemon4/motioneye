# Raspberry Pi 5 LED Control Plan

**Created:** 2025-12-16 22:27
**Updated:** 2025-12-16
**Status:** Ready for implementation
**Scope:** Add a Pi 5-only General Settings toggle that disables all Pi LEDs without requiring restart, using the sysfs approach outlined in `docs/designs/LED-switch.md`.

---

## Executive Summary

Expose a single "Disable Raspberry Pi LEDs" switch in General Settings that immediately turns off the Pi 5 `ACT` and `PWR` LEDs by writing to `/sys/class/leds/*` (no reboot). Persist the preference in main config, apply it at startup, and hide the control when not on Pi 5. Use the LED-switch design doc for command details (set `trigger` to `none` then set `brightness` to `0`; restore defaults on re-enable).

---

## Goals & Constraints

- Pi 5 only: Do not show or act on the toggle on other hardware.
- No reboot required: Changes must apply as soon as the toggle is saved.
- Persisted: Setting survives restarts and reapplies on service start.
- Safety: Avoid breaking main config; fail gracefully if sysfs paths unavailable.
- UI: Control lives in General Settings after the Configuration Backup/Restore buttons, with a separator line before and after.

---

## Approach Overview

1. Reuse Pi detection (`motioneye.controls.pictl`) to gate feature visibility and behavior.
2. Implement a small LED controller that executes the `LED-switch.md` sysfs writes (supports off/on, validates paths, and logs failures).
3. Register a new General Settings boolean via the additional-config system so it flows through main config get/set and the UI form.
4. Hot-apply LED state when the setting changes and at startup if stored as enabled.

---

## Implementation Plan

### 1) Module Registration
- Create `motioneye/controls/ledctl.py` with the LED control logic (see step 2).
- **Critical**: Import `ledctl` in `motioneye/server.py` (alongside other controls like `smbctl`, `v4l2ctl`) so that the `@additional_config` decorator registers the config item on startup.

### 2) Platform Detection & Feature Flag
- The `@additional_config` decorated function returns `None` when `pictl.is_pi5()` is `False`, hiding the toggle on non-Pi5 hardware.
- No changes needed to `handlers/main.py` - the additional config system handles visibility automatically.

### 3) LED Control Helper (backend)
- Create `motioneye/controls/ledctl.py` with:
  - Constants for `/sys/class/leds/ACT` and `/sys/class/leds/PWR`.
  - `is_supported()` that checks `pictl.is_pi5()` and verifies sysfs paths exist.
  - `set_leds_disabled(disabled: bool)` implementing the design doc steps:
    - **Off**: set `trigger` to `none`, then write `brightness` to `0` for both LEDs.
    - **On**: restore `trigger` to `mmc0` (ACT) and `default-on` (PWR).
  - Use `sudo tee` via subprocess for sysfs writes (MotionEye runs as `motion` user).
  - Logging + error handling; return success/failure.
- **Sudoers requirement** (documented in `docs/designs/LED-switch.md`):
  ```
  motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
  motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
  ```

### 4) Config Surface (General Settings)
- Register a new additional config via `@additional_config` decorator:
  ```python
  @additional_config
  def disablePi5Leds():
      if not is_supported():
          return None  # Hide on non-Pi5 or missing sysfs

      return {
          'label': 'Disable Raspberry Pi LEDs',
          'description': 'turns off the red power and green activity LEDs immediately (no reboot required)',
          'type': 'bool',
          'section': 'general',
          'get': _get_leds_disabled,
          'set': _set_leds_disabled,
      }
  ```
- **`_get_leds_disabled()`**: Read from `config.get_main().get('@_disablePi5Leds', False)`
- **`_set_leds_disabled(value)`**:
  1. Call `set_leds_disabled(value)` to apply sysfs changes
  2. Update main config: `main = config.get_main(); main['@_disablePi5Leds'] = value; config.set_main(main)`
- The additional config system automatically handles the `@_` prefix for storage.

### 5) UI Wiring & Placement
- Modify `motioneye/templates/partials/settings/_general.html` to render the LED toggle **after** the Configuration Backup/Restore buttons:
  - Move the `{% for config in main_sections.get('general', {}).get('configs', []) %}` loop to the end of the table (after the Restore button row).
  - Add a separator row before the loop (matching existing separator pattern).
  - Add a separator row after the loop to close the section cleanly.
- No custom markup needed - the `config_item` macro renders bool types as checkbox toggles automatically.
- No JavaScript changes required - additional configs are already handled by the existing serialization/prefill paths.

### 6) Startup Application & Resilience
- In `motioneye/server.py` `run()` function, after `start_motion()` is called (~line 447):
  ```python
  # Apply LED state if configured
  from motioneye.controls import ledctl
  if ledctl.is_supported():
      main_config = config.get_main()
      if main_config.get('@_disablePi5Leds', False):
          ledctl.set_leds_disabled(True)
          logging.info('LED control: LEDs disabled per saved config')
  ```
- If sysfs writes fail at startup, log a warning but continue startup.
- If sysfs writes fail on save, log the error and return failure to surface in the UI.

### 7) Validation & Documentation
- Manual validation on Pi 5:
  - Toggle on (disable LEDs) → verify `ACT/brightness` and `PWR/brightness` are `0` and triggers are `none`.
  - Toggle off (enable LEDs) → verify triggers return to `mmc0` and `default-on`.
  - Restart MotionEye → confirm LED state reapplies based on saved config.
- Update `docs/designs/LED-switch.md` to reference the new UI toggle as the preferred method.
- Verify sudoers file is in place: `/etc/sudoers.d/motioneye-leds`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Permission denied writing to sysfs | Sudoers config documented; clear error logging; feature hidden if `is_supported()` fails |
| Non-Pi5 hardware | Feature gated entirely by `pictl.is_pi5()` check |
| State drift after restarts | Startup hook in `server.py` reapplies saved state |

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `motioneye/controls/ledctl.py` | **Create** - LED control logic and `@additional_config` registration |
| `motioneye/server.py` | **Modify** - Import `ledctl`, add startup LED state application |
| `motioneye/templates/partials/settings/_general.html` | **Modify** - Move additional config loop to end, add separators |
| `docs/designs/LED-switch.md` | **Modify** - Add note about UI toggle |
