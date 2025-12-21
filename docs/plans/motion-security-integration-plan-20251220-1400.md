# Motion 5.0 Security Integration Implementation Plan

**Document Type**: Implementation Plan
**Date**: 2025-12-20 14:00
**Author**: Claude Code
**Purpose**: Step-by-step implementation plan for Motion 5.0 CSRF integration
**Status**: Ready to Execute

---

## Overview

This plan details the implementation of CSRF token support and POST method migration required for MotionEye compatibility with Motion 5.0 security features.

**Related Documents**:
- Analysis: `docs/analysis/motion-security-integration-changes-20251220-1400.md`
- Scratchpad: `docs/scratchpads/motion-security-integration-notes-20251220-1400.md`
- Motion Integration Guide: `docs/designs/motion-security-integration.md`

---

## Implementation Phases

### Phase 1: Core Infrastructure (2-3 hours)
- CSRF token cache structure
- Token retrieval function
- POST helper function

### Phase 2: API Migration (2-3 hours)
- Migrate set_motion_detection()
- Migrate take_snapshot()
- Migrate set_config_hot()

### Phase 3: Testing (3-4 hours)
- Unit tests
- Integration tests
- Manual testing on Pi 5

### Phase 4: Documentation (1-2 hours)
- Update user documentation
- Create troubleshooting guide
- Update developer documentation

**Total Estimated Time**: 8-12 hours

---

## Phase 1: Core Infrastructure

### Step 1.1: Add CSRF Token Cache

**File**: `motioneye/motionctl.py`
**Location**: After line 43 (after `_motion_detected = {}`)

**Code to Add**:

```python
# CSRF token cache for Motion 5.0+ security
_csrf_token_cache = {
    'token': None,
    'timestamp': None,
    'port': None
}
```

**Verification**:
- Code compiles without errors
- Cache initialized on module load

---

### Step 1.2: Implement _get_csrf_token()

**File**: `motioneye/motionctl.py`
**Location**: After `_get_pid()` function (after line 562), before `set_config_hot()`

**Implementation**:

```python
async def _get_csrf_token(force_refresh: bool = False) -> str:
    """
    Retrieve CSRF token from Motion web interface, with caching.

    Args:
        force_refresh: If True, bypass cache and fetch new token

    Returns:
        64-character hexadecimal CSRF token

    Raises:
        Exception: If token cannot be retrieved from Motion
    """
    global _csrf_token_cache

    # Check cache validity
    if not force_refresh:
        cached_token = _csrf_token_cache.get('token')
        cached_port = _csrf_token_cache.get('port')

        if cached_token and cached_port == settings.MOTION_CONTROL_PORT:
            logging.debug(f'Using cached CSRF token: {cached_token[:16]}...')
            return cached_token

    # Fetch Motion homepage
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'

    try:
        request = HTTPRequest(
            url,
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )
        resp = await AsyncHTTPClient().fetch(request)

        # Extract token from JavaScript variable: pCsrfToken = 'abc123...';
        html = resp.body.decode('utf-8')
        match = re.search(r"pCsrfToken\s*=\s*'([0-9a-f]{64})'", html)

        if not match:
            raise Exception('CSRF token not found in Motion response')

        token = match.group(1)

        # Update cache
        _csrf_token_cache['token'] = token
        _csrf_token_cache['port'] = settings.MOTION_CONTROL_PORT
        _csrf_token_cache['timestamp'] = time.time()

        logging.debug(f'Retrieved CSRF token from Motion: {token[:16]}...')

        return token

    except Exception as e:
        logging.error(f'Failed to retrieve CSRF token from Motion: {e}')
        raise Exception(f'CSRF token retrieval failed: {e}')
```

**Testing**:

```python
# Quick test in Python shell
import asyncio
from motioneye import motionctl

async def test():
    token = await motionctl._get_csrf_token()
    print(f"Token: {token}")
    print(f"Length: {len(token)}")
    assert len(token) == 64
    assert all(c in '0123456789abcdef' for c in token)

asyncio.run(test())
```

**Verification**:
- Function compiles
- Returns 64-character hex string
- Caches token correctly
- Logs token retrieval at DEBUG level

