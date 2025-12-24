# Admin Authentication Issues

**Last Updated**: 2025-12-23
**Issue Frequency**: Recurring (3 documented occurrences)

---

## Symptom

After deploying changes to Pi 4 or Pi 5, the admin user loses privileges to the Settings Panel:

- Login page appears, but entering correct credentials fails
- Camera settings appear grayed out
- JavaScript cannot fetch config data
- Server logs show: `authentication failed for user admin`
- HTTP 403 responses on `/login/` and `/config/*/get/` endpoints

---

## Root Cause Analysis

### How MotionEye Authentication Works

1. **Password Storage (Server)**:
   - Admin password stored in `/etc/motioneye/motion.conf` as `@admin_password`
   - Stored as SHA1 hash of plaintext password (e.g., `wwadmin` ’ `45dc502eb21ea282ff458596d23af1e93c2fc59a`)

2. **Password Storage (Client)**:
   - Browser stores `passwordHash` in cookie (named `meye_passord_hash`)
   - This is SHA1 of the entered password

3. **Signature Verification**:
   - Client computes HMAC-SHA256 signature using `passwordHash`
   - Server verifies using stored `@admin_password`
   - If signatures don't match ’ HTTP 403 Unauthorized

### The Bug

**Stale Browser Cookies**: The browser cookie contains a password hash for a **different password** than what's currently configured on the server.

**How This Happens**:
1. Initially, MotionEye is installed with default empty password (`''`)
2. User logs in with empty password ’ cookie stores `SHA1('')` = `da39a3ee5e6b4b0d3255bfef95601890afd80709`
3. User sets a new password (e.g., `wwadmin`) through the UI
4. Server updates `@admin_password` to `SHA1('wwadmin')` = `45dc502eb21ea282ff458596d23af1e93c2fc59a`
5. **Browser cookie NOT updated** if user had "Remember me" checked
6. Future logins fail because:
   - Client sends signature using old empty-password hash
   - Server expects signature using new password hash
   - Signatures don't match ’ 403 Unauthorized

### Evidence from Logs

```log
2025-12-23 22:51:25: [motioneye]    ERROR: authentication failed for user admin
2025-12-23 22:51:25: [motioneye]  WARNING: 403 GET /login/?...&_signature=v2:c5e8f82c41d9e3bad57f4746d92eca0ac118b71d6ed62353d1a4c81d764847fe
```

Signature analysis:
- Received signature computed with `SHA1('')` (empty password hash)
- Server expected signature with `SHA1('wwadmin')` (actual password hash)

---

## Immediate Solution

### Option 1: Clear Browser Cookies (Recommended)

1. Open browser DevTools (F12)
2. Go to **Application** ’ **Cookies**
3. Delete cookies for the MotionEye site:
   - `meye_username`
   - `meye_passord_hash` (note the typo - this is intentional)
4. Refresh the page
5. Log in with correct credentials

### Option 2: Use Incognito/Private Window

1. Open incognito/private browsing window
2. Navigate to MotionEye URL
3. Log in with correct credentials
4. Check "Remember me" to save new cookies

### Option 3: Manual Cookie Fix

In browser console (F12 ’ Console):
```javascript
// Clear auth cookies
document.cookie = "meye_username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
document.cookie = "meye_passord_hash=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
location.reload();
```

---

## Verification Commands

### Check Server Password Hash
```bash
ssh admin@192.168.1.176 "grep '@admin_password' /etc/motioneye/motion.conf"
# Expected: # @admin_password 45dc502eb21ea282ff458596d23af1e93c2fc59a
```

### Verify Password Hash Matches
```bash
echo -n "wwadmin" | shasum -a 1
# Expected: 45dc502eb21ea282ff458596d23af1e93c2fc59a  -
```

### Check Browser Cookie (in browser console)
```javascript
// Get stored password hash
document.cookie.split(';').find(c => c.includes('meye_passord_hash'))
// Should match server's @admin_password value
```

