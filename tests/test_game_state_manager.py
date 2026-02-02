"""GameStateManagerのユニットテスト（Phase 76）

Kivy完全非依存:
- GameStateManagerのみをインスタンス化
- 全依存はモック/スタブで注入
"""

import pytest

from katrain.gui.managers.game_state_manager import GameStateManager


class MockNode:
    """GameNodeのモック"""

    def __init__(self, player: str = "B"):
        self.player = player
        self.note: str | None = None
        self.end_state: str | None = None


class MockGame:
    """Gameのモック"""

    def __init__(self):
        self.undo_calls: list[int] = []
        self.redo_calls: list[int] = []
        self.jump_prev_count = 0
        self.jump_next_count = 0
        self.reset_analysis_count = 0
        self.insert_mode_calls: list[str] = []
        self.current_node: MockNode | None = MockNode()

    def undo(self, n_times: int = 1) -> None:
        self.undo_calls.append(n_times)

    def redo(self, n_times: int = 1) -> None:
        self.redo_calls.append(n_times)

    def jump_to_prev_important_move(self) -> None:
        self.jump_prev_count += 1

    def jump_to_next_important_move(self) -> None:
        self.jump_next_count += 1

    def reset_current_analysis(self) -> None:
        self.reset_analysis_count += 1

    def set_insert_mode(self, mode: str) -> None:
        self.insert_mode_calls.append(mode)


@pytest.fixture
def mock_game() -> MockGame:
    return MockGame()


def create_manager(
    game: MockGame | None = None,
    play_analyze_mode: str = "analyze",
    mode_analyze: str = "analyze",
    clear_calls: list[bool] | None = None,
    switch_calls: list[bool] | None = None,
) -> GameStateManager:
    """テスト用GameStateManagerファクトリ"""
    if clear_calls is None:
        clear_calls = []
    if switch_calls is None:
        switch_calls = []

    return GameStateManager(
        get_game=lambda: game,
        get_play_analyze_mode=lambda: play_analyze_mode,
        mode_analyze=mode_analyze,
        switch_ui_mode=lambda: switch_calls.append(True),
        clear_animating_pv=lambda: clear_calls.append(True),
    )


class TestUndoRedo:
    """Undo/Redoテスト"""

    def test_do_undo_clears_animating_pv_and_delegates(self, mock_game: MockGame) -> None:
        """do_undoがanimating_pvをクリアしてgame.undoに委譲"""
        clear_calls: list[bool] = []
        manager = create_manager(game=mock_game, clear_calls=clear_calls)

        manager.do_undo(3)

        assert len(clear_calls) == 1, "clear_animating_pv must be called"
        assert mock_game.undo_calls == [3], "game.undo must be called with n_times"

    def test_do_undo_with_none_game_does_not_crash(self) -> None:
        """game=Noneでもクラッシュせず、clear_animating_pvは呼ばれる"""
        clear_calls: list[bool] = []
        manager = create_manager(game=None, clear_calls=clear_calls)

        manager.do_undo(1)  # Should not raise

        assert len(clear_calls) == 1, "clear_animating_pv still called even with None game"

    def test_do_redo_clears_animating_pv_and_delegates(self, mock_game: MockGame) -> None:
        """do_redoがanimating_pvをクリアしてgame.redoに委譲"""
        clear_calls: list[bool] = []
        manager = create_manager(game=mock_game, clear_calls=clear_calls)

        manager.do_redo(5)

        assert len(clear_calls) == 1
        assert mock_game.redo_calls == [5]


class TestImportantNavigation:
    """重要局面ナビゲーションテスト"""

    def test_do_prev_important_delegates(self, mock_game: MockGame) -> None:
        """do_prev_importantがgame.jump_to_prev_important_moveに委譲"""
        manager = create_manager(game=mock_game)

        manager.do_prev_important()

        assert mock_game.jump_prev_count == 1

    def test_do_next_important_delegates(self, mock_game: MockGame) -> None:
        """do_next_importantがgame.jump_to_next_important_moveに委譲"""
        manager = create_manager(game=mock_game)

        manager.do_next_important()

        assert mock_game.jump_next_count == 1


