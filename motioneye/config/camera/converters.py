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
import os
import re
import subprocess
from errno import EEXIST
from re import match, sub
from shlex import split

from motioneye import meyectl, motionctl, settings, utils
from motioneye.controls import diskctl, smbctl, v4l2ctl

from .constants import USED_MOTION_OPTIONS


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


def motion_camera_ui_to_dict(
    ui,
    prev_config=None,
    *,
    get_main_func,
    task_scheduler=None,
    translate=lambda x: x,
):
    """
    Convert camera UI config to Motion config dict.

    Args:
        ui: UI configuration dictionary
        prev_config: Previous configuration to merge with
        get_main_func: Function to get main configuration
        task_scheduler: Optional callback for scheduling async tasks
        translate: Translation function for localized messages (gettext)

    Returns:
        Updated configuration dictionary
    """
    prev_config = dict(prev_config or {})
    main_config = get_main_func()  # needed for surveillance password

    # regex definitions for input sanity checks in backend
    # they must match the ones in motioneye/static/js/main.js
    deviceNameValidRegExp = '^[A-Za-z0-9-_+ ]+$'
    deviceNameFailMessage = translate(
        'Device names are only allowed to contain alphanumerical characters, hyphen -, underscore _, plus +, and space'
    )
    filenameValidRegExp = '^([A-Za-z0-9 ()/._-]|%[CYmdHMSqv])+$'
    filenameFailMessage = translate(
        'File names are only allowed to contain alphanumerical characters, parenthesis (), forward slash /, dot ., '
        'underscore _, hyphen -, space, and a subset of motion conversion specifiers: %C %Y %m %d %H %M %S %q %v'
    )
    dirnameValidRegExp = '^[A-Za-z0-9 ()/._-]+$'
    dirnameFailMessage = translate(
        'Directory names are only allowed to contain alphanumerical characters, space, parenthesis (), forward slash /, '
        'dot ., underscore _, and hyphen -'
    )
    emailValidRegExp = '^[A-Za-z0-9 _+.@^~<>,-]+$'
    emailFailMessage = translate(
        'Email addresses are only allowed to contain alphanumerical characters, underscore _, plus +, dot ., at @, '
        'caret ^, tilde ~, angle brackets <>, hyphen -, and may be separated by comma, and space'
    )
    webHookUrlValidRegExp = '^[^;\']+$'
    webHookUrlFailMessage = translate(
        'URLs are not allowed to contain caret ^, semicolon ;, or apostrophe \''
    )

    data = {
        # device
        'camera_name': input_sanity_check(
            deviceNameValidRegExp, ui['name'], 'camera_name', deviceNameFailMessage
        ),
        '@enabled': ui['enabled'],
        'auto_brightness': ui['auto_brightness'],
        'framerate': int(ui['framerate']),
        'rotate': int(ui['rotation']),
        'mask_privacy': '',
        # file storage
        '@storage_device': ui['storage_device'],
        '@network_server': ui['network_server'],
        '@network_share_name': ui['network_share_name'],
        '@network_smb_ver': ui['network_smb_ver'],
        '@network_username': ui['network_username'],
        '@network_password': ui['network_password'],
        '@upload_enabled': ui['upload_enabled'],
        '@upload_movie': ui['upload_movie'],
        '@upload_picture': ui['upload_picture'],
        '@upload_service': ui['upload_service'],
        '@upload_server': ui['upload_server'],
        '@upload_port': ui['upload_port'],
        '@upload_method': ui['upload_method'],
        '@upload_location': ui['upload_location'],
        '@upload_subfolders': ui['upload_subfolders'],
        '@upload_username': ui['upload_username'],
        '@upload_password': ui['upload_password'],
        '@upload_endpoint_url': ui['upload_endpoint_url'],
        '@upload_access_key': ui['upload_access_key'],
        '@upload_secret_key': ui['upload_secret_key'],
        '@upload_bucket': ui['upload_bucket'],
        '@clean_cloud_enabled': ui['clean_cloud_enabled'],
        # text overlay
        'text_left': '',
        'text_right': '',
        'text_scale': ui['text_scale'],
        # streaming
        'stream_localhost': not ui['video_streaming'],
        'stream_port': int(ui['streaming_port']),
        'stream_maxrate': int(ui['streaming_framerate']),
        'stream_quality': max(1, int(ui['streaming_quality'])),
        '@webcam_resolution': max(1, int(ui['streaming_resolution'])),
        '@webcam_server_resize': ui['streaming_server_resize'],
        '@streaming_direct_mode': ui.get('streaming_direct_mode', True),
        'stream_motion': ui['streaming_motion'],
        'stream_auth_method': {'disabled': 0, 'basic': 1, 'digest': 2}.get(
            ui['streaming_auth_mode'], 0
        ),
        'stream_authentication': main_config['@normal_username']
        + ':'
        + main_config['@normal_password'],
        '@lang': main_config['@lang'],
        # still images
        'picture_output': False,
        'snapshot_interval': 0,
        'picture_filename': '',
        'snapshot_filename': '',
        'picture_quality': max(1, int(ui['image_quality'])),
        '@preserve_pictures': int(ui['preserve_pictures']),
        '@manual_snapshots': ui['manual_snapshots'],
        # movies
        'movie_output': False,
        'movie_passthrough': bool(ui['movie_passthrough']),
        'movie_filename': input_sanity_check(
            filenameValidRegExp,
            ui['movie_file_name'],
            'movie_filename',
            filenameFailMessage,
        ),
        'movie_max_time': ui['max_movie_length'],
        '@preserve_movies': int(ui['preserve_movies']),
        # motion detection
        '@motion_detection': ui['motion_detection'],
        'emulate_motion': False,
        'text_changes': ui['show_frame_changes'],
        'locate_motion_mode': ui['show_frame_changes'],
        'threshold_maximum': ui['max_frame_change_threshold'],
        'threshold_tune': ui['auto_threshold_tuning'],
        'noise_tune': ui['auto_noise_detect'],
        'noise_level': max(1, round(int(ui['noise_level']) * 2.55)),
        'lightswitch_percent': ui['light_switch_detect'],
        'event_gap': int(ui['event_gap']),
        'pre_capture': int(ui['pre_capture']),
        'post_capture': int(ui['post_capture']),
        'minimum_motion_frames': int(ui['minimum_motion_frames']),
        'smart_mask_speed': 0,
        'mask_file': '',
        'picture_output_motion': ui['create_debug_media'],
        'movie_output_motion': ui['create_debug_media'],
        # working schedule
        '@working_schedule': '',
        # events
        'on_event_start': '',
        'on_event_end': '',
        'on_movie_end': '',
        'on_picture_save': '',
    }

    if utils.is_v4l2_camera(prev_config):
        proto = 'v4l2'

    elif utils.is_libcamera_device(prev_config):
        proto = 'libcamera'

    elif utils.is_mmal_camera(prev_config):
        proto = 'mmal'

    else:
        proto = 'netcam'

    if proto in ('v4l2', 'mmal', 'libcamera'):
        # leave videodevice unchanged

        # resolution
        if not ui['resolution']:
            ui['resolution'] = '320x240'

        width = int(ui['resolution'].split('x')[0])
        height = int(ui['resolution'].split('x')[1])
        data['width'] = width
        data['height'] = height

        threshold = int(float(ui['frame_change_threshold']) * width * height / 100)

        if proto == 'v4l2':
            # video controls
            vid_control_params = (
                ('{}={}'.format(n, c['value']))
                for n, c in list(ui['video_controls'].items())
            )
            data['vid_control_params'] = ','.join(vid_control_params)

        elif proto == 'libcamera':
            # libcamera buffer count
            data['libcam_buffer_count'] = ui.get('libcam_buffer_count', 4)

            # Autofocus control parameters for Camera v3
            if ui.get('supports_autofocus'):
                af_mode = ui.get('autofocus_mode', 2)
                af_range = ui.get('autofocus_range', 0)
                lens_pos = ui.get('lens_position', 0.0)

                # Store for UI persistence
                data['@supports_autofocus'] = True
                data['@af_mode'] = af_mode
                data['@af_range'] = af_range
                data['@lens_position'] = lens_pos

                # Generate libcam_control_item entries for motion.conf
                # Motion accepts multiple libcam_control_item directives
                control_items = [f'AfMode={af_mode}', f'AfRange={af_range}']
                if af_mode == 0:  # Manual focus mode
                    control_items.append(f'LensPosition={lens_pos}')

                # Motion uses separate libcam_control_item for each control
                data['libcam_control_item'] = control_items

    else:  # assuming netcam
        if match(
            r'^rtsp|^rtmp', data.get('netcam_url', prev_config.get('netcam_url', ''))
        ):
            # motion uses the configured width and height for RTSP/RTMP cameras
            width = int(ui['resolution'].split('x')[0])
            height = int(ui['resolution'].split('x')[1])
            data['width'] = width
            data['height'] = height

            threshold = int(float(ui['frame_change_threshold']) * width * height / 100)

        else:  # width & height are not available for other netcams
            threshold = int(float(ui['frame_change_threshold']) * 640 * 480 / 100)

    data['threshold'] = threshold

    if ui['privacy_mask']:
        capture_width, capture_height = data.get('width'), data.get('height')
        if data.get('rotate') in [90, 270]:
            capture_width, capture_height = capture_height, capture_width

        data['mask_privacy'] = utils.build_editable_mask_file(
            prev_config['@id'],
            'privacy',
            ui['privacy_mask_lines'],
            capture_width,
            capture_height,
        )

    data['target_dir'] = input_sanity_check(
        dirnameValidRegExp, ui['root_directory'], 'target_dir', dirnameFailMessage
    )

    if (ui['storage_device'] == 'network-share') and settings.SMB_SHARES:
        mount_point = smbctl.make_mount_point(
            ui['network_server'], ui['network_share_name'], ui['network_username']
        )
        if ui['root_directory'].startswith('/'):
            ui['root_directory'] = ui['root_directory'][1:]
        data['target_dir'] = os.path.normpath(
            os.path.join(mount_point, ui['root_directory'])
        )

    elif ui['storage_device'].startswith('local-disk'):
        target_dev = ui['storage_device'][10:].replace('-', '/')
        mounted_partitions = diskctl.list_mounted_partitions()
        partition = mounted_partitions[target_dev]
        mount_point = partition['mount_point']

        if ui['root_directory'].startswith('/'):
            ui['root_directory'] = ui['root_directory'][1:]
        data['target_dir'] = os.path.normpath(
            os.path.join(mount_point, ui['root_directory'])
        )

    # try to create the target dir
    try:
        os.makedirs(data['target_dir'])
        logging.debug(
            f'created root directory {data["target_dir"]} for camera {data["camera_name"]}'
        )

    except OSError as e:
        if isinstance(e, OSError) and e.errno == EEXIST:
            pass  # already exists, things should be just fine

        else:
            logging.error(
                f'failed to create root directory "{data["target_dir"]}": {e}',
                exc_info=True,
            )

    if ui['upload_enabled'] and '@id' in prev_config:
        upload_settings = {
            k[7:]: ui[k] for k in list(ui.keys()) if k.startswith('upload_')
        }

        if task_scheduler:
            task_scheduler(
                0,
                uploadservices.update,
                tag=f"uploadservices.update({ui['upload_service']})",
                camera_id=prev_config['@id'],
                service_name=ui['upload_service'],
                settings=upload_settings,
            )

    if ui['text_overlay']:
        left_text = ui['left_text']
        if left_text == 'camera-name':
            data['text_left'] = ui['name']

        elif left_text == 'timestamp':
            data['text_left'] = '%Y-%m-%d\\n%T'

        elif left_text == 'disabled':
            data['text_left'] = ''

        else:
            data['text_left'] = ui['custom_left_text']

        right_text = ui['right_text']
        if right_text == 'camera-name':
            data['text_right'] = ui['name']

        elif right_text == 'timestamp':
            data['text_right'] = '%Y-%m-%d\\n%T'

        elif right_text == 'disabled':
            data['text_right'] = ''

        else:
            data['text_right'] = ui['custom_right_text']

    if ui['still_images']:
        data['picture_filename'] = input_sanity_check(
            filenameValidRegExp,
            ui['image_file_name'],
            'picture_filename',
            filenameFailMessage,
        )
        # script aborts if above sanity check failed, hence no need to check again
        data['snapshot_filename'] = ui['image_file_name']

        capture_mode = ui['capture_mode']
        if capture_mode == 'motion-triggered':
            data['picture_output'] = True

        elif capture_mode == 'motion-triggered-one':
            data['picture_output'] = 'best'

        elif capture_mode == 'interval-snapshots':
            data['snapshot_interval'] = int(ui['snapshot_interval'])

        elif capture_mode == 'all-frames':
            data['picture_output'] = True
            data['emulate_motion'] = True

        elif capture_mode == 'manual':
            data['picture_output'] = False
            data['emulate_motion'] = False

    if ui['movies']:
        data['movie_output'] = True
        recording_mode = ui['recording_mode']
        if recording_mode == 'motion-triggered':
            data['emulate_motion'] = False

        elif recording_mode == 'continuous':
            data['emulate_motion'] = True

    data['movie_codec'] = ui['movie_format']
    q = int(ui['movie_quality'])

    data['movie_quality'] = max(1, q)

    # motion detection

    if ui['despeckle_filter']:
        data['despeckle_filter'] = prev_config['despeckle_filter'] or 'EedDl'

    else:
        data['despeckle_filter'] = ''

    if ui['motion_mask']:
        if ui['motion_mask_type'] == 'smart':
            data['smart_mask_speed'] = 11 - int(ui['smart_mask_sluggishness'])

        elif ui['motion_mask_type'] == 'editable':
            capture_width, capture_height = data.get('width'), data.get('height')
            if data.get('rotate') in [90, 270]:
                capture_width, capture_height = capture_height, capture_width

            data['mask_file'] = utils.build_editable_mask_file(
                prev_config['@id'],
                'motion',
                ui['motion_mask_lines'],
                capture_width,
                capture_height,
            )

    # working schedule
    if ui['working_schedule']:
        data['@working_schedule'] = (
            ui['monday_from']
            + '-'
            + ui['monday_to']
            + '|'
            + ui['tuesday_from']
            + '-'
            + ui['tuesday_to']
            + '|'
            + ui['wednesday_from']
            + '-'
            + ui['wednesday_to']
            + '|'
            + ui['thursday_from']
            + '-'
            + ui['thursday_to']
            + '|'
            + ui['friday_from']
            + '-'
            + ui['friday_to']
            + '|'
            + ui['saturday_from']
            + '-'
            + ui['saturday_to']
            + '|'
            + ui['sunday_from']
            + '-'
            + ui['sunday_to']
        )

        data['@working_schedule_type'] = ui['working_schedule_type']

    # event start
    on_event_start = [f"{meyectl.find_command('relayevent')} start %t"]
    if ui['email_notifications_enabled']:
        emails = sub(
            '\\s',
            '',
            input_sanity_check(
                emailValidRegExp,
                ui['email_notifications_addresses'],
                'email_notifications_addresses',
                emailFailMessage,
            ),
        )

        line = (
            "%(script)s '%(server)s' '%(port)s' '%(account)s' '%(password)s' '%(tls)s' '%(from)s' '%(to)s' "
            "'motion_start' '%%t' '%%Y-%%m-%%dT%%H:%%M:%%S' '%(timespan)s'"
            % {
                'script': meyectl.find_command('sendmail'),
                'server': ui['email_notifications_smtp_server'],
                'port': ui['email_notifications_smtp_port'],
                'account': ui['email_notifications_smtp_account'],
                'password': ui['email_notifications_smtp_password']
                .replace(';', '\\;')
                .replace('%', '%%'),
                'tls': ui['email_notifications_smtp_tls'],
                'from': input_sanity_check(
                    emailValidRegExp,
                    ui['email_notifications_from'],
                    'email_notifications_from',
                    emailFailMessage,
                ),
                'to': emails,
                'timespan': ui['email_notifications_picture_time_span'],
            }
        )

        on_event_start.append(line)
    if ui['telegram_notifications_enabled']:
        line = (
            "%(script)s '%(api)s' '%(chatid)s' '%%t' '%%Y-%%m-%%dT%%H:%%M:%%S' '%(timespan)s'"
            % {
                'script': meyectl.find_command('sendtelegram'),
                'api': ui['telegram_notifications_api'],
                'chatid': ui['telegram_notifications_chat_id'],
                'timespan': ui['telegram_notifications_picture_time_span'],
            }
        )

        on_event_start.append(line)

    if ui['web_hook_notifications_enabled']:
        url = sub(
            '\\s',
            '+',
            input_sanity_check(
                webHookUrlValidRegExp,
                ui['web_hook_notifications_url'],
                'web_hook_notifications_url',
                webHookUrlFailMessage,
            ),
        )

        on_event_start.append(
            "{script} '{method}' '{url}'".format(
                script=meyectl.find_command('webhook'),
                method=ui['web_hook_notifications_http_method'],
                url=url,
            )
        )

    if ui['command_notifications_enabled']:
        on_event_start += utils.split_semicolon(ui['command_notifications_exec'])

    data['on_event_start'] = '; '.join(on_event_start)

    # event end
    on_event_end = [f"{meyectl.find_command('relayevent')} stop %t"]

    if ui['web_hook_end_notifications_enabled']:
        url = sub(
            r'\s',
            '+',
            input_sanity_check(
                webHookUrlValidRegExp,
                ui['web_hook_end_notifications_url'],
                'web_hook_end_notifications_url',
                webHookUrlFailMessage,
            ),
        )

        on_event_end.append(
            "%(script)s '%(method)s' '%(url)s'"
            % {
                'script': meyectl.find_command('webhook'),
                'method': ui['web_hook_end_notifications_http_method'],
                'url': url,
            }
        )

    if ui['command_end_notifications_enabled']:
        on_event_end += utils.split_semicolon(ui['command_end_notifications_exec'])

    data['on_event_end'] = '; '.join(on_event_end)

    # movie end
    on_movie_end = [f"{meyectl.find_command('relayevent')} movie_end %t %f"]

    if ui['web_hook_storage_enabled']:
        url = sub('\\s', '+', ui['web_hook_storage_url'])

        on_movie_end.append(
            "{script} '{method}' '{url}'".format(
                script=meyectl.find_command('webhook'),
                method=ui['web_hook_storage_http_method'],
                url=url,
            )
        )

    if ui['command_storage_enabled']:
        on_movie_end += utils.split_semicolon(ui['command_storage_exec'])

    data['on_movie_end'] = '; '.join(on_movie_end)

    # picture save
    on_picture_save = [f"{meyectl.find_command('relayevent')} picture_save %t %f"]

    if ui['web_hook_storage_enabled']:
        url = sub('\\s', '+', ui['web_hook_storage_url'])

        on_picture_save.append(
            "{script} '{method}' '{url}'".format(
                script=meyectl.find_command('webhook'),
                method=ui['web_hook_storage_http_method'],
                url=url,
            )
        )

    if ui['command_storage_enabled']:
        on_picture_save += utils.split_semicolon(ui['command_storage_exec'])

    data['on_picture_save'] = '; '.join(on_picture_save)

    # additional configs
    for name, value in list(ui.items()):
        if not name.startswith('_'):
            continue

        data['@' + name] = value

    # extra motion options
    for name in list(prev_config.keys()):
        if name not in USED_MOTION_OPTIONS and not name.startswith('@'):
            prev_config.pop(name)

    extra_options = ui.get('extra_options', [])
    for name, value in extra_options:
        data[name] = value or ''

    prev_config.update(data)

    return prev_config


