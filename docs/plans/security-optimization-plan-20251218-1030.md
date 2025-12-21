# MotionEye Security Optimization Plan
**Date**: 2025-12-18
**Version**: 1.0
**Status**: Draft

## Executive Summary

This document outlines a comprehensive security optimization plan for MotionEye based on a thorough security analysis. The plan is organized into three phases based on priority and impact, with Phase 1 addressing critical vulnerabilities requiring immediate attention.

**Risk Assessment Summary:**
- **Critical (P1)**: 4 issues requiring immediate attention
- **High (P2)**: 4 issues to address within 30 days
- **Medium (P3)**: 4 issues to address within 90 days

---

## Phase 1: Critical Security Fixes (Immediate - 1-2 weeks)

### 1.1 Command Injection Remediation

**Issue:** `mediafiles.py:make_timelapse_movie()` uses `shell=True` with user-controlled paths

**Current Code Location:** `motioneye/mediafiles.py:768`

**Remediation Steps:**

1. Replace shell=True with subprocess list arguments:

```python
# BEFORE (vulnerable)
subprocess.Popen(cmd, shell=True, ...)

# AFTER (secure)
import shlex
cmd_list = [
    ffmpeg_binary,
    '-f', 'concat',
    '-safe', '0',
    '-i', manifest_path,
    '-c:v', codec,
    '-b:v', bitrate,
    output_path
]
subprocess.Popen(cmd_list, shell=False, ...)
```

2. Apply `shlex.quote()` to all user-supplied paths
3. Add path validation before command execution

**Files to Modify:**
- `motioneye/mediafiles.py`

**Testing:**
- Create timelapse with camera name containing shell metacharacters
- Verify no command injection possible
- Test with paths containing spaces, quotes, semicolons

---

### 1.2 Replace os.system() with subprocess

**Issue:** `powerctl.py:60` uses `os.system()` which can be exploited

**Remediation Steps:**

1. Replace `os.system()` with `subprocess.run()`:

```python
# BEFORE (vulnerable)
return os.system(p + args) == 0

# AFTER (secure)
import subprocess
try:
    result = subprocess.run([p] + shlex.split(args), check=False)
    return result.returncode == 0
except Exception:
    return False
```

**Files to Modify:**
- `motioneye/controls/powerctl.py`

---

### 1.3 Upgrade Password Hashing

**Issue:** Unsalted SHA1 is cryptographically weak

**Remediation Steps:**

1. Install passlib or use Python's hashlib with proper PBKDF2:

```python
# requirements.txt addition
passlib>=1.7.4

# New password hashing implementation
from passlib.hash import pbkdf2_sha256

def hash_password(password):
    return pbkdf2_sha256.hash(password)

def verify_password(password, hash):
    return pbkdf2_sha256.verify(password, hash)
```

2. Implement password migration on first login:
   - Check if stored password is in old SHA1 format
   - If old format and password matches, re-hash with PBKDF2 and store
   - Update config file with new hash

3. Add password hash version identifier:
```python
# Format: $version$salt$hash
# v1 = old SHA1 (deprecated)
# v2 = PBKDF2-SHA256
```

**Files to Modify:**
- `motioneye/utils/__init__.py`
- `motioneye/handlers/base.py`
- `motioneye/handlers/login.py`
- `motioneye/config.py`

**Backward Compatibility:**
- Support both old and new hash formats during migration period
- Log warning when old format detected
- Auto-upgrade on successful authentication

---

### 1.4 Move OAuth Secrets to Configuration

**Issue:** Hardcoded `CLIENT_NOT_SO_SECRET` in source code

**Remediation Steps:**

1. Move secrets to environment variables or config file:

```python
# settings.py additions
GOOGLE_CLIENT_ID = os.environ.get('MOTIONEYE_GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('MOTIONEYE_GOOGLE_CLIENT_SECRET', '')
DROPBOX_CLIENT_ID = os.environ.get('MOTIONEYE_DROPBOX_CLIENT_ID', '')
DROPBOX_CLIENT_SECRET = os.environ.get('MOTIONEYE_DROPBOX_CLIENT_SECRET', '')
```

2. Update uploadservices.py to use settings:

```python
from motioneye import settings

class GoogleBase:
    CLIENT_ID = settings.GOOGLE_CLIENT_ID
    CLIENT_SECRET = settings.GOOGLE_CLIENT_SECRET
```

