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
Backup and restore operations for configuration.

Provides functions to create tar.gz backups of configuration files
and restore them, with optional system reboot on restore.
"""

import datetime
import glob
import logging
import os.path
import subprocess

from tornado.ioloop import IOLoop

from motioneye import settings, utils
from motioneye.controls.powerctl import PowerControl


def backup():
    """
    Create a backup of configuration files.

    For system-wide config directories (>100 files), performs selective backup
    of motion.conf and camera-*.conf files only.
    For motion-specific directories, performs full backup.

    Returns:
        Bytes content of tar.gz backup, or None on failure
    """
    logging.debug('generating config backup file')

    if len(os.listdir(settings.CONF_PATH)) > 100:
        logging.debug(
            f'config path "{settings.CONF_PATH}" appears to be a system-wide config directory, performing a selective backup'
        )

        cmd = ['tar', 'zc', 'motion.conf']
        cmd += list(
            map(
                os.path.basename,
                glob.glob(os.path.join(settings.CONF_PATH, 'camera-*.conf')),
            )
        )
        try:
            content = utils.call_subprocess(cmd, cwd=settings.CONF_PATH, encoding=None)
            logging.debug(f'backup file created ({len(content)} bytes)')

            return content

        except Exception as e:
            logging.error(f'backup failed: {e}', exc_info=True)

            return None

    else:
        logging.debug(
            f'config path "{settings.CONF_PATH}" appears to be a motion-specific config directory, performing a full backup'
        )

        try:
            content = utils.call_subprocess(
                ['tar', 'zc', '.'], cwd=settings.CONF_PATH, encoding=None
            )
            logging.debug(f'backup file created ({len(content)} bytes)')

            return content

        except Exception as e:
            logging.error(f'backup failed: {e}', exc_info=True)

            return None


def restore(content, invalidate_func=None):
    """
    Restore configuration from a backup file.

    Extracts the tar.gz backup to the config directory and optionally
    reboots the system or invalidates the config cache.

    Args:
        content: Bytes content of tar.gz backup
        invalidate_func: Function to call to invalidate config cache
                        (required if ENABLE_REBOOT is False)

    Returns:
        Dict with 'reboot' key indicating if reboot was triggered,
        False on extraction failure, or None on exception
    """
    logging.info('restoring config from backup file')

    cmd = ['tar', 'zxC', settings.CONF_PATH]

    try:
        p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        msg = p.communicate(content)[0]
        if msg:
            logging.error(f'failed to restore configuration: {msg}')
            return False

        logging.debug('configuration restored successfully')

        if settings.ENABLE_REBOOT:

            def later():
                PowerControl.reboot()

            io_loop = IOLoop.current()
            io_loop.add_timeout(datetime.timedelta(seconds=2), later)

        else:
            if invalidate_func:
                invalidate_func()

        return {'reboot': settings.ENABLE_REBOOT}

    except Exception as e:
        logging.error(f'failed to restore configuration: {e}', exc_info=True)

        return None
