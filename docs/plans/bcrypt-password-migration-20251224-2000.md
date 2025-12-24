# Bcrypt Password Storage Migration Plan

**Date**: 2025-12-24 20:00
**Status**: Implementation Plan
**Priority**: P2 - Security Enhancement
**Dependency**: Implement after session cookie auth (session-cookie-auth-migration-20251224-1930.md)

---

## Executive Summary

Replace SHA1 password hashing with bcrypt for secure password storage. SHA1 is cryptographically broken and unsuitable for password hashing - it's fast (bad for passwords), has known collision attacks, and lacks salting.

---

## Current State Analysis

### Password Storage Locations

| Location | Purpose | Current Format | Notes |
|----------|---------|----------------|-------|
| `@admin_password` in config | Admin password | SHA1 hex (40 chars) or plaintext | Main config file |
| `@normal_password` in config | Normal user password | Plaintext | Never hashed! |
| `@password` in camera config | Remote camera password | Plaintext | For remote MotionEye connections |

### Code Paths Using Passwords

1. **Login Authentication** (`handlers/base.py`, `handlers/login.py`):
   - Compares input against stored SHA1 hash
   - Also accepts plaintext (for backward compat)

2. **Password Setting** (`config/camera/converters.py:166`):
   - Hashes admin password with SHA1 on save
   - Stores normal_password as plaintext (!)

3. **Remote Camera Auth** (`remote.py`):
   - Uses `@password` from config
   - Computes URL signatures for server-to-server auth

4. **HTTP Basic Auth** (`handlers/base.py`):
   - Accepts plaintext or SHA1 hash

---

## Critical Discovery: Two Different Use Cases

### Use Case 1: Local Password Storage (Needs Bcrypt)
- Admin password stored in config
- Normal user password stored in config
- **Goal**: Hash with bcrypt for secure storage

