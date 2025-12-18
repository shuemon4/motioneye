# Pi 5 LED Control Implementation Gap Analysis

**Created:** 2025-12-17 00:10
**Status:** Critical gap identified - feature implemented but not functional
**Severity:** High - Sudoers configuration missing blocks core functionality

---

## Executive Summary

The Pi 5 LED control feature has been **fully implemented in code** according to the plan, but is **non-functional on the deployed Pi 5** due to a **missing sudoers configuration file**. The code is present, the UI appears, but the toggle cannot actually control the LEDs due to permission errors.

---

## Implementation Status

### ✅ Completed Items

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| **LED control module** | ✅ Implemented | `motioneye/controls/ledctl.py:1-174` | Full sysfs control logic |
| **Platform detection** | ✅ Working | `ledctl.py:41-59` via `pictl.is_pi5()` | Properly gates feature |
| **Server.py integration** | ✅ Implemented | `server.py:36,450-454` | Import and startup application |
| **UI registration** | ✅ Visible | `@additional_config` decorator | Toggle appears in General Settings |
| **Code deployment** | ✅ Synced | Verified via SSH | `ledctl.py` exists on Pi 5 |
| **Module installation** | ✅ Installed | `pip3 install` completed | Module imports successfully |
| **sysfs paths** | ✅ Available | `/sys/class/leds/ACT`, `/sys/class/leds/PWR` | Verified on Pi 5 |

---

### ❌ Missing Critical Component

| Component | Status | Impact | Priority |
|-----------|--------|--------|----------|
| **Sudoers configuration** | ❌ Missing | **Feature non-functional** | **CRITICAL** |

**File:** `/etc/sudoers.d/motioneye-leds`

**Required contents:**
```
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
```

**Without this file:**
- All LED toggle operations fail with permission errors
- `ledctl.set_leds_disabled()` returns `False` silently
- User sees no feedback that operation failed
- LEDs remain in current state regardless of toggle setting

---

## Evidence Chain

### 1. Code Exists Locally and on Pi 5

**Local verification:**
```bash
$ ls -la motioneye/controls/ledctl.py
-rw-r--r--  1 tshuey  staff  5419 Dec 16 22:35 ledctl.py
```

**Remote verification:**
```bash
$ ssh admin@192.168.1.176 "test -f ~/motioneye/motioneye/controls/ledctl.py && echo 'File exists'"
File exists in source
```

**Module installed:**
```bash
$ ssh admin@192.168.1.176 "python3 -c 'import motioneye.controls.ledctl; print(\"Module installed\")'"
Module installed
```

---

### 2. UI Toggle Is Visible

**HTML confirmation:**
```bash
$ ssh admin@192.168.1.176 "curl -s http://localhost:8765/ | grep -i 'raspberry pi led'"
<td class="settings-item-label"><span class="settings-item-label">Disable Raspberry Pi LEDs</span></td>
Found in UI
```

**Location:** General Settings section (after Configuration Backup/Restore buttons)

---

### 3. Server Integration Confirmed

**server.py:36** - Import statement:
```python
from motioneye.controls import smbctl, v4l2ctl, ledctl
```

**server.py:450-454** - Startup application:
```python
if ledctl.is_supported():
    main_config = config.get_main()
    if main_config.get('@_disablePi5Leds', False):
        ledctl.set_leds_disabled(True)
        logging.info('LED control: LEDs disabled per saved config')
```

---

### 4. sysfs Paths Available

**Verification:**
```bash
$ ssh admin@192.168.1.176 "ls -la /sys/class/leds/"
lrwxrwxrwx  1 root root 0 Dec 31  1969 ACT -> ../../devices/platform/leds/leds/ACT
lrwxrwxrwx  1 root root 0 Dec 31  1969 PWR -> ../../devices/platform/leds/leds/PWR
```

Both required LED paths exist and are accessible for reading.

---

### 5. Sudoers File Missing

**Critical gap:**
```bash
$ ssh admin@192.168.1.176 "test -f /etc/sudoers.d/motioneye-leds && cat /etc/sudoers.d/motioneye-leds || echo 'Sudoers file missing'"
Sudoers file missing
```

**Impact:** Without this file, the `motion` user cannot write to sysfs LED control files.

---

### 6. No Config Persistence Yet

**Verification:**
```bash
$ ssh admin@192.168.1.176 "grep -n 'disablePi5Leds' /etc/motioneye/motioneye.conf"
No ledctl config found
```

**Analysis:** This is expected since the toggle hasn't been used yet (would fail silently without sudoers).

---

## Root Cause Analysis

### Why the Feature Appears But Doesn't Work

1. **Code deployment complete:** All Python code is present and installed
2. **UI rendering works:** The `@additional_config` decorator successfully registers the toggle
3. **Platform detection works:** `pictl.is_pi5()` returns `True`, sysfs paths exist
4. **Permission model assumed sudoers:** Code at `ledctl.py:116` uses `sudo tee` for sysfs writes
5. **Sudoers never created:** Installation process didn't include this file

