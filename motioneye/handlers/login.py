# Copyright (c) 2020 Vlsarro
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
Module: Login authentication handler for session-based and legacy authentication
Classes: LoginHandler
"""

import logging

from motioneye import config, passwords, session
from motioneye.handlers.base import BaseHandler

__all__ = ('LoginHandler',)


class LoginHandler(BaseHandler):
    """Handle user login and session creation."""

    @BaseHandler.auth()
    def get(self):
        """Legacy: trigger login mechanism on client side."""
        self.finish_json()

    def post(self):
        """Handle session-based login via POST request."""
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')

        main_config = config.get_main()
        admin_username = main_config.get('@admin_username')
        admin_password = main_config.get('@admin_password')
        normal_username = main_config.get('@normal_username')
        normal_password = main_config.get('@normal_password')

        authenticated_user = None

        # Check admin credentials
        if username == admin_username and admin_password:
            if passwords.verify_password(password, admin_password):
                authenticated_user = 'admin'
                # Upgrade legacy hash to bcrypt
                if passwords.needs_upgrade(admin_password):
                    self._upgrade_password('@admin_password', password)

        # Check normal user credentials
        if not authenticated_user and username == normal_username:
            if not normal_password:
                authenticated_user = 'normal'
            elif passwords.verify_password(password, normal_password):
                authenticated_user = 'normal'
                if passwords.needs_upgrade(normal_password):
                    self._upgrade_password('@normal_password', password)

        if authenticated_user:
            token = session.create_session(authenticated_user)
            self.set_cookie(
                session.SESSION_COOKIE_NAME,
                token,
                httponly=True,
                samesite='Lax',
                max_age=session.SESSION_LIFETIME,
            )
            logging.info(f'User {username} logged in as {authenticated_user}')
            return self.finish_json({'success': True, 'user': authenticated_user})
        else:
            logging.warning(f'Failed login attempt for user: {username}')
            self.set_status(401)
            return self.finish_json({'error': 'Invalid credentials'})

    def _upgrade_password(self, key: str, password: str):
        """Upgrade password hash to bcrypt."""
        try:
            main_config = config.get_main()
            main_config[key] = passwords.hash_password(password)
            config.set_main(main_config)
            logging.info(f'{key} upgraded to bcrypt')
        except Exception as e:
            logging.error(f'Failed to upgrade {key}: {e}')
