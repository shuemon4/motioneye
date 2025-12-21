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
Camera preset storage and management.

Provides functions for saving, loading, and managing camera configuration presets.
Presets are stored per-camera in JSON files at /etc/motioneye/camera-{id}-presets.json
"""

import json
import logging
import os
import re
from datetime import datetime

from motioneye import settings

logger = logging.getLogger(__name__)

# Preset file location
PRESET_DIR = settings.CONF_PATH  # /etc/motioneye/

# Settings included in presets
PRESET_SETTINGS = [
    # Autofocus (requires restart)
    'autofocus_mode',
    'autofocus_range',
    'lens_position',

    # Frame rate (requires restart)
    'framerate',

    # Hot-reload settings (apply immediately)
    'brightness',
    'contrast',
    'iso',
    'awb_enable',
    'awb_mode',
    'awb_locked',
    'colour_temp',
    'colour_gain_r',
    'colour_gain_b',

    # Extra options
    'extra_options',
]

HOT_RELOAD_PRESET_SETTINGS = [
    'brightness',
    'contrast',
    'iso',
    'awb_enable',
    'awb_mode',
    'awb_locked',
    'colour_temp',
    'colour_gain_r',
    'colour_gain_b',
]


def _get_preset_file(camera_id):
    """Get the preset file path for a camera."""
    return os.path.join(PRESET_DIR, f'camera-{camera_id}-presets.json')


def _slugify(name):
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug


def _load_preset_file(camera_id):
    """Load presets from file, returning empty structure if not found."""
    filepath = _get_preset_file(camera_id)
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f'Failed to load presets for camera {camera_id}: {e}')

    return {'presets': {}, 'version': 1}


def _save_preset_file(camera_id, data):
    """Save presets to file."""
    filepath = _get_preset_file(camera_id)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        logger.error(f'Failed to save presets for camera {camera_id}: {e}')
        return False


def list_presets(camera_id):
    """List all presets for a camera."""
    data = _load_preset_file(camera_id)
    return [
        {'id': pid, 'name': pdata.get('name', pid), 'modified': pdata.get('modified')}
        for pid, pdata in data.get('presets', {}).items()
    ]


def get_preset(camera_id, preset_id):
    """Get a specific preset by ID."""
    data = _load_preset_file(camera_id)
    return data.get('presets', {}).get(preset_id)


def save_preset(camera_id, name, settings_dict, preset_id=None):
    """
    Save a preset. If preset_id is provided and exists, update it.
    Otherwise create a new preset with a generated ID.

    Returns: (preset_id, created) tuple
    """
    data = _load_preset_file(camera_id)
    now = datetime.utcnow().isoformat() + 'Z'

    if preset_id is None:
        preset_id = _slugify(name)

    # Check if this is a new preset or update
    created = preset_id not in data.get('presets', {})

    if 'presets' not in data:
        data['presets'] = {}

    data['presets'][preset_id] = {
        'name': name,
        'settings': settings_dict,
        'created': data['presets'].get(preset_id, {}).get('created', now),
        'modified': now
    }

    if _save_preset_file(camera_id, data):
        return (preset_id, created)
    return (None, False)


def delete_preset(camera_id, preset_id):
    """Delete a preset by ID. Returns True if deleted."""
    data = _load_preset_file(camera_id)
    if preset_id in data.get('presets', {}):
        del data['presets'][preset_id]
        return _save_preset_file(camera_id, data)
    return False


def rename_preset(camera_id, preset_id, new_name):
    """
    Rename a preset. Updates both the name and the ID (slug).
    Returns: new_preset_id or None if failed
    """
    data = _load_preset_file(camera_id)
    if preset_id not in data.get('presets', {}):
        return None

    new_id = _slugify(new_name)
    if new_id != preset_id and new_id in data['presets']:
        # New ID already exists
        return None

    preset = data['presets'].pop(preset_id)
    preset['name'] = new_name
    preset['modified'] = datetime.utcnow().isoformat() + 'Z'
    data['presets'][new_id] = preset

    if _save_preset_file(camera_id, data):
        return new_id
    return None


def list_all_preset_names():
    """
    List all unique preset names across all cameras.
    Used for global preset discovery.
    """
    all_presets = set()
    try:
        for filename in os.listdir(PRESET_DIR):
            if filename.startswith('camera-') and filename.endswith('-presets.json'):
                filepath = os.path.join(PRESET_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        for pdata in data.get('presets', {}).values():
                            all_presets.add(pdata.get('name', ''))
                except (json.JSONDecodeError, IOError):
                    continue
    except IOError:
        pass

    return sorted(list(all_presets))


def find_preset_by_name(name, exclude_camera_id=None):
    """
    Find a preset by name across all cameras.
    Returns (camera_id, preset_id, preset_data) or None.
    """
    target_slug = _slugify(name)
    try:
        for filename in os.listdir(PRESET_DIR):
            if filename.startswith('camera-') and filename.endswith('-presets.json'):
                # Extract camera ID from filename
                match = re.match(r'camera-(\d+)-presets\.json', filename)
                if not match:
                    continue
                cam_id = int(match.group(1))

                if exclude_camera_id is not None and cam_id == exclude_camera_id:
                    continue

                filepath = os.path.join(PRESET_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        for pid, pdata in data.get('presets', {}).items():
                            if pid == target_slug or _slugify(pdata.get('name', '')) == target_slug:
                                return (cam_id, pid, pdata)
                except (json.JSONDecodeError, IOError):
                    continue
    except IOError:
        pass

    return None
