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
Raspberry Pi platform detection utilities.
Detects Pi model and available camera interfaces.

Camera Interface Priority:
1. libcamera - if rpicam-hello/libcamera-hello is available (Bookworm, Pi 5)
2. mmal - if legacy camera stack available (Bullseye, Pi 4 and earlier)
3. v4l2 - generic fallback for USB cameras

This allows Pi 4 on Bookworm to use libcamera instead of the deprecated MMAL.
"""

import logging
import re

_pi_info_cache = None
_camera_interface_cache = None


def get_pi_model() -> dict | None:
    """
    Detect Raspberry Pi model from /proc/cpuinfo and device tree.

    Returns:
        dict with 'model', 'revision', 'is_pi5', 'camera_interface'
        None if not running on a Raspberry Pi

    Example return:
        {
            'model': 'Raspberry Pi 5 Model B Rev 1.0',
            'revision': 'd04170',
            'is_pi5': True,
            'camera_interface': 'libcamera'
        }
    """
    global _pi_info_cache
    if _pi_info_cache is not None:
        return _pi_info_cache if _pi_info_cache else None

    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
    except (OSError, IOError):
        logging.debug('Could not read /proc/cpuinfo - not running on Linux')
        _pi_info_cache = {}
        return None

    # Extract model info from cpuinfo (present on all Pi models)
    model_match = re.search(r'Model\s*:\s*(.+)', cpuinfo)
    revision_match = re.search(r'Revision\s*:\s*(\w+)', cpuinfo)

    model_str = model_match.group(1).strip() if model_match else ''

    # Check if this is a Raspberry Pi by model string
    # Pi 5 doesn't have BCM chip in cpuinfo but has "Raspberry Pi 5" in Model
    is_pi = 'Raspberry Pi' in model_str

    # Fallback: Check for BCM chips (older Pi models have this in cpuinfo)
    if not is_pi:
        is_pi = any(
            chip in cpuinfo
            for chip in ['BCM2835', 'BCM2836', 'BCM2837', 'BCM2711', 'BCM2712']
        )

    if not is_pi:
        logging.debug('Not running on a Raspberry Pi')
        _pi_info_cache = {}
        return None

    # Check for Pi 5 by model string or BCM2712 chip
    is_pi5 = 'Raspberry Pi 5' in model_str or 'BCM2712' in cpuinfo

    _pi_info_cache = {
        'model': model_str if model_str else 'Unknown Raspberry Pi',
        'revision': revision_match.group(1) if revision_match else 'unknown',
        'is_pi5': is_pi5,
        'camera_interface': 'libcamera' if is_pi5 else 'mmal',
    }

    logging.info(f'Detected Pi model: {_pi_info_cache["model"]}, is_pi5={is_pi5}')
    return _pi_info_cache


def is_pi5() -> bool:
    """
    Returns True if running on Raspberry Pi 5 (BCM2712).

    Pi 5 uses libcamera instead of MMAL for camera access,
    and has no hardware H.264 encoding.
    """
    pi_info = get_pi_model()
    return pi_info.get('is_pi5', False) if pi_info else False


def is_raspberry_pi() -> bool:
    """Returns True if running on any Raspberry Pi model."""
    return get_pi_model() is not None


def get_camera_interface() -> str:
    """
    Returns the camera interface to use for CSI cameras.

    Priority order:
    1. libcamera - if available (Bookworm on any Pi, or Pi 5)
    2. mmal - if on Raspberry Pi with legacy camera stack (Bullseye)
    3. v4l2 - generic fallback

    This allows Pi 4 on Bookworm to use libcamera instead of deprecated MMAL.

    Returns:
        'libcamera' - libcamera stack available (Bookworm, Pi 5)
        'mmal' - Pi 4 and earlier with legacy camera stack (Bullseye)
        'v4l2' - Generic V4L2 (non-Pi or USB cameras)
    """
    global _camera_interface_cache

    if _camera_interface_cache is not None:
        return _camera_interface_cache

    # Import here to avoid circular imports
    from motioneye.controls import rpicamctl

    # First, check if libcamera is available (works on any Pi with Bookworm)
    if rpicamctl.is_rpicam_available():
        _camera_interface_cache = 'libcamera'
        logging.info('Camera interface: libcamera (rpicam tools available)')
        return 'libcamera'

    # Fall back to MMAL on Raspberry Pi with legacy camera stack
    pi_info = get_pi_model()
    if pi_info:
        _camera_interface_cache = 'mmal'
        logging.info('Camera interface: mmal (legacy camera stack)')
        return 'mmal'

    # Not a Pi or no camera interface available
    _camera_interface_cache = 'v4l2'
    logging.info('Camera interface: v4l2 (generic)')
    return 'v4l2'


def uses_libcamera() -> bool:
    """
    Check if the system should use libcamera for CSI cameras.

    This is the preferred check for camera operations - it returns True
    for any system with libcamera available (Pi 4/5 on Bookworm, or Pi 5
    on any OS).

    Returns:
        True if libcamera should be used for CSI cameras
    """
    return get_camera_interface() == 'libcamera'


def clear_cache():
    """Clear the cached Pi info and camera interface. Useful for testing."""
    global _pi_info_cache, _camera_interface_cache
    _pi_info_cache = None
    _camera_interface_cache = None
