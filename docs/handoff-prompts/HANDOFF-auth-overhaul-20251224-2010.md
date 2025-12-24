# HANDOFF: Authentication System Overhaul

**Created**: 2025-12-24 20:10
**Priority**: P1 - Critical Security
**Estimated Effort**: Large (2 major features, implement sequentially)

---

## Overview

This handoff covers a complete authentication system overhaul for MotionEye:

1. **Part A: Session Cookie Auth** - Replace URL signatures with session cookies
2. **Part B: Bcrypt Password Storage** - Replace SHA1 with bcrypt

**Execute in order**: Part A must be complete before Part B (bcrypt is too slow for per-request auth).

---

## Reference Plans

Read these before implementing:

1. `docs/plans/session-cookie-auth-migration-20251224-1930.md` - Session cookie details
2. `docs/plans/bcrypt-password-migration-20251224-2000.md` - Bcrypt migration details

---

# PART A: Session Cookie Authentication

## A1: Create Session Module

**Create**: `motioneye/session.py`

```python
"""
Server-side session management for MotionEye.
Replaces per-request URL signature authentication for browser clients.
"""

import secrets
import time
import logging
from typing import Optional, Dict, Any

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
        'last_access': time.time()
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
        token for token, sess in _sessions.items()
        if current_time - sess['created'] > SESSION_LIFETIME
    ]

    for token in expired:
        del _sessions[token]

    if expired:
        logging.debug(f'Cleaned up {len(expired)} expired sessions')
```

---

## A2: Create Login Handler

**Create**: `motioneye/handlers/login.py`

```python
"""
Login and logout handlers for session-based authentication.
"""

import hashlib
import logging

from motioneye import config, session
from motioneye.handlers.base import BaseHandler

__all__ = ('LoginHandler', 'LogoutHandler')


class LoginHandler(BaseHandler):
    """Handle user login and session creation."""

    def post(self):
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
            password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()
            if password == admin_password or password_hash == admin_password:
                authenticated_user = 'admin'

        # Check normal user credentials
        if not authenticated_user and username == normal_username:
            if not normal_password:
                # No password required for normal user
                authenticated_user = 'normal'
            else:
                password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()
                if password == normal_password or password_hash == normal_password:
                    authenticated_user = 'normal'

        if authenticated_user:
            token = session.create_session(authenticated_user)
            self.set_cookie(
                session.SESSION_COOKIE_NAME,
                token,
                httponly=True,
                samesite='Lax',
                max_age=session.SESSION_LIFETIME
            )
            logging.info(f'User {username} logged in as {authenticated_user}')
            return self.finish_json({'success': True, 'user': authenticated_user})
        else:
            logging.warning(f'Failed login attempt for user: {username}')
            self.set_status(401)
            return self.finish_json({'error': 'Invalid credentials'})


class LogoutHandler(BaseHandler):
    """Handle user logout and session destruction."""

    def post(self):
        token = self.get_cookie(session.SESSION_COOKIE_NAME)
        if token:
            session.destroy_session(token)
            logging.info('User logged out')

        self.clear_cookie(session.SESSION_COOKIE_NAME)
        return self.finish_json({'success': True})
```

---

## A3: Update `get_current_user()` in base.py

**Modify**: `motioneye/handlers/base.py`

Add import at top:
```python
from motioneye import session
```

Replace the `get_current_user()` method with this version that checks session cookies FIRST:

```python
def get_current_user(self):
    main_config = config.get_main()

    # 1. Check session cookie (preferred for browser clients)
    session_token = self.get_cookie(session.SESSION_COOKIE_NAME)
    if session_token:
        username = session.get_username_from_session(session_token)
        if username:
            return username

    # 2. HTTP Basic Auth (for API clients)
    admin_username = main_config.get('@admin_username')
    normal_username = main_config.get('@normal_username')
    admin_password = main_config.get('@admin_password')
    normal_password = main_config.get('@normal_password')

    if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
        up = utils.parse_basic_header(self.request.headers['Authorization'])
        if up:
            admin_hash = hashlib.sha1(admin_password.encode('utf-8')).hexdigest() if admin_password else ''
            normal_hash = hashlib.sha1(normal_password.encode('utf-8')).hexdigest() if normal_password else ''

            if up['username'] == admin_username and admin_password in (
                up['password'], admin_hash
            ):
                return 'admin'

            if up['username'] == normal_username and normal_password in (
                up['password'], normal_hash
            ):
                return 'normal'

    # 3. Legacy URL signatures (keep for backward compatibility)
    username = self.get_argument('_username', None)
    signature = self.get_argument('_signature', None)
    login = self.get_argument('_login', None) == 'true'
    timestamp_str = self.get_argument('_timestamp', None)
    timestamp = int(timestamp_str) if timestamp_str else None

    admin_hash = hashlib.sha1(admin_password.encode('utf-8')).hexdigest() if admin_password else ''
    normal_hash = hashlib.sha1(normal_password.encode('utf-8')).hexdigest() if normal_password else ''

    if username == admin_username and (
        utils.verify_signature(signature, self.request.method, self.request.uri, self.request.body, admin_password, timestamp)
        or utils.verify_signature(signature, self.request.method, self.request.uri, self.request.body, admin_hash, timestamp)
    ):
        return 'admin'

    # No authentication required for normal user if no password set
    if not username and not normal_password:
        return 'normal'

    if username == normal_username and (
        utils.verify_signature(signature, self.request.method, self.request.uri, self.request.body, normal_password, timestamp)
        or utils.verify_signature(signature, self.request.method, self.request.uri, self.request.body, normal_hash, timestamp)
    ):
        return 'normal'

    if username and username != '_' and login:
        logging.error(f'authentication failed for user {username}')

    return None
```

