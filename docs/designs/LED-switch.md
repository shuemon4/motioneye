# Control Raspberry Pi 5 LEDs

**Recommended**: Use the "Disable Raspberry Pi LEDs" toggle in **General Settings** for easy UI-based control (no SSH required).

As an alternative, advanced users can manually manage LED control scripts as described below.

## Overview

MotionEye provides "Run Command" hooks that can execute shell commands:
- On motion start/end
- On startup (via a dummy camera)
- Via scripts tied to camera enable/disable

The integrated UI toggle leverages the sysfs interface to control the Pi 5's LEDs for power saving without reboot.

---

## Raspberry Pi 5 LED Configuration

### Available LEDs

On Pi 5, the LED paths are:
```bash
/sys/class/leds/ACT   # Green activity LED (SD card activity)
/sys/class/leds/PWR   # Red power LED
```

**Note**: Pi 4 used `led0` and `led1`, but Pi 5 uses `ACT` and `PWR`.

### Verify LED paths

```bash
ls -la /sys/class/leds/
```

You should see `ACT` and `PWR` symlinks.

### Check current LED status

```bash
# Activity LED
cat /sys/class/leds/ACT/trigger      # Should show [mmc0] (SD card trigger)
cat /sys/class/leds/ACT/brightness   # 0 or 1

# Power LED
cat /sys/class/leds/PWR/trigger      # Should show [default-on]
cat /sys/class/leds/PWR/brightness   # 0 or 1
```

---

## Step 1: Create LED Control Scripts

### Turn LEDs Off Script

Create `/usr/local/bin/leds-off.sh`:

```bash
sudo nano /usr/local/bin/leds-off.sh
```

```bash
#!/bin/bash
# Disable LEDs for power saving
echo none | sudo tee /sys/class/leds/ACT/trigger > /dev/null
echo 0 | sudo tee /sys/class/leds/ACT/brightness > /dev/null
echo none | sudo tee /sys/class/leds/PWR/trigger > /dev/null
echo 0 | sudo tee /sys/class/leds/PWR/brightness > /dev/null
```

### Turn LEDs On Script

Create `/usr/local/bin/leds-on.sh`:

```bash
sudo nano /usr/local/bin/leds-on.sh
```

```bash
#!/bin/bash
# Restore LEDs to default behavior
echo mmc0 | sudo tee /sys/class/leds/ACT/trigger > /dev/null
echo default-on | sudo tee /sys/class/leds/PWR/trigger > /dev/null
```

### Make Scripts Executable

```bash
sudo chmod +x /usr/local/bin/leds-off.sh
sudo chmod +x /usr/local/bin/leds-on.sh
```

---

## Step 2: Configure Passwordless Sudo for Motion User

The `motion` user (which runs MotionEye) needs permission to control LEDs without a password prompt.

Create `/etc/sudoers.d/motioneye-leds`:

```bash
sudo visudo -f /etc/sudoers.d/motioneye-leds
```

Add these lines:

```
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/trigger
motion ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/class/leds/*/brightness
```

Save and exit. Verify syntax:

```bash
sudo visudo -c -f /etc/sudoers.d/motioneye-leds
```

---

## Step 3: Test LED Control

Test the scripts manually before integrating with MotionEye:

```bash
# Turn LEDs off
sudo /usr/local/bin/leds-off.sh

# Verify they're off (both should show 0)
cat /sys/class/leds/ACT/brightness
cat /sys/class/leds/PWR/brightness

# Turn LEDs back on
sudo /usr/local/bin/leds-on.sh

# Verify they're on
cat /sys/class/leds/ACT/trigger    # Should show [mmc0]
cat /sys/class/leds/PWR/trigger    # Should show [default-on]
```

---

## Step 4: Integrate with MotionEye UI

### Option A: Use Motion Notifications

1. Open the MotionEye web UI
2. Select a camera (or create a dummy camera for system control)
3. Navigate to **Motion Notifications**
4. Under **Run A Command**, add:
   - **On motion start**: `/usr/local/bin/leds-off.sh`
   - **On motion end**: `/usr/local/bin/leds-on.sh`

### Option B: Use File Storage Hooks

1. Navigate to **File Storage** section
2. Under **Run A Command**:
   - Set command to `/usr/local/bin/leds-off.sh` (for disabling during recording)

### Option C: Startup/Shutdown Control

To disable LEDs at MotionEye startup:
1. Create a dummy camera
2. Set **Run A Command** on camera enable to `/usr/local/bin/leds-off.sh`

---

## Verification

After setup, verify LED control works from MotionEye:
1. Trigger the configured event (motion, camera enable, etc.)
2. Check LED status:
   ```bash
   ssh admin@192.168.1.176 "cat /sys/class/leds/ACT/brightness && cat /sys/class/leds/PWR/brightness"
   ```
3. Both should return `0` when disabled

---

## Summary

✅ **No reboot required** - Changes take effect immediately
✅ **Persistent** - Triggers remain active across reboots
✅ **UI-based control** - No SSH needed after initial setup
✅ **Secure** - Sudoers restricts motion user to LED control only

## Important Notes

1. **Trigger vs Brightness**: Pi 5 LEDs use triggers (event-based control). Setting `trigger` to `none` is required before changing brightness.
2. **Power Saving**: Disabling LEDs provides minimal power savings (~10-20mW) but is useful for stealth recording or light-sensitive environments.
3. **Default Behavior**: If scripts fail, LEDs will remain in their last state. Reboot will restore default triggers.