---

### Step 1.3: Implement _post_with_csrf()

**File**: `motioneye/motionctl.py`
**Location**: After `_get_csrf_token()` function

**Implementation**:

```python
async def _post_with_csrf(url: str, data: dict = None) -> 'HTTPResponse':
    """
    Make POST request to Motion API with CSRF token and automatic retry.

    Handles CSRF token retrieval, caching, and automatic refresh on 403 errors.

    Args:
        url: Full URL to Motion API endpoint
        data: Dictionary of POST parameters (CSRF token added automatically)

    Returns:
        HTTPResponse object

    Raises:
        Exception: If request fails after token refresh retry
    """
    from urllib.parse import urlencode

    # Prepare POST data with CSRF token
    post_data = dict(data or {})
    post_data['csrf_token'] = await _get_csrf_token()

    # Encode data for POST
    body = urlencode(post_data)

    # Make POST request
    request = HTTPRequest(
        url,
        method='POST',
        body=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )

    resp = await AsyncHTTPClient().fetch(request, raise_error=False)

    # Handle 403: CSRF token may be stale, refresh and retry once
    if resp.code == 403:
        logging.warning('CSRF token validation failed (HTTP 403), refreshing token and retrying')

        # Refresh token and retry
        post_data['csrf_token'] = await _get_csrf_token(force_refresh=True)
        body = urlencode(post_data)

        request = HTTPRequest(
            url,
            method='POST',
            body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            connect_timeout=_MOTION_CONTROL_TIMEOUT,
            request_timeout=_MOTION_CONTROL_TIMEOUT,
        )

        resp = await AsyncHTTPClient().fetch(request, raise_error=False)

        if resp.code == 403:
            logging.error('CSRF token validation failed after refresh - check Motion configuration')

    return resp
```

**Testing**:

```python
# Quick test
async def test():
    url = 'http://127.0.0.1:7999/1/detection/pause'
    resp = await motionctl._post_with_csrf(url, {})
    print(f"Status: {resp.code}")
    print(f"Body: {resp.body}")

asyncio.run(test())
```

**Verification**:
- Function compiles
- Makes POST request with CSRF token
- Handles 403 with retry
- Logs retry attempts

---

## Phase 2: API Migration

### Step 2.1: Migrate set_motion_detection()

**File**: `motioneye/motionctl.py`
**Location**: Lines 250-285

**Current Code**:

```python
async def set_motion_detection(camera_id, enabled):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    if not enabled:
        _motion_detected[camera_id] = False

    logging.debug(
        f"{['disabling', 'enabling'][enabled]} motion detection for camera with id {camera_id}"
    )

    url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{['pause', 'start'][enabled]}"

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        logging.error(
            'failed to {} motion detection for camera with id {}: {}'.format(
                ['disable', 'enable'][enabled],
                camera_id,
                utils.pretty_http_error(resp),
            )
        )

    else:
        logging.debug(
            f"successfully {['disabled', 'enabled'][enabled]} motion detection for camera with id {camera_id}"
        )
```

**Updated Code**:

```python
async def set_motion_detection(camera_id, enabled):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    if not enabled:
        _motion_detected[camera_id] = False

    endpoint = 'start' if enabled else 'pause'
    action = 'enable' if enabled else 'disable'

    logging.debug(f"{action}ing motion detection for camera with id {camera_id}")

    url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{endpoint}"

    try:
        resp = await _post_with_csrf(url, {})

        if resp.code in [200, 302]:
            logging.debug(f"successfully {action}d motion detection for camera with id {camera_id}")
        else:
            logging.error(f'failed to {action} motion detection for camera {camera_id}: HTTP {resp.code}')

    except Exception as e:
        logging.error(f'failed to {action} motion detection for camera {camera_id}: {e}')
```

**Testing**:

```python
# Test pause
await motionctl.set_motion_detection(1, False)
# Verify: camera 1 detection paused

# Test start
await motionctl.set_motion_detection(1, True)
# Verify: camera 1 detection started
```

**Verification**:
- Function compiles
- Uses POST method
- Includes CSRF token
- Handles errors gracefully
- Logs operations correctly

