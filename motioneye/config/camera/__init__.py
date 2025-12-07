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
Camera configuration operations - CRUD and type conversions.

Submodules:
- crud.py: Add/remove camera operations
- converters.py: UI ↔ dict conversion utilities
- types/: Camera type-specific converters (future)
"""

from motioneye.config.camera.crud import add_camera, rem_camera
from motioneye.config.camera.converters import (
    input_sanity_check,
    simple_mjpeg_camera_ui_to_dict,
    simple_mjpeg_camera_dict_to_ui,
    DEVICE_NAME_REGEX,
    FILENAME_REGEX,
    DIRNAME_REGEX,
    EMAIL_REGEX,
    WEBHOOK_URL_REGEX,
)

__all__ = [
    'add_camera',
    'rem_camera',
    'input_sanity_check',
    'simple_mjpeg_camera_ui_to_dict',
    'simple_mjpeg_camera_dict_to_ui',
    'DEVICE_NAME_REGEX',
    'FILENAME_REGEX',
    'DIRNAME_REGEX',
    'EMAIL_REGEX',
    'WEBHOOK_URL_REGEX',
]
