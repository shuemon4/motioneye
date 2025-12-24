# Session Cookie Authentication Migration Plan

**Date**: 2025-12-24 19:30
**Status**: Implementation Plan
**Priority**: P1 - Critical (Replaces brittle v2 signature system)

---

## Executive Summary

Replace the current per-request URL signature system (v1 SHA-1 and v2 HMAC-SHA256) with standard server-side session cookie authentication for browser clients. This eliminates the cross-language URL canonicalization problem that has caused repeated login failures.

---

## Problem Statement

The current signature-based authentication requires **identical URL encoding** between JavaScript and Python. This is fundamentally brittle because:

1. `encodeURIComponent()` (JS) and `urllib.parse.quote()` (Python) treat special characters differently
2. Parameter ordering must be byte-identical
3. Every edge case (unicode, special chars, binary data) can cause signature mismatch
4. Debugging is extremely difficult - requires comparing exact byte outputs

**Evidence**: Multiple failed fix attempts (`v2-signature-fix-completion-20251224-1730.md`, etc.) despite "successful" deployments.

---

## Solution: Session Cookie Authentication

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      CURRENT SYSTEM (Broken)                     │
├─────────────────────────────────────────────────────────────────┤
│  Browser ─────► Every Request Signed ─────► Python Verifies     │
│                 (URL encoding must match)                        │
│                                                                  │
│  Problem: JS encodeURIComponent() ≠ Python urllib.parse.quote() │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      NEW SYSTEM (Standard)                       │
├─────────────────────────────────────────────────────────────────┤
│  Browser ─────► POST /login ─────► Python Sets Cookie           │
│                 (username+password)  (session token)             │
│                                                                  │
│  Browser ─────► All Requests ─────► Cookie Checked              │
│                 (cookie auto-sent)   (simple lookup)             │
│                                                                  │
│  No encoding issues - cookie is opaque token                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Session Token Design

```python
Session Cookie:
  Name: meye_session
  Value: <random-64-byte-hex-token>
  Attributes:
    - HttpOnly: true    # JS cannot read (XSS protection)
    - Secure: true      # HTTPS only (if enabled)
    - SameSite: Lax     # CSRF protection
    - Path: /           # All routes
    - Max-Age: 86400    # 24 hours (configurable)
```

### Session Storage

```python
# In-memory session store (simple, sufficient for single-server)
_sessions = {
    "token123...": {
        "username": "admin",
        "created": 1735059000,
        "last_access": 1735060000
    }
}

# Future: Redis/file-based for multi-server setups
```

---

## Implementation Phases

### Phase 1: Add Session Infrastructure (Python)

**New file: `motioneye/session.py`**

```python
"""
Server-side session management for MotionEye.
Replaces per-request URL signature authentication.
"""

import secrets
import time
import logging
from typing import Optional, Dict, Any

# Session configuration
SESSION_COOKIE_NAME = 'meye_session'
SESSION_LIFETIME = 86400  # 24 hours
SESSION_CLEANUP_INTERVAL = 3600  # 1 hour

# In-memory session store
_sessions: Dict[str, Dict[str, Any]] = {}
_last_cleanup = 0


def create_session(username: str) -> str:
    """Create a new session and return the token."""
    token = secrets.token_hex(32)  # 64-char hex string
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

    # Check expiration
    if time.time() - session['created'] > SESSION_LIFETIME:
        del _sessions[token]
        return None

    # Update last access time
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
    """Remove expired sessions to prevent memory growth."""
    global _last_cleanup
    current_time = time.time()

    if current_time - _last_cleanup < SESSION_CLEANUP_INTERVAL:
        return

    _last_cleanup = current_time
    expired = [
        token for token, session in _sessions.items()
        if current_time - session['created'] > SESSION_LIFETIME
    ]

    for token in expired:
        del _sessions[token]

    if expired:
        logging.debug(f'Cleaned up {len(expired)} expired sessions')
```

---

### Phase 2: Add Login/Logout Endpoints

**Modify: `motioneye/handlers/base.py`**

```python
# Add new imports
from motioneye import session

# Add LoginHandler class
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
        if username == admin_username:
            password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()
            if password == admin_password or password_hash == admin_password:
                authenticated_user = 'admin'

        # Check normal user credentials
        elif username == normal_username:
            password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()
            if password == normal_password or password_hash == normal_password:
                authenticated_user = 'normal'

        if authenticated_user:
            # Create session and set cookie
            token = session.create_session(authenticated_user)
            self.set_cookie(
                session.SESSION_COOKIE_NAME,
                token,
                httponly=True,
                secure=settings.HTTPS,  # Only set Secure if HTTPS enabled
                samesite='Lax',
                max_age=session.SESSION_LIFETIME
            )
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

        self.clear_cookie(session.SESSION_COOKIE_NAME)
        return self.finish_json({'success': True})
```

