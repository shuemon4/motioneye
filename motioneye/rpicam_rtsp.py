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
RPi Camera RTSP Bridge Manager.

Manages rpicam-vid processes and mediamtx RTSP server to provide
camera streams that Motion can consume as netcam sources.

Architecture:
    rpicam-vid → mediamtx (RTSP server) → motion daemon (netcam)

This module handles:
- Auto-downloading mediamtx if not present
- Starting/stopping mediamtx RTSP server
- Managing rpicam-vid processes for each camera
- Stream URL generation for Motion configuration
"""

import logging
import os
import platform
import signal
import struct
import subprocess
import tarfile
import time
import urllib.request
from typing import Optional

from motioneye import settings
from motioneye.controls import rpicamctl

# mediamtx version and download URL template
_MEDIAMTX_VERSION = '1.9.3'
_MEDIAMTX_URL_TEMPLATE = (
    'https://github.com/bluenviron/mediamtx/releases/download/'
    f'v{_MEDIAMTX_VERSION}/mediamtx_v{_MEDIAMTX_VERSION}_linux_{{arch}}.tar.gz'
)

# Process management
_mediamtx_process: Optional[subprocess.Popen] = None
_rpicam_processes: dict[str, subprocess.Popen] = {}  # camera_id -> process

# Stream restart tracking
_stream_restart_counts: dict[str, int] = {}
_MAX_RESTART_ATTEMPTS = 3


def _detect_architecture() -> str:
    """
    Detect system architecture for mediamtx binary download.

    Supports 64-bit ARM (Pi 4/5) and x86_64 only.

    Returns:
        Architecture string: 'arm64v8', 'amd64'

    Raises:
        RuntimeError: If architecture is not supported
    """
    machine = platform.machine().lower()

    if machine in ('aarch64', 'arm64'):
        return 'arm64v8'
    elif machine in ('x86_64', 'amd64'):
        return 'amd64'
    else:
        raise RuntimeError(
            f"Unsupported architecture: {machine}. "
            "This version requires 64-bit ARM (Pi 4/5) or x86_64."
        )


def _get_mediamtx_path() -> str:
    """Get the path where mediamtx binary should be stored."""
    bin_dir = os.path.join(settings.CONF_PATH, 'bin')
    return os.path.join(bin_dir, 'mediamtx')


def _ensure_mediamtx() -> Optional[str]:
    """
    Download mediamtx if not present, return path to binary.

    Returns:
        Path to mediamtx binary, or None if download failed.
    """
    mediamtx_path = _get_mediamtx_path()

    if os.path.exists(mediamtx_path) and os.access(mediamtx_path, os.X_OK):
        logging.debug(f'mediamtx already present at {mediamtx_path}')
        return mediamtx_path

    # Create bin directory if needed
    bin_dir = os.path.dirname(mediamtx_path)
    if not os.path.exists(bin_dir):
        try:
            os.makedirs(bin_dir)
            logging.info(f'Created bin directory: {bin_dir}')
        except OSError as e:
            logging.error(f'Failed to create bin directory {bin_dir}: {e}')
            return None

    # Detect architecture and build download URL
    arch = _detect_architecture()
    url = _MEDIAMTX_URL_TEMPLATE.format(arch=arch)

    logging.info(f'Downloading mediamtx v{_MEDIAMTX_VERSION} for {arch}...')
    logging.debug(f'Download URL: {url}')

    try:
        # Download to temp file
        tar_path = mediamtx_path + '.tar.gz'
        urllib.request.urlretrieve(url, tar_path)

        # Extract mediamtx binary from tarball
        with tarfile.open(tar_path, 'r:gz') as tar:
            # Find mediamtx in archive
            for member in tar.getmembers():
                if member.name == 'mediamtx' or member.name.endswith('/mediamtx'):
                    member.name = 'mediamtx'  # Rename to just 'mediamtx'
                    tar.extract(member, bin_dir)
                    break
            else:
                logging.error('mediamtx binary not found in archive')
                return None

        # Make executable
        os.chmod(mediamtx_path, 0o755)

        # Clean up tarball
        os.remove(tar_path)

        logging.info(f'mediamtx installed successfully at {mediamtx_path}')
        return mediamtx_path

    except Exception as e:
        logging.error(f'Failed to download/install mediamtx: {e}')
        # Clean up partial downloads
        for path in [tar_path, mediamtx_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        return None


def _get_rtsp_port() -> int:
    """Get the configured RTSP port."""
    return getattr(settings, 'RPICAM_RTSP_PORT', 8554)


def _start_mediamtx() -> bool:
    """
    Start the mediamtx RTSP server.

    Returns:
        True if started successfully, False otherwise.
    """
    global _mediamtx_process

    if _mediamtx_process is not None and _mediamtx_process.poll() is None:
        logging.debug('mediamtx already running')
        return True

    mediamtx_path = _ensure_mediamtx()
    if not mediamtx_path:
        return False

    rtsp_port = _get_rtsp_port()

    # mediamtx configuration via environment variables
    env = os.environ.copy()
    env['MTX_PROTOCOLS'] = 'tcp'  # TCP only for local use
    env['MTX_RTSPADDRESS'] = f':{rtsp_port}'
    env['MTX_LOGLEVEL'] = 'warn'

    try:
        logging.info(f'Starting mediamtx RTSP server on port {rtsp_port}')
        _mediamtx_process = subprocess.Popen(
            [mediamtx_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Brief wait to check if it started successfully
        time.sleep(0.5)
        if _mediamtx_process.poll() is not None:
            stderr = _mediamtx_process.stderr.read().decode('utf-8', errors='replace')
            logging.error(f'mediamtx failed to start: {stderr}')
            _mediamtx_process = None
            return False

        logging.info('mediamtx RTSP server started')
        return True

    except Exception as e:
        logging.error(f'Failed to start mediamtx: {e}')
        _mediamtx_process = None
        return False


def _stop_mediamtx():
    """Stop the mediamtx RTSP server gracefully."""
    global _mediamtx_process

    if _mediamtx_process is None:
        return

    logging.info('Stopping mediamtx RTSP server...')

    try:
        # Try graceful shutdown first
        _mediamtx_process.send_signal(signal.SIGTERM)

        # Wait up to 5 seconds for graceful shutdown
        try:
            _mediamtx_process.wait(timeout=5)
            logging.info('mediamtx stopped gracefully')
        except subprocess.TimeoutExpired:
            # Force kill if needed
            logging.warning('mediamtx did not stop gracefully, forcing...')
            _mediamtx_process.send_signal(signal.SIGKILL)
            _mediamtx_process.wait(timeout=2)
            logging.info('mediamtx killed')

    except Exception as e:
        logging.error(f'Error stopping mediamtx: {e}')

    _mediamtx_process = None


def _start_rpicam_stream(camera_id: str, camera_index: int,
                          width: int = 1920, height: int = 1080,
                          framerate: int = 30) -> bool:
    """
    Start rpicam-vid stream for a camera.

    Args:
        camera_id: Unique camera identifier (e.g., 'cam1')
        camera_index: Camera hardware index (0, 1, etc.)
        width: Stream width
        height: Stream height
        framerate: Stream framerate

    Returns:
        True if stream started successfully, False otherwise.
    """
    global _rpicam_processes

    if camera_id in _rpicam_processes:
        proc = _rpicam_processes[camera_id]
        if proc.poll() is None:
            logging.debug(f'rpicam stream {camera_id} already running')
            return True

    rpicam_vid = rpicamctl.get_rpicam_vid_command()
    if not rpicam_vid:
        logging.error('rpicam-vid command not available')
        return False

    rtsp_port = _get_rtsp_port()
    stream_name = f'cam{camera_id}'
    rtsp_url = f'rtsp://localhost:{rtsp_port}/{stream_name}'

    # Build rpicam-vid command
    # Outputs H.264 to RTSP via UDP
    cmd = [
        rpicam_vid,
        '--camera', str(camera_index),
        '--width', str(width),
        '--height', str(height),
        '--framerate', str(framerate),
        '--codec', 'h264',
        '--inline',  # Include SPS/PPS with every IDR frame
        '--listen',  # Wait for RTSP server connection
        '-t', '0',   # Run indefinitely
        '-o', f'udp://localhost:{rtsp_port}/{stream_name}',
    ]

    try:
        logging.info(f'Starting rpicam stream {camera_id}: {width}x{height}@{framerate}fps')
        logging.debug(f'Command: {" ".join(cmd)}')

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        # Brief wait to check if it started
        time.sleep(0.5)
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode('utf-8', errors='replace')
            logging.error(f'rpicam-vid {camera_id} failed to start: {stderr}')
            return False

        _rpicam_processes[camera_id] = proc
        _stream_restart_counts[camera_id] = 0
        logging.info(f'rpicam stream {camera_id} started, RTSP URL: {rtsp_url}')
        return True

    except Exception as e:
        logging.error(f'Failed to start rpicam stream {camera_id}: {e}')
        return False


def _stop_rpicam_stream(camera_id: str):
    """Stop a specific rpicam-vid stream."""
    global _rpicam_processes

    if camera_id not in _rpicam_processes:
        return

    proc = _rpicam_processes[camera_id]
    logging.info(f'Stopping rpicam stream {camera_id}...')

    try:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
            logging.info(f'rpicam stream {camera_id} stopped')
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=2)
            logging.info(f'rpicam stream {camera_id} killed')

    except Exception as e:
        logging.error(f'Error stopping rpicam stream {camera_id}: {e}')

    del _rpicam_processes[camera_id]
    _stream_restart_counts.pop(camera_id, None)


def _stop_all_rpicam_streams():
    """Stop all rpicam-vid streams."""
    for camera_id in list(_rpicam_processes.keys()):
        _stop_rpicam_stream(camera_id)


# === Public API ===

def should_start() -> bool:
    """
    Check if RTSP bridge should be started.

    Returns True if:
    - Running on a Raspberry Pi
    - rpicam-vid is available
    - RTSP bridge is enabled in settings

    Returns:
        True if RTSP bridge should start, False otherwise.
    """
    # Check if explicitly disabled
    enabled = getattr(settings, 'RPICAM_RTSP_ENABLED', None)
    if enabled is False:
        return False

    # Check for rpicam-vid
    if not rpicamctl.get_rpicam_vid_command():
        logging.debug('RTSP bridge: rpicam-vid not available')
        return False

    # Check for cameras
    cameras = rpicamctl.list_devices()
    if not cameras:
        logging.debug('RTSP bridge: no rpicam cameras detected')
        return False

    return True


def is_running() -> bool:
    """Check if the RTSP bridge (mediamtx) is running."""
    return _mediamtx_process is not None and _mediamtx_process.poll() is None


def start() -> bool:
    """
    Start the RTSP bridge (mediamtx server).

    Note: Individual camera streams are started via add_stream().

    Returns:
        True if mediamtx started successfully, False otherwise.
    """
    if not should_start():
        logging.info('RTSP bridge: conditions not met, not starting')
        return False

    return _start_mediamtx()


def stop():
    """
    Stop the RTSP bridge and all camera streams.

    Performs graceful shutdown:
    1. Stop all rpicam-vid processes
    2. Stop mediamtx server
    """
    logging.info('Stopping RTSP bridge...')
    _stop_all_rpicam_streams()
    _stop_mediamtx()
    logging.info('RTSP bridge stopped')


def add_stream(camera_id: str, camera_index: int,
               width: int = None, height: int = None,
               framerate: int = None) -> Optional[str]:
    """
    Add a camera stream to the RTSP bridge.

    Args:
        camera_id: Unique identifier for this stream
        camera_index: Hardware camera index (0, 1, etc.)
        width: Optional stream width (default from settings)
        height: Optional stream height (default from settings)
        framerate: Optional framerate (default from settings)

    Returns:
        RTSP URL for the stream, or None if failed.
    """
    # Ensure mediamtx is running
    if not is_running():
        if not start():
            return None

    # Use defaults from settings if not specified
    width = width or getattr(settings, 'RPICAM_DEFAULT_WIDTH', 1920)
    height = height or getattr(settings, 'RPICAM_DEFAULT_HEIGHT', 1080)
    framerate = framerate or getattr(settings, 'RPICAM_DEFAULT_FRAMERATE', 30)

    if _start_rpicam_stream(camera_id, camera_index, width, height, framerate):
        return get_rtsp_url(camera_id)
    return None


def remove_stream(camera_id: str):
    """
    Remove a camera stream from the RTSP bridge.

    Args:
        camera_id: The stream identifier to remove.
    """
    _stop_rpicam_stream(camera_id)

    # If no more streams, consider stopping mediamtx
    if not _rpicam_processes:
        logging.info('No active streams, stopping mediamtx')
        _stop_mediamtx()


def get_rtsp_url(camera_id: str) -> str:
    """
    Get the RTSP URL for a camera stream.

    Args:
        camera_id: The stream identifier.

    Returns:
        RTSP URL like 'rtsp://localhost:8554/cam1'
    """
    rtsp_port = _get_rtsp_port()
    return f'rtsp://localhost:{rtsp_port}/cam{camera_id}'


def check_streams():
    """
    Check health of all streams and restart failed ones.

    Call this periodically to ensure streams stay running.
    """
    for camera_id, proc in list(_rpicam_processes.items()):
        if proc.poll() is not None:
            # Stream died
            restart_count = _stream_restart_counts.get(camera_id, 0)
            if restart_count < _MAX_RESTART_ATTEMPTS:
                logging.warning(
                    f'rpicam stream {camera_id} died, attempting restart '
                    f'({restart_count + 1}/{_MAX_RESTART_ATTEMPTS})'
                )
                del _rpicam_processes[camera_id]
                # TODO: Need to store stream params to restart
                # For now, just mark as failed
                _stream_restart_counts[camera_id] = restart_count + 1
            else:
                logging.error(
                    f'rpicam stream {camera_id} failed {_MAX_RESTART_ATTEMPTS} times, '
                    'giving up'
                )
                del _rpicam_processes[camera_id]
