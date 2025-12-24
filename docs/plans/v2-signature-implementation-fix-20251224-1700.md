# V2 Signature Implementation Fix

**Date**: 2025-12-24
**Status**: Implementation Plan
**Priority**: P1 - Critical Security Fix

---

## Problem Statement

The v2 HMAC-SHA256 signature system was partially implemented but contains multiple critical bugs that prevent it from working. Another agent incorrectly reverted all v2 code and marked the issue as "RESOLVED", but this was actually a regression that removed security improvements.

---

## Bugs Found in Original V2 Implementation

### Bug #1: Invalid JavaScript Method (CRITICAL)
**Location**: `motioneye/static/js/main.js:628`

```javascript
// WRONG - JavaScript arrays don't have sortKey() method
query.sortKey(function (q) {return q.key;});

// CORRECT
query.sort(function (a, b) {return a.key.localeCompare(b.key);});
```

**Impact**: Runtime error, signature computation fails completely

---

### Bug #2: URL Encoding Mismatch
**Python** (server-side):
```python
urllib.parse.quote(v, safe="!'()*~")
```

**JavaScript** (client-side):
```javascript
encodeURIComponent(q.value)
```

**Problem**: Different safe characters produce different output

| Character | Python Output | JS Output | Match? |
|-----------|---------------|-----------|--------|
| `!` | `!` (safe) | `%21` | ❌ No |
| `'` | `'` (safe) | `%27` | ❌ No |
| `(` | `(` (safe) | `%28` | ❌ No |
| `)` | `)` (safe) | `%29` | ❌ No |
| `*` | `*` (safe) | `%2A` | ❌ No |
| `~` | `~` (safe) | `%7E` | ❌ No |
| ` ` (space) | `%20` | `%20` | ✅ Yes |

**Impact**: Signatures don't match even with correct HMAC implementation

---

### Bug #3: Missing Parameter Filtering

The v2 code needs to exclude `_signature`, `_timestamp`, and `_csrf` from the signed message, but the implementation was incomplete.

---

## The Fix - Three-Part Strategy

### Part 1: Fix JavaScript URL Encoding

Create a custom `encodeURIComponentRFC3986()` function that matches Python's behavior:

```javascript
/**
 * Encode URI component matching Python's urllib.parse.quote(safe="!'()*~")
 * This ensures client and server produce identical signatures.
 */
function encodeURIComponentRFC3986(str) {
    return encodeURIComponent(str).replace(/[!'()*~]/g, function(c) {
        // Don't encode these characters - match Python safe set
        return c;
    });
}
```

**Rationale**: Instead of changing Python's encoding (which might break other things), we make JavaScript match Python.

---

### Part 2: Fix the Array Sort Bug

```javascript
// Before (broken):
query.sortKey(function (q) {return q.key;});

// After (fixed):
query.sort(function (a, b) {
    return a.key.localeCompare(b.key);
});
```

---

### Part 3: Proper Parameter Exclusion

```javascript
// Exclude signature, timestamp, and CSRF token from signed parameters
query = query.filter(function (q) {
    return q.key !== '_signature' &&
           q.key !== '_timestamp' &&
           q.key !== '_csrf';
});
```

---

## Complete Fixed Implementation

### JavaScript (main.js)

```javascript
/* HMAC-SHA256 implementation - matches Python hmac module */
var hmacSha256 = (function () {
    function hmac(key, message) {
        var blockSize = 64; /* SHA256 block size in bytes */

        /* If key is longer than block size, hash it */
        if (key.length > blockSize) {
            key = hexToStr(sha256(key));
        }

        /* Pad key to block size */
        while (key.length < blockSize) {
            key += String.fromCharCode(0);
        }

        var oKeyPad = '', iKeyPad = '';
        for (var i = 0; i < blockSize; i++) {
            oKeyPad += String.fromCharCode(key.charCodeAt(i) ^ 0x5c);
            iKeyPad += String.fromCharCode(key.charCodeAt(i) ^ 0x36);
        }

        var innerHash = sha256(iKeyPad + message);
        return sha256(oKeyPad + hexToStr(innerHash));
    }

    function hexToStr(hex) {
        var str = '';
        for (var i = 0; i < hex.length; i += 2) {
            str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
        }
        return str;
    }

    return hmac;
}());

/**
 * Encode URI component matching Python's urllib.parse.quote(safe="!'()*~")
 */
function encodeURIComponentRFC3986(str) {
    return encodeURIComponent(str).replace(/[!'()*~]/g, function(c) {
        return c; // Don't encode these characters
    });
}

/**
 * Compute request signature (v2 HMAC-SHA256 with replay protection)
 */
function computeSignature(method, path, body) {
    path = qualifyPath(path);

    var parts = splitUrl(path);
    var query = parts.params;
    path = parts.baseUrl;
    path = '/' + path.substring(basePath.length);

    /* Sort query arguments alphabetically, excluding auth parameters */
    query = Object.keys(query).map(function (key) {
        return {key: key, value: decodeURIComponent(query[key] || '')};
    });

    query = query.filter(function (q) {
        return q.key !== '_signature' &&
               q.key !== '_timestamp' &&
               q.key !== '_csrf';
    });

    query.sort(function (a, b) {
        return a.key.localeCompare(b.key);
    });

    query = query.map(function (q) {
        return q.key + '=' + encodeURIComponentRFC3986(q.value);
    }).join('&');

    path = path + '?' + query;
    path = path.replace(signatureRegExp, '-');
    body = body && body.replace(signatureRegExp, '-');

    // Get current timestamp (seconds since epoch)
    var timestamp = Math.floor(Date.now() / 1000);

    // v2: HMAC-SHA256 with timestamp
    var message = method + ':' + path + ':' + timestamp + ':' + (body || '');
    var sig = 'v2:' + hmacSha256(passwordHash, message).toLowerCase();

    // Return signature and timestamp for caller to add to URL
    return {
        signature: sig,
        timestamp: timestamp
    };
}

/**
 * Add authentication parameters to URL
 */
function addAuthParams(method, url, body) {
    if (!window.username) {
        return url;
    }

    if (url.indexOf('?') < 0) {
        url += '?';
    }
    else {
        url += '&';
    }

    url += '_username=' + window.username;

    if (window._loginDialogSubmitted) {
        url += '&_login=true';
        window._loginDialogSubmitted = false;
    }

    // Compute signature (returns {signature, timestamp})
    var sigData = computeSignature(method, url, body);

    // Add timestamp first (it's part of the signature)
    url += '&_timestamp=' + sigData.timestamp;

    // Add signature last
    url += '&_signature=' + sigData.signature;

    return url;
}
```

