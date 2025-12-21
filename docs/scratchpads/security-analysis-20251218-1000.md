# Security Analysis Scratchpad - MotionEye
**Date**: 2025-12-18
**Analyst**: Claude Code

## Analysis Scope
- Authentication & Session Management
- Input Validation & Injection Prevention
- File Handling & Path Traversal
- Network Security & API Endpoints
- Cryptographic Practices
- Sensitive Data Exposure
- CSRF/XSS Protection

---

## Key Files Analyzed

### Authentication
- `motioneye/handlers/login.py` - Login handling
- `motioneye/handlers/base.py` - Base handler with auth checks
- `motioneye/settings.py` - Settings including auth config
- `motioneye/utils/__init__.py` - Signature computation and auth utilities

### Configuration & Commands
- `motioneye/config/commands.py` - Command execution
- `motioneye/handlers/action.py` - Action command execution
- `motioneye/controls/powerctl.py` - Power control commands

### File Handling
- `motioneye/mediafiles.py` - Media file operations
- `motioneye/handlers/picture.py` - Picture handling
- `motioneye/handlers/movie.py` - Movie handling

### Network/API
- `motioneye/server.py` - Web server setup
- `motioneye/remote.py` - Remote camera handling
- `motioneye/uploadservices.py` - Cloud upload services
- `motioneye/webhook.py` - Webhook execution

---

## Findings

### 1. Authentication & Session Management

#### Observations:
- Signature-based authentication using HMAC-style approach (`utils/compute_signature`)
- Optional HTTP Basic Auth support (`settings.HTTP_BASIC_AUTH`)
- Two user roles: admin and normal user
- No session management - stateless auth on each request
- SHA1 used for password hashing (line 120-125 base.py)
- Password hook available for external password management

#### Vulnerabilities Found:
1. **MEDIUM: Weak Password Hashing** - Uses SHA1 for password hashing instead of bcrypt/argon2/PBKDF2
2. **MEDIUM: No Rate Limiting** - No brute-force protection on authentication
3. **LOW: No Account Lockout** - Failed logins only logged, no lockout mechanism
4. **INFO: No Session Tokens** - Relies on signature per request (could be OK for API use)

#### Severity Rating: MEDIUM

---

### 2. Input Validation

#### Observations:
- JSON parsing without schema validation (handlers/config.py:149)
- URL parameters decoded via `get_argument()`
- File uploads handled via `self.request.files`
- Camera IDs validated as integers
- Limited input sanitization

#### Vulnerabilities Found:
1. **MEDIUM: Insufficient Input Validation** - JSON payloads accepted without schema validation
2. **LOW: Type Coercion Issues** - Some float/int conversions without bounds checking
3. **INFO: Error Messages** - Some error messages could leak internal paths

#### Severity Rating: MEDIUM

---

### 3. File Handling & Path Traversal

#### Observations:
- Path traversal check exists in `mediafiles.get_media_content()` (line 516: `if '..' in path`)
- Files accessed via `os.path.join(target_dir, path)`
- `os.path.realpath()` used in upload services

#### Vulnerabilities Found:
1. **MEDIUM: Incomplete Path Traversal Protection** - Only checks for `..` but not other tricks like URL-encoded paths, symlinks, or absolute paths starting with `/`
2. **MEDIUM: No File Extension Whitelist** - Limited to extensions but could be bypassed
3. **LOW: Symlink Following** - No protection against symlink attacks

#### Severity Rating: MEDIUM

---

### 4. Command Injection

#### Observations:
- Action commands executed via `subprocess.Popen()` (action.py:85)
- Commands from config must exist as executable files in CONF_PATH
- `shlex.quote()` used in some places (mediafiles.py, motionctl.py)
- FFmpeg commands built with string formatting (mediafiles.py:749-764)
- PowerControl uses `os.system()` with unvalidated paths (powerctl.py:60)

#### Vulnerabilities Found:
1. **HIGH: Shell Command Injection in make_timelapse_movie()** - Uses `shell=True` with string formatting including user-controlled paths (mediafiles.py:768)
2. **MEDIUM: os.system() Usage** - PowerControl._exec_prog uses os.system() which is dangerous
3. **LOW: FFmpeg Command Building** - Uses string formatting but paths are quoted

#### Severity Rating: HIGH (due to shell=True with user paths)

---

### 5. Network Security

