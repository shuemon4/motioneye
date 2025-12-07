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
Configuration file format translation.

Handles parsing and writing of Motion .conf file format:
- Converting between Python types and conf file string representations
- Parsing conf files into dictionaries
- Writing dictionaries back to conf file format
"""

import collections
from re import match


def _value_to_python(value):
    """
    Convert a config file string value to Python type.

    Args:
        value: String value from config file

    Returns:
        Converted Python value (bool, int, float, or str)
    """
    value_lower = value.lower()
    if value_lower == 'off':
        return False

    elif value_lower == 'on':
        return True

    try:
        return int(value)

    except ValueError:
        try:
            return float(value)

        except ValueError:
            return value


def _python_to_value(value):
    """
    Convert a Python value to config file string format.

    Args:
        value: Python value (bool, int, float, or str)

    Returns:
        String representation for config file
    """
    if value is True:
        return 'on'

    elif value is False:
        return 'off'

    elif isinstance(value, (int, float)):
        return str(value)

    else:
        return value


def _conf_to_dict(lines, list_names=None, no_convert=None):
    """
    Parse config file lines into a dictionary.

    Args:
        lines: List of config file lines
        list_names: Config keys that can appear multiple times (stored as lists)
        no_convert: Config keys whose values should not be type-converted

    Returns:
        OrderedDict with parsed config values
    """
    if list_names is None:
        list_names = []

    if no_convert is None:
        no_convert = []

    data = collections.OrderedDict()

    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            continue

        _match = match(r'^#\s*(@\w+)\s*(.*)', line)
        if _match:
            name, value = _match.groups()[:2]

        elif line.startswith('#') or line.startswith(';'):  # comment line
            continue

        else:
            parts = line.split(None, 1)
            if len(parts) == 1:  # empty value
                parts.append('')

            (name, value) = parts

            value = value.strip()

        if name not in no_convert:
            value = _value_to_python(value)

        if name in list_names:
            data.setdefault(name, []).append(value)

        else:
            data[name] = value

    return data


def _dict_to_conf(lines, data, list_names=None):
    """
    Write dictionary values to config file format.

    Args:
        lines: Existing config file lines to update
        data: Dictionary of config values to write
        list_names: Config keys that should be written as multiple lines

    Returns:
        List of config file lines
    """
    if list_names is None:
        list_names = []

    conf_lines = []
    remaining = collections.OrderedDict(data)
    processed = set()

    # parse existing lines and replace the values

    for line in lines:
        line = line.strip()
        if len(line) == 0:  # empty line
            conf_lines.append(line)
            continue

        _match = match(r'^#\s*(@\w+)\s*(.*)', line)
        if _match:  # @line
            (name, value) = _match.groups()[:2]

        elif line.startswith('#') or line.startswith(';'):  # simple comment line
            conf_lines.append(line)
            continue

        else:
            parts = line.split(None, 1)
            if len(parts) == 2:
                (name, value) = parts

            else:
                (name, value) = parts[0], ''

        if name in processed:
            continue  # name already processed

        processed.add(name)

        if name in list_names:
            new_value = data.get(name)
            if new_value is not None:
                for v in new_value:
                    if v is None:
                        continue

                    line = name + ' ' + _python_to_value(v)
                    conf_lines.append(line)

            else:
                line = name + ' ' + value
                conf_lines.append(line)

        else:
            new_value = data.get(name)
            if new_value is not None:
                value = _python_to_value(new_value)
                line = name + ' ' + value
                conf_lines.append(line)

        remaining.pop(name, None)

    # add the remaining config values not covered by existing lines
    if len(remaining) and len(lines):
        conf_lines.append('')  # add a blank line

    for name, value in list(remaining.items()):
        if name.startswith('@_'):
            continue  # ignore additional configs

        if name in list_names:
            for v in value:
                if v is None:
                    continue

                line = name + ' ' + _python_to_value(v)
                conf_lines.append(line)

        else:
            line = name + ' ' + _python_to_value(value)
            conf_lines.append(line)

    # build the final config lines
    conf_lines.sort(key=lambda line: not line.startswith('@'))

    lines = []
    for i, line in enumerate(conf_lines):
        # squeeze successive blank lines
        if i > 0 and len(line.strip()) == 0 and len(conf_lines[i - 1].strip()) == 0:
            continue

        if line.startswith('@'):
            line = '# ' + line

        elif i > 0 and conf_lines[i - 1].startswith('@'):
            lines.append('')  # add a blank line between @lines and the rest

        lines.append(line)

    return lines
