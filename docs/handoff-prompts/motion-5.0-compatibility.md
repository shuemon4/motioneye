# MotionEye Motion 5.0 Compatibility Implementation - Handoff Prompt

## Context

You are continuing work on the MotionEye project to add full Motion 5.0 compatibility. The Motion daemon fork (at `/Users/tshuey/Documents/GitHub/motion`) has already been updated with Pi 5/Camera v3 libcamera support. Now MotionEye (at `/Users/tshuey/Documents/GitHub/motioneye`) needs updates to work correctly with Motion 5.0's breaking changes.

## Environment

- **Development machine**: macOS (Darwin 25.1.0)
- **Testing target**: Raspberry Pi 5 with Camera Module v3
- **MotionEye path**: `/Users/tshuey/Documents/GitHub/motioneye`
- **Motion fork path**: `/Users/tshuey/Documents/GitHub/motion`
- **Branch**: `update/motion`

## Problem Statement

Motion 5.0 introduced breaking changes that MotionEye doesn't currently handle:

1. **`stream_port` removed** - Streams now served via webcontrol interface
2. **`webcontrol_interface`** - Changed from integer (0,1,2) to string ("off","default","user","simple")
3. **Stream URLs changed** - From `http://host:stream_port/` to `http://host:webcontrol_port/{cam_id}/stream`
4. **Parameter renames** - `camera_name`→`device_name`, `movie_codec`→`movie_container`
5. **Parameters removed** - `stream_localhost`, `stream_auth_method`, `stream_authentication`, `auto_brightness`, `setup_mode`

MotionEye's `mjpgclient.py:334` currently reads `stream_port` which doesn't exist in Motion 5.0 configs.

## Implementation Tasks

### Task 1: Add Motion 5.0 Version Detection

**File**: `motioneye/motionctl.py`

Add a new function after `is_motion_post43()` (around line 373):

```python
def is_motion_50():
    """Check if Motion version is 5.0 or later."""
    binary, version = find_motion()
    if not binary:
        return False
    return update.compare_versions(version, '5.0') >= 0
```

### Task 2: Add Motion 4.4→5.0 Configuration Adaptation

**File**: `motioneye/config/adaptation.py`

Add new mapping after `_MOTION_44_TO_43_OPTIONS_MAPPING`:

```python
def webcontrol_interface_to_50(v, data):
    """Convert integer webcontrol_interface to Motion 5.0 string."""
    mapping = {0: 'off', 1: 'default', 2: 'user'}
    return {'webcontrol_interface': mapping.get(int(v), 'default')}

def camera_name_to_device_name(v, data):
    """Rename camera_name to device_name for Motion 5.0."""
    return {'device_name': v}

def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0."""
    return {'movie_container': v}

# Motion 4.4 to 5.0 option mappings
_MOTION_44_TO_50_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_to_50,
    'camera_name': camera_name_to_device_name,
    'movie_codec': movie_codec_to_container,
    'stream_port': None,  # Removed in 5.0
    'stream_localhost': None,
    'stream_auth_method': None,
    'stream_authentication': None,
    'auto_brightness': None,
    'setup_mode': None,
}

# Reverse mapping for reading Motion 5.0 configs
def webcontrol_interface_from_50(v, data):
    """Convert Motion 5.0 string webcontrol_interface to integer."""
    mapping = {'off': 0, 'default': 1, 'user': 2, 'simple': 1}
    if isinstance(v, int):
        return {'webcontrol_interface': v}
    return {'webcontrol_interface': mapping.get(str(v).lower(), 1)}

def device_name_to_camera_name(v, data):
    """Rename device_name to camera_name for internal use."""
    return {'camera_name': v}

def movie_container_to_codec(v, data):
    """Rename movie_container to movie_codec for internal use."""
    return {'movie_codec': v}

_MOTION_50_TO_44_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_from_50,
    'device_name': device_name_to_camera_name,
    'movie_container': movie_container_to_codec,
}
```

### Task 3: Update Default Configuration Generation

**File**: `motioneye/config/defaults.py`

Modify `_set_main_defaults()` and `_set_camera_defaults()` to conditionally set values based on Motion version:

```python
# Add import at top
from motioneye import motionctl

# In _set_main_defaults() around line 49:
def _set_main_defaults(data):
    # ... existing code ...
    if motionctl.is_motion_50():
        data.setdefault('webcontrol_interface', 'default')
    else:
        data.setdefault('webcontrol_interface', 1)
    # ... rest of function ...

# In camera defaults around line 118:
def _set_camera_stream_defaults(data, camera_id):
    if not motionctl.is_motion_50():
        # Motion 4.x: Separate stream ports per camera
        data.setdefault('stream_port', 9080 + camera_id)
    # Motion 5.0: No stream_port, streams via webcontrol
```

