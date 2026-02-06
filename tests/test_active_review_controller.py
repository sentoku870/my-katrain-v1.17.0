"""ActiveReviewControllerのユニットテスト（Phase 97）

全テストがKivy不要で実行可能（UIコールバック注入による）。
"""

import pytest
from typing import Any
from unittest.mock import MagicMock


def make_stub_show_feedback() -> tuple[Any, list]:
    """スタブのshow_feedback_fnを作成（呼び出し記録付き）"""
    calls: list[tuple] = []

    def stub(ctx, evaluation, allow_retry, on_retry, on_hint_request):
        calls.append((ctx, evaluation, allow_retry, on_retry, on_hint_request))

    return stub, calls


def make_stub_show_summary() -> tuple[Any, list]:
    """スタブのshow_summary_fnを作成（呼び出し記録付き）"""
    calls: list[tuple] = []

    def stub(ctx, summary):
        calls.append((ctx, summary))

    return stub, calls


class TestActiveReviewControllerImport:
    """Kivy不要でのインポート・インスタンス化テスト"""

    def test_import_does_not_require_kivy(self):
        """ActiveReviewControllerのインポートがKivyを必要としない"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        assert ActiveReviewController is not None

    def test_managers_package_lazy_import(self):
        """managersパッケージからの遅延インポートが機能する"""
        from katrain.gui.managers import ActiveReviewController

        assert ActiveReviewController is not None

    def test_instantiation_without_kivy(self):
        """モックでインスタンス化が可能（UIコールバック注入）"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: False,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        assert controller is not None
        assert controller.session is None


class TestSessionLifecycle:
    """セッション生成・破棄のテスト"""

    def test_session_created_on_mode_change_true(self):
        """on_mode_change(True)でセッションが作成される"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: True,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        assert controller.session is None
        controller.on_mode_change(True)
        assert controller.session is not None

    def test_on_mode_change_true_is_idempotent(self):
        """on_mode_change(True)が冪等（既存セッションを上書きしない）"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: True,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # First call creates session
        controller.on_mode_change(True)
        first_session = controller.session
        assert first_session is not None

        # Add some state to session
        first_session.begin_position(10)

        # Second call should NOT recreate session
        controller.on_mode_change(True)
        assert controller.session is first_session  # Same object
        assert controller.session.has_pending  # State preserved

    def test_session_cleared_on_mode_change_false(self):
        """on_mode_change(False)でセッションがクリアされる（サマリなし）"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, summary_calls = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: False,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # Create session via on_mode_change(True)
        controller.on_mode_change(True)
        assert controller.session is not None

        controller.on_mode_change(False)

        assert controller.session is None
        assert summary_calls == []  # サマリは表示されない

    def test_session_cleared_on_disable(self):
        """disable_if_needed()でセッションがクリアされる"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, summary_calls = make_stub_show_summary()

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # Create session via on_mode_change(True)
        controller.on_mode_change(True)
        assert controller.session is not None

        controller.disable_if_needed()

        assert controller.session is None
        assert mode_state["value"] is False
        assert summary_calls == []  # disable ではサマリ表示しない

    def test_session_property_is_readonly(self):
        """sessionプロパティが読み取り専用として機能する"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: False,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        with pytest.raises(AttributeError):
            controller.session = MagicMock()


class TestToggleDisableParity:
    """toggle/disable動作の振る舞いパリティテスト"""

    def test_is_fog_active_reflects_mode_getter(self):
        """is_fog_active()がget_mode()を反映する"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mode_state = {"value": False}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        assert controller.is_fog_active() is False
        mode_state["value"] = True
        assert controller.is_fog_active() is True

    def test_toggle_from_off_sets_mode_true(self):
        """OFF状態でtoggle()がmode=Trueを設定する"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mode_state = {"value": False}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        controller.toggle()
        assert mode_state["value"] is True

    def test_toggle_from_on_shows_summary_if_results_exist(self):
        """ON状態でtoggle()がサマリを表示しmode=Falseを設定する（結果あり）"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, summary_calls = make_stub_show_summary()

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # Create session via on_mode_change(True) and add result
        controller.on_mode_change(True)
        controller.session.results.append(MagicMock())  # Add result via public API

        controller.toggle()

        assert mode_state["value"] is False
        assert len(summary_calls) == 1  # サマリが表示された

    def test_toggle_from_on_no_summary_if_no_results(self):
        """ON状態でtoggle()が結果なしならサマリを表示しない"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, summary_calls = make_stub_show_summary()

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # Create session via on_mode_change(True) but NO results
        controller.on_mode_change(True)
        # No results added

        controller.toggle()

        assert mode_state["value"] is False
        assert len(summary_calls) == 0  # サマリは表示されない

    def test_disable_if_needed_noop_when_already_off(self):
        """OFF状態でdisable_if_needed()が何もしない"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, _ = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        set_mode_calls = []
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,
            get_controls=lambda: None,
            get_mode=lambda: False,
            set_mode=lambda v: set_mode_calls.append(v),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        controller.disable_if_needed()
        assert set_mode_calls == []  # set_modeは呼ばれない


