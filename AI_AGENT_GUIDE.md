# motionEye AI Agent Development Guide

## Purpose

This document provides comprehensive guidance for AI agents to efficiently develop, update, add, or delete components within the motionEye project. It covers architecture, patterns, conventions, and modification procedures.

---

## Quick Reference

### Project Identity
- **Name**: motionEye
- **Type**: Video surveillance web interface for motion daemon
- **License**: GPL-3.0-or-later
- **Python**: 3.7+
- **Web Framework**: Tornado 6.5+ (async)
- **Default Port**: 8765

### Entry Points
| Script | Module | Purpose |
|--------|--------|---------|
| `meyectl` | `motioneye.meyectl:main` | CLI control utility |
| `motioneye_init` | `motioneye.motioneye_init:main` | System initialization |

### Critical Files (Read Before Modifying)
- `motioneye/server.py` - Application server and route definitions
- `motioneye/config.py` - Configuration management (~80KB, complex)
- `motioneye/settings.py` - Global settings and constants
- `motioneye/handlers/base.py` - Base request handler with auth

---

## Architecture Overview

### Directory Structure
```
motioneye/
├── motioneye/              # Main Python package
│   ├── handlers/           # HTTP request handlers (Tornado)
│   ├── controls/           # System control modules
│   ├── utils/              # Utility modules for streaming
│   ├── static/             # Frontend assets (CSS, JS)
│   ├── templates/          # Jinja2 HTML templates
│   ├── scripts/            # Shell scripts for events
│   ├── extra/              # System integration files
│   └── locale/             # Translations (PO/MO/JSON)
├── tests/                  # Unit tests
├── docker/                 # Docker configuration
├── docs/                   # Documentation
└── l10n/                   # Localization tools
```

### Core Module Responsibilities

| Module | Lines | Purpose | Key Functions |
|--------|-------|---------|---------------|
| `config.py` | ~2500 | Configuration management | `get_main()`, `get_camera()`, `set_camera()` |
| `server.py` | ~520 | HTTP server setup | `run()`, `make_app()`, `handler_mapping` |
| `settings.py` | ~170 | Global constants | All `UPPERCASE_SETTINGS` |
| `mediafiles.py` | ~1200 | Media file handling | `list_pictures()`, `list_movies()` |
| `motionctl.py` | ~500 | Motion daemon control | `start()`, `stop()`, `running()` |
| `tasks.py` | ~200 | Background task queue | `add()`, `start()`, `stop()` |

### Handler Architecture

