# Handoff Prompt: RPi Camera RTSP Bridge Implementation

## Context

This motionEye fork needs native Raspberry Pi Camera support for RPi5 + Camera Module 3. The existing `motion` daemon doesn't support the modern `libcamera` stack, so we're implementing an integrated RTSP bridge that:

1. Detects RPi cameras via `rpicam-hello` (or `libcamera-hello` fallback)
2. Automatically starts `rpicam-vid` + `mediamtx` to create an RTSP stream
3. Configures motionEye to consume the stream as a network camera
4. All transparent to the user - they just see "RPi Camera" in the Add Camera dropdown

## Implementation Plan

**Read the full plan:** `docs/plans/merry-launching-goblet.md`

## Quick Reference

### Files to Create
- `motioneye/controls/rpicamctl.py` - Camera detection (model after `motioneye/controls/mmalctl.py`)
- `motioneye/rpicam_rtsp.py` - RTSP bridge process manager

### Files to Modify
- `motioneye/utils/__init__.py` - Add `is_rpicam_camera()`
- `motioneye/settings.py` - Add `RPICAM_*` settings
- `motioneye/handlers/config.py` - Add `rpicam` protocol in `list()` (~line 479)
- `motioneye/config.py` - Add rpicam camera handling
- `motioneye/server.py` - Add RTSP bridge lifecycle

### Key Patterns to Follow
- Detection: See `motioneye/controls/mmalctl.py` for pattern
- Protocol handling: See `motioneye/handlers/config.py:451-479` for v4l2/mmal examples
- Process management: Use subprocess with SIGTERM/SIGKILL graceful shutdown

### Dependencies
- `rpicam-apps` (system package on RPi)
- `mediamtx` (auto-download from GitHub on first use)

## Start Command

```
Implement the RPi Camera RTSP bridge according to docs/plans/merry-launching-goblet.md

Start with Phase 1: Create motioneye/controls/rpicamctl.py for camera detection.
Follow the pattern in motioneye/controls/mmalctl.py.
```

## Testing Environment

- Raspberry Pi 5 with Camera Module 3 (IMX708 Wide NoIR)
- Raspberry Pi OS Bookworm (uses `rpicam-*` commands)
- motionEye installed from this branch via `pip install .`

## Notes

- The `rpicam-*` commands are the new naming (Bookworm+), `libcamera-*` is legacy (Bullseye)
- Detection command: `rpicam-hello --list-cameras`
- Streaming command: `rpicam-vid -t 0 --width 1920 --height 1080 --framerate 30 --codec h264 -o -`
- mediamtx handles RTSP server, rpicam-vid pipes H.264 to it