---

### Step 2.2: Migrate take_snapshot()

**File**: `motioneye/motionctl.py`
**Location**: Lines 287-311

**Current Code**:

```python
async def take_snapshot(camera_id):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    logging.debug(f'taking snapshot for camera with id {camera_id}')

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'

    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
    if resp.error:
        logging.error(
            f'failed to take snapshot for camera with id {camera_id}: {utils.pretty_http_error(resp)}'
        )

    else:
        logging.debug(f'successfully took snapshot for camera with id {camera_id}')
```

**Updated Code**:

```python
async def take_snapshot(camera_id):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(
            f'could not find motion camera id for camera with id {camera_id}'
        )

    logging.debug(f'taking snapshot for camera with id {camera_id}')

    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'

    try:
        resp = await _post_with_csrf(url, {})

        if resp.code in [200, 302]:
            logging.debug(f'successfully took snapshot for camera with id {camera_id}')
        else:
            logging.error(f'failed to take snapshot for camera {camera_id}: HTTP {resp.code}')

    except Exception as e:
        logging.error(f'failed to take snapshot for camera {camera_id}: {e}')
```

**Testing**:

```python
# Test snapshot
await motionctl.take_snapshot(1)
# Verify: snapshot file created in target directory
```

**Verification**:
- Function compiles
- Uses POST method
- Includes CSRF token
- Snapshot file created
- Logs correctly

---

### Step 2.3: Migrate set_config_hot()

**File**: `motioneye/motionctl.py`
**Location**: Lines 564-658

**Current Code** (key section):

```python
# URL encode the value
encoded_value = urllib.parse.quote(str(value), safe='')
url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set?{param}={encoded_value}'

try:
    request = HTTPRequest(
        url,
        connect_timeout=_MOTION_CONTROL_TIMEOUT,
        request_timeout=_MOTION_CONTROL_TIMEOUT,
    )
    resp = await AsyncHTTPClient().fetch(request)
```

**Updated Code**:

Replace lines 606-616 with:

```python
url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set'
post_data = {param: str(value)}

try:
    resp = await _post_with_csrf(url, post_data)
```

**Full Updated Function**:

```python
async def set_config_hot(camera_id: int, param: str, value: str) -> dict:
    """
    Set a Motion parameter at runtime via hot reload API.

    Args:
        camera_id: MotionEye camera ID
        param: Motion parameter name
        value: New value for the parameter

    Returns:
        dict with keys:
            - success: bool
            - hot_reload: bool (True if applied without restart)
            - old_value: str (previous value, if available)
            - error: str (error message, if failed)
    """
    from motioneye.config.camera.constants import HOT_RELOAD_PARAMS

    # Early check - if not in our known hot-reload list, don't try
    if param not in HOT_RELOAD_PARAMS:
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Parameter requires daemon restart'
        }

    # Check Motion version
    if not is_motion_50():
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Motion 5.0+ required for hot reload'
        }

    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return {
            'success': False,
            'hot_reload': False,
            'error': f'Could not find motion camera id for camera {camera_id}'
        }

    # Build URL and POST data
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set'
    post_data = {param: str(value)}

    try:
        resp = await _post_with_csrf(url, post_data)

        if resp.code == 200:
            try:
                data = json.loads(resp.body.decode('utf-8'))

                if data.get('status') == 'ok' and data.get('hot_reload'):
                    logging.debug(f'Hot reload: {param}={value} on camera {camera_id}')
                    return {
                        'success': True,
                        'hot_reload': True,
                        'old_value': data.get('old_value', '')
                    }
                else:
                    # Motion reported the parameter needs restart
                    return {
                        'success': False,
                        'hot_reload': False,
                        'error': data.get('error', 'Parameter requires daemon restart')
                    }
            except json.JSONDecodeError:
                # Fallback for non-JSON response (older API format)
                logging.debug(f'Hot reload (non-JSON): {param}={value} on camera {camera_id}')
                return {
                    'success': True,
                    'hot_reload': True,
                    'old_value': ''
                }
        else:
            return {
                'success': False,
                'hot_reload': False,
                'error': f'HTTP {resp.code}'
            }

    except Exception as e:
        logging.error(f'Failed to hot-reload {param}: {e}')
        return {
            'success': False,
            'hot_reload': False,
            'error': str(e)
        }
```

