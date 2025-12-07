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
Camera configuration converters.

Provides functions for converting between UI format and dictionary format
for different camera types (motion cameras, simple MJPEG cameras, main config).

Note: The complex motion_camera_ui_to_dict and motion_camera_dict_to_ui
functions remain in config.py due to their extensive dependencies on
other config functions, settings, and external modules.

This module contains:
- Main configuration converters
- Simple MJPEG camera converters (self-contained)
- Input validation utilities
- Converter interface definitions for future extraction
"""

import hashlib
import logging
import re
import subprocess

from motioneye import settings, utils


def input_sanity_check(regex, value, key, msg):
    """
    Validate input value against a regex pattern.

    Args:
        regex: Regular expression pattern to match
        value: Input value to validate
        key: Setting key name for error messages
        msg: Error message if validation fails

    Returns:
        The validated value if it matches

    Raises:
        ValueError: If the value doesn't match the pattern
    """
    if not re.match(regex, value):
        raise ValueError(
            f'Value "{value}" for setting "{key}" did not match regex "{regex}": {msg}'
        )
    return value


def simple_mjpeg_camera_ui_to_dict(ui, prev_config=None):
    """
    Convert simple MJPEG camera UI format to config dictionary.

    Args:
        ui: UI configuration dictionary
        prev_config: Previous configuration to merge with

    Returns:
        Updated configuration dictionary
    """
    prev_config = dict(prev_config or {})

    data = {
        # device
        'camera_name': ui['name'],
        '@enabled': ui['enabled'],
    }

    # additional configs
    for name, value in list(ui.items()):
        if not name.startswith('_'):
            continue

        data['@' + name] = value

    prev_config.update(data)

    return prev_config


def simple_mjpeg_camera_dict_to_ui(data, get_action_commands_func):
    """
    Convert simple MJPEG camera config dictionary to UI format.

    Args:
        data: Camera configuration dictionary
        get_action_commands_func: Function to get action commands for camera

    Returns:
        UI configuration dictionary
    """
    ui = {
        'name': data['camera_name'],
        'enabled': data['@enabled'],
        'id': data['@id'],
        'proto': 'mjpeg',
        'url': data['@url'],
    }

    # additional configs
    for name, value in list(data.items()):
        if not name.startswith('@_'):
            continue

        ui[name[1:]] = value

    # action commands
    action_commands = get_action_commands_func(data)
    ui['actions'] = list(action_commands.keys())

    return ui


def main_ui_to_dict(ui):
    """
    Convert main configuration UI format to config dictionary.

    Args:
        ui: UI configuration dictionary with user credentials and settings

    Returns:
        Configuration dictionary with hashed passwords
    """
    data = {
        '@admin_username': ui['admin_username'],
        '@normal_username': ui['normal_username'],
    }

    def call_hook(u, p):
        if settings.PASSWORD_HOOK:
            env = {'MEYE_USERNAME': u, 'MEYE_PASSWORD': p}

            try:
                utils.call_subprocess(
                    settings.PASSWORD_HOOK, env=env, stderr=subprocess.STDOUT
                )
                logging.debug('password hook exec succeeded')

            except Exception as e:
                logging.error(f'password hook exec failed: {e}')

    if ui.get('admin_password') is not None:
        if ui['admin_password']:
            data['@admin_password'] = hashlib.sha1(
                ui['admin_password'].encode('utf-8')
            ).hexdigest()

        else:
            data['@admin_password'] = ''

        call_hook(ui['admin_username'], ui['admin_password'])

    if ui.get('normal_password') is not None:
        data['@normal_password'] = ui['normal_password']

        call_hook(ui['normal_username'], ui['normal_password'])

    if ui.get('lang') is not None:
        data['@lang'] = ui['lang']

    # additional configs
    for name, value in list(ui.items()):
        if not name.startswith('_'):
            continue

        data['@' + name] = value

    return data


def main_dict_to_ui(data):
    """
    Convert main configuration dictionary to UI format.

    Args:
        data: Configuration dictionary

    Returns:
        UI configuration dictionary with masked passwords
    """
    ui = {
        'admin_username': data['@admin_username'],
        'normal_username': data['@normal_username'],
    }

    if data['@lang']:
        ui['lang'] = data['@lang']

    # don't transmit password (or its hash) to the client;
    # instead transmit an indication of password being set
    if data['@admin_password']:
        ui['admin_password'] = '*****'

    else:
        ui['admin_password'] = ''

    if data['@normal_password']:
        ui['normal_password'] = '*****'

    else:
        ui['normal_password'] = ''

    # additional configs
    for name, value in list(data.items()):
        if not name.startswith('@_'):
            continue

        ui[name[1:]] = value

    return ui


# Validation regex patterns used by motion camera converters
# These must match the ones in motioneye/static/js/main.js
DEVICE_NAME_REGEX = r'^[A-Za-z0-9-_+ ]+$'
FILENAME_REGEX = r'^([A-Za-z0-9 ()/._-]|%[CYmdHMSqv])+$'
DIRNAME_REGEX = r'^[A-Za-z0-9 ()/._-]+$'
EMAIL_REGEX = r'^[A-Za-z0-9 _+.@^~<>,-]+$'
WEBHOOK_URL_REGEX = r"^[^;']+$"
