"""Phase 106A: ControlsPanel購読テスト

全テストはKivy依存。CI環境ではスキップ、ローカルでのみ実行。
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.state import Event, EventType, StateNotifier


def _is_ci_environment():
    """CI環境を検出（CI変数が設定されていればTrue）"""
    ci_value = os.environ.get("CI", "")
    return ci_value != ""


class ControlsPanelDummy:
    """ControlsPanelのテスト用Dummy（bound method再現用）"""

    def __init__(self):
        self._subscribed_notifier = None
        self._analysis_callback = None
        self.graph = MagicMock()
        self.katrain = None

    def _on_analysis_complete(self, event):
        pass


class TestControlsPanelSubscription:
    """購読登録テスト（4テスト）"""

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_on_katrain_calls_subscribe(self):
        """on_katrain()でsubscribe()が呼ばれる"""
        notifier = StateNotifier()
        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        with patch.object(notifier, "subscribe", wraps=notifier.subscribe) as spy_sub:
            from katrain.gui.controlspanel import ControlsPanel

            dummy = ControlsPanelDummy()
            ControlsPanel.on_katrain(dummy, None, mock_katrain)

            spy_sub.assert_called_once()
            call_args = spy_sub.call_args
            assert call_args[0][0] == EventType.ANALYSIS_COMPLETE
            assert call_args[0][1] == dummy._analysis_callback

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_on_katrain_stores_notifier_reference(self):
        """on_katrain()後にnotifier参照が保存される"""
        notifier = StateNotifier()
        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        ControlsPanel.on_katrain(dummy, None, mock_katrain)

        assert dummy._subscribed_notifier is notifier
        assert dummy._analysis_callback is not None

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_katrain_replacement_unsubscribes_old(self):
        """katrainが変更されると旧notifierからunsubscribeされる"""
        old_notifier = StateNotifier()
        new_notifier = StateNotifier()
        old_katrain = MagicMock()
        old_katrain.state_notifier = old_notifier
        new_katrain = MagicMock()
        new_katrain.state_notifier = new_notifier

        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        ControlsPanel.on_katrain(dummy, None, old_katrain)
        old_callback = dummy._analysis_callback

        with patch.object(old_notifier, "unsubscribe", wraps=old_notifier.unsubscribe) as spy_unsub:
            ControlsPanel.on_katrain(dummy, None, new_katrain)
            spy_unsub.assert_called_once_with(EventType.ANALYSIS_COMPLETE, old_callback)

        assert dummy._subscribed_notifier is new_notifier

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_katrain_none_only_unsubscribes(self):
        """katrain=Noneの場合、unsubscribeのみ実行"""
        notifier = StateNotifier()
        mock_katrain = MagicMock()
        mock_katrain.state_notifier = notifier

        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        ControlsPanel.on_katrain(dummy, None, mock_katrain)

        with patch.object(notifier, "unsubscribe", wraps=notifier.unsubscribe) as spy_unsub:
            with patch.object(notifier, "subscribe") as mock_sub:
                ControlsPanel.on_katrain(dummy, None, None)
                spy_unsub.assert_called_once()
                mock_sub.assert_not_called()

        assert dummy._subscribed_notifier is None


class TestAnalysisCompleteCallback:
    """コールバックテスト（5テスト）"""

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_callback_schedules_on_main_thread(self):
        """コールバックがClock.schedule_onceを使用"""
        with patch("katrain.gui.controlspanel.Clock") as mock_clock:
            from katrain.gui.controlspanel import ControlsPanel

            dummy = ControlsPanelDummy()
            event = Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": "Q1"})

            ControlsPanel._on_analysis_complete(dummy, event)

            mock_clock.schedule_once.assert_called_once()

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_callback_calls_update_value(self):
        """コールバックがgraph.update_value(current_node)を呼ぶ"""
        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        mock_graph = MagicMock()
        mock_game = MagicMock()
        mock_node = MagicMock()
        mock_game.current_node = mock_node
        mock_katrain = MagicMock()
        mock_katrain.game = mock_game

        dummy.graph = mock_graph
        dummy.katrain = mock_katrain

        with patch("katrain.gui.controlspanel.Clock") as mock_clock:

            def execute_scheduled(fn, delay):
                fn(0)

            mock_clock.schedule_once.side_effect = execute_scheduled

            event = Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": "Q1"})
            ControlsPanel._on_analysis_complete(dummy, event)

            mock_graph.update_value.assert_called_once_with(mock_node)

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_callback_safe_when_graph_missing(self):
        """graphがNoneでもエラーなし"""
        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        dummy.graph = None

        with patch("katrain.gui.controlspanel.Clock") as mock_clock:

            def execute_scheduled(fn, delay):
                fn(0)

            mock_clock.schedule_once.side_effect = execute_scheduled

            event = Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": "Q1"})
            ControlsPanel._on_analysis_complete(dummy, event)

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_callback_safe_when_game_missing(self):
        """gameがNoneでもエラーなし"""
        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        dummy.katrain = MagicMock()
        dummy.katrain.game = None

        with patch("katrain.gui.controlspanel.Clock") as mock_clock:

            def execute_scheduled(fn, delay):
                fn(0)

            mock_clock.schedule_once.side_effect = execute_scheduled

            event = Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": "Q1"})
            ControlsPanel._on_analysis_complete(dummy, event)

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_callback_safe_when_current_node_missing(self):
        """current_nodeがNoneでもエラーなし"""
        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        mock_game = MagicMock()
        mock_game.current_node = None
        dummy.katrain = MagicMock()
        dummy.katrain.game = mock_game

        with patch("katrain.gui.controlspanel.Clock") as mock_clock:

            def execute_scheduled(fn, delay):
                fn(0)

            mock_clock.schedule_once.side_effect = execute_scheduled

            event = Event.create(EventType.ANALYSIS_COMPLETE, {"query_id": "Q1"})
            ControlsPanel._on_analysis_complete(dummy, event)


class TestSubscriptionEdgeCases:
    """エッジケーステスト（2テスト）"""

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_multiple_katrain_changes(self):
        """katrainが複数回変更されても正しく動作"""
        notifiers = [StateNotifier() for _ in range(3)]
        katrains = [MagicMock() for _ in range(3)]
        for k, n in zip(katrains, notifiers, strict=False):
            k.state_notifier = n

        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        for katrain in katrains:
            ControlsPanel.on_katrain(dummy, None, katrain)

        assert dummy._subscribed_notifier is notifiers[-1]

    @pytest.mark.skipif(_is_ci_environment(), reason="Kivy required, skipped on CI")
    def test_initial_state_handles_none(self):
        """初期状態でkatrain=None設定してもエラーなし"""
        from katrain.gui.controlspanel import ControlsPanel

        dummy = ControlsPanelDummy()
        ControlsPanel.on_katrain(dummy, None, None)

        assert dummy._subscribed_notifier is None
