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
Default configuration values for Motion and camera configs.

Provides functions to set default values for:
- Main motion.conf settings
- Motion camera settings (v4l2, libcamera, mmal, netcam)
- Simple MJPEG camera settings
"""

import os.path

from motioneye import motionctl, settings, utils
from motioneye.controls import pictl


def _set_default_motion(data):
    """
    Set default values for the main motion configuration.

    Args:
        data: Configuration dictionary to set defaults on
    """
    data.setdefault('@enabled', True)

    data.setdefault('@admin_username', 'admin')
    data.setdefault('@admin_password', '')
    data.setdefault('@normal_username', 'user')
    data.setdefault('@normal_password', '')
    data.setdefault('@lang', 'en')

    if not motionctl.is_motion_50():
        data.setdefault('setup_mode', False)
    data.setdefault('webcontrol_port', settings.MOTION_CONTROL_PORT)
    # Motion 5.0 uses string values for webcontrol_interface
    if motionctl.is_motion_50():
        data.setdefault('webcontrol_interface', 'default')
    else:
        data.setdefault('webcontrol_interface', 1)
    data.setdefault('webcontrol_localhost', settings.MOTION_CONTROL_LOCALHOST)
    # the advanced list of parameters will be available
    data.setdefault('webcontrol_parms', 2)


def _set_default_motion_camera(camera_id, data):
    """
    Set default values for a motion camera configuration.

    Handles different camera types: v4l2, libcamera, mmal, netcam.

    Args:
        camera_id: Integer camera ID
        data: Configuration dictionary to set defaults on
    """
    data.setdefault('camera_name', 'Camera' + str(camera_id))
    data.setdefault('@id', camera_id)

    if utils.is_v4l2_camera(data):
        data.setdefault('videodevice', '/dev/video0')
        data.setdefault('vid_control_params', '')
        data.setdefault('width', 352)
        data.setdefault('height', 288)

    elif utils.is_libcamera_device(data):
        # Pi 5 with libcamera
        data.setdefault('libcam_device', 'auto')
        data.setdefault('libcam_buffer_count', 4)
        data.setdefault('width', 1920)
        data.setdefault('height', 1080)
        # Brightness, Contrast, and ISO defaults (hot-reloadable in Motion 5.0+)
        data.setdefault('libcam_brightness', 0.0)  # Neutral brightness
        data.setdefault('libcam_contrast', 1.0)  # Neutral contrast
        data.setdefault('libcam_iso', 100)  # Minimum ISO, least noise
        # AWB defaults for libcamera (stored with @ prefix for UI persistence)
        data.setdefault('@awb_enable', True)   # AWB enabled by default
        data.setdefault('@awb_mode', 0)        # Auto mode
        data.setdefault('@colour_temp', 0)     # 0 = disabled (use AWB)
        data.setdefault('@colour_gain_r', 0.0) # 0 = auto
        data.setdefault('@colour_gain_b', 0.0) # 0 = auto
        # Autofocus defaults for Camera v3 (imx708)
        if data.get('@supports_autofocus'):
            data.setdefault('@af_mode', 2)  # Continuous autofocus
            data.setdefault('@af_range', 0)  # Normal range
            data.setdefault('@lens_position', 0.0)  # Infinity (for manual mode)

    data.setdefault('framerate', 2)
    data.setdefault('rotate', 0)
    data.setdefault('mask_privacy', '')

    data.setdefault('@storage_device', 'custom-path')
    data.setdefault('@network_server', '')
    data.setdefault('@network_share_name', '')
    data.setdefault('@network_smb_ver', '1.0')
    data.setdefault('@network_username', '')
    data.setdefault('@network_password', '')
    data.setdefault(
        'target_dir', os.path.join(settings.MEDIA_PATH, data['camera_name'])
    )
    data.setdefault('@upload_enabled', False)
    data.setdefault('@upload_picture', True)
    data.setdefault('@upload_movie', True)
    data.setdefault('@upload_service', 'ftp')
    data.setdefault('@upload_server', '')
    data.setdefault('@upload_port', '')
    data.setdefault('@upload_method', 'POST')
    data.setdefault('@upload_location', '')
    data.setdefault('@upload_subfolders', True)
    data.setdefault('@upload_username', '')
    data.setdefault('@upload_password', '')
    data.setdefault('@upload_endpoint_url', '')
    data.setdefault('@upload_access_key', '')
    data.setdefault('@upload_secret_key', '')
    data.setdefault('@upload_bucket', '')
    data.setdefault('@clean_cloud_enabled', False)

    # Motion 5.0 removed stream_port, stream_localhost, stream_auth_method
    # Streams are now served via webcontrol interface
    if not motionctl.is_motion_50():
        data.setdefault('stream_localhost', False)
        data.setdefault('stream_port', 9080 + camera_id)
        data.setdefault('stream_auth_method', 0)
    data.setdefault('stream_maxrate', 5)
    data.setdefault('stream_quality', 85)
    data.setdefault('stream_motion', False)

    data.setdefault('@webcam_resolution', 100)
    data.setdefault('@webcam_server_resize', False)

    data.setdefault('text_left', data['camera_name'])
    data.setdefault('text_right', '%Y-%m-%d\\n%T')
    data.setdefault('text_scale', 1)

    data.setdefault('@motion_detection', True)
    data.setdefault('text_changes', False)
    data.setdefault('locate_motion_mode', False)
    data.setdefault('locate_motion_style', 'redbox')

    data.setdefault('threshold', 2000)
    data.setdefault('threshold_maximum', 0)
    data.setdefault('threshold_tune', False)
    data.setdefault('noise_tune', True)
    data.setdefault('noise_level', 32)
    data.setdefault('lightswitch_percent', 0)
    data.setdefault('despeckle_filter', '')
    data.setdefault('minimum_motion_frames', 20)
    data.setdefault('smart_mask_speed', 0)
    data.setdefault('mask_file', '')
    data.setdefault('movie_output_motion', False)
    data.setdefault('picture_output_motion', False)

    data.setdefault('pre_capture', 1)
    data.setdefault('post_capture', 1)

    data.setdefault('picture_output', False)
    data.setdefault('picture_filename', '')
    data.setdefault('emulate_motion', False)
    data.setdefault('event_gap', 30)

    data.setdefault('snapshot_interval', 0)
    data.setdefault('snapshot_filename', '')
    data.setdefault('picture_quality', 85)
    data.setdefault('@preserve_pictures', 0)
    data.setdefault('@manual_snapshots', True)

    data.setdefault('movie_filename', '%Y-%m-%d/%H-%M-%S')
    data.setdefault('movie_max_time', 0)
    data.setdefault('movie_output', False)
    data.setdefault('movie_passthrough', False)

    # Pi 5 has no hardware H.264 encoder - must use software encoding
    # Pi 4 (even with libcamera on Bookworm) still has hardware encoding available
    if pictl.is_pi5():
        data.setdefault('movie_codec', 'mp4')  # will use libx264 (software)

    elif motionctl.has_h264_v4l2m2m_support():
        # Prefer v4l2m2m - works on both Pi 4 Bullseye and Bookworm
        data.setdefault('movie_codec', 'mp4:h264_v4l2m2m')

    elif motionctl.has_h264_omx_support():
        # OMX is deprecated but still works on older setups
        data.setdefault('movie_codec', 'mp4:h264_omx')

    else:
        data.setdefault('movie_codec', 'mp4')  # software fallback

    data.setdefault('movie_quality', 75)  # 75%

    data.setdefault('@preserve_movies', 0)
    data.setdefault('@manual_record', False)

    data.setdefault('@working_schedule', '')
    data.setdefault('@working_schedule_type', 'outside')

    data.setdefault('on_event_start', '')
    data.setdefault('on_event_end', '')
    data.setdefault('on_movie_end', '')
    data.setdefault('on_picture_save', '')


def _set_default_simple_mjpeg_camera(camera_id, data):
    """
    Set default values for a simple MJPEG camera configuration.

    Args:
        camera_id: Integer camera ID
        data: Configuration dictionary to set defaults on
    """
    data.setdefault('camera_name', 'Camera' + str(camera_id))
    data.setdefault('@id', camera_id)
