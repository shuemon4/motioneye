# Updating Motion for MotionEye on Raspberry Pi 5

This guide documents how to build and install a custom Motion binary with libcamera support for Raspberry Pi 5 + Camera Module v3.

## Why This Is Needed

The default Motion 4.7.1 from Raspberry Pi OS Bookworm's apt repositories does NOT support libcamera natively. When MotionEye generates configuration with `libcam_device auto`, the stock Motion binary shows:

```
[ALR] conf_cmdparse: Unknown config option "libcam_device"
[ALR] conf_cmdparse: Unknown config option "libcam_buffer_count"
```

Motion then falls back to V4L2 which cannot access CSI cameras on Pi 5:

```
[ERR] v4l2_mmap_set: Error starting stream. VIDIOC_STREAMON: Invalid argument
[ERR] vid_start: V4L2 device failed to open
```

## Prerequisites

- Raspberry Pi 5 with Camera Module v3 (or compatible CSI camera)
- Raspberry Pi OS Bookworm (64-bit recommended)
- SSH access to the Pi
- Motion source code from: `C:\Users\Trent\Documents\GitHub\motion`

## Build Process

### Step 1: Transfer Motion Source to Pi 5

From Windows:
```bash
cd "C:\Users\Trent\Documents\GitHub\motion"
tar cf - --exclude=.git . | ssh admin@pi5-motioneye "mkdir -p ~/motion && cd ~/motion && tar xf -"
```

### Step 2: Fix Line Endings (Required for Windows-transferred files)

```bash
ssh admin@pi5-motioneye "dos2unix ~/motion/scripts/*.sh && chmod +x ~/motion/scripts/*.sh"
```

### Step 3: Install Build Dependencies

```bash
ssh admin@pi5-motioneye "cd ~/motion && ./scripts/pi5-setup.sh"
```

This installs:
- **Build tools**: autoconf, automake, libtool, pkgconf, gettext, git
- **Required libs**: libjpeg-dev, libmicrohttpd-dev, zlib1g-dev
- **FFmpeg**: libavcodec-dev, libavformat-dev, libavutil-dev, libswscale-dev, libavdevice-dev
- **libcamera**: libcamera-dev, libcamera-tools, libcamera-v4l2 (critical for Pi 5)
- **Optional**: libsqlite3-dev, libwebp-dev, dos2unix

### Step 4: Build Motion

```bash
ssh admin@pi5-motioneye "cd ~/motion && ./scripts/pi5-build.sh"
```

The build script:
1. Runs `autoreconf -fiv`
2. Configures with: `--with-libcam --with-sqlite3 --with-webp --without-v4l2`
3. Builds with `make -j4`

**Expected output:**
```
Motion version 5.0.0-gitUNKNOWN
libcamera: yes(0.5.2)
```

### Step 5: Install the Binary

```bash
ssh admin@pi5-motioneye "sudo cp ~/motion/src/motion /usr/bin/motion"
```

Or for a full install with man pages, data files, etc.:
```bash
ssh admin@pi5-motioneye "cd ~/motion && sudo make install"
```

### Step 6: Create Required Directories

Motion 5.0 expects a database directory:
```bash
ssh admin@pi5-motioneye "sudo mkdir -p /usr/local/var/lib/motion && sudo chmod 755 /usr/local/var/lib/motion"
```

### Step 7: Restart MotionEye

```bash
ssh admin@pi5-motioneye "sudo killall motion python3 2>/dev/null; sleep 2; sudo python3 -m motioneye.meyectl startserver -c /etc/motioneye/motioneye.conf &"
```

## Verification

### Check Motion Version
```bash
ssh admin@pi5-motioneye "motion -h | head -5"
```
Expected: `Motion version 5.0.0-gitUNKNOWN`

### Check Camera Detection
```bash
ssh admin@pi5-motioneye "tail -30 /var/log/motioneye/motion.log"
```

Expected (successful libcamera detection):
```
[INFO] libcamera v0.5.2+99-bfd68f78
[INFO] Adding camera '/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a' for pipeline handler rpi/pisp
[INFO] configuring streams: (0) 1920x1080-YUV420/Rec709
```

## Motion 4.x to 5.0 Breaking Changes

Motion 5.0.0 introduces significant configuration parameter changes:

### Renamed Parameters
| Motion 4.x | Motion 5.0 |
|------------|------------|
| `camera_name` | `device_name` |
| `movie_codec` | `movie_container` |

### Removed Parameters
These parameters no longer exist in Motion 5.0:
- `stream_port`
- `stream_localhost`
- `stream_auth_method`
- `stream_authentication`
- `auto_brightness`
- `setup_mode`

### Changed Parameters
| Parameter | Motion 4.x | Motion 5.0 |
|-----------|------------|------------|
| `webcontrol_interface` | Integer (0, 1, 2) | String ("default", "user", "simple") |

### Streaming Architecture Change

**Motion 4.x**: Separate stream ports per camera (`stream_port 9081`)

**Motion 5.0**: All streams served via webcontrol interface:
- Stream URL: `http://host:webcontrol_port/cam_id/stream`
- Snapshot URL: `http://host:webcontrol_port/cam_id/current`

## MotionEye Compatibility Notes

MotionEye was designed for Motion 4.x. To fully support Motion 5.0:

1. **Config Generation**: Must generate Motion 5.0 compatible parameters
2. **Stream Client**: Must use webcontrol URLs instead of stream_port URLs
3. **Version Detection**: Should detect Motion version and adjust accordingly

### Current Status

With Motion 5.0.0 built with libcamera:
- Camera detection via libcamera: **WORKING**
- Camera configuration: **WORKING** (with deprecated warnings)
- MJPEG stream via webcontrol: **WORKING** (requires config adjustment)

### Known Issues

1. **Deprecated parameter warnings**: Motion 5.0 shows warnings for `camera_name` and `movie_codec` but still accepts them
2. **webcontrol_interface value**: MotionEye sets `webcontrol_interface 1` but Motion 5.0 expects "default"
3. **Stream URL**: MotionEye's mjpgclient needs to use webcontrol-based stream URLs

## Troubleshooting

### "Unknown config option" errors
Motion version mismatch. Ensure Motion 5.0 is installed:
```bash
motion -h | head -1
```

### Camera not detected
Check libcamera:
```bash
rpicam-hello --list-cameras
```

### Database errors
Create the database directory:
```bash
sudo mkdir -p /usr/local/var/lib/motion
```

### Script execution errors ("sh\r: No such file")
Fix Windows line endings:
```bash
dos2unix ~/motion/scripts/*.sh
```

## References

- Motion Project: https://github.com/Motion-Project/motion
- MotionEye Integration Guide: `docs/MotionEye-Integration-Guide.md`
- Pi 5 Camera v3 Support Design: `docs/designs/pi5-camera-v3-support.md`
- Build steps scratchpad: `docs/scratchpads/motion-build-pi5-steps.md`
