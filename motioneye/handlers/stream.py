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
Module: MJPEG stream handler
Functions: StreamHandler
"""

import logging
import time

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.web import RequestHandler

from motioneye import config, motionctl, settings, utils, mjpgclient


class StreamHandler(RequestHandler):
    """Serves MJPEG streams from cameras"""

    def get(self):
        """Stream MJPEG to web UI"""
        try:
            camera_id = int(self.get_argument('id'))
        except (ValueError, TypeError):
            self.set_status(400)
            self.finish('Invalid camera id')
            return

        # Check if camera exists and is enabled
        try:
            camera_config = config.get_camera(camera_id)
        except Exception:
            self.set_status(404)
            self.finish('Camera not found')
            return

        if not camera_config.get('@enabled'):
            self.set_status(403)
            self.finish('Camera is disabled')
            return

        # Only local motion cameras can be streamed
        if not utils.is_local_motion_camera(camera_config):
            self.set_status(400)
            self.finish('Camera is not a local motion camera')
            return

        # Get the MJPEG data from the mjpgclient
        # Wait up to 5 seconds for the first frame
        jpg_data = None
        for attempt in range(50):  # 50 * 0.1s = 5 seconds
            jpg_data = mjpgclient.get_jpg(camera_id)
            if jpg_data is not None:
                break
            time.sleep(0.1)

        if jpg_data is None:
            self.set_status(503)
            self.finish('Camera stream not available')
            return

        # Set response headers for MJPEG streaming
        self.set_header('Content-Type', 'multipart/x-mixed-replace; boundary=--BoundaryString')
        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Connection', 'keep-alive')
        self.set_header('Pragma', 'no-cache')

        # Send MJPEG header and data
        boundary = '--BoundaryString\r\n'
        self.write(boundary.encode())
        self.write(b'Content-Type: image/jpeg\r\n')
        self.write(b'Content-Length: ' + str(len(jpg_data)).encode() + b'\r\n\r\n')
        self.write(jpg_data)
        self.write(b'\r\n')
        self.finish()
