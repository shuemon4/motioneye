# Design: Pi 5 + Camera v3 (libcamera) Support for MotionEye

**Design Version**: 1.0
**Date**: 2025-12-07
**Status**: AWAITING APPROVAL

---

## 1. Executive Summary

This design updates MotionEye to support Raspberry Pi 5 with Camera Module v3 (IMX708) using the libcamera backend. The updated Motion daemon no longer uses MMAL on Pi 5, instead relying on libcamera native integration.

### Key Changes Required

| Area | Current State | Target State |
|------|---------------|--------------|
| Camera Detection | MMAL via `vcgencmd` | libcamera via `libcamera-hello` |
| Config Generation | `mmalcam_name` parameter | `libcam_device` + `libcam_buffer_count` |
| Codec Selection | `h264_v4l2m2m` (hardware) | `libx264` (software) on Pi 5 |
| Platform Detection | None | BCM2712 detection in `/proc/cpuinfo` |
| UI | No autofocus controls | Autofocus mode/range for Camera v3 |

---

## 2. Requirements Analysis

### REQ-1: Pi 5 Platform Detection
Detect when running on Raspberry Pi 5 (BCM2712 SoC) to enable appropriate configuration paths.

### REQ-2: libcamera Camera Enumeration
Enumerate CSI cameras using `libcamera-hello --list-cameras` instead of `vcgencmd get_camera`.

### REQ-3: libcamera Configuration Parameters
Generate motion.conf with new `libcam_device` and `libcam_buffer_count` parameters on Pi 5.

### REQ-4: Codec Selection for Pi 5
Select software encoder (`libx264`) on Pi 5 since hardware H.264 encoding is not available.

### REQ-5: Remove Deprecated MMAL Parameters on Pi 5
Exclude `mmalcam_name`, `mmalcam_control_params` from generated config when on Pi 5.

### REQ-6: Camera v3 Autofocus Controls (Optional)
Expose autofocus settings (AfMode, AfRange, LensPosition) in the UI for Camera v3.

### REQ-7: Backward Compatibility
Maintain support for Pi 4 and earlier with existing MMAL/V4L2 paths.

---

## 3. Architecture Design

### 3.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MotionEye Application                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐ │
│  │   Platform      │    │  Camera Control  │    │    Config      │ │
│  │   Detection     │───▶│  (mmalctl.py →   │───▶│   Generation   │ │
│  │   (NEW: pictl)  │    │   libcamctl.py)  │    │  (config.py)   │ │
│  └─────────────────┘    └──────────────────┘    └────────────────┘ │
│         │                       │                       │          │
│         ▼                       ▼                       ▼          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    motion.conf / camera-X.conf               │   │
│  │  ┌─────────────────┐     ┌──────────────────────────────┐   │   │
│  │  │ Pi 4 (Legacy)   │     │ Pi 5 (libcamera)             │   │   │
│  │  │ mmalcam_name    │     │ libcam_device                │   │   │
│  │  │ h264_v4l2m2m    │     │ libcam_buffer_count          │   │   │
│  │  └─────────────────┘     │ movie_codec: libx264         │   │   │
│  │                          └──────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Motion Daemon       │
                        │   (libcamera backend) │
                        └───────────────────────┘
```

### 3.2 New Module: `motioneye/controls/pictl.py`

Platform detection utility for Raspberry Pi variants.

```python
# motioneye/controls/pictl.py

"""
Raspberry Pi platform detection utilities.
Detects Pi model and available camera interfaces.
"""

def get_pi_model() -> dict | None:
    """
    Detect Raspberry Pi model from /proc/cpuinfo.

    Returns:
        dict with 'model', 'revision', 'is_pi5', 'camera_interface'
        None if not running on a Raspberry Pi

    Example return:
        {
            'model': 'Raspberry Pi 5 Model B',
            'revision': 'd04170',
            'is_pi5': True,
            'camera_interface': 'libcamera'
        }
    """

def is_pi5() -> bool:
    """Returns True if running on Raspberry Pi 5 (BCM2712)."""

def get_camera_interface() -> str:
    """
    Returns the camera interface to use.

    Returns:
        'libcamera' - Pi 5 and newer
        'mmal' - Pi 4 and earlier with legacy camera stack
        'v4l2' - Generic V4L2 (USB cameras, etc.)
    """
```

### 3.3 Updated Module: `motioneye/controls/libcamctl.py`

Replaces/extends `mmalctl.py` for libcamera-based camera detection.

```python
# motioneye/controls/libcamctl.py

"""
libcamera camera detection and control.
Used on Pi 5 and systems with libcamera support.
"""