---

## Testing Strategy

### Test 1: Unit Test - Encoding Parity

```javascript
// Test that our encoding matches Python
function testEncodingParity() {
    var tests = [
        {input: 'hello world', expected: 'hello%20world'},
        {input: "test!'()*~", expected: "test!'()*~"}, // Safe chars
        {input: 'a=b&c=d', expected: 'a%3Db%26c%3Dd'},
        {input: '日本語', expected: '%E6%97%A5%E6%9C%AC%E8%AA%9E'}
    ];

    tests.forEach(function(test) {
        var result = encodeURIComponentRFC3986(test.input);
        console.log(test.input + ' => ' + result +
                   (result === test.expected ? ' ✓' : ' ✗ FAIL'));
    });
}
```

### Test 2: Integration Test - Signature Matching

```python
# Server-side test (Python)
from motioneye import utils

method = 'GET'
path = '/config/list/?_=1735059000000&_username=admin&test=hello world'
body = b''
key = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'  # SHA1 of empty password
timestamp = 1735059000

signature = utils.compute_signature_v2(method, path, body, key, timestamp)
print(f"Python signature: v2:{signature}")
```

```javascript
// Client-side test (JavaScript)
window.passwordHash = 'da39a3ee5e6b4b0d3255bfef95601890afd80709';
var url = '/config/list/?_=1735059000000&_username=admin&test=hello world';
var sigData = computeSignature('GET', url, '');

console.log('JS signature: ' + sigData.signature);
console.log('Timestamp: ' + sigData.timestamp);
```

**Expected**: Both should produce identical signatures (minus timestamp difference)

### Test 3: End-to-End Authentication

1. Deploy to development system
2. Clear browser cookies
3. Log in with admin credentials
4. Verify Settings panel is accessible
5. Check server logs for no 403 errors
6. Verify signature validation succeeds

---

## Rollback Strategy

If v2 implementation fails after deployment:

1. Set feature flag: `useSecureSignature = false` in main.js
2. This falls back to v1 SHA-1 signatures
3. Investigate logs and debug
4. Fix issues without breaking production

---

## Migration Path

**Phase 1**: Deploy with both v1 and v2 support (current state)
- Server accepts both signature types
- Client uses v2 by default
- Old clients continue to work with v1

**Phase 2**: Monitor and validate (1-2 weeks)
- Check logs for v1 vs v2 usage
- Verify no authentication failures
- Collect metrics on signature types

**Phase 3**: Deprecate v1 (future)
- Add warning logs when v1 signatures detected
- Set sunset date for v1 removal
- Eventually remove v1 support

---

## Success Criteria

- ✅ No JavaScript runtime errors in browser console
- ✅ Client and server signatures match exactly
- ✅ Admin can access Settings panel without 403 errors
- ✅ Replay protection works (old timestamps rejected)
- ✅ All automated tests pass
- ✅ Manual testing on Pi 4 and Pi 5 successful

---

## Documentation Updates Required

1. Update `docs/troubleshooting/admin-issues.md`:
   - Change status to "RESOLVED - v2 signatures implemented correctly"
   - Document the actual bugs that were fixed
   - Add testing procedures

2. Add `docs/security/signature-algorithm.md`:
   - Document v2 signature algorithm
   - Explain replay protection
   - Provide examples

3. Update CLAUDE.md project instructions:
   - Note that v2 signatures are now active
   - Document testing requirements for auth changes

---

## Next Steps

1. Implement the fixes in main.js
2. Add comprehensive logging to both client and server
3. Create unit tests for encoding parity
4. Test locally before deploying to Pi
5. Deploy to Pi 4 first (test system)
6. Validate thoroughly before marking as complete
7. Update all documentation

---

*This plan supersedes the incorrect "RESOLVED" status from the previous agent.*
