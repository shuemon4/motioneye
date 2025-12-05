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

import datetime
import fcntl
import functools
import logging
import mimetypes
import multiprocessing
import os.path
import re
import subprocess
import typing
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from errno import EAGAIN, ENOENT
from hashlib import sha1
from io import BytesIO
from shlex import quote
from signal import SIGTERM
from stat import S_ISDIR, S_ISREG
from time import time, monotonic
from zipfile import ZipFile

from PIL import Image
from tornado.concurrent import Future
from tornado.ioloop import IOLoop

from motioneye import config, settings, uploadservices, utils
from motioneye.utils.dtconv import pretty_date_time

_PICTURE_EXTS = ['.jpg']
_MOVIE_EXTS = ['.avi', '.mp4', '.mov', '.swf', '.flv', '.mkv']

FFMPEG_CODEC_MAPPING = {
    'mpeg4': 'mpeg4',
    'msmpeg4': 'msmpeg4v2',
    'swf': 'flv1',
    'flv': 'flv1',
    'mov': 'mpeg4',
    'mp4': 'h264',
    'mkv': 'h264',
    'mp4:h264_omx': 'h264_omx',
    'mkv:h264_omx': 'h264_omx',
    'mp4:h264_v4l2m2m': 'h264_v4l2m2m',
    'mkv:h264_v4l2m2m': 'h264_v4l2m2m',
    'hevc': 'h265',
}

FFMPEG_FORMAT_MAPPING = {
    'mpeg4': 'avi',
    'msmpeg4': 'avi',
    'swf': 'swf',
    'flv': 'flv',
    'mov': 'mov',
    'mp4': 'mp4',
    'mkv': 'matroska',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'matroska',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'matroska',
    'hevc': 'mp4',
}

FFMPEG_EXT_MAPPING = {
    'mpeg4': 'avi',
    'msmpeg4': 'avi',
    'swf': 'swf',
    'flv': 'flv',
    'mov': 'mov',
    'mp4': 'mp4',
    'mkv': 'mkv',
    'mp4:h264_omx': 'mp4',
    'mkv:h264_omx': 'mkv',
    'mp4:h264_v4l2m2m': 'mp4',
    'mkv:h264_v4l2m2m': 'mkv',
    'hevc': 'mp4',
}

MOVIE_EXT_TYPE_MAPPING = {
    'avi': 'video/x-msvideo',
    'mp4': 'video/mp4',
    'mov': 'video/quicktime',
    'swf': 'application/x-shockwave-flash',
    'flv': 'video/x-flv',
    'mkv': 'video/x-matroska',
}

# =============================================================================
# Prepared Files Cache (Pi 5 Optimization: Bounded LRU with size limits)
# =============================================================================

# LRU cache using OrderedDict
# Key: cache_key (hash string)
# Value: (data, size, timestamp)
_prepared_files = OrderedDict()
_prepared_files_total_size = 0

_timelapse_process = None
_timelapse_data = None

_ffmpeg_binary_cache = None

# =============================================================================
# Pi 5 Optimization: ThreadPoolExecutor and Media Listing Cache
# =============================================================================

# ThreadPoolExecutor for media listing (replaces multiprocessing.Process)
_listing_executor = None

# Media listing cache with TTL
# Key: (camera_id, media_type, prefix)
# Value: (timestamp, result_list)
_media_listing_cache = {}


def start():
    """Initialize the media files module (called from server.py)."""
    global _listing_executor
    _listing_executor = ThreadPoolExecutor(max_workers=2)
    logging.debug('mediafiles: ThreadPoolExecutor initialized')


def stop():
    """Shutdown the media files module (called from server.py)."""
    global _listing_executor
    if _listing_executor:
        _listing_executor.shutdown(wait=True)
        _listing_executor = None
        logging.debug('mediafiles: ThreadPoolExecutor shutdown')


def _get_cached_listing(camera_id, media_type, prefix):
    """
    Get cached media listing if available and fresh.

    Returns:
        list or None: Cached result if valid, None otherwise
    """
    cache_key = (camera_id, media_type, prefix)
    cached = _media_listing_cache.get(cache_key)

    if cached is None:
        return None

    timestamp, result = cached
    ttl = getattr(settings, 'MEDIA_LISTING_CACHE_TTL', 10)

    if monotonic() - timestamp > ttl:
        # Cache expired
        del _media_listing_cache[cache_key]
        return None

    logging.debug('mediafiles: cache hit for %s', cache_key)
    return result


def _set_cached_listing(camera_id, media_type, prefix, results):
    """Store media listing in cache."""
    cache_key = (camera_id, media_type, prefix)
    _media_listing_cache[cache_key] = (monotonic(), results)


