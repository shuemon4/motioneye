"""Tests for Motion 5.0 CSRF token integration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from tornado.httpclient import HTTPRequest


class TestCSRFTokenRetrieval:
    """Test CSRF token retrieval and caching."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset CSRF token cache before each test."""
        from motioneye import motionctl
        motionctl._csrf_token_cache = {
            'token': None,
            'timestamp': None,
            'port': None,
            'csrf_supported': None
        }

    @pytest.mark.asyncio
    async def test_csrf_token_extraction(self):
        """Test extracting CSRF token from Motion HTML."""
        from motioneye import motionctl

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

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            token = await motionctl._get_csrf_token()

            assert len(token) == 64
            assert all(c in '0123456789abcdef' for c in token)
            assert token == 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789'

    @pytest.mark.asyncio
    async def test_csrf_token_extraction_with_whitespace(self):
        """Test extracting CSRF token with various whitespace formats."""
        from motioneye import motionctl

        html = """
        <html>
        <script>
        var pCsrfToken='a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2';
        </script>
        </html>
        """

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            token = await motionctl._get_csrf_token()

            assert len(token) == 64
            assert token == 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2'

    @pytest.mark.asyncio
    async def test_csrf_token_caching(self):
        """Test CSRF token is cached and reused."""
        from motioneye import motionctl

        html = """<script>var pCsrfToken = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';</script>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
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
        from motioneye import motionctl

        html = """<script>var pCsrfToken = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';</script>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
            mock_fetch = AsyncMock(return_value=mock_response)
            mock_client.return_value.fetch = mock_fetch

            # First call
            await motionctl._get_csrf_token()

            # Force refresh
            await motionctl._get_csrf_token(force_refresh=True)

            # Verify fetch called twice
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_csrf_token_not_found_returns_none(self):
        """Test that missing CSRF token returns None for legacy Motion."""
        from motioneye import motionctl

        html = """<html><body>No token here</body></html>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            # Should return None for backward compatibility with legacy Motion
            token = await motionctl._get_csrf_token()
            assert token is None
            assert motionctl._csrf_token_cache['csrf_supported'] is False

    @pytest.mark.asyncio
    async def test_csrf_token_invalid_format_returns_none(self):
        """Test that invalid token format returns None for legacy Motion."""
        from motioneye import motionctl

        html = """<script>var pCsrfToken = 'tooshort';</script>"""

        mock_response = Mock()
        mock_response.body = html.encode('utf-8')
        mock_response.code = 200

        with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
            mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

            # Should return None (invalid format doesn't match regex)
            token = await motionctl._get_csrf_token()
            assert token is None


class TestLegacyFallback:
    """Test legacy GET fallback for Motion without CSRF."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset CSRF token cache before each test."""
        from motioneye import motionctl
        motionctl._csrf_token_cache = {
            'token': None,
            'timestamp': None,
            'port': None,
            'csrf_supported': None
        }

    @pytest.mark.asyncio
    async def test_uses_get_when_csrf_not_supported(self):
        """Test that GET is used when Motion doesn't have CSRF."""
        from motioneye import motionctl

        # Mock _get_csrf_token to return None (no CSRF support)
        with patch.object(motionctl, '_get_csrf_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = None

            with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
                mock_response = Mock()
                mock_response.code = 200
                mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

                await motionctl._make_motion_request('http://test.com/endpoint', {})

                # Verify GET request was made (no method specified = GET)
                call_args = mock_client.return_value.fetch.call_args
                request = call_args[0][0]

                # GET request doesn't have method specified or body
                assert request.method == 'GET' or not hasattr(request, 'method') or request.method is None
                assert not hasattr(request, 'body') or request.body is None


class TestPostWithCSRF:
    """Test POST requests with CSRF token."""

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset CSRF token cache before each test."""
        from motioneye import motionctl
        motionctl._csrf_token_cache = {
            'token': None,
            'timestamp': None,
            'port': None,
            'csrf_supported': None
        }

    @pytest.mark.asyncio
    async def test_post_includes_csrf_token(self):
        """Test POST request includes CSRF token in body."""
        from motioneye import motionctl

        test_token = 'a' * 64

        with patch.object(motionctl, '_get_csrf_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = test_token

            with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
                mock_response = Mock()
                mock_response.code = 200
                mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

                # Use command parameter for CSRF mode
                await motionctl._make_motion_request('http://test.com/endpoint', command='test_cmd', camid=1)

                # Verify POST request made with CSRF token
                call_args = mock_client.return_value.fetch.call_args
                request = call_args[0][0]

                assert request.method == 'POST'
                body = request.body if isinstance(request.body, str) else request.body.decode('utf-8')
                assert 'csrf_token=' in body
                assert test_token in body
                assert 'command=test_cmd' in body
                assert request.headers['Content-Type'] == 'application/x-www-form-urlencoded'

    @pytest.mark.asyncio
    async def test_post_includes_data(self):
        """Test POST request includes provided data."""
        from motioneye import motionctl

        test_token = 'b' * 64

        with patch.object(motionctl, '_get_csrf_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = test_token

            with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
                mock_response = Mock()
                mock_response.code = 200
                mock_client.return_value.fetch = AsyncMock(return_value=mock_response)

                await motionctl._make_motion_request('http://test.com/endpoint', data={'brightness': '50'}, command='config', camid=1)

                call_args = mock_client.return_value.fetch.call_args
                request = call_args[0][0]
                body = request.body if isinstance(request.body, str) else request.body.decode('utf-8')

                assert 'brightness=50' in body
                assert f'csrf_token={test_token}' in body

    @pytest.mark.asyncio
    async def test_post_retries_on_403(self):
        """Test POST request retries with fresh token on 403."""
        from motioneye import motionctl

        with patch.object(motionctl, '_get_csrf_token', new_callable=AsyncMock) as mock_get_token:
            # Return different tokens on each call
            mock_get_token.side_effect = [
                'oldtoken' + 'a' * 56,
                'newtoken' + 'b' * 56
            ]

            with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
                # First response: 403, second response: 200
                mock_response_403 = Mock()
                mock_response_403.code = 403

                mock_response_200 = Mock()
                mock_response_200.code = 200

                mock_client.return_value.fetch = AsyncMock(side_effect=[mock_response_403, mock_response_200])

                resp = await motionctl._make_motion_request('http://test.com/endpoint', command='test', camid=1)

                # Verify retry occurred
                assert mock_client.return_value.fetch.call_count == 2
                assert resp.code == 200
                # Verify force_refresh was called
                mock_get_token.assert_any_call(force_refresh=True)

    @pytest.mark.asyncio
    async def test_post_returns_403_after_retry_failure(self):
        """Test POST returns 403 if retry also fails."""
        from motioneye import motionctl

        with patch.object(motionctl, '_get_csrf_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = 'c' * 64

            with patch.object(motionctl, 'AsyncHTTPClient') as mock_client:
                # Both responses: 403
                mock_response_403 = Mock()
                mock_response_403.code = 403

                mock_client.return_value.fetch = AsyncMock(return_value=mock_response_403)

                resp = await motionctl._make_motion_request('http://test.com/endpoint', command='test', camid=1)

                # Should still return 403 response
                assert resp.code == 403


class TestSetMotionDetection:
    """Test set_motion_detection() function with CSRF."""

    @pytest.mark.asyncio
    async def test_pause_detection_uses_command(self):
        """Test pausing detection uses pause_on command."""
        from motioneye import motionctl

        with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
            with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                mock_response = Mock()
                mock_response.code = 200
                mock_request.return_value = mock_response

                await motionctl.set_motion_detection(1, False)

                # Verify command=pause_on for disabling detection
                call_kwargs = mock_request.call_args[1]
                assert call_kwargs['command'] == 'pause_on'
                assert call_kwargs['camid'] == 1

    @pytest.mark.asyncio
    async def test_start_detection_uses_command(self):
        """Test starting detection uses pause_off command."""
        from motioneye import motionctl

        with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
            with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                mock_response = Mock()
                mock_response.code = 200
                mock_request.return_value = mock_response

                await motionctl.set_motion_detection(1, True)

                call_kwargs = mock_request.call_args[1]
                assert call_kwargs['command'] == 'pause_off'

    @pytest.mark.asyncio
    async def test_detection_handles_302_as_success(self):
        """Test 302 response is treated as success."""
        from motioneye import motionctl

        with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
            with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                mock_response = Mock()
                mock_response.code = 302
                mock_request.return_value = mock_response

                # Should not raise, 302 is success
                await motionctl.set_motion_detection(1, True)


class TestTakeSnapshot:
    """Test take_snapshot() function with CSRF."""

    @pytest.mark.asyncio
    async def test_snapshot_uses_command(self):
        """Test taking snapshot uses snapshot command."""
        from motioneye import motionctl

        with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
            with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                mock_response = Mock()
                mock_response.code = 200
                mock_request.return_value = mock_response

                await motionctl.take_snapshot(1)

                # Verify command=snapshot
                call_kwargs = mock_request.call_args[1]
                assert call_kwargs['command'] == 'snapshot'
                assert call_kwargs['camid'] == 1


class TestSetConfigHot:
    """Test set_config_hot() function with CSRF."""

    @pytest.mark.asyncio
    async def test_config_uses_command(self):
        """Test config change uses config command."""
        from motioneye import motionctl

        # Use a parameter that is actually in HOT_RELOAD_PARAMS
        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
                with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                    mock_response = Mock()
                    mock_response.code = 200
                    mock_response.body = b'{"status": "ok", "hot_reload": true}'
                    mock_request.return_value = mock_response

                    # threshold is in HOT_RELOAD_PARAMS
                    result = await motionctl.set_config_hot(1, 'threshold', '2000')

                    # Verify command=config with data
                    call_kwargs = mock_request.call_args[1]
                    assert call_kwargs['command'] == 'config'
                    assert call_kwargs['data'] == {'threshold': '2000'}
                    assert result['success'] is True

    @pytest.mark.asyncio
    async def test_config_includes_param_in_data(self):
        """Test config parameter is included in data dict."""
        from motioneye import motionctl

        # Use libcam_contrast which is in HOT_RELOAD_PARAMS
        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=1):
                with patch.object(motionctl, '_make_motion_request', new_callable=AsyncMock) as mock_request:
                    mock_response = Mock()
                    mock_response.code = 200
                    mock_response.body = b'{"status": "ok", "hot_reload": true}'
                    mock_request.return_value = mock_response

                    await motionctl.set_config_hot(1, 'libcam_contrast', '75')

                    call_kwargs = mock_request.call_args[1]
                    # Data should include the parameter
                    assert call_kwargs['data'] == {'libcam_contrast': '75'}
                    assert call_kwargs['camid'] == 1
