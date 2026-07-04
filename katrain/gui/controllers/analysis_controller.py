"""解析設定制御コントローラー（Phase 133, Phase 173 P0-①-B）

解析フォーカス（黒／白優先）の切り替え、継続解析（思考）のON/OFF、
および思考中アニメーションのアップデートを担当。
"""

from __future__ import annotations

from typing import Any, Protocol

from katrain.core.constants import OUTPUT_DEBUG


class AnalysisContext(Protocol):
    """AnalysisControllerが動作するために必要な外部インターフェース"""

    engine: Any
    game: Any
    board_controls: Any
    analysis_controls: Any
    controls: Any
    pondering: bool
    play_mode: Any
    show_move_num: bool

    def log(self, message: str, level: int) -> None: ...
    def update_state(self) -> None: ...
    def config(self, key: str, default: Any = None) -> Any: ...


class AnalysisController:
    """解析に関連するUI状態とエンジン設定の制御。

    責務:
    - 黒優先・白優先トグルの管理
    - 継続解析（思考）の切り替え
    - アニメーション用の思考ステータス更新
    """

    def __init__(self, ctx: AnalysisContext) -> None:
        self._ctx = ctx

    def set_analysis_focus_toggle(self, focus: str) -> None:
        """解析フォーカス（優先する色）を設定または解除する。"""
        engine = self._ctx.engine
        if not engine or not hasattr(engine, "config"):
            return

        current = engine.config.get("analysis_focus", None)
        # 同じ色をもう一度押したら解除、それ以外ならその色に固定
        new_focus = None if current == focus else focus

        engine.config["analysis_focus"] = new_focus
        # 10 = OUTPUT_DEBUG
        self._ctx.log(f"analysis_focus set to: {new_focus}", 10)

        try:
            self.update_focus_button_states()
            self.re_analyze_from_current_node()
        except Exception as e:
            self._ctx.log(f"set_analysis_focus_toggle() failed: {e}", 10)

    def re_analyze_from_current_node(self) -> None:
        """現在のノード以降の解析をすべてクリアして再実行する。"""
        game = self._ctx.game
        if not game or not game.root:
            return

        for node in game.root.nodes_in_tree:
            if hasattr(node, "clear_analysis"):
                node.clear_analysis()

        game.analyze_all_nodes(analyze_fast=False, even_if_present=True)
        self._ctx.log("Re-analysis started with new analysis_focus setting", 10)

    def update_focus_button_states(self) -> None:
        """UIボタンのテキスト（★マーク）を現在のフォーカス状態に合わせる。"""
        engine = self._ctx.engine
        focus = engine.config.get("analysis_focus", None) if engine and hasattr(engine, "config") else None

        board_controls = self._ctx.board_controls
        if not board_controls:
            return

        ids_map = getattr(board_controls, "ids", {}) or {}
        black_btn = ids_map.get("black_focus_btn")
        white_btn = ids_map.get("white_focus_btn")

        if black_btn is not None:
            black_btn.text = "★黒優先" if focus == "black" else "黒優先"
        if white_btn is not None:
            white_btn.text = "★白優先" if focus == "white" else "白優先"

    def handle_animations(self) -> None:
        """思考中アニメーションの数値を更新する。"""
        if not self._ctx.board_controls:
            return

        if self._ctx.pondering:
            self._ctx.board_controls.engine_status_pondering += 5
        else:
            self._ctx.board_controls.engine_status_pondering = -1

    def toggle_continuous_analysis(self, quiet: bool = False, clock: Any = None) -> None:
        """継続解析（ポンダー）の有効・無効を切り替える。"""
        if self._ctx.pondering:
            # 20 = STATUS_INFO
            self._ctx.controls.set_status("", 20)
        elif not quiet and self._ctx.analysis_controls and clock:
            clock.schedule_once(self._ctx.analysis_controls.hints.activate, 0)

        self._ctx.pondering = not self._ctx.pondering
        self._ctx.update_state()

    def toggle_move_num(self) -> None:
        """棋譜手数表示（move number overlay）の ON/OFF を切り替える。"""
        self._ctx.show_move_num = not self._ctx.show_move_num
        self._ctx.update_state()

    def restore_last_mode(self) -> None:
        """前回終了時のモード（play / analyze）を復元する。"""
        from katrain.core.constants import MODE_ANALYZE, MODE_PLAY

        try:
            last_mode = self._ctx.config("ui_state/last_mode", MODE_PLAY)
            current_mode = getattr(self._ctx.play_mode, "mode", None) if self._ctx.play_mode else None
            if last_mode == MODE_ANALYZE and current_mode == MODE_PLAY:
                # Analyze モードを復元
                self._ctx.play_mode.analyze.trigger_action(duration=0)
            elif last_mode == MODE_PLAY and current_mode == MODE_ANALYZE:
                # Play モードを復元
                self._ctx.play_mode.play.trigger_action(duration=0)
        except Exception as e:
            self._ctx.log(f"restore_last_mode() failed: {e}", OUTPUT_DEBUG)
