"""Tests for QuizManager (Phase 98).

Test categories:
- TestQuizManagerImport: Kivy-free import/instantiation
- TestQuizManagerLazyImport: managers package lazy import
- TestQuizManagerActiveReviewIntegration: Active Review coordination
- TestQuizManagerFormatPointsLoss: Edge cases for format_points_loss
"""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestQuizManagerImport:
    """Kivy-free import and instantiation tests."""

    def test_import_does_not_require_kivy(self):
        """QuizManager import should not require Kivy."""
        # Record Kivy modules before import
        kivy_modules_before = {k for k in sys.modules if k.startswith("kivy")}

        from katrain.gui.managers.quiz_manager import QuizManager

        # Check no new Kivy modules were imported
        kivy_modules_after = {k for k in sys.modules if k.startswith("kivy")}
        new_kivy_modules = kivy_modules_after - kivy_modules_before
        assert not new_kivy_modules, f"Kivy modules imported: {new_kivy_modules}"
        assert QuizManager is not None

    def test_instantiation_without_kivy(self):
        """QuizManager instantiation should not require Kivy."""
        from katrain.gui.managers.quiz_manager import QuizManager

        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )
        assert manager is not None


class TestQuizManagerLazyImport:
    """Tests for managers package lazy import."""

    def test_managers_package_lazy_import(self):
        """Lazy import from managers package should work."""
        from katrain.gui.managers import QuizManager

        assert QuizManager is not None

    def test_managers_package_import_in_headless_context(self):
        """Import should work in headless/CI environment."""
        import os

        os.environ.setdefault("KIVY_NO_ARGS", "1")
        os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

        from katrain.gui.managers import QuizManager

        assert QuizManager is not None


class TestQuizManagerActiveReviewIntegration:
    """Tests for Active Review coordination."""

    def test_start_quiz_session_disables_active_review(self):
        """start_quiz_session() should call disable_if_needed()."""
        from katrain.gui.managers.quiz_manager import QuizManager

        mock_controller = MagicMock()
        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: mock_controller,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session"):
            manager.start_quiz_session([])

        mock_controller.disable_if_needed.assert_called_once()

    def test_start_quiz_session_continues_when_controller_is_none(self):
        """Quiz should continue when controller is None."""
        from katrain.gui.managers.quiz_manager import QuizManager

        log_calls = []
        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: log_calls.append((msg, lvl)),
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session") as mock_start:
            manager.start_quiz_session([])
            mock_start.assert_called_once()

        # Should log info message
        assert any("not available" in msg for msg, _ in log_calls)

    def test_start_quiz_session_continues_on_controller_exception(self):
        """Quiz should continue when controller raises exception."""
        from katrain.gui.managers.quiz_manager import QuizManager

        mock_controller = MagicMock()
        mock_controller.disable_if_needed.side_effect = RuntimeError("test error")

        log_calls = []
        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: mock_controller,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: log_calls.append((msg, lvl)),
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session") as mock_start:
            manager.start_quiz_session([])
            mock_start.assert_called_once()

        # Should log warning
        assert any("Warning" in msg or "Failed" in msg for msg, _ in log_calls)

    def test_disable_if_needed_is_idempotent(self):
        """disable_if_needed() should be safe to call multiple times."""
        from katrain.gui.managers.quiz_manager import QuizManager

        mock_controller = MagicMock()
        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: mock_controller,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        # Call twice
        with patch("katrain.gui.features.quiz_session.start_quiz_session"):
            manager.start_quiz_session([])
            manager.start_quiz_session([])

        # Should be called twice (idempotent doesn't mean "call once")
        assert mock_controller.disable_if_needed.call_count == 2


