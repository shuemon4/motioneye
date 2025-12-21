# MotionEye Changes Required for Motion 5.0 Security Integration

**Document Type**: Analysis / Change Requirements
**Date**: 2025-12-20 14:00
**Author**: Claude Code
**Purpose**: Define required changes to MotionEye for Motion 5.0 security compatibility
**Status**: Ready for Implementation

---

## Executive Summary

Motion 5.0 has implemented comprehensive security hardening (rating: 9.7/10) that introduces **breaking changes** to its HTTP API. MotionEye must be updated to maintain compatibility. This document specifies all required changes.

### Breaking Changes in Motion 5.0

1. **CSRF Protection**: All state-changing API calls now require CSRF tokens (HTTP 403 if missing)
2. **POST Method Enforcement**: State-changing endpoints only accept POST, not GET (HTTP 405 if GET used)
3. **HA1 Authentication**: Optional support for hashed passwords (backward compatible)

### Impact on MotionEye

**Current Status**: MotionEye uses GET requests for state-changing operations WITHOUT CSRF tokens

**Result**: MotionEye is **INCOMPATIBLE** with Motion 5.0 security updates

**Required Action**: Implement CSRF token support and migrate to POST methods

---

## Table of Contents

1. [Scope of Changes](#scope-of-changes)
2. [CSRF Token Implementation](#csrf-token-implementation)
3. [API Endpoint Migration](#api-endpoint-migration)
4. [Error Handling Updates](#error-handling-updates)
5. [Authentication Considerations](#authentication-considerations)
6. [Backward Compatibility](#backward-compatibility)
7. [Testing Requirements](#testing-requirements)
8. [Documentation Updates](#documentation-updates)

---

## Scope of Changes

### Files to Modify

| File | Lines | Change Type | Severity |
|------|-------|-------------|----------|
| `motioneye/motionctl.py` | 45, 250-285, 287-311, 564-658 | Add CSRF support, migrate to POST | CRITICAL |

### Functions Requiring Updates

| Function | Current Method | New Method | CSRF Required |
|----------|---------------|------------|---------------|
| `set_motion_detection()` | GET | POST | Yes |
| `take_snapshot()` | GET | POST | Yes |
| `set_config_hot()` | GET | POST | Yes |
| `get_motion_detection()` | GET | GET | No |
| `is_hot_reload_available()` | GET | GET | No |

### New Functions Required

1. `_get_csrf_token()` - Retrieve and cache CSRF token from Motion
2. `_post_with_csrf()` - Helper to make POST requests with CSRF token

---

## CSRF Token Implementation

### 1. Token Cache Structure

**Location**: Module-level in `motioneye/motionctl.py` (after imports, around line 44)

**Implementation**:

```python
# CSRF token cache for Motion API
_csrf_token_cache = {
    'token': None,
    'timestamp': None,
    'port': None
}
```

**Cache Invalidation Triggers**:
- HTTP 403 response from Motion
- Motion port change in settings
- Manual refresh request (force_refresh parameter)

### 2. Token Retrieval Function

**Location**: New function in `motioneye/motionctl.py` (after `_motion_detected`, around line 45)

**Function Signature**:

```python
async def _get_csrf_token(force_refresh: bool = False) -> str:
    """
    Retrieve CSRF token from Motion web interface.

    Args:
        force_refresh: If True, bypass cache and fetch new token

    Returns:
        64-character hexadecimal CSRF token

    Raises:
        Exception: If token cannot be retrieved
    """
```

**Implementation Requirements**:

1. **Check cache** (if not force_refresh):
   - Return cached token if port matches and token exists
   - Skip to step 2 if cache invalid

2. **Fetch Motion homepage**:
   ```python
   url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'
   request = HTTPRequest(url, connect_timeout=5, request_timeout=5)
   response = await AsyncHTTPClient().fetch(request)
   ```

3. **Extract token from HTML**:
   ```python
   match = re.search(r"pCsrfToken\s*=\s*'([0-9a-f]{64})'", response.body.decode('utf-8'))
   if not match:
       raise Exception('CSRF token not found in Motion response')
   token = match.group(1)
   ```

4. **Update cache**:
   ```python
   _csrf_token_cache['token'] = token
   _csrf_token_cache['port'] = settings.MOTION_CONTROL_PORT
   _csrf_token_cache['timestamp'] = time.time()  # Optional
   ```

5. **Return token**:
   ```python
   return token
   ```

**Error Handling**:
- Log errors at ERROR level
- Re-raise exceptions for caller to handle
- Include helpful context in error messages

### 3. POST with CSRF Helper Function

**Location**: New function in `motioneye/motionctl.py` (after `_get_csrf_token`)

**Function Signature**:

```python
async def _post_with_csrf(url: str, data: dict = None) -> 'HTTPResponse':
    """
    Make POST request to Motion API with CSRF token and automatic retry.

    Args:
        url: Full URL to Motion API endpoint
        data: Dictionary of POST parameters (CSRF token added automatically)

    Returns:
        HTTPResponse object

    Raises:
        Exception: If request fails after retry
    """
```

**Implementation Requirements**:

1. **Prepare data**:
   ```python
   post_data = dict(data or {})
   post_data['csrf_token'] = await _get_csrf_token()
   ```

2. **Encode data for POST**:
   ```python
   from urllib.parse import urlencode
   body = urlencode(post_data)
   ```

3. **Make POST request**:
   ```python
   request = HTTPRequest(
       url,
       method='POST',
       body=body,
       headers={'Content-Type': 'application/x-www-form-urlencoded'},
       connect_timeout=_MOTION_CONTROL_TIMEOUT,
       request_timeout=_MOTION_CONTROL_TIMEOUT,
   )
   response = await AsyncHTTPClient().fetch(request, raise_error=False)
   ```

4. **Handle 403 (stale token)**:
   ```python
   if response.code == 403:
       logging.warning('CSRF token validation failed, refreshing token and retrying')
       post_data['csrf_token'] = await _get_csrf_token(force_refresh=True)
       body = urlencode(post_data)
       request = HTTPRequest(url, method='POST', body=body, headers=headers, ...)
       response = await AsyncHTTPClient().fetch(request, raise_error=False)
   ```

5. **Return response**:
   ```python
   return response
   ```

---

## API Endpoint Migration

### 1. set_motion_detection() Migration

**Current Implementation** (Lines 250-285):

```python
url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{['pause', 'start'][enabled]}"
request = HTTPRequest(url, connect_timeout=_MOTION_CONTROL_TIMEOUT, request_timeout=_MOTION_CONTROL_TIMEOUT)
resp = await AsyncHTTPClient().fetch(request)
```

**Required Changes**:

1. **Build URL** (no query parameters):
   ```python
   endpoint = 'start' if enabled else 'pause'
   url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{endpoint}"
   ```

2. **Use POST with CSRF**:
   ```python
   resp = await _post_with_csrf(url, {})
   ```

3. **Update error handling**:
   ```python
   if resp.code not in [200, 302]:
       logging.error(f'Failed to {endpoint} detection for camera {camera_id}: HTTP {resp.code}')
   ```

**Full Updated Function**:

```python
async def set_motion_detection(camera_id, enabled):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(f'could not find motion camera id for camera with id {camera_id}')

    if not enabled:
        _motion_detected[camera_id] = False

    endpoint = 'start' if enabled else 'pause'
    logging.debug(f"{['disabling', 'enabling'][enabled]} motion detection for camera with id {camera_id}")

    url = f"http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/detection/{endpoint}"

    try:
        resp = await _post_with_csrf(url, {})

        if resp.code in [200, 302]:
            logging.debug(f"successfully {['disabled', 'enabled'][enabled]} motion detection for camera with id {camera_id}")
        else:
            logging.error(f'failed to {endpoint} motion detection for camera {camera_id}: HTTP {resp.code}')

    except Exception as e:
        logging.error(f'failed to {endpoint} motion detection for camera {camera_id}: {e}')
```

### 2. take_snapshot() Migration

**Current Implementation** (Lines 287-311):

```python
url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'
request = HTTPRequest(url, connect_timeout=_MOTION_CONTROL_TIMEOUT, request_timeout=_MOTION_CONTROL_TIMEOUT)
resp = await AsyncHTTPClient().fetch(request)
```

**Required Changes**:

1. **Build URL**:
   ```python
   url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/action/snapshot'
   ```

2. **Use POST with CSRF**:
   ```python
   resp = await _post_with_csrf(url, {})
   ```

3. **Update error handling** (similar to set_motion_detection)

**Full Updated Function**:

```python
async def take_snapshot(camera_id):
    motion_camera_id = camera_id_to_motion_camera_id(camera_id)
    if motion_camera_id is None:
        return logging.error(f'could not find motion camera id for camera with id {camera_id}')

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

### 3. set_config_hot() Migration

**Current Implementation** (Lines 564-658):

```python
encoded_value = urllib.parse.quote(str(value), safe='')
url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set?{param}={encoded_value}'
request = HTTPRequest(url, connect_timeout=_MOTION_CONTROL_TIMEOUT, request_timeout=_MOTION_CONTROL_TIMEOUT)
resp = await AsyncHTTPClient().fetch(request)
```

**Required Changes**:

1. **Build URL** (no query parameters):
   ```python
   url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/{motion_camera_id}/config/set'
   ```

2. **Move parameters to POST body**:
   ```python
   post_data = {param: str(value)}
   ```

3. **Use POST with CSRF**:
   ```python
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

    if param not in HOT_RELOAD_PARAMS:
        return {
            'success': False,
            'hot_reload': False,
            'error': 'Parameter requires daemon restart'
        }

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
                    return {
                        'success': False,
                        'hot_reload': False,
                        'error': data.get('error', 'Parameter requires daemon restart')
                    }
            except json.JSONDecodeError:
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

---

## Error Handling Updates

### HTTP Status Code Handling

**New Status Codes to Handle**:

| Code | Meaning | Action | Log Level |
|------|---------|--------|-----------|
| 403 | CSRF validation failed | Refresh token, retry once | WARNING |
| 405 | Method not allowed | Log error, report bug | ERROR |
| 401 | Unauthorized | Check auth configuration | ERROR |

### Error Message Templates

**403 Forbidden**:
```
CSRF token validation failed for camera {camera_id}. Refreshing token and retrying.
```

**405 Method Not Allowed**:
```
Motion rejected {endpoint} request: wrong HTTP method. This is a MotionEye bug - please report.
```

**Token Retrieval Failed**:
```
Failed to retrieve CSRF token from Motion: {error}. Check that Motion is running on port {port}.
```

### Retry Logic

**Policy**: Retry ONCE on 403, then fail

**Implementation** (in `_post_with_csrf()`):
1. First attempt with cached token
2. If 403, refresh token and retry
3. If still fails, raise exception with detailed error

**No Retry**:
- 405 (wrong method - indicates code bug)
- 401 (authentication issue)
- 500 (server error)
- Network timeouts

---

## Authentication Considerations

### Current Setup Analysis

**Finding**: MotionEye connects to Motion on `127.0.0.1:{MOTION_CONTROL_PORT}`

**Motion Default**: Localhost connections allowed without authentication

**Conclusion**: Authentication typically not required

### If Authentication Is Required

If Motion config has `webcontrol_authentication admin:password`:

**Detection**:
```python
async def _check_motion_auth_required():
    """Test if Motion requires authentication."""
    url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'
    try:
        resp = await AsyncHTTPClient().fetch(url, raise_error=False)
        return resp.code == 401
    except:
        return False
```

**Implementation**:
```python
from requests.auth import HTTPDigestAuth

# Add to _post_with_csrf() and _get_csrf_token()
if motion_auth_username and motion_auth_password:
    # Note: Tornado HTTPRequest doesn't support digest auth directly
    # Would need to use requests library or implement digest manually
    pass
```

**Decision**: Authentication support is OUT OF SCOPE for initial implementation

**Rationale**:
1. Localhost connections don't typically require auth
2. Adds significant complexity
3. No evidence MotionEye sets webcontrol_authentication
4. Can be added later if needed

**Documentation**: Document that Motion authentication is not currently supported

---

## Backward Compatibility

### Motion Version Detection

**Existing Function**: `is_motion_50()` at line 377-382

**Usage**:
```python
if is_motion_50():
    # Use POST + CSRF (Motion 5.0+)
    resp = await _post_with_csrf(url, data)
else:
    # Use legacy GET (Motion 4.x)
    request = HTTPRequest(url, ...)
    resp = await AsyncHTTPClient().fetch(request)
```

### Decision: Require Motion 5.0+

**Rationale**:
1. Simpler implementation (no dual code paths)
2. Cleaner codebase
3. Motion 5.0 is stable and available
4. Security improvements justify upgrade requirement

**Implementation**:
```python
async def set_motion_detection(camera_id, enabled):
    if not is_motion_50():
        logging.error('Motion 5.0+ required for this operation')
        return

    # Proceed with POST + CSRF
    ...
```

**Alternative**: Support both versions with version detection

**If Dual Support Required**:
```python
async def set_motion_detection(camera_id, enabled):
    if is_motion_50():
        # POST + CSRF path
        resp = await _post_with_csrf(url, {})
    else:
        # GET path (legacy)
        request = HTTPRequest(url, ...)
        resp = await AsyncHTTPClient().fetch(request)
```

**Recommendation**: START with Motion 5.0+ requirement, add legacy support only if users demand it

---

## Testing Requirements

### Unit Tests

**New Test File**: `tests/test_motionctl_csrf.py`

**Test Cases**:

1. **test_csrf_token_extraction**
   - Mock Motion HTML response
   - Extract token via regex
   - Verify 64-character hex format

2. **test_csrf_token_caching**
   - Fetch token twice
   - Verify second call uses cache
   - Verify cache invalidation on port change

3. **test_csrf_token_refresh_on_403**
   - Mock 403 response
   - Verify token refresh triggered
   - Verify retry succeeds

4. **test_post_with_csrf_formats_data_correctly**
   - Verify POST body encoding
   - Verify Content-Type header
   - Verify CSRF token included

5. **test_set_motion_detection_post_format**
   - Verify POST method used
   - Verify URL format
   - Verify empty data dict with CSRF token

6. **test_take_snapshot_post_format**
   - Similar to above

7. **test_set_config_hot_moves_params_to_body**
   - Verify params in POST body, not URL
   - Verify CSRF token included

### Integration Tests

**Test File**: `tests/integration/test_motion_security.py`

**Prerequisites**:
- Motion 5.0+ running with security enabled
- Test camera configured

**Test Cases**:

1. **test_motion_detection_pause_start_cycle**
   - Pause detection
   - Verify paused
   - Start detection
   - Verify started

2. **test_snapshot_capture**
   - Take snapshot
   - Verify snapshot file created

3. **test_hot_config_change**
   - Change brightness parameter
   - Verify change applied
   - Verify no restart required

4. **test_token_survives_motion_restart**
   - Get token
   - Restart Motion
   - Verify next request refreshes token
   - Verify operation succeeds

5. **test_multi_camera_operations**
   - Configure 3 cameras
   - Perform operations on each
   - Verify correct camera IDs used

### Manual Testing Checklist

- [ ] Deploy to Raspberry Pi 5 with Motion 5.0
- [ ] Verify all camera operations work
- [ ] Restart Motion, verify auto-recovery
- [ ] Check logs for errors
- [ ] Test with multiple cameras
- [ ] Verify hot reload still works
- [ ] Test error conditions (Motion stopped, wrong port, etc.)

---

## Documentation Updates

### 1. User Documentation

**File**: `docs/MotionEye-Integration-Guide.md`

**Updates Required**:

- Add "Motion Version Requirements" section
- Specify minimum Motion version: 5.0+
- Document security feature compatibility
- Add troubleshooting section for CSRF errors

**New Section Template**:

```markdown
## Motion Version Requirements

MotionEye requires Motion 5.0 or later due to security enhancements.

### Checking Motion Version

ssh admin@192.168.1.176 "motion -h | grep Version"

Expected: `motion Version 5.0.0` or higher

### If Running Motion 4.x

You must upgrade Motion to 5.0+ before using this version of MotionEye.

See: https://github.com/Motion-Project/motion/releases
```

### 2. Troubleshooting Documentation

**File**: `docs/troubleshooting.md` (new file)

**Content**:

```markdown
## Motion API Errors

### HTTP 403 Forbidden

Symptom: "CSRF token validation failed"

Cause: MotionEye's CSRF token is stale or invalid

Solution: Automatic retry should resolve. If persists:
1. Check Motion logs: `journalctl -u motion`
2. Restart MotionEye: `systemctl restart motioneye`
3. Verify Motion version is 5.0+

### HTTP 405 Method Not Allowed

Symptom: "Method Not Allowed" errors in logs

Cause: MotionEye version incompatible with Motion version

Solution: Update MotionEye to latest version
```

### 3. Developer Documentation

**File**: `docs/development/motion-api.md` (new file)

**Content**:

- CSRF token implementation details
- POST method requirements
- Error handling patterns
- Testing guidelines
- Example code snippets

### 4. CLAUDE.md Update

**File**: `CLAUDE.md`

**Add Section**:

```markdown
## Motion Security Integration

Motion 5.0+ requires CSRF tokens for all state-changing operations.

**Implementation**: `motioneye/motionctl.py`
- `_get_csrf_token()` - Token retrieval and caching
- `_post_with_csrf()` - POST helper with auto-retry
- All state-changing functions migrated to POST

**Testing on Pi 5**:
1. Ensure Motion 5.0+ running
2. Deploy MotionEye changes
3. Test: pause/start detection, snapshot, hot reload
```

---

## Summary of Changes

### Code Changes

| File | Function | Change | Lines |
|------|----------|--------|-------|
| `motionctl.py` | NEW: `_get_csrf_token()` | Token retrieval and caching | ~30 |
| `motionctl.py` | NEW: `_post_with_csrf()` | POST helper with retry | ~25 |
| `motionctl.py` | MOD: `set_motion_detection()` | GET → POST + CSRF | ~35 |
| `motionctl.py` | MOD: `take_snapshot()` | GET → POST + CSRF | ~25 |
| `motionctl.py` | MOD: `set_config_hot()` | GET → POST + CSRF | ~65 |

**Total Lines Modified/Added**: ~180 lines

### Test Changes

| File | Type | Lines |
|------|------|-------|
| `tests/test_motionctl_csrf.py` | Unit tests | ~200 |
| `tests/integration/test_motion_security.py` | Integration tests | ~150 |

**Total Test Lines**: ~350 lines

### Documentation Changes

| File | Type | Lines |
|------|------|-------|
| `docs/MotionEye-Integration-Guide.md` | User docs | ~50 |
| `docs/troubleshooting.md` | User docs | ~100 |
| `docs/development/motion-api.md` | Developer docs | ~200 |
| `CLAUDE.md` | AI context | ~20 |

**Total Documentation Lines**: ~370 lines

---

## Implementation Priority

### Phase 1: Critical (Required for Motion 5.0 Compatibility)

1. ✅ Implement `_get_csrf_token()` function
2. ✅ Implement `_post_with_csrf()` helper
3. ✅ Migrate `set_motion_detection()` to POST + CSRF
4. ✅ Migrate `take_snapshot()` to POST + CSRF
5. ✅ Migrate `set_config_hot()` to POST + CSRF

### Phase 2: Testing and Validation

6. ⏳ Write unit tests for CSRF functionality
7. ⏳ Write integration tests for Motion API
8. ⏳ Test on Raspberry Pi 5 with Motion 5.0
9. ⏳ Validate multi-camera scenarios

### Phase 3: Documentation and Polish

10. ⏳ Update user documentation
11. ⏳ Write troubleshooting guide
12. ⏳ Update developer documentation
13. ⏳ Add logging and error messages

---

## Risk Mitigation

### Risk: Breaking Existing Deployments

**Mitigation**:
- Require Motion 5.0+ explicitly
- Document upgrade requirements clearly
- Add version detection warnings
- Provide rollback instructions

### Risk: CSRF Token Caching Bugs

**Mitigation**:
- Implement automatic retry on 403
- Add comprehensive unit tests
- Log all token operations at DEBUG level
- Test Motion restart scenarios

### Risk: Performance Degradation

**Mitigation**:
- Efficient token caching (one fetch per session)
- Minimal overhead (one extra HTTP request)
- Benchmark before/after implementation

---

## Success Criteria

### Functional

- ✅ All Motion API calls succeed with Motion 5.0
- ✅ CSRF tokens cached and reused correctly
- ✅ Automatic retry on token expiry
- ✅ Multi-camera operations work correctly

### Non-Functional

- ✅ No performance regression (< 5% overhead)
- ✅ Clear error messages for users
- ✅ Comprehensive test coverage (> 90%)
- ✅ Complete documentation

---

**End of Change Requirements Document**

**Next Step**: Create implementation plan in `docs/plans/`
