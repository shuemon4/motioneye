# MotionEye Pi 5 Optimization - Implementation Summary

This document details the optimizations implemented for running MotionEye on a Raspberry Pi 5 with a single Pi Camera setup. All changes focus on reducing SD card wear, improving response times, and managing memory efficiently.

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 1: Quick Wins](#phase-1-quick-wins)
3. [Phase 2: Medium Effort Improvements](#phase-2-medium-effort-improvements)
4. [Phase 3: Memory Management](#phase-3-memory-management)
5. [Configuration Reference](#configuration-reference)
6. [Files Modified](#files-modified)
7. [Performance Impact](#performance-impact)
8. [Rollback Instructions](#rollback-instructions)

---

## Overview

### Goals
- **Reduce SD card writes** - Minimize wear on flash storage
- **Improve response times** - Faster media listing and UI interactions
- **Manage memory** - Prevent unbounded cache growth on limited RAM
- **Maintain compatibility** - No breaking changes to API or configuration

### Implementation Approach
Changes were organized into three phases by risk level:
- **Phase 1**: Low risk, high impact quick wins
- **Phase 2**: Moderate risk, requires testing
- **Phase 3**: Memory management improvements

---

## Phase 1: Quick Wins

### 1.1 Debounced Task Saves

**File**: `motioneye/tasks.py`

**Problem**: Tasks were saved to disk on every add and after each task execution (every 2 seconds), causing excessive SD card writes.

**Solution**: Implemented debounced saving with configurable interval.

**Changes**:
```python
# New module-level state
_dirty = False
_last_save_time = 0

# New functions
def _mark_dirty():
    """Mark task state as dirty (needs saving)."""
    global _dirty
    _dirty = True

def _flush_if_dirty(force=False):
    """Flush to disk if dirty and interval has passed."""
    # Only writes if _dirty=True AND interval exceeded
    # force=True bypasses interval check (used on shutdown)

def _do_save():
    """Actually write tasks to disk."""
    # Moved from old _save() function
```

**Behavior**:
- `add()` now calls `_mark_dirty()` instead of immediate save
- `_check_tasks()` calls `_flush_if_dirty()` after processing
- `stop()` calls `_flush_if_dirty(force=True)` to ensure data is saved on shutdown
- Default interval: 30 seconds (configurable via `TASK_SAVE_INTERVAL`)

---

### 1.2 Static Content Cache

**File**: `motioneye/static_cache.py` (new)

**Problem**: `no-preview.svg` was read from disk on every 404/error response in picture and movie previews.

**Solution**: Cache frequently-accessed static files in memory at startup.

**Implementation**:
```python
# Cache storage
_cache = {}

# Files cached at startup
_CACHE_FILES = [
    'img/no-preview.svg',
    'img/error.svg',
]

def load_static_files():
    """Load static files into memory cache at startup."""

def get_static(name):
    """Get a static file from cache (returns None if not found)."""

def get_static_or_read(name):
    """Get from cache with fallback to disk read."""
```

**Integration**:
- `server.py`: Calls `static_cache.load_static_files()` at startup
- `handlers/picture.py`: Uses `static_cache.get_static_or_read('img/no-preview.svg')`
- `handlers/movie.py`: Uses `static_cache.get_static_or_read('img/no-preview.svg')`

---

### 1.3 Polling Interval Adjustments

**File**: `motioneye/settings.py`

**Changes**:
| Setting | Old Value | New Value | Rationale |
|---------|-----------|-----------|-----------|
| `MOTION_CHECK_INTERVAL` | 10s | 30s | Motion stable with single camera |
| `MJPG_CLIENT_TIMEOUT` | 10s | 20s | More tolerance for recording |
| `MJPG_CLIENT_IDLE_TIMEOUT` | 10s | 60s | Keep connection for occasional viewing |

---

## Phase 2: Medium Effort Improvements

### 2.1 ThreadPoolExecutor for Media Listing

**File**: `motioneye/mediafiles.py`

**Problem**: `list_media()` spawned a new `multiprocessing.Process` for each request, with 10-50ms overhead per spawn on Pi 5.

**Solution**: Replace with `ThreadPoolExecutor` for lower overhead on I/O-bound operations.

**Implementation**:
```python
# Module-level executor
_listing_executor = None

def start():
    """Initialize ThreadPoolExecutor (called from server.py)."""
    global _listing_executor
    _listing_executor = ThreadPoolExecutor(max_workers=2)

def stop():
    """Shutdown executor (called from server.py)."""
    if _listing_executor:
        _listing_executor.shutdown(wait=True)

def _do_list_media_sync(target_dir, exts, prefix):
    """Synchronous worker function for thread pool."""
    # Returns list of media file dicts

def list_media(camera_config, media_type, prefix=None):
    """List media using thread pool instead of subprocess."""
    # Submits work to executor, returns Future
```

**Benefits**:
- Thread creation ~1ms vs process spawn ~10-50ms
- No IPC overhead (shared memory)
- Better suited for I/O-bound directory scanning

---

### 2.2 Media Listing Cache with TTL

**File**: `motioneye/mediafiles.py`

**Problem**: Repeated media listing requests caused redundant directory scans.

**Solution**: TTL-based cache for media listing results.

**Implementation**:
```python
# Cache structure
# Key: (camera_id, media_type, prefix)
# Value: (timestamp, result_list)
_media_listing_cache = {}

def _get_cached_listing(camera_id, media_type, prefix):
    """Get cached result if fresh (within TTL)."""

def _set_cached_listing(camera_id, media_type, prefix, results):
    """Store results in cache with current timestamp."""

def invalidate_listing_cache(camera_id=None):
    """Clear cache entries (all or per-camera)."""
```

**Cache Behavior**:
- TTL: 10 seconds (configurable via `MEDIA_LISTING_CACHE_TTL`)
- Automatically checked and populated in `list_media()`
- Can be invalidated after file operations

---

### 2.3 Single-Pass Cleanup Scan

**Files**: `motioneye/mediafiles.py`, `motioneye/cleanup.py`

**Problem**: `_do_cleanup()` called `cleanup_media('picture')` then `cleanup_media('movie')`, resulting in two full directory scans per camera.

**Solution**: New `cleanup_media_combined()` function that handles both in one pass.

**Implementation**:
```python
def cleanup_media_combined() -> dict:
    """
    Single-pass cleanup for both pictures and movies.

    Returns:
        dict: {
            'pictures_removed': int,
            'movies_removed': int,
            'bytes_freed': int,
            'cameras_processed': int
        }
    """
```

**Algorithm**:
1. Iterate cameras once
2. Calculate retention thresholds for both pictures and movies
3. Single `findfiles()` call per camera
4. Categorize files by extension during iteration
5. Apply appropriate retention rules per file type
6. Return combined statistics

**Updated cleanup.py**:
```python
def _do_cleanup():
    stats = mediafiles.cleanup_media_combined()
    logging.debug(
        'cleanup done: %d pictures, %d movies removed, %d bytes freed',
        stats['pictures_removed'],
        stats['movies_removed'],
        stats['bytes_freed']
    )
```

---

### 2.4 FFmpeg Path Caching

**File**: `motioneye/mediafiles.py`

**Problem**: `find_ffmpeg()` runs `which ffmpeg` and codec probing, which is expensive in subprocesses that lose the cache.

**Solution**: Refactored for clearer caching and added helper function.

**Implementation**:
```python
def _discover_ffmpeg() -> tuple:
    """Expensive discovery operation."""
    # Runs 'which', version check, codec enumeration
    return (binary, version, codecs)

def find_ffmpeg() -> tuple:
    """Cached wrapper around discovery."""
    global _ffmpeg_binary_cache
    if _ffmpeg_binary_cache:
        return _ffmpeg_binary_cache
    _ffmpeg_binary_cache = _discover_ffmpeg()
    return _ffmpeg_binary_cache

def get_ffmpeg_binary() -> str:
    """Get just the path for subprocess calls."""
    result = find_ffmpeg()
    return result[0] if result else None
```

---

## Phase 3: Memory Management

### 3.2 + 3.3 Bounded LRU Prepared Files Cache

**File**: `motioneye/mediafiles.py`

**Problem**: `_prepared_files` dict stored zip/timelapse binary data in RAM with 1-hour timeout and no size limits. Could cause memory exhaustion.

**Solution**: Bounded LRU cache with configurable limits.

**Implementation**:
```python
from collections import OrderedDict

# LRU cache: Key -> (data, size, timestamp)
_prepared_files = OrderedDict()
_prepared_files_total_size = 0

def _evict_prepared_cache_lru():
    """Evict oldest entries if over limits."""
    max_size_bytes = settings.PREPARED_FILES_MAX_SIZE_MB * 1024 * 1024
    max_entries = settings.PREPARED_FILES_MAX_ENTRIES

    # Evict by count
    while len(_prepared_files) > max_entries:
        key, (data, size, ts) = _prepared_files.popitem(last=False)
        _prepared_files_total_size -= size

    # Evict by size
    while _prepared_files_total_size > max_size_bytes and _prepared_files:
        key, (data, size, ts) = _prepared_files.popitem(last=False)
        _prepared_files_total_size -= size

def get_prepared_cache(key):
    """Get and remove entry, updating size tracking."""

def set_prepared_cache(data):
    """Add entry with LRU eviction and timeout scheduling."""
```

**Defaults**:
- `PREPARED_FILES_TIMEOUT`: 1800 seconds (30 minutes, was 1 hour)
- `PREPARED_FILES_MAX_SIZE_MB`: 500 MB
- `PREPARED_FILES_MAX_ENTRIES`: 10 entries

---

## Configuration Reference

All new settings in `motioneye/settings.py`:

```python
# =============================================================================
# Pi 5 Optimization Settings
# =============================================================================

# Task save debouncing - reduces SD card writes
TASK_SAVE_INTERVAL = 30  # seconds between disk writes
TASK_SAVE_ON_SHUTDOWN_ONLY = False  # if True, only save tasks on shutdown

# Prepared files cache limits - prevents unbounded memory growth
PREPARED_FILES_TIMEOUT = 1800  # 30 minutes (was 1 hour)
PREPARED_FILES_MAX_SIZE_MB = 500  # maximum total cache size
PREPARED_FILES_MAX_ENTRIES = 10  # maximum number of cached items

# Media listing cache TTL - reduces repeated directory scans
MEDIA_LISTING_CACHE_TTL = 10  # seconds to cache media listings

# Maximum files to return in a single listing (for pagination support)
MEDIA_LISTING_MAX_FILES = 1000
```

---

## Files Modified

| File | Changes |
|------|---------|
| `motioneye/settings.py` | New Pi 5 optimization settings, adjusted polling intervals |
| `motioneye/tasks.py` | Debounced task saves with `_mark_dirty()` and `_flush_if_dirty()` |
| `motioneye/static_cache.py` | **New file** - Static content caching module |
| `motioneye/server.py` | Initialize/shutdown static_cache and mediafiles modules |
| `motioneye/mediafiles.py` | ThreadPoolExecutor, media listing cache, single-pass cleanup, LRU prepared cache, ffmpeg caching |
| `motioneye/cleanup.py` | Uses `cleanup_media_combined()` for single-pass cleanup |
| `motioneye/handlers/picture.py` | Uses static_cache for no-preview.svg |
| `motioneye/handlers/movie.py` | Uses static_cache for no-preview.svg |

---

## Performance Impact

### Expected Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Task saves per hour | ~1800 | ~120 | 93% reduction |
| Media listing response | 50-100ms | 1-10ms (cached) | 90%+ faster |
| Cleanup scan time | 2x directory scan | 1x directory scan | 50% reduction |
| Static file I/O | Every request | Once at startup | ~100% reduction |
| Process spawn overhead | 10-50ms per listing | ~1ms per listing | 90%+ reduction |

### Memory Usage

| Component | Before | After |
|-----------|--------|-------|
| Prepared files cache | Unbounded | Max 500MB, 10 entries |
| Static cache | 0 | ~10-50KB |
| Media listing cache | 0 | ~1-10KB per camera |

---

## Rollback Instructions

Each change is isolated and can be reverted independently:

### Task Debouncing
Restore `_save()` calls in `tasks.py`:
- Replace `_mark_dirty()` with `_save()` in `add()`
- Replace `_flush_if_dirty()` with `_save()` in `_check_tasks()`
- Remove `_flush_if_dirty(force=True)` from `stop()`

### Static Cache
- Remove `static_cache.load_static_files()` from `server.py`
- Revert `handlers/picture.py` and `handlers/movie.py` to use `open().read()`
- Delete `motioneye/static_cache.py`

### ThreadPoolExecutor
- Remove `mediafiles.start()` and `mediafiles.stop()` from `server.py`
- Restore original `list_media()` function with `multiprocessing.Process`

### Media Listing Cache
- Remove cache check/set calls from `list_media()`
- Delete cache-related functions

### Single-Pass Cleanup
- Restore original `_do_cleanup()` in `cleanup.py`:
  ```python
  mediafiles.cleanup_media('picture')
  mediafiles.cleanup_media('movie')
  ```

### Prepared Files LRU Cache
- Restore `_prepared_files = {}` (regular dict)
- Restore original `get_prepared_cache()` and `set_prepared_cache()`

---

## Testing Recommendations

### Unit Tests
- Task save debouncing: Verify no writes within interval
- Media cache: TTL expiration, invalidation
- Prepared files: Size limits, LRU eviction, entry limits

### Integration Tests
- Full cleanup cycle timing comparison
- Media listing response time before/after
- Memory usage under load

### Pi 5 Specific Tests
- SD card write frequency monitoring (`iostat -d 1`)
- CPU usage during cleanup
- Memory usage over 24-hour period

### Monitoring Commands
```bash
# Monitor SD card writes
iostat -d 1 | grep mmcblk

# Monitor memory usage
watch -n 1 'free -m'

# Check motionEye memory
ps aux | grep motioneye
```

---

## Notes

- All changes maintain backward compatibility with existing configurations
- No breaking changes to REST API or UI
- Security posture maintained (path validation, auth unchanged)
- Focus on Pi 5 single-camera use case per original analysis requirements
- Original `cleanup_media()` function preserved for backward compatibility
