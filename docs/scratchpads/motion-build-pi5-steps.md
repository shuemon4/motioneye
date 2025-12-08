# Motion Build Steps for Pi 5 with libcamera Support

**Date**: 2025-12-07
**Target**: Raspberry Pi 5 + Camera Module 3 (imx708_wide_noir)
**Connection**: ssh admin@pi5-motioneye (password: wwadmin)

## Problem

The default Motion 4.7.1 from apt does NOT support libcamera:
```
[ALR] [ALL] conf_cmdparse: Unknown config option "libcam_device"
[ALR] [ALL] conf_cmdparse: Unknown config option "libcam_buffer_count"
```

Motion falls back to V4L2 which cannot access the Pi camera:
```
[ERR] [VID] v4l2_mmap_set: Error starting stream. VIDIOC_STREAMON: Invalid argument
[ERR] [VID] vid_start: V4L2 device failed to open
```

## Solution

Build Motion from custom source at `C:\Users\Trent\Documents\GitHub\motion` which includes libcamera support for Pi 5.

## Step-by-Step Build Process

### Step 1: Transfer Motion Source to Pi 5

```bash
cd "C:\Users\Trent\Documents\GitHub\motion"
tar cf - --exclude=.git . | ssh admin@pi5-motioneye "mkdir -p ~/motion && cd ~/motion && tar xf -"
```

### Step 2: Run Setup Script (Install Dependencies)

```bash
ssh admin@pi5-motioneye "cd ~/motion && chmod +x scripts/*.sh && ./scripts/pi5-setup.sh"
```

This installs:
- Build tools (autoconf, automake, libtool, etc.)
- Required dependencies (libjpeg, libmicrohttpd, zlib)
- FFmpeg dependencies (libavcodec, libavformat, etc.)
- libcamera (critical for Pi 5)
- Optional dependencies (sqlite3, webp, dos2unix)

### Step 3: Build Motion

```bash
ssh admin@pi5-motioneye "cd ~/motion && ./scripts/pi5-build.sh"
```

This:
1. Fixes Windows line endings (dos2unix)
2. Sets executable permissions
3. Runs autoreconf
4. Configures for Pi 5 with libcamera (--with-libcam, --without-v4l2)
5. Builds with make -j4

### Step 4: Install Built Binary

```bash
ssh admin@pi5-motioneye "cd ~/motion && sudo make install"
```

### Step 5: Restart MotionEye

```bash
ssh admin@pi5-motioneye "sudo systemctl restart motioneye"
```

## Verification

Check Motion version and libcamera support:
```bash
ssh admin@pi5-motioneye "motion -h | head -5"
```

Check Motion log for successful camera detection:
```bash
ssh admin@pi5-motioneye "tail -20 /var/log/motioneye/motion.log"
```

## Expected Result

Motion should:
1. Recognize `libcam_device auto` configuration
2. Detect the Camera Module 3 via libcamera
3. Start streaming at configured resolution

## Actual Results (2025-12-07)

### Success: Motion 5.0.0 Built and Installed
- Motion 5.0.0-gitUNKNOWN built successfully with libcamera support
- Camera detected: `imx708_wide_noir` via libcamera v0.5.2
- Stream configured: 1920x1080-YUV420/Rec709

### Motion Log Showing Success
```
[INFO] libcamera v0.5.2+99-bfd68f78
[INFO] Adding camera '/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a' for pipeline handler rpi/pisp
[INFO] configuring streams: (0) 1920x1080-YUV420/Rec709
[INFO] Sensor: /base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a - Selected sensor format: 2304x1296-SBGGR10_1X10/RAW
```

### Issues Found - Motion 4.x to 5.0 Breaking Changes

Motion 5.0.0 has significant config parameter changes that affect MotionEye:

| Old Parameter (4.x) | New Parameter (5.0) | Status |
|---------------------|---------------------|--------|
| `camera_name` | `device_name` | Deprecated warning |
| `movie_codec` | `movie_container` | Deprecated warning |
| `stream_port` | Removed | **BREAKING** |
| `stream_localhost` | Removed | **BREAKING** |
| `stream_auth_method` | Removed | **BREAKING** |
| `stream_authentication` | Removed | **BREAKING** |
| `auto_brightness` | Removed | **BREAKING** |
| `webcontrol_interface` | Changed from int to string | **BREAKING** |

### Motion 5.0 Streaming Changes

Motion 5.0 removed the separate `stream_port` parameter. Streams are now served via the webcontrol interface:
- `webcontrol_port 7999` serves all streams
- `webcontrol_interface` must be "default", "user", or "simple" (not integer)
- Stream URLs changed from `http://host:stream_port/` to `http://host:webcontrol_port/cam_id/stream`

### Next Steps Required

1. **Update MotionEye config generation** to handle Motion 5.0 parameter changes
2. **Update mjpgclient.py** to use new webcontrol-based stream URLs
3. **Add Motion version detection** to generate appropriate config format
4. **Update converters.py** to map old params to new params based on Motion version
