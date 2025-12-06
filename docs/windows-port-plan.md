# MotionEye Windows Port Plan

## Goal
Create a Windows-compatible version of motionEye with full functionality (motion detection, recording, live streaming) while keeping the Pi5 version lightweight. The Pi5 will serve as a remote camera source.

## Repository Decision: Same Repo (Conditional Code Paths)

**Rationale:** The Windows-specific code will **NOT add CPU overhead to Pi5** because:
1. Platform detection happens once at startup (`if sys.platform == 'win32'`)
2. Windows-only modules (OpenCV backend, wincamctl) are only imported on Windows
3. The backend abstraction uses a factory pattern - Pi5 instantiates `MotionBackend`, Windows instantiates `OpenCVBackend`
4. No runtime penalty - Python's lazy imports mean unused code isn't loaded

**Benefits of same repo:**
- Single codebase to maintain
- Bug fixes in handlers/UI benefit both platforms
- Shared test infrastructure
- Easier to keep feature parity

## Testing Approach
Primary testing will use **Pi5 as remote camera** (no local Windows webcam). This means:
- Priority on `remote.py` integration testing early
- Local Windows camera support can be tested later with virtual cameras or deferred

## Architecture Strategy
**Conditional code paths with backend abstraction**
- Create a clean backend abstraction layer
- Keep Linux `motion` backend for Pi5/Linux
- Add OpenCV backend for Windows
- Platform detection at runtime (zero cost on Pi5)

```
+------------------------------------------+
|        Web UI (unchanged)                |
|   (Tornado handlers, templates, JS)      |
+------------------------------------------+
                    |
+------------------------------------------+
|      Platform Abstraction Layer          |
|   (motioneye/platform.py - NEW)          |
+------------------------------------------+
         /                    \
+----------------+      +------------------+
| Linux Backend  |      | Windows Backend  |
| (motion daemon)|      | (Python/OpenCV)  |
+----------------+      +------------------+
```

---

## Phase 1: Core Infrastructure (Week 1-2)

### 1.1 Platform Detection & Path Abstraction
**Create:** `motioneye/platform.py`
```python
# Platform detection and path utilities
def is_windows() -> bool
def get_conf_path() -> str      # Windows: %APPDATA%\motionEye\config
def get_run_path() -> str       # Windows: %APPDATA%\motionEye\run
def get_media_path() -> str     # Windows: %USERPROFILE%\Videos\motionEye
def get_log_path() -> str
def get_null_device() -> str    # Windows: 'NUL', Linux: '/dev/null'
```

**Modify:** `motioneye/settings.py` (lines 29-50)
- Replace hardcoded Linux paths with calls to `platform.py`
- Current hardcoded values:
  - Line 29: `CONF_PATH = '/etc/motioneye'`
  - Line 32-35: `RUN_PATH` searches `/run`, `/var/run`
  - Line 41-44: `LOG_PATH` searches `/log`, `/var/log`
  - Line 50: `MEDIA_PATH = '/var/lib/motioneye'`
  - Line 99: `SMB_MOUNT_ROOT = '/media'`

### 1.2 Process Management Abstraction
**Modify:** `motioneye/server.py`
- Replace `Daemon` class (lines 51-160) with cross-platform version
- Critical Linux-only code:
  - Line 59, 72: `os.fork()` - doesn't exist on Windows
  - Line 67: `os.setsid()` - POSIX only
  - Lines 82-87: `/dev/null` and `os.dup2()` - Unix only
- **Windows approach:** Use `subprocess.Popen` with `CREATE_NO_WINDOW` flag, or run as foreground process

**Modify:** Signal handling throughout
- `server.py` lines 110, 132, 139, 243: `os.kill()`, `signal.SIGTERM`
- `motionctl.py` lines 164-178: `os.kill()`, `os.waitpid()`
- `cleanup.py` line 53: `signal.SIGKILL`
- **Windows approach:** Use `psutil` library or `process.terminate()`

### 1.3 File Locking Abstraction
**Create:** `motioneye/utils/filelock.py`
- Replace `fcntl` (Unix-only) used in:
  - `motioneye/controls/v4l2ctl.py` line 17
  - `motioneye/mediafiles.py` line 18
- **Windows approach:** Use `msvcrt.locking()` or `portalocker` package

---

## Phase 2: Video Backend (Week 2-4)

### 2.1 Backend Abstraction Layer
**Create:** `motioneye/backends/`
```
backends/
  __init__.py
  base.py              # Abstract interface
  opencv_backend.py    # Windows implementation
  motion_backend.py    # Linux wrapper (existing behavior)
```

**Backend Interface (`base.py`):**
```python
class VideoBackend(ABC):
    def start_camera(self, camera_config) -> int
    def stop_camera(self, camera_id)
    def get_current_frame(self, camera_id) -> bytes  # JPEG
    def is_motion_detected(self, camera_id) -> bool
    def enable_motion_detection(self, camera_id, enabled: bool)
    def take_snapshot(self, camera_id) -> str
    def start_recording(self, camera_id)
    def stop_recording(self, camera_id)
```

### 2.2 OpenCV Backend Implementation
**Create:** `motioneye/backends/opencv_backend.py`
- Camera capture using `cv2.VideoCapture()`
- Motion detection using `cv2.createBackgroundSubtractorMOG2()`
- JPEG encoding with `cv2.imencode('.jpg', frame)`
- Video recording with `cv2.VideoWriter()` or FFmpeg pipe