def list_devices() -> list[tuple[str, str, dict]]:
    """
    Enumerate cameras using libcamera-hello --list-cameras.

    Returns:
        List of (device_id, display_name, properties) tuples

    Example:
        [
            ('camera0', 'IMX708 (Camera Module 3)', {
                'sensor': 'imx708',
                'max_resolution': '4608x2592',
                'path': '/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a',
                'supports_autofocus': True
            }),
        ]
    """

def get_camera_properties(device_id: str) -> dict:
    """
    Get detailed properties for a specific camera.

    Returns dict with:
        - sensor: Sensor model (imx708, imx219, etc.)
        - max_resolution: Maximum supported resolution
        - modes: Available capture modes
        - supports_autofocus: Boolean (true for Camera v3)
        - path: Full libcamera device path
    """

def is_libcamera_available() -> bool:
    """Check if libcamera-hello is available on the system."""
```

### 3.4 Camera Type Abstraction

Add new camera type concept in `utils/__init__.py`:

```python
# In motioneye/utils/__init__.py

def is_libcamera_device(config) -> bool:
    """Tells if a camera uses libcamera (libcam_device parameter)."""
    return bool(config.get('libcam_device'))

def is_local_motion_camera(config):
    """Tells if a camera is managed by the local motion instance."""
    return bool(
        config.get('videodevice')
        or config.get('video_device')
        or config.get('netcam_url')
        or config.get('mmalcam_name')
        or config.get('libcam_device')  # NEW: libcamera support
    )
```

---

## 4. Detailed Design

### 4.1 Platform Detection (`pictl.py`)

**File**: `motioneye/controls/pictl.py` (NEW)

**Implementation**:

```python
import logging
import re
from subprocess import CalledProcessError
from motioneye import utils as motioneye_utils

_pi_info_cache = None

def get_pi_model() -> dict | None:
    """Detect Raspberry Pi model from /proc/cpuinfo."""
    global _pi_info_cache
    if _pi_info_cache is not None:
        return _pi_info_cache

    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
    except (OSError, IOError):
        _pi_info_cache = {}
        return None

    # Check for BCM2712 (Pi 5)
    is_pi5 = 'BCM2712' in cpuinfo

    # Check for older Pi models
    is_pi = any(chip in cpuinfo for chip in ['BCM2835', 'BCM2836', 'BCM2837', 'BCM2711', 'BCM2712'])

    if not is_pi:
        _pi_info_cache = {}
        return None

    # Extract model info
    model_match = re.search(r'Model\s*:\s*(.+)', cpuinfo)
    revision_match = re.search(r'Revision\s*:\s*(\w+)', cpuinfo)

    _pi_info_cache = {
        'model': model_match.group(1).strip() if model_match else 'Unknown Raspberry Pi',
        'revision': revision_match.group(1) if revision_match else 'unknown',
        'is_pi5': is_pi5,
        'camera_interface': 'libcamera' if is_pi5 else 'mmal'
    }

    logging.debug(f'Detected Pi model: {_pi_info_cache}')
    return _pi_info_cache

def is_pi5() -> bool:
    """Returns True if running on Raspberry Pi 5."""
    pi_info = get_pi_model()
    return pi_info.get('is_pi5', False) if pi_info else False

def get_camera_interface() -> str:
    """Returns the camera interface to use (libcamera, mmal, or v4l2)."""
    pi_info = get_pi_model()
    if not pi_info:
        return 'v4l2'
    return pi_info.get('camera_interface', 'v4l2')
```

**Traces To**: REQ-1 (Pi 5 Platform Detection)

---

### 4.2 libcamera Camera Detection (`libcamctl.py`)

**File**: `motioneye/controls/libcamctl.py` (NEW)

**Implementation**:

```python
import logging
import re
from subprocess import CalledProcessError
from motioneye import utils as motioneye_utils

_LIBCAMERA_HELLO = 'libcamera-hello'

def is_libcamera_available() -> bool:
    """Check if libcamera-hello is available."""
    try:
        motioneye_utils.call_subprocess(['which', _LIBCAMERA_HELLO])
        return True
    except CalledProcessError:
        return False