### Use Case 2: Remote Camera Signatures (Needs Shared Secret)
- Remote MotionEye instances authenticate via URL signatures
- Both sides must compute identical HMAC using shared secret
- **Constraint**: Cannot use bcrypt (one-way hash doesn't work for HMAC)

### Solution: Separate the Concerns

| Password Type | Storage | Usage |
|--------------|---------|-------|
| Admin password | **Bcrypt hash** | Local login verification |
| Normal password | **Bcrypt hash** | Local login verification |
| Remote camera password | **Plaintext** (or encrypted at rest) | HMAC signature computation |

---

## Why Bcrypt?

| Feature | SHA1 | Bcrypt |
|---------|------|--------|
| Speed | Very fast (~1B hashes/sec) | Intentionally slow (configurable) |
| Salt | None (must add manually) | Built-in per-password salt |
| Work Factor | Fixed | Adjustable (future-proof) |
| Collision Resistance | Broken | Strong |
| Purpose | General hashing | Password hashing |
| Rainbow Table Resistance | None | Strong (due to salt) |

**Bcrypt cost factor**: We'll use cost=12 (default), which takes ~250ms per hash. This is acceptable for login (happens rarely) but makes brute-force attacks impractical.

---

## Implementation Plan

### Phase 1: Add Bcrypt Dependency

**Modify**: `pyproject.toml`

```toml
dependencies = [
  "tornado>=6.5.0",
  "jinja2",
  "pillow",
  "pycurl",
  "babel",
  "bcrypt>=4.0.0",  # Add this line
  ...
]
```

---

### Phase 2: Create Password Utility Module

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

# Bcrypt cost factor (2^12 = 4096 iterations, ~250ms per hash)
BCRYPT_COST = 12

# Regex to detect bcrypt hash format
BCRYPT_REGEX = re.compile(r'^\$2[aby]?\$\d{2}\$[./A-Za-z0-9]{53}$')

# Regex to detect SHA1 hash format (40 hex chars)
SHA1_REGEX = re.compile(r'^[a-f0-9]{40}$')


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plaintext password

    Returns:
        Bcrypt hash string (60 chars)
    """
    if not password:
        return ''

    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash.
    Supports bcrypt (preferred), SHA1 (legacy), and plaintext (legacy).

    Args:
        password: Plaintext password to verify
        stored_hash: Stored password hash or plaintext

    Returns:
        True if password matches, False otherwise
    """
    if not password or not stored_hash:
        # Empty password matches empty stored value
        return password == stored_hash

    password_bytes = password.encode('utf-8')

    # Check if stored value is bcrypt hash
    if is_bcrypt_hash(stored_hash):
        try:
            return bcrypt.checkpw(password_bytes, stored_hash.encode('utf-8'))
        except Exception as e:
            logging.error(f'Bcrypt verification failed: {e}')
            return False

    # Check if stored value is SHA1 hash (legacy)
    if is_sha1_hash(stored_hash):
        password_sha1 = hashlib.sha1(password_bytes).hexdigest()
        return password_sha1 == stored_hash

    # Fall back to plaintext comparison (very old configs)
    return password == stored_hash


def is_bcrypt_hash(value: str) -> bool:
    """Check if value is a bcrypt hash."""
    return bool(value and BCRYPT_REGEX.match(value))


def is_sha1_hash(value: str) -> bool:
    """Check if value is a SHA1 hash (40 hex chars)."""
    return bool(value and SHA1_REGEX.match(value))


def needs_upgrade(stored_hash: str) -> bool:
    """
    Check if stored password hash should be upgraded to bcrypt.

    Returns True for SHA1 hashes and plaintext passwords.
    Returns False for bcrypt hashes and empty values.
    """
    if not stored_hash:
        return False

    if is_bcrypt_hash(stored_hash):
        return False

    return True  # SHA1 or plaintext needs upgrade


def upgrade_hash_on_login(password: str, stored_hash: str, save_callback) -> None:
    """
    Upgrade password hash to bcrypt on successful login.

    This is called after successful verification to transparently
    upgrade legacy SHA1/plaintext passwords to bcrypt.

    Args:
        password: Verified plaintext password
        stored_hash: Current stored hash (SHA1 or plaintext)
        save_callback: Function to call with new bcrypt hash
    """
    if needs_upgrade(stored_hash):
        new_hash = hash_password(password)
        try:
            save_callback(new_hash)
            logging.info('Password hash upgraded to bcrypt')
        except Exception as e:
            logging.error(f'Failed to upgrade password hash: {e}')
```

---

### Phase 3: Update Password Storage on Save

**Modify**: `motioneye/config/camera/converters.py`

Replace SHA1 hashing with bcrypt:

```python
# Old code (line 164-168):
if ui['admin_password']:
    data['@admin_password'] = hashlib.sha1(
        ui['admin_password'].encode('utf-8')
    ).hexdigest()

# New code:
from motioneye import passwords

if ui['admin_password']:
    data['@admin_password'] = passwords.hash_password(ui['admin_password'])
```

Also update normal_password to use hashing:

```python
# Old code (line 175-176):
if ui.get('normal_password') is not None:
    data['@normal_password'] = ui['normal_password']

# New code:
if ui.get('normal_password') is not None:
    if ui['normal_password']:
        data['@normal_password'] = passwords.hash_password(ui['normal_password'])
    else:
        data['@normal_password'] = ''
```

---

### Phase 4: Update Login Verification

**Modify**: `motioneye/handlers/login.py`

Replace SHA1 comparison with password verification:

```python
from motioneye import passwords

class LoginHandler(BaseHandler):
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
                # Upgrade hash if needed (transparent migration)
                if passwords.needs_upgrade(admin_password):
                    self._upgrade_admin_password(password)

        # Check normal user credentials
        if not authenticated_user and username == normal_username:
            if not normal_password:
                authenticated_user = 'normal'
            elif passwords.verify_password(password, normal_password):
                authenticated_user = 'normal'
                if passwords.needs_upgrade(normal_password):
                    self._upgrade_normal_password(password)

        # ... rest of login logic ...

    def _upgrade_admin_password(self, password):
        """Upgrade admin password to bcrypt on successful login."""
        try:
            main_config = config.get_main()
            main_config['@admin_password'] = passwords.hash_password(password)
            config.set_main(main_config)
            logging.info('Admin password upgraded to bcrypt')
        except Exception as e:
            logging.error(f'Failed to upgrade admin password: {e}')

    def _upgrade_normal_password(self, password):
        """Upgrade normal password to bcrypt on successful login."""
        try:
            main_config = config.get_main()
            main_config['@normal_password'] = passwords.hash_password(password)
            config.set_main(main_config)
            logging.info('Normal password upgraded to bcrypt')
        except Exception as e:
            logging.error(f'Failed to upgrade normal password: {e}')
```

---

### Phase 5: Update HTTP Basic Auth

**Modify**: `motioneye/handlers/base.py`

Update `get_current_user()` to use password verification:

```python
from motioneye import passwords

# In HTTP Basic Auth section:
if settings.HTTP_BASIC_AUTH and 'Authorization' in self.request.headers:
    up = utils.parse_basic_header(self.request.headers['Authorization'])
    if up:
        if up['username'] == admin_username:
            if passwords.verify_password(up['password'], admin_password):
                return 'admin'

        if up['username'] == normal_username:
            if passwords.verify_password(up['password'], normal_password):
                return 'normal'
```

---

### Phase 6: Keep Remote Camera Auth Unchanged

**Important**: The remote camera authentication in `remote.py` uses URL signatures computed with HMAC. This requires a shared secret, NOT a one-way hash.

**DO NOT CHANGE**:
- `remote.py` - continues using `@password` for signature computation
- `utils.compute_signature()` - still needed for remote cameras
- Camera config `@password` field - stays as plaintext (or add encryption at rest later)

The remote camera password (`@password`) is separate from admin/normal passwords (`@admin_password`, `@normal_password`).

---

## Migration Strategy: Transparent Upgrade

### How It Works

1. **On Password Set** (new passwords):
   - Always hash with bcrypt
   - Store bcrypt hash in config

2. **On Login** (existing passwords):
   - `verify_password()` detects hash type (bcrypt/SHA1/plaintext)
   - Verifies against appropriate algorithm
   - If verification succeeds AND hash is legacy:
     - Compute bcrypt hash
     - Save to config
     - Log "Password upgraded to bcrypt"

3. **Result**:
   - No forced password resets
   - Users automatically upgraded on next login
   - New installations always use bcrypt

### Backward Compatibility Matrix

| Stored Format | Login Works? | Auto-Upgrade? |
|--------------|--------------|---------------|
| Bcrypt hash | Yes | No (already secure) |
| SHA1 hash | Yes | Yes (on next login) |
| Plaintext | Yes | Yes (on next login) |
| Empty | Yes (no password) | No |

---

## Code to Remove (After Migration Period)

After 6-12 months when all users have logged in at least once:

### Keep Forever (for remote cameras)
- `utils.compute_signature()` - needed for remote camera auth
- `utils.verify_signature()` - needed for remote camera auth

### Can Remove Later
- SHA1 fallback in `passwords.verify_password()` (but low risk to keep)
- Plaintext fallback (but low risk to keep)

**Recommendation**: Keep the fallbacks indefinitely - they're minimal code and prevent lockouts for users who upgrade after long periods.

---

## Security Considerations

### Password Timing Attacks

Bcrypt's `checkpw()` is designed to be constant-time for valid hashes. However, we should ensure error paths don't leak timing info:

```python
# Good: Both paths take similar time
if passwords.verify_password(password, stored_hash):
    return 'admin'
else:
    time.sleep(0.1)  # Add delay on failure to prevent timing attacks
    return None
```

### Rate Limiting

With session cookies + bcrypt, add login rate limiting:

```python
# Future enhancement: Track failed attempts
LOGIN_ATTEMPTS = {}  # {ip: [timestamp, timestamp, ...]}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300

def check_rate_limit(ip):
    # ... implementation ...
```

### Password Complexity

Consider adding password validation:

```python
MIN_PASSWORD_LENGTH = 8

def validate_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    return True, None
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | MODIFY | Add bcrypt dependency |
| `motioneye/passwords.py` | **CREATE** | New password utilities module |
| `motioneye/config/camera/converters.py` | MODIFY | Use bcrypt for password storage |
| `motioneye/handlers/login.py` | MODIFY | Use verify_password(), add upgrade |
| `motioneye/handlers/base.py` | MODIFY | Update HTTP Basic Auth |

### Files NOT Changed

| File | Reason |
|------|--------|
| `motioneye/remote.py` | Uses HMAC signatures, not password hashes |
| `motioneye/utils/__init__.py` | `compute_signature()` still needed for remote cameras |

---

## Testing Plan

### Unit Tests (`test_passwords.py`)

```python
import pytest
from motioneye import passwords

def test_hash_password():
    hashed = passwords.hash_password('test123')
    assert passwords.is_bcrypt_hash(hashed)
    assert len(hashed) == 60

def test_verify_bcrypt():
    hashed = passwords.hash_password('mypassword')
    assert passwords.verify_password('mypassword', hashed)
    assert not passwords.verify_password('wrongpassword', hashed)

def test_verify_sha1_legacy():
    # SHA1 hash of 'admin'
    sha1_hash = 'd033e22ae348aeb5660fc2140aec35850c4da997'
    assert passwords.verify_password('admin', sha1_hash)
    assert not passwords.verify_password('wrong', sha1_hash)

def test_verify_plaintext_legacy():
    assert passwords.verify_password('secret', 'secret')
    assert not passwords.verify_password('wrong', 'secret')

def test_needs_upgrade():
    assert passwords.needs_upgrade('plaintext')
    assert passwords.needs_upgrade('d033e22ae348aeb5660fc2140aec35850c4da997')  # SHA1
    assert not passwords.needs_upgrade('$2b$12$...')  # bcrypt
    assert not passwords.needs_upgrade('')  # empty

def test_empty_password():
    assert passwords.verify_password('', '')
    assert not passwords.verify_password('something', '')
    assert not passwords.verify_password('', 'something')
```

### Integration Tests

1. Login with bcrypt password → success
2. Login with SHA1 password → success + upgrade to bcrypt
3. Login with plaintext password → success + upgrade to bcrypt
4. Change password in settings → stored as bcrypt
5. HTTP Basic Auth with bcrypt password → success
6. Remote camera communication → still works (uses different auth)

---

## Rollback Plan

If bcrypt causes issues:

1. The `verify_password()` function accepts all formats
2. Existing SHA1/plaintext passwords continue to work
3. To rollback: change `hash_password()` back to SHA1

```python
# Emergency rollback (not recommended):
def hash_password(password: str) -> str:
    return hashlib.sha1(password.encode('utf-8')).hexdigest()
```

---

## Performance Considerations

### Hash Computation Time

| Algorithm | Time per Hash | Hashes per Second |
|-----------|--------------|-------------------|
| SHA1 | ~1μs | ~1,000,000 |
| Bcrypt (cost=12) | ~250ms | ~4 |

**Impact**: Login takes ~250ms longer. This is acceptable and intentional.

### CPU Usage on Raspberry Pi

Bcrypt is CPU-intensive. On Pi 4:
- Single hash: ~300-500ms
- Acceptable for login (happens rarely)
- **Don't use bcrypt for per-request auth** (this is why we use session cookies)

---

## Dependency on Session Cookie Auth

**This plan assumes session cookie auth is implemented first.**

With signatures, every request would need password verification → bcrypt would add 250ms to every request → unacceptable.

With session cookies:
- Bcrypt only runs at login (once per session)
- All subsequent requests use fast session token lookup
- 250ms at login is acceptable

---

## Success Criteria

- [ ] New passwords stored as bcrypt hashes
- [ ] Login works with bcrypt passwords
- [ ] Login works with legacy SHA1 passwords (auto-upgrade)
- [ ] Login works with legacy plaintext passwords (auto-upgrade)
- [ ] Remote camera auth still works
- [ ] HTTP Basic Auth still works
- [ ] No noticeable performance impact (session cookies handle per-request auth)
- [ ] Password upgrade logged on first login

---

## References

- OWASP Password Storage Cheat Sheet
- bcrypt Python library: https://pypi.org/project/bcrypt/
- Session cookie auth plan: `docs/plans/session-cookie-auth-migration-20251224-1930.md`

---

**Plan created by**: Claude Code
**Date**: 2025-12-24
**Next Action**: Implement session cookie auth first, then bcrypt migration