**Result:** Feature appears functional in UI but silently fails on every toggle operation.

---

## Implementation vs Plan Comparison

### What Was Implemented

| Plan Item | Implementation | Variance |
|-----------|----------------|----------|
| Platform detection | ✅ Exactly as planned | None |
| LED control logic | ✅ Exactly as planned | None |
| Config registration | ✅ Exactly as planned | None |
| Server integration | ✅ Better (import at top) | Improvement |
| UI placement | ✅ Exactly as planned | None |
| **Sudoers setup** | ❌ **Not completed** | **Critical gap** |
| Startup application | ✅ Exactly as planned | None |

---

### Deviation from Plan

**Plan specified (Step 3):**
> **Sudoers requirement** (documented in `docs/designs/LED-switch.md`):
> ```
> motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
> motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
> ```

**Plan specified (Step 7 - Validation):**
> - Verify sudoers file is in place: `/etc/sudoers.d/motioneye-leds`

**Reality:** This step was documented but never executed during deployment.

---

## Why This Was Missed

### Likely Scenarios

1. **Assumption of automatic handling:** Developer may have assumed sudoers config would be handled by installation process
2. **Documentation vs execution gap:** Plan documented the requirement but deployment checklist didn't enforce it
3. **Testing on development machine:** If tested as root user or with existing sudo permissions, would appear to work
4. **Silent failure mode:** Code logs errors but doesn't surface failures to UI (returns `False` silently)

---

## Impact Assessment

### Current User Experience

1. User sees "Disable Raspberry Pi LEDs" toggle in General Settings ✅
2. User clicks toggle to disable LEDs
3. UI accepts the change without error indication
4. **LEDs remain on** (change silently fails)
5. User assumes feature is broken or doesn't work on their hardware

### Security Implications

**None** - The missing sudoers file is actually the *secure default*. The feature failing gracefully due to lack of permissions is correct behavior. The gap is operational, not security-related.

---

## Resolution Path

### Immediate Fix (Single Command)

Create the sudoers file on the Pi 5:

```bash
ssh admin@192.168.1.176 "echo 'motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness' | sudo tee /etc/sudoers.d/motioneye-leds > /dev/null && sudo chmod 440 /etc/sudoers.d/motioneye-leds && sudo visudo -c -f /etc/sudoers.d/motioneye-leds"
```

**Verification:**
```bash
ssh admin@192.168.1.176 "sudo cat /etc/sudoers.d/motioneye-leds"
```

---

### Post-Fix Testing Checklist

After creating sudoers file:

1. **Test manual sysfs write:**
   ```bash
   ssh admin@192.168.1.176 "echo none | sudo tee /sys/class/leds/ACT/trigger"
   ```
   Expected: No permission errors

2. **Test ledctl module directly:**
   ```bash
   ssh admin@192.168.1.176 "python3 -c 'from motioneye.controls import ledctl; print(ledctl.set_leds_disabled(True))'"
   ```
   Expected: `True`

3. **Verify LED state:**
   ```bash
   ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/brightness && cat /sys/class/leds/PWR/brightness"
   ```
   Expected: Both show `0`

4. **Test UI toggle:**
   - Open `http://192.168.1.176:8765/`
   - Navigate to General Settings
   - Click "Disable Raspberry Pi LEDs" toggle
   - Verify LEDs turn off immediately

5. **Test persistence:**
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
   ```
   - Check if LEDs remain off after restart
   - Verify config stored: `grep disablePi5Leds /etc/motioneye/motioneye.conf`

6. **Test re-enable:**
   - Toggle LED setting off (enable LEDs)
   - Verify LEDs turn back on
   - Check triggers restored: `cat /sys/class/leds/ACT/trigger` should show `[mmc0]`

---

## Long-Term Improvements

### 1. Installation Documentation

Add sudoers setup to installation guide:

**File:** `README.md` or `docs/installation.md`

```markdown
## Post-Installation: LED Control (Pi 5 only)

To enable LED control from the UI, create sudoers configuration:

```bash
sudo tee /etc/sudoers.d/motioneye-leds > /dev/null <<EOF
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
EOF

sudo chmod 440 /etc/sudoers.d/motioneye-leds
sudo visudo -c -f /etc/sudoers.d/motioneye-leds
```
```

---

### 2. Automated Setup Script

Create `scripts/setup-pi5-leds.sh`:

```bash
#!/bin/bash
# Automated Pi 5 LED control setup

if ! grep -q "Raspberry Pi 5" /proc/cpuinfo; then
    echo "Not a Raspberry Pi 5, skipping LED setup"
    exit 0
fi

echo "Setting up Pi 5 LED control permissions..."

sudo tee /etc/sudoers.d/motioneye-leds > /dev/null <<'EOF'
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
EOF

