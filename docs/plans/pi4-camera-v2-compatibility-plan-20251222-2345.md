# Pi 4 + Camera v2 Backward Compatibility Plan

**Goal**: Ensure MotionEye (updated for Pi 5 + Camera v3) works correctly on Pi 4 with Camera v2

**Target Configuration**: Pi 4 + Bookworm (32-bit) + Camera v2 (IMX219) using libcamera
**Test Hardware**: Available (Pi 4 + Camera v2)

---

## Summary of Issues Found

### Critical Issues (Must Fix)

| Issue | Location | Impact |
|-------|----------|--------|
| libcamera validation missing | `rpicamctl.py` | Pi 4 on Bookworm may fail silently |
| Error logging at DEBUG only | Multiple files | Users see "no cameras" with no explanation |
| MMAL fallback not robust | `mmalctl.py` | vcgencmd may not exist on some systems |

### Medium Issues (Should Fix)

| Issue | Location | Impact |
|-------|----------|--------|
| No config migration MMAL→libcamera | `converters.py` | Upgrade path broken |
| Resolution defaults assume v3 | `defaults.py` | 1920x1080 may be excessive for v2 |
| Cache never invalidates | `pictl.py`, `rpicamctl.py` | Tool detection stale after OS changes |
| Stream port migration silent | `adaptation.py` | Old configs break without warning |

### Low Priority (Nice to Have)

| Issue | Location | Impact |
|-------|----------|--------|
| No sensor-specific defaults | `defaults.py` | Generic settings for all sensors |
| Multi-camera mixed v2/v3 | `converters.py` | First camera's AF capability used for all |

---

## Recommended Implementation Plan

### Phase 1: Improve Detection Robustness

**File: `motioneye/controls/rpicamctl.py`**

1. Add validation that `rpicam-hello --list-cameras` actually succeeds and returns cameras
2. Upgrade logging from DEBUG to WARNING when detection fails
3. Add `clear_cache()` function call at startup

**File: `motioneye/controls/mmalctl.py`**

4. Add try/except around vcgencmd calls with graceful fallback
5. Log at WARNING level if vcgencmd not found

**File: `motioneye/controls/pictl.py`**

6. Add startup cache clear
7. Add validation that selected interface actually works before returning

### Phase 2: Sensor-Specific Defaults

**File: `motioneye/config/defaults.py`**

8. Add sensor-specific resolution defaults:
   - IMX708 (v3): 1920x1080 (current)
   - IMX219 (v2): 1280x720 or 1640x1232 (native 2x2 binned)
   - Other sensors: Conservative 640x480

9. Add sensor-specific ISO defaults:
   - IMX708: 100-800 typical range
   - IMX219: 100-1600 (different noise characteristics)

### Phase 3: Error Visibility

**All detection files:**

10. Create unified error reporting for camera detection failures
11. Surface errors to UI when no cameras found (not just empty list)
12. Add troubleshooting hints based on platform/OS combination

---

## Critical Files to Modify

| File | Priority | Changes |
|------|----------|---------|
| `motioneye/controls/rpicamctl.py` | HIGH | Validation, logging, cache clear |
| `motioneye/controls/mmalctl.py` | HIGH | Robust vcgencmd handling |
| `motioneye/controls/pictl.py` | HIGH | Cache clear, interface validation |
| `motioneye/config/defaults.py` | MEDIUM | Sensor-specific defaults |

---

## Testing Requirements

Test on Pi 4 + Bookworm (32-bit) + Camera v2:

1. **Camera detection**: Verify `rpicam-hello --list-cameras` detects IMX219
2. **libcamera path**: Verify camera enumeration returns correct sensor info
3. **MotionEye add camera**: Verify Camera v2 can be added via UI
4. **Stream verification**: Verify MJPEG stream works at configured resolution
5. **Error visibility**: Verify failed detection shows useful error (if camera disconnected)
6. **Autofocus UI**: Verify autofocus controls are hidden for Camera v2

---

## Out of Scope

- MMAL/Bullseye support (focus is Bookworm + libcamera)
- Configuration migration from old MMAL configs
- Adding new Camera v2 specific features
- Changing UI controls for v2 (already correctly hidden)
- Hardware encoder changes (already working)
- Multi-camera mixed sensor handling (complex edge case)
- Trixie/Debian 13 support (separate future task)

---

## Estimated Scope

- **Files modified**: 4
- **Lines changed**: ~80-120
- **Risk level**: Low (mostly adding validation and logging)