**Testing**:

```python
# Test hot config change
result = await motionctl.set_config_hot(1, 'brightness', '50')
assert result['success'] == True
assert result['hot_reload'] == True
```

**Verification**:
- Function compiles
- Uses POST method
- Params in POST body, not URL
- Includes CSRF token
- Returns correct result dict

---

## Phase 3: Testing

### Step 3.1: Create Unit Tests

**File**: `tests/test_motionctl_csrf.py` (new file)

**Implementation**:

```python
import pytest
import re
from unittest.mock import Mock, patch, AsyncMock
from tornado.httpclient import HTTPRequest, HTTPResponse
from motioneye import motionctl


class TestCSRFTokenRetrieval:
    """Test CSRF token retrieval and caching."""

    @pytest.mark.asyncio
    async def test_csrf_token_extraction(self):
        """Test extracting CSRF token from Motion HTML."""
        html = """
        <html>
        <script>
        var pCsrfToken = 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789';
        </script>
        </html>
        """

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            token = await motionctl._get_csrf_token()

            assert len(token) == 64
            assert all(c in '0123456789abcdef' for c in token)
            assert token == 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'

    @pytest.mark.asyncio
    async def test_csrf_token_caching(self):
        """Test CSRF token is cached and reused."""
        html = """<script>var pCsrfToken = 'a' * 64;</script>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
            mock_fetch = AsyncMock(return_value=mock_response)
            mock_client.return_value.fetch = mock_fetch

            # First call - should fetch
            token1 = await motionctl._get_csrf_token()

            # Second call - should use cache
            token2 = await motionctl._get_csrf_token()

            # Verify fetch called only once
            assert mock_fetch.call_count == 1
            assert token1 == token2

    @pytest.mark.asyncio
    async def test_csrf_token_refresh(self):
        """Test CSRF token refresh when force_refresh=True."""
        html = """<script>var pCsrfToken = 'b' * 64;</script>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
            mock_fetch = AsyncMock(return_value=mock_response)
            mock_client.return_value.fetch = mock_fetch

            # First call
            await motionctl._get_csrf_token()

            # Force refresh
            await motionctl._get_csrf_token(force_refresh=True)

            # Verify fetch called twice
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_csrf_token_not_found(self):
        """Test error handling when CSRF token not found in HTML."""
        html = """<html><body>No token here</body></html>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            with pytest.raises(Exception, match='CSRF token not found'):
                await motionctl._get_csrf_token()


class TestPostWithCSRF:
    """Test POST requests with CSRF token."""

    @pytest.mark.asyncio
    async def test_post_includes_csrf_token(self):
        """Test POST request includes CSRF token in body."""
        with patch('motioneye.motionctl._get_csrf_token') as mock_get_token:
            mock_get_token.return_value = 'a' * 64

            with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
                mock_response = Mock()
                mock_response.code = 200
                mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

                await motionctl._post_with_csrf('http://test.com/endpoint', {})

                # Verify POST request made with CSRF token
                call_args = mock_client.return_value.fetch.call_args
                request = call_args[0][0]

                assert request.method == 'POST'
                assert 'csrf_token=' in request.body
                assert request.headers['Content-Type'] == 'application/x-www-form-urlencoded'

    @pytest.mark.asyncio
    async def test_post_retries_on_403(self):
        """Test POST request retries with fresh token on 403."""
        with patch('motioneye.motionctl._get_csrf_token') as mock_get_token:
            mock_get_token.side_effect = ['oldtoken' + 'a' * 56, 'newtoken' + 'b' * 56]

            with patch('motioneye.motionctl.AsyncHTTPClient') as mock_client:
                # First response: 403, second response: 200
                mock_response_403 = Mock()
                mock_response_403.code = 403

                mock_response_200 = Mock()
                mock_response_200.code = 200

                mock_client.return_value.fetch = AsyncMock(side_effect=[mock_response_403, mock_response_200])

                resp = await motionctl._post_with_csrf('http://test.com/endpoint', {})

                # Verify retry occurred
                assert mock_client.return_value.fetch.call_count == 2
                assert resp.code == 200


class TestSetMotionDetection:
    """Test set_motion_detection() function."""

    @pytest.mark.asyncio
    async def test_pause_detection_uses_post(self):
        """Test pausing detection uses POST method."""
        with patch('motioneye.motionctl.camera_id_to_motion_camera_id', return_value=1):
            with patch('motioneye.motionctl._post_with_csrf') as mock_post:
                mock_response = Mock()
                mock_response.code = 200
                mock_post.return_value = mock_response

                await motionctl.set_motion_detection(1, False)

                # Verify POST called with correct URL
                call_args = mock_post.call_args
                assert '/detection/pause' in call_args[0][0]
                assert call_args[0][1] == {}  # Empty data dict


class TestTakeSnapshot:
    """Test take_snapshot() function."""

    @pytest.mark.asyncio
    async def test_snapshot_uses_post(self):
        """Test taking snapshot uses POST method."""
        with patch('motioneye.motionctl.camera_id_to_motion_camera_id', return_value=1):
            with patch('motioneye.motionctl._post_with_csrf') as mock_post:
                mock_response = Mock()
                mock_response.code = 200
                mock_post.return_value = mock_response

                await motionctl.take_snapshot(1)

                # Verify POST called
                call_args = mock_post.call_args
                assert '/action/snapshot' in call_args[0][0]
```