### Task 4: Refactor MJPG Client for Motion 5.0 Stream URLs

**File**: `motioneye/mjpgclient.py`

This is the most critical change. The client must connect to different URLs based on Motion version.

```python
# Add import at top
from motioneye import motionctl

# Modify get_jpg() function starting around line 318:
def get_jpg(camera_id):
    if camera_id not in MjpgClient.clients:
        logging.debug(f'creating mjpg client for camera {camera_id}')

        camera_config = config.get_camera(camera_id)
        if not camera_config['@enabled'] or not utils.is_local_motion_camera(camera_config):
            logging.error(f'could not start mjpg client for camera id {camera_id}: not enabled or not local')
            return None

        username, password = None, None
        auth_mode = None

        if motionctl.is_motion_50():
            # Motion 5.0: Streams via webcontrol interface
            from motioneye import config as config_module
            main_config = config_module.get_main()
            port = main_config.get('webcontrol_port', 8080)
            motion_camera_id = motionctl.camera_id_to_motion_camera_id(camera_id)
            stream_path = f'/{motion_camera_id}/stream'

            # Auth is via webcontrol settings in Motion 5.0
            if main_config.get('webcontrol_auth_method'):
                auth_str = main_config.get('webcontrol_authentication', ':')
                if ':' in auth_str:
                    username, password = auth_str.split(':', 1)
                auth_mode = 'digest' if main_config.get('webcontrol_auth_method') == 'digest' else 'basic'
        else:
            # Motion 4.x: Separate stream ports
            port = camera_config['stream_port']
            stream_path = '/'
            if camera_config.get('stream_auth_method', 0) > 0:
                username, password = camera_config.get('stream_authentication', ':').split(':')
                auth_mode = 'digest' if camera_config.get('stream_auth_method') > 1 else 'basic'

        client = MjpgClient(camera_id, port, username, password, auth_mode, stream_path)
        client.do_connect()

        MjpgClient.clients[camera_id] = client

    client = MjpgClient.clients[camera_id]
    return client.get_last_jpg()
```

**Also modify the MjpgClient class**:

```python
class MjpgClient(IOStream):
    # ... existing code ...

    def __init__(self, camera_id, port, username, password, auth_mode, stream_path='/'):
        self._camera_id = camera_id
        self._port = port
        self._username = username or ''
        self._password = password or ''
        self._auth_mode = auth_mode
        self._auth_digest_state = {}
        self._stream_path = stream_path  # NEW: configurable stream path

        # ... rest of init ...

    def _on_connect(self, future: Future) -> None:
        result, _ = self._get_future_result(future)
        if not result:
            return

        logging.debug(f'mjpg client for camera {self._camera_id} connected on port {self._port}')

        if self._auth_mode == 'basic':
            logging.debug('mjpg client using basic authentication')
            auth_header = utils.build_basic_header(self._username, self._password)
            self.write(
                f'GET {self._stream_path} HTTP/1.0\r\nAuthorization: {auth_header}\r\nConnection: close\r\n\r\n'.encode()
            )
        elif self._auth_mode == 'digest':
            logging.debug('digest authentication _on_connect')
            self.write(f'GET {self._stream_path} HTTP/1.0\r\n\r\n'.encode())
        else:
            logging.debug('no authentication _on_connect')
            self.write(f'GET {self._stream_path} HTTP/1.0\r\nConnection: close\r\n\r\n'.encode())

        self._seek_http()
```

### Task 5: Update Config Serialization

**File**: `motioneye/config/serialization.py` (or `motioneye/config/storage.py`)

Ensure configs are adapted before writing to disk for Motion 5.0. Find where motion.conf is written and add:

```python
from motioneye.config.adaptation import adapt_config_directives, _MOTION_44_TO_50_OPTIONS_MAPPING

def write_motion_config(data):
    if motionctl.is_motion_50():
        # Create a copy to avoid modifying the original
        data = dict(data)
        adapt_config_directives(data, _MOTION_44_TO_50_OPTIONS_MAPPING)
    # ... existing write logic ...
```

### Task 6: Update Camera Constants

**File**: `motioneye/config/camera/constants.py`

