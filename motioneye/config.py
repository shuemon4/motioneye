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
Motion and camera configuration management.

This module serves as the main entry point for configuration operations,
delegating most functionality to specialized submodules while maintaining
backward compatibility with the original API.

Main functions exported:
- Configuration I/O: get_main(), set_main(), get_camera(), set_camera(), get_camera_ids()
- Camera operations: add_camera(), rem_camera()
- Backup/restore: backup(), restore()
- Extensions: get_additional_structure(), additional_section, additional_config
- Converters: motion_camera_ui_to_dict(), motion_camera_dict_to_ui()
- Commands: get_action_commands(), get_monitor_command()
- Network: get_network_shares()

Most implementation has been refactored into:
- motioneye.config.storage: Configuration file I/O and caching
- motioneye.config.camera.crud: Camera add/remove operations
- motioneye.config.camera.converters: UI/dict conversion functions
- motioneye.config.backup: Backup and restore operations
- motioneye.config.commands: Action and monitor command handling
- motioneye.config.extensions: Plugin system for additional configs
- motioneye.config.adaptation: Version compatibility mappings
- motioneye.config.serialization: Config file parsing/writing
- motioneye.config.defaults: Default value assignment
"""

import logging
import os.path
from errno import EEXIST, ENOENT
from re import match, sub
from shlex import split

from motioneye import meyectl, motionctl, settings, tasks, uploadservices, utils
from motioneye.controls import diskctl, pictl, smbctl, v4l2ctl

# Import from refactored modules
from motioneye.config.adaptation import (
    adapt_config_directives,
    _MOTION_41_TO_43_OPTIONS_MAPPING,
    _MOTION_43_TO_41_OPTIONS_MAPPING,
    _MOTION_43_TO_44_OPTIONS_MAPPING,
    _MOTION_44_TO_43_OPTIONS_MAPPING,
)
from motioneye.config.serialization import (
    _value_to_python,
    _python_to_value,
    _conf_to_dict,
    _dict_to_conf,
)
from motioneye.config.defaults import (
    _set_default_motion,
    _set_default_motion_camera,
    _set_default_simple_mjpeg_camera,
)
from motioneye.config.commands import (
    get_action_commands,
    get_monitor_command,
    invalidate_monitor_commands,
)
from motioneye.config.extensions import (
    additional_section,
    additional_config,
    get_additional_structure,
    _get_additional_config,
    _set_additional_config,
)
from motioneye.config.storage import (
    get_main,
    set_main,
    get_camera,
    set_camera,
    get_camera_ids,
    get_enabled_local_motion_cameras,
    get_network_shares,
    invalidate,
)
from motioneye.config.camera.crud import (
    add_camera as _add_camera_impl,
    rem_camera as _rem_camera_impl,
)
from motioneye.config.camera.converters import (
    input_sanity_check,
    main_ui_to_dict,
    main_dict_to_ui,
    simple_mjpeg_camera_ui_to_dict,
    simple_mjpeg_camera_dict_to_ui as _simple_mjpeg_camera_dict_to_ui_impl,
    motion_camera_ui_to_dict as _motion_camera_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_camera_dict_to_ui_impl,
)
from motioneye.config.backup import (
    backup,
    restore as _restore_impl,
)

_CAMERA_CONFIG_FILE_NAME = 'camera-%(id)s.conf'
_MAIN_CONFIG_FILE_NAME = 'motion.conf'


# NOTE: Adaptation functions (text_double, webcontrol_html_output, etc.)
# and version mappings (_MOTION_*_OPTIONS_MAPPING) have been extracted to
# motioneye/config/adaptation.py

# NOTE: Storage functions (get_main, set_main, get_camera, set_camera, etc.)
# have been extracted to motioneye/config/storage.py


def add_camera(device_details):
    """
    Add a new camera to the configuration.

    Wrapper that calls config.camera.crud.add_camera with injected dependencies.
    """
    return _add_camera_impl(
        device_details,
        get_camera_ids_func=get_camera_ids,
        get_camera_func=get_camera,
        set_camera_func=set_camera,
        motion_camera_dict_to_ui_func=motion_camera_dict_to_ui,
        motion_camera_ui_to_dict_func=motion_camera_ui_to_dict,
        simple_mjpeg_camera_dict_to_ui_func=simple_mjpeg_camera_dict_to_ui,
        simple_mjpeg_camera_ui_to_dict_func=simple_mjpeg_camera_ui_to_dict,
        clear_cache_func=invalidate,
    )


def rem_camera(camera_id):
    """
    Remove a camera from the configuration.

    Wrapper that calls config.camera.crud.rem_camera with injected dependencies.
    """
    return _rem_camera_impl(
        camera_id,
        get_main_func=get_main,
        set_main_func=set_main,
        clear_cache_func=invalidate,
    )


# NOTE: Main converters (main_ui_to_dict, main_dict_to_ui) have been
# extracted to motioneye/config/camera/converters.py


def motion_camera_ui_to_dict(ui, prev_config=None):
    """
    Convert camera UI config to Motion config dict.

    Wrapper that calls the implementation in converters.py with injected dependencies.
    """
    def _task_scheduler(delay, func, **kwargs):
        tasks.add(delay, func, **kwargs)

    return _motion_camera_ui_to_dict_impl(
        ui,
        prev_config,
        get_main_func=get_main,
        task_scheduler=_task_scheduler,
        translate=_,
    )


def motion_camera_dict_to_ui(data):
    """
    Convert Motion config dict to camera UI format.

    Wrapper that calls the implementation in converters.py with injected dependencies.
    """
    return _motion_camera_dict_to_ui_impl(
        data,
        get_action_commands_func=get_action_commands,
    )


def simple_mjpeg_camera_dict_to_ui(data):
    """
    Convert simple MJPEG camera config dictionary to UI format.

    Wrapper that calls config.camera.converters.simple_mjpeg_camera_dict_to_ui
    with injected get_action_commands dependency.
    """
    return _simple_mjpeg_camera_dict_to_ui_impl(data, get_action_commands)


# NOTE: Command functions (get_action_commands, get_monitor_command,
# invalidate_monitor_commands) have been extracted to motioneye/config/commands.py


def restore(content):
    """
    Restore configuration from a backup file.

    Wrapper that calls config.backup.restore with injected invalidate dependency.
    """
    return _restore_impl(content, invalidate_func=invalidate)


# NOTE: Serialization functions (_value_to_python, _python_to_value,
# _conf_to_dict, _dict_to_conf) have been extracted to
# motioneye/config/serialization.py


# NOTE: Default value functions (_set_default_motion, _set_default_motion_camera,
# _set_default_simple_mjpeg_camera) have been extracted to
# motioneye/config/defaults.py

# NOTE: Extension functions (get_additional_structure, _get_additional_config,
# _set_additional_config, additional_section, additional_config) have been
# extracted to motioneye/config/extensions.py