class TestResetAnalysis:
    """解析リセットテスト"""

    def test_do_reset_analysis_delegates(self, mock_game: MockGame) -> None:
        """do_reset_analysisがgame.reset_current_analysisに委譲"""
        manager = create_manager(game=mock_game)

        manager.do_reset_analysis()

        assert mock_game.reset_analysis_count == 1


class TestResign:
    """投了テスト

    投了ロジックの仕様（コード読み取りで確認済み）:
    - current_node.player = 概念上の「最後の着手者」= next_playerの対戦相手
    - 投了する側 = next_player（手番プレイヤー）
    - 勝者 = current_node.player
    - end_state = "{winner}+R"
    """

    def test_do_resign_sets_winner_when_black_moved_last(self, mock_game: MockGame) -> None:
        """黒が最後に着手 → 白が投了 → B+R（黒勝ち）"""
        assert mock_game.current_node is not None
        mock_game.current_node.player = "B"
        manager = create_manager(game=mock_game)

        manager.do_resign()

        assert mock_game.current_node.end_state == "B+R"

    def test_do_resign_sets_winner_when_white_moved_last(self, mock_game: MockGame) -> None:
        """白が最後に着手 → 黒が投了 → W+R（白勝ち）"""
        assert mock_game.current_node is not None
        mock_game.current_node.player = "W"
        manager = create_manager(game=mock_game)

        manager.do_resign()

        assert mock_game.current_node.end_state == "W+R"

    def test_do_resign_at_root_standard_game(self, mock_game: MockGame) -> None:
        """ルートノード（通常対局）: player="W", next_player="B" → 黒投了 → W+R

        KaTrainの仕様:
        - ルートでplayer="W"は「概念上、白が最後に打った」を意味
        - next_player="B"（黒が先手）
        - 黒が投了すると白勝ち: end_state="W+R"
        """
        assert mock_game.current_node is not None
        mock_game.current_node.player = "W"  # ルートノードの標準値
        manager = create_manager(game=mock_game)

        manager.do_resign()

        assert mock_game.current_node.end_state == "W+R"

    def test_do_resign_at_root_handicap_game(self, mock_game: MockGame) -> None:
        """ルートノード（置き碁）: player="B", next_player="W" → 白投了 → B+R

        KaTrainの仕様:
        - 置き碁ではplayer="B"（黒の置き石あり）
        - next_player="W"（白が先手）
        - 白が投了すると黒勝ち: end_state="B+R"
        """
        assert mock_game.current_node is not None
        mock_game.current_node.player = "B"  # 置き碁ルートの値
        manager = create_manager(game=mock_game)

        manager.do_resign()

        assert mock_game.current_node.end_state == "B+R"

    def test_do_resign_uses_current_node_player_as_winner(self, mock_game: MockGame) -> None:
        """current_node.playerが勝者として使用されることを確認（反転検出テスト）"""
        assert mock_game.current_node is not None
        mock_game.current_node.player = "B"
        manager = create_manager(game=mock_game)

        manager.do_resign()

        # 検証: end_stateがcurrent_node.playerで始まる
        # もしnext_player（投了側）を使っていたらこのテストは失敗する
        assert mock_game.current_node.end_state is not None
        assert mock_game.current_node.end_state.startswith(mock_game.current_node.player)
        assert mock_game.current_node.end_state == "B+R"  # 明示的な値チェック


class TestSetNote:
    """ノート設定テスト"""

    def test_set_note_updates_current_node(self, mock_game: MockGame) -> None:
        """set_noteがcurrent_node.noteを更新"""
        manager = create_manager(game=mock_game)

        manager.set_note("This is a test note")

        assert mock_game.current_node is not None
        assert mock_game.current_node.note == "This is a test note"

    def test_set_note_overwrites_existing_note(self, mock_game: MockGame) -> None:
        """既存のノートを上書き"""
        assert mock_game.current_node is not None
        mock_game.current_node.note = "Old note"
        manager = create_manager(game=mock_game)

        manager.set_note("New note")

        assert mock_game.current_node.note == "New note"


