# Copyright (c) 2013 Calin Crisan
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
RPi Camera RTSP Bridge using MediaMTX native rpiCamera source.

MediaMTX has built-in support for Raspberry Pi cameras via libcamera,
eliminating the need for external rpicam-vid processes or complex piping.
"""

import logging
import os
import platform
import subprocess
import tarfile
import tempfile
import time
import urllib.request

from motioneye import settings
from motioneye.controls import rpicamctl


_mediamtx_process = None
_active_cameras = {}  # {camera_id: config}
_bridge_enabled = None


def _detect_architecture():
    """
    Detect system architecture for mediamtx download.

    Note: On Raspberry Pi, the kernel may be 64-bit (aarch64) but userspace
    can be 32-bit (armhf). We need to detect the userspace architecture
    since mediamtx's rpiCamera source links against system libraries.
    """
    import struct

    # Check Python's pointer size to detect userspace bitness
    # This is more reliable than platform.machine() on mixed systems
    bits = struct.calcsize('P') * 8

    machine = platform.machine().lower()

    # Handle 32-bit userspace on 64-bit kernel (common on RPi)
    if machine in ('aarch64', 'arm64'):
        if bits == 32:
            logging.info('detected 32-bit userspace on 64-bit kernel, using armv7')
            return 'armv7'
        return 'arm64v8'
    elif machine.startswith('armv7'):
        return 'armv7'
    elif machine.startswith('arm'):
        return 'armv6'
    elif machine in ('x86_64', 'amd64'):
        if bits == 32:
            return '386'
        return 'amd64'
    elif machine in ('i386', 'i686'):
        return '386'

    logging.warning(f'unknown architecture {machine}, defaulting to armv7')
    return 'armv7'


def _ensure_mediamtx():
    """
    Download mediamtx if not present, return path to binary.
    Returns None if download fails.
    """
    bin_dir = os.path.join(settings.MEDIA_PATH, 'bin')
    mediamtx_path = os.path.join(bin_dir, 'mediamtx')

    if os.path.exists(mediamtx_path):
        return mediamtx_path

    logging.info('mediamtx not found, downloading...')

    # Create bin directory if needed
    os.makedirs(bin_dir, exist_ok=True)

    arch = _detect_architecture()
    version = 'v1.9.3'
    url = f'https://github.com/bluenviron/mediamtx/releases/download/{version}/mediamtx_{version}_linux_{arch}.tar.gz'

    try:
        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp_file:
            logging.info(f'downloading mediamtx from {url}')
            urllib.request.urlretrieve(url, tmp_file.name)

            # Extract mediamtx binary
            with tarfile.open(tmp_file.name, 'r:gz') as tar:
                # Find the mediamtx binary in the archive
                member = tar.getmember('mediamtx')
                member.name = os.path.basename(member.name)
                tar.extract(member, bin_dir)

            os.unlink(tmp_file.name)

        # Make executable
        os.chmod(mediamtx_path, 0o755)
        logging.info(f'mediamtx downloaded successfully to {mediamtx_path}')
        return mediamtx_path

    except Exception as e:
        logging.error(f'failed to download mediamtx: {e}')
        return None


def _create_mediamtx_config():
    """
    Create mediamtx configuration file using native rpiCamera source.

    MediaMTX natively supports Raspberry Pi cameras through libcamera,
    so we don't need to run external rpicam-vid processes.
    """
    config_dir = os.path.join(settings.MEDIA_PATH, 'bin')
    config_path = os.path.join(config_dir, 'mediamtx.yml')

    port = getattr(settings, 'RPICAM_RTSP_PORT', 8554)
    width = getattr(settings, 'RPICAM_DEFAULT_WIDTH', 1920)
    height = getattr(settings, 'RPICAM_DEFAULT_HEIGHT', 1080)
    framerate = getattr(settings, 'RPICAM_DEFAULT_FRAMERATE', 30)

    # Build paths configuration for each active camera
    paths_config = ""
    for camera_id, cam_config in _active_cameras.items():
        cam_index = cam_config.get('index', 0)
        cam_width = cam_config.get('width', width)
        cam_height = cam_config.get('height', height)
        cam_fps = cam_config.get('framerate', framerate)
        stream_path = camera_id.replace('rpicam', 'cam')

        paths_config += f"""
  {stream_path}:
    source: rpiCamera
    rpiCameraCamID: {cam_index}
    rpiCameraWidth: {cam_width}
    rpiCameraHeight: {cam_height}
    rpiCameraFPS: {cam_fps}
    rpiCameraIDRPeriod: {cam_fps}
    rpiCameraBitrate: 4000000
    rpiCameraProfile: main
    rpiCameraLevel: '4.1'
"""

    # If no cameras configured yet, add a default cam0 path
    if not paths_config:
        paths_config = f"""
  cam0:
    source: rpiCamera
    rpiCameraCamID: 0
    rpiCameraWidth: {width}
    rpiCameraHeight: {height}
    rpiCameraFPS: {framerate}
    rpiCameraIDRPeriod: {framerate}
    rpiCameraBitrate: 4000000
    rpiCameraProfile: main
    rpiCameraLevel: '4.1'
"""

    config_content = f"""# MediaMTX configuration for RPi Camera RTSP bridge
# Uses native rpiCamera source (libcamera integration)

logLevel: info
logDestinations: [stdout]

# RTSP server settings
protocols: [tcp]
rtspAddress: :{port}