def list_devices() -> list:
    """
    Enumerate cameras using libcamera-hello --list-cameras.

    Returns list of (device_id, display_name, properties) tuples.
    """
    logging.debug('Detecting libcamera cameras')

    if not is_libcamera_available():
        logging.debug('libcamera-hello not found')
        return []

    try:
        output = motioneye_utils.call_subprocess(
            [_LIBCAMERA_HELLO, '--list-cameras'],
            timeout=10
        )
    except CalledProcessError as e:
        logging.debug(f'libcamera-hello failed: {e}')
        return []

    cameras = []
    output = motioneye_utils.make_str(output)

    # Parse output like:
    # 0 : imx708 [4608x2592] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)
    #     Modes: 'SRGGB10_CSI2P' : 1536x864 2304x1296 4608x2592

    camera_pattern = re.compile(
        r'^(\d+)\s*:\s*(\w+)\s*\[(\d+x\d+)\]\s*\(([^)]+)\)',
        re.MULTILINE
    )

    for match in camera_pattern.finditer(output):
        index, sensor, max_res, path = match.groups()
        device_id = f'camera{index}'

        # Determine if camera supports autofocus (Camera v3 = imx708)
        supports_autofocus = sensor.lower() == 'imx708'

        # Create display name
        sensor_names = {
            'imx708': 'Camera Module 3',
            'imx219': 'Camera Module 2',
            'ov5647': 'Camera Module 1',
        }
        display_name = sensor_names.get(sensor.lower(), sensor.upper())

        properties = {
            'sensor': sensor,
            'max_resolution': max_res,
            'path': path,
            'supports_autofocus': supports_autofocus,
            'index': int(index)
        }

        cameras.append((device_id, display_name, properties))
        logging.debug(f'Found libcamera device: {device_id} ({display_name})')

    return cameras

def get_camera_properties(device_id: str) -> dict | None:
    """Get detailed properties for a specific camera."""
    devices = list_devices()
    for dev_id, name, props in devices:
        if dev_id == device_id:
            return props
    return None
```

**Traces To**: REQ-2 (libcamera Camera Enumeration)

---

### 4.3 Updated Camera Handler (`handlers/config.py`)

**File**: `motioneye/handlers/config.py`

**Changes at lines 466-479** (camera listing):

```python
# BEFORE:
elif proto == 'mmal':
    configured_devices = set()
    for camera_id in config.get_camera_ids():
        data = config.get_camera(camera_id)
        if utils.is_mmal_camera(data):
            configured_devices.add(data['mmalcam_name'])

    cameras = [
        {'id': d[0], 'name': d[1]}
        for d in mmalctl.list_devices()
        if (d[0] not in configured_devices)
    ]

    return self.finish_json({'cameras': cameras})

# AFTER:
elif proto == 'mmal':
    configured_devices = set()
    for camera_id in config.get_camera_ids():
        data = config.get_camera(camera_id)
        if utils.is_mmal_camera(data):
            configured_devices.add(data['mmalcam_name'])
        elif utils.is_libcamera_device(data):
            configured_devices.add(data['libcam_device'])

    # Use libcamera on Pi 5, MMAL on older Pis
    if pictl.is_pi5():
        cameras = [
            {
                'id': d[0],
                'name': d[1],
                'properties': d[2]
            }
            for d in libcamctl.list_devices()
            if d[0] not in configured_devices
        ]
    else:
        cameras = [
            {'id': d[0], 'name': d[1]}
            for d in mmalctl.list_devices()
            if d[0] not in configured_devices
        ]

    return self.finish_json({'cameras': cameras})
```

**Traces To**: REQ-2, REQ-7

---

### 4.4 Configuration Generation (`config.py`)

**File**: `motioneye/config.py`

#### 4.4.1 Default Camera Config (lines ~2266-2280)

```python
# BEFORE:
if utils.is_v4l2_camera(data):
    data.setdefault('videodevice', '/dev/video0')
    data.setdefault('vid_control_params', '')
    data.setdefault('width', 352)
    data.setdefault('height', 288)

# AFTER:
if utils.is_v4l2_camera(data):
    data.setdefault('videodevice', '/dev/video0')
    data.setdefault('vid_control_params', '')
    data.setdefault('width', 352)
    data.setdefault('height', 288)

elif utils.is_libcamera_device(data):
    # Pi 5 with libcamera
    data.setdefault('libcam_device', 'auto')
    data.setdefault('libcam_buffer_count', 4)
    data.setdefault('width', 1920)
    data.setdefault('height', 1080)
    # Autofocus defaults for Camera v3
    if data.get('@supports_autofocus'):
        data.setdefault('@af_mode', 2)      # Continuous
        data.setdefault('@af_range', 0)     # Normal
        data.setdefault('@lens_position', 0.0)
```

#### 4.4.2 Codec Selection (lines 2354-2361)

```python
# BEFORE:
if motionctl.has_h264_omx_support():
    data.setdefault('movie_codec', 'mp4:h264_omx')
