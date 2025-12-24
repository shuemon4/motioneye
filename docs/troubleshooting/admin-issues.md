# Admin Authentication Issues

**Last Updated**: 2025-12-24
**Issue Frequency**: Recurring (3 documented occurrences)
**Status**: RESOLVED - Root cause identified and fixed

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

### Two Separate Issues Were Identified

**Issue 1: Stale Browser Cookies** (Minor)
- Browser cookies stored old password hash that didn't match server config
- Solved by clearing cookies or using incognito window

**Issue 2: Broken v2 Signature Implementation** (MAJOR - NOW FIXED)
- A partially-implemented v2 signature system (HMAC-SHA256) was causing mismatches
- The JavaScript and Python implementations didn't produce matching signatures
- **This has been reverted to the stable v1 signature system**

### How MotionEye Authentication Works (v1 - Current)

1. **Password Storage (Server)**:
   - Admin password stored in `/etc/motioneye/motion.conf` as `@admin_password`
   - Stored as SHA1 hash of plaintext password (e.g., `wwadmin` → `45dc502eb21ea282ff458596d23af1e93c2fc59a`)

2. **Password Storage (Client)**:
   - Browser stores `passwordHash` in cookie (named `meye_passord_hash`)
   - This is SHA1 of the entered password

3. **Signature Verification (v1)**:
   - Client computes: `SHA1(method + ':' + path + ':' + body + ':' + passwordHash)`
   - Server verifies using stored `@admin_password`
   - If signatures don't match → HTTP 403 Unauthorized

### Common Confusion: Settings Panel Still Grayed Out

If you can see the video stream but Settings is grayed out, you're logged in as **normal user**, not admin:

- **Empty normal_password**: Any unauthenticated access gets "normal" user role automatically
- **Normal users** can view streams but cannot access Settings
- **Solution**: Click the key icon and log in with `admin` / `wwadmin` (or your admin password)

---

## Issue 3: Settings Panel Overlay Blocks Interaction (Fixed 2025-12-24)

### Symptom

After logging in as admin:
- Video stream is visible
- Settings panel shows all options
- **But cannot click or interact with any settings** - appears to have an invisible overlay blocking interaction
- Browser console shows error:
  ```
  main.js:2811 Uncaught TypeError: Cannot set properties of undefined (setting 'checked')
      at dict2CameraUi (main.js:2811)
  ```

### Root Cause

The `#streamingDirectModeSwitch` element is **commented out** in the HTML template (`motioneye/templates/partials/settings/_video_streaming.html`, lines 33-41). The "Direct Streaming" feature was intentionally hidden with an HTML comment:

```html
<!-- Direct Streaming hidden until proper authentication integration is implemented.
     See: https://github.com/motioneye-project/motioneye/issues/XXX
     When enabled, requires webcontrol_localhost=off which exposes Motion's port to the network.
<tr class="settings-item" depends="videoStreamingEnabled">
    ...
    <input type="checkbox" ... id="streamingDirectModeSwitch" checked>
    ...
</tr>
-->
```

However, the JavaScript code in `main.js` still tried to access this non-existent element:

```javascript
// Line 2811 - crashes because element doesn't exist
$('#streamingDirectModeSwitch')[0].checked = dict['streaming_direct_mode'] !== false;
```

This crash occurred during `dict2CameraUi()` which prevented `endProgress()` from being called. The progress overlay (`div.settings-progress`) remained visible at `opacity: 0.9`, blocking all interaction with the Settings panel.

### Fix Applied

Added null checks in `motioneye/static/js/main.js`:

**Line 2454** (in `cameraUi2Dict`):
```javascript
// Before:
'streaming_direct_mode': $('#streamingDirectModeSwitch')[0].checked,

// After:
'streaming_direct_mode': $('#streamingDirectModeSwitch')[0] ? $('#streamingDirectModeSwitch')[0].checked : true,
```

**Line 2811** (in `dict2CameraUi`):
```javascript
// Before:
$('#streamingDirectModeSwitch')[0].checked = dict['streaming_direct_mode'] !== false;

// After:
var streamingDirectModeEl = $('#streamingDirectModeSwitch')[0];
if (streamingDirectModeEl) {
    streamingDirectModeEl.checked = dict['streaming_direct_mode'] !== false;
}
```

### Solution After Deploying Fix

1. Deploy the updated code to the Pi
2. Restart MotionEye: `sudo systemctl restart motioneye`
3. **Hard refresh browser** (Ctrl+Shift+R or Cmd+Shift+R) to clear cached JavaScript
4. Log in as admin - Settings panel should now be fully interactive

---

## Immediate Solution

### Option 1: Clear Browser Cookies (Recommended)

1. Open browser DevTools (F12)
2. Go to **Application** � **Cookies**
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

In browser console (F12 � Console):
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
| `utils/__init__.py:242-280` | `compute_signature()` - v1 SHA1 signature |
| `utils/__init__.py:322-358` | `verify_signature()` - signature verification |
| `config/camera/converters.py:164-177` | Password hash storage |
| `static/js/main.js:617-641` | Client-side signature computation |
| `static/js/main.js:4025-4031` | Login dialog cookie storage |

### Signature Algorithm (v1 - Current)

**v1 Signature (Plain SHA1)**:
```
message = "{METHOD}:{path}:{body}:{passwordHash}"
signature = SHA1(message).toLowerCase()
```

Where:
- `METHOD`: HTTP method (GET, POST)
- `path`: Sorted query parameters, `_signature` excluded
- `body`: Request body (empty for GET)
- `passwordHash`: SHA1 of plaintext password

### What Was Fixed (2025-12-24)

A partially-implemented v2 signature system was reverted:
- Removed `hmacSha256()` function from `main.js`
- Removed `useSecureSignature = true` flag
- Removed timestamp parameter from signature computation
- Reverted to simple SHA1 signature matching upstream MotionEye

### Cookie Names

- `meye_username`: Stored username
- `meye_passord_hash`: SHA1 hash of password (typo is intentional, matches legacy code)

---

## Related Issues

1. **403 from localhost (127.0.0.1)**: Motion event relay requests also fail if credentials mismatch
2. **Config endpoints failing**: `/config/1/get/` returns 403 when auth fails

---

## Appendix: Debugging Script (v1 Signatures)

```python
#!/usr/bin/env python3
"""Verify MotionEye v1 authentication signature."""

import hashlib
import urllib.parse

def verify_v1_signature(received_sig, password, method, uri):
    """Check if v1 signature matches expected."""
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

    # v1: SHA1 of method:path:body:passwordHash
    message = f'{method}:{path}::{password_hash}'
    expected = hashlib.sha1(message.encode('utf-8')).hexdigest().lower()

    print(f"Password: {password}")
    print(f"Password hash: {password_hash}")
    print(f"Processed path: {path}")
    print(f"Message: {message}")
    print(f"Expected sig: {expected}")
    print(f"Received sig: {received_sig}")
    print(f"Match: {expected == received_sig}")

# Example usage
verify_v1_signature(
    received_sig="16a86df6b796782066892df5d7f73e5a803f3d70",
    password="wwadmin",
    method="GET",
    uri="/config/list/?_=1735059000000&_username=admin"
)
```
