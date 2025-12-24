# Issue: Video Stream Not Loading on Pi 4 (64-bit Trixie)

**Date:** 2025-12-23
**Platform:** Raspberry Pi 4 Model B, 64-bit Debian Trixie
**Camera:** Pi Camera Module v2 (IMX219)
**Affected Versions:** MotionEye 0.43.1b5, Motion 5.0.0

## Symptoms

- MotionEye web interface loads but video stream shows blank/loading
- Camera configured and enabled in MotionEye UI
- Service running without obvious errors in basic logs

## Root Cause

The `motioneye.conf` file contained an explicit `motion_binary` directive pointing to the wrong Motion binary:

```
motion_binary /usr/bin/motion
```

**Problem:** On systems with Motion compiled from source (required for libcamera support), two Motion binaries exist:

| Path | Source | libcamera Support |
|------|--------|-------------------|
| `/usr/bin/motion` | APT package (Motion 4.7.x) | No |
| `/usr/local/bin/motion` | Compiled from source (Motion 5.0) | Yes |

The explicit path overrode MotionEye's auto-detection, causing it to use the APT version which lacks libcamera support required for Pi cameras on 64-bit systems.

## Diagnosis Steps

### 1. Check Motion Service Status
```bash
sudo systemctl status motioneye
```

Look for V4L2 errors in the output:
```
[ERR] [VID] v4l2_mmap_set: Error starting stream. VIDIOC_STREAMON: Invalid argument
[ERR] [VID] vid_start: V4L2 device failed to open
```

These errors indicate Motion is trying V4L2 instead of libcamera.

### 2. Verify Camera Detection
```bash
rpicam-hello --list-cameras
```

Should show the camera (e.g., `imx219`).

### 3. Check Which Motion Binary Has libcamera
```bash
# Check APT version
ldd /usr/bin/motion | grep libcam
# (empty = no libcamera)

# Check source-compiled version
ldd /usr/local/bin/motion | grep libcam
# Should show: libcamera.so.0.6 => /lib/aarch64-linux-gnu/libcamera.so.0.6
```

### 4. Verify Auto-Detection Path
```bash
which motion
# Should return: /usr/local/bin/motion
```

### 5. Test Motion Stream Directly
```bash
# After fixing, verify Motion is streaming
curl -s --max-time 3 'http://localhost:7999/1/mjpg/stream' -o /tmp/test.dat
file /tmp/test.dat
# Should show: multipart data or JPEG content
```

## Resolution

### Option A: Minimal Config (Recommended)

Use a minimal `motioneye.conf` that relies on auto-detection:

```bash
sudo tee /etc/motioneye/motioneye.conf << 'EOF'
port 8765
listen 0.0.0.0
EOF

sudo systemctl restart motioneye
```

### Option B: Explicit Correct Path

If you must specify the binary explicitly:

```bash
sudo tee /etc/motioneye/motioneye.conf << 'EOF'
port 8765
listen 0.0.0.0
motion_binary /usr/local/bin/motion
EOF

sudo systemctl restart motioneye
```

## Verification

After applying the fix:

1. **Check Motion binary in use:**
   ```bash
   ps aux | grep motion
   # Should show: /usr/local/bin/motion
   ```

2. **Test MotionEye picture endpoint:**
   ```bash
   curl -s 'http://localhost:8765/picture/1/current/' -o /tmp/test.jpg
   file /tmp/test.jpg
   # Should show: JPEG image data
   ```

3. **Refresh browser** - video stream should now load

## Related Warnings (Non-Blocking)

After fixing the binary path, you may see warnings about deprecated config options:

```
[ALR] edit_set: Unknown config option "stream_localhost"
[ALR] edit_set: Unknown config option "stream_port"
[ALR] edit_set: Unknown config option "stream_auth_method"
```

These are Motion 4.x options that were removed in Motion 5.0. They don't prevent streaming but will be cleaned up when you save the camera configuration through the MotionEye UI.

## Prevention

When installing MotionEye on Pi 4/5 with 64-bit OS:

1. **Do NOT specify `motion_binary`** in the config unless necessary
2. Ensure `/usr/local/bin` is in PATH before `/usr/bin`
3. Verify `which motion` returns the libcamera-enabled version
4. Use the minimal config template from `motioneye/extra/motioneye.conf.sample`

## See Also

- [Installation Guide - Pi 4](../installation/pi4-64bit-notes.md)
- [Installation Guide - Pi 5](../installation/pi5-64bit-notes.md)
- [Motion 5.0 Migration](../plans/trixie-64bit-migration-plan.md)