# Camera paths - each uses native libcamera integration
paths:{paths_config}
"""

    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        logging.debug(f'mediamtx config written to {config_path}')
        return config_path
    except Exception as e:
        logging.error(f'failed to create mediamtx config: {e}')
        return None


def _start_mediamtx():
    """Start mediamtx RTSP server with native rpiCamera support"""
    global _mediamtx_process

    if _mediamtx_process and _mediamtx_process.poll() is None:
        logging.debug('mediamtx already running')
        return True

    mediamtx_path = _ensure_mediamtx()
    if not mediamtx_path:
        logging.error('cannot start mediamtx: binary not available')
        return False

    config_path = _create_mediamtx_config()
    if not config_path:
        logging.error('cannot start mediamtx: config creation failed')
        return False

    port = getattr(settings, 'RPICAM_RTSP_PORT', 8554)

    try:
        logging.info(f'starting mediamtx on port {port} with native rpiCamera source')

        # Ensure ldconfig and other system binaries are in PATH for rpiCamera source
        env = os.environ.copy()
        env['PATH'] = '/usr/sbin:/sbin:' + env.get('PATH', '')

        # Start mediamtx with config file
        _mediamtx_process = subprocess.Popen(
            [mediamtx_path, config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.path.dirname(config_path),
            env=env,
        )

        # Wait for startup and check for errors
        time.sleep(3)

        if _mediamtx_process.poll() is not None:
            # Process exited, read output for error
            output = _mediamtx_process.stdout.read().decode('utf-8', errors='ignore')
            logging.error(f'mediamtx failed to start: {output}')
            return False

        logging.info('mediamtx started successfully with native rpiCamera')
        return True

    except Exception as e:
        logging.error(f'failed to start mediamtx: {e}')
        return False


def _stop_mediamtx():
    """Stop mediamtx RTSP server"""
    global _mediamtx_process

    if not _mediamtx_process or _mediamtx_process.poll() is not None:
        _mediamtx_process = None
        return

    logging.info('stopping mediamtx')

    try:
        _mediamtx_process.terminate()
        _mediamtx_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logging.warning('mediamtx did not stop gracefully, killing')
        _mediamtx_process.kill()
        _mediamtx_process.wait()

    _mediamtx_process = None
    logging.info('mediamtx stopped')


def _restart_mediamtx():
    """Restart mediamtx to apply new camera configuration"""
    _stop_mediamtx()
    time.sleep(1)
    return _start_mediamtx()


def add_stream(camera_id, camera_index=0, width=None, height=None, framerate=None):
    """
    Add a camera stream configuration and restart mediamtx.
    Returns RTSP URL on success, None on failure.
    """
    global _active_cameras

    # Use defaults from settings if not specified
    width = width or getattr(settings, 'RPICAM_DEFAULT_WIDTH', 1920)
    height = height or getattr(settings, 'RPICAM_DEFAULT_HEIGHT', 1080)
    framerate = framerate or getattr(settings, 'RPICAM_DEFAULT_FRAMERATE', 30)

    # Store camera configuration
    _active_cameras[camera_id] = {
        'index': camera_index,
        'width': width,
        'height': height,
        'framerate': framerate,
    }

    logging.info(f'adding rpicam stream: {camera_id} (camera {camera_index}, {width}x{height}@{framerate}fps)')

    # Start or restart mediamtx with new config
    if _mediamtx_process and _mediamtx_process.poll() is None:
        if not _restart_mediamtx():
            del _active_cameras[camera_id]
            return None
    else:
        if not _start_mediamtx():
            del _active_cameras[camera_id]
            return None

    url = get_stream_url(camera_id)
    logging.info(f'rpicam stream available at: {url}')
    return url


def remove_stream(camera_id):
    """Remove a camera stream and update mediamtx"""
    global _active_cameras

    if camera_id not in _active_cameras:
        return

    logging.info(f'removing rpicam stream: {camera_id}')
    del _active_cameras[camera_id]

    if not _active_cameras:
        # No more cameras, stop mediamtx
        _stop_mediamtx()
    else:
        # Restart with updated config
        _restart_mediamtx()


def get_stream_url(camera_id):
    """Get RTSP URL for a camera stream"""
    port = getattr(settings, 'RPICAM_RTSP_PORT', 8554)
    stream_path = camera_id.replace('rpicam', 'cam')
    return f'rtsp://127.0.0.1:{port}/{stream_path}'


def start():
    """Initialize RTSP bridge (called at server startup)"""
    global _bridge_enabled

    if _bridge_enabled is None:
        _bridge_enabled = getattr(settings, 'RPICAM_RTSP_ENABLED', None)
        if _bridge_enabled is None:
            # Auto-detect based on rpicam tool availability
            _bridge_enabled = rpicamctl.is_rpicam_available()

    if not _bridge_enabled:
        logging.info('rpicam RTSP bridge disabled (tools not available)')
        return

    logging.info('rpicam RTSP bridge enabled (using mediamtx native rpiCamera)')


def stop():
    """Shutdown RTSP bridge (called at server shutdown)"""
    global _active_cameras

    logging.info('stopping rpicam RTSP bridge')

    # Clear active cameras
    _active_cameras = {}

    # Stop mediamtx
    _stop_mediamtx()

    logging.info('rpicam RTSP bridge stopped')


def is_running():
    """Check if mediamtx is running"""
    return _mediamtx_process and _mediamtx_process.poll() is None


def should_start():
    """Check if RTSP bridge should be started"""
    return _bridge_enabled