def invalidate_listing_cache(camera_id=None):
    """
    Invalidate media listing cache.

    Args:
        camera_id: If provided, only invalidate cache for this camera.
                   If None, invalidate all cache entries.
    """
    global _media_listing_cache

    if camera_id is None:
        _media_listing_cache = {}
        logging.debug('mediafiles: cleared all listing cache')
    else:
        keys_to_remove = [k for k in _media_listing_cache if k[0] == camera_id]
        for key in keys_to_remove:
            del _media_listing_cache[key]
        logging.debug('mediafiles: cleared listing cache for camera %s', camera_id)


def findfiles(path: str) -> typing.List[tuple]:
    files = []
    for name in os.listdir(path):
        # ignore hidden files/dirs and other unwanted files
        if name.startswith('.') or name == 'lastsnap.jpg':
            continue
        pathname = os.path.join(path, name)
        st = os.lstat(pathname)
        mode = st.st_mode
        if S_ISDIR(mode):
            files.extend(findfiles(pathname))

        elif S_ISREG(mode):
            files.append((pathname, name, st))

    return files


def _list_media_files(
    directory: str, exts: typing.List[str], prefix: str = None
) -> typing.List[tuple]:
    media_files = []

    if prefix is not None:
        if prefix == 'ungrouped':
            prefix = ''

        root = os.path.join(directory, prefix)
        if not os.path.exists(root):
            return media_files

        for name in os.listdir(root):
            # ignore hidden files/dirs and other unwanted files
            if name.startswith('.') or name == 'lastsnap.jpg':
                continue

            full_path = os.path.join(root, name)
            try:
                st = os.stat(full_path)

            except Exception as e:
                logging.error('stat failed: ' + str(e))
                continue

            if not S_ISREG(st.st_mode):  # not a regular file
                continue

            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue

            media_files.append((full_path, st))

    else:
        for full_path, name, st in findfiles(directory):
            full_path_lower = full_path.lower()
            if not [e for e in exts if full_path_lower.endswith(e)]:
                continue

            media_files.append((full_path, st))

    return media_files


def _remove_older_files(
    directory: str,
    moment: datetime.datetime,
    clean_cloud_info: dict,
    exts: typing.List[str],
):
    removed_folder_count = 0
    for full_path, st in _list_media_files(directory, exts):
        file_moment = datetime.datetime.fromtimestamp(st.st_mtime)
        if file_moment < moment:
            logging.debug(f'removing file {full_path}...')

            # remove the file itself
            try:
                os.remove(full_path)

            except OSError as e:
                if e.errno == ENOENT:
                    pass  # the file might have been removed in the meantime

                else:
                    logging.error(f'failed to remove {full_path}: {e}')

            # remove the parent directories if empty or contain only thumb files
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                continue

            listing = os.listdir(dir_path)
            thumbs = [l for l in listing if l.endswith('.thumb')]

            if len(listing) == len(thumbs):  # only thumbs
                for p in thumbs:
                    try:
                        os.remove(os.path.join(dir_path, p))

                    except Exception as e:
                        logging.error(f'failed to remove {p}: {e}')

            if not listing or len(listing) == len(thumbs):
                # this will possibly cause following paths that are in the media files for loop
                # to be removed in advance; the os.remove call will raise ENOENT which is silently ignored
                logging.debug(f'removing empty directory {dir_path}...')
                try:
                    os.removedirs(dir_path)
                    removed_folder_count += 1

                except Exception as e:
                    logging.error(f'failed to remove {dir_path}: {e}')

    if clean_cloud_info and removed_folder_count > 0:
        uploadservices.clean_cloud(directory, {}, clean_cloud_info)


def _discover_ffmpeg() -> tuple:
    """
    Discover ffmpeg binary and its capabilities.
    This is the expensive operation we want to cache.
    """
    # binary
    try:
        binary = utils.call_subprocess(['which', 'ffmpeg'])

    except subprocess.CalledProcessError:  # not found
        return None, None, None

    # version
    try:
        output = utils.call_subprocess([quote(binary), '-version'])

    except subprocess.CalledProcessError as e:
        logging.error('ffmpeg: could not find version: %s', e)
        return None, None, None

    result = re.findall('ffmpeg version (.+?) ', output, re.IGNORECASE)
    version = result and result[0] or ''

    # codecs
    try:
        output = utils.call_subprocess(binary + ' -codecs -hide_banner', shell=True)

    except subprocess.CalledProcessError as e:
        logging.error('ffmpeg: could not list supported codecs: %s', e)
        return None, None, None

    lines = output.split('\n')
    lines = [l for l in lines if re.match('^ [DEVILSA.]{6} [^=].*', l)]

    codecs = {}
    for line in lines:
        m = re.match(r'^ [DEVILSA.]{6} ([\w+_]+)', line)
        if not m:
            continue

        codec = m.group(1)

        decoders = set()
        encoders = set()

        m = re.search(r'decoders: ([\w\s_]+)+', line)
        if m:
            decoders = set(m.group(1).split())

        m = re.search(r'encoders: ([\w\s_]+)+', line)
        if m:
            encoders = set(m.group(1).split())

        codecs[codec] = {'encoders': encoders, 'decoders': decoders}

    logging.debug('found ffmpeg executable "%s" version "%s"', binary, version)

    return (binary, version, codecs)