---

### Phase 3: Update Authentication Check

**Modify: `motioneye/handlers/base.py` - `get_current_user()`**

```python
def get_current_user(self):
    main_config = config.get_main()

    # === NEW: Check session cookie first ===
    session_token = self.get_cookie(session.SESSION_COOKIE_NAME)
    if session_token:
        username = session.get_username_from_session(session_token)
        if username:
            return username  # 'admin' or 'normal'

    # === LEGACY: HTTP Basic Auth (keep for API clients) ===
    if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
        up = utils.parse_basic_header(self.request.headers['Authorization'])
        if up:
            admin_username = main_config.get('@admin_username')
            admin_password = main_config.get('@admin_password')
            normal_username = main_config.get('@normal_username')
            normal_password = main_config.get('@normal_password')

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

    # === LEGACY: URL signatures (keep during migration, remove later) ===
    # ... existing signature code stays for backward compatibility ...

    # No authentication for anonymous normal user
    normal_password = main_config.get('@normal_password')
    if not normal_password:
        return 'normal'

    return None
```

---

### Phase 4: Simplify JavaScript

**Modify: `motioneye/static/js/main.js`**

```javascript
// ============================================================
// REMOVE THESE (no longer needed):
// ============================================================
// - var passwordHash = '';
// - var hmacSha256 = (function() {...})();
// - var sha256 = (function() {...})();
// - function encodeURIComponentRFC3986(str) {...}
// - function computeSignature(method, path, body) {...}
// - function addAuthParams(method, url, body) {...}
// - PASSWORD_COOKIE usage (meye_password_hash)

// ============================================================
// SIMPLIFY ajax() function:
// ============================================================
function ajax(method, url, data, successHandler, errorHandler, options) {
    // No more addAuthParams() call needed!
    // Cookie is automatically sent by browser

    url = qualifyPath(url);

    var processData = true;
    var contentType = 'application/x-www-form-urlencoded; charset=UTF-8';

    // ... rest of ajax options ...

    $.ajax({
        type: method,
        url: url,  // No signature added!
        data: data,
        // ... rest of options ...
    });
}

// ============================================================
// NEW: Simple login function
// ============================================================
function doLogin(username, password, callback) {
    $.ajax({
        type: 'POST',
        url: basePath + 'login',
        data: {
            username: username,
            password: password
        },
        success: function(data) {
            window.username = data.user;
            if (callback) callback(true);
        },
        error: function() {
            if (callback) callback(false);
        }
    });
}

function doLogout(callback) {
    $.ajax({
        type: 'POST',
        url: basePath + 'logout',
        success: function() {
            window.username = null;
            if (callback) callback();
        }
    });
}
```

---

### Phase 5: Add Routes

**Modify: `motioneye/server.py`**

```python
from motioneye.handlers.base import LoginHandler, LogoutHandler

# Add to handlers list:
handlers = [
    # ... existing handlers ...
    (r'^/login/?$', LoginHandler),
    (r'^/logout/?$', LogoutHandler),
]
```

---

## Code to Remove

### JavaScript (`main.js`) - Lines to Delete

| Line Range | Description |
|------------|-------------|
| 19 | `var passwordHash = '';` |
| 394-474 | SHA1 implementation (keep for password hashing at login only) |
| 475-550 | SHA256 implementation |
| 551-590 | HMAC-SHA256 implementation |
| 591-661 | `encodeURIComponentRFC3986()` function |
| 663-709 | `computeSignature()` function |
| 711-739 | `addAuthParams()` function |
| All calls to `addAuthParams()` | ~10 locations |

**Approximate reduction: ~300 lines of complex crypto code**

### Python (`utils/__init__.py`) - Lines to Delete

| Line Range | Description |
|------------|-------------|
| 41 | `_SIGNATURE_REGEX` pattern |
| 242-278 | `compute_signature()` v1 function |
| 279 | `SIGNATURE_TIMESTAMP_TOLERANCE` |
| 282-319 | `compute_signature_v2()` function |
| 322-386 | `verify_signature()` function |

**Approximate reduction: ~100 lines**

### Python (`handlers/base.py`) - Lines to Simplify

| Line Range | Description |
|------------|-------------|
| 111-116 | Remove `_signature` and `_timestamp` argument parsing |
| 147-188 | Remove signature verification logic |

---

## What to Keep

### 1. Remote Camera Signatures (`remote.py`)

The signature system is **still needed** for server-to-server communication between MotionEye instances. When a "hub" MotionEye connects to a "remote" MotionEye:

```python
# remote.py line 63
url += '&_signature=' + utils.compute_signature(method, url, data, password)
```