class TestInsertMode:
    """挿入モードテスト"""

    def test_do_insert_mode_delegates_to_game(self, mock_game: MockGame) -> None:
        """do_insert_modeがgame.set_insert_modeに委譲"""
        manager = create_manager(game=mock_game, play_analyze_mode="analyze")

        manager.do_insert_mode("toggle")

        assert mock_game.insert_mode_calls == ["toggle"]

    def test_do_insert_mode_switches_ui_when_not_analyze(self, mock_game: MockGame) -> None:
        """MODE_ANALYZE以外ではswitch_ui_modeが呼ばれる"""
        switch_calls: list[bool] = []
        manager = create_manager(
            game=mock_game,
            play_analyze_mode="play",
            mode_analyze="analyze",
            switch_calls=switch_calls,
        )

        manager.do_insert_mode("toggle")

        assert len(switch_calls) == 1, "switch_ui_mode must be called"

    def test_do_insert_mode_no_switch_when_analyze(self, mock_game: MockGame) -> None:
        """MODE_ANALYZEではswitch_ui_modeは呼ばれない"""
        switch_calls: list[bool] = []
        manager = create_manager(
            game=mock_game,
            play_analyze_mode="analyze",
            mode_analyze="analyze",
            switch_calls=switch_calls,
        )

        manager.do_insert_mode("toggle")

        assert len(switch_calls) == 0, "switch_ui_mode must not be called"

    def test_do_insert_mode_no_switch_when_game_none(self) -> None:
        """game=Noneではswitch_ui_modeは呼ばれない（ゲーム操作がスキップされるため）"""
        switch_calls: list[bool] = []
        manager = create_manager(
            game=None,
            play_analyze_mode="play",
            mode_analyze="analyze",
            switch_calls=switch_calls,
        )

        manager.do_insert_mode("toggle")

        assert len(switch_calls) == 0, "switch_ui_mode must not be called when game=None"


class TestNullSafety:
    """Null安全性テスト（game=Noneで全メソッド安全）"""

    def test_all_methods_safe_with_none_game(self) -> None:
        """全メソッドがgame=Noneでクラッシュしない"""
        manager = create_manager(game=None)

        # All should complete without raising
        manager.do_undo(1)
        manager.do_redo(1)
        manager.do_prev_important()
        manager.do_next_important()
        manager.do_reset_analysis()
        manager.do_resign()
        manager.set_note("test")
        manager.do_insert_mode("toggle")

    def test_resign_safe_with_none_current_node(self) -> None:
        """current_node=Noneでdo_resignが安全"""
        mock_game = MockGame()
        mock_game.current_node = None
        manager = create_manager(game=mock_game)

        manager.do_resign()  # Should not raise

    def test_set_note_safe_with_none_current_node(self) -> None:
        """current_node=Noneでset_noteが安全"""
        mock_game = MockGame()
        mock_game.current_node = None
        manager = create_manager(game=mock_game)

        manager.set_note("test")  # Should not raise


class TestCallbackInvocation:
    """コールバック呼び出しテスト"""

    def test_clear_animating_pv_called_before_undo(self, mock_game: MockGame) -> None:
        """clear_animating_pvがundo前に呼ばれる"""
        call_order: list[str] = []

        def track_clear() -> None:
            call_order.append("clear")

        original_undo = mock_game.undo

        def track_undo(n: int = 1) -> None:
            call_order.append("undo")
            original_undo(n)

        mock_game.undo = track_undo

        manager = GameStateManager(
            get_game=lambda: mock_game,
            get_play_analyze_mode=lambda: "analyze",
            mode_analyze="analyze",
            switch_ui_mode=lambda: None,
            clear_animating_pv=track_clear,
        )

        manager.do_undo(1)

        assert call_order == ["clear", "undo"], "clear must be called before undo"

    def test_clear_animating_pv_called_before_redo(self, mock_game: MockGame) -> None:
        """clear_animating_pvがredo前に呼ばれる"""
        call_order: list[str] = []

        def track_clear() -> None:
            call_order.append("clear")

        original_redo = mock_game.redo

        def track_redo(n: int = 1) -> None:
            call_order.append("redo")
            original_redo(n)

        mock_game.redo = track_redo

        manager = GameStateManager(
            get_game=lambda: mock_game,
            get_play_analyze_mode=lambda: "analyze",
            mode_analyze="analyze",
            switch_ui_mode=lambda: None,
            clear_animating_pv=track_clear,
        )

        manager.do_redo(1)

        assert call_order == ["clear", "redo"], "clear must be called before redo"