**Run Tests**:

```bash
cd /Users/tshuey/Documents/GitHub/motioneye
python -m pytest tests/test_motionctl_csrf.py -v
```

**Verification**:
- All tests pass
- Code coverage > 90% for modified functions

---

### Step 3.2: Create Integration Tests

**File**: `tests/integration/test_motion_security.py` (new file)

**Prerequisites**:
- Motion 5.0+ running on localhost:7999
- Camera configured

**Implementation**:

```python
import pytest
import asyncio
from motioneye import motionctl


@pytest.mark.integration
class TestMotionSecurityIntegration:
    """Integration tests against real Motion 5.0+ instance."""

    @pytest.mark.asyncio
    async def test_csrf_token_retrieval(self):
        """Test retrieving CSRF token from running Motion instance."""
        token = await motionctl._get_csrf_token(force_refresh=True)

        assert token is not None
        assert len(token) == 64
        assert all(c in '0123456789abcdef' for c in token)

    @pytest.mark.asyncio
    async def test_detection_pause_start_cycle(self):
        """Test pausing and starting detection."""
        # Pause detection
        await motionctl.set_motion_detection(1, False)

        # Verify status
        result = await motionctl.get_motion_detection(1)
        assert result.enabled == False

        # Start detection
        await motionctl.set_motion_detection(1, True)

        # Verify status
        result = await motionctl.get_motion_detection(1)
        assert result.enabled == True

    @pytest.mark.asyncio
    async def test_snapshot_capture(self):
        """Test capturing snapshot."""
        # Take snapshot
        await motionctl.take_snapshot(1)

        # Verify snapshot file created (implementation depends on Motion config)
        # This would check the snapshot directory for new files

    @pytest.mark.asyncio
    async def test_hot_config_change(self):
        """Test hot configuration change."""
        # Change brightness
        result = await motionctl.set_config_hot(1, 'brightness', '50')

        assert result['success'] == True
        assert result['hot_reload'] == True
```

**Run Tests**:

```bash
# On Raspberry Pi 5
cd ~/motioneye
python -m pytest tests/integration/test_motion_security.py -v -m integration
```

**Verification**:
- All integration tests pass
- Operations complete successfully
- No errors in Motion logs

---

### Step 3.3: Manual Testing on Raspberry Pi 5

**Deployment**:

```bash
# From Mac
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
  /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/

ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"

ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
```

**Manual Test Checklist**:

