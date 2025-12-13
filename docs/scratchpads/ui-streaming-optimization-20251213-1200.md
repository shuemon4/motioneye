# UI Streaming Optimization for Raspberry Pi

**Date**: 2025-12-13
**Goal**: Modernize UI display while minimizing CPU impact on Raspberry Pi

---

## Current CPU Profile (Estimated)

| Component | CPU Usage | Notes |
|-----------|-----------|-------|
| Motion daemon | 30-50% | Core video processing |
| JPEG extraction | 5-10% per cam | Snapshot polling overhead |
| Python backend | 5-15% | Tornado handlers |
| **Total available for UI improvements** | ~20-30% | Must stay within this |

---

## Option Analysis

### Option 1: Keep MJPEG, Improve Client-Side Only

**Changes:**
- Better error recovery (exponential backoff)
- Smarter frame skipping when browser tab inactive
- Visibility API to pause hidden cameras
- Reduce polling frequency on low-bandwidth detection

**CPU Impact**: ~0% (all changes client-side JavaScript)

**Pros:**
- Zero server CPU increase
- Immediate implementation
- No Motion config changes

**Cons:**
- No latency improvement
- No adaptive quality
- Still uses old polling model

**Verdict**: ✅ RECOMMENDED as Phase 1

---

### Option 2: Native MJPEG Streaming (Motion's Built-in)

**Current state**: Already supported for "simple MJPEG" cameras
**Gap**: Motion-controlled cameras use snapshot polling instead

**Why polling exists:**
- Allows server-side resize (bandwidth control)
- Enables motion detection overlay
- Supports authentication layer

**Could we switch Motion cameras to direct MJPEG?**
- Motion already exposes `/1/mjpg/stream` endpoint
- Currently MotionEye proxies through snapshot handler

**CPU Impact**: Actually REDUCES CPU
- Eliminates per-frame JPEG extraction
- Removes Python handler overhead
- Direct stream passthrough

**Implementation:**
```javascript
// Instead of polling /picture/1/current/
// Use direct Motion stream:
img.src = 'http://localhost:7999/1/mjpg/stream';
```

**Challenges:**
- Lose server-side resize capability
- Need to handle authentication differently
- Motion detection status needs separate channel

**Verdict**: ✅ RECOMMENDED as Phase 2 (optional mode)

---

### Option 3: HLS Streaming

**CPU Impact**: HIGH NEGATIVE
- Requires ffmpeg transcoding
- Segment creation overhead
- Not suitable for Pi

**Verdict**: ❌ NOT RECOMMENDED for Pi

---

### Option 4: WebRTC

**CPU Impact**: MODERATE-HIGH
- Requires STUN/TURN setup
- Codec negotiation overhead
- Complex server component

**Verdict**: ❌ NOT RECOMMENDED for Pi

---

### Option 5: WebSocket Binary Frames

**Concept**: Send raw JPEG frames over WebSocket instead of HTTP polling

**CPU Impact**: SLIGHT REDUCTION
- Eliminates HTTP overhead per frame
- Persistent connection
- Could batch multiple cameras

**Implementation complexity**: Medium

**Verdict**: ⚠️ CONSIDER for Phase 3

---

## Recommended Approach

### Phase 1: Client-Side Optimizations (Zero CPU cost)

1. **Page Visibility API** - Pause streams when tab hidden
2. **Intersection Observer** - Only refresh visible cameras
3. **Exponential backoff** - Reduce load on errors
4. **Adaptive framerate** - Detect slow connections, reduce FPS
5. **RequestAnimationFrame** - Sync with browser paint cycle

### Phase 2: Direct MJPEG Mode (Reduces CPU)

1. Add UI toggle: "Low CPU Mode" or "Direct Streaming"
2. When enabled, bypass Python snapshot handler
3. Connect directly to Motion's MJPEG endpoint
4. Trade-off: Lose server-side resize

### Phase 3: Future (If Needed)

1. WebSocket frame delivery
2. Optional quality presets

---

## Implementation Priority

| Change | Effort | CPU Savings | UX Improvement |
|--------|--------|-------------|----------------|
| Visibility API pause | 1 hour | HIGH | Medium |
| Intersection Observer | 2 hours | HIGH | Low |
| Exponential backoff | 1 hour | LOW | High |
| Direct MJPEG mode | 4 hours | MEDIUM | High |
| Adaptive framerate | 3 hours | MEDIUM | Medium |

---

## Questions to Resolve

1. Is server-side resize heavily used? (bandwidth vs CPU trade-off)
2. What's the typical camera count per Pi installation?
3. Is motion detection overlay critical in live view?
4. Authentication requirements for direct Motion streams?

---

## Notes

- Pi 5 has better CPU than Pi 4, but still constrained
- libcamera already uses significant CPU for encoding
- Goal: Improve perceived performance without adding load
