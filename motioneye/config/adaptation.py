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
Motion version compatibility adaptations.

Handles configuration directive mapping between different Motion versions:
- Motion 4.1 to 4.3
- Motion 4.3 to 4.4
- And reverse mappings
"""


def text_double(v, data):
    """Convert text_double boolean to text_scale integer."""
    return {'text_scale': [1, 2][v]}


def webcontrol_html_output(v, data):
    """Convert webcontrol_html_output to webcontrol_interface."""
    return {'webcontrol_interface': int(v)}


def text_scale(v, data):
    """Convert text_scale integer to text_double boolean."""
    return {'text_double': True if int(v) > 1 else False}


def webcontrol_interface(v, data):
    """Convert webcontrol_interface to webcontrol_html_output."""
    return {'webcontrol_html_output': bool(v)}


# Motion 4.1 to 4.3 option mappings
_MOTION_41_TO_43_OPTIONS_MAPPING = {
    'ffmpeg_video_codec': 'movie_codec',
    'ffmpeg_output_movies': 'movie_output',
    'ffmpeg_output_debug_movies': 'movie_output_motion',
    'ffmpeg_variable_bitrate': 'movie_quality',
    'lightswitch': 'lightswitch_percent',
    'max_movie_time': 'movie_max_time',
    'output_pictures': 'picture_output',
    'output_debug_pictures': 'picture_output_motion',
    'quality': 'picture_quality',
    'rtsp_uses_tcp': 'netcam_use_tcp',
    'text_double': text_double,
    'webcontrol_html_output': webcontrol_html_output,
}


# Motion 4.3 to 4.1 option mappings (reverse)
_MOTION_43_TO_41_OPTIONS_MAPPING = {
    'movie_codec': 'ffmpeg_video_codec',
    'movie_output': 'ffmpeg_output_movies',
    'movie_output_motion': 'ffmpeg_output_debug_movies',
    'movie_quality': 'ffmpeg_variable_bitrate',
    'lightswitch_percent': 'lightswitch',
    'movie_max_time': 'max_movie_time',
    'picture_output': 'output_pictures',
    'picture_output_motion': 'output_debug_pictures',
    'picture_quality': 'quality',
    'netcam_use_tcp': 'rtsp_uses_tcp',
    'text_scale': text_scale,
    'webcontrol_interface': webcontrol_interface,
    # motion pre-v4.1
    'webcontrol_parms': None,
}


def netcam_keepalive_params(v, data):
    """Convert netcam_keepalive to netcam_params format."""
    # value can be 'force' as well
    v = 'on' if v == True else 'off' if v == False else v

    if 'netcam_params' in data and data['netcam_params']:
        return {'netcam_params': data['netcam_params'] + ',keepalive = ' + v}

    return {'netcam_params': 'keepalive = ' + v}


def netcam_tolerant_check_params(v, data):
    """Convert netcam_tolerant_check to netcam_params format."""
    v = 'on' if v else 'off'

    if 'netcam_params' in data and data['netcam_params']:
        return {'netcam_params': data['netcam_params'] + ',tolerant_check = ' + v}

    return {'netcam_params': 'tolerant_check = ' + v}


def netcam_use_tcp_params(v, data):
    """Convert netcam_use_tcp to netcam_params format."""
    v = 'tcp' if v else 'udp'

    if 'netcam_params' in data and data['netcam_params']:
        return {'netcam_params': data['netcam_params'] + ',rtsp_transport = ' + v}

    return {'netcam_params': 'rtsp_transport = ' + v}


def netcam_params(v, data):
    """Parse netcam_params string into individual settings."""
    params = {}
    for param in v.split(','):
        param = [x.strip() for x in param.split('=')]
        if param[0] == 'keepalive':
            params['netcam_keepalive'] = param[1]

        elif param[0] == 'tolerant_check':
            params['netcam_tolerant_check'] = param[1]

        elif param[0] == 'rtsp_transport':
            if param[1] == 'udp':
                params['netcam_use_tcp'] = False

            else:
                params['netcam_use_tcp'] = True

    return params


# Motion 4.3 to 4.4 option mappings
_MOTION_43_TO_44_OPTIONS_MAPPING = {
    'netcam_keepalive': netcam_keepalive_params,
    'netcam_tolerant_check': netcam_tolerant_check_params,
    'netcam_use_tcp': netcam_use_tcp_params,
    'vid_control_params': 'video_params',
    'videodevice': 'video_device',
}


# Motion 4.4 to 4.3 option mappings (reverse)
_MOTION_44_TO_43_OPTIONS_MAPPING = {
    'netcam_params': netcam_params,
    'video_params': 'vid_control_params',
    'video_device': 'videodevice',
}


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
    'swf': 'flv',
    'ffv1': 'mkv',
}


def movie_codec_to_container(v, data):
    """Rename movie_codec to movie_container for Motion 5.0.

    Also migrates legacy formats that were removed in Motion 5.0:
    - mpeg4, msmpeg4 -> mp4
    - swf -> flv
    - ffv1 -> mkv
    """
    container = _LEGACY_FORMAT_MAPPING.get(v, v)
    return {'movie_container': container}


def migrate_legacy_movie_container(v, data):
    """Migrate legacy movie_container values to Motion 5.0 compatible values.

    Handles configs that already have movie_container set to legacy values
    like mpeg4, msmpeg4, swf, ffv1.
    """
    return {'movie_container': _LEGACY_FORMAT_MAPPING.get(v, v)}


_MOTION_44_TO_50_OPTIONS_MAPPING = {
    'webcontrol_interface': webcontrol_interface_to_50,
    'camera_name': camera_name_to_device_name,
    'movie_codec': movie_codec_to_container,
    'movie_container': migrate_legacy_movie_container,  # Migrate legacy values
    'stream_port': None,  # Removed in 5.0
    'stream_localhost': None,
    'stream_auth_method': None,
    'stream_authentication': None,
    'auto_brightness': None,
    'setup_mode': None,
}


# Motion 5.0 to 4.4 option mappings (reverse - for reading Motion 5.0 configs)
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


_MOTION_50_TO_44_OPTIONS_MAPPING = {
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