All handlers inherit from `BaseHandler` (Tornado's `RequestHandler`):

```python
# Location: motioneye/handlers/base.py

class BaseHandler(RequestHandler):
    def get_all_arguments(self) -> dict    # Parse query + JSON body
    def get_json(self)                      # Parse JSON body
    def finish_json(self, data=None)        # JSON response
    def render(self, template, **context)   # Jinja2 template
    def get_current_user(self)              # Auth check

    @staticmethod
    def auth(admin=False, prompt=True)      # Auth decorator
```

### Route Definition Pattern

Routes are defined in `server.py:handler_mapping`:

```python
handler_mapping = [
    (r'^/$', MainHandler),
    (r'^/config/main/(?P<op>set|get)/?$', ConfigHandler),
    (r'^/config/(?P<camera_id>\d+)/(?P<op>get|set|rem|test|authorize)/?$', ConfigHandler),
    (r'^/picture/(?P<camera_id>\d+)/(?P<op>current|list|frame)/?$', PictureHandler),
    # ... more routes
]
```

---

## Handler Reference

### Available Handlers

| Handler | File | Routes | Purpose |
|---------|------|--------|---------|
| `MainHandler` | `handlers/main.py` | `/` | Main HTML UI |
| `ConfigHandler` | `handlers/config.py` | `/config/*` | Camera/main configuration |
| `PictureHandler` | `handlers/picture.py` | `/picture/*` | Picture operations |
| `MovieHandler` | `handlers/movie.py` | `/movie/*` | Video file operations |
| `ActionHandler` | `handlers/action.py` | `/action/*` | Camera controls (PTZ) |
| `LoginHandler` | `handlers/login.py` | `/login` | Authentication |
| `PrefsHandler` | `handlers/prefs.py` | `/prefs/*` | User preferences |
| `PowerHandler` | `handlers/power.py` | `/power/*` | Shutdown/reboot |
| `VersionHandler` | `handlers/version.py` | `/version` | Version info |
| `LogHandler` | `handlers/log.py` | `/log/*` | Log file access |
| `UpdateHandler` | `handlers/update.py` | `/update` | Version updates |

### Handler Implementation Pattern

```python
# New handler template
from tornado.web import HTTPError
from motioneye.handlers.base import BaseHandler

class MyHandler(BaseHandler):
    @BaseHandler.auth(admin=True)  # Requires admin auth
    async def get(self, camera_id=None, op=None):
        if op == 'my_operation':
            result = await self._my_operation(camera_id)
            return self.finish_json(result)
        raise HTTPError(400, 'unknown operation')

    @BaseHandler.auth(admin=True)
    async def post(self, camera_id=None, op=None):
        data = self.get_all_arguments()
        # Process data...
        return self.finish_json({'ok': True})
```

---

## API Endpoint Reference

### Configuration Endpoints

```
GET  /config/main/get          → Main config (requires admin)
POST /config/main/set          → Update main config (requires admin)
GET  /config/{id}/get          → Camera config (requires admin)
POST /config/{id}/set          → Update camera config (requires admin)
POST /config/{id}/rem          → Remove camera (requires admin)
POST /config/add               → Add camera (requires admin)
GET  /config/list              → List cameras (requires auth)
GET  /config/backup            → Download config backup
POST /config/restore           → Restore config from backup
```

### Media Endpoints

```
GET  /picture/{id}/current     → Current camera frame
GET  /picture/{id}/list        → List pictures
POST /picture/{id}/download/{filename}  → Download picture
POST /picture/{id}/zipped/{group}       → Download as ZIP
GET  /movie/{id}/list          → List movies
POST /movie/{id}/download/{filename}    → Download movie
GET  /movie/{id}/playback/{filename}    → Stream movie
```

### Action Endpoints

```
POST /action/{id}/{action}     → Execute camera action
     Actions: lock, unlock, light_on, light_off,
              alarm_on, alarm_off, up, right, down, left,
              zoom_in, zoom_out, preset1-9
```

### System Endpoints

```
POST /login                    → Authenticate
GET  /version                  → Version info
POST /power/shutdown           → System shutdown
POST /power/reboot             → System reboot
GET  /log/{name}               → View log file
```

---

## Configuration System

### Config File Locations

```
/etc/motioneye/           → Main config directory (CONF_PATH)
├── motion.conf           → Main configuration
├── camera-{id}.conf      → Per-camera configuration
└── tasks.pickle          → Background task state
```

### Configuration Functions

```python
# motioneye/config.py

# Main config
config.get_main()                    → dict
config.set_main(main_config)         → None

# Camera config
config.get_camera_ids()              → list[int]
config.get_camera(camera_id)         → dict
config.set_camera(camera_id, config) → None
config.add_camera(device_details)    → dict
config.rem_camera(camera_id)         → None

# UI conversion (important!)
config.motion_camera_dict_to_ui(data)     → dict  # Config → UI
config.motion_camera_ui_to_dict(ui, prev) → dict  # UI → Config

# Cache invalidation
config.invalidate()                  → None
```

### Config Key Conventions

- `@key` - motionEye-specific setting (not passed to motion daemon)
- `key` - Motion daemon setting
- `@enabled` - Camera enable state
- `@proto` - Protocol type (motioneye, mjpeg, etc.)

### Camera Types

```python
from motioneye import utils

utils.is_local_motion_camera(config)  # Has videodevice/netcam_url
utils.is_remote_camera(config)        # @proto == 'motioneye'
utils.is_v4l2_camera(config)          # Has videodevice
utils.is_mmal_camera(config)          # Has mmalcam_name
utils.is_net_camera(config)           # Has netcam_url
utils.is_simple_mjpeg_camera(config)  # @proto == 'mjpeg'
```

---

## Coding Patterns & Conventions

### Async Pattern

All handlers are async and use Tornado's IOLoop:

```python
from tornado.ioloop import IOLoop
import datetime

# Schedule callback
io_loop = IOLoop.current()
io_loop.add_timeout(
    datetime.timedelta(seconds=10),
    callback_function
)

# Async handler method
async def get(self, camera_id):
    result = await some_async_operation()
    self.finish_json(result)
```

### Background Tasks

```python
from motioneye import tasks

# Add task to run in 60 seconds
tasks.add(
    when=60,  # seconds from now
    func=my_function,
    tag='my_task_name',
    callback=on_complete,  # Optional
    **params
)

# Or with datetime
tasks.add(
    when=datetime.datetime.now() + datetime.timedelta(hours=1),
    func=my_function,
    tag='scheduled_task'
)
```

### Logging Pattern

```python
import logging

logging.debug('detailed info')
logging.info('general info')
logging.warning('warning message')
logging.error('error message')
logging.error('error with trace', exc_info=True)
```

### Error Handling Pattern

```python
from tornado.web import HTTPError

# Raise HTTP error
raise HTTPError(404, 'not found')
raise HTTPError(400, 'invalid parameter')
raise HTTPError(403, 'unauthorized')

# JSON error response
self.finish_json({'error': 'description'})
```

### Authentication Decorator

```python
class MyHandler(BaseHandler):
    @BaseHandler.auth()           # Any authenticated user
    async def get(self): ...

    @BaseHandler.auth(admin=True) # Admin only
    async def post(self): ...

    @BaseHandler.auth(prompt=False)  # No login prompt on failure
    async def delete(self): ...
```

---

## Modification Guidelines

### Adding a New Handler

1. **Create handler file** in `motioneye/handlers/`:

```python
# motioneye/handlers/myfeature.py
from tornado.web import HTTPError
from motioneye.handlers.base import BaseHandler

__all__ = ('MyFeatureHandler',)

class MyFeatureHandler(BaseHandler):
    @BaseHandler.auth(admin=True)
    async def get(self, camera_id=None, op=None):
        if op == 'status':
            return self.finish_json({'status': 'ok'})
        raise HTTPError(400, 'unknown operation')
```

2. **Register route** in `motioneye/server.py`:

```python
from motioneye.handlers.myfeature import MyFeatureHandler

handler_mapping = [
    # ... existing routes ...
    (r'^/myfeature/(?P<camera_id>\d+)/(?P<op>\w+)/?$', MyFeatureHandler),
    (r'^.*$', NotFoundHandler),  # Keep this last!
]
```

3. **Add tests** in `tests/test_handlers/`:

```python
# tests/test_handlers/test_myfeature.py
from tests import WebTestCase

class TestMyFeatureHandler(WebTestCase):
    def test_get_status(self):
        response = self.fetch('/myfeature/1/status')
        self.assertEqual(response.code, 200)
```

### Adding a New Setting

1. **Add to `settings.py`**:

```python
# motioneye/settings.py

# Description of new setting
MY_NEW_SETTING = 'default_value'
```

2. **Use in code**:

```python
from motioneye import settings

if settings.MY_NEW_SETTING:
    # Do something
```

### Adding a Control Module

1. **Create in `motioneye/controls/`**:

```python
# motioneye/controls/myctl.py
import logging

def my_operation():
    logging.debug('performing operation...')
    # Implementation
    return result
```

2. **Import and use**:

```python
from motioneye.controls import myctl
result = myctl.my_operation()
```

### Adding a Utility Module

1. **Create in `motioneye/utils/`**:

```python
# motioneye/utils/myutil.py
def my_utility_function(param):
    return processed_result
```

2. **Export in `__init__.py`** (optional):

```python
# motioneye/utils/__init__.py
from motioneye.utils.myutil import my_utility_function
```

### Modifying Configuration Options

1. **Add motion option** to `_USED_MOTION_OPTIONS` in `config.py`:

```python
_USED_MOTION_OPTIONS = {
    # ... existing options ...
    'my_new_option',
}
```

2. **Add UI conversion** in `motion_camera_ui_to_dict()` and `motion_camera_dict_to_ui()`:

```python
def motion_camera_ui_to_dict(ui, prev_config=None):
    # ... existing code ...
    data['my_new_option'] = ui.get('myNewOption', 'default')

def motion_camera_dict_to_ui(data):
    # ... existing code ...
    ui['myNewOption'] = data.get('my_new_option', 'default')
```

---

## Testing

### Test Structure

```
tests/
├── __init__.py          # WebTestCase base class
├── test_handlers/
│   ├── test_base.py
│   └── test_login.py
└── test_utils/
    ├── test_http.py
    ├── test_mjpeg.py
    └── test_rtmp.py
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_handlers/test_base.py

# Run with coverage
python -m pytest tests/ --cov=motioneye
```

### Test Utilities

```python
# tests/__init__.py provides:
from tests import WebTestCase, AsyncMock

class MyTest(WebTestCase):
    def test_something(self):
        response = self.fetch('/endpoint')
        self.assertEqual(response.code, 200)
```

---

## Dependencies

### Runtime Dependencies

```toml
# From pyproject.toml
tornado>=6.5.0    # Async web framework
jinja2            # HTML templating
pillow            # Image processing
pycurl            # HTTP client
babel             # Internationalization
boto3             # AWS S3 uploads
```

### External Dependencies

- **motion** - Core motion detection daemon (separate install)
- **ffmpeg** - Video codec support
- **v4l-utils** - Video4Linux camera support
- **cifs-utils** - SMB share support (optional)

### Check Dependency Availability

```python
from motioneye import motionctl, mediafiles
from motioneye.controls import v4l2ctl

has_motion = motionctl.find_motion()[0] is not None
has_ffmpeg = mediafiles.find_ffmpeg() is not None
has_v4l = v4l2ctl.find_v4l2_ctl() is not None
```

---

## Performance Optimizations (Pi 5)

### Recent Optimizations

The codebase includes Pi 5 optimizations in `settings.py`:

```python
# Task save debouncing
TASK_SAVE_INTERVAL = 30              # Seconds between disk writes
TASK_SAVE_ON_SHUTDOWN_ONLY = False   # Only save on shutdown

# Prepared files cache limits
PREPARED_FILES_TIMEOUT = 1800        # 30 minutes
PREPARED_FILES_MAX_SIZE_MB = 500     # Maximum cache size
PREPARED_FILES_MAX_ENTRIES = 10      # Maximum cached items

# Media listing cache
MEDIA_LISTING_CACHE_TTL = 10         # Seconds to cache listings
MEDIA_LISTING_MAX_FILES = 1000       # Max files per listing

# Timeouts
MOTION_CHECK_INTERVAL = 30           # Was 10
MJPG_CLIENT_TIMEOUT = 20             # Was 10
MJPG_CLIENT_IDLE_TIMEOUT = 60        # Was 10
```

### ThreadPoolExecutor Usage

`mediafiles.py` uses ThreadPoolExecutor for background operations:

```python
from concurrent.futures import ThreadPoolExecutor

_listing_executor = ThreadPoolExecutor(max_workers=2)

def start():
    global _listing_executor
    _listing_executor = ThreadPoolExecutor(max_workers=2)

def stop():
    if _listing_executor:
        _listing_executor.shutdown(wait=True)
```

---

## Localization

### Translation Files

```
motioneye/locale/{lang}/LC_MESSAGES/
├── motioneye.po    # Source strings
└── motioneye.mo    # Compiled binary
```

### Adding Translations

```python
# Mark string for translation
from motioneye import settings

message = _('string to translate')

# Access current language
current_lang = settings.lingvo
```

### Build Translations

```bash
# Compile PO to MO files
make -C l10n compile

# Extract strings from Python
pybabel extract -F babel.cfg -o l10n/motioneye.pot motioneye/
```

---

## Docker Support

### Dockerfile Location

`docker/Dockerfile` - Debian trixie-slim based

### Build & Run

```bash
# Build
docker build -t motioneye -f docker/Dockerfile .

# Run
docker run -d -p 8765:8765 \
    -v /etc/motioneye:/etc/motioneye \
    -v /var/lib/motioneye:/var/lib/motioneye \
    motioneye
```

### Docker Compose

```bash
cd docker
docker-compose up -d
```

---

## Common Modification Scenarios

### Scenario: Add New Camera Type

1. Add detection in `motioneye/utils/__init__.py`:
```python
def is_my_camera_type(config):
    return config.get('@proto') == 'my_type'
```

2. Add listing support in `handlers/config.py`:
```python
elif proto == 'my_type':
    cameras = my_camera_listing()
    return self.finish_json({'cameras': cameras})
```

3. Add config conversion in `config.py`:
```python
def my_camera_ui_to_dict(ui, prev_config=None): ...
def my_camera_dict_to_ui(data): ...
```

### Scenario: Add New Upload Service

1. Add class in `motioneye/uploadservices.py`:
```python
class MyService(UploadService):
    NAME = 'my_service'

    def upload(self, ...): ...
    def test_access(self, ...): ...
```

2. Register in `_services` dict

### Scenario: Add New Notification Method

1. Create module `motioneye/send_myservice.py`:
```python
def send_message(api_key, recipient, message, files):
    # Implementation
    pass
```

2. Add test endpoint in `handlers/config.py`:
```python
elif what == 'my_service':
    from motioneye import send_myservice
    # Test implementation
```

---

## Security Considerations

### Authentication

- Signature-based auth (primary)
- HTTP Basic Auth (optional, via `HTTP_BASIC_AUTH` setting)
- Admin/Normal user separation
- Password hashing with SHA1

### Sensitive Settings

- `@admin_password` - Admin credentials
- `@normal_password` - Viewer credentials
- `PASSWORD_HOOK` - External password handler

### Never Commit

- Actual passwords or API keys
- Certificate files
- User-specific configurations

---

## Version & Release

### Version Location

```python
# motioneye/__init__.py
VERSION = 'x.x.x'
```

### Changelog

`https://github.com/motioneye-project/motioneye/releases`

---

## Troubleshooting

### Common Issues

| Issue | Check | Solution |
|-------|-------|----------|
| Motion not starting | `motionctl.find_motion()` | Install motion daemon |
| Config not saving | `settings.CONF_PATH` permissions | `chmod 755 /etc/motioneye` |
| Stream not working | `MJPG_CLIENT_TIMEOUT` | Increase timeout |
| High CPU | Camera resolution | Lower resolution/framerate |

### Debug Mode

```python
# In settings.py or command line
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Locations

- Default: `/var/log/motioneye.log`
- Fallback: `/tmp/motioneye.log`
- Motion logs: Via LogHandler at `/log/motion`

---

## File Change Checklist

Before committing changes:

- [ ] Run tests: `python -m pytest tests/`
- [ ] Check imports: No circular dependencies
- [ ] Update `__all__` if adding public functions
- [ ] Add handler to `handler_mapping` if new route
- [ ] Document new settings in this guide
- [ ] Check async/await consistency
- [ ] Verify authentication decorators
- [ ] Test on Python 3.7+ (minimum version)
