# MotionEye Optimization Analysis for Raspberry Pi 5

## Executive Summary

This document analyzes the MotionEye codebase from a Raspberry Pi 5 optimization perspective, identifying performance bottlenecks, resource inefficiencies, and areas for improvement. The analysis focuses on reducing CPU usage, minimizing SD card wear, improving web UI responsiveness, and ensuring 24/7 reliability.

## Target Use Case

**Hardware**: Raspberry Pi 5 with single Pi Camera module (board camera)

**Usage Pattern**:
- **Recording Modes**: Motion Detection OR Continuous recording (mutually exclusive)
- **Live Viewing**: Occasional, at random times during either recording mode
- **Priority**: Recording takes precedence over live streaming

**Implications for Optimization**:
- Multi-camera scaling concerns are **not applicable**
- MJPEG client management is simpler (single stream)
- Focus on recording I/O efficiency over stream fanout
- Live view can be throttled/degraded if recording is active

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Critical Performance Issues](#critical-performance-issues)
3. [Moderate Priority Issues](#moderate-priority-issues)
4. [Minor Improvements](#minor-improvements)
5. [Configuration Recommendations](#configuration-recommendations)
6. [Implementation Priority](#implementation-priority)

---

## Architecture Overview

### Current Stack
- **Web Framework**: Tornado 6.5+ (async HTTP server)
- **Templating**: Jinja2
- **Image Processing**: Pillow (PIL)
- **Networking**: pycurl, AsyncHTTPClient
- **Background Tasks**: multiprocessing.Pool (single process)
- **Motion Integration**: HTTP control interface (port 7999)

### Key Components Analyzed
| File | Size | Function | Optimization Potential |
|------|------|----------|----------------------|
| `config.py` | 80KB | Configuration management with caching | Medium |
| `mediafiles.py` | 32KB | Media file operations, cleanup, timelapse | High |
| `tasks.py` | 4KB | Background task scheduling | Medium-High |
| `mjpgclient.py` | 13KB | MJPEG stream client | Medium |
| `server.py` | 14KB | Web server, request routing | Low |
| `remote.py` | 28KB | Remote server orchestration | Low |
| `cleanup.py` | 2KB | Media file cleanup subprocess | Medium |

---

## Critical Performance Issues

### 1. Task System Writes to Disk on Every Task Add/Remove

**Location**: `tasks.py:87`, `tasks.py:107`

**Problem**: The `_save()` function is called every time a task is added or removed, writing `tasks.pickle` to disk. This causes:
- Excessive SD card writes (potential wear)
- I/O blocking on task queue operations
- Unnecessary CPU cycles for pickle serialization

```python
def add(when, func, tag=None, callback=None, **params):
    # ... task insertion logic ...
    _save()  # Called on every add!

def _check_tasks():
    # ...
    if changed:
        _save()  # Called on every task execution!
```

**Impact**: With multiple cameras generating motion events, tasks can be added frequently, causing constant disk writes.

**Recommendation**:
- Debounce saves (e.g., max once per 30 seconds)
- Use a dirty flag and save only on shutdown or periodically
- Consider keeping task state in memory only (tasks survive restart via `_load()` but most are short-lived anyway)

---

### 2. Synchronous File I/O in Request Handlers

**Location**: `handlers/picture.py:305-309`, `mediafiles.py:517-532`

**Problem**: Several handlers perform synchronous file reads:

```python
# handlers/picture.py:305-309
content = open(
    os.path.join(settings.STATIC_PATH, 'img', 'no-preview.svg'), 'rb'
).read()
```

**Impact**: Blocks the Tornado event loop, reducing responsiveness for all concurrent requests.

**Recommendation**:
- Cache static content at startup
- Use `aiofiles` or thread pool executor for file I/O
- Pre-load frequently accessed resources

---

### 3. Media Listing Spawns Subprocess Per Request

**Location**: `mediafiles.py:418-508`

**Problem**: `list_media()` creates a new `multiprocessing.Process` for every listing request:

```python
def list_media(camera_config: dict, media_type: str, prefix=None) -> typing.Awaitable:
    # ...
    process = multiprocessing.Process(target=do_list_media, args=(child_pipe,))
    process.start()
```

**Impact**:
- Process creation overhead (~10-50ms per spawn on Pi 5)
- Memory overhead for each subprocess
- High context switching under load
- Polling loop with 0.5s interval adds latency

**Recommendation**:
- Use `ThreadPoolExecutor` instead of multiprocessing for I/O-bound file listing
- Implement result caching with TTL (e.g., 5-10 seconds)
- Consider async directory iteration using `aiofiles` or `os.scandir()` generators

---

### 4. Recursive Directory Scanning Without Pagination

**Location**: `mediafiles.py:108-123`

**Problem**: `findfiles()` recursively scans entire directory trees:

```python
def findfiles(path: str) -> typing.List[tuple]:
    files = []
    for name in os.listdir(path):
        # ...
        if S_ISDIR(mode):
            files.extend(findfiles(pathname))  # Recursive!
        elif S_ISREG(mode):
            files.append((pathname, name, st))
    return files
```

**Impact**:
- With months of recordings, directories can contain 10,000+ files
- O(n) memory usage - entire file list loaded into memory
- Blocks event loop during scan
- No early termination or pagination

**Recommendation**:
- Use generators (`yield`) instead of list accumulation
- Implement pagination (return first N files, with "more available" flag)
- Add date-range filtering at scan level
- Cache directory listings with invalidation on file changes

---

### 5. Cleanup Process Scans All Files Twice

**Location**: `cleanup.py:79-92`, `mediafiles.py:288-346`

**Problem**: `cleanup_media()` is called separately for pictures and movies, each performing a full directory scan:

```python
def _do_cleanup():
    mediafiles.cleanup_media('picture')  # Full scan
    mediafiles.cleanup_media('movie')    # Another full scan
```

**Impact**: Doubles cleanup time; on large media directories, this can take minutes and consume significant CPU.

**Recommendation**:
- Single pass that handles both pictures and movies
- Use file extension to categorize during single scan
- Add early exit if no files need cleanup (check newest file first)

---

### 6. FFmpeg Binary Discovery on Every Operation

**Location**: `mediafiles.py:226-285`

**Problem**: While `find_ffmpeg()` has caching, the cache is module-level and only persists within a single process. Subprocesses (cleanup, timelapse) rediscover ffmpeg each time.

```python
_ffmpeg_binary_cache = None

def find_ffmpeg() -> tuple:
    global _ffmpeg_binary_cache
    if _ffmpeg_binary_cache:
        return _ffmpeg_binary_cache
    # ... expensive discovery ...
```

**Impact**: Subprocess calls to `which ffmpeg` and `ffmpeg -codecs` add latency.

**Recommendation**:
- Persist ffmpeg path in settings/config
- Validate once at startup
- Pass path to subprocesses via arguments

---

## Moderate Priority Issues

### 7. MJPEG Client Garbage Collector Polling

**Location**: `mjpgclient.py:367-415`

**Problem**: The garbage collector runs at `MJPG_CLIENT_TIMEOUT` intervals (default 10s) and iterates over all clients:

```python
def _garbage_collector():
    io_loop.add_timeout(
        datetime.timedelta(seconds=settings.MJPG_CLIENT_TIMEOUT), _garbage_collector
    )
    for camera_id, client in list(MjpgClient.clients.items()):
        # ... check each client ...
```

**Impact**: ~~Minor, but with many cameras, this creates periodic CPU spikes.~~ **REDUCED PRIORITY for single-camera setup** - With only one camera, this loop is trivial.

**Recommendation**:
- ~~Use per-client timeouts instead of global polling~~
- **For single camera**: Keep as-is; the overhead is negligible
- Consider increasing `MJPG_CLIENT_IDLE_TIMEOUT` to reduce reconnection churn during occasional live viewing

---

### 8. Config Cache Invalidation Strategy

**Location**: `config.py:2057-2067`

**Problem**: `invalidate()` clears all caches, requiring full reload:

```python
def invalidate():
    global _main_config_cache, _camera_config_cache, _camera_ids_cache
    _main_config_cache = None
    _camera_config_cache = {}
    _camera_ids_cache = None
```

This is called after backup restore but could be triggered too aggressively.

**Impact**: Next request must re-read all config files from disk.

**Recommendation**:
- Implement selective cache invalidation (per-camera)
- Use file modification timestamps to detect stale cache

---

### 9. Prepared Files Cache Unbounded Growth

**Location**: `mediafiles.py:99-100`, `mediafiles.py:1040-1063`

**Problem**: The `_prepared_files` cache stores large binary data (zip files, timelapse movies):

```python
_prepared_files = {}

def set_prepared_cache(data):
    key = sha1(str(time()).encode()).hexdigest()
    _prepared_files[key] = data
    # Timeout-based cleanup after 1 hour
```

**Impact**: If users generate but don't download files, memory grows unboundedly until timeout (1 hour).

**Recommendation**:
- Limit cache size (e.g., max 500MB or 10 entries)
- Use LRU eviction
- Store large files on disk in temp directory instead of RAM
- Reduce timeout for Pi 5 (30 minutes should suffice)

---

### 10. V4L2 Control Enumeration on Config Access

**Location**: `config.py:1546-1582`

**Problem**: Getting camera config triggers V4L2 control enumeration:

```python
video_controls = v4l2ctl.list_ctrls(data['videodevice'])
```

**Impact**: System calls to v4l2-ctl add latency to config requests.

**Note**: For Pi Camera module, this may use `mmalcam_name` instead of `videodevice`, so V4L2 enumeration may not apply. Verify which interface your Pi Camera uses.

**Recommendation**:
- Cache V4L2/MMAL controls per device
- Invalidate only on device reconnection or explicit refresh
- For Pi Camera: Check if MMAL controls have similar overhead

---

### 11. Motion Detection State File Access

**Location**: `motionctl.py` (referenced throughout)

**Problem**: Motion detection state may involve frequent file or HTTP checks.

**Recommendation**:
- Cache motion detection state with short TTL (1-2 seconds)
- Use event-driven updates from motion daemon if possible

---

## Minor Improvements

### 12. Logging Overhead

**Location**: Throughout codebase

**Problem**: Debug logging with string formatting even when debug level is disabled:

```python
logging.debug(f'getting disk usage for path {path}...')
```

**Impact**: String formatting occurs before log level check.

**Recommendation**:
- Use lazy formatting: `logging.debug('getting disk usage for path %s...', path)`
- Consider reducing default log level to `WARNING` in production

---

### 13. Disk Usage Calculation Per Config Access

**Location**: `config.py:1619-1624`

**Problem**: `get_disk_usage()` called during config to UI conversion:

```python
usage = utils.get_disk_usage(data['target_dir'])
```

**Impact**: Syscall overhead, though relatively minor.

**Recommendation**:
- Cache disk usage with 60-second TTL
- Update asynchronously in background

---

### 14. Image Resizing Without Caching

**Location**: `mediafiles.py:903-919`, `mediafiles.py:995-1037`

**Problem**: Preview images are resized on every request:

```python
image.thumbnail((width, height), Image.BILINEAR)
```

**Impact**: CPU-intensive for large images, especially at common preview sizes.

**Recommendation**:
- Cache resized thumbnails on disk (named by size)
- Generate common sizes during idle time
- Use faster resize algorithms for previews (NEAREST or BOX)

---

### 15. Regex Compilation in Request Path

**Location**: `mjpgclient.py:281`, `server.py:48`

**Problem**: Regexes compiled at module level is good, but some are repeated:

```python
_CURRENT_PICTURE_REGEX = re.compile(r'^/picture/\d+/current')
```

**Status**: Already well-optimized.

---

## Single-Camera Specific Recommendations

### Recording Priority Over Live Streaming

For your use case where recording must take precedence over live viewing:

**Current Behavior**: MotionEye's MJPEG client connects to motion's stream port, which is the same stream used for recording. There's no explicit prioritization.

**Recommendations**:

1. **Reduce live stream quality when recording**:
   - Configure motion's `stream_maxrate` to a lower FPS (e.g., 5) during recording
   - Full framerate goes to recording, reduced rate to live view

2. **Increase stream buffer tolerance**:
   - Set `MJPG_CLIENT_TIMEOUT` higher (15-20s) to tolerate dropped frames during heavy recording I/O

3. **Consider separate stream port** (if supported by motion version):
   - Primary port for recording at full quality
   - Secondary port for live view at reduced quality

### Pi Camera Module Considerations

The Pi Camera uses MMAL (Multi-Media Abstraction Layer) on older systems or libcamera on newer Pi OS:

1. **Check camera interface**:
   ```bash
   # For MMAL (legacy)
   vcgencmd get_camera

   # For libcamera (modern)
   libcamera-hello --list-cameras
   ```

2. **GPU memory allocation**: Ensure sufficient GPU memory for encoding:
   ```bash
   # In /boot/config.txt
   gpu_mem=256  # For 1080p recording
   ```

3. **Hardware encoding**: Motion should use the Pi's hardware H.264 encoder. Verify this is active to minimize CPU load.

## Configuration Recommendations

### Recommended settings.py Tuning for Pi 5 (Single Camera)

```python
# Polling frequencies - can be more relaxed with single camera
MOTION_CHECK_INTERVAL = 30  # Was 10, motion is stable with single camera
MJPG_CLIENT_TIMEOUT = 20    # Was 10, more tolerance for recording priority
MJPG_CLIENT_IDLE_TIMEOUT = 60  # Was 10, you view occasionally so keep connection longer

# Cleanup interval - adjust based on storage capacity
CLEANUP_INTERVAL = 86400  # 24 hours; adjust based on SD card size

# Remote settings - not needed for single local camera
REMOTE_REQUEST_TIMEOUT = 5  # Was 10, fail faster (or disable remote features entirely)

# Media listing timeout
LIST_MEDIA_TIMEOUT = 60  # Was 120, prompt user sooner
```

### New Settings to Consider Adding

```python
# Prepared files cache settings
PREPARED_FILES_MAX_SIZE_MB = 500
PREPARED_FILES_MAX_ENTRIES = 10
PREPARED_FILES_TIMEOUT = 1800  # 30 minutes

# Task persistence settings
TASK_SAVE_INTERVAL = 30  # Seconds between disk writes
TASK_SAVE_ON_SHUTDOWN_ONLY = True

# Media listing cache
MEDIA_LISTING_CACHE_TTL = 10  # Seconds
MEDIA_LISTING_MAX_FILES = 1000  # Pagination limit
```

---

## Implementation Priority (Revised for Single Camera)

### Phase 1: Quick Wins (Low Risk, High Impact)
1. **Debounce task saves** - Simple change, significant SD card wear reduction
2. **Cache static content** - One-time load at startup
3. **Reduce polling intervals** - Configuration-only change
4. **Use lazy log formatting** - Search and replace

### Phase 2: Medium Effort (Moderate Risk)
5. **Replace subprocess with ThreadPoolExecutor** for media listing
6. **Implement media listing cache** with TTL
7. **Single-pass cleanup scan** for pictures and movies
8. ~~Cache V4L2 controls per device~~ **Lower priority** - single camera, infrequent config access

### Phase 3: Architectural Changes (Higher Risk)
9. **Generator-based file iteration** with pagination - **Important for long-term recording**
10. **Disk-based prepared files cache** for large data
11. ~~Async file I/O throughout handlers~~ **Lower priority** - single camera reduces concurrency pressure
12. **Persistent ffmpeg path** in configuration

### Deprioritized for Single-Camera Setup
- MJPEG client garbage collector optimization (trivial with one camera)
- Per-client timeout management (single client)
- Remote server features (local camera only)
- Multi-camera scaling patterns

### New Priority: Continuous Recording Considerations

Since you alternate between Motion Detection and Continuous recording:

1. **SD Card Write Optimization** - **CRITICAL**
   - Continuous recording generates constant write I/O
   - Consider external USB SSD for recordings (reduces SD card wear)
   - If using SD card: Use high-endurance card (e.g., Samsung PRO Endurance)

2. **File Segmentation Settings**
   - Configure motion's `movie_max_time` to segment recordings (e.g., 15-minute chunks)
   - Smaller files = easier cleanup, faster listing, less data loss on corruption

3. **Cleanup Strategy for Continuous Mode**
   - More aggressive cleanup needed (recordings accumulate faster)
   - Consider reducing `CLEANUP_INTERVAL` to 6 hours for continuous mode
   - Set appropriate `disk_usage` threshold in MotionEye config

4. **Generator-based file iteration becomes MORE important**
   - Continuous recording creates many more files than motion-only
   - Pagination/generators prevent memory issues when listing days of recordings

---

## Performance Monitoring Recommendations

### Metrics to Track

1. **CPU Usage**: Per-process (motioneye, motion)
2. **Memory Usage**: RSS and heap growth over time
3. **SD Card Writes**: `iostat` or `/proc/diskstats`
4. **Request Latency**: P50, P95, P99 for key endpoints
5. **Cache Hit Rates**: Config, media listing, prepared files

### Logging for Performance

Add optional timing logs:

```python
import time

class Timer:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        self.start = time.monotonic()
        return self
    def __exit__(self, *args):
        elapsed = time.monotonic() - self.start
        if elapsed > 0.1:  # Log slow operations
            logging.warning(f'{self.name} took {elapsed:.2f}s')
```

---

## Security Notes

While optimizing, maintain security posture:

1. **Input validation** remains intact in config handlers
2. **Path traversal protection** (`'..' in path` check) preserved
3. **Authentication decorators** unchanged
4. **Subprocess calls** use proper quoting

---

## Conclusion

The MotionEye codebase is well-structured for its purpose but has several areas that can be optimized for Raspberry Pi 5's constrained environment.

### For Your Single-Camera Setup, the Most Impactful Changes Are:

1. **Reducing disk writes from the task system** - Protects SD card during 24/7 operation
2. **Implementing caching for media listings** - Critical for continuous recording which generates many files
3. **Generator-based file iteration with pagination** - Prevents memory issues with long recording histories
4. **Optimizing cleanup for continuous recording mode** - Single-pass scan, appropriate intervals

### Lower Priority for Single Camera:
- Multi-camera scaling optimizations
- MJPEG client management complexity
- Remote server features
- High-concurrency async patterns

### Hardware Recommendations:
- **Strongly consider external USB SSD** for recordings to protect SD card
- Ensure adequate GPU memory allocation for Pi Camera encoding
- Use high-endurance SD card if not using external storage

These changes would significantly reduce SD card wear and improve responsiveness while maintaining reliable 24/7 video surveillance with your Pi Camera module.

---

## References

- [Tornado Performance Best Practices](https://www.tornadoweb.org/en/stable/guide/running.html)
- [Python asyncio and File I/O](https://docs.python.org/3/library/asyncio-task.html)
- [Raspberry Pi SD Card Wear Optimization](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [Motion Project Documentation](https://motion-project.github.io/motion_config.html)
