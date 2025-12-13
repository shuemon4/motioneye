# UI Streaming Optimization Implementation Plan

**Date**: 2025-12-13
**Author**: Claude Code
**Status**: Draft - Pending Review
**Target Platform**: Raspberry Pi 5 with 1-2 cameras

---

## Executive Summary

This plan modernizes MotionEye's camera feed display with a focus on **reducing CPU usage** on Raspberry Pi. The approach prioritizes client-side JavaScript optimizations (zero server CPU cost) and adds an optional Direct MJPEG mode that bypasses Python handlers (reduces server CPU).

**Key Constraints:**
- Server-side resize: Low importance (can be sacrificed)
- Camera count: 1-2 cameras typical
- Must not increase Pi CPU usage

---

## Current State Analysis

### Existing Architecture

| Component | Location | Function |
|-----------|----------|----------|
| Refresh loop | `main.js:5490` | `setTimeout(refreshCameraFrames, 15)` - polls every 15ms |
| Frame refresh | `main.js:5402-5432` | `refreshCameraFrame()` - HTTP GET to `/picture/{id}/current/` |
| Error handler | `main.js:5024-5034` | Sets error state, reduces refresh rate |
| Load handler | `main.js:5035-5121` | Clears error, tracks FPS, reads cookies |
| MJPEG mode | `main.js:5445-5458` | Direct stream for `proto == 'mjpeg'` cameras |
| Backend handler | `handlers/picture.py:99-141` | Extracts JPEG from Motion stream |

### Current Inefficiencies

1. **No visibility awareness**: Refreshes continue when browser tab is hidden
2. **No viewport awareness**: Off-screen cameras still refresh
3. **Fixed backoff**: Always 2 seconds on error, no exponential increase
4. **setTimeout drift**: Not synced to browser paint cycle
5. **Continuous polling**: Even when Motion stream is directly available

---

## Implementation Phases

### Phase 1: Client-Side Optimizations (Zero CPU Cost)

All changes in this phase are JavaScript-only and execute in the browser. **No impact on Raspberry Pi CPU.**

#### 1.1 Page Visibility API - Pause Hidden Tabs

**Purpose**: Stop refreshing camera frames when the browser tab is not visible.

**Files Modified**: `motioneye/static/js/main.js`

**Implementation**:

```javascript
// Add near top of file (after line 40)
var pageVisible = true;

document.addEventListener('visibilitychange', function() {
    pageVisible = !document.hidden;
    if (pageVisible) {
        // Resume immediately when tab becomes visible
        refreshCameraFrames();
    }
});
```

**Modify `refreshCameraFrames()`** (line 5490):

```javascript
// Before: setTimeout(refreshCameraFrames, refreshInterval);
// After:
if (pageVisible) {
    setTimeout(refreshCameraFrames, refreshInterval);
} else {
    // Check again in 500ms when hidden (low frequency check)
    setTimeout(refreshCameraFrames, 500);
}
```

**Expected Savings**: 100% CPU reduction when tab hidden (common scenario)

---

#### 1.2 Intersection Observer - Viewport-Aware Refresh

**Purpose**: Only refresh cameras currently visible in the viewport.

**Files Modified**: `motioneye/static/js/main.js`

**Implementation**:

```javascript
// Add near top of file
var cameraVisibility = {}; // {cameraId: boolean}
var intersectionObserver = null;

function initIntersectionObserver() {
    if (!('IntersectionObserver' in window)) {
        return; // Fallback: refresh all cameras
    }

    intersectionObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            var cameraId = entry.target.id.substring(6); // 'camera1' -> '1'
            cameraVisibility[cameraId] = entry.isIntersecting;
        });
    }, {
        threshold: 0.1 // Consider visible if 10% in view
    });
}
```

**Modify `addCameraFrameUi()`** (around line 4870):

```javascript
// After: cameraFrameDiv.attr('id', 'camera' + cameraId);
// Add:
if (intersectionObserver) {
    intersectionObserver.observe(cameraFrameDiv[0]);
}
```

