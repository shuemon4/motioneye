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
Motion 5.0+ configuration adaptations.

This version requires Motion 5.0 or later.
Handles configuration directive mapping for Motion 5.0+ compatibility.
"""


# Motion 4.4 to 5.0 option mappings
def webcontrol_interface_to_50(v, data):
    """Convert integer webcontrol_interface to Motion 5.0 string."""
    mapping = {0: 'off', 1: 'default', 2: 'user'}
    return {'webcontrol_interface': mapping.get(int(v), 'default')}


def camera_name_to_device_name(v, data):
    """Rename camera_name to device_name for Motion 5.0."""
    return {'device_name': v}


# Legacy formats removed in Motion 5.0
_LEGACY_FORMAT_MAPPING = {
    'mpeg4': 'mp4',
    'msmpeg4': 'mp4',
    'swf': 'mp4',
    'flv': 'mp4',
    'ffv1': 'mkv',
    'ogg': 'mp4',
}


def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0.

    Also migrates legacy formats that were removed in Motion 5.0:
    - mpeg4, msmpeg4 -> mp4
    - swf, flv, ogg -> mp4
    - ffv1 -> mkv

    Note: Minimal migration support only. Project targets fresh Pi 5 installs.
    """
    container = _LEGACY_FORMAT_MAPPING.get(v, v)
    return {'movie_container': container}


def migrate_legacy_movie_container(v, data):
    """Migrate legacy movie_container values to Motion 5.0 compatible values.

    Handles configs that already have movie_container set to legacy values
    like mpeg4, msmpeg4, swf, ffv1.
    """
    return {'movie_container': _LEGACY_FORMAT_MAPPING.get(v, v)}


MOTION_50_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_to_50,
    'camera_name': camera_name_to_device_name,
    'movie_codec': movie_codec_to_container,
    'movie_container': migrate_legacy_movie_container,  # Migrate legacy values
    'stream_port': None,  # Removed in 5.0
    'stream_localhost': None,
    'stream_auth_method': None,
    'stream_authentication': None,
    'setup_mode': None,
}


# Motion 5.0 reverse mappings (for reading Motion 5.0 configs)
def webcontrol_interface_from_50(v, data):
    """Convert Motion 5.0 string webcontrol_interface to integer."""
    mapping = {'off': 0, 'default': 1, 'user': 2, 'simple': 1}
    if isinstance(v, int):
        return {'webcontrol_interface': v}
    return {'webcontrol_interface': mapping.get(str(v).lower(), 1)}


def device_name_to_camera_name(v, data):
    """Rename device_name to camera_name for internal use."""
    return {'camera_name': v}


def movie_container_to_codec(v, data):
    """Rename movie_container to movie_codec for internal use."""
    return {'movie_codec': v}


MOTION_50_FROM_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_from_50,
    'device_name': device_name_to_camera_name,
    'movie_container': movie_container_to_codec,
}


def adapt_config_directives(data, mapping):
    """
    Adapt configuration directives using the provided mapping.

    Transforms config dictionary keys/values according to the mapping rules.
    Supports both simple string mappings and callable transformers.
    If a mapping value is explicitly set to None (key exists in mapping),
    the config key is removed from data.

    Args:
        data: Configuration dictionary to transform (modified in place)
        mapping: Dictionary mapping old names to new names or transformer functions
                 If value is None, the key is removed from data.
    """
    for name in list(data.keys()):
        if name not in mapping:
            continue

        mapped = mapping[name]
        value = data.pop(name)

        if mapped is None:
            # Explicitly mapped to None - remove the option (don't add it back)
            continue

        if callable(mapped):
            data.update(mapped(value, data))

        else:  # assuming simple new name
            data[mapped] = value
