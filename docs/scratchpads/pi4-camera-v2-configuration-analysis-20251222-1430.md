# Pi Camera v2 Configuration for Pi 4 (Updated MotionEye)

## Analysis Context

**Question**: How do I configure Pi Camera v2 on Pi 4 for the updated MotionEye that was built for Pi 5 + Camera v3?

**Key Finding**: The updated codebase is **fully compatible** with Pi 4 + Camera v2. The system uses multiple camera detection mechanisms and automatically selects the correct configuration based on hardware capabilities.

---

## Hardware Configuration Detection

The MotionEye system uses a **detection-based approach** to determine camera type and capabilities:

### Camera Type Detection (in `motioneye/utils/__init__.py`)

```python
def is_v4l2_camera(config):
    """V4L2 USB/generic cameras with videodevice parameter"""
    return bool(config.get('videodevice'))

def is_libcamera_device(config):
    """libcamera devices (Pi 5+ native)"""
    return bool(config.get('libcam_device'))

def is_mmal_camera(config):
    """Legacy MMAL devices (deprecated)"""
    return bool(config.get('mmalcam_name'))

def is_rpicam_camera(config):
    """RPi cameras using RTSP bridge"""
    return bool(config.get('@rpicam'))
```

**Pi Camera v2 Detection Path**:
- Pi Camera v2 (IMX219 sensor) is **not** a libcamera device on Pi 4
- It **is** a V4L2 device when libcamera integration is enabled in Bookworm
- Falls back to MMAL/legacy if on older Bullseye without libcamera

---

## Default Configuration Setup

From `motioneye/config/defaults.py`, the system applies hardware-specific defaults:

### For V4L2 Cameras (Pi Camera v2 on Pi 4)
```python
if utils.is_v4l2_camera(data):
    data.setdefault('videodevice', '/dev/video0')
    data.setdefault('vid_control_params', '')
    data.setdefault('width', 352)      # Safe starting resolution
    data.setdefault('height', 288)
    data.setdefault('framerate', 2)
```

### For libcamera Devices (Pi 5 + Camera v3)
```python
elif utils.is_libcamera_device(data):
    data.setdefault('libcam_device', 'auto')
    data.setdefault('width', 1920)     # Native Camera v3 capability
    data.setdefault('height', 1080)
    data.setdefault('libcam_brightness', 0.0)
    data.setdefault('libcam_contrast', 1.0)
    data.setdefault('libcam_iso', 100)
```

### Hardware Encoding Selection

The system automatically selects the best H.264 encoder:
```python
if pictl.is_pi5():
    # Pi 5 has no hardware H.264 encoder
    data.setdefault('movie_codec', 'mp4')  # Software encoding (libx264)

elif motionctl.has_h264_v4l2m2m_support():
    # Pi 4 (both Bullseye and Bookworm) - preferred
    data.setdefault('movie_codec', 'mp4:h264_v4l2m2m')

elif motionctl.has_h264_omx_support():
    # Legacy OMX encoder fallback
    data.setdefault('movie_codec', 'mp4:h264_omx')

else:
    # Software fallback
    data.setdefault('movie_codec', 'mp4')
```

**Benefit for Pi 4**: v4l2m2m hardware H.264 encoding is available and will be used automatically, making it more efficient than Pi 5's software encoding.

---

## Configuration Steps for Pi Camera v2 on Pi 4

### 1. Verify Hardware is Detected

On the Pi 4, check that libcamera/v4l2 integration is available:

```bash
# List available cameras as V4L2 devices
v4l2-ctl --list-devices

# Or check libcamera devices
rpicam-hello --list-cameras
# or legacy command
libcamera-hello --list-cameras
```

Expected output for Pi Camera v2:
```
Platform : BCM2835 ISP
ISP: /dev/media0
```

### 2. Add Camera via MotionEye Web Interface

1. **Access MotionEye**: `http://192.168.1.246:8765/` (Pi 4)
2. **Add Camera** → Select "Local Motion Camera"
3. **Camera Type**: Let MotionEye auto-detect, or select "Generic Camera"
4. **Video Device**: `/dev/video0` (or detect from dropdown if available)

### 3. Minimal Configuration

For Pi Camera v2 on Pi 4, these settings will be auto-populated:

| Setting | Value | Notes |
|---------|-------|-------|
| **Video Device** | `/dev/video0` | Auto-detected |
| **Resolution** | 1920x1080 | Adjust based on CPU load (Pi 4 limited) |
| **Frame Rate** | 2-5 fps | Start conservative, increase if CPU permits |
| **Movie Codec** | `mp4:h264_v4l2m2m` | Auto-selected for Pi 4 |
| **Width/Height** | 1920x1080 | Pi Camera v2 supports up to 3280x2464, but CPU-intensive |

