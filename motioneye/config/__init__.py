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
    restore,
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
    simple_mjpeg_camera_ui_to_dict,
    # simple_mjpeg_camera_dict_to_ui requires get_action_commands injection
)

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
    'simple_mjpeg_camera_ui_to_dict',
]
