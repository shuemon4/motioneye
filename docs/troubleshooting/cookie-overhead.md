# Cookie Overhead on Frame Requests

**Last Updated**: 2025-12-24
**Status**: Known behavior (upstream design)
**Priority**: Low - Performance optimization opportunity

---

## Symptom

Browser DevTools shows cookies being set on every frame request:

```
Request URL: http://192.168.1.176:8765/picture/1/current/?_=1766613671937
Status Code: 200 OK

Response Headers:
set-cookie: motion_detected_1=false; Path=/
set-cookie: capture_fps_1=24.9; Path=/
set-cookie: monitor_info_1=""; Path=/
```

This happens 15-30 times per second per camera (matching the streaming framerate).

---

## Root Cause

This is **original upstream MotionEye design**, not a fork-specific issue.

The picture handler (`motioneye/handlers/picture.py:131-154`) sets cookies on every frame response to communicate metadata to the JavaScript:

```python
# Local camera
self.set_cookie('motion_detected_' + camera_id_str, ...)
self.set_cookie('capture_fps_' + camera_id_str, ...)
self.set_cookie('monitor_info_' + camera_id_str, ...)

# Remote camera
self.set_cookie('motion_detected_' + camera_id_str, str(resp.motion_detected).lower())
self.set_cookie('capture_fps_' + camera_id_str, '%.1f' % resp.capture_fps)
self.set_cookie('monitor_info_' + camera_id_str, resp.monitor_info or '')
```

The JavaScript reads these cookies to update UI elements:

- **motion_detected**: Shows red border on camera frame when motion detected
- **capture_fps**: Displays FPS in camera overlay
- **monitor_info**: Shows additional monitor status

**Files involved:**
- `motioneye/handlers/picture.py` - Sets cookies
- `motioneye/static/js/main.js:5499-5514` - Reads cookies
- `motioneye/static/js/frame.js:54` - Reads motion_detected cookie

---

## Impact

### HTTP Overhead
- 3 `Set-Cookie` headers added to every frame response
- Each cookie adds ~50-100 bytes to response headers
- At 25 fps: ~150-300 extra bytes/second per camera
- Minimal impact on modern networks, but inefficient

### Browser Cookie Storage
- Cookies accumulate per camera ID
- Not a significant storage concern

### CPU Impact
- Cookie parsing on every request
- Minimal but non-zero overhead

---

## Why It Exists

The original MotionEye design needed to communicate real-time metadata (motion detection, FPS) without:
1. Making separate AJAX calls (would double request count)
2. Modifying the JPEG image data
3. Using WebSockets (adds complexity)

Cookies provided a simple "side-channel" that rides along with existing frame requests.

---

## Potential Optimizations

### Option 1: Use HTTP Headers Instead of Cookies
Replace `set_cookie()` with custom headers:

```python
self.set_header('X-Motion-Detected', 'true')
self.set_header('X-Capture-FPS', '24.9')
self.set_header('X-Monitor-Info', '')
```

**Pros**: No cookie storage, slightly smaller overhead
**Cons**: Requires JavaScript changes to read from XHR headers instead of cookies

### Option 2: Only Set Cookies When Values Change
Cache previous values and only set cookies when they differ:

```python
if motion_state != self.get_cookie('motion_detected_' + camera_id_str):
    self.set_cookie('motion_detected_' + camera_id_str, motion_state)
```

**Pros**: Dramatically reduces cookie traffic
**Cons**: Adds state tracking, potential sync issues

### Option 3: Separate Polling Endpoint
Create a lightweight JSON endpoint polled every 1-2 seconds:

```
GET /status/1 → {"motion_detected": false, "fps": 24.9, "monitor_info": ""}
```

**Pros**: Clean separation of concerns
**Cons**: Additional requests (though much less frequent)

Note: This was partially implemented as `streaming_direct_mode` but was removed as dead code (2025-12-24) because the UI was hidden and it exposed an unauthenticated port.

### Option 4: WebSocket for Real-time Updates
Push updates only when values change via WebSocket.

**Pros**: Most efficient for real-time updates
**Cons**: Significant architectural change, adds complexity

---

## Recommendation

**Leave as-is for now.** The overhead is minimal and the current design works reliably.

If optimization is desired in the future:
1. **Option 2** (conditional cookies) offers the best effort-to-benefit ratio
2. **Option 1** (HTTP headers) is cleaner but requires more JavaScript changes
3. **Option 3** (polling endpoint) is good if adding other status features

---

## Related Files

| File | Purpose |
|------|---------|
| `motioneye/handlers/picture.py` | Sets cookies on frame response |
| `motioneye/static/js/main.js` | Reads cookies for UI updates |
| `motioneye/static/js/frame.js` | Reads motion_detected for embed frame |
| `motioneye/remote.py` | Reads cookies from remote camera responses |