3. Add documentation for users to create their own OAuth apps
4. Add validation to ensure secrets are configured before use

**Files to Modify:**
- `motioneye/settings.py`
- `motioneye/uploadservices.py`

---

## Phase 2: High Priority Security Improvements (2-4 weeks)

### 2.1 Enhance Path Traversal Protection

**Issue:** Current check only looks for `..` string

**Remediation Steps:**

1. Create comprehensive path validation utility:

```python
import os
import re

def safe_path_join(base_dir, user_path):
    """
    Safely join paths preventing directory traversal attacks.
    """
    # Normalize the base directory
    base_dir = os.path.normpath(os.path.abspath(base_dir))

    # Reject absolute paths
    if os.path.isabs(user_path):
        raise ValueError("Absolute paths not allowed")

    # Reject various traversal patterns
    dangerous_patterns = [
        r'\.\.',           # Parent directory
        r'^/',             # Absolute path
        r'^\\',            # Windows absolute
        r'%2e%2e',         # URL encoded ..
        r'%252e%252e',     # Double URL encoded
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, user_path, re.IGNORECASE):
            raise ValueError(f"Path contains forbidden pattern")

    # Join and resolve
    full_path = os.path.normpath(os.path.join(base_dir, user_path))

    # Verify result is within base directory
    if not full_path.startswith(base_dir):
        raise ValueError("Path escapes base directory")

    # Check for symlinks escaping base
    real_path = os.path.realpath(full_path)
    if not real_path.startswith(os.path.realpath(base_dir)):
        raise ValueError("Symlink escapes base directory")

    return full_path
```

2. Apply to all file access points in mediafiles.py

**Files to Modify:**
- `motioneye/utils/__init__.py` (add utility)
- `motioneye/mediafiles.py` (use utility)
- `motioneye/handlers/picture.py`
- `motioneye/handlers/movie.py`

---

### 2.2 Implement Rate Limiting

**Issue:** No protection against brute-force attacks

**Remediation Steps:**

1. Implement token bucket rate limiter:

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_attempts=5, window_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts = defaultdict(list)

    def is_allowed(self, identifier):
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old attempts
        self._attempts[identifier] = [
            t for t in self._attempts[identifier] if t > cutoff
        ]

        if len(self._attempts[identifier]) >= self.max_attempts:
            return False

        self._attempts[identifier].append(now)
        return True

    def get_wait_time(self, identifier):
        if not self._attempts[identifier]:
            return 0
        oldest = min(self._attempts[identifier])
        return max(0, oldest + self.window_seconds - time.time())
```

2. Apply to authentication endpoints:

```python
# In base.py
auth_limiter = RateLimiter(max_attempts=5, window_seconds=300)

def check_authentication(self):
    client_ip = self.request.remote_ip
    if not auth_limiter.is_allowed(client_ip):
        wait_time = auth_limiter.get_wait_time(client_ip)
        raise HTTPError(429, f"Too many attempts. Try again in {int(wait_time)} seconds")
```

**Files to Modify:**
- `motioneye/utils/__init__.py` (add RateLimiter class)
- `motioneye/handlers/base.py` (apply rate limiting)

**Configuration:**
Add to settings.py:
```python
AUTH_RATE_LIMIT_ATTEMPTS = 5
AUTH_RATE_LIMIT_WINDOW = 300  # seconds
```

---

### 2.3 Add HTTPS Support

**Issue:** No TLS encryption for web traffic

**Remediation Steps:**

1. Add SSL/TLS configuration to settings:

```python
# settings.py additions
SSL_ENABLED = False
SSL_CERTIFICATE = '/etc/motioneye/ssl/cert.pem'
SSL_KEY = '/etc/motioneye/ssl/key.pem'
```

2. Update server.py to support HTTPS:

```python
import ssl

if settings.SSL_ENABLED:
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(settings.SSL_CERTIFICATE, settings.SSL_KEY)
    http_server = tornado.httpserver.HTTPServer(
        application,
        ssl_options=ssl_ctx
    )
else:
    http_server = tornado.httpserver.HTTPServer(application)
```

3. Add auto-redirect HTTP to HTTPS:

```python
if settings.SSL_ENABLED and settings.SSL_REDIRECT:
    # Start HTTP server that redirects to HTTPS
    redirect_app = tornado.web.Application([
        (r".*", RedirectHandler)
    ])