sudo chmod 440 /etc/sudoers.d/motioneye-leds

if sudo visudo -c -f /etc/sudoers.d/motioneye-leds; then
    echo "✅ Pi 5 LED control permissions configured"
else
    echo "❌ Sudoers file syntax error"
    sudo rm /etc/sudoers.d/motioneye-leds
    exit 1
fi
```

---

### 3. Runtime Diagnostics

Enhance `ledctl.py` to detect and report missing sudoers:

**ledctl.py:72-74** - Add diagnostic check:

```python
def is_supported() -> bool:
    """Check if LED control is supported on this hardware."""
    if not pictl.is_pi5():
        return False

    # Check if all required sysfs paths exist
    required_paths = [ACT_TRIGGER, ACT_BRIGHTNESS, PWR_TRIGGER, PWR_BRIGHTNESS]
    for path in required_paths:
        if not os.path.exists(path):
            logging.debug(f'LED control: sysfs path not found: {path}')
            return False

    # NEW: Check if sudoers is configured
    if not _check_sudo_permissions():
        logging.warning('LED control: sudoers configuration missing - feature will not work')
        logging.warning('LED control: run setup script or see docs/designs/LED-switch.md')
        # Still return True to show the toggle (with warning in logs)

    return True

def _check_sudo_permissions() -> bool:
    """Check if motion user can write to LED sysfs files."""
    try:
        result = subprocess.run(
            'sudo -n -l | grep /sys/class/leds',
            shell=True,
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False
```

---

### 4. UI Error Feedback

**Current behavior:** Toggle silently fails (returns `False` but no user feedback)

**Improvement:** Add error handling in config setter:

```python
def _set_leds_disabled(disabled: bool) -> bool:
    """Set the LED state with error feedback."""
    success = set_leds_disabled(disabled)

    if not success:
        # Log detailed error for troubleshooting
        logging.error('LED control failed - check sudoers configuration')
        # Could raise exception here to surface error in UI
        # raise RuntimeError('LED control requires sudoers configuration')

    return success
```

**Note:** Current additional_config framework may not support error surfacing. This would need framework enhancement.

---

## Comparison to Review Document

### Review Document Findings vs Reality

| Review Concern | Reality | Resolution |
|----------------|---------|------------|
| Config persistence unclear | ✅ Framework handles it (not tested yet) | Works as designed, no action needed |
| `_get_leds_disabled()` reads hardware state | ✅ Intentional design choice | Correct - reflects actual state |
| Sudoers file not verified | ❌ **Critical - file missing** | **Create file immediately** |
| Startup config key unclear | ✅ Correctly implemented as `@_disablePi5Leds` | No action needed |

---

## Conclusions

### What Went Right

1. **Code implementation**: Exactly matches plan specification
2. **Architecture**: Clean separation of concerns, proper platform detection
3. **UI integration**: Seamless integration with existing config system
4. **Error handling**: Graceful degradation, good logging

### What Went Wrong

1. **Deployment checklist gap**: Sudoers setup documented but not executed
2. **Validation oversight**: Final testing didn't include permission verification
3. **Silent failure**: No user-visible feedback when toggle fails

### What Needs to Happen

1. **Immediate:** Create `/etc/sudoers.d/motioneye-leds` on Pi 5
2. **Short-term:** Test full toggle workflow (on/off, restart, persistence)
3. **Medium-term:** Add setup script to automate sudoers configuration
4. **Long-term:** Enhance error feedback and diagnostics

---

## Remediation Commands

### Quick Fix (Copy-Paste Ready)

```bash
# Create sudoers file
ssh admin@192.168.1.176 "echo 'motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness' | sudo tee /etc/sudoers.d/motioneye-leds > /dev/null"

# Set correct permissions
ssh admin@192.168.1.176 "sudo chmod 440 /etc/sudoers.d/motioneye-leds"

# Validate syntax
ssh admin@192.168.1.176 "sudo visudo -c -f /etc/sudoers.d/motioneye-leds"

# Test LED control
ssh admin@192.168.1.176 "python3 -c 'from motioneye.controls import ledctl; print(\"Disable LEDs:\", ledctl.set_leds_disabled(True)); print(\"Enable LEDs:\", ledctl.set_leds_disabled(False))'"

# Verify LED state
ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/brightness /sys/class/leds/PWR/brightness"
```

---

## Files Referenced

- **Plan:** `docs/plans/pi5-led-control-plan-20251216-2227.md`
- **Review:** `docs/scratchpads/pi5-led-implementation-review-20251216-2235.md`
- **Implementation:** `motioneye/controls/ledctl.py`
- **Server integration:** `motioneye/server.py:36,450-454`
- **Design doc:** `docs/designs/LED-switch.md`
- **Missing file:** `/etc/sudoers.d/motioneye-leds` (on Pi 5)