### 2.3 MJPEG Streaming Server
**Create:** `motioneye/backends/mjpeg_server.py`
- Replaces motion daemon's streaming (port 8081+)
- Async Tornado handler serving multipart/x-mixed-replace
- Integrates with `mjpgclient.py`

### 2.4 Modify motionctl.py
**File:** `motioneye/motionctl.py`
- Add backend factory: `get_backend() -> VideoBackend`
- Route all calls through backend abstraction
- Keep same public interface for handlers

---

## Phase 3: Control Module Replacements (Week 4-5)

### 3.1 Camera Enumeration
**Create:** `motioneye/controls/wincamctl.py`
- Replace `v4l2ctl.py` functionality on Windows
- Enumerate cameras via OpenCV index probing
- Get resolutions via DirectShow (optional: `pygrabber`)

**Modify:** `motioneye/controls/v4l2ctl.py`
- Add platform check, delegate to `wincamctl.py` on Windows

### 3.2 Disk Management
**Modify:** `motioneye/controls/diskctl.py`
- Replace `/proc/mounts` parsing (line 70 in `smbctl.py`)
- Use `psutil.disk_partitions()` cross-platform
- Use `shutil.disk_usage()` for space calculations

### 3.3 Shell Command Replacements
Various files use Linux commands via subprocess:
- `which` command → `shutil.which()` (Python 3.3+)
- `find`, `grep`, `xargs` → Python `pathlib`/`glob`
- `poweroff`, `systemctl` → Windows `shutdown.exe` or disable feature

---

## Phase 4: Recording & Media (Week 5-6)

### 4.1 Video Recording
**In:** `motioneye/backends/opencv_backend.py`
- Implement circular buffer for pre-capture
- Use `cv2.VideoWriter` with appropriate codec (MJPEG/H264)
- Match motion's filename patterns: `%Y-%m-%d/%H-%M-%S`

### 4.2 Snapshot & Timelapse
**Modify:** `motioneye/mediafiles.py`
- Replace shell commands with Python equivalents
- Use `pathlib` for cross-platform paths
- Configure FFmpeg path for Windows

---

## Phase 5: Integration (Week 6-7)

### 5.1 Configuration
**Modify:** `motioneye/config.py`
- Handle Windows camera identifiers (index vs `/dev/video*`)
- Create config directory on first run
- Use forward slashes in config files (Python handles both)

### 5.2 Startup Scripts
**Create:**
- `scripts/motioneye-windows.bat` - Simple startup
- `scripts/install-windows-service.py` - Optional Windows service (using `pywin32`)

### 5.3 Handler Verification
**Test all handlers in:** `motioneye/handlers/`
- Verify picture/movie streaming works
- Test remote camera from Pi5
- Validate action handlers (snapshot, record)

---

## Critical Files Summary

| File | Changes |
|------|---------|
| `motioneye/settings.py` | Platform-aware paths (lines 29-50, 99) |
| `motioneye/server.py` | Replace Daemon class (lines 51-160), signal handling |
| `motioneye/motionctl.py` | Backend abstraction, remove Linux process calls |
| `motioneye/mjpgclient.py` | Connect to new streaming server on Windows |
| `motioneye/mediafiles.py` | Remove fcntl, shell commands |
| `motioneye/controls/v4l2ctl.py` | Platform delegation |
| `motioneye/controls/diskctl.py` | Cross-platform disk detection |

## New Files to Create

| File | Purpose |
|------|---------|
| `motioneye/platform.py` | Platform detection, path utilities |
| `motioneye/backends/__init__.py` | Backend package |
| `motioneye/backends/base.py` | Abstract backend interface |
| `motioneye/backends/opencv_backend.py` | OpenCV camera/motion implementation |
| `motioneye/backends/motion_backend.py` | Wrapper for Linux motion daemon |
| `motioneye/backends/mjpeg_server.py` | MJPEG streaming server |
| `motioneye/controls/wincamctl.py` | Windows camera enumeration |
| `motioneye/utils/filelock.py` | Cross-platform file locking |

---

## Dependencies

### New Python Packages
```
opencv-python>=4.5.0    # Video capture and motion detection
numpy                   # Required by OpenCV
psutil                  # Cross-platform process/disk management
portalocker             # Cross-platform file locking
pywin32                 # Windows service support (optional)
```

### External Tools
- **FFmpeg for Windows** - Required for timelapse/video conversion
  - Download from ffmpeg.org, add to PATH

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Motion detection quality | High | Tune MOG2/KNN params; expose in config |
| USB camera latency | Medium | Threaded capture; DirectShow fallback |
| pycurl Windows build | Medium | Use pre-built wheels from Gohlke |
| MJPEG streaming perf | Medium | Async IO; optimize JPEG encoding |

---

## Development Priority Order

Since testing uses **Pi5 as remote camera**, we prioritize getting the server running first:

1. **Phase 1.1** - Platform paths (get server starting on Windows)
2. **Phase 1.2** - Process management (run without daemon mode)
3. **Remote cameras first** - Verify Pi5 connection works (uses existing `remote.py`, should work with minimal changes)
4. **Phase 2.1-2.3** - Basic local camera capture + streaming (lower priority)
5. **Phase 2.2** - Motion detection for local cameras
6. **Phase 4** - Recording for local cameras
7. **Remaining** - Polish and edge cases

**Milestone 1 (usable system):** Server starts on Windows + Pi5 remote camera works
**Milestone 2 (full local support):** Local Windows camera capture + motion detection + recording
