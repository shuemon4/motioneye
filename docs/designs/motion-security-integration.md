# Motion Security Integration Guide for MotionEye

**Target Audience:** AI Agent / Claude Code
**Purpose:** Integrate MotionEye with Motion's new security features
**Motion Version:** 5.0.0+security (Phases 1-5 implemented)
**Last Updated:** 2025-12-20

---

## Executive Summary

Motion has implemented comprehensive security hardening (rating: 9.7/10) across 5 phases. MotionEye **must** be updated to work with these security features, particularly:

1. **CSRF Protection** - All state-changing API calls require valid CSRF tokens
2. **POST Method Enforcement** - State-changing endpoints only accept POST (not GET)
3. **HA1 Digest Authentication** - Support for hashed passwords
4. **Security Headers** - New HTTP headers in all responses

**Breaking Changes:**
- GET requests to `/detection/pause`, `/detection/start`, `/action/*`, `/config/set` now return HTTP 405
- POST requests without CSRF token return HTTP 403
- All state-changing operations require valid CSRF token in request body

---

## Table of Contents

1. [Overview of Motion Security Changes](#overview-of-motion-security-changes)
2. [CSRF Token Handling](#csrf-token-handling)
3. [POST Method Migration](#post-method-migration)
4. [Authentication Changes](#authentication-changes)
5. [API Endpoint Changes](#api-endpoint-changes)
6. [Implementation Checklist](#implementation-checklist)
7. [Testing Procedures](#testing-procedures)
8. [Code Examples](#code-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview of Motion Security Changes

### Phase 1: CSRF Protection (9/10) ⚠️ BREAKING

**What Changed:**
- Every state-changing operation requires a CSRF token
- Tokens are 64-character hex strings, regenerated on Motion restart
- Tokens are injected into HTML pages as JavaScript variable `pCsrfToken`
- POST requests must include `csrf_token` parameter

**Impact on MotionEye:**
- All API calls that change state need CSRF token
- Must retrieve token before making state-changing calls
- Token must be included in POST request body

**HTTP Status Codes:**
- `403 Forbidden` - Missing or invalid CSRF token
- `405 Method Not Allowed` - GET used on POST-only endpoint

### Phase 2: Security Headers (8.5/10) ℹ️ NON-BREAKING

**What Changed:**
- Motion now sends 5 HTTP security headers in all responses
- Content-Security-Policy may affect JavaScript/CSS loading

**Impact on MotionEye:**
- Minimal impact (informational)
- May need to adjust CSP if embedding Motion pages in iframes
- Headers are informational and shouldn't break functionality

### Phase 3: Command Injection Prevention (9.3/10) ℹ️ NON-BREAKING

**What Changed:**
- Motion sanitizes shell metacharacters in user input
- Affects filenames and action parameters

**Impact on MotionEye:**
- No direct impact on API integration
- Filenames with shell metacharacters get sanitized automatically

### Phase 4: Compiler Hardening (9.5/10) ℹ️ NON-BREAKING

**What Changed:**
- Motion binary compiled with security flags (PIE, RELRO, stack canaries)

**Impact on MotionEye:**
- No impact on API integration
- Improves overall system security

### Phase 5: Credential Management (9.7/10) ℹ️ OPTIONAL

**What Changed:**
- Motion supports HA1 digest hashes instead of plaintext passwords
- Environment variable expansion for sensitive config parameters

**Impact on MotionEye:**
- MotionEye can use HA1 hashes when configuring Motion
- Backward compatible with plaintext passwords

---

## CSRF Token Handling

### Understanding CSRF Tokens

**Token Format:**
- 64 hexadecimal characters
- Generated at Motion startup
- Same token for all requests in a session
- Invalidated when Motion restarts

**Token Lifecycle:**
```
1. Motion starts → generates CSRF token
2. MotionEye fetches Motion web page → receives token in HTML
3. MotionEye extracts token from JavaScript variable
4. MotionEye includes token in all POST requests
5. Motion validates token → accepts/rejects request
```

### Retrieving CSRF Token

**Method 1: Parse HTML (Recommended)**

```python
import re
import requests

def get_csrf_token(motion_base_url, auth=None):
    """
    Retrieve CSRF token from Motion web interface.

    Args:
        motion_base_url: Base URL of Motion (e.g., 'http://localhost:8080')
        auth: Optional tuple of (username, password) for digest auth

    Returns:
        str: 64-character CSRF token

    Raises:
        ValueError: If token not found in response
    """
    # Fetch Motion homepage
    response = requests.get(
        motion_base_url,
        auth=auth,
        timeout=10
    )
    response.raise_for_status()

    # Extract token from JavaScript: pCsrfToken = 'abc123...';
    match = re.search(r"pCsrfToken\s*=\s*'([0-9a-f]{64})'", response.text)

    if not match:
        raise ValueError("CSRF token not found in Motion response")

    return match.group(1)
```

**Method 2: Custom Endpoint (If Added to Motion)**

```python
def get_csrf_token_api(motion_base_url, auth=None):
    """
    Alternative: Use dedicated CSRF token endpoint (if implemented).
    """
    response = requests.get(
        f"{motion_base_url}/0/config/csrf_token",
        auth=auth,
        timeout=10
    )
    response.raise_for_status()
    return response.json()['csrf_token']
```

### Including CSRF Token in Requests

**POST Request Format:**

```python
import requests
from requests.auth import HTTPDigestAuth

def motion_api_post(motion_base_url, endpoint, params, auth_tuple=None):
    """
    Make POST request to Motion API with CSRF token.

    Args:
        motion_base_url: Base URL of Motion
        endpoint: API endpoint (e.g., '/0/config/set')
        params: Dictionary of parameters to send
        auth_tuple: Tuple of (username, password)

    Returns:
        requests.Response object
    """
    # Get CSRF token
    csrf_token = get_csrf_token(motion_base_url, auth_tuple)

    # Add token to parameters
    params['csrf_token'] = csrf_token

    # Prepare authentication
    auth = None
    if auth_tuple:
        auth = HTTPDigestAuth(auth_tuple[0], auth_tuple[1])

    # Make POST request
    response = requests.post(
        f"{motion_base_url}{endpoint}",
        data=params,
        auth=auth,
        timeout=30
    )

    return response
```

### Token Caching Strategy

**Problem:** Fetching token on every request is inefficient

**Solution:** Cache token and refresh on 403 errors

```python
class MotionClient:
    def __init__(self, base_url, username=None, password=None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self._csrf_token = None
        self._auth = None

        if username and password:
            self._auth = HTTPDigestAuth(username, password)

    def _get_csrf_token(self, force_refresh=False):
        """Get CSRF token, with caching."""
        if self._csrf_token is None or force_refresh:
            response = requests.get(self.base_url, auth=self._auth, timeout=10)
            response.raise_for_status()

            match = re.search(r"pCsrfToken\s*=\s*'([0-9a-f]{64})'", response.text)
            if not match:
                raise ValueError("CSRF token not found")

            self._csrf_token = match.group(1)

        return self._csrf_token

    def post(self, endpoint, params):
        """Make POST request with automatic CSRF token handling."""
        # Try with cached token
        params['csrf_token'] = self._get_csrf_token()

        response = requests.post(
            f"{self.base_url}{endpoint}",
            data=params,
            auth=self._auth,
            timeout=30
        )

        # If 403, refresh token and retry once
        if response.status_code == 403:
            params['csrf_token'] = self._get_csrf_token(force_refresh=True)
            response = requests.post(
                f"{self.base_url}{endpoint}",
                data=params,
                auth=self._auth,
                timeout=30
            )

        return response
```

---

## POST Method Migration

### Affected Endpoints

**BREAKING:** These endpoints now **require** POST method:

| Endpoint Pattern | Previous | New | Description |
|------------------|----------|-----|-------------|
| `/0/detection/pause` | GET | POST | Pause motion detection |
| `/0/detection/start` | GET | POST | Start motion detection |
| `/0/detection/connection` | GET | GET | Status check (unchanged) |
| `/0/action/snapshot` | GET | POST | Take snapshot |
| `/0/action/restart` | GET | POST | Restart motion |
| `/0/action/quit` | GET | POST | Shutdown motion |
| `/0/action/eventstart` | GET | POST | Trigger event start |
| `/0/action/eventend` | GET | POST | Trigger event end |
| `/0/config/set` | GET/POST | POST | Set configuration |
| `/0/config/write` | GET/POST | POST | Write config to file |

**Safe to use GET:**

| Endpoint Pattern | Method | Description |
|------------------|--------|-------------|
| `/0/detection/status` | GET | Get detection status |
| `/0/detection/connection` | GET | Check connection |
| `/0/action/status` | GET | Get action status |
| `/0/config/get` | GET | Get configuration |
| `/0/config/list` | GET | List all config |

### Migration Examples

**Before (GET request):**
```python
# OLD - Will fail with HTTP 405
response = requests.get(
    'http://localhost:8080/0/detection/pause',
    auth=auth
)
```

**After (POST request with CSRF token):**
```python
# NEW - Required format
csrf_token = get_csrf_token('http://localhost:8080', auth)

response = requests.post(
    'http://localhost:8080/0/detection/pause',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

### URL Parameter Migration

**Before:**
```python
# OLD - Parameters in URL query string
url = f'{base_url}/0/config/set?brightness=50&contrast=100'
response = requests.get(url, auth=auth)
```

**After:**
```python
# NEW - Parameters in POST body
csrf_token = get_csrf_token(base_url, auth)

response = requests.post(
    f'{base_url}/0/config/set',
    data={
        'csrf_token': csrf_token,
        'brightness': 50,
        'contrast': 100
    },
    auth=auth
)
```

---

## Authentication Changes

### HA1 Digest Authentication

**Background:**
Motion now supports storing password hashes instead of plaintext.

**HA1 Hash Format:**
```
MD5(username:Motion:password)
```

**Example:**
```bash
# Generate HA1 hash
echo -n "admin:Motion:secretpass" | md5sum
# Output: 5f4dcc3b5aa765d61d8327deb882cf99
```

**MotionEye Configuration:**

When MotionEye writes Motion config files, it can use either:

1. **Plaintext (backward compatible):**
   ```
   webcontrol_authentication admin:secretpass
   ```

2. **HA1 hash (recommended):**
   ```
   webcontrol_authentication admin:5f4dcc3b5aa765d61d8327deb882cf99
   ```

**Detection:** Motion automatically detects 32-character hex strings as HA1 hashes.

**MotionEye Implementation:**

```python
import hashlib

def generate_ha1_hash(username, password, realm='Motion'):
    """Generate HA1 hash for Motion digest authentication."""
    ha1_input = f"{username}:{realm}:{password}"
    return hashlib.md5(ha1_input.encode()).hexdigest()

def write_motion_config_auth(username, password, use_ha1=True):
    """Write authentication to Motion config file."""
    if use_ha1:
        ha1_hash = generate_ha1_hash(username, password)
        auth_value = f"{username}:{ha1_hash}"
    else:
        auth_value = f"{username}:{password}"

    return f"webcontrol_authentication {auth_value}\n"
```

**Client-Side Authentication:**

MotionEye still needs the **plaintext password** to authenticate API requests:

```python
from requests.auth import HTTPDigestAuth

# MotionEye stores plaintext password for API calls
# Motion config file has HA1 hash
auth = HTTPDigestAuth('admin', 'secretpass')

response = requests.get(
    'http://localhost:8080/0/config/list',
    auth=auth
)
```

**Important:** The HA1 hash in the config file is for Motion's internal use. MotionEye must still authenticate with plaintext password via HTTP Digest Auth.

---

## API Endpoint Changes

### Complete Endpoint Reference

#### Detection Control

**Pause Detection (POST Required)**
```python
# Endpoint: /0/detection/pause
# Method: POST
# CSRF: Required

csrf_token = get_csrf_token(base_url, auth)
response = requests.post(
    f'{base_url}/0/detection/pause',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

**Start Detection (POST Required)**
```python
# Endpoint: /0/detection/start
# Method: POST
# CSRF: Required

csrf_token = get_csrf_token(base_url, auth)
response = requests.post(
    f'{base_url}/0/detection/start',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

**Get Detection Status (GET - Unchanged)**
```python
# Endpoint: /0/detection/status
# Method: GET
# CSRF: Not required

response = requests.get(
    f'{base_url}/0/detection/status',
    auth=auth
)
```

#### Action Endpoints

**Snapshot (POST Required)**
```python
# Endpoint: /0/action/snapshot
# Method: POST
# CSRF: Required

csrf_token = get_csrf_token(base_url, auth)
response = requests.post(
    f'{base_url}/0/action/snapshot',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

**Restart Motion (POST Required)**
```python
# Endpoint: /0/action/restart
# Method: POST
# CSRF: Required

csrf_token = get_csrf_token(base_url, auth)
response = requests.post(
    f'{base_url}/0/action/restart',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

#### Configuration Endpoints

**Set Configuration (POST Required)**
```python
# Endpoint: /0/config/set
# Method: POST
# CSRF: Required
# Parameters: Any config parameter name/value pairs

csrf_token = get_csrf_token(base_url, auth)
response = requests.post(
    f'{base_url}/0/config/set',
    data={
        'csrf_token': csrf_token,
        'brightness': 50,
        'contrast': 100,
        'threshold': 1500
    },
    auth=auth
)
```

**Get Configuration (GET - Unchanged)**
```python
# Endpoint: /0/config/get?query=brightness
# Method: GET
# CSRF: Not required

response = requests.get(
    f'{base_url}/0/config/get?query=brightness',
    auth=auth
)
```

**List All Configuration (GET - Unchanged)**
```python
# Endpoint: /0/config/list
# Method: GET
# CSRF: Not required

response = requests.get(
    f'{base_url}/0/config/list',
    auth=auth
)
```

#### Multi-Camera Endpoints

For multi-camera setups, replace `/0/` with camera number:

```python
# Camera 1: /1/detection/pause
# Camera 2: /2/detection/pause
# All cameras: /0/detection/pause

csrf_token = get_csrf_token(base_url, auth)

# Pause detection on camera 1
response = requests.post(
    f'{base_url}/1/detection/pause',
    data={'csrf_token': csrf_token},
    auth=auth
)
```

---

## Implementation Checklist

### Phase 1: Initial Integration

- [ ] **Understand CSRF Token Mechanism**
  - [ ] Read token retrieval section
  - [ ] Test token extraction from HTML
  - [ ] Verify token format (64 hex chars)

- [ ] **Update HTTP Client Code**
  - [ ] Create CSRF token retrieval function
  - [ ] Implement token caching mechanism
  - [ ] Add token refresh on 403 errors

- [ ] **Identify Affected Code Paths**
  - [ ] Search codebase for Motion API calls
  - [ ] List all state-changing operations
  - [ ] Create migration plan

### Phase 2: Endpoint Migration

- [ ] **Detection Control**
  - [ ] Migrate `pause_detection()` to POST + CSRF
  - [ ] Migrate `start_detection()` to POST + CSRF
  - [ ] Keep `get_detection_status()` as GET

- [ ] **Action Endpoints**
  - [ ] Migrate `take_snapshot()` to POST + CSRF
  - [ ] Migrate `restart_motion()` to POST + CSRF
  - [ ] Migrate all `action/*` endpoints to POST + CSRF

- [ ] **Configuration**
  - [ ] Migrate `set_config()` to POST + CSRF
  - [ ] Migrate `write_config()` to POST + CSRF
  - [ ] Keep `get_config()` and `list_config()` as GET

### Phase 3: Testing

- [ ] **Unit Tests**
  - [ ] Test CSRF token retrieval
  - [ ] Test token caching
  - [ ] Test token refresh on 403
  - [ ] Test POST request formatting

- [ ] **Integration Tests**
  - [ ] Test against Motion with security features
  - [ ] Test each migrated endpoint
  - [ ] Test multi-camera scenarios
  - [ ] Test authentication with HA1 hashes

- [ ] **Error Handling**
  - [ ] Test behavior on missing token (expect 403)
  - [ ] Test behavior on invalid token (expect 403)
  - [ ] Test behavior on GET to POST-only endpoint (expect 405)
  - [ ] Test token refresh after Motion restart

### Phase 4: Documentation

- [ ] **Update MotionEye Documentation**
  - [ ] Document Motion security requirements
  - [ ] Update API integration guide
  - [ ] Add troubleshooting section

- [ ] **Update Installation Guide**
  - [ ] Specify minimum Motion version
  - [ ] Document security configuration options

---

## Testing Procedures

### Test Environment Setup

**1. Start Motion with Security Features**
```bash
# On Raspberry Pi or test server
cd ~/motion
./configure --with-libcam --with-sqlite3
make -j4
src/motion -n -c /etc/motion/motion.conf
```

**2. Verify Security Features Enabled**
```bash
# Check CSRF protection
curl -s http://localhost:8080/0/detection/pause
# Expected: HTTP 405: Method Not Allowed

# Check security headers
curl -I http://localhost:8080/ | grep X-Frame-Options
# Expected: X-Frame-Options: SAMEORIGIN

# Check CSRF token in HTML
curl -s http://localhost:8080/ | grep pCsrfToken
# Expected: pCsrfToken = 'abc123...';
```

### Unit Tests

**Test 1: CSRF Token Retrieval**
```python
def test_csrf_token_retrieval():
    """Test CSRF token can be retrieved from Motion."""
    token = get_csrf_token('http://localhost:8080')

    assert token is not None
    assert len(token) == 64
    assert all(c in '0123456789abcdef' for c in token)
    print(f"✓ CSRF token retrieved: {token[:16]}...")
```

**Test 2: POST Request with Token**
```python
def test_post_with_csrf_token():
    """Test POST request with valid CSRF token succeeds."""
    client = MotionClient('http://localhost:8080', 'admin', 'password')

    response = client.post('/0/detection/pause', {})

    assert response.status_code in [200, 302]
    print("✓ POST request with CSRF token succeeded")
```

**Test 3: POST Request without Token**
```python
def test_post_without_csrf_token():
    """Test POST request without CSRF token fails."""
    response = requests.post(
        'http://localhost:8080/0/detection/pause',
        data={'brightness': 50},
        auth=HTTPDigestAuth('admin', 'password')
    )

    assert response.status_code == 403
    assert 'CSRF validation failed' in response.text
    print("✓ POST without CSRF token correctly rejected")
```

**Test 4: GET Request to POST-Only Endpoint**
```python
def test_get_to_post_only_endpoint():
    """Test GET request to POST-only endpoint fails."""
    response = requests.get(
        'http://localhost:8080/0/detection/pause',
        auth=HTTPDigestAuth('admin', 'password')
    )

    assert response.status_code == 405
    assert 'Method Not Allowed' in response.text
    print("✓ GET to POST-only endpoint correctly rejected")
```

### Integration Tests

**Test 5: Complete Detection Control Workflow**
```python
def test_detection_control_workflow():
    """Test complete workflow: pause, check status, resume."""
    client = MotionClient('http://localhost:8080', 'admin', 'password')

    # Pause detection
    response = client.post('/0/detection/pause', {})
    assert response.status_code in [200, 302]
    print("✓ Paused detection")

    # Check status (GET request, no CSRF needed)
    response = requests.get(
        'http://localhost:8080/0/detection/status',
        auth=client._auth
    )
    assert response.status_code == 200
    print("✓ Retrieved status")

    # Resume detection
    response = client.post('/0/detection/start', {})
    assert response.status_code in [200, 302]
    print("✓ Resumed detection")
```

**Test 6: Configuration Change**
```python
def test_configuration_change():
    """Test changing configuration parameters."""
    client = MotionClient('http://localhost:8080', 'admin', 'password')

    # Set configuration
    response = client.post('/0/config/set', {
        'brightness': 50,
        'contrast': 100
    })
    assert response.status_code in [200, 302]
    print("✓ Configuration changed")

    # Verify changes (GET request)
    response = requests.get(
        'http://localhost:8080/0/config/get?query=brightness',
        auth=client._auth
    )
    assert response.status_code == 200
    assert 'brightness' in response.text
    print("✓ Configuration verified")
```

**Test 7: Token Refresh After Motion Restart**
```python
def test_token_refresh_after_restart():
    """Test token is refreshed after Motion restarts."""
    client = MotionClient('http://localhost:8080', 'admin', 'password')

    # Get initial token
    token1 = client._get_csrf_token()
    print(f"Initial token: {token1[:16]}...")

    # Restart Motion (simulated or actual)
    # In real test: restart_motion_daemon()

    # Token should be refreshed automatically on 403
    response = client.post('/0/detection/pause', {})

    # Verify new token retrieved
    token2 = client._csrf_token
    assert token2 != token1  # Should be different after restart
    print(f"New token after restart: {token2[:16]}...")
    print("✓ Token automatically refreshed")
```

### Performance Tests

**Test 8: Token Caching Performance**
```python
import time

def test_token_caching_performance():
    """Verify token caching improves performance."""
    client = MotionClient('http://localhost:8080', 'admin', 'password')

    # Time 10 requests without caching (force refresh each time)
    start = time.time()
    for _ in range(10):
        client._get_csrf_token(force_refresh=True)
    uncached_time = time.time() - start
    print(f"Uncached: {uncached_time:.3f}s for 10 requests")

    # Time 10 requests with caching
    start = time.time()
    for _ in range(10):
        client._get_csrf_token(force_refresh=False)
    cached_time = time.time() - start
    print(f"Cached: {cached_time:.3f}s for 10 requests")

    # Caching should be significantly faster
    assert cached_time < uncached_time / 5
    print(f"✓ Caching is {uncached_time/cached_time:.1f}x faster")
```

---

## Code Examples

### Complete MotionClient Implementation

```python
import re
import requests
import hashlib
from requests.auth import HTTPDigestAuth
from typing import Optional, Dict, Any

class MotionClient:
    """
    Client for interacting with Motion API with security features.

    Handles:
    - CSRF token retrieval and caching
    - Automatic token refresh on failures
    - HTTP Digest authentication
    - POST method enforcement
    """

    def __init__(self, base_url: str, username: Optional[str] = None,
                 password: Optional[str] = None):
        """
        Initialize Motion API client.

        Args:
            base_url: Base URL of Motion (e.g., 'http://localhost:8080')
            username: Optional username for digest authentication
            password: Optional password for digest authentication
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self._csrf_token = None
        self._auth = None

        if username and password:
            self._auth = HTTPDigestAuth(username, password)

    def _get_csrf_token(self, force_refresh: bool = False) -> str:
        """
        Retrieve CSRF token from Motion, with caching.

        Args:
            force_refresh: If True, fetch new token even if cached

        Returns:
            64-character hexadecimal CSRF token

        Raises:
            ValueError: If token not found in response
            requests.RequestException: If HTTP request fails
        """
        if self._csrf_token is None or force_refresh:
            response = requests.get(
                self.base_url,
                auth=self._auth,
                timeout=10
            )
            response.raise_for_status()

            # Extract token from JavaScript variable
            match = re.search(
                r"pCsrfToken\s*=\s*'([0-9a-f]{64})'",
                response.text
            )

            if not match:
                raise ValueError("CSRF token not found in Motion response")

            self._csrf_token = match.group(1)

        return self._csrf_token

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """
        Make GET request to Motion API.

        Args:
            endpoint: API endpoint (e.g., '/0/config/list')
            params: Optional query parameters

        Returns:
            requests.Response object
        """
        url = f"{self.base_url}{endpoint}"

        response = requests.get(
            url,
            params=params,
            auth=self._auth,
            timeout=30
        )

        return response

    def post(self, endpoint: str, data: Dict[str, Any]) -> requests.Response:
        """
        Make POST request to Motion API with CSRF token.

        Automatically handles:
        - CSRF token retrieval and inclusion
        - Token refresh on 403 errors
        - Retry on token validation failure

        Args:
            endpoint: API endpoint (e.g., '/0/detection/pause')
            data: Dictionary of data to POST (CSRF token added automatically)

        Returns:
            requests.Response object
        """
        url = f"{self.base_url}{endpoint}"

        # Add CSRF token to data
        post_data = data.copy()
        post_data['csrf_token'] = self._get_csrf_token()

        # Make POST request
        response = requests.post(
            url,
            data=post_data,
            auth=self._auth,
            timeout=30
        )

        # If 403 Forbidden, token may be stale - refresh and retry once
        if response.status_code == 403 and 'CSRF' in response.text:
            post_data['csrf_token'] = self._get_csrf_token(force_refresh=True)
            response = requests.post(
                url,
                data=post_data,
                auth=self._auth,
                timeout=30
            )

        return response

    # High-level API methods

    def pause_detection(self, camera_id: int = 0) -> requests.Response:
        """Pause motion detection on specified camera."""
        return self.post(f'/{camera_id}/detection/pause', {})

    def start_detection(self, camera_id: int = 0) -> requests.Response:
        """Start motion detection on specified camera."""
        return self.post(f'/{camera_id}/detection/start', {})

    def get_detection_status(self, camera_id: int = 0) -> requests.Response:
        """Get detection status for specified camera."""
        return self.get(f'/{camera_id}/detection/status')

    def take_snapshot(self, camera_id: int = 0) -> requests.Response:
        """Take snapshot on specified camera."""
        return self.post(f'/{camera_id}/action/snapshot', {})

    def set_config(self, camera_id: int = 0, **kwargs) -> requests.Response:
        """
        Set configuration parameters.

        Example:
            client.set_config(0, brightness=50, contrast=100)
        """
        return self.post(f'/{camera_id}/config/set', kwargs)

    def get_config(self, query: str, camera_id: int = 0) -> requests.Response:
        """Get configuration parameter value."""
        return self.get(f'/{camera_id}/config/get', {'query': query})

    def list_config(self, camera_id: int = 0) -> requests.Response:
        """List all configuration parameters."""
        return self.get(f'/{camera_id}/config/list')

    @staticmethod
    def generate_ha1_hash(username: str, password: str, realm: str = 'Motion') -> str:
        """
        Generate HA1 hash for Motion digest authentication.

        Args:
            username: Username
            password: Password
            realm: Authentication realm (default: 'Motion')

        Returns:
            32-character MD5 hash
        """
        ha1_input = f"{username}:{realm}:{password}"
        return hashlib.md5(ha1_input.encode()).hexdigest()


# Usage Example
if __name__ == '__main__':
    # Initialize client
    client = MotionClient(
        'http://localhost:8080',
        username='admin',
        password='password'
    )

    # Pause detection
    response = client.pause_detection(camera_id=0)
    print(f"Pause detection: {response.status_code}")

    # Set configuration
    response = client.set_config(0, brightness=50, contrast=100)
    print(f"Set config: {response.status_code}")

    # Get configuration
    response = client.get_config('brightness', camera_id=0)
    print(f"Get config: {response.status_code}")

    # Resume detection
    response = client.start_detection(camera_id=0)
    print(f"Start detection: {response.status_code}")
```

---

## Troubleshooting

### Issue 1: HTTP 403 Forbidden - CSRF validation failed

**Symptoms:**
```
POST /0/detection/pause → 403 Forbidden
Response: "CSRF validation failed. Please reload the page and try again."
```

**Causes:**
- Missing CSRF token in POST data
- Invalid/expired CSRF token
- Motion was restarted (tokens regenerated)

**Solutions:**
1. Verify token is being retrieved:
   ```python
   token = get_csrf_token('http://localhost:8080')
   print(f"Token: {token}")
   # Should print 64 hex characters
   ```

2. Verify token is included in POST:
   ```python
   print(f"POST data: {post_data}")
   # Should include: {'csrf_token': 'abc123...', ...}
   ```

3. Force token refresh:
   ```python
   client._get_csrf_token(force_refresh=True)
   ```

4. Check Motion logs:
   ```bash
   sudo journalctl -u motion | grep CSRF
   # Look for token validation failures
   ```

### Issue 2: HTTP 405 Method Not Allowed

**Symptoms:**
```
GET /0/detection/pause → 405 Method Not Allowed
Response: "HTTP 405: Method Not Allowed\nState-changing operations must use POST method."
```

**Cause:**
- Using GET method on POST-only endpoint

**Solution:**
- Change to POST method:
  ```python
  # WRONG
  response = requests.get(f'{base_url}/0/detection/pause')

  # CORRECT
  csrf_token = get_csrf_token(base_url)
  response = requests.post(
      f'{base_url}/0/detection/pause',
      data={'csrf_token': csrf_token}
  )
  ```

### Issue 3: Token Not Found in HTML

**Symptoms:**
```python
ValueError: CSRF token not found in Motion response
```

**Causes:**
- Motion version too old (pre-security updates)
- Fetching wrong endpoint
- HTML parsing regex incorrect

**Solutions:**
1. Verify Motion version:
   ```bash
   motion --version
   # Should show 5.0.0 or later with security features
   ```

2. Check HTML response:
   ```python
   response = requests.get('http://localhost:8080')
   print(response.text[:1000])
   # Look for: pCsrfToken = 'abc123...';
   ```

3. Update regex if needed:
   ```python
   # Try alternative patterns
   match = re.search(r"pCsrfToken\s*=\s*['\"]([0-9a-f]{64})['\"]", text)
   ```

### Issue 4: Authentication Failed

**Symptoms:**
```
HTTP 401 Unauthorized
```

**Causes:**
- Wrong username/password
- Motion configured with HA1 hash but client using wrong password
- Digest auth not supported by client

**Solutions:**
1. Verify credentials:
   ```bash
   # Check Motion config
   grep webcontrol_authentication /etc/motion/motion.conf
   ```

2. Test authentication manually:
   ```bash
   curl -u admin:password http://localhost:8080/0/config/list
   ```

3. Ensure HTTPDigestAuth (not HTTPBasicAuth):
   ```python
   from requests.auth import HTTPDigestAuth
   auth = HTTPDigestAuth('admin', 'password')  # CORRECT
   ```

### Issue 5: Token Caching Issues

**Symptoms:**
- First request succeeds, subsequent requests fail
- Intermittent 403 errors

**Cause:**
- Token cached but Motion restarted
- Stale token not being refreshed

**Solution:**
- Implement proper token refresh logic:
  ```python
  def post(self, endpoint, data):
      # Try with cached token
      data['csrf_token'] = self._get_csrf_token()
      response = requests.post(url, data=data, auth=self._auth)

      # If 403, refresh and retry
      if response.status_code == 403:
          data['csrf_token'] = self._get_csrf_token(force_refresh=True)
          response = requests.post(url, data=data, auth=self._auth)

      return response
  ```

### Issue 6: Security Headers Breaking Iframe Embedding

**Symptoms:**
- Cannot embed Motion pages in MotionEye iframes
- Browser console error: "Refused to display in a frame"

**Cause:**
- `X-Frame-Options: SAMEORIGIN` header

**Solution:**
- If Motion and MotionEye are on same origin, this should work
- If different origins, you may need to modify Motion's CSP headers
- Contact Motion developers for iframe embedding support

---

## Summary for AI Implementation

**Required Changes to MotionEye:**

1. **Add CSRF Token Support:**
   - Implement token retrieval from Motion HTML
   - Cache token per Motion instance
   - Include token in all POST requests
   - Refresh token on 403 errors

2. **Migrate to POST Methods:**
   - Change all state-changing operations from GET to POST
   - Move parameters from URL query string to POST body
   - Keep read-only operations as GET

3. **Update Error Handling:**
   - Handle HTTP 403 (CSRF failure) → refresh token and retry
   - Handle HTTP 405 (wrong method) → switch to POST
   - Handle HTTP 401 (auth failure) → check credentials

4. **Optional: HA1 Hash Support:**
   - When writing Motion config, generate HA1 hashes
   - Keep plaintext passwords for API authentication
   - Generate hash: `MD5(username:Motion:password)`

**Testing Checklist:**
- [ ] Can retrieve CSRF token from Motion
- [ ] Can pause/start detection with POST + CSRF
- [ ] Can change configuration with POST + CSRF
- [ ] Can take snapshots with POST + CSRF
- [ ] Token automatically refreshes on Motion restart
- [ ] Handles authentication correctly
- [ ] Works with multi-camera setups

**Key Files to Modify in MotionEye:**
- Motion API client/wrapper (add CSRF support)
- Detection control functions (migrate to POST)
- Configuration functions (migrate to POST)
- Action handlers (migrate to POST)

**Reference Implementation:**
See `MotionClient` class in Code Examples section above.

---

**End of Integration Guide**

**Questions? Contact:** Review `doc/SECURITY_DEPLOYMENT_GUIDE.md` in Motion repository for full details.