**Modify `refreshCameraFrame()`** (line 5402):

```javascript
function refreshCameraFrame(cameraId, img, serverSideResize) {
    // Add visibility check at start
    if (cameraVisibility[cameraId] === false) {
        return; // Skip refresh for off-screen cameras
    }

    // ... rest of existing function
}
```

**Expected Savings**: Proportional to off-screen cameras (significant in grid view with scrolling)

---

#### 1.3 Exponential Backoff on Errors

**Purpose**: Reduce hammering when a camera is unreachable.

**Files Modified**: `motioneye/static/js/main.js`

**Implementation**:

```javascript
// Add near top of file
var cameraBackoff = {}; // {cameraId: {count: N, nextRetry: timestamp}}
var MAX_BACKOFF_MS = 30000; // Max 30 seconds between retries

function getBackoffDelay(cameraId) {
    var backoff = cameraBackoff[cameraId];
    if (!backoff) return 0;

    var now = new Date().getTime();
    if (now < backoff.nextRetry) {
        return backoff.nextRetry - now;
    }
    return 0;
}

function incrementBackoff(cameraId) {
    var backoff = cameraBackoff[cameraId] || {count: 0};
    backoff.count++;
    // Exponential: 1s, 2s, 4s, 8s, 16s, 30s (capped)
    var delay = Math.min(1000 * Math.pow(2, backoff.count - 1), MAX_BACKOFF_MS);
    backoff.nextRetry = new Date().getTime() + delay;
    cameraBackoff[cameraId] = backoff;
}

function resetBackoff(cameraId) {
    delete cameraBackoff[cameraId];
}
```

**Modify error handler** (line 5024):

```javascript
cameraImg[0].onerror = function () {
    this.error = true;
    this.loading_count = 0;

    var cameraId = cameraFrameDiv.attr('id').substring(6);
    incrementBackoff(cameraId); // Add this line

    // ... rest of existing handler
};
```

**Modify load handler** (line 5035):

```javascript
cameraImg[0].onload = function () {
    if (this.error) {
        var cameraId = cameraFrameDiv.attr('id').substring(6);
        resetBackoff(cameraId); // Add this line

        // ... rest of existing handler
    }
    // ...
};
```

**Modify `refreshCameraFrame()`** (line 5402):

```javascript
function refreshCameraFrame(cameraId, img, serverSideResize) {
    if (refreshDisabled[cameraId]) {
        return;
    }

    // Add backoff check
    if (getBackoffDelay(cameraId) > 0) {
        return;
    }

    // ... rest of existing function
}
```

**Expected Savings**: Significant when cameras offline; reduces error storms

---

#### 1.4 RequestAnimationFrame Synchronization

**Purpose**: Align refresh loop with browser paint cycle for smoother rendering.

**Files Modified**: `motioneye/static/js/main.js`

**Implementation**:

Replace the current `setTimeout` loop with `requestAnimationFrame`:

```javascript
// Add near top of file
var lastRefreshTime = 0;
var useRAF = 'requestAnimationFrame' in window;

function refreshLoop(timestamp) {
    if (!pageVisible) {
        // When hidden, use slower polling
        setTimeout(function() { requestAnimationFrame(refreshLoop); }, 500);
        return;
    }

    // Throttle to ~66fps max (15ms interval)
    if (timestamp - lastRefreshTime >= refreshInterval) {
        lastRefreshTime = timestamp;
        refreshCameraFramesInternal();
    }

    requestAnimationFrame(refreshLoop);
}
```

**Modify initialization** (around document.ready):

```javascript
// Replace: setTimeout(refreshCameraFrames, refreshInterval);
// With:
if (useRAF) {
    requestAnimationFrame(refreshLoop);
} else {
    setTimeout(refreshCameraFrames, refreshInterval); // Fallback
}
```

**Expected Savings**: Smoother rendering, reduced jank, better battery life on laptops