#### Observations:
- Server listens on all interfaces by default (0.0.0.0:8765)
- HTTPS not enforced (HTTP only by default)
- Certificate validation optional (`settings.VALIDATE_CERTS`)
- Motion control interface on localhost only by default
- Remote camera communication includes credentials in URLs

#### Vulnerabilities Found:
1. **HIGH: No HTTPS by Default** - All traffic including passwords sent in plaintext
2. **MEDIUM: Certificate Validation Optional** - Can be disabled, enabling MITM attacks
3. **MEDIUM: Password in Remote URLs** - Credentials passed in URL query strings
4. **LOW: No IP Whitelisting** - No access control beyond authentication

#### Severity Rating: HIGH

---

### 6. Cryptographic Practices

#### Observations:
- SHA1 for password hashing (weak)
- SHA1 for request signatures
- No salt in password hashing
- Google/Dropbox OAuth uses hardcoded client secrets
- Upload services store credentials in JSON file

#### Vulnerabilities Found:
1. **HIGH: Weak Password Storage** - Unsalted SHA1, trivially brute-forced
2. **HIGH: Hardcoded API Secrets** - Google CLIENT_NOT_SO_SECRET exposed in source (uploadservices.py:163)
3. **MEDIUM: Weak Signature Algorithm** - SHA1 deprecated for security
4. **LOW: Credentials in Config Files** - Stored in plaintext JSON

#### Severity Rating: HIGH

---

### 7. Sensitive Data Exposure

#### Observations:
- Passwords stored in config files (motioneye.conf)
- OAuth credentials stored in uploadservices.json
- SMTP/FTP/SFTP credentials stored in config
- Error messages may expose internal paths
- Server version exposed in headers

#### Vulnerabilities Found:
1. **MEDIUM: Plaintext Credential Storage** - All service credentials stored unencrypted
2. **LOW: Version Information Disclosure** - Server header reveals motionEye version
3. **LOW: Config Backup Exposes Secrets** - Backup includes all credentials
4. **INFO: Logging Contains Sensitive Data** - Some debug logs may contain credentials

#### Severity Rating: MEDIUM

---

### 8. CSRF/XSS Protection

#### Observations:
- No CSRF tokens implemented
- Signature-based auth provides some CSRF protection
- JSON responses for API endpoints
- HTML templates use Jinja2 (auto-escaping)
- Camera names rendered in HTML

#### Vulnerabilities Found:
1. **MEDIUM: No CSRF Protection** - No explicit CSRF tokens, relies on signature
2. **LOW: Potential Stored XSS** - Camera names/descriptions could contain XSS payloads
3. **INFO: Cookie Attributes** - Motion detection cookies lack HttpOnly/Secure flags

#### Severity Rating: MEDIUM

---

## Summary Table

| Category | Severity | Issues Found | Priority |
|----------|----------|--------------|----------|
| Authentication | MEDIUM | 4 | P2 |
| Input Validation | MEDIUM | 3 | P2 |
| Path Traversal | MEDIUM | 3 | P2 |
| Command Injection | HIGH | 3 | P1 |
| Network Security | HIGH | 4 | P1 |
| Cryptography | HIGH | 4 | P1 |
| Data Exposure | MEDIUM | 4 | P2 |
| CSRF/XSS | MEDIUM | 3 | P3 |

---

## Critical Findings Summary

### P1 - Critical (Immediate Action Required)
1. Command injection via shell=True in timelapse creation
2. No HTTPS support/enforcement
3. Weak password hashing (unsalted SHA1)
4. Hardcoded OAuth client secrets in source code

### P2 - High (Should Fix Soon)
1. Incomplete path traversal protection
2. No rate limiting on authentication
3. Certificate validation can be disabled
4. Plaintext credential storage

### P3 - Medium (Plan to Address)
1. No CSRF tokens
2. Missing input validation schemas
3. Version disclosure in headers
4. Cookie security attributes

---

## Additional Notes

### Positive Security Features
- Signature-based API authentication provides replay protection
- Motion control bound to localhost by default
- File extension restrictions on media files
- Admin-only restrictions on destructive operations
- `shlex.quote()` used in some command building

### Architecture Considerations
- Tornado async framework is generally secure
- Jinja2 template engine has auto-escaping
- Subprocess calls generally avoid shell=True (except timelapse)
- Clear separation of admin vs normal user capabilities

