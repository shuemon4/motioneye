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

import re
from logging import debug
from subprocess import CalledProcessError

from motioneye import utils


def find_rpicam_tools():
    """
    Locate rpicam-vid/rpicam-hello (preferred) or
    libcamera-vid/libcamera-hello (legacy fallback).
    Returns dict with paths: {'vid': path, 'hello': path, 'prefix': 'rpicam'|'libcamera'}
    """
    # Try modern rpicam-* tools first (Bookworm+)
    try:
        vid_path = utils.call_subprocess(['which', 'rpicam-vid']).strip()
        hello_path = utils.call_subprocess(['which', 'rpicam-hello']).strip()
        debug('found rpicam-* tools (modern)')
        return {'vid': vid_path, 'hello': hello_path, 'prefix': 'rpicam'}
    except CalledProcessError:
        pass

    # Fall back to libcamera-* tools (Bullseye)
    try:
        vid_path = utils.call_subprocess(['which', 'libcamera-vid']).strip()
        hello_path = utils.call_subprocess(['which', 'libcamera-hello']).strip()
        debug('found libcamera-* tools (legacy)')
        return {'vid': vid_path, 'hello': hello_path, 'prefix': 'libcamera'}
    except CalledProcessError:
        pass

    return None


def list_devices():
    """
    Detect RPi cameras via rpicam-hello --list-cameras.
    Returns list of tuples: [(device_id, device_name), ...]
    """
    debug('detecting RPi cameras via rpicam/libcamera tools')

    tools = find_rpicam_tools()
    if not tools:
        debug('unable to detect RPi camera: rpicam-hello/libcamera-hello not found')
        return []

    try:
        # Run with --list-cameras flag and short timeout to avoid GUI display
        output = utils.call_subprocess(
            [tools['hello'], '--list-cameras', '-t', '1'],
            timeout=5
        )
    except CalledProcessError as e:
        debug(f'unable to detect RPi camera: "{tools["hello"]} --list-cameras" failed: {e}')
        return []
    except Exception as e:
        debug(f'unable to detect RPi camera: unexpected error: {e}')
        return []

    # Parse output for camera entries
    # Format: "0 : imx708 [4608x2592 10-bit RGGB] (/base/soc/...)"
    cameras = []
    camera_pattern = re.compile(r'^(\d+)\s*:\s*(\w+)\s*\[([^\]]+)\]')

    for line in output.splitlines():
        match = camera_pattern.match(line.strip())
        if match:
            index = match.group(1)
            model = match.group(2)
            resolution = match.group(3)

            # Create device ID and friendly name
            device_id = f'rpicam{index}'
            device_name = f'RPi Camera ({model.upper()})'

            cameras.append((device_id, device_name))
            debug(f'RPi camera detected: {device_name} at index {index}')

    if not cameras:
        debug('no RPi cameras detected')

    return cameras


def get_camera_modes(index=0):
    """
    Get supported resolutions and framerates for a camera.
    Returns list of dicts: [{'width': int, 'height': int, 'fps': float}, ...]
    """
    tools = find_rpicam_tools()
    if not tools:
        return []

    try:
        output = utils.call_subprocess(
            [tools['hello'], '--list-cameras', '-t', '1'],
            timeout=5
        )
    except (CalledProcessError, Exception):
        return []

    # Parse modes from output
    # Format: "  1920x1080 [47.57 fps - ...]"
    modes = []
    in_camera_section = False
    camera_index_pattern = re.compile(rf'^{index}\s*:')
    mode_pattern = re.compile(r'\s+(\d+)x(\d+)\s+\[([0-9.]+)\s+fps')

    for line in output.splitlines():
        # Check if we're in the right camera section
        if camera_index_pattern.match(line):
            in_camera_section = True
            continue

        # Stop when we hit the next camera
        if in_camera_section and re.match(r'^\d+\s*:', line):
            break

        # Parse mode lines
        if in_camera_section:
            match = mode_pattern.match(line)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
                fps = float(match.group(3))

                # Avoid duplicates
                mode = {'width': width, 'height': height, 'fps': fps}
                if mode not in modes:
                    modes.append(mode)

    return modes


def is_rpicam_available():
    """Quick check if rpicam tools are available"""
    return find_rpicam_tools() is not None