---

### Phase 2: Direct MJPEG Mode (Reduces Server CPU)

**Purpose**: Bypass Python handler and connect directly to Motion's MJPEG stream.

**Trade-off**: Loses server-side resize (acceptable per requirements).

#### 2.1 Add "Direct Streaming" UI Toggle

**Files Modified**:
- `motioneye/templates/main.html` (or wherever settings UI lives)
- `motioneye/static/js/main.js`

**New Setting**: `streaming_direct_mode` (boolean)

**UI Location**: Video Streaming section, below existing controls

```html
<tr class="settings-item advanced-setting" id="streamingDirectModeRow" title="...">
    <td class="settings-item-label">
        <span class="settings-item-label">Direct Streaming</span>
    </td>
    <td class="settings-item-value">
        <input type="checkbox" class="styled" id="streamingDirectModeSwitch">
    </td>
    <td class="settings-item-help">
        <span class="help-mark" title="Connect directly to Motion stream. Reduces CPU usage but disables server-side resize.">?</span>
    </td>
</tr>
```

---

#### 2.2 Implement Direct MJPEG Streaming

**Files Modified**: `motioneye/static/js/main.js`

**Implementation** (modify around line 5445):

```javascript
// In cameraFrames.each() block:
if (!this.img) {
    this.img = $(this).find('img.camera')[0];

    // Check for direct mode (new logic)
    if (this.config['streaming_direct_mode'] && this.config['stream_port']) {
        var directUrl = 'http://' + window.location.hostname + ':' +
                        this.config['stream_port'] + '/1/stream';
        directUrl += '?_=' + new Date().getTime();
        this.img.src = directUrl;
        this.directMode = true;
        return; // No polling needed
    }

    // Existing MJPEG handling
    if (this.config['proto'] == 'mjpeg') {
        // ... existing code
    }
}

// Skip refresh for direct mode cameras
if (this.directMode) {
    return;
}
```

**Note**: Motion 5.0 stream endpoint is `/1/stream` (not `/1/mjpg/stream`). Need to verify with current Motion version.

---

#### 2.3 Motion Detection Status via Separate Channel

**Problem**: Direct MJPEG mode bypasses the picture handler that sets motion detection cookies.

**Solution**: Add a lightweight status polling endpoint or use existing websocket if available.

**Option A - Status Endpoint** (Recommended):

Create new handler `/status/<camera_id>` that returns JSON:

```python
# handlers/status.py (new file)
class StatusHandler(BaseHandler):
    @BaseHandler.auth(prompt=False)
    async def get(self, camera_id):
        self.set_header('Content-Type', 'application/json')
        return self.finish({
            'motion_detected': motionctl.is_motion_detected(camera_id),
            'capture_fps': mjpgclient.get_fps(camera_id),
            'monitor_info': monitor.get_monitor_info(camera_id)
        })
```

**Client-side polling** (once per second):

```javascript
function pollCameraStatus(cameraId) {
    if (!cameraFrames[cameraId].directMode) return;

    $.getJSON(basePath + 'status/' + cameraId, function(data) {
        // Update motion detection indicator
        var frame = $('#camera' + cameraId);
        if (data.motion_detected) {
            frame.addClass('motion-detected');
        } else {
            frame.removeClass('motion-detected');
        }
        // Update FPS display
        frame.find('span.camera-fps').html(data.capture_fps.toFixed(1) + ' fps');
    });
}

// Call every 1000ms for direct mode cameras
setInterval(function() {
    $('.camera-frame').each(function() {
        if (this.directMode) {
            pollCameraStatus(this.id.substring(6));
        }
    });
}, 1000);
```

**Option B - WebSocket** (Future enhancement):
- More efficient for real-time updates
- Higher implementation complexity
- Consider for Phase 3

---

## File Change Summary

