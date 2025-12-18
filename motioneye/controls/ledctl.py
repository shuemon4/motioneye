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
Module: Raspberry Pi 5 LED control via sysfs
Functions: is_supported(), set_leds_disabled()
"""

import logging
import os
import subprocess

from motioneye import config, utils
from motioneye.config import additional_config
from motioneye.controls import pictl

# LED sysfs paths for Raspberry Pi 5
ACT_LED_PATH = '/sys/class/leds/ACT'
PWR_LED_PATH = '/sys/class/leds/PWR'

# Sysfs control files
ACT_TRIGGER = os.path.join(ACT_LED_PATH, 'trigger')
ACT_BRIGHTNESS = os.path.join(ACT_LED_PATH, 'brightness')
PWR_TRIGGER = os.path.join(PWR_LED_PATH, 'trigger')
PWR_BRIGHTNESS = os.path.join(PWR_LED_PATH, 'brightness')


def is_supported() -> bool:
    """
    Check if LED control is supported on this hardware.

    Returns True only if:
    - Running on Raspberry Pi 5
    - sysfs LED control files exist and are accessible
    """
    if not pictl.is_pi5():
        return False

    # Check if all required sysfs paths exist
    required_paths = [ACT_TRIGGER, ACT_BRIGHTNESS, PWR_TRIGGER, PWR_BRIGHTNESS]
    for path in required_paths:
        if not os.path.exists(path):
            logging.debug(f'LED control: sysfs path not found: {path}')
            return False

    return True


def set_leds_disabled(disabled: bool) -> bool:
    """
    Apply LED state change via sysfs.

    Args:
        disabled: True to turn off LEDs, False to restore defaults

    Returns:
        True if successful, False if operation failed
    """
    if not is_supported():
        logging.warning('LED control: feature not supported on this hardware')
        return False

    try:
        if disabled:
            # Turn LEDs off: set trigger to 'none', then brightness to 0
            logging.debug('LED control: disabling LEDs')

            # Activity LED
            _sysfs_write(ACT_TRIGGER, 'none')
            _sysfs_write(ACT_BRIGHTNESS, '0')

            # Power LED
            _sysfs_write(PWR_TRIGGER, 'none')
            _sysfs_write(PWR_BRIGHTNESS, '0')
        else:
            # Turn LEDs on: restore default triggers
            logging.debug('LED control: enabling LEDs')

            # Activity LED
            _sysfs_write(ACT_TRIGGER, 'mmc0')

            # Power LED
            _sysfs_write(PWR_TRIGGER, 'default-on')

        return True

    except Exception as e:
        logging.error(f'LED control: failed to apply LED state: {e}')
        return False


def _sysfs_write(path: str, value: str) -> None:
    """
    Write a value to a sysfs file using sudo tee (for unprivileged access).

    Args:
        path: Full path to sysfs file
        value: Value to write

    Raises:
        RuntimeError if write fails
    """
    cmd = f'echo {value} | sudo tee {path} > /dev/null'
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logging.debug(f'LED control: wrote {value} to {path}')
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'sysfs write failed ({path}): {e.stderr}')


def _get_leds_disabled() -> bool:
    """Get the current LED state from sysfs."""
    # Read actual LED state from sysfs to determine if disabled
    # If trigger is 'none' and brightness is 0, they're disabled
    try:
        with open(ACT_BRIGHTNESS, 'r') as f:
            act_brightness = int(f.read().strip())
        with open(PWR_BRIGHTNESS, 'r') as f:
            pwr_brightness = int(f.read().strip())

        # LEDs are disabled if both brightness values are 0
        return act_brightness == 0 and pwr_brightness == 0
    except Exception as e:
        logging.debug(f'Failed to read LED state from sysfs: {e}')
        return False


def _set_leds_disabled(disabled: bool) -> bool:
    """
    Set the LED state by applying sysfs changes.

    The UI framework automatically persists this via config storage.

    Args:
        disabled: True to turn off LEDs, False to restore defaults

    Returns:
        True if sysfs write succeeded
    """
    return set_leds_disabled(disabled)


@additional_config
def disablePi5Leds():
    """
    Additional config for Pi 5 LED control.

    Returns a config dict for the UI or None if not supported.
    """
    if not is_supported():
        return None

    return {
        'label': 'Disable Raspberry Pi LEDs',
        'description': 'turns off the red power and green activity LEDs immediately (no reboot required)',
        'type': 'bool',
        'section': 'general',
        'get': _get_leds_disabled,
        'set': _set_leds_disabled,
    }
