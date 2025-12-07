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
Configuration I/O operations and caching.

Provides functions for reading and writing main and camera configuration
files, with caching for performance.
"""

import logging
import os.path
from errno import ENOENT
from re import match

from motioneye import motionctl, settings, utils

from motioneye.config.adaptation import (
    adapt_config_directives,
    _MOTION_41_TO_43_OPTIONS_MAPPING,
    _MOTION_43_TO_41_OPTIONS_MAPPING,
    _MOTION_43_TO_44_OPTIONS_MAPPING,
    _MOTION_44_TO_43_OPTIONS_MAPPING,
)
from motioneye.config.serialization import _conf_to_dict, _dict_to_conf
from motioneye.config.defaults import (
    _set_default_motion,
    _set_default_motion_camera,
    _set_default_simple_mjpeg_camera,
)
from motioneye.config.extensions import (
    _get_additional_config,
    _set_additional_config,
    invalidate_additional_structure,
)


# Config file name templates
_CAMERA_CONFIG_FILE_NAME = 'camera-%(id)s.conf'
_MAIN_CONFIG_FILE_NAME = 'motion.conf'

# Global caches
_main_config_cache = None
_camera_config_cache = {}
_camera_ids_cache = None


def get_main(as_lines=False):
    """
    Get the main motion configuration.

    Args:
        as_lines: If True, return raw config file lines instead of parsed dict

    Returns:
        Configuration dictionary or list of lines if as_lines=True
    """
    global _main_config_cache

    if not as_lines and _main_config_cache is not None:
        return _main_config_cache

    config_file_path = os.path.join(settings.CONF_PATH, _MAIN_CONFIG_FILE_NAME)

    logging.debug(f'reading main config from file {config_file_path}...')

    lines = None
    try:
        f = open(config_file_path)

    except OSError as e:
        if e.errno == ENOENT:  # file does not exist
            logging.info(
                f'main config file {config_file_path} does not exist, using default values'
            )

            lines = []
            f = None

        else:
            logging.error(f'could not open main config file {config_file_path}: {e}')

            raise

    if lines is None and f:
        try:
            lines = [line[:-1] for line in f.readlines()]

        except Exception as e:
            logging.error(f'could not read main config file {config_file_path}: {e}')

            raise

        finally:
            f.close()

    if as_lines:
        return lines

    main_config = _conf_to_dict(
        lines,
        list_names=['camera'],
        no_convert=[
            '@admin_username',
            '@admin_password',
            '@normal_username',
            '@normal_password',
        ],
    )

    # adapt directives for motion versions < 4.2 and > 4.3
    adapt_config_directives(main_config, _MOTION_41_TO_43_OPTIONS_MAPPING)
    adapt_config_directives(main_config, _MOTION_44_TO_43_OPTIONS_MAPPING)

    _get_additional_config(main_config)
    _set_default_motion(main_config)

    _main_config_cache = main_config

    return main_config


def set_main(main_config):
    """
    Save the main motion configuration.

    Args:
        main_config: Configuration dictionary to save
    """
    global _main_config_cache

    main_config = dict(main_config)
    for n, v in list(_main_config_cache.items()):
        main_config.setdefault(n, v)
    _main_config_cache = main_config

    main_config = dict(main_config)
    _set_additional_config(main_config)

    # adapt directives for motion versions < 4.2 and > 4.3
    if motionctl.is_motion_pre42():
        adapt_config_directives(main_config, _MOTION_43_TO_41_OPTIONS_MAPPING)

    elif motionctl.is_motion_post43():
        adapt_config_directives(main_config, _MOTION_43_TO_44_OPTIONS_MAPPING)

    config_file_path = os.path.join(settings.CONF_PATH, _MAIN_CONFIG_FILE_NAME)

    # read the actual configuration from file
    lines = get_main(as_lines=True)

    # write the configuration to file
    logging.debug(f'writing main config to {config_file_path}...')

    try:
        f = open(config_file_path, 'w')

    except Exception as e:
        logging.error(
            f'could not open main config file {config_file_path} for writing: {e}'
        )

        raise

    lines = _dict_to_conf(lines, main_config, list_names=['camera'])

    try:
        f.writelines([utils.make_str(line) + '\n' for line in lines])

    except Exception as e:
        logging.error(f'could not write main config file {config_file_path}: {e}')

        raise

    finally:
        f.close()


def get_camera_ids(filter_valid=True):
    """
    Get list of camera IDs from config directory.

    Args:
        filter_valid: If True, only return IDs for valid camera configs

    Returns:
        Sorted list of camera ID integers
    """
    global _camera_ids_cache

    if _camera_ids_cache is not None:
        return _camera_ids_cache

    config_path = settings.CONF_PATH

    logging.debug(f'listing config dir {config_path}...')

    try:
        ls = os.listdir(config_path)

    except Exception as e:
        logging.error(f'failed to list config dir {config_path}: {e}')

        raise

    camera_ids = []

    pattern = '^' + _CAMERA_CONFIG_FILE_NAME.replace('%(id)s', r'(\d+)') + '$'
    for name in ls:
        _match = match(pattern, name)
        if _match:
            camera_id = int(_match.groups()[0])
            logging.debug(f'found camera with id {camera_id}')

            camera_ids.append(camera_id)

    camera_ids.sort()

    if not filter_valid:
        return camera_ids

    filtered_camera_ids = []
    for camera_id in camera_ids:
        if get_camera(camera_id):
            filtered_camera_ids.append(camera_id)

    _camera_ids_cache = filtered_camera_ids

    return filtered_camera_ids


def get_enabled_local_motion_cameras():
    """
    Get list of enabled local motion cameras.

    Returns:
        List of camera config dictionaries for enabled local motion cameras
    """
    if not get_main().get('@enabled'):
        return []

    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]
    return [c for c in cameras if c.get('@enabled') and utils.is_local_motion_camera(c)]


def get_network_shares():
    """
    Get list of network share mount configurations.

    Returns:
        List of dicts with server, share, smb_ver, username, password keys
    """
    if not get_main().get('@enabled'):
        return []

    camera_ids = get_camera_ids()
    cameras = [get_camera(camera_id) for camera_id in camera_ids]

    mounts = []
    for camera in cameras:
        if camera.get('@storage_device') != 'network-share':
            continue

        mounts.append(
            {
                'server': camera['@network_server'],
                'share': camera['@network_share_name'],
                'smb_ver': camera['@network_smb_ver'],
                'username': camera['@network_username'],
                'password': camera['@network_password'],
            }
        )

    return mounts


def get_camera(camera_id, as_lines=False):
    """
    Get camera configuration by ID.

    Args:
        camera_id: Integer camera ID
        as_lines: If True, return raw config file lines

    Returns:
        Camera configuration dictionary, list of lines, or None if invalid
    """
    if not as_lines and camera_id in _camera_config_cache:
        return _camera_config_cache[camera_id]

    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {
        'id': camera_id
    }

    logging.debug(f'reading camera config from {camera_config_path}...')

    try:
        f = open(camera_config_path)

    except Exception as e:
        logging.error(f'could not open camera config file: {str(e)}')

        raise

    try:
        lines = [line.strip() for line in f.readlines()]

    except Exception as e:
        logging.error(f'could not read camera config file {camera_config_path}: {e}')

        raise

    finally:
        f.close()

    if as_lines:
        return lines

    camera_config = _conf_to_dict(
        lines,
        no_convert=[
            '@network_share_name',
            '@network_smb_ver',
            '@network_server',
            '@network_username',
            '@network_password',
            '@storage_device',
            '@upload_server',
            '@upload_username',
            '@upload_password',
            '@upload_endpoint_url',
            '@upload_access_key',
            '@upload_secret_key',
            '@upload_bucket',
            'camera_name',
        ],
    )

    if utils.is_local_motion_camera(camera_config):
        # determine the enabled status
        main_config = get_main()
        cameras = main_config.get('camera', [])
        camera_config['@enabled'] = (
            _CAMERA_CONFIG_FILE_NAME % {'id': camera_id} in cameras
        )
        camera_config['@id'] = camera_id

        # adapt directives for motion versions < 4.2 and > 4.3
        adapt_config_directives(camera_config, _MOTION_41_TO_43_OPTIONS_MAPPING)
        adapt_config_directives(camera_config, _MOTION_44_TO_43_OPTIONS_MAPPING)

        _get_additional_config(camera_config, camera_id=camera_id)

        _set_default_motion_camera(camera_id, camera_config)

    elif utils.is_remote_camera(camera_config):
        pass

    elif utils.is_simple_mjpeg_camera(camera_config):
        _get_additional_config(camera_config, camera_id=camera_id)

        _set_default_simple_mjpeg_camera(camera_id, camera_config)

    else:  # incomplete configuration
        logging.warning(
            f'camera config file at {camera_config_path} is incomplete, ignoring'
        )

        return None

    _camera_config_cache[camera_id] = dict(camera_config)

    return camera_config


def set_camera(camera_id, camera_config):
    """
    Save camera configuration.

    Args:
        camera_id: Integer camera ID
        camera_config: Camera configuration dictionary to save
    """
    camera_config['@id'] = camera_id
    _camera_config_cache[camera_id] = camera_config

    camera_config = dict(camera_config)

    if utils.is_local_motion_camera(camera_config):
        # adapt directives for motion versions < 4.2 and > 4.3
        if motionctl.is_motion_pre42():
            adapt_config_directives(camera_config, _MOTION_43_TO_41_OPTIONS_MAPPING)

        elif motionctl.is_motion_post43():
            adapt_config_directives(camera_config, _MOTION_43_TO_44_OPTIONS_MAPPING)

        # set the enabled status in main config
        main_config = get_main()
        cameras = main_config.setdefault('camera', [])
        config_file_name = _CAMERA_CONFIG_FILE_NAME % {'id': camera_id}
        if camera_config['@enabled'] and config_file_name not in cameras:
            cameras.append(config_file_name)

        elif not camera_config['@enabled']:
            cameras = [c for c in cameras if c != config_file_name]

        main_config['camera'] = cameras

        set_main(main_config)
        _set_additional_config(camera_config, camera_id=camera_id)

    elif utils.is_remote_camera(camera_config):
        pass

    elif utils.is_simple_mjpeg_camera(camera_config):
        _set_additional_config(camera_config, camera_id=camera_id)

    # read the actual configuration from file
    config_file_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {
        'id': camera_id
    }
    if os.path.isfile(config_file_path):
        lines = get_camera(camera_id, as_lines=True)

    else:
        lines = []

    # write the configuration to file
    camera_config_path = os.path.join(settings.CONF_PATH, _CAMERA_CONFIG_FILE_NAME) % {
        'id': camera_id
    }
    logging.debug(f'writing camera config to {camera_config_path}...')

    try:
        f = open(camera_config_path, 'w')

    except Exception as e:
        logging.error(
            f'could not open camera config file {camera_config_path} for writing: {e}'
        )

        raise

    lines = _dict_to_conf(lines, camera_config)

    try:
        f.writelines([utils.make_str(line) + '\n' for line in lines])

    except Exception as e:
        logging.error(f'could not write camera config file {camera_config_path}: {e}')

        raise

    finally:
        f.close()


def invalidate():
    """
    Invalidate all configuration caches.

    Clears main config, camera config, camera IDs, and additional structure caches.
    """
    global _main_config_cache
    global _camera_config_cache
    global _camera_ids_cache

    logging.debug('invalidating config cache')
    _main_config_cache = None
    _camera_config_cache = {}
    _camera_ids_cache = None
    invalidate_additional_structure()


def clear_camera_cache():
    """Clear just the camera config cache."""
    global _camera_ids_cache
    _camera_ids_cache = None
    _camera_config_cache.clear()
