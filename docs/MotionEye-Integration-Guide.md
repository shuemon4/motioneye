# Motion Pi 5 + Camera v3 Updates: MotionEye Integration Guide

**Document Purpose**: This document provides all information needed to update MotionEye to work with the updated Motion daemon that now supports Raspberry Pi 5 and Camera Module v3 (IMX708).

**For**: AI assistant updating MotionEye project
**From**: Motion project (Pi 5/Camera v3 fork)
**Date**: 2025-12-06

---

## Executive Summary

Motion has been updated to natively support:
- **Raspberry Pi 5** (Cortex-A76 @ 2.4GHz, VideoCore VII GPU)
- **Camera Module 3** (IMX708 sensor with autofocus)
- **libcamera** backend (replacing legacy MMAL/V4L2)
- **SQLite** database for event logging (optional)

### Key Changes from Original Motion

| Aspect | Before (Motion 4.x) | After (This Fork) |
|--------|---------------------|-------------------|
| Camera API | MMAL + V4L2 | **libcamera native** |
| Pi Support | Pi 3/4 | **Pi 5 optimized** |
| Camera Module | v1, v2 | **v3 (IMX708)** |
| Stream Role | Viewfinder | **VideoRecording** |
| Buffer Count | 1 | **4 (configurable)** |
| H.264 Encoding | Hardware (Pi 4) | **Software (Pi 5)** |
| Database | MySQL/MariaDB/PostgreSQL/SQLite | **SQLite only** |

---

## What MotionEye Needs to Know

### 1. Motion Binary Compatibility

The updated Motion binary is a drop-in replacement but requires:

```bash
# Required packages on Pi 5
sudo apt install libcamera-dev libcamera-tools libjpeg-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libmicrohttpd-dev libsqlite3-dev
```

**Detection**: Motion still responds to `motion --help` and version checks. MotionEye's existing detection should work.

### 2. New Configuration Parameters

MotionEye generates `motion.conf` files. Add support for these new parameters:

```ini
# libcamera device selection (NEW)
# Options: "auto", "camera0", "camera1", "imx708", "imx219"
libcam_device auto

# libcamera buffer count (NEW)
# Range: 2-8, Default: 4
# Higher values = smoother capture, more memory
libcam_buffer_count 4
```

### 3. Removed/Deprecated Parameters

These parameters are **no longer effective** on Pi 5 with libcamera:

| Parameter | Status | Reason |
|-----------|--------|--------|
| `mmalcam_name` | Removed | MMAL not used on Pi 5 |
| `mmalcam_control_params` | Removed | Use libcamera controls |
| `v4l2_palette` | N/A for CSI | libcamera handles format |
| `video_device` | N/A for CSI | Use `libcam_device` |

### 4. Camera Detection Changes

**Old behavior** (Pi 4 with MMAL):
- Cameras detected via `/dev/video*` or MMAL
- Could mix USB and CSI cameras freely

**New behavior** (Pi 5 with libcamera):
- CSI cameras detected via libcamera API
- USB cameras filtered out by default
- Camera IDs look like: `/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a`

**MotionEye consideration**: When listing available cameras, you may need to:
1. Check if running on Pi 5 (check `/proc/cpuinfo` for BCM2712)
2. Use `libcamera-hello --list-cameras` to enumerate cameras
3. Map camera indices to `libcam_device camera0`, `camera1`, etc.

### 5. Encoder Changes (Important!)

**Pi 5 has NO hardware H.264 encoding**. This affects:

| Setting | Pi 4 | Pi 5 |
|---------|------|------|
| `movie_codec` | `h264_v4l2m2m` (hardware) | `libx264` (software) |
| CPU Usage | Low (~10%) | Higher (30-50%) |
| Recommendation | 1080p30 fine | Consider 720p for multi-cam |

**MotionEye should**:
1. Not offer `h264_v4l2m2m` as codec option on Pi 5
2. Warn users about CPU impact at 1080p
3. Suggest 720p for multi-camera setups

### 6. Autofocus Support (Camera v3)

Camera Module v3 has autofocus. Motion exposes these via libcamera controls:

```ini
# Autofocus mode
# 0 = manual, 1 = auto (one-shot), 2 = continuous
libcam_control_item AfMode=2

# Autofocus range
# 0 = normal, 1 = macro, 2 = full
libcam_control_item AfRange=0

# Manual lens position (when AfMode=0)
# Range: 0.0 (infinity) to 10.0+ (macro)
libcam_control_item LensPosition=0.0
```

**MotionEye UI suggestion**: Add autofocus controls for Camera v3:
- Dropdown: "Autofocus Mode" (Off/Auto/Continuous)
- Dropdown: "Focus Range" (Normal/Macro/Full)
- Slider: "Manual Focus" (when mode = Off)