def motion_camera_dict_to_ui(
    data,
    *,
    get_action_commands_func,
):
    """
    Convert Motion config dict to camera UI format.

    Args:
        data: Motion configuration dictionary
        get_action_commands_func: Function to get action commands for camera

    Returns:
        UI configuration dictionary
    """
    ui = {
        # device
        'name': data['camera_name'],
        'enabled': data['@enabled'],
        'id': data['@id'],
        'auto_brightness': data.get('auto_brightness', False),  # Removed in Motion 5.0
        'framerate': int(data['framerate']),
        'rotation': int(data['rotate']),
        'privacy_mask': False,
        'privacy_mask_lines': [],
        # file storage
        'smb_shares': settings.SMB_SHARES,
        'storage_device': data['@storage_device'],
        'network_server': data['@network_server'],
        'network_share_name': data['@network_share_name'],
        'network_smb_ver': data['@network_smb_ver'],
        'network_username': data['@network_username'],
        'network_password': data['@network_password'],
        'disk_used': 0,
        'disk_total': 0,
        'available_disks': diskctl.list_mounted_disks(),
        'upload_enabled': data['@upload_enabled'],
        'upload_picture': data['@upload_picture'],
        'upload_movie': data['@upload_movie'],
        'upload_service': data['@upload_service'],
        'upload_server': data['@upload_server'],
        'upload_port': data['@upload_port'],
        'upload_method': data['@upload_method'],
        'upload_location': data['@upload_location'],
        'upload_subfolders': data['@upload_subfolders'],
        'upload_username': data['@upload_username'],
        'upload_password': data['@upload_password'],
        'upload_authorization_key': '',  # needed, otherwise the field is hidden
        'upload_endpoint_url': data['@upload_endpoint_url'],
        'upload_access_key': data['@upload_access_key'],
        'upload_secret_key': data['@upload_secret_key'],
        'upload_bucket': data['@upload_bucket'],
        'clean_cloud_enabled': data['@clean_cloud_enabled'],
        'web_hook_storage_enabled': False,
        'command_storage_enabled': False,
        # text overlay
        'text_overlay': False,
        'left_text': 'camera-name',
        'right_text': 'timestamp',
        'custom_left_text': '',
        'custom_right_text': '',
        # streaming (many options removed in Motion 5.0)
        'video_streaming': not data.get('stream_localhost', False),
        'streaming_framerate': int(data.get('stream_maxrate', 1)),
        'streaming_quality': int(data.get('stream_quality', 85)),
        'streaming_resolution': int(data['@webcam_resolution']),
        'streaming_server_resize': data['@webcam_server_resize'],
        'streaming_direct_mode': data.get('@streaming_direct_mode', True),
        'streaming_port': int(data.get('stream_port', 8081)),
        'streaming_auth_mode': {0: 'disabled', 1: 'basic', 2: 'digest'}.get(
            data.get('stream_auth_method'), 'disabled'
        ),
        'streaming_motion': int(data.get('stream_motion', 0)),
        # still images
        'still_images': False,
        'capture_mode': 'motion-triggered',
        'image_file_name': '%Y-%m-%d/%H-%M-%S',
        'image_quality': data['picture_quality'],
        'snapshot_interval': 0,
        'preserve_pictures': data['@preserve_pictures'],
        'manual_snapshots': data['@manual_snapshots'],
        # movies
        'movies': False,
        'recording_mode': 'motion-triggered',
        'movie_file_name': data['movie_filename'],
        'max_movie_length': data['movie_max_time'],
        'preserve_movies': data['@preserve_movies'],
        'movie_passthrough': data['movie_passthrough'],
        # motion detection
        'motion_detection': data['@motion_detection'],
        'show_frame_changes': data['text_changes'] or data['locate_motion_mode'],
        'auto_noise_detect': data['noise_tune'],
        'max_frame_change_threshold': data['threshold_maximum'],
        'auto_threshold_tuning': data['threshold_tune'],
        'noise_level': round(int(data['noise_level']) / 2.55),
        'light_switch_detect': data['lightswitch_percent'],
        'despeckle_filter': data['despeckle_filter'],
        'event_gap': int(data['event_gap']),
        'pre_capture': int(data['pre_capture']),
        'post_capture': int(data['post_capture']),
        'minimum_motion_frames': int(data['minimum_motion_frames']),
        'motion_mask': False,
        'motion_mask_type': 'smart',
        'smart_mask_sluggishness': 5,
        'motion_mask_lines': [],
        'create_debug_media': data['movie_output_motion']
        or data['picture_output_motion'],
        # motion notifications
        'email_notifications_enabled': False,
        'telegram_notifications_enabled': False,
        'web_hook_notifications_enabled': False,
        'web_hook_end_notifications_enabled': False,
        'command_notifications_enabled': False,
        'command_end_notifications_enabled': False,
        # working schedule
        'working_schedule': False,
        'working_schedule_type': 'during',
        'monday_from': '',
        'monday_to': '',
        'tuesday_from': '',
        'tuesday_to': '',
        'wednesday_from': '',
        'wednesday_to': '',
        'thursday_from': '',
        'thursday_to': '',
        'friday_from': '',
        'friday_to': '',
        'saturday_from': '',
        'saturday_to': '',
        'sunday_from': '',
        'sunday_to': '',
    }

    if utils.is_net_camera(data):
        ui['device_url'] = data['netcam_url']
        ui['proto'] = 'netcam'

        # resolutions
        if match(r'^rtsp|^rtmp', data['netcam_url']):
            # motion uses the configured width and height for RTSP/RTMP cameras
            resolutions = utils.COMMON_RESOLUTIONS
            resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]
            ui['available_resolutions'] = [
                (str(w) + 'x' + str(h)) for (w, h) in resolutions
            ]
            ui['resolution'] = str(data['width']) + 'x' + str(data['height'])

            threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])

        else:  # width & height are not available for other netcams
            # we have no other choice but use something like 640x480 as reference
            threshold = data['threshold'] * 100.0 / (640 * 480)

    elif utils.is_libcamera_device(data):
        ui['device_url'] = data['libcam_device']
        ui['proto'] = 'libcamera'
        ui['libcam_buffer_count'] = data.get('libcam_buffer_count', 4)

        # Autofocus controls for Camera v3 (imx708)
        # Check stored flag first, then detect dynamically for existing cameras
        supports_af = data.get('@supports_autofocus')
        if supports_af is None:
            # Detect autofocus support dynamically from libcamera device
            from motioneye.controls import rpicamctl
            device_id = data.get('libcam_device', 'camera0')
            props = rpicamctl.get_camera_properties(device_id)
            if props:
                supports_af = props.get('supports_autofocus', False)

        if supports_af:
            ui['autofocus_mode'] = data.get('@af_mode', 2)
            ui['autofocus_range'] = data.get('@af_range', 0)
            ui['lens_position'] = data.get('@lens_position', 0.0)
            ui['supports_autofocus'] = True

        resolutions = utils.COMMON_RESOLUTIONS
        resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]
        ui['available_resolutions'] = [
            (str(w) + 'x' + str(h)) for (w, h) in resolutions
        ]
        ui['resolution'] = str(data['width']) + 'x' + str(data['height'])

        threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])

    elif utils.is_mmal_camera(data):
        ui['device_url'] = data['mmalcam_name']
        ui['proto'] = 'mmal'

        resolutions = utils.COMMON_RESOLUTIONS
        resolutions = [r for r in resolutions if motionctl.resolution_is_valid(*r)]
        ui['available_resolutions'] = [
            (str(w) + 'x' + str(h)) for (w, h) in resolutions
        ]
        ui['resolution'] = str(data['width']) + 'x' + str(data['height'])

        threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])

    else:  # assuming v4l2
        ui['device_url'] = data['videodevice']
        ui['proto'] = 'v4l2'

        # resolutions
        resolutions = v4l2ctl.list_resolutions(data['videodevice'])
        ui['available_resolutions'] = [
            (str(w) + 'x' + str(h)) for (w, h) in resolutions
        ]
        ui['resolution'] = str(data['width']) + 'x' + str(data['height'])

        video_controls = v4l2ctl.list_ctrls(data['videodevice'])
        video_controls = [
            (n, c)
            for (n, c) in list(video_controls.items())
            if 'min' in c and 'max' in c and 'value' in c
        ]

        vid_control_params = data['vid_control_params'].split(',')
        vid_control_values = {}
        for param in vid_control_params:
            parts = param.split('=')
            if len(parts) == 1:
                name, value = param, 1

            elif len(parts) == 2:
                name, value = parts

            else:
                continue  # ignore any other kind of param

            vid_control_values[name] = value

        ui['video_controls'] = {
            n: {
                'min': int(c['min']),
                'max': int(c['max']),
                'step': int(c['step']) if 'step' in c else None,
                'value': int(vid_control_values.get(n, c['value'])),
            }
            for n, c in video_controls
        }

        threshold = data['threshold'] * 100.0 / (data['width'] * data['height'])

    ui['frame_change_threshold'] = threshold

    if (data['@storage_device'] == 'network-share') and settings.SMB_SHARES:
        mount_point = smbctl.make_mount_point(
            data['@network_server'],
            data['@network_share_name'],
            data['@network_username'],
        )

        ui['root_directory'] = data['target_dir'][len(mount_point) :] or '/'

    elif data['@storage_device'].startswith('local-disk'):
        target_dev = data['@storage_device'][10:].replace('-', '/')
        mounted_partitions = diskctl.list_mounted_partitions()
        for partition in list(mounted_partitions.values()):
            if partition['target'] == target_dev and data['target_dir'].startswith(
                partition['mount_point']
            ):
                ui['root_directory'] = (
                    data['target_dir'][len(partition['mount_point']) :] or '/'
                )
                break

        else:  # not found for some reason
            logging.error(
                f'could not find mounted partition for device "{target_dev}" and target dir "{data["target_dir"]}"'
            )

            ui['root_directory'] = data['target_dir']

    else:
        ui['root_directory'] = data['target_dir']

    # disk usage
    usage = None
    if os.path.exists(data['target_dir']):
        usage = utils.get_disk_usage(data['target_dir'])
    if usage:
        ui['disk_used'], ui['disk_total'] = usage

    ui['text_scale'] = data['text_scale']
    text_left = data['text_left']
    text_right = data['text_right']
    if text_left or text_right:
        ui['text_overlay'] = True

        if text_left == data['camera_name']:
            ui['left_text'] = 'camera-name'

        elif text_left == '%Y-%m-%d\\n%T':
            ui['left_text'] = 'timestamp'

        elif text_left == '':
            ui['left_text'] = 'disabled'

        else:
            ui['left_text'] = 'custom-text'
            ui['custom_left_text'] = text_left

        if text_right == data['camera_name']:
            ui['right_text'] = 'camera-name'

        elif text_right == '%Y-%m-%d\\n%T':
            ui['right_text'] = 'timestamp'

        elif text_right == '':
            ui['right_text'] = 'disabled'

        else:
            ui['right_text'] = 'custom-text'
            ui['custom_right_text'] = text_right

    emulate_motion = data['emulate_motion']
    picture_output = data['picture_output']
    picture_filename = data['picture_filename']
    snapshot_interval = data['snapshot_interval']
    snapshot_filename = data['snapshot_filename']

    ui['still_images'] = bool(snapshot_filename) or bool(picture_filename)

    if emulate_motion:
        ui['capture_mode'] = 'all-frames'
        if picture_filename:
            ui['image_file_name'] = picture_filename

    elif snapshot_interval:
        ui['capture_mode'] = 'interval-snapshots'
        ui['snapshot_interval'] = snapshot_interval
        if snapshot_filename:
            ui['image_file_name'] = snapshot_filename

    elif picture_output:
        if picture_output == 'best':
            ui['capture_mode'] = 'motion-triggered-one'

        else:
            ui['capture_mode'] = 'motion-triggered'

        if picture_filename:
            ui['image_file_name'] = picture_filename

    else:  # assuming manual
        ui['capture_mode'] = 'manual'
        if snapshot_filename:
            ui['image_file_name'] = snapshot_filename

    if data['movie_output']:
        ui['movies'] = True

    if emulate_motion:
        ui['recording_mode'] = 'continuous'

    else:
        ui['recording_mode'] = 'motion-triggered'

    ui['movie_format'] = data['movie_codec']
    ui['movie_quality'] = data['movie_quality']

    # masks
    if data['mask_file']:
        ui['motion_mask'] = True
        ui['motion_mask_type'] = 'editable'

        capture_width, capture_height = data.get('width'), data.get('height')
        if int(data.get('rotate')) in [90, 270]:
            capture_width, capture_height = capture_height, capture_width

        ui['motion_mask_lines'] = utils.parse_editable_mask_file(
            data['@id'], 'motion', capture_width, capture_height
        )

    elif data['smart_mask_speed']:
        ui['motion_mask'] = True
        ui['motion_mask_type'] = 'smart'
        ui['smart_mask_sluggishness'] = 11 - data['smart_mask_speed']

    if data['mask_privacy']:
        ui['privacy_mask'] = True

        capture_width, capture_height = data.get('width'), data.get('height')
        if int(data.get('rotate')) in [90, 270]:
            capture_width, capture_height = capture_height, capture_width

        ui['privacy_mask_lines'] = utils.parse_editable_mask_file(
            data['@id'], 'privacy', capture_width, capture_height
        )

    # working schedule
    working_schedule = data['@working_schedule']
    if working_schedule:
        days = working_schedule.split('|')
        ui['working_schedule'] = True
        ui['monday_from'], ui['monday_to'] = days[0].split('-')
        ui['tuesday_from'], ui['tuesday_to'] = days[1].split('-')
        ui['wednesday_from'], ui['wednesday_to'] = days[2].split('-')
        ui['thursday_from'], ui['thursday_to'] = days[3].split('-')
        ui['friday_from'], ui['friday_to'] = days[4].split('-')
        ui['saturday_from'], ui['saturday_to'] = days[5].split('-')
        ui['sunday_from'], ui['sunday_to'] = days[6].split('-')
        ui['working_schedule_type'] = data['@working_schedule_type']

    # event start
    on_event_start = data.get('on_event_start') or []
    if on_event_start:
        on_event_start = utils.split_semicolon(on_event_start)

    ui['email_notifications_picture_time_span'] = 0
    ui['telegram_notifications_picture_time_span'] = 0
    command_notifications = []
    for e in on_event_start:
        if ' sendmail ' in e:
            e = split(e)

            if len(e) < 10:
                continue

            if len(e) < 16:
                # backwards compatibility with older configs lacking "from" field
                e.insert(-5, '')

            ui['email_notifications_enabled'] = True
            ui['email_notifications_smtp_server'] = e[-11]
            ui['email_notifications_smtp_port'] = e[-10]
            ui['email_notifications_smtp_account'] = e[-9]
            ui['email_notifications_smtp_password'] = (
                e[-8].replace('\\;', ';').replace('%%', '%')
            )
            ui['email_notifications_smtp_tls'] = e[-7].lower() == 'true'
            ui['email_notifications_from'] = e[-6]
            ui['email_notifications_addresses'] = e[-5]
            try:
                ui['email_notifications_picture_time_span'] = int(e[-1])

            except (TypeError, ValueError):
                ui['email_notifications_picture_time_span'] = 0

        elif ' sendtelegram ' in e:
            e = split(e)

            if len(e) < 6:
                continue

            ui['telegram_notifications_enabled'] = True
            ui['telegram_notifications_api'] = e[-5]
            ui['telegram_notifications_chat_id'] = e[-4]
            try:
                ui['telegram_notifications_picture_time_span'] = int(e[-1])

            except (TypeError, ValueError):
                ui['telegram_notifications_picture_time_span'] = 0

        elif ' webhook ' in e:
            e = split(e)

            if len(e) < 3:
                continue

            ui['web_hook_notifications_enabled'] = True
            ui['web_hook_notifications_http_method'] = e[-2]
            ui['web_hook_notifications_url'] = e[-1]

        elif 'relayevent' in e:
            continue  # ignore internal relay script

        else:  # custom command
            command_notifications.append(e)

    if command_notifications:
        ui['command_notifications_enabled'] = True
        ui['command_notifications_exec'] = '; '.join(command_notifications)

    # event end
    on_event_end = data.get('on_event_end') or []
    if on_event_end:
        on_event_end = utils.split_semicolon(on_event_end)

    command_end_notifications = []
    for e in on_event_end:
        if ' webhook ' in e:
            e = split(e)

            if len(e) < 3:
                continue

            ui['web_hook_end_notifications_enabled'] = True
            ui['web_hook_end_notifications_http_method'] = e[-2]
            ui['web_hook_end_notifications_url'] = e[-1]

        elif 'relayevent' in e or 'eventrelay.py' in e:
            continue  # ignore internal relay script

        else:  # custom command
            command_end_notifications.append(e)

    if command_end_notifications:
        ui['command_end_notifications_enabled'] = True
        ui['command_end_notifications_exec'] = '; '.join(command_end_notifications)

    # movie end
    on_movie_end = data.get('on_movie_end') or []
    if on_movie_end:
        on_movie_end = utils.split_semicolon(on_movie_end)

    command_storage = []
    for e in on_movie_end:
        if ' webhook ' in e:
            e = split(e)

            if len(e) < 3:
                continue

            ui['web_hook_storage_enabled'] = True
            ui['web_hook_storage_http_method'] = e[-2]
            ui['web_hook_storage_url'] = e[-1]

        elif 'relayevent' in e:
            continue  # ignore internal relay script

        else:  # custom command
            command_storage.append(e)

    if command_storage:
        ui['command_storage_enabled'] = True
        ui['command_storage_exec'] = '; '.join(command_storage)

    # additional configs
    for name, value in list(data.items()):
        if not name.startswith('@_'):
            continue

        ui[name[1:]] = value

    # extra motion options
    extra_options = []
    for name, value in list(data.items()):
        if name not in USED_MOTION_OPTIONS and not name.startswith('@'):
            if isinstance(value, bool):
                # boolean values should be transferred as on/off
                value = ['off', 'on'][value]

            extra_options.append((name, value))

    ui['extra_options'] = extra_options

    # action commands
    action_commands = get_action_commands_func(data)
    ui['actions'] = list(action_commands.keys())

    return ui


