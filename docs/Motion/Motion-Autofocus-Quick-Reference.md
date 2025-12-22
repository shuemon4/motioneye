# Motion Autofocus - AI Quick Reference

**TL;DR:** Motion now supports autofocus hot-reload via HTTP API for Raspberry Pi cameras with libcamera.

---

## Quick Decision Tree

```
Need autofocus control?
├─ Yes: Is subject at fixed distance?
│  ├─ Yes → Use Manual mode (libcam_af_mode=0) + set lens_position
│  └─ No: Is subject moving?
│     ├─ Yes → Use Continuous mode (libcam_af_mode=2)
│     └─ No → Use Auto mode (libcam_af_mode=1)
└─ No: Skip this feature
```

---

## 4 Core Parameters (Hot-Reloadable)

| Parameter | Type | Range | Default | Hot-Reload |
|-----------|------|-------|---------|------------|
| `libcam_af_mode` | int | 0-2 | 0 (Manual) | ✅ |
| `libcam_lens_position` | float | 0.0-15.0 | 0.0 (∞) | ✅ |
| `libcam_af_range` | int | 0-2 | 0 (Normal) | ✅ |
| `libcam_af_speed` | int | 0-1 | 0 (Normal) | ✅ |

---

## 3 Common Scenarios (Copy-Paste Ready)

### 1. Fixed Focus at 2 Meters (Static Camera)
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=0"
curl "http://localhost:8080/1/config/set?libcam_lens_position=0.5"
```

### 2. Continuous AF (Motion Tracking)
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
curl "http://localhost:8080/1/config/set?libcam_af_speed=1"
```

### 3. Macro Focus (Close-Up)
```bash
curl "http://localhost:8080/1/config/set?libcam_af_mode=2"
curl "http://localhost:8080/1/config/set?libcam_af_range=1"
```

---

## Dioptre → Distance Cheat Sheet

| Dioptres | Distance | Use Case |
|----------|----------|----------|
| 0.0 | ∞ | Outdoor, far subjects |
| 0.333 | 3m | Room camera |
| 0.5 | 2m | Desk/hallway |
| 1.0 | 1m | Close monitoring |
| 2.0 | 50cm | License plate |
| 10.0 | 10cm | Macro (very close) |

**Formula:** `distance (meters) = 1 / dioptres`

---

## HTTP API One-Liner

```bash
# Template
curl "http://<host>:<port>/<camera_id>/config/set?<param>=<value>"

# Example
curl "http://192.168.1.176:8080/1/config/set?libcam_af_mode=2"
```

**Default:** `localhost:8080` for Motion webcontrol

---

## Python Quick Implementation

```python
import requests

def set_af_mode(camera_id, mode):
    """mode: 0=Manual, 1=Auto, 2=Continuous"""
    url = f"http://localhost:8080/{camera_id}/config/set"
    return requests.get(url, params={"libcam_af_mode": mode}).ok

def set_focus_distance(camera_id, distance_meters):
    """Set focus in meters (auto-converts to dioptres)"""
    dioptres = 0.0 if distance_meters == 0 else 1.0 / distance_meters
    url = f"http://localhost:8080/{camera_id}/config/set"
    requests.get(url, params={"libcam_af_mode": 0})  # Set Manual
    return requests.get(url, params={"libcam_lens_position": dioptres}).ok
```

---

## Critical Rules

1. ⚠️ **lens_position only works when af_mode=0 (Manual)**
2. ⚠️ **AfState and AfPauseState are READ-ONLY** (don't try to set them)
3. ⚠️ **AfWindows requires libcam_params** (not hot-reloadable individually)
4. ✅ **All 4 core params are hot-reloadable** (no restart needed)

---

## Config File Syntax

```conf
# New style (hot-reloadable)
libcam_af_mode 2
libcam_af_range 0
libcam_af_speed 1

# Old style (still works)
libcam_params AfMode=2,AfRange=0,AfSpeed=1
```

**Prefer new style** for hot-reload capability.

---

## MotionEye UI Hints

**Dropdown for AF Mode:**
```
Manual (Fixed Focus) → 0
Auto (On Demand) → 1
Continuous (Tracking) → 2
```

**Slider for Lens Position (shown only if Manual):**
```
Display: "Focus Distance: 2.0 meters"
Internal: libcam_lens_position = 0.5
```

**Disable lens_position slider when mode ≠ 0**

---

## Validation Rules

```python
# Quick validators
af_mode: lambda x: x in [0, 1, 2]
lens_position: lambda x: 0.0 <= x <= 15.0
af_range: lambda x: x in [0, 1, 2]
af_speed: lambda x: x in [0, 1]
```

---

## Error Messages to Handle

| Error | Meaning | Solution |
|-------|---------|----------|
| "Read-only control" | Tried to set AfState/AfPauseState | Remove from config |
| Timeout | Motion not responding | Check Motion service running |
| Invalid value | Out of range | Validate before sending |

---

## Testing One-Liner

```bash
# Test if Motion supports autofocus API
curl -s "http://localhost:8080/1/config/set?libcam_af_mode=0" && echo "✅ AF API working" || echo "❌ AF API failed"
```

---

## Performance Impact

| Mode | CPU Impact | Use When |
|------|------------|----------|
| Manual | None | Fixed distance |
| Auto | Low | On-demand focus |
| Continuous | Moderate | Motion tracking |

---

## Further Reading

**Full API Documentation:** `Motion-Autofocus-API.md`
**Implementation Details:** `/Users/tshuey/Documents/GitHub/motion/doc/plans/20251221-autofocus-implementation-plan.md`
**libcamera Reference:** https://libcamera.org/api-html/namespacelibcamera_1_1controls.html