---

## Build Configuration for Motion

When building Motion for MotionEye Docker image:

```bash
# Recommended configure flags for Pi 5
./configure \
  --with-libcam \
  --without-v4l2 \
  --with-sqlite3 \
  --without-mysql \
  --without-mariadb \
  --without-pgsql \
  --enable-pi5-optimize  # Optional, adds -mcpu=cortex-a76

make -j4
```

### Dependencies for Dockerfile

```dockerfile
# For Pi 5 + Camera v3 support
RUN apt-get update && apt-get install -y \
    libcamera-dev \
    libcamera-tools \
    libjpeg-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libmicrohttpd-dev \
    libsqlite3-dev \
    autoconf \
    automake \
    libtool \
    pkgconf \
    g++
```

---

## Configuration Generation Changes

### motion.conf Template Updates

MotionEye generates `motion.conf` dynamically. Update the template:

```python
# In motioneye/config.py or equivalent

# Detect Pi 5
def is_pi5():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'BCM2712' in f.read()
    except:
        return False

# Camera device parameter
if is_pi5():
    # Use libcamera device selection
    config['libcam_device'] = 'auto'  # or 'camera0', 'camera1'
    config['libcam_buffer_count'] = 4
else:
    # Legacy MMAL/V4L2 path
    config['mmalcam_name'] = 'vc.ril.camera'
```

### Codec Selection

```python
def get_video_codec():
    if is_pi5():
        # No hardware H.264 on Pi 5
        return 'libx264'  # or 'mpeg4' for lower CPU
    else:
        # Pi 4 and earlier have hardware encoding
        return 'h264_v4l2m2m'
```

---

## Motion Control Interface

Motion's HTTP control interface (port 7999) is **unchanged**. MotionEye can continue using:

```
GET /0/detection/status
GET /0/detection/start
GET /0/detection/pause
GET /0/config/list
POST /0/config/set?param=value
```

### New Parameters via Control Interface

These new parameters are now available:

```
/0/config/set?libcam_device=camera0
/0/config/set?libcam_buffer_count=4
```

---

## Camera Enumeration

### Detecting Available Cameras on Pi 5

```bash
# List libcamera cameras
libcamera-hello --list-cameras

# Example output:
# 0 : imx708 [4608x2592] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)
#     Modes: 'SRGGB10_CSI2P' : 1536x864 2304x1296 4608x2592
```

MotionEye should parse this to populate camera dropdown.

### Mapping to Motion Config

| libcamera-hello Output | motion.conf Setting |
|------------------------|---------------------|
| `0 : imx708` | `libcam_device camera0` |
| `1 : imx219` | `libcam_device camera1` |
| By sensor | `libcam_device imx708` |

---

## Performance Expectations

### Pi 5 Performance Profile

| Resolution | FPS | Detection | Encoding | Total CPU |
|------------|-----|-----------|----------|-----------|
| 1920x1080 | 30 | ~15% | ~35% | ~50% |
| 1280x720 | 30 | ~8% | ~20% | ~28% |
| 640x480 | 30 | ~3% | ~8% | ~11% |

### Multi-Camera Guidelines

| Cameras | Recommended Resolution | Expected CPU |
|---------|------------------------|--------------|
| 1 | 1920x1080 | 50% |
| 2 | 1280x720 | 60% |
| 3-4 | 640x480 | 45-65% |

**MotionEye should display these guidelines** when users add multiple cameras on Pi 5.

---

## Docker Considerations

### Volume Mounts

```yaml
# docker-compose.yml
volumes:
  - /etc/motioneye:/etc/motioneye          # MotionEye config
  - /var/lib/motioneye:/var/lib/motioneye  # Media storage
  - /var/lib/motion:/var/lib/motion        # Motion's SQLite DB (optional)
  - /dev:/dev                              # Camera access
```

### Device Access

For libcamera to work in Docker:

```yaml
# docker-compose.yml
devices:
  - /dev/video0:/dev/video0    # May not be needed for CSI
  - /dev/dri:/dev/dri          # GPU access for libcamera
  - /dev/media0:/dev/media0    # Media controller
```

Or use:
```yaml
privileged: true  # Simpler but less secure
```

### Container Camera Detection

libcamera requires access to:
- `/dev/dri/card*` - DRM devices
- `/dev/media*` - Media controller
- `/run/udev` - Device enumeration
- Camera firmware files

```dockerfile
# Ensure firmware is available
RUN apt-get install -y raspi-firmware
```

---

## SQLite Database (Motion Side)

Motion optionally logs events to SQLite:

```ini
# motion.conf
database_type sqlite3
database_dbname /var/lib/motion/motion.db
```

