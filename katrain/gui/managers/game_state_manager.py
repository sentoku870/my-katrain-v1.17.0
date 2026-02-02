"""ゲーム状態管理マネージャー（Phase 76）

ゲーム状態のライフサイクル操作（undo/redo/navigation）を担当。
依存注入パターンでKivy非依存テストを実現。

使用例:
    from katrain.gui.managers.game_state_manager import GameStateManager

    manager = GameStateManager(
        get_game=lambda: self.game,
        get_play_analyze_mode=lambda: self.play_analyze_mode,
        mode_analyze=MODE_ANALYZE,
        switch_ui_mode=lambda: self.play_mode.switch_ui_mode() if self.play_mode else None,
        clear_animating_pv=lambda: setattr(self.board_gui, "animating_pv", None) if self.board_gui else None,
    )

    manager.do_undo(n_times=1)
    manager.do_redo(n_times=5)
"""
from __future__ import annotations

from typing import Callable, Protocol


class GameNodeProtocol(Protocol):
    """GameStateManagerが使用するGameNodeの最小インターフェース"""

    player: str
    note: str | None
    end_state: str | None


class GameProtocol(Protocol):
    """GameStateManagerが使用するGameの最小インターフェース"""

    current_node: GameNodeProtocol | None

    def undo(self, n_times: int = 1) -> None:
        ...

    def redo(self, n_times: int = 1) -> None:
        ...

    def jump_to_prev_important_move(self) -> None:
        ...

    def jump_to_next_important_move(self) -> None:
        ...

    def reset_current_analysis(self) -> None:
        ...

    def set_insert_mode(self, mode: str) -> None:
        ...


class GameStateManager:
    """ゲーム状態のライフサイクル管理

    責務:
    - undo/redo操作
    - 重要局面ナビゲーション
    - 解析リセット
    - 投了処理
    - ノート設定
    - 挿入モード切替

    不変条件:
    - 全メソッドはgame=Noneで安全（クラッシュしない）
    - game=Noneの場合、ゲーム操作は行わないがUIコールバックは呼ばれる場合あり
      （例: do_undo/do_redoはgame=NoneでもPVクリアを実行）
    - UIスレッドからの呼び出しを想定（メッセージループ経由）
    """

    def __init__(
        self,
        get_game: Callable[[], GameProtocol | None],
        get_play_analyze_mode: Callable[[], str],
        mode_analyze: str,
        switch_ui_mode: Callable[[], None],
        clear_animating_pv: Callable[[], None],
    ) -> None:
        """GameStateManagerを初期化する。

        Args:
            get_game: 現在のGameオブジェクトを取得するコールバック
            get_play_analyze_mode: 現在のモード（MODE_PLAY/MODE_ANALYZE）を取得
            mode_analyze: MODE_ANALYZE定数値（文字列注入）
            switch_ui_mode: PlayModeウィジェットのモード切替コールバック
            clear_animating_pv: board_gui.animating_pvをNoneに設定するコールバック
        """
        self._get_game = get_game
        self._get_play_analyze_mode = get_play_analyze_mode
        self._mode_analyze = mode_analyze
        self._switch_ui_mode = switch_ui_mode
        self._clear_animating_pv = clear_animating_pv

    def do_undo(self, n_times: int = 1) -> None:
        """アンドゥ実行。

        Args:
            n_times: 戻す手数

        Note:
            "smart" モードの判定はKaTrainGuiで行い、解決済みの
            n_timesを渡すこと。
        """
        self._clear_animating_pv()
        game = self._get_game()
        if game is not None:
            game.undo(n_times)

    def do_redo(self, n_times: int = 1) -> None:
        """リドゥ実行。

        Args:
            n_times: 進める手数
        """
        self._clear_animating_pv()
        game = self._get_game()
        if game is not None:
            game.redo(n_times)

    def do_prev_important(self) -> None:
        """前の重要局面にジャンプ。"""
        game = self._get_game()
        if game is not None:
            game.jump_to_prev_important_move()

    def do_next_important(self) -> None:
        """次の重要局面にジャンプ。"""
        game = self._get_game()
        if game is not None:
            game.jump_to_next_important_move()

    def do_reset_analysis(self) -> None:
        """現在のノードの解析をリセット。"""
        game = self._get_game()
        if game is not None:
            game.reset_current_analysis()

    def do_resign(self) -> None:
        """投了処理。

        end_stateを"{winner}+R"形式で設定する。
        current_node.playerは最後の着手者であり、投了側の対戦相手（勝者）となる。

        例: 黒が着手後、白が投了 → end_state = "B+R"（黒勝ち）
        """
        game = self._get_game()
        if game is not None and game.current_node is not None:
            winner = game.current_node.player
            game.current_node.end_state = f"{winner}+R"

    def set_note(self, note: str) -> None:
        """現在のノードにノートを設定。

        Args:
            note: ノートテキスト（UIのTextInput.textから渡される、常に文字列）

        Note:
            この関数はgui.kvから直接呼び出され、メッセージループを通らない。
            UI更新は不要（TextInputが既に表示済み）。

        Type assumption:
            noteは常にstr型。KivyのTextInput.textは常に文字列を返すため、
            str | None対応は不要。歴史的にKaTrainGui.set_noteは型注釈なしだったが、
            実際の使用ではすべて文字列。
        """
        game = self._get_game()
        if game is not None and game.current_node is not None:
            game.current_node.note = note

    def do_insert_mode(self, mode: str = "toggle") -> None:
        """挿入モードを切り替え。

        Args:
            mode: "toggle" または具体的なモード名

        Side effects:
            MODE_ANALYZE以外の場合、switch_ui_mode()を呼び出す。
        """
        game = self._get_game()
        if game is not None:
            game.set_insert_mode(mode)
            if self._get_play_analyze_mode() != self._mode_analyze:
                self._switch_ui_mode()
