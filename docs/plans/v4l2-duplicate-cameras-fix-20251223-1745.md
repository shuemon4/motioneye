# Fix V4L2 Camera Dropdown Duplicates

**Date**: 2025-12-23 17:45
**Issue**: Camera dropdown shows 15 duplicate entries when adding V4L2 camera
**Platform**: Pi 4/5 with 64-bit OS

---

## Problem Analysis

### Current Behavior
- Adding a new V4L2 camera shows:
  - 5x `bcm2835-codec-decode`
  - 10x `bcm2835-isp`
  - (Pi 5 would show 18x `pispbe`, 8x `rp1-cfe`, etc.)

### Root Cause
1. `v4l2ctl.list_devices()` returns every `/dev/videoX` node as separate camera
2. Hardware accelerators have multiple video nodes:
   - `bcm2835-codec-decode`: 5 nodes (decoder)
   - `bcm2835-isp`: 10 nodes (image signal processor)
   - `pispbe`: 18 nodes (Pi 5 ISP)
   - `rp1-cfe`: 8 nodes (Pi 5 camera frontend)
3. UI receives list with duplicate names, displays all
4. No filtering for non-camera devices

### V4L2 Device Types on Pi 4/5

**Not cameras** (should be hidden):
- `bcm2835-codec-decode` - H.264 hardware decoder
- `bcm2835-codec` - Generic codec interface
- `bcm2835-isp` - Image signal processor
- `pispbe` - Pi 5 ISP backend
- `rp1-cfe` - Pi 5 camera frontend interface
- `rpi-hevc-dec` - HEVC hardware decoder
- `unicam` - Camera interface (not the camera itself)

**Actual cameras** (should be shown):
- USB webcams: "USB Camera", device-specific names
- **NOT** CSI cameras - those use libcamera/rpicam on Pi 4+

---

## Solution Design

### Approach 1: Filter Non-Camera Devices (Recommended)

Create a blocklist of known hardware accelerator prefixes:

```python
# In v4l2ctl.py
_NON_CAMERA_DEVICES = {
    'bcm2835-codec',      # Matches bcm2835-codec-decode, bcm2835-codec-encode, etc.
    'bcm2835-isp',
    'pispbe',
    'rp1-cfe',
    'rpi-hevc-dec',
    'unicam',
}

def _is_system_device(name):
    """Check if device is a system video processor, not a camera."""
    name_lower = name.lower()
    for prefix in _NON_CAMERA_DEVICES:
        if name_lower.startswith(prefix):
            return True
    return False
```

Modify `list_devices()` to skip system devices:

```python
def list_devices():
    # ... existing code ...
    for line in output.split('\n'):
        if line.startswith('\t'):
            device = line.strip()
            persistent_device = find_persistent_device(device)

            # Skip if this is a system device
            if not _is_system_device(name):
                devices.append((device, persistent_device, name))
                logging.debug(f'found device {name}: {device}, {persistent_device}')
            else:
                logging.debug(f'skipping system device {name}: {device}')
        else:
            name = line.split('(')[0].strip()

    return devices
```

**Pros**:
- Clean, permanent fix
- Eliminates visual clutter
- Prevents users from selecting non-functional "cameras"
- Future-proof for new hardware accelerators

**Cons**:
- Requires maintaining blocklist
- Could theoretically hide a real camera with similar name (unlikely)

### Approach 2: Deduplicate by Name Only

Keep first device per camera name:

```python
def list_devices():
    # ... existing code ...
    seen_names = set()
    devices = []

    for line in output.split('\n'):
        if line.startswith('\t'):
            device = line.strip()
            persistent_device = find_persistent_device(device)

            # Only add if we haven't seen this camera name before
            if name not in seen_names:
                devices.append((device, persistent_device, name))
                seen_names.add(name)
                logging.debug(f'found device {name}: {device}, {persistent_device}')
        else:
            name = line.split('(')[0].strip()

    return devices
```

**Pros**:
- Simple implementation
- No maintenance of device lists

**Cons**:
- Still shows non-camera devices
- May hide legitimate secondary cameras with same name
- Doesn't solve root problem

### Approach 3: Combined (Best)

Combine both approaches:
1. Filter out known system devices
2. Deduplicate remaining devices by name

---

## Implementation Plan

### Phase 1: Add System Device Filter
1. Add `_NON_CAMERA_DEVICES` constant to `v4l2ctl.py`
2. Add `_is_system_device()` helper function
3. Modify `list_devices()` to skip system devices
4. Add debug logging for skipped devices

### Phase 2: Add Deduplication
1. Track seen camera names in `list_devices()`
2. Skip duplicate names, keeping first device path
3. Log when duplicates are skipped

### Phase 3: Testing
1. Test on Pi 4 (admin@192.168.1.246)
2. Test on Pi 5 (admin@192.168.1.176)
3. Verify with USB webcam (if available)
4. Check MotionEye UI shows clean camera list

### Phase 4: Documentation
1. Document behavior in code comments
2. Update troubleshooting docs if needed

---

## Expected Results

**Before**:
```
Camera dropdown shows:
- bcm2835-codec-decode (5 times)
- bcm2835-isp (10 times)
```

**After**:
```
Camera dropdown shows:
- (empty if no USB cameras)
- "USB Camera" (if USB camera connected)
```

---

## Testing Checklist

- [ ] Pi 4: No system devices in dropdown
- [ ] Pi 5: No system devices in dropdown
- [ ] USB camera appears correctly (if available)
- [ ] Existing configured cameras still work
- [ ] No duplicate entries
- [ ] Log messages show filtered devices

---

## Notes

- CSI cameras (Pi Camera) should never appear in V4L2 dropdown on Pi 4+
- They appear in libcamera/rpicam dropdown instead
- V4L2 is only for USB webcams on modern Pi OS
- This aligns with the removal of MMAL support in this fork
