"""Phase 107: KaTrainGui購読テスト（CI互換、スレッドセーフ版）

Note: KaTrainGuiはKivy Screenクラスのため、object.__new__()が使用不可。
MagicMockで代替し、必要な属性を手動設定してメソッドを直接呼び出す。

CI環境ではKivyインポートがクラッシュするため、スキップ。
"""

import concurrent.futures
import os
import threading
from unittest.mock import MagicMock, patch

import pytest


def _is_ci_environment():
    """CI環境を検出（CI変数が設定されていればTrue）"""
    ci_value = os.environ.get("CI", "")
    return ci_value != ""


# CI環境ではKaTrainGuiのインポートがクラッシュするためスキップ
pytestmark = pytest.mark.skipif(_is_ci_environment(), reason="KaTrainGui import crashes on headless CI")


class TestSetupStateSubscriptions:
    """購読登録テスト"""

    def test_subscribes_three_events(self):
        """3つのイベントが購読される"""
        from katrain.__main__ import KaTrainGui
        from katrain.core.state import EventType

        mock_notifier = MagicMock()

        gui = MagicMock()
        gui._state_subscriptions_setup = False
        gui._state_notifier = mock_notifier
        gui.state_notifier = mock_notifier
        gui._on_game_changed = MagicMock()
        gui._on_analysis_complete = MagicMock()
        gui._on_config_updated = MagicMock()

        KaTrainGui._setup_state_subscriptions(gui)

        assert mock_notifier.subscribe.call_count == 3
        event_types = [c[0][0] for c in mock_notifier.subscribe.call_args_list]
        assert EventType.GAME_CHANGED in event_types
        assert EventType.ANALYSIS_COMPLETE in event_types
        assert EventType.CONFIG_UPDATED in event_types

    def test_double_setup_is_noop(self):
        """二重登録は無視される"""
        from katrain.__main__ import KaTrainGui

        mock_notifier = MagicMock()

        gui = MagicMock()
        gui._state_subscriptions_setup = False
        gui._state_notifier = mock_notifier
        gui.state_notifier = mock_notifier
        gui._on_game_changed = MagicMock()
        gui._on_analysis_complete = MagicMock()
        gui._on_config_updated = MagicMock()

        KaTrainGui._setup_state_subscriptions(gui)
        KaTrainGui._setup_state_subscriptions(gui)

        assert mock_notifier.subscribe.call_count == 3

    def test_setup_sets_flag(self):
        """購読後にフラグがTrueになる"""
        from katrain.__main__ import KaTrainGui

        mock_notifier = MagicMock()

        gui = MagicMock()
        gui._state_subscriptions_setup = False
        gui.state_notifier = mock_notifier

        KaTrainGui._setup_state_subscriptions(gui)

        assert gui._state_subscriptions_setup is True


class TestScheduleUiUpdate:
    """Coalescingテスト（スレッドセーフ版）"""

    def test_single_call_schedules_once(self):
        """単一呼び出しで1回スケジュール"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = None
        gui._pending_redraw_board = False
        gui._do_ui_update = MagicMock()

        with patch("katrain.__main__.Clock.schedule_once") as mock_schedule:
            mock_event = MagicMock()
            mock_schedule.return_value = mock_event

            KaTrainGui._schedule_ui_update(gui, redraw_board=True)

            mock_schedule.assert_called_once()
            assert gui._pending_ui_update is mock_event
            assert gui._pending_redraw_board is True

    def test_multiple_calls_coalesce(self):
        """複数呼び出しが1回にcoalesce"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = None
        gui._pending_redraw_board = False
        gui._do_ui_update = MagicMock()

        with patch("katrain.__main__.Clock.schedule_once") as mock_schedule:
            mock_event = MagicMock()
            mock_schedule.return_value = mock_event

            # 1回目: スケジュール
            KaTrainGui._schedule_ui_update(gui, redraw_board=False)
            # 2回目: coalescingでスキップ
            KaTrainGui._schedule_ui_update(gui, redraw_board=True)

            assert mock_schedule.call_count == 1
            assert gui._pending_redraw_board is True

    def test_redraw_flag_accumulates_with_or(self):
        """redraw_boardフラグはORで蓄積"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()  # 既にスケジュール済み
        gui._pending_redraw_board = False

        with patch("katrain.__main__.Clock.schedule_once"):
            KaTrainGui._schedule_ui_update(gui, redraw_board=False)
            assert gui._pending_redraw_board is False

            KaTrainGui._schedule_ui_update(gui, redraw_board=True)
            assert gui._pending_redraw_board is True

            KaTrainGui._schedule_ui_update(gui, redraw_board=False)
            assert gui._pending_redraw_board is True


class TestEventHandlers:
    """イベントハンドラテスト"""

    def test_on_game_changed_schedules_with_redraw(self):
        """GAME_CHANGED → redraw_board=True"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._schedule_ui_update = MagicMock()

        KaTrainGui._on_game_changed(gui, MagicMock())

        gui._schedule_ui_update.assert_called_once_with(redraw_board=True)

    def test_on_analysis_complete_schedules_without_redraw(self):
        """ANALYSIS_COMPLETE → redraw_board=False"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._schedule_ui_update = MagicMock()

        KaTrainGui._on_analysis_complete(gui, MagicMock())

        gui._schedule_ui_update.assert_called_once_with(redraw_board=False)

    def test_on_config_updated_schedules_without_redraw(self):
        """CONFIG_UPDATED → redraw_board=False"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._schedule_ui_update = MagicMock()

        KaTrainGui._on_config_updated(gui, MagicMock())

        gui._schedule_ui_update.assert_called_once_with(redraw_board=False)


