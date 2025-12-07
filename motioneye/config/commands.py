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
Action and monitor command handling for cameras.

Provides functions to discover and manage executable action commands
(like PTZ controls, alarms, etc.) and monitor commands for cameras.
"""

import os.path

from motioneye import settings


# Available camera actions
_ACTIONS = [
    'lock',
    'unlock',
    'light_on',
    'light_off',
    'alarm_on',
    'alarm_off',
    'up',
    'right',
    'down',
    'left',
    'zoom_in',
    'zoom_out',
    'preset1',
    'preset2',
    'preset3',
    'preset4',
    'preset5',
    'preset6',
    'preset7',
    'preset8',
    'preset9',
]

# Cache for monitor commands
_monitor_command_cache = {}


def get_action_commands(camera_config):
    """
    Get available action commands for a camera.

    Scans the config directory for executable action scripts named
    {action}_{camera_id} and returns a dictionary of available actions.

    Args:
        camera_config: Camera configuration dictionary with '@id' key

    Returns:
        Dictionary mapping action names to script paths or True for built-in actions
    """
    camera_id = camera_config['@id']

    action_commands = {}
    for action in _ACTIONS:
        path = os.path.join(settings.CONF_PATH, f'{action}_{camera_id}')
        if os.access(path, os.X_OK):
            action_commands[action] = path

    if camera_config.get('@manual_snapshots') and bool(
        camera_config.get('snapshot_filename')
    ):
        action_commands['snapshot'] = True

    if camera_config.get('@manual_record'):
        action_commands['record'] = True

    return action_commands


def get_monitor_command(camera_id):
    """
    Get the monitor command for a camera.

    Checks for an executable monitor script in the config directory
    and caches the result.

    Args:
        camera_id: Integer camera ID

    Returns:
        Path to monitor script or None if not found
    """
    if camera_id not in _monitor_command_cache:
        path = os.path.join(settings.CONF_PATH, f'monitor_{camera_id}')
        if os.access(path, os.X_OK):
            _monitor_command_cache[camera_id] = path

        else:
            _monitor_command_cache[camera_id] = None

    return _monitor_command_cache[camera_id]


def invalidate_monitor_commands():
    """Clear the monitor command cache."""
    _monitor_command_cache.clear()
