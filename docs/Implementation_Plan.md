# MotionEye Pi 5 Optimization - Implementation Plan

## Overview

This plan addresses the optimization recommendations from `Prompted_analysis.md` for a **single Raspberry Pi 5 + Pi Camera** setup. Changes are organized by phase with risk assessment and implementation details.

---

## Phase 1: Quick Wins (Low Risk, High Impact)

### 1.1 Debounce Task Saves
**File**: `motioneye/tasks.py`
**Risk**: Low | **Effort**: ~30 min | **Impact**: High (SD card wear reduction)

**Current State**:
- `_save()` called on every `add()` and after each task execution in `_check_tasks()`
- With 2-second check interval, this means constant disk writes

**Implementation**:
```
1. Add module-level state:
   - _dirty = False (flag indicating unsaved changes)
   - _last_save_time = 0 (monotonic timestamp)
   - TASK_SAVE_INTERVAL = 30 (configurable in settings.py)

2. Modify _save():
   - Set _dirty = True instead of immediate write
   - Return immediately (no I/O)

3. Create _flush_if_dirty():
   - Check if _dirty and (now - _last_save_time) > TASK_SAVE_INTERVAL
   - If true: write pickle, set _dirty = False, update _last_save_time

4. Add flush on shutdown:
   - In stop() function, call _flush_if_dirty() unconditionally

5. Add periodic flush:
   - In _check_tasks(), call _flush_if_dirty() after task processing
```

**New Settings** (settings.py):
- `TASK_SAVE_INTERVAL = 30` (seconds between disk writes)
- `TASK_SAVE_ON_SHUTDOWN_ONLY = False` (optional: disable periodic saves entirely)

---

### 1.2 Cache Static Content at Startup
**File**: `motioneye/handlers/picture.py`, `motioneye/server.py`
**Risk**: Low | **Effort**: ~20 min | **Impact**: Medium (reduced I/O per request)

**Current State**:
- `no-preview.svg` read from disk on every 404/error response
- Other static files may have similar patterns

**Implementation**:
```
1. Create motioneye/static_cache.py:
   - _cache = {} dict
   - load_static_files() function called at startup
   - get_static(name) function for retrieval

2. In server.py run():
   - Call static_cache.load_static_files() before starting IOLoop

3. In handlers/picture.py:
   - Replace open().read() with static_cache.get_static('no-preview.svg')

4. Cache these files at minimum:
   - img/no-preview.svg
   - img/error.svg (if exists)
   - Any other frequently-accessed static content
```

---

### 1.3 Reduce Polling Intervals (Configuration Only)
**File**: `motioneye/settings.py`
**Risk**: Very Low | **Effort**: ~5 min | **Impact**: Medium

**Changes**:
```python
# Existing defaults to modify:
MOTION_CHECK_INTERVAL = 30    # Was 10 - motion stable with single camera
MJPG_CLIENT_TIMEOUT = 20      # Was 10 - more tolerance for recording
MJPG_CLIENT_IDLE_TIMEOUT = 60 # Was 10 - occasional viewing, keep connection

# New settings to add:
TASK_SAVE_INTERVAL = 30
TASK_SAVE_ON_SHUTDOWN_ONLY = False
PREPARED_FILES_TIMEOUT = 1800  # 30 min instead of 1 hour
PREPARED_FILES_MAX_SIZE_MB = 500
PREPARED_FILES_MAX_ENTRIES = 10
MEDIA_LISTING_CACHE_TTL = 10
MEDIA_LISTING_MAX_FILES = 1000
```

---

### 1.4 Lazy Log Formatting
**Files**: All Python files
**Risk**: Very Low | **Effort**: ~1 hour | **Impact**: Low-Medium

**Pattern to Replace**:
```python
# FROM:
logging.debug(f'getting disk usage for path {path}...')

# TO:
logging.debug('getting disk usage for path %s...', path)
```

