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
Secure password hashing utilities using bcrypt.
Replaces SHA1 hashing for password storage.
"""

import hashlib
import logging
import re

import bcrypt

BCRYPT_COST = 12  # ~250ms per hash
BCRYPT_REGEX = re.compile(r'^\$2[aby]?\$\d{2}\$[./A-Za-z0-9]{53}$')
SHA1_REGEX = re.compile(r'^[a-f0-9]{40}$')


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    if not password:
        return ''

    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.
    Supports bcrypt, SHA1 (legacy), and plaintext (legacy).
    """
    if not password or not stored_hash:
        return password == stored_hash

    password_bytes = password.encode('utf-8')

    # Check bcrypt
    if is_bcrypt_hash(stored_hash):
        try:
            return bcrypt.checkpw(password_bytes, stored_hash.encode('utf-8'))
        except Exception as e:
            logging.error(f'Bcrypt verification failed: {e}')
            return False

    # Check SHA1 (legacy)
    if is_sha1_hash(stored_hash):
        password_sha1 = hashlib.sha1(password_bytes).hexdigest()
        return password_sha1 == stored_hash

    # Plaintext comparison (very old configs)
    return password == stored_hash


def is_bcrypt_hash(value: str) -> bool:
    """Check if value is a bcrypt hash."""
    return bool(value and BCRYPT_REGEX.match(value))


def is_sha1_hash(value: str) -> bool:
    """Check if value is a SHA1 hash."""
    return bool(value and SHA1_REGEX.match(value))


def needs_upgrade(stored_hash: str) -> bool:
    """Check if stored hash should be upgraded to bcrypt."""
    if not stored_hash:
        return False
    if is_bcrypt_hash(stored_hash):
        return False
    return True