def find_ffmpeg() -> tuple:
    """
    Find ffmpeg binary with caching.

    Pi 5 Optimization: Caches the ffmpeg path and codec info to avoid
    repeated subprocess calls for 'which' and codec probing.
    """
    global _ffmpeg_binary_cache

    if _ffmpeg_binary_cache:
        return _ffmpeg_binary_cache

    _ffmpeg_binary_cache = _discover_ffmpeg()
    return _ffmpeg_binary_cache


def get_ffmpeg_binary() -> str:
    """
    Get just the ffmpeg binary path (for subprocess calls).

    Pi 5 Optimization: Useful for passing to subprocesses without
    needing to re-discover ffmpeg.
    """
    result = find_ffmpeg()
    return result[0] if result else None


def cleanup_media(media_type: str) -> None:
    logging.debug(f'cleaning up {media_type}s...')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        preserve_media = camera_config.get(f'@preserve_{media_type}s', 0)
        if preserve_media == 0:
            continue  # preserve forever

        still_images_enabled = bool(camera_config['picture_filename']) or bool(
            camera_config['snapshot_filename']
        )
        movies_enabled = bool(camera_config['movie_output'])

        if media_type == 'picture' and not still_images_enabled:
            continue  # only cleanup pictures for cameras with still images enabled

        elif media_type == 'movie' and not movies_enabled:
            continue  # only cleanup movies for cameras with movies enabled

        preserve_moment = datetime.datetime.now() - datetime.timedelta(
            days=preserve_media
        )

        target_dir = camera_config.get('target_dir')
        cloud_enabled = camera_config.get('@upload_enabled')
        clean_cloud_enabled = camera_config.get('@clean_cloud_enabled')
        cloud_dir = camera_config.get('@upload_location')
        service_name = camera_config.get('@upload_service')
        clean_cloud_info = None
        if (
            cloud_enabled
            and clean_cloud_enabled
            and camera_id
            and service_name
            and cloud_dir
        ):
            clean_cloud_info = {
                'camera_id': camera_id,
                'service_name': service_name,
                'cloud_dir': cloud_dir,
            }
        if os.path.exists(target_dir):
            # create a sentinel file to make sure the target dir is never removed
            open(os.path.join(target_dir, '.keep'), 'w').close()

        logging.debug(
            f'calling _remove_older_files: {cloud_enabled} {clean_cloud_enabled} {clean_cloud_info}'
        )
        _remove_older_files(target_dir, preserve_moment, clean_cloud_info, exts=exts)


