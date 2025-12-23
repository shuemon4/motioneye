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
Camera add/remove operations.

Provides functions for adding new cameras and removing existing cameras
from the motionEye configuration.
"""

import logging
import os.path
from re import match
from urllib.parse import urlunparse

from motioneye import settings, utils
from motioneye.controls import pictl, v4l2ctl

from motioneye.config.defaults import (
    _set_default_motion_camera,
    _set_default_simple_mjpeg_camera,
)


# Config file name template
_CAMERA_CONFIG_FILE_NAME = 'camera-%(id)s.conf'


def add_camera(device_details, get_camera_ids_func, get_camera_func, set_camera_func,
               motion_camera_dict_to_ui_func, motion_camera_ui_to_dict_func,
               simple_mjpeg_camera_dict_to_ui_func, simple_mjpeg_camera_ui_to_dict_func,
               clear_cache_func):
    """
    Add a new camera to the configuration.

    Supports v4l2, motioneye, mmal/libcamera, netcam, and mjpeg camera types.

    Args:
        device_details: Dict with camera details (proto, path, host, port, etc.)
        get_camera_ids_func: Function to get list of camera IDs
        get_camera_func: Function to get camera config by ID
        set_camera_func: Function to save camera config
        motion_camera_dict_to_ui_func: Converter function
        motion_camera_ui_to_dict_func: Converter function
        simple_mjpeg_camera_dict_to_ui_func: Converter function
        simple_mjpeg_camera_ui_to_dict_func: Converter function
        clear_cache_func: Function to clear camera config cache

    Returns:
        Camera configuration dictionary for the new camera
    """
    proto = device_details['proto']
    if proto in ['netcam', 'mjpeg']:
        host = device_details['host']
        if device_details['port']:
            host += ':' + str(device_details['port'])

        device_details['url'] = urlunparse(
            (device_details['scheme'], host, device_details['path'], '', '', '')
        )

    # determine the last camera id
    camera_ids = get_camera_ids_func()

    camera_id = 1
    while camera_id in camera_ids:
        camera_id += 1

    logging.info(f'adding new {proto} camera with id {camera_id}...')

    # prepare a default camera config
    camera_config = {'@enabled': True}
    if proto == 'v4l2':
        # find a suitable resolution
        for w, h in v4l2ctl.list_resolutions(device_details['path']):
            if w > 300:
                camera_config['width'] = w
                camera_config['height'] = h
                break

        camera_config['videodevice'] = device_details['path']

    elif proto == 'motioneye':
        camera_config['@proto'] = 'motioneye'
        camera_config['@scheme'] = device_details['scheme']
        camera_config['@host'] = device_details['host']
        camera_config['@port'] = device_details['port']
        camera_config['@path'] = device_details['path']
        camera_config['@username'] = device_details['username']
        camera_config['@password'] = device_details['password']
        camera_config['@remote_camera_id'] = device_details['remote_camera_id']

    elif proto in ('libcamera', 'mmal'):
        # libcamera is the only CSI camera backend on Pi 4+ / Trixie
        # 'mmal' is accepted as alias for backwards compatibility
        if not pictl.uses_libcamera():
            raise ValueError(
                'libcamera not available. Ensure rpicam-apps is installed '
                'and a CSI camera is connected.'
            )
        camera_config['libcam_device'] = device_details['path']
        camera_config['libcam_buffer_count'] = 4

        # Check if camera supports autofocus (Camera v3 / IMX708)
        if device_details.get('supports_autofocus'):
            camera_config['@supports_autofocus'] = True
            # Camera v3 - high resolution default
            camera_config['width'] = 1920
            camera_config['height'] = 1080
        else:
            # Camera v2 (IMX219) and others - conservative resolution
            camera_config['width'] = 1280
            camera_config['height'] = 720

    elif proto == 'netcam':
        camera_config['netcam_url'] = device_details['url']

        if device_details['username']:
            camera_config['netcam_userpass'] = (
                device_details['username'] + ':' + device_details['password']
            )

        camera_config['netcam_keepalive'] = device_details.get('keep_alive', False)
        camera_config['netcam_tolerant_check'] = True

        if device_details.get('camera_index') == 'udp':
            camera_config['netcam_use_tcp'] = False

        if match(r'^rtsp|^rtmp', camera_config['netcam_url']):
            camera_config['width'] = 640
            camera_config['height'] = 480

    else:  # assuming mjpeg
        camera_config['@proto'] = 'mjpeg'
        camera_config['@url'] = device_details['url']

    if utils.is_local_motion_camera(camera_config):
        _set_default_motion_camera(camera_id, camera_config)

        # go through the config conversion functions back and forth once
        camera_config = motion_camera_ui_to_dict_func(
            motion_camera_dict_to_ui_func(camera_config), camera_config
        )

    elif utils.is_simple_mjpeg_camera(camera_config):
        _set_default_simple_mjpeg_camera(camera_id, camera_config)

        # go through the config conversion functions back and forth once
        camera_config = simple_mjpeg_camera_ui_to_dict_func(
            simple_mjpeg_camera_dict_to_ui_func(camera_config), camera_config
        )

    # write the configuration to file
    set_camera_func(camera_id, camera_config)

    clear_cache_func()

    camera_config = get_camera_func(camera_id)

    return camera_config


def rem_camera(camera_id, get_main_func, set_main_func, clear_cache_func):
    """
    Remove a camera from the configuration.

    Removes the camera from main config and deletes the camera config file.

    Args:
        camera_id: Integer camera ID to remove
        get_main_func: Function to get main config
        set_main_func: Function to save main config
        clear_cache_func: Function to clear camera config cache
    """
    camera_config_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {
        'id': camera_id
    }

    # remove the camera from the main config
    main_config = get_main_func()
    cameras = main_config.setdefault('camera', [])
    cameras = [t for t in cameras if t != camera_config_name]

    main_config['camera'] = cameras

    set_main_func(main_config)

    logging.info(f'removing camera config file {camera_config_path}...')

    clear_cache_func()

    try:
        os.remove(camera_config_path)

    except Exception as e:
        logging.error(f'could not remove camera config file {camera_config_path}: {e}')

        raise
