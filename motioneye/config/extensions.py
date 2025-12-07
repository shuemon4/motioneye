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
Plugin system for additional configuration sections and items.

Provides decorators and functions for registering and retrieving
additional configuration sections and items from plugins/extensions.
"""

import collections
import logging

from motioneye import settings


# Global registries for additional config functions
_additional_section_funcs = []
_additional_config_funcs = []
_additional_structure_cache = {}


def additional_section(func):
    """
    Decorator to register a function that provides an additional config section.

    The decorated function should return a dictionary with section configuration
    or None to skip registration.

    Args:
        func: Function that returns section configuration dict
    """
    _additional_section_funcs.append(func)


def additional_config(func):
    """
    Decorator to register a function that provides an additional config item.

    The decorated function should return a dictionary with config item details
    or None to skip registration.

    Args:
        func: Function that returns config item dict
    """
    _additional_config_funcs.append(func)


def get_additional_structure(camera, separators=False):
    """
    Get the additional configuration structure for main or camera config.

    Collects registered sections and config items, filtering by camera context
    and reboot requirements.

    Args:
        camera: Boolean indicating camera config (True) or main config (False)
        separators: Whether to include separator-type config items

    Returns:
        Tuple of (sections_dict, configs_dict)
    """
    if _additional_structure_cache.get((camera, separators)) is None:
        logging.debug(
            'loading additional config structure for {}, {} separators'.format(
                'camera' if camera else 'main', 'with' if separators else 'without'
            )
        )

        # gather sections
        sections = collections.OrderedDict()
        for func in _additional_section_funcs:
            result = func()
            if not result:
                continue

            if result.get('reboot') and not settings.ENABLE_REBOOT:
                continue

            if bool(result.get('camera')) != bool(camera):
                continue

            result['name'] = func.__name__
            sections[func.__name__] = result

            logging.debug(f"additional config section: {result['name']}")

        configs = collections.OrderedDict()
        for func in _additional_config_funcs:
            result = func()
            if not result:
                continue

            if result.get('reboot') and not settings.ENABLE_REBOOT:
                continue

            if bool(result.get('camera')) != bool(camera):
                continue

            if result['type'] == 'separator' and not separators:
                continue

            result['name'] = func.__name__
            configs[func.__name__] = result

            section = sections.setdefault(result.get('section'), {})
            section.setdefault('configs', []).append(result)

            logging.debug(f"additional config item: {result['name']}")

        _additional_structure_cache[(camera, separators)] = sections, configs

    return _additional_structure_cache[(camera, separators)]


def _get_additional_config(data, camera_id=None):
    """
    Populate data dict with values from additional config getters.

    Args:
        data: Configuration dictionary to populate
        camera_id: Camera ID for camera-specific configs, or None for main config
    """
    args = [camera_id] if camera_id else []

    (sections, configs) = get_additional_structure(camera=bool(camera_id))
    get_funcs = {c.get('get') for c in list(configs.values()) if c.get('get')}
    get_func_values = collections.OrderedDict((f, f(*args)) for f in get_funcs)

    for name, section in list(sections.items()):
        if not section.get('get'):
            continue

        if section.get('get_set_dict'):
            data['@_' + name] = get_func_values.get(section['get'], {}).get(name)

        else:
            data['@_' + name] = get_func_values.get(section['get'])

    for name, config in list(configs.items()):
        if not config.get('get'):
            continue

        if config.get('get_set_dict'):
            data['@_' + name] = get_func_values.get(config['get'], {}).get(name)

        else:
            data['@_' + name] = get_func_values.get(config['get'])


def _set_additional_config(data, camera_id=None):
    """
    Save values from data dict using additional config setters.

    Args:
        data: Configuration dictionary with values to save
        camera_id: Camera ID for camera-specific configs, or None for main config
    """
    args = [camera_id] if camera_id else []

    (sections, configs) = get_additional_structure(camera=bool(camera_id))

    set_func_values = collections.OrderedDict()
    for name, section in list(sections.items()):
        if not section.get('set'):
            continue

        if ('@_' + name) not in data:
            continue

        if section.get('get_set_dict'):
            set_func_values.setdefault(section['set'], {})[name] = data['@_' + name]

        else:
            set_func_values[section['set']] = data['@_' + name]

    for name, config in list(configs.items()):
        if not config.get('set'):
            continue

        if ('@_' + name) not in data:
            continue

        if config.get('get_set_dict'):
            set_func_values.setdefault(config['set'], {})[name] = data['@_' + name]

        else:
            set_func_values[config['set']] = data['@_' + name]

    for func, value in list(set_func_values.items()):
        func(*(args + [value]))


def invalidate_additional_structure():
    """Clear the additional structure cache."""
    _additional_structure_cache.clear()