```

4. Add self-signed certificate generation script

**Files to Modify:**
- `motioneye/settings.py`
- `motioneye/server.py`
- Add `scripts/generate-ssl-cert.sh`

---

### 2.4 Strengthen Certificate Validation

**Issue:** Certificate validation can be disabled

**Remediation Steps:**

1. Add warning when validation is disabled:

```python
if not settings.VALIDATE_CERTS:
    logging.warning(
        "SECURITY WARNING: Certificate validation is disabled. "
        "This makes the connection vulnerable to MITM attacks."
    )
```

2. Add per-host certificate pinning support:

```python
# settings.py
CERTIFICATE_PINS = {
    # 'hostname': 'sha256_fingerprint'
}
```

3. Implement certificate verification callback:

```python
def verify_certificate(conn, cert, errno, depth, ok):
    if not ok:
        return False

    hostname = conn.getinfo(pycurl.EFFECTIVE_URL)
    if hostname in settings.CERTIFICATE_PINS:
        # Verify pin matches
        pass
    return True
```

**Files to Modify:**
- `motioneye/settings.py`
- `motioneye/utils/__init__.py`
- `motioneye/remote.py`

---

## Phase 3: Security Hardening (4-8 weeks)

### 3.1 Implement Input Validation Schema

**Issue:** JSON payloads accepted without validation

**Remediation Steps:**

1. Install jsonschema:
```
pip install jsonschema
```

2. Create schemas for each endpoint:

```python
# schemas/camera_config.py
CAMERA_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "camera_name": {"type": "string", "maxLength": 64},
        "rotation": {"type": "integer", "enum": [0, 90, 180, 270]},
        # ... other fields
    },
    "additionalProperties": False
}
```

3. Create validation decorator:

```python
from jsonschema import validate, ValidationError

def validate_json(schema):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            try:
                data = json.loads(self.request.body)
                validate(data, schema)
            except ValidationError as e:
                raise HTTPError(400, f"Invalid request: {e.message}")
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator
```

**Files to Modify:**
- Create `motioneye/schemas/` directory
- `motioneye/handlers/config.py`
- Other handler files

---

### 3.2 Add CSRF Protection

**Issue:** No explicit CSRF tokens

**Remediation Steps:**

1. Generate CSRF token on login:

```python
import secrets

def generate_csrf_token():
    return secrets.token_urlsafe(32)
```

2. Add CSRF token to all forms:

```html
<input type="hidden" name="_csrf_token" value="{{ csrf_token }}">
```

3. Validate CSRF token on POST/PUT/DELETE:

```python
def check_csrf_token(self):
    if self.request.method in ['POST', 'PUT', 'DELETE']:
        token = self.get_argument('_csrf_token', None)
        if token != self.get_cookie('csrf_token'):
            raise HTTPError(403, "Invalid CSRF token")
```

**Files to Modify:**
- `motioneye/handlers/base.py`
- `motioneye/templates/main.html`
- JavaScript files to include CSRF token in AJAX requests

---

### 3.3 Enhance Cookie Security

**Issue:** Cookies lack security attributes

**Remediation Steps:**

1. Add secure cookie settings:

```python
def set_secure_cookie(self, name, value):
    self.set_cookie(
        name,
        value,
        httponly=True,
        secure=settings.SSL_ENABLED,
        samesite='Strict'
    )
```

2. Apply to all cookie operations in handlers

**Files to Modify:**
- `motioneye/handlers/base.py`
- `motioneye/handlers/picture.py`

---

### 3.4 Implement Security Headers

**Issue:** Missing security headers

**Remediation Steps:**

1. Add middleware for security headers:

```python
class SecurityHeadersMiddleware:
    def set_default_headers(self):
        self.set_header('X-Content-Type-Options', 'nosniff')
        self.set_header('X-Frame-Options', 'DENY')
        self.set_header('X-XSS-Protection', '1; mode=block')
        self.set_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        if settings.SSL_ENABLED:
            self.set_header('Strict-Transport-Security',
                          'max-age=31536000; includeSubDomains')
        # CSP header
        self.set_header('Content-Security-Policy',
                       "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                       "style-src 'self' 'unsafe-inline'")
```

2. Remove server version header:

```python
# In BaseHandler
def set_default_headers(self):
    self.clear_header('Server')
```

**Files to Modify:**
- `motioneye/handlers/base.py`

---

### 3.5 Encrypt Stored Credentials

**Issue:** Credentials stored in plaintext

**Remediation Steps:**

1. Implement credential encryption:

```python
from cryptography.fernet import Fernet

class CredentialStore:
    def __init__(self, key_file):
        self.key = self._load_or_create_key(key_file)
        self.fernet = Fernet(self.key)

    def encrypt(self, plaintext):
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext):
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