---

## A4: Add Routes

**Modify**: `motioneye/server.py`

Add import:
```python
from motioneye.handlers.login import LoginHandler, LogoutHandler
```

Add routes to the handlers list (add early, before other handlers):
```python
(r'^/login/?$', LoginHandler),
(r'^/logout/?$', LogoutHandler),
```

---

## A5: Update JavaScript

**Modify**: `motioneye/static/js/main.js`

### 5a. Add session login functions (after the cookie functions, around line 860):

```javascript
/* Session-based authentication */
function doSessionLogin(username, password, callback) {
    $.ajax({
        type: 'POST',
        url: basePath + 'login',
        data: {
            username: username,
            password: password
        },
        success: function(data) {
            if (data.success) {
                window.username = data.user;
                window._sessionAuth = true;
                if (callback) callback(true, data.user);
            } else {
                if (callback) callback(false);
            }
        },
        error: function(xhr) {
            if (callback) callback(false);
        }
    });
}

function doSessionLogout(callback) {
    $.ajax({
        type: 'POST',
        url: basePath + 'logout',
        success: function() {
            window.username = null;
            window._sessionAuth = false;
            if (callback) callback(true);
        },
        error: function() {
            if (callback) callback(false);
        }
    });
}
```

### 5b. Find the login dialog submit handler (around line 4096-4120)

Replace the authentication logic. Find this section:
```javascript
window.passwordHash = sha1(passwordEntry.val()).toLowerCase();
```

And replace the entire authentication flow in that section to use session login:

```javascript
/* Try session-based login */
doSessionLogin(usernameEntry.val(), passwordEntry.val(), function(success, userType) {
    if (success) {
        window.username = usernameEntry.val();
        hideModalDialog();
        setCookie(USERNAME_COOKIE, window.username, 3650);
        /* Session handles auth, no need to store password hash */
        if (loginDialogCallback) {
            loginDialogCallback(userType);
        }
    } else {
        passwordEntry.val('');
        passwordEntry.focus();
        showErrorMessage('Invalid credentials');
    }
});
return; /* Don't continue with old signature-based auth */
```

### 5c. Update the doLogout function (find it in the file):

```javascript
function doLogout() {
    doSessionLogout(function() {
        window.username = null;
        window._sessionAuth = false;
        setCookie(USERNAME_COOKIE, '');
        setCookie(PASSWORD_COOKIE, '');
        location.reload();
    });
}
```

---

## A6: Test Part A

Deploy to Pi 4:
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
    /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.246:~/motioneye/

ssh admin@192.168.1.246 "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"
```

Verify:
1. Clear browser cookies
2. Login → check for `meye_session` cookie
3. Access Settings panel
4. Logout → cookie cleared
5. Check logs: `sudo journalctl -u motioneye -n 50 --no-pager`

**Only proceed to Part B after Part A is verified working!**

---

# PART B: Bcrypt Password Storage

## B1: Add Bcrypt Dependency

**Modify**: `pyproject.toml`

Add to dependencies:
```toml
"bcrypt>=4.0.0",
```

---

## B2: Create Password Module

**Create**: `motioneye/passwords.py`

```python
"""
Secure password hashing utilities using bcrypt.
Replaces SHA1 hashing for password storage.
"""

import bcrypt
import hashlib
import logging
import re

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
```

---

## B3: Update Login Handler to Use Bcrypt

**Modify**: `motioneye/handlers/login.py`

Replace hashlib.sha1 with passwords module:

```python
"""
Login and logout handlers for session-based authentication.
"""

import logging

from motioneye import config, passwords, session
from motioneye.handlers.base import BaseHandler

__all__ = ('LoginHandler', 'LogoutHandler')


