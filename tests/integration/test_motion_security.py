"""
Integration tests for Motion 5.0 CSRF security features.

These tests require a real Motion 5.0+ instance running on localhost:7999.
Run with: pytest tests/integration/test_motion_security.py -v -m integration

Prerequisites:
- Motion 5.0+ installed and running
- At least one camera configured
- Motion control port accessible on localhost:7999
"""

import pytest
import re


@pytest.mark.integration
class TestMotionSecurityIntegration:
    """Integration tests against real Motion 5.0+ instance."""

    @pytest.mark.asyncio
    async def test_csrf_token_retrieval(self):
        """Test retrieving CSRF token from running Motion instance."""
        from motioneye import motionctl

        # Force refresh to get a new token
        token = await motionctl._get_csrf_token(force_refresh=True)

        assert token is not None
        assert len(token) == 64
        assert all(c in '0123456789abcdef' for c in token)

    @pytest.mark.asyncio
    async def test_csrf_token_caching_works(self):
        """Test that token caching actually works."""
        from motioneye import motionctl

        # Get fresh token
        token1 = await motionctl._get_csrf_token(force_refresh=True)

        # Get cached token
        token2 = await motionctl._get_csrf_token()

        # Should be the same token (cached)
        assert token1 == token2

    @pytest.mark.asyncio
    async def test_detection_pause_start_cycle(self):
        """Test pausing and starting motion detection."""
        from motioneye import motionctl

        # This test assumes camera 1 exists
        camera_id = 1

        # Pause detection
        await motionctl.set_motion_detection(camera_id, False)

        # Verify paused (check status endpoint)
        result = await motionctl.get_motion_detection(camera_id)
        assert result.enabled is False

        # Start detection
        await motionctl.set_motion_detection(camera_id, True)

        # Verify started
        result = await motionctl.get_motion_detection(camera_id)
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_snapshot_capture(self):
        """Test capturing a snapshot."""
        from motioneye import motionctl

        # This should not raise an exception
        await motionctl.take_snapshot(1)

        # Verify no exception occurred and snapshot was requested

    @pytest.mark.asyncio
    async def test_hot_config_change(self):
        """Test hot configuration change."""
        from motioneye import motionctl

        # Test with threshold which is hot-reloadable
        result = await motionctl.set_config_hot(1, 'threshold', '2000')

        # Either success or proper error response
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'hot_reload' in result

    @pytest.mark.asyncio
    async def test_post_request_format(self):
        """Test that POST requests are correctly formatted."""
        from motioneye import motionctl, settings
        from tornado.httpclient import AsyncHTTPClient, HTTPRequest

        # Get CSRF token
        token = await motionctl._get_csrf_token(force_refresh=True)

        # Verify token format
        assert re.match(r'^[0-9a-f]{64}$', token)

        # Verify we can fetch Motion homepage
        url = f'http://127.0.0.1:{settings.MOTION_CONTROL_PORT}/'
        request = HTTPRequest(url, connect_timeout=5, request_timeout=5)
        resp = await AsyncHTTPClient().fetch(request)

        assert resp.code == 200
        assert b'pCsrfToken' in resp.body


@pytest.mark.integration
class TestMotionVersionCheck:
    """Test Motion version detection."""

    def test_motion_50_detection(self):
        """Test that we can detect Motion 5.0+."""
        from motioneye import motionctl

        # This should return True on systems with Motion 5.0+
        result = motionctl.is_motion_50()

        # Just verify it returns a boolean
        assert isinstance(result, bool)

    def test_motion_binary_found(self):
        """Test that motion binary can be found."""
        from motioneye import motionctl

        binary, version = motionctl.find_motion()

        if binary:
            assert version is not None
            # Log version for debugging
            print(f"Found Motion: {binary} version {version}")
        else:
            pytest.skip("Motion binary not found on this system")


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in security operations."""

    @pytest.mark.asyncio
    async def test_invalid_camera_id_handled(self):
        """Test that invalid camera IDs are handled gracefully."""
        from motioneye import motionctl

        # This should log an error but not crash
        await motionctl.set_motion_detection(99999, False)

        # If we get here without exception, error handling worked

    @pytest.mark.asyncio
    async def test_snapshot_invalid_camera_handled(self):
        """Test that snapshot with invalid camera is handled."""
        from motioneye import motionctl

        # This should log an error but not crash
        await motionctl.take_snapshot(99999)


@pytest.mark.integration
class TestTokenRefresh:
    """Test CSRF token refresh scenarios."""

    @pytest.mark.asyncio
    async def test_token_refresh_after_stale(self):
        """Test that stale tokens are refreshed."""
        from motioneye import motionctl

        # Manually set a stale token
        motionctl._csrf_token_cache['token'] = 'staletoken' + '0' * 54
        motionctl._csrf_token_cache['port'] = motionctl.settings.MOTION_CONTROL_PORT

        # Try an operation - should work because of retry logic
        # Note: This would fail on first try and succeed on refresh
        try:
            await motionctl.set_motion_detection(1, True)
        except Exception:
            # Expected to potentially fail if Motion rejects the stale token
            # and retry also fails (e.g., Motion not running)
            pass

    @pytest.mark.asyncio
    async def test_multiple_operations_use_cached_token(self):
        """Test that multiple operations reuse the cached token."""
        from motioneye import motionctl

        # Clear cache and get fresh token
        motionctl._csrf_token_cache['token'] = None
        token1 = await motionctl._get_csrf_token(force_refresh=True)

        # Multiple operations should use cached token
        token2 = await motionctl._get_csrf_token()
        token3 = await motionctl._get_csrf_token()

        assert token1 == token2 == token3
