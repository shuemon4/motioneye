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
libcamera camera detection and control.
Used on Pi 5 and systems with libcamera support.

This module enumerates cameras using libcamera-hello and provides
device information for configuration generation.
"""

import logging
import re
from subprocess import CalledProcessError

from motioneye import utils

# Raspberry Pi OS Bookworm uses 'rpicam-hello', older versions use 'libcamera-hello'
_LIBCAMERA_COMMANDS = ['rpicam-hello', 'libcamera-hello']

# Cached libcamera command - detected once at startup/first use
# None = not yet detected, '' = no command available, 'cmd' = the command to use
_libcamera_command_cache: str | None = None

# Known sensor models and their display names
# Note: Sensor names may have suffixes like _wide, _noir, _wide_noir
_SENSOR_NAMES = {
    'imx708': 'Camera Module 3',
    'imx219': 'Camera Module 2',
    'ov5647': 'Camera Module 1',
    'imx477': 'HQ Camera',
    'imx296': 'GS Camera',
    'imx500': 'AI Camera',
}

# Sensors that support autofocus (base name matching)
_AUTOFOCUS_SENSORS = {'imx708'}


def _get_base_sensor_name(sensor: str) -> str:
    """
    Extract base sensor name from variants like imx708_wide_noir.

    Args:
        sensor: Full sensor name like 'imx708_wide_noir'

    Returns:
        Base sensor name like 'imx708'
    """
    # Common suffixes for sensor variants
    for suffix in ['_wide_noir', '_wide', '_noir']:
        if sensor.lower().endswith(suffix):
            return sensor[:len(sensor) - len(suffix)]
    return sensor


def _find_libcamera_command() -> str | None:
    """
    Find the available libcamera command (rpicam-hello or libcamera-hello).

    Uses cached result after first detection to avoid repeated subprocess calls.

    Returns:
        Command name if found, None otherwise
    """
    global _libcamera_command_cache

    # Return cached result if already detected
    if _libcamera_command_cache is not None:
        return _libcamera_command_cache if _libcamera_command_cache else None

    # Detect command on first call
    for cmd in _LIBCAMERA_COMMANDS:
        try:
            utils.call_subprocess(['which', cmd])
            _libcamera_command_cache = cmd
            logging.info(f'libcamera command detected: {cmd}')
            return cmd
        except CalledProcessError:
            continue

    # No command found - cache empty string to indicate "checked but not found"
    _libcamera_command_cache = ''
    logging.debug('No libcamera command available (checked: rpicam-hello, libcamera-hello)')
    return None


def init_libcamera() -> bool:
    """
    Initialize libcamera detection at startup.

    Call this during application startup to detect the libcamera command
    early and log the result. This avoids detection delays on first camera
    enumeration.

    Returns:
        True if libcamera command is available, False otherwise
    """
    cmd = _find_libcamera_command()
    return cmd is not None


def get_libcamera_command() -> str | None:
    """
    Get the detected libcamera command name.

    Returns:
        'rpicam-hello' or 'libcamera-hello' if available, None otherwise
    """
    return _find_libcamera_command()


def is_libcamera_available() -> bool:
    """
    Check if a libcamera command is available on the system.

    Returns:
        True if rpicam-hello or libcamera-hello binary is found
    """
    return _find_libcamera_command() is not None


def list_devices() -> list:
    """
    Enumerate cameras using libcamera-hello --list-cameras.

    Returns:
        List of (device_id, display_name, properties) tuples.

        device_id: String like 'camera0', 'camera1' for use with libcam_device
        display_name: Human-readable name like 'Camera Module 3 (imx708)'
        properties: Dict with sensor, max_resolution, path, supports_autofocus, index

    Example:
        [
            ('camera0', 'Camera Module 3 (imx708)', {
                'sensor': 'imx708',
                'max_resolution': '4608x2592',
                'path': '/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a',
                'supports_autofocus': True,
                'index': 0
            }),
        ]
    """
    logging.debug('Detecting libcamera cameras')

    cmd = _find_libcamera_command()
    if not cmd:
        logging.debug('No libcamera command found (rpicam-hello or libcamera-hello)')
        return []

    try:
        output = utils.call_subprocess(
            [cmd, '--list-cameras', '-t', '1'],
            timeout=10
        )
    except CalledProcessError as e:
        logging.debug(f'{cmd} failed: {e}')
        return []
    except Exception as e:
        logging.debug(f'{cmd} error: {e}')
        return []

    cameras = []
    output = utils.make_str(output)

    # Parse output like:
    # Available cameras
    # -----------------
    # 0 : imx708 [4608x2592 10-bit RGGB] (/base/axi/pcie@120000/rp1/i2c@88000/imx708@1a)
    #     Modes: 'SRGGB10_CSI2P' : 1536x864 [120.13 fps - (0, 0)/4608x2592 crop]
    #                             2304x1296 [56.03 fps - (0, 0)/4608x2592 crop]
    #                             4608x2592 [14.35 fps - (0, 0)/4608x2592 crop]

    # Pattern matches: "0 : imx708 [4608x2592" or "0 : imx708 [4608x2592 10-bit RGGB]"
    camera_pattern = re.compile(
        r'^(\d+)\s*:\s*(\w+)\s*\[(\d+x\d+)',
        re.MULTILINE
    )

    # Pattern for device path in parentheses
    path_pattern = re.compile(r'\(([^)]+)\)')

    for line in output.split('\n'):
        match = camera_pattern.match(line.strip())
        if not match:
            continue

        index, sensor, max_res = match.groups()
        device_id = f'camera{index}'

        # Extract device path from the same line
        path_match = path_pattern.search(line)
        path = path_match.group(1) if path_match else ''

        # Determine sensor properties using base name (handles imx708_wide_noir etc.)
        base_sensor = _get_base_sensor_name(sensor)
        base_sensor_lower = base_sensor.lower()
        supports_autofocus = base_sensor_lower in _AUTOFOCUS_SENSORS

        # Create display name using base sensor for lookup
        friendly_name = _SENSOR_NAMES.get(base_sensor_lower, sensor.upper())
        # Include variant info if present
        if base_sensor.lower() != sensor.lower():
            variant = sensor[len(base_sensor):].replace('_', ' ').strip()
            display_name = f'{friendly_name} {variant} ({sensor})'
        else:
            display_name = f'{friendly_name} ({sensor})'

        properties = {
            'sensor': sensor,
            'max_resolution': max_res,
            'path': path,
            'supports_autofocus': supports_autofocus,
            'index': int(index),
        }

        cameras.append((device_id, display_name, properties))
        logging.debug(f'Found libcamera device: {device_id} - {display_name}')

    if not cameras:
        logging.debug('No libcamera cameras detected')

    return cameras


def get_camera_properties(device_id: str) -> dict | None:
    """
    Get detailed properties for a specific camera.

    Args:
        device_id: Camera device ID like 'camera0'

    Returns:
        Dict with sensor, max_resolution, path, supports_autofocus, index
        None if camera not found
    """
    devices = list_devices()
    for dev_id, name, props in devices:
        if dev_id == device_id:
            return props
    return None


def get_sensor_display_name(sensor: str) -> str:
    """
    Get the friendly display name for a sensor model.

    Args:
        sensor: Sensor model like 'imx708' or 'imx708_wide_noir'

    Returns:
        Friendly name like 'Camera Module 3'
    """
    base_sensor = _get_base_sensor_name(sensor)
    return _SENSOR_NAMES.get(base_sensor.lower(), sensor.upper())


def supports_autofocus(sensor: str) -> bool:
    """
    Check if a sensor model supports autofocus.

    Args:
        sensor: Sensor model like 'imx708' or 'imx708_wide_noir'

    Returns:
        True if sensor has autofocus capability
    """
    base_sensor = _get_base_sensor_name(sensor)
    return base_sensor.lower() in _AUTOFOCUS_SENSORS
