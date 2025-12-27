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
RPi Camera detection and control via rpicam-apps (libcamera).

Named rpicamctl.py to match the official Raspberry Pi naming (rpicam-apps).
Used on Pi 5 and systems with libcamera support.

This module:
- Enumerates cameras using rpicam-hello (or libcamera-hello for legacy)
- Provides device information for configuration generation
- Handles both new (rpicam-*) and old (libcamera-*) command names

Tool Detection Priority:
1. rpicam-vid / rpicam-hello (Bookworm/Trixie, preferred)
2. libcamera-vid / libcamera-hello (older Bookworm, legacy fallback)
"""

import logging
import re
from subprocess import CalledProcessError

from motioneye import utils

# Raspberry Pi OS Bookworm uses 'rpicam-*', older versions use 'libcamera-*'
_RPICAM_HELLO_COMMANDS = ['rpicam-hello', 'libcamera-hello']
_RPICAM_VID_COMMANDS = ['rpicam-vid', 'libcamera-vid']

# Cached command detection - detected once at startup/first use
# None = not yet detected, '' = no command available, 'cmd' = the command to use
_rpicam_hello_cache: str | None = None
_rpicam_vid_cache: str | None = None

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

# Sensor variants that lack AWB calibration (NoIR = No InfraRed filter)
# These cameras see infrared light which makes AWB calibration impossible
# ColourTemperature and AwbLocked controls will not work on these sensors
_NOIR_SUFFIXES = ('_noir', '_wide_noir')


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


def _find_rpicam_tool(tool_type: str) -> str | None:
    """
    Find the available rpicam tool (rpicam-* or libcamera-* fallback).

    Uses cached result after first detection to avoid repeated subprocess calls.

    Args:
        tool_type: Either 'hello' or 'vid'

    Returns:
        Command name if found, None otherwise
    """
    global _rpicam_hello_cache, _rpicam_vid_cache

    if tool_type == 'hello':
        cache = _rpicam_hello_cache
        commands = _RPICAM_HELLO_COMMANDS
    elif tool_type == 'vid':
        cache = _rpicam_vid_cache
        commands = _RPICAM_VID_COMMANDS
    else:
        raise ValueError(f"Unknown tool type: {tool_type}")

    # Return cached result if already detected
    if cache is not None:
        return cache if cache else None

    # Detect command on first call
    for cmd in commands:
        try:
            utils.call_subprocess(['which', cmd])
            if tool_type == 'hello':
                _rpicam_hello_cache = cmd
            else:
                _rpicam_vid_cache = cmd
            logging.info(f'rpicam-{tool_type} command detected: {cmd}')
            return cmd
        except CalledProcessError:
            continue

    # No command found - cache empty string to indicate "checked but not found"
    if tool_type == 'hello':
        _rpicam_hello_cache = ''
    else:
        _rpicam_vid_cache = ''
    logging.debug(f'No rpicam-{tool_type} command available (checked: {", ".join(commands)})')
    return None


def find_rpicam_tools() -> dict:
    """
    Locate rpicam-vid/rpicam-hello (preferred) or
    libcamera-vid/libcamera-hello (legacy fallback).

    Returns:
        Dict with paths: {'vid': path_or_none, 'hello': path_or_none}
    """
    return {
        'vid': _find_rpicam_tool('vid'),
        'hello': _find_rpicam_tool('hello'),
    }


def init_rpicam() -> bool:
    """
    Initialize rpicam detection at startup.

    Call this during application startup to detect the rpicam commands
    early and log the result. This avoids detection delays on first camera
    enumeration.

    Returns:
        True if rpicam-hello (or libcamera-hello) is available, False otherwise
    """
    # Clear cache to ensure fresh detection at startup
    clear_cache()
    cmd = _find_rpicam_tool('hello')
    return cmd is not None


# Backwards compatibility alias
init_libcamera = init_rpicam


def get_rpicam_hello_command() -> str | None:
    """
    Get the detected rpicam-hello command name.

    Returns:
        'rpicam-hello' or 'libcamera-hello' if available, None otherwise
    """
    return _find_rpicam_tool('hello')


# Backwards compatibility alias
get_libcamera_command = get_rpicam_hello_command


def get_rpicam_vid_command() -> str | None:
    """
    Get the detected rpicam-vid command name.

    Returns:
        'rpicam-vid' or 'libcamera-vid' if available, None otherwise
    """
    return _find_rpicam_tool('vid')


def is_rpicam_available() -> bool:
    """
    Check if rpicam tools are available on the system.

    Returns:
        True if rpicam-hello or libcamera-hello binary is found
    """
    return _find_rpicam_tool('hello') is not None


# Backwards compatibility alias
is_libcamera_available = is_rpicam_available


def list_devices() -> list:
    """
    Enumerate cameras using rpicam-hello --list-cameras.

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
    logging.debug('Detecting rpicam/libcamera cameras')

    cmd = _find_rpicam_tool('hello')
    if not cmd:
        logging.warning(
            'No libcamera command found (rpicam-hello or libcamera-hello) - libcamera cameras will not be detected. '
            'On Raspberry Pi OS Bookworm, ensure rpicam-apps is installed: sudo apt install rpicam-apps'
        )
        return []

    try:
        output = utils.call_subprocess(
            [cmd, '--list-cameras', '-t', '1'],
            timeout=10
        )
    except CalledProcessError as e:
        logging.warning(f'{cmd} failed to enumerate cameras: {e}')
        return []
    except Exception as e:
        logging.warning(f'{cmd} error during camera enumeration: {e}')
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
        has_autofocus = base_sensor_lower in _AUTOFOCUS_SENSORS
        is_noir = is_noir_sensor(sensor)

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
            'supports_autofocus': has_autofocus,
            'is_noir': is_noir,
            'index': int(index),
        }

        cameras.append((device_id, display_name, properties))
        logging.debug(f'Found libcamera device: {device_id} - {display_name}')

    if not cameras:
        logging.warning(
            'No libcamera cameras detected. Troubleshooting: '
            '1) Check camera is physically connected, '
            '2) Ensure camera is enabled (run "sudo raspi-config" and enable camera), '
            '3) Verify with "rpicam-hello --list-cameras" or "libcamera-hello --list-cameras"'
        )

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


