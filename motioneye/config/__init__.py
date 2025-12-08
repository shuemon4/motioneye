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
Config package - modular configuration management for motionEye.

This package provides configuration management split into focused modules:

Module Structure:
-----------------
- adaptation.py: Motion version compatibility mappings
- serialization.py: Config file format translation (.conf ↔ dict)
- defaults.py: Default configuration values for motion and cameras
- extensions.py: Plugin system for additional config sections
- commands.py: Action and monitor command handling
- backup.py: Backup and restore operations
- storage.py: Configuration I/O with caching
- camera/
  - crud.py: Add/remove camera operations
  - converters.py: UI ↔ dict conversion for camera configs

All public functions are re-exported here for backward compatibility.
Import from this package or directly from submodules:

    # Either works:
    from motioneye.config import get_main, set_camera
    from motioneye.config.storage import get_main
"""

# Phase 1: Pure function modules (zero dependencies)
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

# Phase 2: Support modules
from motioneye.config.extensions import (
    additional_section,
    additional_config,
    get_additional_structure,
    _get_additional_config,
    _set_additional_config,
    invalidate_additional_structure,
)

from motioneye.config.commands import (
    get_action_commands,
    get_monitor_command,
    invalidate_monitor_commands,
)

from motioneye.config.backup import (
    backup,
    restore as _restore_impl,
)

# Phase 3: Core storage (has dependencies on above modules)
from motioneye.config.storage import (
    get_main,
    set_main,
    get_camera,
    set_camera,
    get_camera_ids,
    get_enabled_local_motion_cameras,
    get_network_shares,
    invalidate,
    clear_camera_cache,
)

# Phase 4/5: Camera operations
from motioneye.config.camera.converters import (
    input_sanity_check,
    main_ui_to_dict,
    main_dict_to_ui,
    simple_mjpeg_camera_ui_to_dict,
    simple_mjpeg_camera_dict_to_ui as _simple_mjpeg_camera_dict_to_ui_impl,
    motion_camera_ui_to_dict as _motion_camera_ui_to_dict_impl,
    motion_camera_dict_to_ui as _motion_camera_dict_to_ui_impl,
)

from motioneye.config.camera.crud import (
    add_camera as _add_camera_impl,
    rem_camera as _rem_camera_impl,
)


# Wrapper functions that inject dependencies
# These were originally in config.py but need to be here since
# Python loads config/ as a package, not config.py as a module

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


def motion_camera_ui_to_dict(ui, prev_config=None):
    """
    Convert camera UI config to Motion config dict.

    Wrapper that calls the implementation in converters.py with injected dependencies.
    """
    # Import here to avoid circular imports
    from motioneye import tasks, settings

    def _task_scheduler(delay, func, **kwargs):
        tasks.add(delay, func, **kwargs)

    # Get the translation function from settings
    # settings.traduction is set up in meyectl.py during startup
    if settings.traduction and hasattr(settings.traduction, 'gettext'):
        translate_func = settings.traduction.gettext
    else:
        # Fallback to identity function if no translation available
        translate_func = lambda x: x

    return _motion_camera_ui_to_dict_impl(
        ui,
        prev_config,
        get_main_func=get_main,
        task_scheduler=_task_scheduler,
        translate=translate_func,
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


def restore(content):
    """
    Restore configuration from a backup file.

    Wrapper that calls config.backup.restore with injected invalidate dependency.
    """
    return _restore_impl(content, invalidate_func=invalidate)


# Re-export all public symbols
__all__ = [
    # Adaptation
    'adapt_config_directives',
    '_MOTION_41_TO_43_OPTIONS_MAPPING',
    '_MOTION_43_TO_41_OPTIONS_MAPPING',
    '_MOTION_43_TO_44_OPTIONS_MAPPING',
    '_MOTION_44_TO_43_OPTIONS_MAPPING',
    # Serialization
    '_value_to_python',
    '_python_to_value',
    '_conf_to_dict',
    '_dict_to_conf',
    # Defaults
    '_set_default_motion',
    '_set_default_motion_camera',
    '_set_default_simple_mjpeg_camera',
    # Extensions
    'additional_section',
    'additional_config',
    'get_additional_structure',
    '_get_additional_config',
    '_set_additional_config',
    'invalidate_additional_structure',
    # Commands
    'get_action_commands',
    'get_monitor_command',
    'invalidate_monitor_commands',
    # Backup
    'backup',
    'restore',
    # Storage
    'get_main',
    'set_main',
    'get_camera',
    'set_camera',
    'get_camera_ids',
    'get_enabled_local_motion_cameras',
    'get_network_shares',
    'invalidate',
    'clear_camera_cache',
    # Converters
    'input_sanity_check',
    'main_ui_to_dict',
    'main_dict_to_ui',
    'simple_mjpeg_camera_ui_to_dict',
    'simple_mjpeg_camera_dict_to_ui',
    'motion_camera_ui_to_dict',
    'motion_camera_dict_to_ui',
    # Camera CRUD
    'add_camera',
    'rem_camera',
]