class TestHandleGuess:
    """handle_guess()のテスト（Kivy不要 - UIコールバック注入 + monkeypatch）"""

    def test_handle_guess_returns_early_if_no_game(self):
        """handle_guess()がgame=Noneなら早期returnする"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: None,  # No game
            get_controls=lambda: None,
            get_mode=lambda: True,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        controller.handle_guess((3, 3))
        assert feedback_calls == []  # No feedback called

    def test_handle_guess_calls_feedback_on_ready_node(self, monkeypatch):
        """handle_guess()が準備完了ノードでshow_feedback_fnを呼ぶ"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController
        from katrain.core.study.active_review import ReviewReadyResult, GuessGrade
        import katrain.core.study.active_review as ar_module

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        # Mock node with analysis
        mock_node = MagicMock()
        mock_node.move_number = 10
        mock_node.analysis = {"moves": [{"move": "D4", "visits": 100, "order": 0}]}

        mock_game = MagicMock()
        mock_game.current_node = mock_node

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: mock_game,
            get_controls=lambda: MagicMock(),
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )
        controller.on_mode_change(True)  # Create session via public API

        # Monkeypatch is_review_ready to return ready
        monkeypatch.setattr(ar_module, "is_review_ready", lambda node: ReviewReadyResult(ready=True))

        # Monkeypatch ActiveReviewer
        mock_evaluation = MagicMock()
        mock_evaluation.grade = GuessGrade.PERFECT

        class MockReviewer:
            def __init__(self, preset):
                pass

            def evaluate_guess(self, coords, node):
                return mock_evaluation

        monkeypatch.setattr(ar_module, "ActiveReviewer", MockReviewer)

        controller.handle_guess((3, 3))

        assert len(feedback_calls) == 1
        assert feedback_calls[0][1] == mock_evaluation  # evaluation
        assert feedback_calls[0][2] is False  # allow_retry (PERFECT = no retry)

    def test_handle_guess_no_feedback_when_not_ready(self, monkeypatch):
        """handle_guess()が準備未完了ノードでfeedbackを呼ばない"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController
        from katrain.core.study.active_review import ReviewReadyResult
        import katrain.core.study.active_review as ar_module

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mock_node = MagicMock()
        mock_node.move_number = 10

        mock_game = MagicMock()
        mock_game.current_node = mock_node

        mock_controls = MagicMock()

        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: default,
            get_game=lambda: mock_game,
            get_controls=lambda: mock_controls,
            get_mode=lambda: True,
            set_mode=lambda v: None,
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )

        # Monkeypatch is_review_ready to return not ready
        monkeypatch.setattr(
            ar_module,
            "is_review_ready",
            lambda node: ReviewReadyResult(ready=False, message_key="active_review:not_analyzed"),
        )

        controller.handle_guess((3, 3))

        assert feedback_calls == []  # Feedbackは呼ばれない
        mock_controls.set_status.assert_called()  # ステータス表示

    def test_handle_guess_allows_retry_on_blunder(self, monkeypatch):
        """handle_guess()がBLUNDERでリトライを許可する"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController
        from katrain.core.study.active_review import ReviewReadyResult, GuessGrade
        import katrain.core.study.active_review as ar_module

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mock_node = MagicMock()
        mock_node.move_number = 10

        mock_game = MagicMock()
        mock_game.current_node = mock_node

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: mock_game,
            get_controls=lambda: MagicMock(),
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )
        controller.on_mode_change(True)  # Create session via public API

        monkeypatch.setattr(ar_module, "is_review_ready", lambda node: ReviewReadyResult(ready=True))

        mock_evaluation = MagicMock()
        mock_evaluation.grade = GuessGrade.BLUNDER  # Bad grade

        class MockReviewer:
            def __init__(self, preset):
                pass

            def evaluate_guess(self, coords, node):
                return mock_evaluation

        monkeypatch.setattr(ar_module, "ActiveReviewer", MockReviewer)

        controller.handle_guess((3, 3))

        assert len(feedback_calls) == 1
        assert feedback_calls[0][2] is True  # allow_retry
        assert feedback_calls[0][3] is not None  # on_retry callback
        assert feedback_calls[0][4] is not None  # on_hint_request callback

    def test_handle_guess_no_retry_on_second_attempt(self, monkeypatch):
        """handle_guess()が2回目のBLUNDERではリトライを許可しない"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController
        from katrain.core.study.active_review import ReviewReadyResult, GuessGrade
        import katrain.core.study.active_review as ar_module

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mock_node = MagicMock()
        mock_node.move_number = 10

        mock_game = MagicMock()
        mock_game.current_node = mock_node

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: mock_game,
            get_controls=lambda: MagicMock(),
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )
        controller.on_mode_change(True)  # Create session via public API

        monkeypatch.setattr(ar_module, "is_review_ready", lambda node: ReviewReadyResult(ready=True))

        mock_evaluation = MagicMock()
        mock_evaluation.grade = GuessGrade.BLUNDER

        class MockReviewer:
            def __init__(self, preset):
                pass

            def evaluate_guess(self, coords, node):
                return mock_evaluation

        monkeypatch.setattr(ar_module, "ActiveReviewer", MockReviewer)

        # First guess - allows retry
        controller.handle_guess((3, 3))
        assert feedback_calls[0][2] is True  # allow_retry

        # Simulate retry click (mark_retry called)
        controller.session.mark_retry()

        # Second guess - no retry
        controller.handle_guess((4, 4))
        assert len(feedback_calls) == 2
        assert feedback_calls[1][2] is False  # allow_retry = False on second attempt


class TestHandleGuessNodeChange:
    """handle_guess()でのノード変更検出テスト"""

    def test_handle_guess_aborts_pending_on_node_change(self, monkeypatch):
        """handle_guess()がノード変更時にpendingをabortする"""
        from katrain.gui.managers.active_review_controller import ActiveReviewController
        from katrain.core.study.active_review import ReviewReadyResult, GuessGrade
        import katrain.core.study.active_review as ar_module

        stub_feedback, feedback_calls = make_stub_show_feedback()
        stub_summary, _ = make_stub_show_summary()

        mock_node_10 = MagicMock()
        mock_node_10.move_number = 10

        mock_node_20 = MagicMock()
        mock_node_20.move_number = 20

        current_node = [mock_node_10]  # Use list for mutable closure

        mock_game = MagicMock()
        mock_game.current_node = property(lambda self: current_node[0])
        type(mock_game).current_node = property(lambda self: current_node[0])

        mode_state = {"value": True}
        controller = ActiveReviewController(
            get_ctx=lambda: MagicMock(),
            get_config=lambda setting, default=None: "standard" if "skill" in setting else default,
            get_game=lambda: mock_game,
            get_controls=lambda: MagicMock(),
            get_mode=lambda: mode_state["value"],
            set_mode=lambda v: mode_state.update({"value": v}),
            logger=lambda msg, level=0: None,
            show_feedback_fn=stub_feedback,
            show_summary_fn=stub_summary,
        )
        controller.on_mode_change(True)  # Create session

        monkeypatch.setattr(ar_module, "is_review_ready", lambda node: ReviewReadyResult(ready=True))

        mock_evaluation = MagicMock()
        mock_evaluation.grade = GuessGrade.BLUNDER

        class MockReviewer:
            def __init__(self, preset):
                pass

            def evaluate_guess(self, coords, node):
                return mock_evaluation

        monkeypatch.setattr(ar_module, "ActiveReviewer", MockReviewer)

        # First guess on node 10
        controller.handle_guess((3, 3))
        assert controller.session.has_pending is True  # After retry allowed

        # Simulate retry click
        controller.session.mark_retry()
        assert controller.session.has_pending is True
        assert controller.session._pending_move_number == 10

        # Change to different node before second guess
        current_node[0] = mock_node_20

        # Second guess on different node - should abort pending
        controller.handle_guess((4, 4))

        # Pending should have been aborted and new position started
        # The session should now have pending for node 20, not 10
        assert controller.session._pending_move_number == 20
