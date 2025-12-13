# Copyright (c) 2020 Vlsarro
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
Module: Camera status endpoint for direct streaming mode
Classes: StatusHandler

This handler provides a lightweight JSON endpoint for polling camera status
(motion detection, FPS, monitor info) when using direct MJPEG streaming mode.
"""

import logging

from motioneye import config, mjpgclient, monitor, motionctl, remote
from motioneye.handlers.base import BaseHandler

__all__ = ('StatusHandler',)


class StatusHandler(BaseHandler):
    """
    Lightweight status endpoint for direct streaming mode.
    Returns JSON with motion detection state, capture FPS, and monitor info.
    """

    def compute_etag(self):
        return None

    async def get(self, camera_id):
        camera_id = int(camera_id)
        camera_config = config.get_camera(camera_id)

        if not camera_config:
            logging.error(f'status: camera {camera_id} not found')
            return self.finish_json({'error': 'camera not found'})

        if camera_config.get('@proto') == 'netcam' and camera_config.get('@remote'):
            # Remote camera - fetch status from remote server
            resp = await remote.get_current_picture(
                camera_config,
                width=1,  # Minimal size, we just want status
                height=1,
            )
            if resp is None:
                return self.finish_json({
                    'motion_detected': False,
                    'capture_fps': 0,
                    'monitor_info': '',
                    'error': 'remote camera unavailable'
                })

            return self.finish_json({
                'motion_detected': resp.motion_detected,
                'capture_fps': resp.capture_fps,
                'monitor_info': resp.monitor_info or ''
            })

        # Local camera
        return self.finish_json({
            'motion_detected': motionctl.is_motion_detected(camera_id),
            'capture_fps': mjpgclient.get_fps(camera_id),
            'monitor_info': monitor.get_monitor_info(camera_id)
        })

    def finish_json(self, data):
        """Helper to return JSON response"""
        import json
        self.set_header('Content-Type', 'application/json')
        self.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        return self.finish(json.dumps(data))