def is_noir_sensor(sensor: str) -> bool:
    """
    Check if a sensor is a NoIR (No InfraRed filter) variant.

    NoIR cameras lack AWB calibration data because they see infrared light
    which makes color temperature calibration impossible. On these cameras:
    - ColourTemperature control will NOT work
    - AwbLocked control will NOT work
    - ColourGains (manual red/blue) WILL work
    - AwbMode presets WILL work (with limited effect)

    Args:
        sensor: Sensor model like 'imx708' or 'imx708_wide_noir'

    Returns:
        True if sensor is a NoIR variant
    """
    sensor_lower = sensor.lower()
    return any(sensor_lower.endswith(suffix) for suffix in _NOIR_SUFFIXES)


def get_camera_modes(index: int) -> list:
    """
    Get supported resolutions and framerates for a camera.

    Parses the "Modes" section from rpicam-hello --list-cameras output.

    Args:
        index: Camera index (0, 1, etc.)

    Returns:
        List of dicts with 'resolution', 'fps', 'format' keys.
        Example: [{'resolution': '1920x1080', 'fps': 30.0, 'format': 'SRGGB10_CSI2P'}]
    """
    cmd = _find_rpicam_tool('hello')
    if not cmd:
        return []

    try:
        output = utils.call_subprocess(
            [cmd, '--list-cameras', '-t', '1'],
            timeout=10
        )
    except (CalledProcessError, Exception) as e:
        logging.debug(f'Failed to get camera modes: {e}')
        return []

    output = utils.make_str(output)
    modes = []

    # Find the camera section
    camera_section_pattern = re.compile(rf'^{index}\s*:', re.MULTILINE)
    camera_match = camera_section_pattern.search(output)
    if not camera_match:
        return []

    # Find the start of next camera section (or end of output)
    next_camera_pattern = re.compile(rf'^{index + 1}\s*:', re.MULTILINE)
    next_match = next_camera_pattern.search(output, camera_match.end())
    end_pos = next_match.start() if next_match else len(output)

    camera_section = output[camera_match.start():end_pos]

    # Parse mode lines like:
    # 'SRGGB10_CSI2P' : 1536x864 [120.13 fps - (0, 0)/4608x2592 crop]
    mode_pattern = re.compile(
        r"'(\w+)'\s*:\s*(\d+)x(\d+)\s*\[(\d+\.?\d*)\s*fps"
    )

    for match in mode_pattern.finditer(camera_section):
        fmt, width, height, fps = match.groups()
        modes.append({
            'resolution': f'{width}x{height}',
            'fps': float(fps),
            'format': fmt,
        })

    return modes


def clear_cache():
    """
    Clear the cached rpicam command detection.

    Useful for testing or when system state changes.
    """
    global _rpicam_hello_cache, _rpicam_vid_cache
    _rpicam_hello_cache = None
    _rpicam_vid_cache = None