elif motionctl.has_h264_v4l2m2m_support():
    data.setdefault('movie_codec', 'mp4:h264_v4l2m2m')
else:
    data.setdefault('movie_codec', 'mp4')

# AFTER:
from motioneye.controls import pictl

if pictl.is_pi5():
    # Pi 5 has no hardware H.264 encoder - use software
    data.setdefault('movie_codec', 'mp4')  # Uses libx264
elif motionctl.has_h264_omx_support():
    data.setdefault('movie_codec', 'mp4:h264_omx')
elif motionctl.has_h264_v4l2m2m_support():
    data.setdefault('movie_codec', 'mp4:h264_v4l2m2m')
else:
    data.setdefault('movie_codec', 'mp4')
```

#### 4.4.3 Config Dict to UI Conversion (around line 1528)

```python
# BEFORE:
elif utils.is_mmal_camera(data):
    ui['device_url'] = data['mmalcam_name']
    ui['proto'] = 'mmal'
    resolutions = utils.COMMON_RESOLUTIONS
    ...

# AFTER:
elif utils.is_libcamera_device(data):
    ui['device_url'] = data['libcam_device']
    ui['proto'] = 'libcamera'
    ui['libcam_buffer_count'] = data.get('libcam_buffer_count', 4)

    # Autofocus controls for Camera v3
    if data.get('@supports_autofocus'):
        ui['autofocus_mode'] = data.get('@af_mode', 2)
        ui['autofocus_range'] = data.get('@af_range', 0)
        ui['lens_position'] = data.get('@lens_position', 0.0)
        ui['supports_autofocus'] = True

    resolutions = utils.COMMON_RESOLUTIONS
    resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]
    ui['available_resolutions'] = [f'{w}x{h}' for w, h in resolutions]

elif utils.is_mmal_camera(data):
    ui['device_url'] = data['mmalcam_name']
    ui['proto'] = 'mmal'
    ...
```

#### 4.4.4 UI Dict to Config Conversion

Add handling for libcamera devices when converting UI input to motion config:

```python
# In motion_camera_ui_to_dict function

if ui.get('proto') == 'libcamera':
    data['libcam_device'] = ui.get('device_url', 'auto')
    data['libcam_buffer_count'] = ui.get('libcam_buffer_count', 4)

    # Autofocus control parameters
    if ui.get('supports_autofocus'):
        af_mode = ui.get('autofocus_mode', 2)
        af_range = ui.get('autofocus_range', 0)
        lens_pos = ui.get('lens_position', 0.0)

        # Generate libcam_control_item entries
        control_items = []
        control_items.append(f'AfMode={af_mode}')
        control_items.append(f'AfRange={af_range}')
        if af_mode == 0:  # Manual focus
            control_items.append(f'LensPosition={lens_pos}')

        # Multiple control items joined with newline
        data['libcam_control_item'] = control_items

        # Store for UI
        data['@af_mode'] = af_mode
        data['@af_range'] = af_range
        data['@lens_position'] = lens_pos
        data['@supports_autofocus'] = True
```

**Traces To**: REQ-3, REQ-4, REQ-5, REQ-6

---

### 4.5 Utils Updates (`utils/__init__.py`)

**File**: `motioneye/utils/__init__.py`

**Add new function** (after line 215):

```python
def is_libcamera_device(config) -> bool:
    """Tells if a camera uses libcamera (Pi 5+ with libcam_device parameter)."""
    return bool(config.get('libcam_device'))
```

**Update `is_local_motion_camera`** (lines 193-200):

```python
def is_local_motion_camera(config):
    """Tells if a camera is managed by the local motion instance."""
    return bool(
        config.get('videodevice')
        or config.get('video_device')
        or config.get('netcam_url')
        or config.get('mmalcam_name')
        or config.get('libcam_device')  # NEW: libcamera support
    )
```

**Traces To**: REQ-3, REQ-7

---

### 4.6 Docker Updates

**File**: `docker/Dockerfile`

Add libcamera dependencies:

```dockerfile
# BEFORE (around line 19-20):
DEBIAN_FRONTEND="noninteractive" apt-get -qq --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
  ca-certificates curl python3 fdisk $PACKAGES && \

# AFTER:
DEBIAN_FRONTEND="noninteractive" apt-get -qq --option Dpkg::Options::="--force-confnew" --no-install-recommends install \
  ca-certificates curl python3 fdisk \
  libcamera-dev libcamera-tools \
  $PACKAGES && \