```bash
# 1. Check MotionEye started
ssh admin@192.168.1.176 "sudo systemctl status motioneye"

# 2. Check logs for CSRF token retrieval
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager | grep CSRF"

# 3. Test via web interface
# - Open http://192.168.1.176:8765/
# - Pause/start detection via UI
# - Take snapshot via UI
# - Change settings (brightness, contrast)

# 4. Verify Motion logs show POST requests
ssh admin@192.168.1.176 "sudo journalctl -u motion -n 50 --no-pager | grep POST"

# 5. Test CSRF token refresh by restarting Motion
ssh admin@192.168.1.176 "sudo systemctl restart motion"
# Then perform operation via MotionEye UI
# Verify: Token automatically refreshed

# 6. Check for errors
ssh admin@192.168.1.176 "sudo journalctl -u motioneye -p err -n 50 --no-pager"
```

**Expected Results**:
- ✅ MotionEye starts without errors
- ✅ CSRF token retrieved on first operation
- ✅ Token cached and reused
- ✅ All camera operations work
- ✅ Token automatically refreshes after Motion restart
- ✅ No HTTP 403 or 405 errors

---

## Phase 4: Documentation

### Step 4.1: Update User Documentation

**File**: `docs/MotionEye-Integration-Guide.md`

**Add Section** (after "## Important: Platform-Specific Updates"):

```markdown
---

## Motion Version Requirements

**Important**: MotionEye requires Motion 5.0 or later due to security enhancements in the Motion API.

### Checking Your Motion Version

On your Raspberry Pi, run:

```bash
motion -h | grep Version
```

**Expected output**: `motion Version 5.0.0` or higher

### If Running Motion 4.x

You must upgrade Motion to version 5.0+ before using this version of MotionEye. Motion 5.0 introduced CSRF protection and other security features that are required for compatibility.

**Upgrade Instructions**:

1. Check latest release: https://github.com/Motion-Project/motion/releases
2. Follow Motion installation instructions for Raspberry Pi
3. Verify version after upgrade
4. Restart MotionEye service

### Security Features in Motion 5.0

Motion 5.0 includes comprehensive security hardening:

- **CSRF Protection**: All state-changing operations require CSRF tokens
- **POST Method Enforcement**: API calls use POST instead of GET
- **Security Headers**: HTTP security headers in all responses
- **Command Injection Prevention**: Shell metacharacter sanitization

MotionEye fully supports these security features.

---
```

**Verification**:
- Section reads clearly
- Instructions are accurate
- Links work

---

### Step 4.2: Create Troubleshooting Guide

**File**: `docs/troubleshooting/motion-api-errors.md` (new file)

**Content**:

```markdown
# Motion API Troubleshooting Guide

This guide covers common errors when MotionEye communicates with Motion.

---

## HTTP 403 Forbidden - CSRF Validation Failed

### Symptoms

- Error in logs: `CSRF token validation failed (HTTP 403)`
- Camera operations fail (pause/start detection, snapshot, config changes)

### Causes

1. Motion CSRF token has become stale
2. Motion was restarted
3. Communication issue between MotionEye and Motion

### Solutions

**Automatic Recovery**:
MotionEye automatically refreshes the CSRF token on 403 errors. The operation should succeed on retry.

**Manual Steps**:

1. Check Motion is running:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion logs for errors:
   ```bash
   sudo journalctl -u motion -n 100 --no-pager
   ```

3. Restart MotionEye to clear cache:
   ```bash
   sudo systemctl restart motioneye
   ```

4. If problem persists, verify Motion version:
   ```bash
   motion -h | grep Version
   ```
   Expected: 5.0.0 or higher

---

## HTTP 405 Method Not Allowed

### Symptoms

- Error in logs: `Motion rejected request: wrong HTTP method`
- API calls fail with HTTP 405

### Cause

Version mismatch between MotionEye and Motion.

### Solution

1. Verify Motion version is 5.0+:
   ```bash
   motion -h | grep Version
   ```

2. Verify MotionEye is up to date:
   ```bash
   pip3 show motioneye | grep Version
   ```

3. If Motion < 5.0, upgrade Motion
4. If issue persists, file a bug report

---

## CSRF Token Not Found

### Symptoms

- Error in logs: `CSRF token not found in Motion response`
- MotionEye cannot communicate with Motion

### Causes

1. Motion version too old (< 5.0)
2. Motion not running
3. Wrong port configured

### Solutions

1. Verify Motion is running:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion web interface accessible:
   ```bash
   curl http://127.0.0.1:7999/
   ```

3. Verify Motion control port in MotionEye settings (default: 7999)

4. Check Motion version:
   ```bash
   motion -h | grep Version
   ```
   Must be 5.0 or higher

---

## Connection Timeout

### Symptoms

- Error in logs: `Connection timeout`
- Operations take a long time then fail

### Causes

1. Motion is overloaded
2. Network issue on localhost
3. Motion crashed/hung

### Solutions

1. Check Motion status:
   ```bash
   sudo systemctl status motion
   ```

2. Check Motion CPU usage:
   ```bash
   top -p $(pgrep motion)
   ```

3. Restart Motion if hung:
   ```bash
   sudo systemctl restart motion
   ```

4. Check MotionEye timeout settings (default: 5 seconds)

---

## Performance Issues

### Symptoms

- Slow response from camera operations
- Delayed snapshot capture
- UI lag

### Solutions

1. Check CSRF token caching is working:
   - Look for `Using cached CSRF token` in DEBUG logs
   - Should NOT see token retrieval on every request

2. Enable DEBUG logging:
   ```bash
   # In motioneye.conf
   log_level debug
   ```

3. Monitor token retrieval frequency:
   ```bash
   sudo journalctl -u motioneye -f | grep "CSRF token"
   ```

Expected: Token retrieved once per Motion session, cached for subsequent requests

---

## Getting Help

If none of these solutions work:

1. Collect logs:
   ```bash
   sudo journalctl -u motioneye -n 200 > motioneye.log
   sudo journalctl -u motion -n 200 > motion.log
   ```

2. Check versions:
   ```bash
   motion -h | grep Version
   pip3 show motioneye | grep Version
   ```

3. File issue at: https://github.com/motioneye-project/motioneye/issues

Include:
- Log files
- Motion version
- MotionEye version
- Description of problem
- Steps to reproduce
```

**Verification**:
- Document is clear and helpful
- All commands tested and work
- Links correct

---

### Step 4.3: Update CLAUDE.md

**File**: `CLAUDE.md`

**Add Section** (in "## Important: Platform-Specific Updates"):

```markdown
### Motion 5.0 Security Integration

Motion 5.0 introduced CSRF protection and POST method enforcement for all state-changing API operations.

**Implementation**: `motioneye/motionctl.py`

**Key Functions**:
- `_get_csrf_token()` - Retrieves and caches CSRF token from Motion
- `_post_with_csrf()` - Makes POST requests with automatic CSRF token and retry on 403
- `set_motion_detection()` - Migrated to POST + CSRF
- `take_snapshot()` - Migrated to POST + CSRF
- `set_config_hot()` - Migrated to POST + CSRF

**CSRF Token Flow**:
1. MotionEye fetches Motion homepage (http://127.0.0.1:7999/)
2. Extracts token from JavaScript: `pCsrfToken = '[64-hex-chars]';`
3. Caches token for reuse
4. Includes token in all POST requests as `csrf_token` parameter
5. Automatically refreshes on HTTP 403 errors

**Testing on Pi 5**:
1. Deploy code to Pi 5
2. Restart MotionEye service
3. Check logs for CSRF token retrieval
4. Test pause/start detection, snapshot, config changes
5. Verify no HTTP 403/405 errors

**Troubleshooting**:
- HTTP 403: Token validation failed → automatic retry with fresh token
- HTTP 405: Wrong method (indicates bug)
- Token not found: Check Motion version (must be 5.0+)
```

**Verification**:
- Section provides clear context for AI agents
- Covers key implementation details
- Includes troubleshooting tips

---

## Deployment Plan

### Pre-Deployment Checklist

- [ ] All code changes committed
- [ ] All unit tests pass
- [ ] Code reviewed (if applicable)
- [ ] Documentation updated
- [ ] Backup of current MotionEye configuration

### Deployment Steps