class TestQuizManagerFormatPointsLoss:
    """Tests for format_points_loss edge cases."""

    def _create_manager(self):
        """Helper to create QuizManager instance."""
        from katrain.gui.managers.quiz_manager import QuizManager

        return QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

    def test_format_points_loss_with_positive_value(self):
        """Positive value should be formatted."""
        manager = self._create_manager()
        result = manager.format_points_loss(3.5)
        # Locale-dependent: 3.5 or 3,5
        assert "3" in result
        assert isinstance(result, str)

    def test_format_points_loss_with_none(self):
        """None should return a valid string."""
        manager = self._create_manager()
        result = manager.format_points_loss(None)
        assert result is not None
        assert isinstance(result, str)

    def test_format_points_loss_with_zero(self):
        """Zero should be formatted."""
        manager = self._create_manager()
        result = manager.format_points_loss(0.0)
        assert "0" in result
        assert isinstance(result, str)

    def test_format_points_loss_with_negative_value(self):
        """Negative value should not crash (edge case)."""
        manager = self._create_manager()
        result = manager.format_points_loss(-1.5)
        assert isinstance(result, str)

    def test_format_points_loss_rounding(self):
        """Decimal values should be formatted."""
        manager = self._create_manager()
        result = manager.format_points_loss(2.567)
        assert isinstance(result, str)

    def test_format_points_loss_large_value(self):
        """Large value should be formatted."""
        manager = self._create_manager()
        result = manager.format_points_loss(99.9)
        assert isinstance(result, str)


class TestQuizManagerDoQuizPopup:
    """Tests for do_quiz_popup method."""

    def test_do_quiz_popup_calls_underlying_function(self):
        """do_quiz_popup should call quiz_popup.do_quiz_popup."""
        from katrain.gui.managers.quiz_manager import QuizManager

        mock_ctx = MagicMock()
        manager = QuizManager(
            get_ctx=lambda: mock_ctx,
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_popup.do_quiz_popup") as mock_popup:
            manager.do_quiz_popup()

            mock_popup.assert_called_once()
            # Verify ctx is passed
            call_args = mock_popup.call_args
            assert call_args[0][0] == mock_ctx

    def test_do_quiz_popup_passes_start_session_callback(self):
        """do_quiz_popup should pass start_quiz_session as callback."""
        from katrain.gui.managers.quiz_manager import QuizManager

        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_popup.do_quiz_popup") as mock_popup:
            manager.do_quiz_popup()

            # Second argument should be start_quiz_session
            call_args = mock_popup.call_args
            assert call_args[0][1] == manager.start_quiz_session


class TestQuizManagerStartQuizSession:
    """Tests for start_quiz_session method."""

    def test_start_quiz_session_passes_quiz_items(self):
        """start_quiz_session should pass quiz_items to underlying function."""
        from katrain.gui.managers.quiz_manager import QuizManager

        mock_ctx = MagicMock()
        mock_quiz_items = [MagicMock(), MagicMock()]
        manager = QuizManager(
            get_ctx=lambda: mock_ctx,
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session") as mock_session:
            manager.start_quiz_session(mock_quiz_items)

            mock_session.assert_called_once()
            call_args = mock_session.call_args
            assert call_args[0][0] == mock_ctx
            assert call_args[0][1] == mock_quiz_items

    def test_start_quiz_session_passes_format_points_loss(self):
        """start_quiz_session should pass format_points_loss as callback."""
        from katrain.gui.managers.quiz_manager import QuizManager

        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=lambda: None,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session") as mock_session:
            manager.start_quiz_session([])

            call_args = mock_session.call_args
            # Third argument should be format_points_loss
            assert call_args[0][2] == manager.format_points_loss

    def test_start_quiz_session_passes_update_state_fn(self):
        """start_quiz_session should pass update_state_fn as callback."""
        from katrain.gui.managers.quiz_manager import QuizManager

        update_fn = MagicMock()
        manager = QuizManager(
            get_ctx=lambda: MagicMock(),
            get_active_review_controller=lambda: None,
            update_state_fn=update_fn,
            logger=lambda msg, lvl=0: None,
        )

        with patch("katrain.gui.features.quiz_session.start_quiz_session") as mock_session:
            manager.start_quiz_session([])

            call_args = mock_session.call_args
            # Fourth argument should be update_state_fn
            assert call_args[0][3] == update_fn