Add Motion 5.0 specific parameters and mark deprecated ones:

```python
# Add new Motion 5.0 parameters
MOTION_50_PARAMS = [
    'device_name',
    'movie_container',
]

# Mark parameters removed in Motion 5.0
MOTION_50_REMOVED_PARAMS = [
    'stream_port',
    'stream_localhost',
    'stream_auth_method',
    'stream_authentication',
    'auto_brightness',
    'setup_mode',
]
```

## Testing Procedure

### Local Testing (Mac)

1. Run MotionEye unit tests:
   ```bash
   cd /Users/tshuey/Documents/GitHub/motioneye
   python -m pytest tests/
   ```

2. Test version detection mock:
   ```python
   # Create test in tests/test_motionctl.py
   def test_is_motion_50():
       with patch('motioneye.motionctl.find_motion') as mock:
           mock.return_value = ('/usr/bin/motion', '5.0.0')
           assert motionctl.is_motion_50() == True

           mock.return_value = ('/usr/bin/motion', '4.7.1')
           assert motionctl.is_motion_50() == False
   ```

### Pi 5 Testing

1. **Transfer updated MotionEye to Pi 5**:
   ```bash
   rsync -avz --exclude='.git' /Users/tshuey/Documents/GitHub/motioneye/ admin@pi5-motioneye:~/motioneye/
   ```

2. **Install/update on Pi 5**:
   ```bash
   ssh admin@pi5-motioneye "cd ~/motioneye && pip install -e ."
   ```

3. **Verify Motion version**:
   ```bash
   ssh admin@pi5-motioneye "motion -h | head -5"
   # Should show: Motion version 5.0.0-gitUNKNOWN
   ```

4. **Test camera detection**:
   ```bash
   ssh admin@pi5-motioneye "rpicam-hello --list-cameras"
   ```

5. **Start MotionEye and check logs**:
   ```bash
   ssh admin@pi5-motioneye "sudo python3 -m motioneye.meyectl startserver -c /etc/motioneye/motioneye.conf"
   # In another terminal:
   ssh admin@pi5-motioneye "tail -f /var/log/motioneye/motion.log"
   ```

6. **Verification checklist**:
   - [ ] MotionEye web UI loads at `http://pi5-motioneye:8765`
   - [ ] Camera is detected and listed
   - [ ] Live stream displays in web UI
   - [ ] No "Unknown config option" errors in motion.log
   - [ ] Snapshot button works
   - [ ] Motion detection toggle works
   - [ ] Recording creates valid video files

## Files Summary

| File | Changes |
|------|---------|
| `motioneye/motionctl.py` | Add `is_motion_50()` function |
| `motioneye/config/adaptation.py` | Add `_MOTION_44_TO_50_OPTIONS_MAPPING` and reverse |
| `motioneye/config/defaults.py` | Conditional defaults for Motion 5.0 |
| `motioneye/mjpgclient.py` | Refactor for webcontrol stream URLs |
| `motioneye/config/serialization.py` | Apply adaptation before config write |
| `motioneye/config/camera/constants.py` | Add Motion 5.0 parameter lists |

## Reference Documents

- Design doc: `/Users/tshuey/Documents/GitHub/motion/doc/plans/Pi5-CamV3-Implementation-Design.md`
- Breaking changes: `/Users/tshuey/Documents/GitHub/motioneye/docs/Update-Motion-MotionEye.md`
- Integration guide: `/Users/tshuey/Documents/GitHub/motioneye/docs/MotionEye-Integration-Guide.md`

## Success Criteria

1. MotionEye generates valid Motion 5.0 configuration files
2. No deprecated parameter warnings in Motion logs (optional - can accept warnings)
3. Live video streaming works through MotionEye web interface
4. Motion detection and recording function correctly
5. Backward compatibility with Motion 4.x maintained (gated by version check)

## Implementation Priority Order

1. **Task 1** (Version Detection) - Foundation for all other changes
2. **Task 2** (Adaptation Mapping) - Config translation layer
3. **Task 3** (Default Config) - webcontrol_interface fix
4. **Task 4** (MJPG Client) - Critical for live view
5. **Task 5** (Config Serialization) - Clean config output
6. **Task 6** (Constants) - Documentation/organization

## Notes

- All changes should be gated by `is_motion_50()` to maintain backward compatibility
- The Motion fork already has all libcamera changes implemented - no changes needed there
- Focus on MotionEye Python code changes only
- Test thoroughly on Pi 5 before considering complete
