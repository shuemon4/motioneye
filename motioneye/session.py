# Copyright (c) 2024 MotionEye Contributors
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
Server-side session management for MotionEye.
Replaces per-request URL signature authentication for browser clients.
"""

import logging
import secrets
import time
from typing import Any, Dict, Optional

SESSION_COOKIE_NAME = 'meye_session'
SESSION_LIFETIME = 86400  # 24 hours
SESSION_CLEANUP_INTERVAL = 3600  # 1 hour

_sessions: Dict[str, Dict[str, Any]] = {}
_last_cleanup = 0


def create_session(username: str) -> str:
    """Create a new session and return the token."""
    token = secrets.token_hex(32)
    _sessions[token] = {
        'username': username,
        'created': time.time(),
        'last_access': time.time(),
    }
    _cleanup_sessions()
    logging.info(f'Session created for user: {username}')
    return token


def get_session(token: str) -> Optional[Dict[str, Any]]:
    """Get session data if token is valid and not expired."""
    if not token or token not in _sessions:
        return None

    session = _sessions[token]
    if time.time() - session['created'] > SESSION_LIFETIME:
        del _sessions[token]
        return None

    session['last_access'] = time.time()
    return session


def destroy_session(token: str) -> bool:
    """Destroy a session (logout)."""
    if token in _sessions:
        del _sessions[token]
        return True
    return False


def get_username_from_session(token: str) -> Optional[str]:
    """Get username from session token."""
    session = get_session(token)
    return session['username'] if session else None


def _cleanup_sessions():
    """Remove expired sessions."""
    global _last_cleanup
    current_time = time.time()

    if current_time - _last_cleanup < SESSION_CLEANUP_INTERVAL:
        return

    _last_cleanup = current_time
    expired = [
        token
        for token, sess in _sessions.items()
        if current_time - sess['created'] > SESSION_LIFETIME
    ]

    for token in expired:
        del _sessions[token]

    if expired:
        logging.debug(f'Cleaned up {len(expired)} expired sessions')