class TestDoUiUpdateCallback:
    """_do_ui_update()コールバックテスト"""

    def test_calls_update_gui_with_accumulated_flags(self):
        """update_gui()が蓄積されたフラグで呼ばれる"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()  # 非None（スケジュール済み状態）
        gui._pending_redraw_board = True
        gui.game = MagicMock()
        gui.game.current_node = MagicMock()
        gui.update_gui = MagicMock()
        gui.log = MagicMock()

        # _do_ui_updateを直接呼び出し
        KaTrainGui._do_ui_update(gui, 0)

        gui.update_gui.assert_called_once_with(gui.game.current_node, redraw_board=True)

    def test_skips_when_no_game(self):
        """game=Noneの場合はスキップ"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = False
        gui.game = None
        gui.update_gui = MagicMock()

        KaTrainGui._do_ui_update(gui, 0)

        gui.update_gui.assert_not_called()

    def test_skips_when_no_current_node(self):
        """current_node=Noneの場合はスキップ"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = False
        gui.game = MagicMock()
        gui.game.current_node = None
        gui.update_gui = MagicMock()

        KaTrainGui._do_ui_update(gui, 0)

        gui.update_gui.assert_not_called()

    def test_resets_flags_after_execution(self):
        """実行後にフラグがリセットされる"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = True
        gui.game = MagicMock()
        gui.game.current_node = MagicMock()
        gui.update_gui = MagicMock()
        gui.log = MagicMock()

        # 実行前の確認
        assert gui._pending_ui_update is not None

        KaTrainGui._do_ui_update(gui, 0)

        # フラグがリセットされている
        assert gui._pending_ui_update is None
        assert gui._pending_redraw_board is False

    def test_logs_exception_without_raising(self):
        """update_gui例外時はログ出力して継続"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = False
        gui.game = MagicMock()
        gui.game.current_node = MagicMock()
        gui.update_gui = MagicMock(side_effect=RuntimeError("test error"))
        gui.log = MagicMock()

        # 例外が発生してもraiseされない
        KaTrainGui._do_ui_update(gui, 0)  # Should not raise

        # ログが呼ばれている
        gui.log.assert_called_once()
        assert "update_gui failed" in gui.log.call_args[0][0]

    def test_redraw_false_passed_correctly(self):
        """redraw_board=Falseが正しく渡される"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = False  # redraw=False
        gui.game = MagicMock()
        gui.game.current_node = MagicMock()
        gui.update_gui = MagicMock()
        gui.log = MagicMock()

        KaTrainGui._do_ui_update(gui, 0)

        gui.update_gui.assert_called_once_with(gui.game.current_node, redraw_board=False)


class TestThreadSafety:
    """スレッドセーフ性テスト"""

    def test_concurrent_schedule_calls(self):
        """複数スレッドからの同時呼び出しでも1回のみスケジュール"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = None
        gui._pending_redraw_board = False
        gui._do_ui_update = MagicMock()

        schedule_call_count = 0
        schedule_lock = threading.Lock()

        with patch("katrain.__main__.Clock.schedule_once") as mock_schedule:

            def track_schedule(fn, delay):
                nonlocal schedule_call_count
                with schedule_lock:
                    schedule_call_count += 1
                return MagicMock()

            mock_schedule.side_effect = track_schedule

            # 10スレッドから同時に呼び出し
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(KaTrainGui._schedule_ui_update, gui, redraw_board=True) for _ in range(10)]
                concurrent.futures.wait(futures)

        # 1回のみスケジュールされる
        assert schedule_call_count == 1
        # redraw_boardは最終的にTrue
        assert gui._pending_redraw_board is True

    def test_flags_reset_atomically(self):
        """フラグリセットがアトミックに行われる"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = MagicMock()
        gui._pending_redraw_board = True
        gui.game = MagicMock()
        gui.game.current_node = MagicMock()
        gui.update_gui = MagicMock()
        gui.log = MagicMock()

        # _do_ui_update を呼ぶ
        KaTrainGui._do_ui_update(gui, 0)

        # フラグがアトミックにリセットされている
        with gui._ui_update_lock:
            assert gui._pending_ui_update is None
            assert gui._pending_redraw_board is False

    def test_schedule_default_redraw_false(self):
        """redraw_board引数省略時はFalse"""
        from katrain.__main__ import KaTrainGui

        gui = MagicMock()
        gui._ui_update_lock = threading.Lock()
        gui._pending_ui_update = None
        gui._pending_redraw_board = False
        gui._do_ui_update = MagicMock()

        with patch("katrain.__main__.Clock.schedule_once") as mock_schedule:
            mock_schedule.return_value = MagicMock()

            # 引数なしで呼び出し
            KaTrainGui._schedule_ui_update(gui)

            assert gui._pending_redraw_board is False
