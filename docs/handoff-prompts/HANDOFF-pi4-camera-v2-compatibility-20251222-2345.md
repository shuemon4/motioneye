# Handoff: Pi 4 + Camera v2 Backward Compatibility Implementation

## Context

MotionEye was recently updated specifically for Pi 5 + Camera v3 (libcamera/IMX708). Analysis revealed several gaps for Pi 4 + Camera v2 (IMX219) operation. This task implements fixes for those gaps.

**Target Configuration**: Pi 4 + Bookworm (32-bit) + Camera v2 (IMX219) using libcamera

---

## Your Task

Execute the implementation plan documented in:
```
docs/plans/pi4-camera-v2-compatibility-plan-20251222-2345.md
```

Additional analysis notes are in:
```
docs/scratchpads/pi4-camera-v2-compatibility-analysis-20251222-2330.md
```

---

## Implementation Summary

### Phase 1: Improve Detection Robustness (Priority: HIGH)

**File: `motioneye/controls/rpicamctl.py`**
- Add validation that `rpicam-hello --list-cameras` succeeds AND returns cameras
- Upgrade logging from DEBUG to WARNING when detection fails
- Ensure `clear_cache()` is called appropriately

**File: `motioneye/controls/mmalctl.py`**
- Add try/except around vcgencmd calls with graceful fallback
- Log at WARNING level if vcgencmd not found

**File: `motioneye/controls/pictl.py`**
- Add startup cache clear mechanism
- Add validation that selected interface actually works

### Phase 2: Sensor-Specific Defaults (Priority: MEDIUM)

**File: `motioneye/config/defaults.py`**
- Add sensor-specific resolution defaults:
  - IMX708 (v3): 1920x1080 (keep current)
  - IMX219 (v2): 1280x720 or 1640x1232
  - Other sensors: 640x480 conservative default

### Phase 3: Error Visibility (Priority: MEDIUM)

- Surface camera detection errors to UI (not just empty list)
- Add troubleshooting hints based on platform

---

## Key Technical Details

### Sensor Detection
The sensor is identified via `rpicam-hello --list-cameras` output parsing:
```
0 : imx219 [3280x2464 10-bit] (/base/soc/i2c0mux/i2c@1/imx219@10)
```

Sensor mapping in `rpicamctl.py`:
```python
_SENSOR_NAMES = {
    'imx708': 'Camera Module 3',    # Has autofocus
    'imx219': 'Camera Module 2',    # No autofocus
    ...
}
_AUTOFOCUS_SENSORS = {'imx708'}     # Only v3 has AF
```

### Interface Selection Logic
In `pictl.py`:
```python
if rpicamctl.is_rpicam_available():  # rpicam-hello exists?
    return 'libcamera'
elif get_pi_model():  # Is this a Pi?
    return 'mmal'
else:
    return 'v4l2'
```

**Gap**: No validation that libcamera actually works with connected camera.

### What's Already Working
- Autofocus UI correctly hidden for Camera v2 (IMX219 not in `_AUTOFOCUS_SENSORS`)
- Hardware codec detection (v4l2m2m vs OMX)
- libcamera path selection on Bookworm

---

## Testing

Test hardware is available: Pi 4 + Camera v2

After implementation, test on Pi 4:
1. `rpicam-hello --list-cameras` should detect IMX219
2. MotionEye camera enumeration should list Camera v2
3. Add camera via UI should work
4. MJPEG stream should work
5. Autofocus controls should be hidden
6. Disconnect camera and verify error message appears (not just empty list)

### Deployment Commands
```bash
# Sync to Pi 4
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.246:~/motioneye/

# Install
ssh admin@192.168.1.246 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

# Restart
ssh admin@192.168.1.246 "sudo systemctl restart motioneye"

# Check logs
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 50 --no-pager"
```

**IMPORTANT**: Ask the user if the Pi 4 is powered on before attempting SSH connections.

---

## Out of Scope

- MMAL/Bullseye support (focus is Bookworm + libcamera only)
- Configuration migration from old MMAL configs
- New Camera v2 specific features
- UI control changes (already working correctly)
- Trixie/Debian 13 support (separate future task)

---

## Estimated Scope

- **Files modified**: 4
- **Lines changed**: ~80-120
- **Risk level**: Low (mostly validation and logging improvements)