```

**Traces To**: REQ-2 (libcamera tools needed for camera enumeration)

---

## 5. Requirements Traceability Matrix

| Requirement | Design Element | Coverage |
|-------------|----------------|----------|
| REQ-1: Pi 5 Detection | `pictl.py`: `is_pi5()`, `get_pi_model()` | Full |
| REQ-2: libcamera Enumeration | `libcamctl.py`: `list_devices()` | Full |
| REQ-3: libcamera Config Params | `config.py`: libcam_device, libcam_buffer_count | Full |
| REQ-4: Codec Selection | `config.py`: Pi 5 → libx264 fallback | Full |
| REQ-5: Remove MMAL on Pi 5 | `config.py`: libcamera path excludes mmalcam_name | Full |
| REQ-6: Autofocus Controls | `config.py`: @af_mode, @af_range, @lens_position | Full |
| REQ-7: Backward Compatibility | All paths preserve existing MMAL/V4L2 logic | Full |

---

## 6. Assumptions

1. **Motion Binary**: The updated Motion binary with libcamera support is installed and accessible.

2. **libcamera-hello**: The `libcamera-hello` tool is available on Pi 5 systems for camera enumeration.

3. **Raspberry Pi OS Bookworm**: The system is running Raspberry Pi OS Bookworm or newer with libcamera stack.

4. **Camera v3 Identification**: The IMX708 sensor indicates Camera Module v3 with autofocus support.

5. **Single Camera Interface**: A given Pi uses either libcamera (Pi 5) OR MMAL (Pi 4 and earlier), not both simultaneously.

---

## 7. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| libcamera-hello parsing fails | Camera detection broken | Low | Fallback to empty list, log warning |
| Motion binary version mismatch | Config params not recognized | Medium | Version check for libcamera params |
| Docker libcamera access issues | No camera in container | Medium | Document device/privilege requirements |
| Software encoding CPU impact | High CPU on Pi 5 | Known | UI warning for 1080p multi-cam |
| Autofocus parameters incorrect | Focus issues | Low | Validate parameter ranges |

---

## 8. File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `motioneye/controls/pictl.py` | Raspberry Pi platform detection |
| `motioneye/controls/libcamctl.py` | libcamera camera enumeration |

### Modified Files
| File | Changes |
|------|---------|
| `motioneye/utils/__init__.py` | Add `is_libcamera_device()`, update `is_local_motion_camera()` |
| `motioneye/config.py` | libcamera config generation, codec selection, UI conversion |
| `motioneye/handlers/config.py` | Camera listing for libcamera devices |
| `docker/Dockerfile` | Add libcamera-dev, libcamera-tools dependencies |

---

## 9. Testing Checklist

### Platform Detection
- [ ] `is_pi5()` returns True on Pi 5
- [ ] `is_pi5()` returns False on Pi 4
- [ ] `is_pi5()` returns False on non-Pi hardware
- [ ] `get_camera_interface()` returns 'libcamera' on Pi 5
- [ ] `get_camera_interface()` returns 'mmal' on Pi 4

### Camera Enumeration
- [ ] `libcamctl.list_devices()` detects Camera v3 on Pi 5
- [ ] Camera sensor correctly identified as imx708
- [ ] `supports_autofocus` is True for Camera v3
- [ ] Backward compatible: `mmalctl.list_devices()` still works on Pi 4

### Configuration Generation
- [ ] `libcam_device` written to motion.conf on Pi 5
- [ ] `libcam_buffer_count` defaults to 4
- [ ] `mmalcam_name` NOT written on Pi 5
- [ ] `movie_codec` defaults to `mp4` (libx264) on Pi 5
- [ ] Autofocus parameters written for Camera v3

### Live View & Recording
- [ ] MJPEG stream works from Motion on Pi 5
- [ ] H.264 recordings created and playable
- [ ] Autofocus functioning (if Camera v3)

### Docker
- [ ] libcamera access from container works
- [ ] Camera enumeration succeeds in Docker

---

## 10. Implementation Order

1. **Phase 1: Platform Detection**
   - Create `pictl.py`
   - Add tests for Pi detection

2. **Phase 2: Camera Enumeration**
   - Create `libcamctl.py`
   - Update `handlers/config.py` camera listing
   - Add tests for libcamera parsing

3. **Phase 3: Configuration**
   - Update `utils/__init__.py`
   - Update `config.py` for libcamera params
   - Update codec selection logic

4. **Phase 4: UI (Optional)**
   - Add autofocus controls to frontend
   - Add CPU usage warnings for Pi 5

5. **Phase 5: Docker**
   - Update Dockerfile
   - Test container camera access

---

**Design Status**: READY FOR AUDIT

