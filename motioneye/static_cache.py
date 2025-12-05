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
Static file cache module for Pi 5 optimization.

Caches frequently-accessed static files at startup to reduce disk I/O
during request handling.
"""

import logging
import os

from motioneye import settings

# Cache storage
_cache = {}

# Files to cache at startup
_CACHE_FILES = [
    'img/no-preview.svg',
    'img/error.svg',
]


def load_static_files():
    """Load static files into memory cache at startup."""
    global _cache

    _cache = {}
    loaded = 0

    for rel_path in _CACHE_FILES:
        full_path = os.path.join(settings.STATIC_PATH, rel_path)

        if not os.path.exists(full_path):
            logging.debug('static cache: file not found: %s', rel_path)
            continue

        try:
            with open(full_path, 'rb') as f:
                _cache[rel_path] = f.read()
            loaded += 1
            logging.debug('static cache: loaded %s (%d bytes)',
                          rel_path, len(_cache[rel_path]))

        except Exception as e:
            logging.error('static cache: failed to load %s: %s', rel_path, e)

    logging.debug('static cache: loaded %d files', loaded)


def get_static(name):
    """
    Get a static file from cache.

    Args:
        name: Relative path within STATIC_PATH (e.g., 'img/no-preview.svg')

    Returns:
        bytes: File content if cached, None if not found
    """
    return _cache.get(name)


def get_static_or_read(name):
    """
    Get a static file from cache, falling back to disk read.

    Args:
        name: Relative path within STATIC_PATH (e.g., 'img/no-preview.svg')

    Returns:
        bytes: File content from cache or disk
    """
    # Try cache first
    content = _cache.get(name)
    if content is not None:
        return content

    # Fallback to disk read
    full_path = os.path.join(settings.STATIC_PATH, name)
    try:
        with open(full_path, 'rb') as f:
            return f.read()

    except Exception as e:
        logging.error('static cache: failed to read %s: %s', name, e)
        return None
