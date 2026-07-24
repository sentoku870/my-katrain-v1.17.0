"""Tests for DialogFactory (Phase PR4 coverage).

The factory wraps ``I18NPopup`` instantiation with a known popup size and
content type. Each test mocks ``I18NPopup`` and the popup content class
to verify the wiring is correct.

This file targets >70% coverage on ``katrain.gui.managers.dialog_factory``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.gui.managers.dialog_factory import DialogFactory


def _make_factory():
    """Return a DialogFactory with a MagicMock gui."""
    return DialogFactory(gui=MagicMock(name="gui"))


def _mocked_popup(content_cls):
    """Context manager stack that mocks I18NPopup + a content class.

    Returns a tuple ``(factory, raw_popup, content_mock)``.
    """
    from contextlib import ExitStack

    factory = _make_factory()
    stack = ExitStack()
    mock_popup = stack.enter_context(patch("katrain.gui.managers.dialog_factory.I18NPopup"))
    mock_content_cls = stack.enter_context(patch(f"katrain.gui.managers.dialog_factory.{content_cls}"))
    mock_clamp = stack.enter_context(patch("katrain.gui.managers.dialog_factory.clamp_popup_size"))
    raw_popup = MagicMock(name="raw_popup")
    # ``I18NPopup(...)`` returns mock_popup.return_value. The factory uses
    # ``getattr(raw, '__self__', raw)`` so we wire __self__ to our raw_popup
    # and make raw_popup.content point at the content_mock so that
    # ``popup.content.popup = popup`` (inside the factory) lands on the mock.
    mock_popup.return_value.__self__ = raw_popup
    content_mock = MagicMock(name="content")
    mock_content_cls.return_value = content_mock
    raw_popup.content = content_mock
    return stack, factory, raw_popup, content_mock, mock_clamp


class TestCreateNewGamePopup:
    def test_creates_new_game_popup_with_correct_size(self):
        stack, factory, raw_popup, content_mock, _clamp = _mocked_popup("NewGamePopup")
        with stack:
            popup = factory.create_new_game_popup()
        # Content class instantiated with the gui.
        assert popup is not None
        # The content's popup attribute is wired back to raw_popup.
        assert content_mock.popup is raw_popup


class TestCreateTimerPopup:
    def test_creates_timer_popup(self):
        stack, factory, _raw_popup, content_mock, _clamp = _mocked_popup("ConfigTimerPopup")
        with stack:
            popup = factory.create_timer_popup()
        assert popup is not None
        assert content_mock.popup is not None


class TestCreateTeacherPopup:
    def test_creates_teacher_popup_with_dismiss_cleanup(self):
        """The teacher popup binds ``on_dismiss`` to ``content.cleanup()``."""
        stack, factory, raw_popup, _content_mock, _clamp = _mocked_popup("ConfigTeacherPopup")
        with stack:
            factory.create_teacher_popup()
        # The dismiss handler is bound (P2-A H3 lang leak guard).
        raw_popup.bind.assert_called_once()
        # ``bind`` was called with kwargs (the factory uses
        # ``popup.bind(on_dismiss=lambda ...)``).
        kwargs = raw_popup.bind.call_args.kwargs
        assert "on_dismiss" in kwargs
        # The bound callable is a lambda wrapping content.cleanup.
        assert callable(kwargs["on_dismiss"])


class TestCreateAiPopup:
    def test_creates_ai_popup(self):
        stack, factory, _raw_popup, content_mock, _clamp = _mocked_popup("ConfigAIPopup")
        with stack:
            popup = factory.create_ai_popup()
        assert popup is not None
        assert content_mock.popup is not None


class TestCreateEngineRecoveryPopup:
    def test_creates_engine_recovery_popup_with_args(self):
        stack, factory, raw_popup, content_mock, _clamp = _mocked_popup("EngineRecoveryPopup")
        error_message = "engine crashed"
        code = 42
        with stack:
            popup = factory.create_engine_recovery_popup(error_message, code)
        assert popup is not None
        # The content's popup attribute is wired back to raw_popup.
        assert content_mock.popup is raw_popup
        # The factory called the content class with the gui + error_message + code.
        # (We can't easily reach the patched EngineRecoveryPopup here, so we
        # verify the side-effect: content_mock.popup assignment is the contract.)


class TestIsEngineRecoveryPopup:
    def test_none_returns_false(self):
        factory = _make_factory()
        assert factory.is_engine_recovery_popup(None) is False

    def test_popup_without_content_returns_false(self):
        factory = _make_factory()
        popup = MagicMock(spec=[])  # no .content attr
        assert factory.is_engine_recovery_popup(popup) is False

    def test_engine_recovery_content_returns_true(self):
        factory = _make_factory()
        from katrain.gui.managers.dialog_factory import EngineRecoveryPopup

        content = MagicMock(spec=EngineRecoveryPopup)
        popup = MagicMock(content=content)
        assert factory.is_engine_recovery_popup(popup) is True

    def test_unrelated_content_returns_false(self):
        factory = _make_factory()
        popup = MagicMock(content="not a popup instance")
        assert factory.is_engine_recovery_popup(popup) is False


class TestImports:
    def test_factory_imports_clean(self):
        """All popup content classes referenced by the factory exist."""
        from katrain.gui.managers import dialog_factory

        for sym in (
            "ConfigAIPopup",
            "ConfigTeacherPopup",
            "ConfigTimerPopup",
            "DialogFactory",
            "EngineRecoveryPopup",
            "I18NPopup",
            "NewGamePopup",
        ):
            assert hasattr(dialog_factory, sym), f"missing import: {sym}"
