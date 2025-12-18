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
Module: CPU temperature endpoint for Raspberry Pi
Classes: TemperatureHandler

Provides the current CPU temperature for display in the UI header.
Works on Raspberry Pi by reading /sys/class/thermal/thermal_zone0/temp.
"""

import json
import logging
import os

from motioneye.handlers.base import BaseHandler

__all__ = ('TemperatureHandler',)

# Path to thermal zone file on Linux (Raspberry Pi)
THERMAL_ZONE_PATH = '/sys/class/thermal/thermal_zone0/temp'

# Cache temperature for 5 seconds to avoid excessive file reads
_temp_cache = {'value': None, 'timestamp': 0}
CACHE_TTL = 5  # seconds


class TemperatureHandler(BaseHandler):
    """
    Returns the current CPU temperature in JSON format.
    Response: {"temp_c": 45.2, "temp_f": 113.4} or {"error": "..."}
    """

    def compute_etag(self):
        return None

    def get(self):
        import time

        now = time.time()

        # Check cache
        if _temp_cache['value'] is not None and (now - _temp_cache['timestamp']) < CACHE_TTL:
            return self._finish_json(_temp_cache['value'])

        # Try to read temperature
        temp_c = self._read_temperature()

        if temp_c is not None:
            temp_f = (temp_c * 9 / 5) + 32
            result = {
                'temp_c': round(temp_c, 1),
                'temp_f': round(temp_f, 1)
            }
            _temp_cache['value'] = result
            _temp_cache['timestamp'] = now
            return self._finish_json(result)
        else:
            return self._finish_json({'error': 'Temperature not available'})

    def _read_temperature(self):
        """Read CPU temperature from thermal zone file."""
        try:
            if os.path.exists(THERMAL_ZONE_PATH):
                with open(THERMAL_ZONE_PATH, 'r') as f:
                    # Value is in millidegrees Celsius
                    temp_millidegrees = int(f.read().strip())
                    return temp_millidegrees / 1000.0
        except (IOError, ValueError, OSError) as e:
            logging.debug(f'Could not read temperature: {e}')

        return None

    def _finish_json(self, data):
        """Helper to return JSON response."""
        self.set_header('Content-Type', 'application/json')
        self.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        return self.finish(json.dumps(data))
