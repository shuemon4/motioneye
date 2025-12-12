# Audio Support Requirements Analysis for MotionEye

**Date:** 2025-12-11
**Status:** Requirements Gathering
**Author:** Claude Code Analysis

---

## Executive Summary

This document analyzes the feasibility and requirements for adding audio support to MotionEye. Historically, neither Motion nor MotionEye has supported audio recording. However, recent developments in Motion 5.0 (February 2025) have added audio passthrough support for network cameras, creating an opportunity to extend this functionality to MotionEye.

---

## Current State Analysis

### Motion Audio Support Status

#### Historical Context
- Motion has been video-only since its inception (~2000)
- The maintainer historically resisted audio features, citing legal concerns: "In 'most' countries it is fine to record video but illegal to record audio security footage"
- Community workarounds involved running separate FFmpeg processes to capture audio alongside Motion's video

#### Recent Development (February 2025)
As of **February 5, 2025**, Motion's master branch now supports recording audio from network cameras via the `movie_passthrough` option.

**Key Configuration:**
```
movie_passthrough on
```

This enables audio recording only when:
- The camera source is a network camera (RTSP/RTMP)
- The camera stream includes an audio track
- Passthrough mode is enabled (no re-encoding)

**Source:** [GitHub Discussion #1366](https://github.com/Motion-Project/motion/discussions/1366)

#### MotionPlus Alternative
MotionPlus (a Motion fork) has had experimental audio support for longer, though users report:
- Audio works with RTSP streams
- Some latency issues ("extreme latency" reported by some users)
- Occasional codec compatibility issues (e.g., "Could not find tag for codec pcm_alaw")

**Source:** [MotionPlus Discussion #29](https://github.com/Motion-Project/motionplus/discussions/29)

---

### MotionEye Current Architecture

#### Audio-Related Code: None

A comprehensive search of the MotionEye codebase revealed:
- **No audio configuration options** in `config/camera/converters.py`
- **No audio device detection** logic
- **No audio playback** in movie handlers (`handlers/movie.py`, `handlers/movie_playback.py`)
- **No audio streaming** infrastructure
- Only references to "audio" found were in translation files (`.po` files) for unrelated UI text

#### Relevant Existing Components

| Component | Location | Current Function | Audio Relevance |
|-----------|----------|------------------|-----------------|
| Camera Config | `config/camera/converters.py` | Converts UI ↔ Motion config | Would need audio device/settings |
| Movie Handler | `handlers/movie.py` | Lists, previews, deletes movies | Would need audio-aware playback |
| Movie Playback | `handlers/movie_playback.py` | Serves video files for playback | Browser audio codec support |
| Motion Control | `motionctl.py` | Manages Motion daemon | Passthrough config options |
| Media Files | `mediafiles.py` | File management | Audio file handling if separate |

---

### Raspberry Pi 5 Audio Capabilities

#### Hardware Constraints
- **No built-in microphone** on Raspberry Pi
- **No analog audio input** - only output via 3.5mm jack
- Audio input requires external hardware:
  - USB microphones
  - USB webcams with built-in microphones
  - USB sound cards with line-in
  - I2S microphone boards (HATs)

#### Software Stack

**ALSA (Advanced Linux Sound Architecture)**
- Primary audio subsystem on Raspberry Pi OS
- Device enumeration: `arecord -l`
- Device naming: `hw:<card>,<device>` (e.g., `hw:1,0`)
- Configuration: `/etc/asound.conf` or `~/.asoundrc`

**PulseAudio (Optional)**
- Higher-level audio server
- Better multi-application audio handling
- Can simplify device management

**Source:** [Adafruit ALSA Guide](https://learn.adafruit.com/usb-audio-cards-with-a-raspberry-pi/updating-alsa-config)

#### libcamera Audio Integration

The `libcamera-vid` command supports audio capture:
```bash
libcamera-vid --libav-audio --audio-source alsa --audio-device plughw:0
```

**Known Issues:**
- Microphone sync issues reported when using libcamera with external mics
- High CPU usage on single core with some configurations
- PulseAudio drivers may spread load more evenly

**Source:** [Raspberry Pi Forums - Audio Sync Issues](https://forums.raspberrypi.com/viewtopic.php?p=2086679)

---

## Technical Considerations

### Audio Source Types

#### 1. USB Microphones (Local to Pi)
- Requires ALSA device detection and configuration
- Audio captured independently from video
- Synchronization challenges with motion events
- Works with Pi Camera or any video source

#### 2. RTSP Camera Audio Streams
- Audio embedded in camera's RTSP stream
- Motion 5.0's `movie_passthrough` handles this
- No additional hardware needed on Pi
- Sync handled by camera/stream

#### 3. Hybrid Approach
- Support both simultaneously
- More complex implementation
- Maximum flexibility

### Playback Considerations

#### Browser Limitations
| Stream Type | Audio Support | Notes |
|-------------|---------------|-------|
| MJPEG | No | MJPEG is image sequence, no audio channel |
| HLS | Yes | Requires transcoding infrastructure |
| WebRTC | Yes | Complex, requires signaling server |
| MP4 Download | Yes | Works today if audio in file |

#### Current MotionEye Streaming
MotionEye uses MJPEG for live streaming, which fundamentally cannot carry audio. Adding live audio would require:
- Protocol change to HLS or WebRTC
- Significant frontend changes
- Additional server-side transcoding

### Recording vs. Streaming

| Feature | Complexity | Motion Support |
|---------|------------|----------------|
| Audio in recorded clips | Medium | Yes (passthrough) |
| Live audio streaming | High | No |
| Audio-triggered events | Medium | No |

---

## Open Questions for Requirements

### 1. Audio Source Types
**Question:** Which audio sources need to be supported?

| Option | Description | Complexity |
|--------|-------------|------------|
| A | USB microphones/webcams connected to Pi | Medium |
| B | RTSP camera streams with embedded audio | Low (Motion 5.0 supports) |
| C | Both A and B | High |

### 2. Primary Use Case
**Question:** What is the primary goal for audio support?

| Option | Description |
|--------|-------------|
| A | Record audio synchronized with motion-triggered video clips |
| B | Record continuous audio alongside video |
| C | Use audio as a detection trigger (sound-activated recording) |
| D | Audio-only recording independent of video |

### 3. Playback Requirements
**Question:** Where does audio need to be playable?

| Option | Description | Feasibility |
|--------|-------------|-------------|
| A | Embedded in downloaded MP4 files only | Easy |
| B | Playable in MotionEye web UI | Medium |
| C | Live audio streaming in web UI | Hard (requires protocol change) |

### 4. Live Streaming
**Question:** Does the live MJPEG stream need audio?

| Option | Description | Impact |
|--------|-------------|--------|
| A | No - audio only in recordings | Minimal changes |
| B | Yes - need live audio | Major architecture change (WebRTC/HLS) |

### 5. Motion Version Dependency
**Question:** What Motion version compatibility is required?

| Option | Description | Audio Support |
|--------|-------------|---------------|
| A | Require Motion 5.0+ | Native passthrough audio |
| B | Support older Motion versions | Script-based workarounds needed |

### 6. Hardware Context
**Questions:**
- What USB microphone/audio devices are planned for use?
- Do the RTSP cameras in use already include audio streams?
- Is there a specific microphone placement scenario (near camera, separate location)?

---

## Preliminary Architecture Options

### Option A: Motion Passthrough Only (Simplest)

**Scope:** Support audio only for RTSP cameras with audio streams via Motion's `movie_passthrough`

**Changes Required:**
1. Update Motion config generation to enable passthrough
2. Ensure MotionEye doesn't strip audio from downloaded files
3. Add UI toggle for "Record Audio" (if passthrough available)

**Pros:**
- Minimal MotionEye changes
- Leverages Motion 5.0 native support
- No additional audio hardware needed

**Cons:**
- No support for local USB microphones
- No live audio streaming
- Requires Motion 5.0+

### Option B: FFmpeg Audio Muxing (Medium Complexity)

**Scope:** Capture audio separately via FFmpeg/ALSA and mux with video

**Changes Required:**
1. ALSA device detection and configuration UI
2. FFmpeg subprocess management for audio capture
3. Post-recording muxing of audio + video
4. Synchronization logic for motion events

**Pros:**
- Works with any video source
- Supports local USB microphones
- Can work with older Motion versions

**Cons:**
- Complex synchronization
- Additional CPU/resource usage
- More failure points

### Option C: Full Audio Integration (Most Complex)

**Scope:** Native audio support with live streaming

**Changes Required:**
1. All of Option A and B
2. WebRTC or HLS streaming infrastructure
3. Frontend audio player integration
4. Real-time audio encoding

**Pros:**
- Complete audio experience
- Live audio monitoring
- Maximum feature parity with commercial NVRs

**Cons:**
- Significant development effort
- Major architecture changes
- Higher resource requirements

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Audio/video sync issues | High | Medium | Use passthrough when possible |
| Browser codec compatibility | Medium | Medium | Stick to standard codecs (AAC) |
| CPU overhead on Pi | Medium | High | Profile and optimize, consider hardware encoding |
| Motion passthrough bugs | Medium | Medium | Test extensively, have fallback |
| Legal concerns (audio recording) | Low | High | Add clear warnings, user consent |

---

## Next Steps

1. **Clarify requirements** using the questions above
2. **Determine scope** (Option A, B, or C)
3. **Create detailed design** based on chosen scope
4. **Prototype** critical path (audio capture → muxing → playback)
5. **Test on target hardware** (Raspberry Pi 5 with Camera v3)

---

## References

- [Motion GitHub Discussion #1366 - Audio Recording Support](https://github.com/Motion-Project/motion/discussions/1366)
- [MotionPlus Audio Stream Discussion #29](https://github.com/Motion-Project/motionplus/discussions/29)
- [MotionPlus Passthrough Issues Discussion #32](https://github.com/Motion-Project/motionplus/discussions/32)
- [Motion Configuration Reference](https://motion-project.github.io/motion_config.html)
- [Raspberry Pi Audio Documentation](https://www.raspberrypi.com/documentation/accessories/audio.html)
- [Adafruit - USB Audio Cards with Raspberry Pi](https://learn.adafruit.com/usb-audio-cards-with-a-raspberry-pi/updating-alsa-config)
- [Raspberry Pi Forums - libcamera Audio Sync Issues](https://forums.raspberrypi.com/viewtopic.php?p=2086679)
- [RaspberryTips - Add Microphone to Raspberry Pi](https://raspberrytips.com/add-microphone-raspberry-pi/)
- [Pi My Life Up - Using a Microphone with Raspberry Pi](https://pimylifeup.com/raspberrypi-microphone/)