class LoginHandler(BaseHandler):
    """Handle user login and session creation."""

    def post(self):
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
                max_age=session.SESSION_LIFETIME
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


class LogoutHandler(BaseHandler):
    """Handle user logout and session destruction."""

    def post(self):
        token = self.get_cookie(session.SESSION_COOKIE_NAME)
        if token:
            session.destroy_session(token)
            logging.info('User logged out')

        self.clear_cookie(session.SESSION_COOKIE_NAME)
        return self.finish_json({'success': True})
```

---

## B4: Update Password Storage

**Modify**: `motioneye/config/camera/converters.py`

Add import:
```python
from motioneye import passwords
```

Find line ~166 (admin password hashing) and replace:

```python
# OLD:
if ui['admin_password']:
    data['@admin_password'] = hashlib.sha1(
        ui['admin_password'].encode('utf-8')
    ).hexdigest()

# NEW:
if ui['admin_password']:
    data['@admin_password'] = passwords.hash_password(ui['admin_password'])
```

Find line ~175 (normal password) and update:

```python
# OLD:
if ui.get('normal_password') is not None:
    data['@normal_password'] = ui['normal_password']

# NEW:
if ui.get('normal_password') is not None:
    if ui['normal_password']:
        data['@normal_password'] = passwords.hash_password(ui['normal_password'])
    else:
        data['@normal_password'] = ''
```

---

## B5: Update HTTP Basic Auth

**Modify**: `motioneye/handlers/base.py`

Add import:
```python
from motioneye import passwords
```

Update the HTTP Basic Auth section in `get_current_user()`:

```python
if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
    up = utils.parse_basic_header(self.request.headers['Authorization'])
    if up:
        if up['username'] == admin_username:
            if passwords.verify_password(up['password'], admin_password):
                return 'admin'

        if up['username'] == normal_username:
            if not normal_password or passwords.verify_password(up['password'], normal_password):
                return 'normal'
```

---

## B6: Install Bcrypt on Pi

```bash
ssh admin@192.168.1.246 "sudo pip3 install bcrypt --break-system-packages"
```

---

## B7: Test Part B

1. Deploy updated code
2. Login with existing SHA1 password → should work
3. Check logs for "upgraded to bcrypt"
4. Check config file - password should now be bcrypt format ($2b$...)
5. Login again → should work with bcrypt
6. Change password in settings → should be stored as bcrypt

---

# Sub-Agent Tasks

After implementation, spawn these sub-agents in parallel:

## Agent 1: Security Review
```
Review the authentication implementation for security issues:
1. Check session.py for token entropy and timing attacks
2. Check passwords.py for proper bcrypt usage
3. Verify cookie attributes (HttpOnly, SameSite)
4. Check for session fixation vulnerabilities
5. Verify password verification is constant-time
6. Check for authentication bypass paths
```

## Agent 2: Test Suite
```
Create comprehensive tests:
1. motioneye/tests/test_session.py - session management tests
2. motioneye/tests/test_passwords.py - password hashing tests
3. motioneye/tests/test_login.py - login handler tests
Include tests for:
- Session creation, retrieval, expiration, destruction
- Bcrypt hashing and verification
- SHA1 legacy verification and upgrade
- Plaintext legacy verification and upgrade
- Login success and failure cases
- Logout clearing session
```

## Agent 3: Code Cleanup
```
After verification, clean up old code:
1. Remove unused signature code from main.js:
   - hmacSha256 function
   - encodeURIComponentRFC3986 function
   - computeSignature function
   - addAuthParams function (but check all call sites first!)
2. Remove PASSWORD_COOKIE usage if no longer needed
3. Remove passwordHash global variable if unused
4. Keep sha1 function (still used for password hashing at login form)
5. Keep remote.py signature code (still needed for remote cameras)
```

---

# Success Criteria

## Part A (Session Cookies)
- [ ] Login creates session cookie
- [ ] Session cookie has HttpOnly and SameSite attributes
- [ ] Authenticated requests succeed
- [ ] Logout clears session
- [ ] HTTP Basic Auth still works
- [ ] Remote cameras still work

## Part B (Bcrypt)
- [ ] New passwords stored as bcrypt
- [ ] Login works with bcrypt passwords
- [ ] Login works with legacy SHA1 (auto-upgrade)
- [ ] Password upgrade logged
- [ ] HTTP Basic Auth works with bcrypt

---

# Rollback

## Part A Rollback
- Session code is additive, signatures still work
- Clear cookies to force signature auth
- Revert if needed

## Part B Rollback
- passwords.verify_password() accepts all formats
- Existing SHA1/plaintext continue to work
- No forced rollback needed

---

**Execute Part A first, verify, then Part B. Use sub-agents for parallel review and testing.**
