"""Tests for Motion 5.0 hot-reload integration."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from motioneye.config.camera.constants import HOT_RELOAD_PARAMS, RESTART_REQUIRED_PARAMS


class TestParameterClassification:
    """Test parameter classification constants."""

    def test_hot_reload_params_not_empty(self):
        """HOT_RELOAD_PARAMS should contain parameters."""
        assert len(HOT_RELOAD_PARAMS) > 0

    def test_restart_required_params_not_empty(self):
        """RESTART_REQUIRED_PARAMS should contain parameters."""
        assert len(RESTART_REQUIRED_PARAMS) > 0

    def test_no_overlap(self):
        """Hot-reload and restart-required sets should not overlap."""
        overlap = HOT_RELOAD_PARAMS & RESTART_REQUIRED_PARAMS
        assert len(overlap) == 0, f"Parameters in both sets: {overlap}"

    def test_threshold_is_hot_reloadable(self):
        """Threshold should be hot-reloadable."""
        assert 'threshold' in HOT_RELOAD_PARAMS

    def test_width_requires_restart(self):
        """Width should require restart."""
        assert 'width' in RESTART_REQUIRED_PARAMS

    def test_text_left_is_hot_reloadable(self):
        """Text overlay should be hot-reloadable."""
        assert 'text_left' in HOT_RELOAD_PARAMS

    def test_stream_quality_is_hot_reloadable(self):
        """Stream quality should be hot-reloadable."""
        assert 'stream_quality' in HOT_RELOAD_PARAMS

    def test_stream_port_requires_restart(self):
        """Stream port should require restart."""
        assert 'stream_port' in RESTART_REQUIRED_PARAMS

    def test_movie_quality_is_hot_reloadable(self):
        """Movie quality should be hot-reloadable."""
        assert 'movie_quality' in HOT_RELOAD_PARAMS

    def test_movie_codec_requires_restart(self):
        """Movie codec should require restart."""
        assert 'movie_codec' in RESTART_REQUIRED_PARAMS


class TestSetConfigHot:
    """Test set_config_hot function."""

    @pytest.mark.asyncio
    async def test_rejects_non_hot_reload_param(self):
        """Should reject parameters not in HOT_RELOAD_PARAMS."""
        from motioneye import motionctl

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            result = await motionctl.set_config_hot(1, 'width', '1920')

        assert result['success'] is False
        assert result['hot_reload'] is False
        assert 'restart' in result['error'].lower()

    @pytest.mark.asyncio
    async def test_rejects_old_motion_version(self):
        """Should reject if Motion < 5.0."""
        from motioneye import motionctl

        with patch.object(motionctl, 'is_motion_50', return_value=False):
            result = await motionctl.set_config_hot(1, 'threshold', '2000')

        assert result['success'] is False
        assert 'Motion 5.0' in result['error']

    @pytest.mark.asyncio
    async def test_rejects_invalid_camera_id(self):
        """Should reject if camera ID cannot be mapped."""
        from motioneye import motionctl

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'camera_id_to_motion_camera_id', return_value=None):
                result = await motionctl.set_config_hot(999, 'threshold', '2000')

        assert result['success'] is False
        assert result['hot_reload'] is False
        assert 'camera' in result['error'].lower()


class TestApplyConfigChanges:
    """Test apply_config_changes function."""

    @pytest.mark.asyncio
    async def test_identifies_changed_params(self):
        """Should correctly identify changed parameters."""
        from motioneye import motionctl

        old_config = {'threshold': '1500', 'width': '1920', '@enabled': True}
        new_config = {'threshold': '2000', 'width': '1920', '@enabled': True}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = {'success': True, 'hot_reload': True, 'old_value': '1500'}

                result = await motionctl.apply_config_changes(1, old_config, new_config)

        assert 'threshold' in result['hot_reloaded']
        assert result['needs_restart'] is False

    @pytest.mark.asyncio
    async def test_mixed_changes(self):
        """Should handle mix of hot-reload and restart-required changes."""
        from motioneye import motionctl

        old_config = {'threshold': '1500', 'width': '1920'}
        new_config = {'threshold': '2000', 'width': '1280'}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = {'success': True, 'hot_reload': True, 'old_value': '1500'}

                result = await motionctl.apply_config_changes(1, old_config, new_config)

        assert 'threshold' in result['hot_reloaded']
        assert 'width' in result['restart_params']
        assert result['needs_restart'] is True

    @pytest.mark.asyncio
    async def test_ignores_internal_params(self):
        """Should ignore @ prefixed MotionEye internal parameters."""
        from motioneye import motionctl

        old_config = {'@enabled': True, '@motion_detection': False}
        new_config = {'@enabled': False, '@motion_detection': True}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                result = await motionctl.apply_config_changes(1, old_config, new_config)

        # Should not have tried to hot-reload any internal params
        mock_set.assert_not_called()
        assert result['hot_reloaded'] == []
        assert result['restart_params'] == []
        assert result['needs_restart'] is False

    @pytest.mark.asyncio
    async def test_no_changes(self):
        """Should handle case with no actual changes."""
        from motioneye import motionctl

        config = {'threshold': '1500', 'width': '1920'}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                result = await motionctl.apply_config_changes(1, config, config.copy())

        mock_set.assert_not_called()
        assert result['hot_reloaded'] == []
        assert result['restart_params'] == []
        assert result['needs_restart'] is False

    @pytest.mark.asyncio
    async def test_hot_reload_failure_triggers_restart(self):
        """Should add param to restart list if hot reload fails."""
        from motioneye import motionctl

        old_config = {'threshold': '1500'}
        new_config = {'threshold': '2000'}

        with patch.object(motionctl, 'is_motion_50', return_value=True):
            with patch.object(motionctl, 'set_config_hot', new_callable=AsyncMock) as mock_set:
                mock_set.return_value = {'success': False, 'hot_reload': False, 'error': 'Connection refused'}

                result = await motionctl.apply_config_changes(1, old_config, new_config)

        assert 'threshold' in result['restart_params']
        assert result['needs_restart'] is True
        assert len(result['errors']) > 0


class TestUIParamMapping:
    """Test UI to Motion parameter mapping."""

    def test_frame_change_threshold_maps_to_threshold(self):
        """frame_change_threshold UI param should map to threshold."""
        from motioneye.config.camera.converters import UI_TO_MOTION_PARAMS
        assert UI_TO_MOTION_PARAMS.get('frame_change_threshold') == 'threshold'

    def test_resolution_maps_to_multiple_params(self):
        """resolution UI param should map to width and height."""
        from motioneye.config.camera.converters import UI_TO_MOTION_PARAMS
        assert UI_TO_MOTION_PARAMS.get('resolution') == ['width', 'height']

    def test_ui_param_requires_restart_for_resolution(self):
        """Resolution changes should require restart."""
        from motioneye.config.camera.converters import ui_param_requires_restart
        assert ui_param_requires_restart('resolution') is True

    def test_ui_param_no_restart_for_threshold(self):
        """Threshold changes should not require restart."""
        from motioneye.config.camera.converters import ui_param_requires_restart
        assert ui_param_requires_restart('frame_change_threshold') is False

    def test_ui_param_requires_restart_for_unknown(self):
        """Unknown params should require restart for safety."""
        from motioneye.config.camera.converters import ui_param_requires_restart
        assert ui_param_requires_restart('unknown_param') is True