1. **Backup Current State**
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl stop motioneye"
   ssh admin@192.168.1.176 "sudo tar -czf ~/motioneye-backup-$(date +%Y%m%d).tar.gz /etc/motioneye /var/lib/motioneye"
   ```

2. **Deploy New Code**
   ```bash
   rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' \
     /Users/tshuey/Documents/GitHub/motioneye/ admin@192.168.1.176:~/motioneye/
   ```

3. **Install**
   ```bash
   ssh admin@192.168.1.176 "cd ~/motioneye && sudo pip3 install . --break-system-packages"
   ```

4. **Restart Services**
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl restart motioneye"
   ```

5. **Verify Deployment**
   ```bash
   ssh admin@192.168.1.176 "sudo systemctl status motioneye"
   ssh admin@192.168.1.176 "sudo journalctl -u motioneye -n 50 --no-pager"
   ```

6. **Test Operations**
   - Open web interface
   - Test pause/start detection
   - Test snapshot
   - Test settings changes

### Rollback Plan

If deployment fails:

```bash
# Stop MotionEye
ssh admin@192.168.1.176 "sudo systemctl stop motioneye"

# Restore from backup
ssh admin@192.168.1.176 "sudo tar -xzf ~/motioneye-backup-YYYYMMDD.tar.gz -C /"

# Reinstall previous version
ssh admin@192.168.1.176 "cd ~/motioneye && git checkout <previous-commit> && sudo pip3 install . --break-system-packages"

# Restart
ssh admin@192.168.1.176 "sudo systemctl start motioneye"
```

---

## Success Criteria

### Functional Requirements

- ✅ CSRF token retrieved successfully from Motion
- ✅ Token cached and reused for multiple requests
- ✅ Automatic token refresh on 403 errors
- ✅ All camera operations work (pause/start, snapshot, config)
- ✅ Multi-camera support functional
- ✅ Hot reload functionality preserved

### Performance Requirements

- ✅ No significant performance degradation (< 5% overhead)
- ✅ Token caching reduces HTTP requests
- ✅ Operations complete within normal timeframes

### Quality Requirements

- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Code coverage > 90% for modified functions
- ✅ No new linter errors
- ✅ Documentation complete and accurate

### User Experience Requirements

- ✅ No user-visible breaking changes
- ✅ Clear error messages
- ✅ Helpful troubleshooting documentation
- ✅ Smooth upgrade path

---

## Timeline

### Estimated Duration: 8-12 hours

**Phase 1**: Core Infrastructure (2-3 hours)
- Day 1, Morning

**Phase 2**: API Migration (2-3 hours)
- Day 1, Afternoon

**Phase 3**: Testing (3-4 hours)
- Day 2, Morning + Afternoon

**Phase 4**: Documentation (1-2 hours)
- Day 2, Late Afternoon

**Deployment**: (1 hour)
- Day 2 or Day 3

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Breaking existing functionality | HIGH | LOW | Comprehensive testing |
| CSRF token caching bugs | MEDIUM | LOW | Unit tests, retry logic |
| Performance degradation | LOW | LOW | Benchmarking, caching |
| Motion version incompatibility | HIGH | MEDIUM | Version detection, docs |
| Deployment failure on Pi 5 | MEDIUM | LOW | Backup, rollback plan |

---

## Post-Implementation Tasks

### Week 1
- [ ] Monitor logs for errors
- [ ] Collect user feedback (if applicable)
- [ ] Address any bug reports

### Week 2
- [ ] Review performance metrics
- [ ] Optimize if needed
- [ ] Update FAQ based on user questions

### Month 1
- [ ] Consider backward compatibility for Motion 4.x (if demand exists)
- [ ] Evaluate security posture
- [ ] Plan additional security enhancements

---

## Related Work

This implementation should be coordinated with other security improvements identified in:

- `docs/analysis/security-plan-analysis.md` - Overall security gaps
- `docs/scratchpads/security-analysis-20251218-1000.md` - MotionEye security audit
- `docs/plans/security-optimization-plan-20251218-1030.md` - Broader security plan

**Recommendation**: Complete Motion security integration FIRST (blocking issue), then address other security improvements.

---

**End of Implementation Plan**

**Status**: Ready to Execute
**Next Action**: Begin Phase 1 - Core Infrastructure Implementation
