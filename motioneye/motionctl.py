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
Module: Motion daemon control and management
Functions: find_motion(), start(), stop(), restart(), check_enable_disable(), check_disabled(), make_movie_preview(), invalidate_movie_preview(), get_motion_detection(), set_motion_detection(), take_snapshot(), has_h264_omx_support(), resolution_is_valid()
"""

import errno
import json
import logging
import os.path
import re
import signal
import subprocess
import time
import urllib.parse
from shlex import quote

from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.ioloop import IOLoop

from motioneye import mediafiles, settings, update, utils
from motioneye.controls.powerctl import PowerControl

_MOTION_CONTROL_TIMEOUT = 5

_started = False
_motion_binary_cache = None
_motion_detected = {}

# CSRF token cache for Motion 5.0+ security
_csrf_token_cache = {
    'token': None,
    'timestamp': None,
    'port': None,
    'csrf_supported': None  # None = unknown, True = has CSRF, False = no CSRF
}

# Camera capabilities cache (camera_id -> supportedControls dict)
_camera_capabilities_cache = {}


def find_motion():
    global _motion_binary_cache
    if _motion_binary_cache:
        return _motion_binary_cache

    # binary
    if settings.MOTION_BINARY:
        if os.path.exists(settings.MOTION_BINARY):
            binary = settings.MOTION_BINARY

        else:
            return None, None

    else:  # autodetect motion binary path
        try:
            binary = utils.call_subprocess(['which', 'motion'])

        except subprocess.CalledProcessError:  # not found
            return None, None

    # version
    try:
        output = utils.call_subprocess(quote(binary) + ' -h || true', shell=True)

    except subprocess.CalledProcessError as e:  # not found as
        logging.error(f'motion version could not be found: {e}')
        return None, None

    result = re.findall('motion Version ([^,]+)', output, re.IGNORECASE)
    version = result and result[0] or ''

    logging.debug(f'found motion executable "{binary}" version "{version}"')

    _motion_binary_cache = (binary, version)

    return _motion_binary_cache


def invalidate_capabilities_cache():
    """Called when Motion restarts to clear cached capabilities."""
    global _camera_capabilities_cache
    _camera_capabilities_cache = {}


def start(deferred=False):
    from motioneye import config, mjpgclient

    if deferred:
        io_loop = IOLoop.current()
        io_loop.add_callback(start, deferred=False)

    global _started

    _started = True

    enabled_local_motion_cameras = config.get_enabled_local_motion_cameras()
    if running() or not enabled_local_motion_cameras:
        return

    logging.debug('searching motion executable')

    binary, version = find_motion()
    if not binary:
        raise Exception('motion executable could not be found')

    logging.debug(f'starting motion executable "{binary}" version "{version}"')

    motion_cfg_path = os.path.join(settings.CONF_PATH, 'motion.conf')
    motion_log_path = os.path.join(settings.LOG_PATH, 'motion.log')
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')

    args = [binary, '-n', '-c', motion_cfg_path, '-d']

    if settings.LOG_LEVEL <= logging.DEBUG:
        args.append('9')

    elif settings.LOG_LEVEL <= logging.WARN:
        args.append('5')

    elif settings.LOG_LEVEL <= logging.ERROR:
        args.append('4')

    else:  # fatal, quiet
        args.append('1')

    log_file = open(motion_log_path, 'w')

    process = subprocess.Popen(
        args, stdout=log_file, stderr=log_file, close_fds=True, cwd=settings.CONF_PATH
    )

    # wait 2 seconds to see that the process has successfully started
    for _ in range(20):
        time.sleep(0.1)
        exit_code = process.poll()
        if exit_code is not None and exit_code != 0:
            raise Exception(f'motion failed to start with exit code "{exit_code}"')

    pid = process.pid

    # write the pid to file
    with open(motion_pid_path, 'w') as f:
        f.write(str(pid) + '\n')

    IOLoop.current().spawn_callback(_disable_initial_motion_detection)

    # if mjpg client idle timeout is disabled, create mjpg clients for all cameras by default
    if not settings.MJPG_CLIENT_IDLE_TIMEOUT:
        logging.debug('creating default mjpg clients for local cameras')
        for camera in enabled_local_motion_cameras:
            mjpgclient.get_jpg(camera['@id'])


def stop(invalidate=False):
    from motioneye import mjpgclient

    global _started, _csrf_token_cache

    _started = False

    # Invalidate camera capabilities cache since Motion will be restarted
    invalidate_capabilities_cache()

    # Invalidate CSRF token cache since Motion will generate a new token on restart
    _csrf_token_cache = {
        'token': None,
        'timestamp': None,
        'port': None,
        'csrf_supported': None
    }

    if not running():
        return

    logging.debug('stopping motion')

    mjpgclient.close_all(invalidate=invalidate)

    pid = _get_pid()
    if pid is not None:
        try:
            # send the TERM signal once
            os.kill(pid, signal.SIGTERM)

            # wait 5 seconds for the process to exit
            for i in range(50):  # @UnusedVariable
                os.waitpid(pid, os.WNOHANG)
                time.sleep(0.1)

            # send the KILL signal once
            os.kill(pid, signal.SIGKILL)

            # wait 2 seconds for the process to exit
            for i in range(20):  # @UnusedVariable
                time.sleep(0.1)
                os.waitpid(pid, os.WNOHANG)

            # the process still did not exit
            if settings.ENABLE_REBOOT:
                logging.error('could not terminate the motion process')
                PowerControl.reboot()

            else:
                raise Exception('could not terminate the motion process')

        except OSError as e:
            if e.errno not in (errno.ESRCH, errno.ECHILD):
                raise


def running():
    pid = _get_pid()
    if pid is None:
        return False

    try:
        os.waitpid(pid, os.WNOHANG)
        os.kill(pid, 0)

        # the process is running
        return True

    except OSError as e:
        if e.errno not in (errno.ESRCH, errno.ECHILD):
            raise

    return False


def started():
    return _started


async def get_motion_detection(camera_id) -> utils.GetMotionDetectionResult:
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        error = f'could not find motion camera id for camera with id {camera_id}'
        logging.error(error)
        return utils.GetMotionDetectionResult(None, error=error)

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/status'

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        return utils.GetMotionDetectionResult(None, error=utils.pretty_http_error(resp))

    resp_body = resp.body.decode('utf-8')
    enabled = bool(resp_body.lower().count('active'))

    logging.debug(
        f"motion detection is {['disabled', 'enabled'][enabled]} for camera with id {id}"
    )

    return utils.GetMotionDetectionResult(enabled, None)


async def get_camera_capabilities(camera_id: int) -> dict:
    """
    Fetch camera capabilities from Motion's /status.json endpoint.

    Args:
        camera_id: MotionEye camera ID

    Returns:
        dict with supportedControls map, or empty dict if unavailable
    """
    global _camera_capabilities_cache

    # Return cached value if available
    if camera_id in _camera_capabilities_cache:
        return _camera_capabilities_cache[camera_id]

    if not running():
        return {}

    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return {}

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/0/status.json'

    try:
        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )
        resp = await AsyncHTTPClient().fetch(request, raise_error=False)

        if resp.code != 200:
            logging.warning(f'status.json returned HTTP {resp.code}')
            return {}

        data = json.loads(resp.body.decode('utf-8'))
        cam_key = f'cam{motion_camera_id}'
        logging.info(f'Capability discovery: looking for {cam_key} in status response')

        if cam_key in data.get('status', {}):
            capabilities = data['status'][cam_key].get('supportedControls', {})
            _camera_capabilities_cache[camera_id] = capabilities
            logging.info(f'Camera {camera_id}: discovered {len(capabilities)} capabilities')
            return capabilities

        logging.warning(f'Camera {camera_id}: {cam_key} not found in status response')
        return {}

    except Exception as e:
        logging.warning(f'Failed to fetch camera capabilities: {e}')
        return {}


async def set_motion_detection(camera_id, enabled):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    if not enabled:
        _motion_detected[camera_id] = False

    # Motion 5.0 command: pause_off = start detection, pause_on = stop detection
    command = 'pause_off' if enabled else 'pause_on'
    endpoint = 'start' if enabled else 'pause'
    action = 'enable' if enabled else 'disable'

    logging.debug(f"{action}ing motion detection for camera with id {camera_id}")

    # Legacy URL for non-CSRF Motion
    url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{endpoint}"

    try:
        resp = await _make_motion_request(url, command=command, camid=motion_camera_id)

        if resp.code in [200, 302]:
            logging.debug(f"successfully {action}d motion detection for camera with id {camera_id}")
        else:
            logging.error(f'failed to {action} motion detection for camera {camera_id}: HTTP {resp.code}')

    except Exception as e:
        logging.error(f'failed to {action} motion detection for camera {camera_id}: {e}')


async def take_snapshot(camera_id):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    logging.debug(f'taking snapshot for camera with id {camera_id}')

    # Legacy URL for non-CSRF Motion
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'

    try:
        resp = await _make_motion_request(url, command='snapshot', camid=motion_camera_id)

        if resp.code in [200, 302]:
            logging.debug(f'successfully took snapshot for camera with id {camera_id}')
        else:
            logging.error(f'failed to take snapshot for camera {camera_id}: HTTP {resp.code}')

    except Exception as e:
        logging.error(f'failed to take snapshot for camera {camera_id}: {e}')


def is_motion_detected(camera_id):
    return _motion_detected.get(camera_id, False)


def set_motion_detected(camera_id, motion_detected):
    if motion_detected:
        logging.debug(f'marking motion detected for camera with id {camera_id}')

    else:
        logging.debug(f'clearing motion detected for camera with id {camera_id}')

    _motion_detected[camera_id] = motion_detected


def camera_id_to_motion_camera_id(camera_id):
    from motioneye import config

    # find the corresponding motion camera_id
    # (which can be different from camera_id)

    main_config = config.get_main()
    cameras = main_config.get('camera', [])

    camera_filename = f'camera-{camera_id}.conf'
    for i, camera in enumerate(cameras):
        if camera != camera_filename:
            continue

        return i + 1

    return None


def motion_camera_id_to_camera_id(motion_camera_id):
    from motioneye import config

    main_config = config.get_main()
    cameras = main_config.get('camera', [])

    try:
        return int(
            re.search(r'camera-(\d+).conf', cameras[int(motion_camera_id) - 1]).group(1)
        )

    except IndexError:
        return None


def is_motion_pre42():
    binary, version = find_motion()
    if not binary:
        return False

    return update.compare_versions(version, '4.2') < 0


def is_motion_post43():
    binary, version = find_motion()
    if not binary:
        return False

    return update.compare_versions(version, '4.4') >= 0  # 4.3.2 > 4.3


def is_motion_50():
    """Check if Motion version is 5.0 or later."""
    binary, version = find_motion()
    if not binary:
        return False
    return update.compare_versions(version, '5.0') >= 0


def validate_motion_version():
    """Ensure Motion 5.0+ is installed. Call at startup."""
    if not is_motion_50():
        raise RuntimeError(
            "Motion 5.0+ is required. Please upgrade Motion or use an older MotionEye version."
        )


def detect_platform():
    """
    Detect if running on Raspberry Pi and which model.

    Returns:
        str: Platform identifier
            - 'pi5': Raspberry Pi 5
            - 'pi4': Raspberry Pi 4
            - 'pi': Generic Raspberry Pi (older models)
            - 'arm_unknown': ARM architecture but not confirmed Pi
            - 'generic': x86_64 or other architecture
    """
    # Layer 1: Device tree (most reliable for Pi)
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip('\x00')
            if 'Raspberry Pi' in model:
                if 'Pi 5' in model:
                    return 'pi5'
                elif 'Pi 4' in model:
                    return 'pi4'
                return 'pi'
    except (FileNotFoundError, IOError):
        pass

    # Layer 2: /proc/cpuinfo (fallback)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'Model' in line and 'Raspberry Pi' in line:
                    if 'Pi 5' in line:
                        return 'pi5'
                    elif 'Pi 4' in line:
                        return 'pi4'
                    return 'pi'
    except (FileNotFoundError, IOError):
        pass

    # Layer 3: Architecture hints
    import platform

    machine = platform.machine()
    if machine in ('aarch64', 'armv7l', 'armv8'):
        return 'arm_unknown'

    return 'generic'


def is_raspberry_pi():
    """
    Check if running on Raspberry Pi hardware.

    Returns:
        bool: True if confirmed Raspberry Pi, False otherwise
    """
    platform_type = detect_platform()
    return platform_type in ('pi5', 'pi4', 'pi')


def has_h264_v4l2m2m_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_v4l2m2m' in codecs.get('h264', {}).get('encoders', set())


def has_h264_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvenc' in codecs.get('h264', {}).get('encoders', set())


def has_h264_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_nvmpi' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_nvmpi_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvmpi' in codecs.get('hevc', {}).get('encoders', set())


def has_hevc_nvenc_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_nvenc' in codecs.get('hevc', {}).get('encoders', set())


def has_h264_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'h264_qsv' in codecs.get('h264', {}).get('encoders', set())


def has_hevc_qsv_support():
    binary, version, codecs = mediafiles.find_ffmpeg()
    if not binary:
        return False

    # TODO also check for motion codec parameter support

    return 'hevc_qsv' in codecs.get('hevc', {}).get('encoders', set())


def resolution_is_valid(width, height):
    # width & height must be be modulo 8

    if width % 8:
        return False

    if height % 8:
        return False

    return True


async def _disable_initial_motion_detection():
    from motioneye import config

    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        if not camera_config['@motion_detection']:
            logging.debug(
                f'motion detection disabled by config for camera with id {camera_id}'
            )
            await set_motion_detection(camera_id, False)


def _get_pid():
    motion_pid_path = os.path.join(settings.RUN_PATH, 'motion.pid')

    # read the pid from file
    try:
        with open(motion_pid_path) as f:
            return int(f.readline().strip())

    except (OSError, ValueError):
        return None


async def _get_csrf_token(force_refresh: bool = False) -> str:
    """
    Retrieve CSRF token from Motion web interface, with caching.

    Args:
        force_refresh: If True, bypass cache and fetch new token

    Returns:
        64-character hexadecimal CSRF token, or None if CSRF not supported
    """
    global _csrf_token_cache

    # Check if we already know CSRF is not supported
    if _csrf_token_cache.get('csrf_supported') is False and not force_refresh:
        return None

    # Check cache validity
    if not force_refresh:
        cached_token = _csrf_token_cache.get('token')
        cached_port = _csrf_token_cache.get('port')

        if cached_token and cached_port == settings.MOTION_CONTROL_PORT:
            logging.debug(f'Using cached CSRF token: {cached_token[:16]}...')
            return cached_token

    # Fetch Motion homepage
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'

    try:
        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )
        resp = await AsyncHTTPClient().fetch(request)

        # Extract token from JavaScript variable: pCsrfToken = 'abc123...';
        html = resp.body.decode('utf-8')
        match = re.search(r"pCsrfToken\s*=\s*'([0-9a-f]{64})'", html)

        if not match:
            # Motion version doesn't have CSRF - this is OK, use legacy GET
            logging.debug('Motion does not have CSRF tokens - using legacy API')
            _csrf_token_cache['csrf_supported'] = False
            _csrf_token_cache['port'] = settings.MOTION_CONTROL_PORT
            return None

        token = match.group(1)

        # Update cache
        _csrf_token_cache['token'] = token
        _csrf_token_cache['port'] = settings.MOTION_CONTROL_PORT
        _csrf_token_cache['timestamp'] = time.time()
        _csrf_token_cache['csrf_supported'] = True

        logging.debug(f'Retrieved CSRF token from Motion: {token[:16]}...')

        return token

    except Exception as e:
        logging.warning(f'Failed to check CSRF token from Motion: {e}')
        # Assume no CSRF support on error, try legacy API
        _csrf_token_cache['csrf_supported'] = False
        return None


async def _make_motion_request(url: str, data: dict = None, command: str = None, camid: int = None, use_post: bool = False) -> 'HTTPResponse':
    """
    Make request to Motion API, using POST+CSRF command API if supported, otherwise GET.

    Handles CSRF token retrieval, caching, and automatic fallback to legacy GET API.

    Args:
        url: Full URL to Motion API endpoint
        data: Dictionary of parameters
        command: Motion command (e.g., 'pause_on', 'snapshot') for CSRF mode
        camid: Camera ID for CSRF mode
        use_post: If True, use POST with CSRF token to the specified URL (for hot reload)

    Returns:
        HTTPResponse object
    """
    from urllib.parse import urlencode, urlparse, urlunparse

    # Check if Motion has CSRF support
    csrf_token = await _get_csrf_token()

    if csrf_token and command:
        # Motion 5.0+ with security - use root URL with command format
        root_url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'

        post_data = {
            'csrf_token': csrf_token,
            'command': command,
            'camid': camid or 0,
        }
        # Add any additional data
        if data:
            post_data.update(data)

        body = urlencode(post_data)

        request = HTTPRequest(
            root_url,
            method='POST',
            body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )

        resp = await AsyncHTTPClient().fetch(request, raise_error=False)

        # Handle 403: CSRF token may be stale, refresh and retry once
        if resp.code == 403:
            logging.warning('CSRF token validation failed (HTTP 403), refreshing token and retrying')

            new_token = await _get_csrf_token(force_refresh=True)
            if new_token:
                post_data['csrf_token'] = new_token
                body = urlencode(post_data)

                request = HTTPRequest(
                    root_url,
                    method='POST',
                    body=body,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    connect_timeout=_MOTION_CONTROL_TIMEOUT,
                    request_timeout=_MOTION_CONTROL_TIMEOUT,
                )

                resp = await AsyncHTTPClient().fetch(request, raise_error=False)

                if resp.code == 403:
                    logging.error('CSRF token validation failed after refresh - check Motion configuration')

        return resp

    elif csrf_token and use_post:
        # Motion 5.0+ hot reload: POST to specific URL with CSRF token only
        # Used for /config/set endpoint where param is in URL query string
        post_data = {'csrf_token': csrf_token}
        if data:
            post_data.update(data)

        body = urlencode(post_data)

        request = HTTPRequest(
            url,
            method='POST',
            body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )

        resp = await AsyncHTTPClient().fetch(request, raise_error=False)

        # Handle 403: CSRF token may be stale, refresh and retry once
        if resp.code == 403:
            logging.warning('CSRF token validation failed (HTTP 403), refreshing token and retrying')

            new_token = await _get_csrf_token(force_refresh=True)
            if new_token:
                post_data['csrf_token'] = new_token
                body = urlencode(post_data)

                request = HTTPRequest(
                    url,
                    method='POST',
                    body=body,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    connect_timeout=_MOTION_CONTROL_TIMEOUT,
                    request_timeout=_MOTION_CONTROL_TIMEOUT,
                )

                resp = await AsyncHTTPClient().fetch(request, raise_error=False)

                if resp.code == 403:
                    logging.error('CSRF token validation failed after refresh - check Motion configuration')

        return resp

    else:
        # Motion doesn't have CSRF - use legacy GET API with endpoint URLs
        if data:
            parsed = urlparse(url)
            query = urlencode(data)
            if parsed.query:
                query = parsed.query + '&' + query
            url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )

        return await AsyncHTTPClient().fetch(request, raise_error=False)


# Keep old name as alias for backward compatibility
async def _post_with_csrf(url: str, data: dict = None) -> 'HTTPResponse':
    """Alias for _make_motion_request for backward compatibility."""
    return await _make_motion_request(url, data)


async def set_config_hot(camera_id: int, param: str, value: str) -> dict:
    """
    Set a Motion parameter at runtime via hot reload API.

    Args:
        camera_id: MotionEye camera ID
        param: Motion parameter name
        value: New value for the parameter

    Returns:
        dict with keys:
            - success: bool
            - hot_reload: bool (True if applied without restart)
            - old_value: str (previous value, if available)
            - error: str (error message, if failed)
    """
    from motioneye.config.camera.constants import HOT_RELOAD_PARAMS

    # Early check - if not in our known hot-reload list, don't try
    if param not in HOT_RELOAD_PARAMS:
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Parameter requires daemon restart'
        }

    # Motion 5.0+ required (always true now)
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return {
            'success': False,
            'hot_reload': False,
            'error': f'Could not find motion camera id for camera {camera_id}'
        }

    # Build URL with parameter in query string (Motion 5.0 hot reload API)
    # Format: POST /{camera_id}/config/set?{param}={value}
    # The parameter goes in the URL query string, CSRF token goes in POST body
    from urllib.parse import quote
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set?{param}={quote(str(value))}'

    try:
        # Use POST with CSRF token to the specific URL (use_post=True)
        # Note: Do NOT pass command='config' - that would route to the wrong handler
        # The hot reload endpoint is the URL itself, not a command
        resp = await _make_motion_request(url, data=None, command=None, camid=motion_camera_id, use_post=True)

        if resp.code == 200:
            try:
                data = json.loads(resp.body.decode('utf-8'))

                if data.get('status') == 'ok' and data.get('hot_reload'):
                    logging.debug(f'Hot reload: {param}={value} on camera {camera_id}')
                    result = {
                        'success': True,
                        'hot_reload': True,
                        'old_value': data.get('old_value', '')
                    }
                    # Pass through ignored array if present
                    if data.get('ignored'):
                        result['ignored'] = data['ignored']
                    return result
                else:
                    # Motion reported the parameter needs restart
                    return {
                        'success': False,
                        'hot_reload': False,
                        'error': data.get('error', 'Parameter requires daemon restart')
                    }
            except json.JSONDecodeError:
                # Fallback for non-JSON response (older API format)
                logging.debug(f'Hot reload (non-JSON): {param}={value} on camera {camera_id}')
                return {
                    'success': True,
                    'hot_reload': True,
                    'old_value': ''
                }
        else:
            return {
                'success': False,
                'hot_reload': False,
                'error': f'HTTP {resp.code}'
            }

    except Exception as e:
        logging.error(f'Failed to hot-reload {param}: {e}')
        return {
            'success': False,
            'hot_reload': False,
            'error': str(e)
        }


async def apply_config_changes(camera_id: int, old_config: dict, new_config: dict) -> dict:
    """
    Intelligently apply configuration changes using hot reload where possible.

    Args:
        camera_id: MotionEye camera ID
        old_config: Previous Motion configuration dict
        new_config: New Motion configuration dict

    Returns:
        dict with keys:
            - hot_reloaded: list of param names that were hot-reloaded
            - needs_restart: bool (True if any changes require restart)
            - restart_params: list of param names that need restart
            - errors: list of error messages
    """
    from motioneye.config.camera.constants import HOT_RELOAD_PARAMS

    hot_reloaded = []
    restart_params = []
    errors = []

    # Find changed parameters (only Motion parameters, not @ prefixed MotionEye internal ones)
    all_params = set(old_config.keys()) | set(new_config.keys())
    motion_params = [p for p in all_params if not p.startswith('@')]

    for param in motion_params:
        old_val = old_config.get(param)
        new_val = new_config.get(param)

        # Skip unchanged parameters
        if old_val == new_val:
            continue

        # Skip None -> None
        if old_val is None and new_val is None:
            continue

        # Convert values to string for comparison (Motion API uses strings)
        old_str = str(old_val) if old_val is not None else ''
        new_str = str(new_val) if new_val is not None else ''

        if old_str == new_str:
            continue

        if param in HOT_RELOAD_PARAMS:
            # Try hot reload
            result = await set_config_hot(camera_id, param, new_str)

            if result['success']:
                hot_reloaded.append(param)
                logging.debug(f'Camera {camera_id}: Hot-reloaded {param}={new_str}')
            else:
                # Hot reload failed, will need restart
                restart_params.append(param)
                if result.get('error'):
                    errors.append(f"{param}: {result['error']}")
                logging.debug(f'Camera {camera_id}: {param} requires restart: {result.get("error")}')
        else:
            # Parameter requires restart
            restart_params.append(param)
            logging.debug(f'Camera {camera_id}: {param} requires restart (not in HOT_RELOAD_PARAMS)')

    return {
        'hot_reloaded': hot_reloaded,
        'needs_restart': len(restart_params) > 0,
        'restart_params': restart_params,
        'errors': errors
    }


async def is_hot_reload_available() -> bool:
    """
    Check if Motion's hot reload API is available.

    Returns:
        True if Motion 5.0+ with hot reload API is running
    """
    # Motion 5.0+ required (always true now)
    if not running():
        return False

    try:
        # Test with a safe parameter query
        url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/0/config/list'
        request = HTTPRequest(
            url,
            connect_timeout=2,
            request_timeout=2,
        )
        resp = await AsyncHTTPClient().fetch(request)
        return resp.code == 200
    except Exception:
        return False