# Validation regex patterns used by motion camera converters
# These must match the ones in motioneye/static/js/main.js
DEVICE_NAME_REGEX = r'^[A-Za-z0-9-_+ ]+$'
FILENAME_REGEX = r'^([A-Za-z0-9 ()/._-]|%[CYmdHMSqv])+$'
DIRNAME_REGEX = r'^[A-Za-z0-9 ()/._-]+$'
EMAIL_REGEX = r'^[A-Za-z0-9 _+.@^~<>,-]+$'
WEBHOOK_URL_REGEX = r"^[^;']+$"


# Mapping from UI parameter names to Motion parameter names
UI_TO_MOTION_PARAMS = {
    'frame_change_threshold': 'threshold',
    'max_frame_change_threshold': 'threshold_maximum',
    'auto_threshold_tuning': 'threshold_tune',
    'noise_level': 'noise_level',
    'auto_noise_detect': 'noise_tune',
    'despeckle_filter': 'despeckle_filter',
    'minimum_motion_frames': 'minimum_motion_frames',
    'event_gap': 'event_gap',
    'light_switch_detect': 'lightswitch_percent',
    'text_scale': 'text_scale',
    'streaming_framerate': 'stream_maxrate',
    'streaming_quality': 'stream_quality',
    'streaming_motion': 'stream_motion',
    'image_quality': 'picture_quality',
    'movie_quality': 'movie_quality',
    'movie_file_name': 'movie_filename',
    'max_movie_length': 'movie_max_time',
    'pre_capture': 'pre_capture',
    'post_capture': 'post_capture',
    'snapshot_interval': 'snapshot_interval',
    # Parameters that require restart
    'resolution': ['width', 'height'],  # Special: maps to two params
    'rotation': 'rotate',
    'movie_format': 'movie_codec',
    'streaming_port': 'stream_port',
}


def ui_param_requires_restart(ui_param: str) -> bool:
    """
    Check if a UI parameter change will require daemon restart.

    Args:
        ui_param: The UI parameter name (from frontend)

    Returns:
        True if changing this parameter requires restart
    """
    from motioneye.config.camera.constants import RESTART_REQUIRED_PARAMS, HOT_RELOAD_PARAMS

    motion_param = UI_TO_MOTION_PARAMS.get(ui_param)

    if motion_param is None:
        # Unknown mapping - assume restart needed for safety
        return True

    if isinstance(motion_param, list):
        # Multiple Motion params - restart if any require it
        return any(p in RESTART_REQUIRED_PARAMS or p not in HOT_RELOAD_PARAMS for p in motion_param)

    return motion_param in RESTART_REQUIRED_PARAMS or motion_param not in HOT_RELOAD_PARAMS
