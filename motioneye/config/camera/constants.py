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

"""Shared constants for camera configuration converters."""

USED_MOTION_OPTIONS = {
    'auto_brightness',
    'despeckle_filter',
    'camera_name',
    'emulate_motion',
    'event_gap',
    'framerate',
    'height',
    'libcam_device',
    'libcam_buffer_count',
    'lightswitch_percent',
    'locate_motion_mode',
    'locate_motion_style',
    'mask_file',
    'mask_privacy',
    'movie_codec',
    'movie_filename',
    'movie_max_time',
    'movie_output_motion',
    'movie_output',
    'movie_quality',
    'movie_passthrough',
    'minimum_motion_frames',
    'mmalcam_name',
    'netcam_keepalive',
    'netcam_tolerant_check',
    'netcam_url',
    'netcam_use_tcp',
    'netcam_userpass',
    'noise_level',
    'noise_tune',
    'on_event_end',
    'on_event_start',
    'on_movie_end',
    'on_picture_save',
    'picture_filename',
    'picture_output_motion',
    'picture_output',
    'picture_quality',
    'post_capture',
    'pre_capture',
    'rotate',
    'smart_mask_speed',
    'snapshot_filename',
    'snapshot_interval',
    'stream_authentication',
    'stream_auth_method',
    'stream_localhost',
    'stream_maxrate',
    'stream_motion',
    'stream_port',
    'stream_quality',
    'target_dir',
    'text_changes',
    'text_scale',
    'text_left',
    'text_right',
    'threshold',
    'threshold_maximum',
    'threshold_tune',
    'videodevice',
    'vid_control_params',
    'webcontrol_interface',
    'webcontrol_localhost',
    'webcontrol_parms',
    'webcontrol_port',
    'width',
}

# Motion 5.0 new parameters (renamed from 4.x equivalents)
MOTION_50_PARAMS = {
    'device_name',      # Renamed from camera_name
    'movie_container',  # Renamed from movie_codec
}

# Parameters removed in Motion 5.0
MOTION_50_REMOVED_PARAMS = {
    'stream_port',
    'stream_localhost',
    'stream_auth_method',
    'stream_authentication',
    'auto_brightness',
    'setup_mode',
}