def cleanup_media_combined() -> dict:
    """
    Single-pass cleanup for both pictures and movies.

    Pi 5 Optimization: Performs a single directory scan per camera instead of
    two separate scans (one for pictures, one for movies). This halves the I/O
    overhead for cleanup operations.

    Returns:
        dict: Statistics about removed files
    """
    stats = {
        'pictures_removed': 0,
        'movies_removed': 0,
        'bytes_freed': 0,
        'cameras_processed': 0,
    }

    all_picture_exts = set(_PICTURE_EXTS)
    all_movie_exts = set(_MOVIE_EXTS + ['.thumb'])

    for camera_id in config.get_camera_ids():
        camera_config = config.get_camera(camera_id)
        if not utils.is_local_motion_camera(camera_config):
            continue

        # Get retention settings for both types
        preserve_pictures = camera_config.get('@preserve_pictures', 0)
        preserve_movies = camera_config.get('@preserve_movies', 0)

        # Check if any cleanup is needed
        if preserve_pictures == 0 and preserve_movies == 0:
            continue  # Both set to preserve forever

        # Check if media types are enabled
        still_images_enabled = bool(camera_config.get('picture_filename')) or bool(
            camera_config.get('snapshot_filename')
        )
        movies_enabled = bool(camera_config.get('movie_output'))

        # Skip if nothing to clean
        if not still_images_enabled and not movies_enabled:
            continue

        # Skip if retention is infinite for both enabled types
        if (not still_images_enabled or preserve_pictures == 0) and \
           (not movies_enabled or preserve_movies == 0):
            continue

        target_dir = camera_config.get('target_dir')
        if not os.path.exists(target_dir):
            continue

        # Create sentinel file
        try:
            open(os.path.join(target_dir, '.keep'), 'w').close()
        except Exception:
            pass

        # Calculate preservation moments
        now = datetime.datetime.now()
        picture_preserve_moment = None
        movie_preserve_moment = None

        if still_images_enabled and preserve_pictures > 0:
            picture_preserve_moment = now - datetime.timedelta(days=preserve_pictures)

        if movies_enabled and preserve_movies > 0:
            movie_preserve_moment = now - datetime.timedelta(days=preserve_movies)

        # Cloud cleanup info
        cloud_enabled = camera_config.get('@upload_enabled')
        clean_cloud_enabled = camera_config.get('@clean_cloud_enabled')
        cloud_dir = camera_config.get('@upload_location')
        service_name = camera_config.get('@upload_service')
        clean_cloud_info = None
        if cloud_enabled and clean_cloud_enabled and service_name and cloud_dir:
            clean_cloud_info = {
                'camera_id': camera_id,
                'service_name': service_name,
                'cloud_dir': cloud_dir,
            }

        # Single-pass file scan
        removed_folders = 0
        for full_path, name, st in findfiles(target_dir):
            full_path_lower = full_path.lower()
            file_moment = datetime.datetime.fromtimestamp(st.st_mtime)

            should_remove = False
            is_picture = False
            is_movie = False

            # Check if it's a picture file
            if any(full_path_lower.endswith(ext) for ext in all_picture_exts):
                is_picture = True
                if picture_preserve_moment and file_moment < picture_preserve_moment:
                    should_remove = True

            # Check if it's a movie file (or thumb)
            elif any(full_path_lower.endswith(ext) for ext in all_movie_exts):
                is_movie = True
                if movie_preserve_moment and file_moment < movie_preserve_moment:
                    should_remove = True

            if not should_remove:
                continue

            # Remove the file
            try:
                file_size = st.st_size
                os.remove(full_path)
                stats['bytes_freed'] += file_size

                if is_picture:
                    stats['pictures_removed'] += 1
                elif is_movie:
                    stats['movies_removed'] += 1

                logging.debug('removed file %s', full_path)

            except OSError as e:
                if e.errno != ENOENT:
                    logging.error('failed to remove %s: %s', full_path, e)
                continue

            # Try to clean up empty parent directories
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                continue

            try:
                listing = os.listdir(dir_path)
                thumbs = [l for l in listing if l.endswith('.thumb')]

                # Remove orphaned thumbs
                if len(listing) == len(thumbs):
                    for p in thumbs:
                        try:
                            os.remove(os.path.join(dir_path, p))
                        except Exception:
                            pass

                # Remove empty directory
                if not listing or len(listing) == len(thumbs):
                    logging.debug('removing empty directory %s...', dir_path)
                    os.removedirs(dir_path)
                    removed_folders += 1

            except Exception as e:
                logging.debug('could not clean directory %s: %s', dir_path, e)

        # Clean cloud if needed
        if clean_cloud_info and removed_folders > 0:
            try:
                uploadservices.clean_cloud(target_dir, {}, clean_cloud_info)
            except Exception as e:
                logging.error('failed to clean cloud: %s', e)

        stats['cameras_processed'] += 1

    return stats


