"""Game クラス (Phase 141 分割)

``BaseGame`` を継承し、解析・挿入モード・重要局面ナビなどの機能を
``GameNavigator`` / ``AnalysisOrchestrator`` / ``InsertModeController``
に委譲して合成するクラス。

後方互換のため、既存呼び出し元 (``game.analyze_extra(...)`` 等) は
従来通り動作する。
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from katrain.core.constants import (
    OUTPUT_INFO,
    AnalysisMode,
)
from katrain.core.engine import KataGoEngine
from katrain.core.game.analysis_orchestrator import AnalysisOrchestrator
from katrain.core.game.base import BaseGame
from katrain.core.game.insert_mode import InsertModeController
from katrain.core.game.navigation import GameNavigator
from katrain.core.game_node import GameNode
from katrain.core.reports.karte.models import KarteGenerationError  # re-exported for backward compatibility
from katrain.core.sgf_parser import Move

# eval_metrics は katrain.core 直下のパッケージ (このファイルが katrain.core.game 配下のため明示的に絶対 import)
from katrain.core import eval_metrics
from katrain.core.eval_metrics import (
    EvalSnapshot,
    GameSummaryData,
    MistakeCategory,
    MoveEval,
    snapshot_from_game,
)


class Game(BaseGame):
    """Extensions related to analysis etc.

    解析・ナビ・挿入モードなどの各責務は、内部のコントローラに委譲する。
    既存 API は維持されるため、呼び出し側の変更は不要。
    """

    # Class-level type annotations for instance variables
    engines: dict[str, KataGoEngine]
    insert_after: GameNode | None
    region_of_interest: list[int | None] | None
    navigator: GameNavigator
    analysis: AnalysisOrchestrator
    insert_mode_ctrl: InsertModeController

    def __init__(
        self,
        katrain: Any,
        engine: dict[str, Any] | Any,
        move_tree: GameNode | None = None,
        analyze_fast: bool = False,
        game_properties: dict[str, Any | None] | None = None,
        sgf_filename: str | None = None,
    ) -> None:
        super().__init__(
            katrain=katrain, move_tree=move_tree, game_properties=game_properties, sgf_filename=sgf_filename
        )
        if not isinstance(engine, dict):
            engine = {"B": engine, "W": engine}
        self.engines = engine

        self.insert_mode = False
        self.insert_after = None
        self.region_of_interest = None

        # Initialize controllers (Phase 1-3)
        self.navigator = GameNavigator(self)
        self.analysis = AnalysisOrchestrator(self)
        self.insert_mode_ctrl = InsertModeController(self)

        # Stop any existing pondering before starting full-game analysis
        katrain.pondering = False
        for e in set(self.engines.values()):
            if e:
                e.stop_pondering()

        threading.Thread(
            target=lambda: self.analyze_all_nodes(analyze_fast=analyze_fast, even_if_present=True),
            daemon=True,
        ).start()  # return faster, but bypass Kivy Clock

    # ------------------------------------------------------------------
    # 解析オーケストレーション (Phase 2: AnalysisOrchestrator に委譲)
    # ------------------------------------------------------------------

    def analyze_all_nodes(
        self,
        priority: int | None = None,
        analyze_fast: bool = False,
        even_if_present: bool = True,
        *,
        throttle_max_attempts: int = 50,
        throttle_poll_interval: float = 0.1,
    ) -> None:
        from katrain.core.constants import PRIORITY_GAME_ANALYSIS

        if priority is None:
            priority = PRIORITY_GAME_ANALYSIS
        return self.analysis.analyze_all_nodes(
            priority=priority,
            analyze_fast=analyze_fast,
            even_if_present=even_if_present,
            throttle_max_attempts=throttle_max_attempts,
            throttle_poll_interval=throttle_poll_interval,
        )

    def analyze_extra(self, mode: str | AnalysisMode, **kwargs: Any) -> None:
        return self.analysis.analyze_extra(mode, **kwargs)

    def selfplay(self, until_move: int | str, target_b_advantage: float | None = None) -> None:
        return self.analysis.selfplay(until_move, target_b_advantage)

    def analyze_undo(self, node: GameNode) -> None:
        return self.analysis.analyze_undo(node)

    def reset_current_analysis(self) -> None:
        return self.analysis.reset_current_analysis()

    def set_region_of_interest(self, region_of_interest: tuple[int, int, int, int]) -> None:
        return self.analysis.set_region_of_interest(region_of_interest)

    # backward-compat private method aliases (used by tests)
    def _handle_stop_mode(self) -> None:
        return self.analysis._handle_stop_mode()

    def _handle_ponder_mode(self, cn: GameNode, engine: KataGoEngine) -> None:
        return self.analysis._handle_ponder_mode(cn, engine)

    def _handle_extra_mode(self, cn: GameNode, engine: KataGoEngine) -> None:
        return self.analysis._handle_extra_mode(cn, engine)

    def _handle_game_mode(self, engine: KataGoEngine, **kwargs: Any) -> None:
        return self.analysis._handle_game_mode(engine, **kwargs)

    def _handle_sweep_equalize_modes(
        self,
        cn: GameNode,
        engine: KataGoEngine,
        mode: AnalysisMode,
        stones: set[tuple[int, int] | None],
    ) -> None:
        return self.analysis._handle_sweep_equalize_modes(cn, engine, mode, stones)

    def _wait_for_engine_capacity(
        self,
        engine: KataGoEngine,
        headroom: int = 10,
        *,
        max_attempts: int = 100,
        poll_interval: float = 0.1,
    ) -> bool:
        return self.analysis._wait_for_engine_capacity(
            engine, headroom, max_attempts=max_attempts, poll_interval=poll_interval
        )

    def build_eval_snapshot(self) -> EvalSnapshot:
        """
        現在の Game（メイン分岐）から EvalSnapshot を生成するヘルパー。

        Phase 2 以降で UI や教育機能から共通で呼び出す入口として使う。
        """
        return snapshot_from_game(self)

    def log_mistake_summary_for_debug(self) -> None:
        """
        対局全体のミス分類サマリをコンソールに出力するデバッグ用ユーティリティ。
        - Phase3 のしきい値設定・挙動確認に使用する。
        """
        snapshot = self.build_eval_snapshot()

        counts: dict[MistakeCategory, int] = {}
        for m in snapshot.moves:
            # None の場合は GOOD 扱いに寄せる
            cat = m.mistake_category or MistakeCategory.GOOD
            counts[cat] = counts.get(cat, 0) + 1

        total_moves = len(snapshot.moves)

        print("=== Mistake summary (debug) ===")
        print(f"Total moves: {total_moves}")
        # カテゴリ順に固定したい場合は MistakeCategory の順で回す
        for cat in MistakeCategory:
            n = counts.get(cat, 0)
            label = cat.value  # "BLUNDER" 等
            print(f"{label:10s}: {n:3d}")

    # ------------------------------------------------------------------
    # 重要局面レポート / YoseAnalyzer 連携用のヘルパー
    # ------------------------------------------------------------------

    def _find_node_by_move_number(self, move_number: int) -> GameNode | None:
        """メインブランチの手数でノードを検索

        Args:
            move_number: 手数（1-indexed）

        Returns:
            GameNode | None: 見つかったノード、または None
        """
        for node in eval_metrics.iter_main_branch_nodes(self):
            node_move_no = len(node.nodes_from_root) - 1
            if node_move_no == move_number:
                return node
        return None

    def get_important_move_evals(
        self,
        *,
        level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
        compute_reason_tags: bool = True,
    ) -> list[MoveEval]:
        """
        現在の対局（メイン分岐）について、
        重要度スコアの大きい手 (= 重要局面候補) を MoveEval のリストとして返す。

        - EvalSnapshot + pick_important_moves をまとめた入口。
        - 今後 YoseAnalyzer からもここを呼ぶ想定。
        """
        snapshot = self.build_eval_snapshot()

        # 手が 1 手もない（起動直後の空局面など）は空リスト
        if not snapshot.moves:
            return []

        important_moves = eval_metrics.pick_important_moves(
            snapshot,
            level=level,
            recompute=True,
        )

        # Phase 5: 重要局面のみ理由タグを計算
        if compute_reason_tags:
            from katrain.core import board_analysis

            unknown_count = 0
            for move_eval in important_moves:
                try:
                    # 対応するノードを検索
                    node = self._find_node_by_move_number(move_eval.move_number)
                    if node is None:
                        move_eval.reason_tags = ["unknown"]
                        unknown_count += 1
                        continue

                    # このノードで盤面を分析
                    board_state = board_analysis.analyze_board_at_node(self, node)

                    # 候補手を取得
                    candidates = node.candidate_moves if hasattr(node, "candidate_moves") else []

                    # タグを計算（Phase 17: skill_preset を渡す）
                    move_eval.reason_tags = board_analysis.get_reason_tags_for_move(
                        board_state, move_eval, node, candidates, skill_preset=level
                    )

                    # タグが空の場合は "unknown" を設定
                    if not move_eval.reason_tags:
                        move_eval.reason_tags = ["unknown"]
                        unknown_count += 1
                except Exception as e:
                    # 失敗時は優雅に処理: 分析失敗時は "unknown" を設定
                    self.katrain.log(
                        f"Failed to compute reason tags for move #{move_eval.move_number}: {e}", OUTPUT_INFO
                    )
                    move_eval.reason_tags = ["unknown"]
                    unknown_count += 1

            # unknown_count をログに出力（カバレッジ確認用）
            if unknown_count > 0 and important_moves:
                self.katrain.log(
                    f"[ReasonTags] {unknown_count}/{len(important_moves)} moves have unknown reason tags", OUTPUT_INFO
                )

        return important_moves

    def build_important_moves_report(
        self,
        *,
        level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
        max_lines: int | None = None,
    ) -> str:
        """
        現在の対局（メイン分岐）について、
        「重要度スコアが大きい手」をテキストレポートとして返す。

        - 手数 / 手番 / 着手 / 損失(目) / ミス分類 / 難易度 / 形勢差Δ / 勝率Δ
        - eval_metrics.pick_important_moves の結果に基づく

        Args:
            level:
                重要局面検出のレベル。
                - "easy"   : ゆるめに拾う
                - "normal" : 標準
                - "strict" : より厳しめに大きな局面だけ
            max_lines:
                レポートの最大行数（None の場合は全件）

        Note:
            PR #120: Moved implementation to katrain.core.reports.important_moves_report
        """
        from katrain.core.reports import important_moves_report

        important_moves = self.get_important_move_evals(level=level)
        return important_moves_report.build_important_moves_report(
            important_moves,
            level=level,
            max_lines=max_lines,
        )

    def build_karte_report(
        self,
        level: str = eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL,
        player_filter: str | None = None,
        raise_on_error: bool = False,
        skill_preset: str = eval_metrics.DEFAULT_SKILL_PRESET,
        target_visits: int | None = None,
    ) -> str:
        """Build a compact, markdown-friendly report for the current game.

        Args:
            level: Important move level setting
            player_filter: Filter by player ("B", "W", or None for both)
                          Can also be a username string to match against player names
            raise_on_error: If True, raise KarteGenerationError on failure.
                           If False (default), return error markdown instead.
            skill_preset: Skill preset for strictness ("auto" or one of SKILL_PRESETS keys)
            target_visits: Target visits for effective reliability threshold calculation.
                If None, uses the hardcoded RELIABILITY_VISITS_THRESHOLD (200).

        Returns:
            Markdown-formatted karte report.
            On error with raise_on_error=False, returns a report with ERROR section.

        Raises:
            KarteGenerationError: If raise_on_error=True and generation fails.

        Note:
            PR #119: Moved implementation to katrain.core.reports.karte_report
        """
        from katrain.core.reports import karte_report

        return karte_report.build_karte_report(
            self,
            level=level,
            player_filter=player_filter,
            raise_on_error=raise_on_error,
            skill_preset=skill_preset,
            target_visits=target_visits,
        )

    # ------------------------------------------------------------------
    # Quiz Methods (Phase B2)
    # ------------------------------------------------------------------

    def get_quiz_items(
        self,
        *,
        loss_threshold: float = eval_metrics.DEFAULT_QUIZ_LOSS_THRESHOLD,
        limit: int = eval_metrics.DEFAULT_QUIZ_ITEM_LIMIT,
    ) -> list[eval_metrics.QuizItem]:
        """
        対局からクイズ用の大きなミス一覧を取得。
        """
        from katrain.core.reports import quiz_report

        snapshot = self.build_eval_snapshot()
        return quiz_report.get_quiz_items(
            snapshot,
            loss_threshold=loss_threshold,
            limit=limit,
        )

    def build_quiz_questions(
        self,
        quiz_items: list[eval_metrics.QuizItem],
        *,
        max_choices: int = 3,
    ) -> list[eval_metrics.QuizQuestion]:
        """
        クイズ項目からクイズ問題を生成。
        """
        from katrain.core.reports import quiz_report

        return quiz_report.build_quiz_questions(
            quiz_items,
            self.get_main_branch_node_before_move,
            max_choices=max_choices,
        )

    @staticmethod
    def build_summary_report(game_data_list: list[GameSummaryData], focus_player: str | None = None) -> str:
        """
        複数局から統計まとめを生成（Phase 6）

        Note: PR #116 で katrain.core.reports.summary_report に移動。
        後方互換性のため委譲メソッドを残す。

        Args:
            game_data_list: 各対局のデータリスト
            focus_player: 集計対象プレイヤー名（Noneなら全プレイヤー）

        Returns:
            Markdown形式のまとめレポート
        """
        from katrain.core.reports import summary_report

        return summary_report.build_summary_report(game_data_list, focus_player)

    def log_important_moves_for_debug(
        self,
        *,
        level: str = "normal",
    ) -> None:
        """
        現在の対局（メイン分岐）について、
        「重要度スコアが大きい手」をログに出力するデバッグ用ヘルパー。

        - UI からはまだ呼ばない想定。
        - Phase 2 以降の機能実装時に挙動確認用として利用する。

        Args:
            level: 重要局面検出のレベル ("easy" / "normal" / "strict")
        """
        important_moves = self.get_important_move_evals(level=level)

        if not important_moves:
            settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
                level,
                eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
            )
            self.katrain.log(
                f"[Eval] No moves with importance > {settings.importance_threshold}",
                OUTPUT_INFO,
            )
            return

        # ヘッダ行
        settings = eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level,
            eval_metrics.IMPORTANT_MOVE_SETTINGS_BY_LEVEL[eval_metrics.DEFAULT_IMPORTANT_MOVE_LEVEL],
        )
        self.katrain.log(
            f"[Eval] Important moves (level={level}, "
            f"threshold={settings.importance_threshold}, max_moves={settings.max_moves})",
            OUTPUT_INFO,
        )

        # 各手を 1 行ずつログ出力
        for m in important_moves:
            self.katrain.log(
                (
                    "[Eval] move #{num} {player} {gtp} "
                    "score_before={sb} score_after={sa} "
                    "delta_score={ds} points_lost={pl} "
                    "importance={imp}"
                ).format(
                    num=m.move_number,
                    player=m.player or "-",
                    gtp=m.gtp or "-",
                    sb=None if m.score_before is None else f"{m.score_before:.2f}",
                    sa=None if m.score_after is None else f"{m.score_after:.2f}",
                    ds=None if m.delta_score is None else f"{m.delta_score:.2f}",
                    pl=None if m.points_lost is None else f"{m.points_lost:.2f}",
                    imp=None if m.importance_score is None else f"{m.importance_score:.2f}",
                ),
                OUTPUT_INFO,
            )

    # ------------------------------------------------------------------
    # 重要局面ナビ用のヘルパー (Phase 1: GameNavigator に委譲)
    # ------------------------------------------------------------------

    def _iter_main_branch_nodes(self) -> "Iterator[GameNode]":
        return self.navigator._iter_main_branch_nodes()

    def get_main_branch_node_before_move(self, move_number: int) -> GameNode | None:
        return self.navigator.get_main_branch_node_before_move(move_number)

    def _compute_important_moves(self, max_moves: int = 20) -> list[tuple[int, float, GameNode]]:
        return self.navigator._compute_important_moves(max_moves=max_moves)

    def get_important_move_numbers(self, max_moves: int = 20) -> list[int]:
        return self.navigator.get_important_move_numbers(max_moves=max_moves)

    def get_next_important_node(self, max_moves: int = 20) -> GameNode | None:
        return self.navigator.get_next_important_node(max_moves=max_moves)

    def get_prev_important_node(self, max_moves: int = 20) -> GameNode | None:
        return self.navigator.get_prev_important_node(max_moves=max_moves)

    def jump_to_next_important_move(self, max_moves: int = 20) -> GameNode | None:
        return self.navigator.jump_to_next_important_move(max_moves=max_moves)

    def jump_to_prev_important_move(self, max_moves: int = 20) -> GameNode | None:
        return self.navigator.jump_to_prev_important_move(max_moves=max_moves)

    # ------------------------------------------------------------------
    # 挿入モード (Phase 3: InsertModeController に委譲)
    # ------------------------------------------------------------------

    def set_current_node(self, node: GameNode) -> None:
        # BaseGame.__init__ から呼ばれるため、insert_mode_ctrl 未設定の可能性あり
        ctrl = getattr(self, "insert_mode_ctrl", None)
        if ctrl is not None and ctrl.handle_set_current_node(node):
            return
        super().set_current_node(node)

    def undo(self, n_times: int | str = 1, stop_on_mistake: Any = None) -> None:
        """Undo with insert-mode handling. Thread-safe via RLock."""
        ctrl = getattr(self, "insert_mode_ctrl", None)
        with self._lock:
            if ctrl is not None and ctrl.handle_undo(n_times):
                return
            super().undo(n_times=n_times, stop_on_mistake=stop_on_mistake)

    def redo(self, n_times: int = 1, stop_on_mistake: float | None = None) -> None:
        ctrl = getattr(self, "insert_mode_ctrl", None)
        if ctrl is not None and ctrl.handle_redo():
            return
        super().redo(n_times=n_times, stop_on_mistake=stop_on_mistake)

    def set_insert_mode(self, mode: bool | str) -> None:
        ctrl = getattr(self, "insert_mode_ctrl", None)
        if ctrl is not None:
            ctrl.set_insert_mode(mode)

    # Play a Move from the current position, raise IllegalMoveException if invalid.
    def play(self, move: Move, ignore_ko: bool = False, analyze: bool = True) -> GameNode:
        played_node = super().play(move, ignore_ko)
        if analyze:
            if self.region_of_interest:
                played_node.analyze(self.engines[played_node.next_player], analyze_fast=True)
                played_node.analyze(self.engines[played_node.next_player], region_of_interest=self.region_of_interest)
            else:
                played_node.analyze(self.engines[played_node.next_player])
        return played_node


# Backward-compatibility re-exports (used by tests/conftest.py and external code)
__all__ = [
    "BaseGame",
    "Game",
    "IllegalMoveException",
    "KaTrainSGF",
    "Move",
    "KarteGenerationError",
    "GameNavigator",
    "AnalysisOrchestrator",
    "InsertModeController",
]