### 4. Performance Tuning for Pi Camera v2 on Pi 4

**CPU Considerations** (from project rules):
- Pi 4 is less powerful than Pi 5
- Camera v2 (IMX219) is older than Camera v3 (IMX708)
- Must minimize CPU usage to prevent thermal throttling

**Recommended Settings**:

```
Width:           1280  (compromise between quality and CPU load)
Height:          960
Framerate:       2-3 fps (adjust based on motion detection needs)
Movie Codec:     mp4:h264_v4l2m2m (hardware accelerated)
Movie Quality:   75% (default, adequate for motion detection)
Threshold:       2000 (motion detection sensitivity)
```

**Optional V4L2 Controls** (if fine-tuning needed):

Set `vid_control_params` in the UI under **Advanced Settings**:

Examples:
```
# Adjust brightness and contrast
brightness=50,contrast=50

# Set fixed white balance
white_balance_automatic=0,white_balance_temperature_auto=1
```

---

## What's Different from Pi 5 + Camera v3

### Pi 5 (Camera v3) Specific Features NOT Available on Pi 4 + Camera v2

These advanced controls are **only** for Camera v3 (IMX708):

- **Autofocus**: Camera v3 has autofocus; Camera v2 does not
- **Colour Temperature Control**: `libcam_colour_temp` - Camera v3 only
- **Colour Gains Control**: `libcam_colour_gain_r/b` - Camera v3 only
- **Native libcamera Controls**: `libcam_*` parameters only work with libcamera devices

The UI will automatically **hide these controls** for V4L2 cameras (Camera v2 on Pi 4).

### Pi 4 Advantages

1. **Hardware H.264 Encoding**: v4l2m2m is available and faster than software encoding
2. **V4L2 Standard Controls**: Full access to standard video controls
3. **Proven Stability**: Camera v2 is mature and well-tested on Pi 4

---

## Configuration File Location

After adding the camera, MotionEye generates config files:

```
/etc/motioneye/camera-1.conf     # Camera 1 configuration
/etc/motion/motion.conf           # Main Motion daemon config
```

The system automatically:
1. Detects V4L2 device presence
2. Applies V4L2-specific defaults
3. Excludes libcamera parameters
4. Selects h264_v4l2m2m for encoding

---

## Motion 5.0 Compatibility

The updated MotionEye is compatible with Motion 5.0+, which changed:

### Stream Endpoints (Motion 5.0)
- **Old**: Individual stream ports (9081, 9082, etc.) removed
- **New**: All streams served via webcontrol interface (http://192.168.1.246:7999/)

This works the same for V4L2 and libcamera cameras.

### CSRF Protection (Motion 5.0)
- Motion requires CSRF tokens for state changes
- MotionEye automatically handles token retrieval and refresh
- No additional configuration needed

---

## Troubleshooting

### Camera Not Detected

```bash
# Check if device exists
ls -l /dev/video*

# Check if accessible by motion user
sudo -u motion ls -l /dev/video0

# Verify libcamera/v4l2 integration
rpicam-hello --help 2>&1 | head -5
```

### Motion Fails to Start

Check logs:
```bash
sudo journalctl -u motion -n 50 --no-pager
```

Look for:
- `Could not open V4L2 device /dev/video0`
- `Permission denied` (run `sudo chown motion:motion /dev/video0`)
- `v4l2m2m not available` (software encoding will be used)

### Low Frame Rate / High CPU Usage

1. Reduce resolution to 1024x768 or 640x480
2. Reduce frame rate to 1-2 fps
3. Disable motion detection if only streaming
4. Check CPU temp: `vcgencmd measure_temp`

---

## Summary

**Your Pi 4 + Camera v2 will work with this updated MotionEye** without any special configuration beyond:

1. Ensuring libcamera support is enabled (Bookworm) or available
2. Setting `/dev/video0` as the video device
3. Letting MotionEye auto-detect and configure
4. Tuning resolution/framerate for Pi 4's CPU capabilities

The system's intelligent detection will:
- ✅ Use V4L2 device detection (not libcamera)
- ✅ Apply V4L2-specific defaults
- ✅ Select hardware H.264 encoding for efficiency
- ✅ Hide Camera v3-only controls in the UI
- ✅ Work seamlessly with Motion 5.0's new architecture

**No manual configuration of libcamera-specific parameters is needed** – the system handles this automatically based on detected hardware.