**Implementation**:
- Use grep/sed to find all f-string logging calls
- Replace with lazy % formatting
- Focus on debug/info levels (most frequent)
- Priority files: mediafiles.py, config.py, handlers/*.py

---

## Phase 2: Medium Effort (Moderate Risk)

### 2.1 Replace Subprocess with ThreadPoolExecutor for Media Listing
**File**: `motioneye/mediafiles.py`
**Risk**: Medium | **Effort**: ~2 hours | **Impact**: High

**Current State**:
- `list_media()` spawns `multiprocessing.Process` for each listing request
- 10-50ms overhead per subprocess spawn on Pi 5
- Polling loop with 0.5s intervals adds latency

**Implementation**:
```
1. Create module-level ThreadPoolExecutor:
   - _listing_executor = ThreadPoolExecutor(max_workers=2)
   - Initialize in new start() function called from server.py

2. Modify list_media():
   - Replace multiprocessing.Process with executor.submit()
   - Use asyncio.get_event_loop().run_in_executor()
   - Return awaitable Future directly

3. Update do_list_media():
   - Remove pipe-based communication
   - Return result directly (executor handles threading)

4. Add shutdown handling:
   - Create stop() function to shutdown executor gracefully
   - Call from server.py shutdown sequence
```

**Benefits**:
- Eliminates subprocess spawn overhead
- Thread creation ~1ms vs process ~10-50ms
- No IPC overhead (shared memory)
- Better for I/O-bound operations

---

### 2.2 Implement Media Listing Cache with TTL
**File**: `motioneye/mediafiles.py`
**Risk**: Medium | **Effort**: ~1.5 hours | **Impact**: High

**Implementation**:
```
1. Add cache structure:
   _media_listing_cache = {}
   # Key: (camera_id, media_type, prefix)
   # Value: (timestamp, result_list)

2. Create cache functions:
   - _get_cached_listing(camera_id, media_type, prefix)
   - _set_cached_listing(camera_id, media_type, prefix, results)
   - _invalidate_listing_cache(camera_id=None)

3. Modify list_media():
   - Check cache first with TTL validation
   - If cache hit and fresh: return cached result
   - If miss or stale: fetch and update cache

4. Add cache invalidation triggers:
   - After file upload completes
   - After cleanup runs
   - After timelapse creation
   - Manual invalidation endpoint (optional)

5. Use settings:
   - MEDIA_LISTING_CACHE_TTL = 10 (seconds)
```

**Cache Key Strategy**:
- Include prefix in key for directory-specific caching
- Separate cache entries per camera_id
- TTL-based expiration (not LRU) for simplicity

---

### 2.3 Single-Pass Cleanup Scan
**File**: `motioneye/cleanup.py`, `motioneye/mediafiles.py`
**Risk**: Medium | **Effort**: ~1.5 hours | **Impact**: Medium

**Current State**:
- `_do_cleanup()` calls `cleanup_media('picture')` then `cleanup_media('movie')`
- Each call does full directory scan via `findfiles()`
- Doubles cleanup time for mixed media directories

**Implementation**:
```
1. Create new function in mediafiles.py:
   def cleanup_media_combined(camera_config: dict) -> dict:
       """Single-pass cleanup for both pictures and movies."""

2. Implementation:
   - Single call to findfiles() for target_dir
   - Categorize files by extension during iteration
   - Apply picture retention rules to picture files
   - Apply movie retention rules to movie files
   - Return stats: {pictures_removed, movies_removed, bytes_freed}

3. Modify cleanup.py:
   - Replace two cleanup_media() calls with single cleanup_media_combined()
   - Iterate cameras once, not twice

4. Add early-exit optimization:
   - Check newest file timestamp first
   - If newest file is within retention period, skip full scan
   - Use os.scandir() generator instead of listdir()
```

---

### 2.4 Persistent FFmpeg Path
**File**: `motioneye/mediafiles.py`, `motioneye/config.py`
**Risk**: Low | **Effort**: ~45 min | **Impact**: Low-Medium

**Current State**:
- `find_ffmpeg()` caches result in module variable `_ffmpeg_binary_cache`
- Cache lost on subprocess spawn (cleanup, timelapse workers)
- Each subprocess rediscovers ffmpeg via `which` and codec probing

**Implementation**:
```
1. Add to main config file (motion.conf or motioneye.conf):
   - @ffmpeg_binary_path (auto-discovered, persisted)
   - @ffmpeg_libx264 (boolean: hardware encoding available)

2. Modify find_ffmpeg():
   - First check config for persisted path
   - If found: validate binary exists, return cached
   - If not found or invalid: discover, persist to config, return

3. Pass to subprocesses:
   - Include ffmpeg path in subprocess arguments
   - Avoid re-discovery in worker processes

4. Invalidation:
   - Re-discover on startup if binary doesn't exist
   - Add admin endpoint to force re-discovery
```

---

## Phase 3: Architectural Changes (Higher Risk)

### 3.1 Generator-Based File Iteration with Pagination
**File**: `motioneye/mediafiles.py`
**Risk**: Medium-High | **Effort**: ~3 hours | **Impact**: High (for continuous recording)

**Current State**:
- `findfiles()` returns complete list in memory
- `_list_media_files()` loads all files before filtering
- O(n) memory for n files - problematic with months of recordings

**Implementation**:
```
1. Convert findfiles() to generator:
   def findfiles_gen(path: str) -> typing.Iterator[tuple]:
       for name in os.scandir(path):  # Use scandir for efficiency
           if name.is_dir():
               yield from findfiles_gen(name.path)
           elif name.is_file():
               yield (name.path, name.name, name.stat())

2. Add pagination parameters:
   def list_media_paginated(
       camera_config, media_type, prefix=None,
       offset=0, limit=MEDIA_LISTING_MAX_FILES
   ) -> Awaitable[dict]:
       # Returns: {files: [...], has_more: bool, total_estimate: int}

3. Modify UI to support pagination:
   - Add "Load More" button or infinite scroll
   - Pass offset/limit parameters in API calls

4. Backward compatibility:
   - Keep list_media() for existing callers
   - Internally use paginated version with high limit
```

**Benefits**:
- Memory usage O(page_size) instead of O(total_files)
- Faster initial response (don't wait for full scan)
- Critical for continuous recording (generates many files)

---

### 3.2 Disk-Based Prepared Files Cache
**File**: `motioneye/mediafiles.py`
**Risk**: Medium | **Effort**: ~2 hours | **Impact**: Medium

**Current State**:
- `_prepared_files` dict stores zip/timelapse binary data in RAM
- 1-hour timeout before cleanup
- Unbounded growth until timeout

**Implementation**:
```
1. Create temp directory structure:
   PREPARED_FILES_DIR = os.path.join(settings.RUN_PATH, 'prepared')

2. Modify set_prepared_cache():
   - Write data to temp file instead of memory
   - Store file path in _prepared_files dict
   - Apply size limits (PREPARED_FILES_MAX_SIZE_MB)
   - Apply entry limits (PREPARED_FILES_MAX_ENTRIES)
   - Use LRU eviction when limits exceeded

3. Modify get_prepared_cache():
   - Read from temp file
   - Delete file after retrieval (one-time download)
   - Handle missing file gracefully

4. Cleanup on shutdown:
   - Remove PREPARED_FILES_DIR contents
   - Add to server.py shutdown sequence

5. Reduce timeout:
   - PREPARED_FILES_TIMEOUT = 1800 (30 min)
```

**Memory Savings**:
- Zip files can be 100MB+ each
- Moving to disk frees significant RAM on Pi 5 (4-8GB)

---

### 3.3 Bounded Prepared Files Cache with LRU
**File**: `motioneye/mediafiles.py`
**Risk**: Low-Medium | **Effort**: ~1 hour | **Impact**: Medium

**Implementation** (alternative to 3.2 if disk-based is rejected):
```
1. Add size tracking:
   _prepared_files_total_size = 0

2. Implement LRU with limits:
   from collections import OrderedDict
   _prepared_files = OrderedDict()

3. On set_prepared_cache():
   - Add entry to end (most recent)
   - Update total size
   - While over limit: pop oldest entry

4. On get_prepared_cache():
   - Move accessed entry to end (LRU touch)
```

---

## Phase 4: Optional Enhancements

### 4.1 Disk Usage Caching
**File**: `motioneye/config.py`, `motioneye/utils.py`
**Risk**: Low | **Effort**: ~30 min | **Impact**: Low

```
1. Cache disk usage with 60-second TTL
2. Update asynchronously in background
3. Serve stale data while refreshing
```

### 4.2 V4L2/MMAL Control Caching
**File**: `motioneye/config.py`
**Risk**: Low | **Effort**: ~45 min | **Impact**: Low (single camera)

```
1. Cache v4l2ctl.list_ctrls() results per device
2. Invalidate on device reconnection
3. Add refresh button in UI
```

### 4.3 Selective Config Cache Invalidation
**File**: `motioneye/config.py`
**Risk**: Medium | **Effort**: ~1 hour | **Impact**: Low-Medium

```
1. Add invalidate_camera(camera_id) function
2. Clear only specific camera from _camera_config_cache
3. Keep other caches intact
4. Use file modification timestamps for stale detection
```

---

## Implementation Order

### Week 1: Foundation
1. **1.3** Settings changes (5 min)
2. **1.1** Debounce task saves (30 min)
3. **1.2** Static content cache (20 min)
4. **1.4** Lazy log formatting (1 hour)

### Week 2: Core Improvements
5. **2.1** ThreadPoolExecutor for media listing (2 hours)
6. **2.2** Media listing cache (1.5 hours)
7. **2.3** Single-pass cleanup (1.5 hours)

### Week 3: Advanced
8. **2.4** Persistent ffmpeg path (45 min)
9. **3.2** Disk-based prepared files (2 hours)
10. **3.1** Generator-based iteration (3 hours) - if continuous recording used heavily

---

## Testing Strategy

### Unit Tests
- Task save debouncing: verify no writes within interval
- Media cache: TTL expiration, invalidation
- Prepared files: size limits, LRU eviction

### Integration Tests
- Full cleanup cycle timing comparison
- Media listing response time before/after
- Memory usage under load

### Pi 5 Specific Tests
- SD card write frequency monitoring (`iostat`)
- CPU usage during cleanup
- Memory usage over 24-hour period

---

## Rollback Plan

Each change is isolated and can be reverted independently:

1. **Task debouncing**: Remove dirty flag logic, restore direct `_save()` calls
2. **Static cache**: Remove cache module, restore file reads
3. **ThreadPoolExecutor**: Restore subprocess-based listing
4. **Media cache**: Bypass cache, always fetch fresh
5. **Single-pass cleanup**: Restore separate picture/movie calls

---

## Metrics to Track

### Before Implementation
- Baseline SD card writes per hour
- Media listing response times
- Cleanup cycle duration
- Memory usage at rest and under load

### After Implementation
- Compare all above metrics
- Cache hit rates (add logging)
- Task save frequency

---

## Files Modified Summary

| File | Changes |
|------|---------|
| `motioneye/settings.py` | New settings constants |
| `motioneye/tasks.py` | Debounced saves |
| `motioneye/server.py` | Static cache init, executor shutdown |
| `motioneye/static_cache.py` | New module |
| `motioneye/mediafiles.py` | ThreadPoolExecutor, caching, generators |
| `motioneye/cleanup.py` | Single-pass cleanup |
| `motioneye/config.py` | Selective invalidation, disk usage cache |
| `motioneye/handlers/picture.py` | Static cache usage |
| `motioneye/*.py` | Lazy log formatting |

---

## Notes

- All changes maintain backward compatibility with existing configurations
- No breaking changes to REST API or UI
- Security posture maintained (path validation, auth unchanged)
- Focus on Pi 5 single-camera use case per analysis requirements