**Keep**: `utils.compute_signature()` for remote camera use only.

### 2. HTTP Basic Auth

Keep for API clients that don't use browser cookies:

```python
if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
    # ... verify basic auth ...
```

### 3. SHA1 for Password Hashing

Keep SHA1 in JavaScript for hashing password before sending to server (existing password storage uses SHA1). This is separate from request signing.

```javascript
// Keep this for password hashing at login
var sha1 = (function () { ... })();

// Login form handler
password_hash = sha1(passwordEntry.val()).toLowerCase();
```

---

## Migration Path

### Step 1: Deploy with Both Systems Active

1. Add session cookie authentication
2. Keep signature auth working (fallback)
3. All new logins use sessions
4. Old clients with signatures still work

### Step 2: Monitor and Validate (1-2 weeks)

1. Check logs for session vs signature usage
2. Verify no authentication failures
3. Test all browsers (Chrome, Firefox, Safari, mobile)

### Step 3: Remove Signature Code

1. Delete JavaScript signature code
2. Simplify Python authentication
3. Keep only remote camera signatures

---

## Testing Plan

### Unit Tests

```python
# test_session.py

def test_create_session():
    token = session.create_session('admin')
    assert len(token) == 64
    assert session.get_username_from_session(token) == 'admin'

def test_session_expiration():
    token = session.create_session('admin')
    # Mock time to be past expiration
    session._sessions[token]['created'] -= session.SESSION_LIFETIME + 1
    assert session.get_session(token) is None

def test_logout_destroys_session():
    token = session.create_session('admin')
    session.destroy_session(token)
    assert session.get_session(token) is None
```

### Integration Tests

1. Login with correct credentials → session cookie set
2. Login with wrong credentials → 401 error
3. Access protected endpoint with session cookie → success
4. Access protected endpoint without cookie → 403
5. Logout → cookie cleared, session destroyed
6. Access after logout → 403

### Browser Tests

1. Chrome, Firefox, Safari, Edge
2. Mobile browsers (iOS Safari, Android Chrome)
3. Incognito/private modes
4. Cookie blocking scenarios

---

## Rollback Plan

If session auth has issues:

1. The signature system remains active during migration
2. Users can clear cookies and use signature auth
3. Disable session auth via config flag if needed

---

## Security Considerations

### Improvements Over Signatures

| Aspect | Signatures | Session Cookies |
|--------|-----------|-----------------|
| XSS Protection | Low (hash in JS) | High (HttpOnly) |
| CSRF Protection | None | SameSite attribute |
| Replay Protection | Timestamp-based | Unique session token |
| Credential Exposure | Hash in every URL | Hash sent once at login |

### Additional Recommendations

1. **Rate limiting**: Add login attempt limiting (e.g., 5 attempts per minute)
2. **Session rotation**: Generate new token after privilege change
3. **Secure flag**: Set when HTTPS is enabled
4. **Audit logging**: Log login/logout events

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `motioneye/session.py` | **CREATE** | New session management module |
| `motioneye/handlers/base.py` | MODIFY | Add LoginHandler, LogoutHandler, update get_current_user() |
| `motioneye/server.py` | MODIFY | Add /login and /logout routes |
| `motioneye/static/js/main.js` | MODIFY | Remove signature code, simplify ajax() |
| `motioneye/utils/__init__.py` | MODIFY | Remove v2 signature code (keep v1 for remote) |
| `test_session.py` | **CREATE** | Unit tests for session management |
| `test_v2_signatures.py` | DELETE | No longer needed |

---

## Timeline

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Add session infrastructure | ~50 lines Python |
| 2 | Add login/logout endpoints | ~60 lines Python |
| 3 | Update auth check | ~20 lines Python |
| 4 | Simplify JavaScript | -300 lines JS |
| 5 | Add routes | ~5 lines Python |
| 6 | Testing | All browsers/scenarios |
| 7 | Remove old code | -100 lines Python |

**Net result**: Simpler, more maintainable, more secure.

---

## Success Criteria

- [ ] Login works with session cookies in all browsers
- [ ] Logout properly clears session
- [ ] Protected endpoints require authentication
- [ ] HTTP Basic Auth still works for API clients
- [ ] Remote camera communication still works
- [ ] No 403 errors for authenticated users
- [ ] ~400 lines of complex crypto code removed

---

## References

- `docs/analysis/login-cookie.md` - Original proposal
- `docs/summaries/v2-signature-deployment-success-20251224-1815.md` - Previous attempt
- OWASP Session Management Cheat Sheet
- Tornado RequestHandler cookie methods

---

**Plan created by**: Claude Code
**Date**: 2025-12-24
**Next Action**: Implement Phase 1 (session.py)