def make_movie_preview(camera_config: dict, full_path: str) -> typing.Union[str, None]:
    framerate = camera_config['framerate']
    pre_capture = camera_config['pre_capture']
    offs = pre_capture / framerate
    offs = max(4, offs * 2)
    path = quote(full_path)
    thumb_path = full_path + '.thumb'

    logging.debug(
        f'creating movie preview for {full_path} with an offset of {offs} seconds...'
    )

    cmd = f'ffmpeg -i {path} -f mjpeg -vframes 1 -ss {offs} -y {path}.thumb'
    logging.debug(f'running command "{cmd}"')

    try:
        utils.call_subprocess(cmd.split(), stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as e:
        logging.error(f'failed to create movie preview for {full_path}: {e}')

        return None

    try:
        st = os.stat(thumb_path)

    except OSError:
        logging.error(f'failed to create movie preview for {full_path}')

        return None

    if st.st_size == 0:
        logging.debug(
            f'movie probably too short, grabbing first frame from {full_path}...'
        )

        cmd = f'ffmpeg -i {path} -f mjpeg -vframes 1 -ss 0 -y {path}.thumb'
        logging.debug(f'running command "{cmd}"')

        # try again, this time grabbing the very first frame
        try:
            utils.call_subprocess(cmd.split(), stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            logging.error(f'failed to create movie preview for {full_path}: {e}')

            return None

        try:
            st = os.stat(thumb_path)

        except OSError:
            logging.error(f'failed to create movie preview for {full_path}')

            return None

    if st.st_size == 0:
        logging.error(f'failed to create movie preview for {full_path}')
        try:
            os.remove(thumb_path)

        except:
            pass

        return None

    return thumb_path


def _do_list_media_sync(target_dir: str, exts: list, prefix: str) -> list:
    """
    Synchronous media listing worker function.
    Runs in ThreadPoolExecutor thread.
    """
    media_list = []

    mf = _list_media_files(target_dir, exts=exts, prefix=prefix)
    for p, st in mf:
        path = p[len(target_dir):]
        if not path.startswith('/'):
            path = '/' + path

        timestamp = st.st_mtime
        size = st.st_size

        mime_type = mimetypes.guess_type(path)[0]
        if mime_type is None:
            mime_type = 'video/mpeg'

        media_list.append({
            'path': path,
            'mimeType': mime_type,
            'momentStr': pretty_date_time(
                datetime.datetime.fromtimestamp(timestamp)
            ),
            'momentStrShort': pretty_date_time(
                datetime.datetime.fromtimestamp(timestamp), short=True
            ),
            'sizeStr': utils.pretty_size(size),
            'timestamp': timestamp,
        })

    return media_list


def list_media(camera_config: dict, media_type: str, prefix=None) -> typing.Awaitable:
    """
    List media files for a camera.

    Pi 5 Optimization: Uses ThreadPoolExecutor instead of multiprocessing.Process
    for ~10-50ms spawn time savings. Also implements TTL-based caching.
    """
    fut = Future()
    target_dir = camera_config.get('target_dir')
    camera_id = camera_config.get('@id')

    if media_type == 'picture':
        exts = _PICTURE_EXTS
    elif media_type == 'movie':
        exts = _MOVIE_EXTS
    else:
        fut.set_result([])
        return fut

    # Check cache first
    cached = _get_cached_listing(camera_id, media_type, prefix)
    if cached is not None:
        fut.set_result(cached)
        return fut

    # Use ThreadPoolExecutor if available, fallback to synchronous
    if _listing_executor is None:
        logging.warning('mediafiles: executor not initialized, running synchronously')
        try:
            result = _do_list_media_sync(target_dir, exts, prefix)
            _set_cached_listing(camera_id, media_type, prefix, result)
            fut.set_result(result)
        except Exception as e:
            logging.error('failed to list media files: %s', e)
            fut.set_result(None)
        return fut

    logging.debug('starting media listing in thread pool...')

    def on_complete(future_result):
        try:
            result = future_result.result()
            logging.debug('media listing has returned %d files', len(result))
            _set_cached_listing(camera_id, media_type, prefix, result)
            fut.set_result(result)
        except Exception as e:
            logging.error('failed to list media files: %s', e)
            fut.set_result(None)

    io_loop = IOLoop.current()
    executor_future = _listing_executor.submit(
        _do_list_media_sync, target_dir, exts, prefix
    )

    # Add callback that runs on IOLoop
    def check_future():
        if executor_future.done():
            on_complete(executor_future)
        else:
            io_loop.add_timeout(datetime.timedelta(seconds=0.1), check_future)

    check_future()
    return fut


def get_media_path(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, path)
    return full_path


def get_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    if '..' in path:
        raise Exception('invalid media path')

    full_path = os.path.join(target_dir, path)

    try:
        with open(full_path, 'rb') as f:
            return f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {str(e)}')

        return None


def get_zipped_content(
    camera_config: dict, media_type: str, group: str
) -> typing.Awaitable:
    fut = Future()
    target_dir = camera_config.get('target_dir')

    if media_type == 'picture':
        exts = _PICTURE_EXTS

    elif media_type == 'movie':
        exts = _MOVIE_EXTS

    working = multiprocessing.Value('b')
    working.value = True

    # create a subprocess to add files to zip
    def do_zip(pipe):
        parent_pipe.close()

        mf = _list_media_files(target_dir, exts=exts, prefix=group)
        paths = []
        for p, st in mf:  # @UnusedVariable
            path = p[len(target_dir) :]
            if path.startswith('/'):
                path = path[1:]

            paths.append(path)

        zip_filename = os.path.join(settings.MEDIA_PATH, f'.zip-{int(time())}')
        logging.debug(f'adding {len(paths)} files to zip file "{zip_filename}"')

        try:
            with ZipFile(zip_filename, mode='w') as f:
                for path in paths:
                    full_path = os.path.join(target_dir, path)
                    f.write(full_path, path)

        except Exception as e:
            logging.error(f'failed to create zip file "{zip_filename}": {e}')

            working.value = False
            pipe.close()
            return

        logging.debug(f'reading zip file "{zip_filename}" into memory')

        try:
            with open(zip_filename, mode='rb') as f:
                data = f.read()

            working.value = False
            pipe.send(data)
            logging.debug('zip data ready')

        except Exception as e:
            logging.error(f'failed to read zip file "{zip_filename}": {e}')
            working.value = False

        finally:
            os.remove(zip_filename)
            pipe.close()

    logging.debug('starting zip process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=do_zip, args=(child_pipe,))
    process.start()
    child_pipe.close()

    # poll the subprocess to see when it has finished
    started = datetime.datetime.now()

    def poll_process():
        io_loop = IOLoop.current()
        if working.value:
            now = datetime.datetime.now()
            delta = now - started
            if delta.seconds < settings.ZIP_TIMEOUT:
                io_loop.add_timeout(datetime.timedelta(seconds=0.5), poll_process)

            else:  # process did not finish in time
                logging.error('timeout waiting for the zip process to finish')
                try:
                    os.kill(process.pid, SIGTERM)

                except:
                    pass  # nevermind

                fut.set_result(None)

        else:  # finished
            try:
                data = parent_pipe.recv()
                logging.debug(f'zip process has returned {len(data)} bytes')

            except:
                data = None

            fut.set_result(data)

    poll_process()
    return fut


def make_timelapse_movie(camera_config, framerate, interval, group):
    global _timelapse_process
    global _timelapse_data

    target_dir = camera_config.get('target_dir')
    # save movie_codec as a different variable so it doesn't get lost in the CODEC_MAPPING
    movie_codec = camera_config.get('movie_codec')

    codec = FFMPEG_CODEC_MAPPING.get(movie_codec, movie_codec)
    fmt = FFMPEG_FORMAT_MAPPING.get(movie_codec, movie_codec)
    file_format = FFMPEG_EXT_MAPPING.get(movie_codec, movie_codec)

    # create a subprocess to retrieve media files
    def do_list_media(pipe):
        parent_pipe.close()

        mf = _list_media_files(target_dir, exts=_PICTURE_EXTS, prefix=group)
        for p, st in mf:
            timestamp = st.st_mtime

            pipe.send({'path': p, 'timestamp': timestamp})

        pipe.close()

    logging.debug('starting media listing process...')

    (parent_pipe, child_pipe) = multiprocessing.Pipe(duplex=False)
    _timelapse_process = multiprocessing.Process(
        target=do_list_media, args=(child_pipe,)
    )
    _timelapse_process.progress = 0
    _timelapse_process.start()
    _timelapse_data = None

    child_pipe.close()

    started = [datetime.datetime.now()]
    media_list = []

    # use correct extension for the movie_codec
    tmp_filename = os.path.join(settings.MEDIA_PATH, f'.{int(time())}.{file_format}')

    def read_media_list():
        while parent_pipe.poll():
            try:
                media_list.append(parent_pipe.recv())

            except EOFError:
                break

    def poll_media_list_process():
        io_loop = IOLoop.current()
        if _timelapse_process.is_alive():  # not finished yet
            now = datetime.datetime.now()
            delta = now - started[0]
            if (
                delta.seconds < settings.TIMELAPSE_TIMEOUT
            ):  # the subprocess has limited time to complete its job
                io_loop.add_timeout(
                    datetime.timedelta(seconds=0.5), poll_media_list_process
                )
                read_media_list()

            else:  # process did not finish in time
                logging.error('timeout waiting for the media listing process to finish')
                try:
                    os.kill(_timelapse_process.pid, SIGTERM)

                except:
                    pass  # nevermind

                _timelapse_process.progress = -1

        else:  # finished
            read_media_list()
            logging.debug(f'media listing process has returned {len(media_list)} files')

            if not media_list:
                _timelapse_process.progress = -1

                return

            pictures = select_pictures(media_list)
            make_movie(pictures)

    def select_pictures(media_list):
        media_list.sort(key=lambda e: e['timestamp'])
        start = media_list[0]['timestamp']
        slices = {}
        max_idx = 0
        for m in media_list:
            offs = m['timestamp'] - start
            pos = float(offs) / interval - 0.5
            idx = int(round(pos))
            max_idx = idx
            m['delta'] = abs(pos - idx)
            slices.setdefault(idx, []).append(m)

        selected = []
        for i in range(max_idx + 1):
            s = slices.get(i)
            if not s:
                continue

            selected.append(min(s, key=lambda m: m['delta']))

        logging.debug(f'selected {len(selected)}/{len(media_list)} media files')

        return selected

    def make_movie(pictures):
        global _timelapse_process

        # don't specify file format with -f, let ffmpeg work it out from the extension
        cmd = 'rm -f %(tmp_filename)s;'
        cmd += (
            'cat %(jpegs)s | ffmpeg -framerate %(framerate)s -f image2pipe -vcodec mjpeg -i - -vcodec %(codec)s '
            '-format %(format)s -b:v %(bitrate)s -qscale:v 0.1 %(tmp_filename)s'
        )

        bitrate = 9999999

        cmd = cmd % {
            'tmp_filename': tmp_filename,
            'jpegs': ' '.join(('"' + p['path'] + '"') for p in pictures),
            'framerate': framerate,
            'codec': codec,
            'format': fmt,
            'bitrate': bitrate,
        }

        logging.debug(f'executing "{cmd}"')

        _timelapse_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True
        )
        _timelapse_process.progress = 0.01  # 1%

        # make subprocess stdout pipe non-blocking
        fd = _timelapse_process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        poll_movie_process(pictures)

    def poll_movie_process(pictures):
        global _timelapse_process
        global _timelapse_data

        io_loop = IOLoop.current()
        if _timelapse_process.poll() is None:  # not finished yet
            io_loop.add_timeout(
                datetime.timedelta(seconds=0.5),
                functools.partial(poll_movie_process, pictures),
            )

            try:
                output = _timelapse_process.stdout.read()
                if not output:
                    return

            except OSError as e:
                if e.errno == EAGAIN:
                    return

                raise

            frame_index = re.findall(br'frame=\s*(\d+)', output)
            try:
                frame_index = int(frame_index[-1])

            except (IndexError, ValueError):
                return

            _timelapse_process.progress = max(0.01, float(frame_index) / len(pictures))

            logging.debug(
                f'timelapse progress: {int(100 * _timelapse_process.progress)} %'
            )

        else:  # finished
            exit_code = _timelapse_process.poll()
            _timelapse_process = None

            if exit_code != 0:
                logging.error('ffmpeg process failed')
                _timelapse_data = None

                try:
                    os.remove(tmp_filename)

                except:
                    pass

            else:
                logging.debug(
                    f'reading timelapse movie file "{tmp_filename}" into memory'
                )

                try:
                    with open(tmp_filename, mode='rb') as f:
                        _timelapse_data = f.read()

                    logging.debug(
                        f'timelapse movie process has returned {len(_timelapse_data)} bytes'
                    )

                except Exception as e:
                    logging.error(
                        f'failed to read timelapse movie file "{tmp_filename}": {e}'
                    )

                finally:
                    try:
                        os.remove(tmp_filename)

                    except:
                        pass

    poll_media_list_process()


def check_timelapse_movie():
    if _timelapse_process:
        if (
            hasattr(_timelapse_process, 'poll') and _timelapse_process.poll() is None
        ) or (
            hasattr(_timelapse_process, 'is_alive') and _timelapse_process.is_alive()
        ):
            return {'progress': _timelapse_process.progress, 'data': None}

        else:
            return {'progress': _timelapse_process.progress, 'data': _timelapse_data}

    else:
        return {'progress': -1, 'data': _timelapse_data}


def get_media_preview(camera_config, path, media_type, width, height):
    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, path)

    if media_type == 'movie':
        if not os.path.exists(full_path + '.thumb'):
            # at this point we expect the thumb to
            # have already been created by the thumbnailer task;
            # if, for some reason that's not the case,
            # we create it right away
            if not make_movie_preview(camera_config, full_path):
                return None

        full_path += '.thumb'

    try:
        with open(full_path, 'rb') as f:
            content = f.read()

    except Exception as e:
        logging.error(f'failed to read file {full_path}: {e}')
        return None

    if width is height is None:
        return content

    bio = BytesIO(content)
    try:
        image = Image.open(bio)

    except Exception as e:
        logging.error(f'failed to open media preview image file: {e}')
        return None

    width = width and int(float(width)) or image.size[0]
    height = height and int(float(height)) or image.size[1]

    image.thumbnail((width, height), Image.BILINEAR)

    bio = BytesIO()
    image.save(bio, format='JPEG')

    return bio.getvalue()


def del_media_content(camera_config, path, media_type):
    target_dir = camera_config.get('target_dir')

    full_path = os.path.join(target_dir, path)

    # create a sentinel file to make sure the target dir is never removed
    open(os.path.join(target_dir, '.keep'), 'w').close()

    try:
        # remove the file itself
        os.remove(full_path)

        # remove the thumb file
        try:
            os.remove(full_path + '.thumb')

        except:
            pass

        # remove the parent directories if empty or contains only thumb files
        dir_path = os.path.dirname(full_path)
        listing = os.listdir(dir_path)
        thumbs = [l for l in listing if l.endswith('.thumb')]

        if len(listing) == len(thumbs):  # only thumbs
            for p in thumbs:
                os.remove(os.path.join(dir_path, p))

        if not listing or len(listing) == len(thumbs):
            logging.debug(f'removing empty directory {dir_path}...')
            os.removedirs(dir_path)

    except Exception as e:
        logging.error(f'failed to remove file {full_path}: {str(e)}')

        raise


def del_media_group(camera_config, group, media_type):
    if media_type == 'picture':
        exts = _PICTURE_EXTS

    else:  # media_type == 'movie'
        exts = _MOVIE_EXTS + ['.thumb']

    target_dir = camera_config.get('target_dir')
    full_path = os.path.join(target_dir, group)

    # create a sentinel file to make sure the target dir is never removed
    open(os.path.join(target_dir, '.keep'), 'w').close()

    mf = _list_media_files(target_dir, exts=exts, prefix=group)
    for path, st in mf:  # @UnusedVariable
        try:
            os.remove(path)

        except Exception as e:
            logging.error(f'failed to remove file {full_path}: {str(e)}')
            raise

    # remove the group directory if empty or contains only thumb files
    listing = os.listdir(full_path)
    thumbs = [l for l in listing if l.endswith('.thumb')]

    if len(listing) == len(thumbs):  # only thumbs
        for p in thumbs:
            os.remove(os.path.join(full_path, p))

    if not listing or len(listing) == len(thumbs):
        logging.debug(f'removing empty directory {full_path}...')
        os.removedirs(full_path)


def get_current_picture(camera_config, width, height):
    from motioneye import mjpgclient

    jpg = mjpgclient.get_jpg(camera_config['@id'])

    if jpg is None:
        return None

    if width is height is None:
        return jpg  # no server-side resize needed

    bio = BytesIO(jpg)
    try:
        image = Image.open(bio)

    except Exception as e:
        logging.error(f'failed to open media image file: {e}')
        return None

    if width and width < 1:  # given as percent
        width = int(width * image.size[0])
    if height and height < 1:  # given as percent
        height = int(height * image.size[1])

    width = width and int(width) or image.size[0]
    height = height and int(height) or image.size[1]

    webcam_resolution = camera_config['@webcam_resolution']
    max_width = image.size[0] * webcam_resolution / 100
    max_height = image.size[1] * webcam_resolution / 100

    width = min(max_width, width)
    height = min(max_height, height)

    if width >= image.size[0] and height >= image.size[1]:
        return jpg  # no enlarging of the picture on the server side

    image.thumbnail((width, height), Image.BICUBIC)

    bio = BytesIO()
    image.save(bio, format='JPEG')

    return bio.getvalue()


def _evict_prepared_cache_lru():
    """
    Evict oldest entries from prepared cache if over limits.
    Pi 5 Optimization: Bounded LRU cache prevents unbounded memory growth.
    """
    global _prepared_files_total_size

    max_size_bytes = getattr(settings, 'PREPARED_FILES_MAX_SIZE_MB', 500) * 1024 * 1024
    max_entries = getattr(settings, 'PREPARED_FILES_MAX_ENTRIES', 10)

    # Evict by entry count
    while len(_prepared_files) > max_entries:
        key, (data, size, ts) = _prepared_files.popitem(last=False)
        _prepared_files_total_size -= size
        logging.debug('evicted prepared cache entry %s (count limit)', key)

    # Evict by size
    while _prepared_files_total_size > max_size_bytes and _prepared_files:
        key, (data, size, ts) = _prepared_files.popitem(last=False)
        _prepared_files_total_size -= size
        logging.debug('evicted prepared cache entry %s (size limit)', key)


def get_prepared_cache(key):
    """
    Get and remove a prepared file from cache.
    Pi 5 Optimization: LRU touch on access for better cache behavior.
    """
    global _prepared_files_total_size

    entry = _prepared_files.pop(key, None)
    if entry is None:
        return None

    data, size, ts = entry
    _prepared_files_total_size -= size
    return data


def set_prepared_cache(data):
    """
    Store a prepared file in cache with LRU eviction.
    Pi 5 Optimization: Bounded cache with configurable limits.
    """
    global _prepared_files_total_size

    key = sha1(str(time()).encode()).hexdigest()  # nosec B303

    if key in _prepared_files:
        logging.warning('key "%s" already present in prepared cache', key)
        # Remove old entry first
        old_data, old_size, old_ts = _prepared_files.pop(key)
        _prepared_files_total_size -= old_size

    data_size = len(data)
    _prepared_files[key] = (data, data_size, monotonic())
    _prepared_files_total_size += data_size

    # Evict old entries if over limits
    _evict_prepared_cache_lru()

    # Schedule timeout cleanup
    timeout = getattr(settings, 'PREPARED_FILES_TIMEOUT', 1800)

    def clear():
        global _prepared_files_total_size
        entry = _prepared_files.pop(key, None)
        if entry is not None:
            data, size, ts = entry
            _prepared_files_total_size -= size
            logging.debug('prepared cache entry %s expired', key)

    io_loop = IOLoop.current()
    io_loop.add_timeout(datetime.timedelta(seconds=timeout), clear)

    logging.debug(
        'prepared cache: added %s (%d bytes, %d entries, %d MB total)',
        key, data_size, len(_prepared_files),
        _prepared_files_total_size // (1024 * 1024)
    )

    return key