| File | Phase | Changes |
|------|-------|---------|
| `motioneye/static/js/main.js` | 1 & 2 | Visibility API, Intersection Observer, backoff, RAF, direct mode |
| `motioneye/templates/main.html` | 2 | Direct streaming toggle UI |
| `motioneye/handlers/status.py` | 2 | New status endpoint (if direct mode) |
| `motioneye/server.py` | 2 | Register status handler route |
| `motioneye/config/camera/converters.py` | 2 | Add streaming_direct_mode config |

---

## Testing Plan

### Phase 1 Testing

| Test Case | Expected Result |
|-----------|-----------------|
| Switch to different browser tab | Camera refresh stops, FPS drops to 0 |
| Return to MotionEye tab | Camera refresh resumes immediately |
| Scroll camera off-screen (grid view) | That camera stops refreshing |
| Disconnect camera | Exponential backoff kicks in (1s, 2s, 4s...) |
| Reconnect camera | Backoff resets, immediate refresh |

### Phase 2 Testing

| Test Case | Expected Result |
|-----------|-----------------|
| Enable Direct Streaming | Stream connects to Motion port directly |
| Motion detection event | Indicator updates (via status endpoint) |
| Disable Direct Streaming | Falls back to snapshot polling |
| Pi CPU usage (htop) | Reduction visible in Python process |

### Browser Compatibility

| Browser | Phase 1 | Phase 2 |
|---------|---------|---------|
| Chrome 90+ | Full support | Full support |
| Firefox 85+ | Full support | Full support |
| Safari 14+ | Full support | Full support |
| Edge 90+ | Full support | Full support |
| IE 11 | Fallback (no IntersectionObserver) | Fallback |

---

## Rollback Plan

All changes are additive and can be disabled:

1. **Phase 1**: Remove visibility/intersection checks, revert to original setTimeout loop
2. **Phase 2**: Hide "Direct Streaming" toggle, always use snapshot polling

No database migrations or config file format changes required.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Intersection Observer not supported | Low | Low | Fallback to refresh all |
| Direct MJPEG auth issues | Medium | Medium | Keep snapshot mode as default |
| Motion detection delay in direct mode | Medium | Low | Status polling every 1s acceptable |
| Browser memory with long MJPEG streams | Low | Medium | MJPEG img tag handles this natively |

---

## Implementation Order

1. **Phase 1.1**: Page Visibility API (~30 min)
2. **Phase 1.3**: Exponential backoff (~45 min)
3. **Phase 1.2**: Intersection Observer (~1 hour)
4. **Phase 1.4**: RequestAnimationFrame (~1 hour)
5. **Phase 2.1**: Direct mode UI toggle (~30 min)
6. **Phase 2.2**: Direct MJPEG implementation (~2 hours)
7. **Phase 2.3**: Status endpoint (~1 hour)

**Total Estimated Time**: ~7 hours

---

## Success Metrics

| Metric | Current | Phase 1 Target | Phase 2 Target |
|--------|---------|----------------|----------------|
| CPU when tab hidden | 100% baseline | <5% | <5% |
| CPU with 2 cams, 1 visible | 100% | ~60% | ~40% |
| Error recovery time | Fixed 2s | Adaptive 1-30s | Adaptive 1-30s |
| Frame jank (visual) | Occasional | Smooth | Smooth |

---

## Open Questions for Review

1. **Motion 5.0 stream endpoint**: Is it `/1/stream` or `/1/mjpg/stream`? Need to verify.
2. **Authentication**: Does direct Motion stream require separate auth handling?
3. **Status endpoint frequency**: Is 1 second polling acceptable for motion detection?
4. **Default behavior**: Should Direct Streaming be opt-in (default off) or opt-out?

---

## Approval Checklist

- [ ] Phase 1 approach approved
- [ ] Phase 2 approach approved
- [ ] Status endpoint design approved
- [ ] UI toggle placement approved
- [ ] Testing plan adequate
- [ ] Rollback plan adequate

---

**Reviewer Notes**: _(To be filled by reviewer)_

