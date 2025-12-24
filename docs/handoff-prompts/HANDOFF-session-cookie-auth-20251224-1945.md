# HANDOFF: Session Cookie Authentication Implementation

**Created**: 2025-12-24 19:45
**Priority**: P1 - Critical
**Estimated Effort**: Medium (5 phases, ~200 lines new, ~400 lines removed)

---

## Context

MotionEye has had persistent login failures due to a brittle URL signature authentication system that requires identical URL encoding between JavaScript and Python. After multiple failed fix attempts, we've decided to replace it with standard session cookie authentication.

**Read the plan first**: `docs/plans/session-cookie-auth-migration-20251224-1930.md`

---

## Your Mission

Implement session cookie authentication to replace URL signatures for browser clients. Use sub-agents for parallel work where possible.

---

## Phase 1: Create Session Module

**Create new file**: `motioneye/session.py`

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

## Phase 2: Add Login/Logout Handlers

**Modify**: `motioneye/handlers/base.py`

1. Add import at top:
```python
from motioneye import session
```

2. Add to `__all__`:
```python
__all__ = ('BaseHandler', 'NotFoundHandler', 'ManifestHandler', 'CsrfTokenHandler', 'LoginHandler', 'LogoutHandler')
```

3. Add new handler classes (after `CsrfTokenHandler`):

```python
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

## Phase 3: Update `get_current_user()` Method

**Modify**: `motioneye/handlers/base.py` - `get_current_user()` method

Replace the entire method with this version that checks session cookies FIRST:

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
            if up['username'] == admin_username and admin_password in (
                up['password'],
                hashlib.sha1(up['password'].encode('utf-8')).hexdigest(),
            ):
                return 'admin'

            if up['username'] == normal_username and normal_password in (
                up['password'],
                hashlib.sha1(up['password'].encode('utf-8')).hexdigest(),
            ):
                return 'normal'

    # 3. Legacy URL signatures (keep for backward compatibility during migration)
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

## Phase 4: Add Routes

**Modify**: `motioneye/server.py`

1. Find the imports section and add:
```python
from motioneye.handlers.base import LoginHandler, LogoutHandler
```

2. Find the `handlers = [` list and add these routes (add near the top of the list, before config handlers):
```python
(r'^/login/?$', LoginHandler),
(r'^/logout/?$', LogoutHandler),
```

---

## Phase 5: Update JavaScript

**Modify**: `motioneye/static/js/main.js`

### 5a. Add new login/logout functions (add near the cookie functions around line 860):

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

### 5b. Modify the login dialog submit handler

Find the login dialog code (around line 4040-4060). The current code computes `passwordHash` and uses signatures. Replace the authentication part to try session login first:

Find this section:
```javascript
window.passwordHash = sha1(passwordEntry.val()).toLowerCase();
```

And modify the login flow to use session auth:

```javascript
/* Try session-based login first */
doSessionLogin(usernameEntry.val(), passwordEntry.val(), function(success, userType) {
    if (success) {
        window.username = usernameEntry.val();
        hideModalDialog();
        setCookie(USERNAME_COOKIE, window.username, 3650);
        /* Don't store password hash in cookie anymore - session handles it */
        if (loginDialogCallback) {
            loginDialogCallback(userType);
        }
    } else {
        /* Session login failed */
        passwordEntry.val('');
        passwordEntry.focus();
        showErrorMessage('Invalid credentials');
    }
});
return; /* Don't continue with old signature-based auth */
```

### 5c. Update logout function

Find `doLogout()` function and update it:

```javascript
function doLogout() {
    /* Clear session on server */
    doSessionLogout(function() {
        /* Clear local state */
        window.username = null;
        window._sessionAuth = false;
        setCookie(USERNAME_COOKIE, '');
        setCookie(PASSWORD_COOKIE, '');
        location.reload();
    });
}
```

---

## Verification Steps

After implementation, verify on Pi 4 (192.168.1.246):

### 1. Deploy and restart:
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
    /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.246:~/motioneye/

ssh admin@192.168.1.246 "cd ~/motioneye && sudo pip3 install . --break-system-packages && sudo systemctl restart motioneye"
```

### 2. Check logs for errors:
```bash
ssh admin@192.168.1.246 "sudo journalctl -u motioneye -n 50 --no-pager"
```

### 3. Test login flow:
- Clear browser cookies
- Navigate to http://192.168.1.246:8765/
- Login with admin credentials
- Check for `meye_session` cookie in browser dev tools
- Verify Settings panel is accessible
- Check server logs for "Session created for user: admin"

### 4. Test logout:
- Click logout
- Verify `meye_session` cookie is cleared
- Verify Settings panel shows login prompt

---

## Sub-Agent Tasks (Parallel Execution)

After implementation, spawn these sub-agents:

### Agent 1: Code Review
```
Review the session cookie implementation for security issues:
1. Check session.py for token security (sufficient entropy, timing attacks)
2. Check LoginHandler for authentication bypass vulnerabilities
3. Verify cookie attributes (HttpOnly, SameSite) are properly set
4. Check for session fixation vulnerabilities
5. Verify logout properly clears sessions
```

### Agent 2: Test Coverage
```
Create test file test_session_auth.py with:
1. Unit tests for session.py (create, get, destroy, expiration)
2. Integration tests for LoginHandler (success, failure, wrong password)
3. Integration tests for LogoutHandler
4. Test session cookie attributes
```

### Agent 3: JavaScript Review
```
Review main.js changes for:
1. Proper error handling in doSessionLogin/doSessionLogout
2. No remaining calls to addAuthParams that should use session
3. Cookie cleanup on logout
4. Backward compatibility with existing cookie-based state
```

---

## Important Notes

1. **Keep signature code during migration** - Don't delete `utils.compute_signature()` or `utils.verify_signature()` yet. They're needed for:
   - Backward compatibility with old browser sessions
   - Remote camera communication (`remote.py`)

2. **Test on Pi 4 first** - Don't deploy to Pi 5 until Pi 4 is verified working

3. **Check for 403 errors** - The most common issue. If you see 403s after login, the session cookie isn't being read properly.

4. **Browser cache** - Hard refresh (Ctrl+Shift+R) to ensure new JS is loaded

---

## Success Criteria

- [ ] Login creates session cookie with correct attributes
- [ ] Authenticated requests succeed (no 403)
- [ ] Logout clears session
- [ ] Settings panel accessible after login
- [ ] No JavaScript errors in browser console
- [ ] Server logs show "Session created" on login
- [ ] HTTP Basic Auth still works (for API clients)
- [ ] Remote cameras still work (signature auth still in remote.py)

---

## Rollback

If session auth fails:
1. The signature code is still present and working
2. Clear browser cookies to force signature-based auth
3. Revert changes if necessary

---

**Execute this plan. Use sub-agents for code review and testing after implementation is complete.**