**Schema**:
```sql
CREATE TABLE motion (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER,
    file_typ TEXT,      -- 'image' or 'movie'
    file_nm TEXT,       -- filename
    file_dir TEXT,      -- directory path
    full_nm TEXT,       -- full path
    file_sz INTEGER,    -- size in bytes
    file_dtl INTEGER,   -- date (yyyymmdd)
    file_tmc TEXT,      -- time 12h format
    file_tml TEXT,      -- time 24h format
    diff_avg INTEGER,   -- motion difference average
    sdev_min INTEGER,   -- standard deviation min
    sdev_max INTEGER,   -- standard deviation max
    sdev_avg INTEGER    -- standard deviation average
);
```

**MotionEye consideration**:
- MotionEye doesn't use databases (it's file-based)
- Motion's SQLite is optional and independent
- No conflict with MotionEye's architecture

---

## Testing Checklist for MotionEye Integration

### 1. Camera Detection
- [ ] MotionEye detects Pi 5 (BCM2712)
- [ ] Camera dropdown populated from `libcamera-hello`
- [ ] `libcam_device` correctly written to motion.conf

### 2. Configuration Generation
- [ ] New `libcam_*` parameters in motion.conf
- [ ] Legacy MMAL parameters not included on Pi 5
- [ ] Correct codec selection (libx264 on Pi 5)

### 3. Live View
- [ ] MJPEG stream works from Motion
- [ ] No frame drops at 1080p30
- [ ] Autofocus working (if Camera v3)

### 4. Recording
- [ ] H.264 files created and playable
- [ ] Correct timestamps in recordings
- [ ] File cleanup working

### 5. Motion Control
- [ ] Start/stop detection
- [ ] Configuration changes via web UI
- [ ] Snapshot capture

### 6. Docker (if applicable)
- [ ] libcamera access from container
- [ ] Camera enumeration works
- [ ] No permission issues

---

## Error Messages and Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "No cameras found" | libcamera not detecting camera | Check cable, enable in raspi-config |
| "Create request error" | Buffer allocation failed | Increase `libcam_buffer_count` |
| Low framerate | CPU overloaded | Reduce resolution or cameras |
| "VideoRecording role failed" | Old libcamera version | Update to Bookworm packages |
| No hardware encoding | Expected on Pi 5 | Use `libx264`, accept CPU usage |

### Motion Startup Messages (Normal)

```
[1] [NTC] [ALL] conf_load: Processing camera config file /etc/motion/camera-1.conf
[1] [NTC] [ALL] libcam: Found Pi camera: /base/axi/pcie@120000/rp1/i2c@88000/imx708@1a
[1] [NTC] [ALL] libcam: Selected camera: /base/axi/pcie@120000/rp1/i2c@88000/imx708@1a
[1] [NTC] [ALL] libcam: Camera started
```

---

## Summary: MotionEye Changes Needed

### Required Changes

1. **Pi 5 Detection** (`motioneye/config.py` or equivalent)
   - Check for BCM2712 in /proc/cpuinfo
   - Set appropriate configuration path

2. **Camera Enumeration**
   - Parse `libcamera-hello --list-cameras`
   - Generate `libcam_device` values

3. **Config Generation**
   - Add `libcam_device`, `libcam_buffer_count`
   - Remove MMAL params on Pi 5
   - Set codec to `libx264` on Pi 5

4. **UI Updates** (optional but recommended)
   - Autofocus controls for Camera v3
   - CPU usage warnings for 1080p on Pi 5
   - Resolution recommendations for multi-cam

### Optional Changes

5. **Docker Updates**
   - Add libcamera packages
   - Ensure device access for libcamera

6. **Performance Guidance**
   - Display CPU estimates per resolution
   - Warn when adding multiple 1080p cameras

---

## File References in Motion Project

| Purpose | File Path | Notes |
|---------|-----------|-------|
| libcamera capture | `src/libcam.cpp` | Main camera code |
| Configuration | `src/conf.cpp` | Parameter handling |
| Config headers | `src/conf.hpp` | Parameter definitions |
| Motion detection | `src/alg.cpp` | **Unchanged** |
| Video encoding | `src/movie.cpp` | FFmpeg integration |
| Sample config | `data/motion-dist.conf.in` | Template file |

---

## Contact

This document was prepared from the Motion project fork for Pi 5 + Camera v3 support.

Repository: `C:\Users\Trent\Documents\GitHub\motion`
Related Design Docs:
- `doc/plans/Pi5-CamV3-Implementation-Design.md` - Full implementation design
- `doc/scratchpads/pi5-camv3-implementation.md` - Implementation notes

---

*Document Version: 1.0*
*Last Updated: 2025-12-06*