2. Apply to credential storage in config files
3. Add migration script for existing configurations

**Files to Modify:**
- `motioneye/config.py`
- `motioneye/uploadservices.py`

---

## Implementation Timeline

| Phase | Priority | Estimated Time | Target Completion |
|-------|----------|----------------|-------------------|
| Phase 1.1 | P1 | 2 days | Week 1 |
| Phase 1.2 | P1 | 1 day | Week 1 |
| Phase 1.3 | P1 | 3 days | Week 1-2 |
| Phase 1.4 | P1 | 2 days | Week 2 |
| Phase 2.1 | P2 | 2 days | Week 3 |
| Phase 2.2 | P2 | 2 days | Week 3 |
| Phase 2.3 | P2 | 3 days | Week 3-4 |
| Phase 2.4 | P2 | 1 day | Week 4 |
| Phase 3.1 | P3 | 3 days | Week 5-6 |
| Phase 3.2 | P3 | 2 days | Week 6 |
| Phase 3.3 | P3 | 1 day | Week 7 |
| Phase 3.4 | P3 | 2 days | Week 7 |
| Phase 3.5 | P3 | 3 days | Week 8 |

---

## Testing Requirements

### Security Testing Checklist

- [ ] Authentication bypass attempts
- [ ] Brute-force attack simulation
- [ ] SQL/Command injection testing
- [ ] Path traversal attacks
- [ ] XSS payload injection
- [ ] CSRF attack simulation
- [ ] Session hijacking attempts
- [ ] SSL/TLS configuration verification
- [ ] Cookie security attribute verification
- [ ] Rate limiting verification
- [ ] Certificate validation testing
- [ ] Password hash strength verification

### Recommended Tools

- **OWASP ZAP** - Automated security scanning
- **Burp Suite** - Manual security testing
- **sqlmap** - SQL injection testing
- **nikto** - Web server scanning
- **testssl.sh** - SSL/TLS testing

---

## Documentation Updates Required

1. **User Documentation:**
   - SSL/TLS setup guide
   - OAuth app creation guide
   - Password migration notes
   - Security best practices

2. **Developer Documentation:**
   - Secure coding guidelines
   - Input validation requirements
   - Authentication flow documentation

---

## Dependencies

### New Dependencies Required

```
# requirements.txt additions
passlib>=1.7.4        # Password hashing
jsonschema>=4.0.0     # Input validation
cryptography>=3.4.0   # Credential encryption
```

### Version Requirements

- Python 3.8+ (for security improvements)
- OpenSSL 1.1.1+ (for TLS 1.3 support)

---

## Risk Assessment

### Migration Risks

| Change | Risk | Mitigation |
|--------|------|------------|
| Password hash upgrade | Users may need to reset passwords | Auto-migration on login |
| SSL enforcement | May break existing setups | Gradual rollout, clear docs |
| Rate limiting | May affect legitimate users | Configurable limits |
| Path validation | May break edge cases | Thorough testing |

### Backward Compatibility

- All changes should maintain backward compatibility where possible
- Old password hashes should be auto-upgraded
- HTTP should remain available during transition
- Config file format changes should be auto-migrated

---

## Success Metrics

- Zero critical vulnerabilities in security scans
- Pass OWASP Top 10 checklist
- < 1% false positive rate on rate limiting
- 100% of passwords migrated to new hash format
- SSL/TLS configuration achieves A+ rating on SSL Labs

---

## Appendix: Quick Reference

### Files Requiring Changes (by priority)

**P1 (Critical):**
- `motioneye/mediafiles.py`
- `motioneye/controls/powerctl.py`
- `motioneye/utils/__init__.py`
- `motioneye/handlers/base.py`
- `motioneye/uploadservices.py`
- `motioneye/settings.py`

**P2 (High):**
- `motioneye/server.py`
- `motioneye/remote.py`
- `motioneye/handlers/picture.py`
- `motioneye/handlers/movie.py`

**P3 (Medium):**
- `motioneye/handlers/config.py`
- `motioneye/config.py`
- `motioneye/templates/main.html`
- Static JavaScript files

---

*Document prepared by Claude Code security analysis*
*Last updated: 2025-12-18*
