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
    'despeckle_filter',
    'camera_name',
    'emulate_motion',
    'event_gap',
    'framerate',
    'height',
    'libcam_device',
    'libcam_buffer_count',
    'libcam_brightness',
    'libcam_contrast',
    'libcam_iso',
    'libcam_control_item',
    'libcam_awb_enable',
    'libcam_awb_mode',
    'libcam_awb_locked',
    'libcam_colour_temp',
    'libcam_colour_gain_r',
    'libcam_colour_gain_b',
    'libcam_af_mode',
    'libcam_af_range',
    'libcam_af_speed',
    'libcam_lens_position',
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

# Parameters that can be updated at runtime without daemon restart (Motion 5.0+)
HOT_RELOAD_PARAMS = {
    # Motion Detection (Tier 1 - most frequently adjusted)
    'threshold',
    'threshold_maximum',
    'threshold_tune',
    'noise_level',
    'noise_tune',
    'despeckle_filter',
    'minimum_motion_frames',
    'event_gap',
    'lightswitch_percent',
    'lightswitch_frames',
    'static_object_time',
    'smart_mask_speed',
    'emulate_motion',

    # Text Overlays (Tier 2)
    'text_left',
    'text_right',
    'text_scale',
    'text_changes',
    'text_event',
    'locate_motion_mode',
    'locate_motion_style',

    # Event Handlers (Tier 3)
    'on_event_start',
    'on_event_end',
    'on_motion_detected',
    'on_movie_start',
    'on_movie_end',
    'on_picture_save',
    'on_action_user',
    'on_area_detected',
    'on_camera_found',
    'on_camera_lost',
    'on_secondary_detect',

    # Capture Control
    'pre_capture',
    'post_capture',
    'snapshot_interval',

    # Picture Output
    'picture_output',
    'picture_output_motion',
    'picture_quality',
    'picture_exif',
    'picture_filename',

    # Movie Settings (runtime adjustable)
    'movie_filename',
    'movie_bps',
    'movie_quality',
    'movie_max_time',
    'movie_extpipe_use',
    'movie_extpipe',

    # Timelapse
    'timelapse_interval',
    'timelapse_mode',
    'timelapse_fps',
    'timelapse_container',
    'timelapse_filename',

    # Secondary Detection
    'secondary_interval',
    'secondary_method',
    'secondary_params',

    # Streaming (safe subset)
    'stream_preview_scale',
    'stream_preview_newline',
    'stream_preview_method',
    'stream_preview_pps',
    'stream_quality',
    'stream_grey',
    'stream_motion',
    'stream_maxrate',
    'stream_limit',

    # Device Settings (safe subset)
    'device_name',
    'target_dir',
    'watchdog_tmo',
    'watchdog_kill',
    'pause',

    # PTZ Control
    'ptz_auto_track',
    'ptz_wait',
    'ptz_move_track',
    'ptz_pan_left',
    'ptz_pan_right',
    'ptz_tilt_up',
    'ptz_tilt_down',
    'ptz_zoom_in',
    'ptz_zoom_out',

    # SQL Database
    'sql_event_start',
    'sql_event_end',
    'sql_movie_start',
    'sql_movie_end',
    'sql_pic_save',

    # libcamera Controls (Pi Camera v3, Motion 5.0+)
    'libcam_brightness',
    'libcam_contrast',
    'libcam_iso',
    'libcam_awb_enable',
    'libcam_awb_mode',
    'libcam_awb_locked',
    'libcam_colour_temp',
    'libcam_colour_gain_r',
    'libcam_colour_gain_b',
    # Autofocus controls (Motion 5.0+ hot-reloadable)
    'libcam_af_mode',       # 0=Manual, 1=Auto, 2=Continuous
    'libcam_lens_position', # 0.0-15.0 dioptres
    'libcam_af_range',      # 0=Normal, 1=Macro, 2=Full
    'libcam_af_speed',      # 0=Normal, 1=Fast
    'libcam_af_trigger',    # 0=Start, 1=Cancel (action, not persistent)
}

# Parameters that always require daemon restart
RESTART_REQUIRED_PARAMS = {
    # System
    'daemon', 'pid_file', 'log_level', 'log_file', 'log_type_str',

    # Device
    'libcam_device', 'libcam_options', 'v4l2_device', 'v4l2_params',
    'netcam_url', 'netcam_params', 'netcam_high_url', 'netcam_userpass',

    # Resolution
    'width', 'height', 'framerate', 'rotate', 'flip_axis',

    # Webcontrol
    'webcontrol_port', 'webcontrol_ipv6', 'webcontrol_localhost',
    'webcontrol_parms', 'webcontrol_interface', 'webcontrol_auth_method',
    'webcontrol_authentication', 'webcontrol_tls', 'webcontrol_cert',
    'webcontrol_key', 'webcontrol_header_params', 'webcontrol_cors_header',

    # Streaming
    'stream_port', 'stream_localhost', 'stream_tls',
    'stream_cors_header', 'stream_authentication',

    # Recording
    'movie_output', 'movie_output_motion', 'movie_container',
    'movie_codec', 'movie_passthrough', 'movie_retain',

    # Database
    'database_type', 'database_dbname', 'database_host',
    'database_port', 'database_user', 'database_password',
    'database_busy_timeout',

    # Masks (file-based)
    'mask_file', 'mask_privacy',

    # Audio
    'sound_device', 'sound_params', 'sound_trigger',
    'sound_alerts', 'sound_window', 'sound_show', 'sound_file',

    # Pipes
    'video_pipe', 'video_pipe_motion', 'extpipe_use', 'extpipe',
}

# Maps Motion supportedControls keys to MotionEye UI element IDs
# Used by frontend to determine which controls to show/hide based on camera capabilities
CAPABILITY_TO_UI_ELEMENT = {
    'AfMode': ['autofocusModeSelect', 'autofocusRangeSelect', 'autofocusSpeedSelect'],
    'LensPosition': ['lensPositionSlider'],
    'AfTrigger': ['triggerAutofocusButton'],
    'AfRange': ['autofocusRangeSelect'],
    'AfSpeed': ['autofocusSpeedSelect'],
    'AwbEnable': ['awbEnableSwitch', 'awbModeSelect', 'awbLockedSwitch'],
    'ColourTemperature': ['colourTempSlider'],
    'ColourGains': ['colourGainRSlider', 'colourGainBSlider'],
    'Brightness': ['brightnessSlider'],
    'Contrast': ['contrastSlider'],
    'AnalogueGain': ['isoSlider'],
}