### Check Server Logs for Auth Failures
```bash
ssh admin@192.168.1.176 "sudo tail -100 /etc/motioneye/motioneye.log | grep -i 'auth\|403'"
```

---

## Prevention

### For Users

1. **After changing passwords**: Clear browser cookies and log in again
2. **Testing deployments**: Use incognito window to avoid cookie issues
3. **Multiple browsers**: Be aware each browser has its own cookies

### For Developers

The issue is in the password change flow (`converters.py:164-177`):
- Server updates `@admin_password` in config
- But client's cookie is not invalidated

**Potential Fix**: When password changes, the server could:
1. Generate a version/nonce stored alongside password
2. Include nonce in signature verification
3. If nonce mismatch, invalidate session

---

## Technical Details

### Files Involved

| File | Purpose |
|------|---------|
| `handlers/base.py:107-194` | `get_current_user()` - verifies signatures |
| `utils/__init__.py:282-319` | `compute_signature_v2()` - HMAC-SHA256 signature |
| `utils/__init__.py:322-358` | `verify_signature()` - signature verification |
| `config/camera/converters.py:164-177` | Password hash storage |
| `static/js/main.js:656-681` | Client-side signature computation |
| `static/js/main.js:4025-4031` | Login dialog cookie storage |

### Signature Algorithm

**v2 Signature (HMAC-SHA256 with timestamp)**:
```
message = "{METHOD}:{path}:{timestamp}:{body}"
signature = "v2:" + HMAC-SHA256(passwordHash, message)
```

Where:
- `METHOD`: HTTP method (GET, POST)
- `path`: Sorted query parameters, `_signature` excluded
- `timestamp`: Unix timestamp (seconds)
- `body`: Request body (empty for GET)
- `passwordHash`: SHA1 of plaintext password

### Cookie Names

- `meye_username`: Stored username
- `meye_passord_hash`: SHA1 hash of password (typo is intentional, matches legacy code)

---

## Related Issues

1. **403 from localhost (127.0.0.1)**: Motion event relay requests also fail if credentials mismatch
2. **Config endpoints failing**: `/config/1/get/` returns 403 when auth fails

---

## Appendix: Debugging Script

```python
#!/usr/bin/env python3
"""Verify MotionEye authentication signature."""

import hmac
import hashlib
import urllib.parse

def verify_signature(received_sig, password, method, uri, timestamp):
    """Check if signature matches expected."""
    password_hash = hashlib.sha1(password.encode('utf-8')).hexdigest()

    # Process URI like server does
    parts = list(urllib.parse.urlsplit(uri))
    query = [
        q for q in urllib.parse.parse_qsl(parts[3], keep_blank_values=True)
        if q[0] != '_signature'
    ]
    query.sort(key=lambda q: q[0])
    query = [(n, urllib.parse.quote(v, safe="!'()*~")) for n, v in query]
    parts[3] = '&'.join([f'{n}={v}' for n, v in query])
    parts[0] = parts[1] = ''
    path = urllib.parse.urlunsplit(parts)

    message = f'{method}:{path}:{timestamp}:'
    expected = 'v2:' + hmac.new(
        password_hash.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest().lower()

    print(f"Password: {password}")
    print(f"Password hash: {password_hash}")
    print(f"Processed path: {path}")
    print(f"Message: {message}")
    print(f"Expected sig: {expected}")
    print(f"Received sig: {received_sig}")
    print(f"Match: {expected == received_sig}")

# Example usage
verify_signature(
    received_sig="v2:c5e8f82c41d9e3bad57f4746d92eca0ac118b71d6ed62353d1a4c81d764847fe",
    password="wwadmin",  # or "" for empty
    method="GET",
    uri="/login/?_=1766551885536&_username=admin&_login=true&_timestamp=1766551885",
    timestamp=1766551885
)
```
