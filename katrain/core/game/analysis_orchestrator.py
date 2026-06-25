"""AnalysisOrchestrator クラス (Phase 141 分割)

``Game`` インスタンスの解析関連責務を集約する。
``analyze_all_nodes`` / ``analyze_extra`` / ``selfplay`` / ``analyze_undo`` など、
KataGo エンジンとの連携が必要な全メソッドを担当する。

責務:
- 解析ディスパッチ (``analyze_extra`` + 5 つの mode ハンドラ)
- 全ノード解析 (``analyze_all_nodes``)
- 自身対局 (``selfplay``)
- 自動 Undo (``analyze_undo``)
- 解析リセット (``reset_current_analysis``)
- 解析対象領域設定 (``set_region_of_interest``)
- エンジンキャパシティ待機 (``_wait_for_engine_capacity``)

UI ステータス通知 (``katrain.controls.set_status``) を含むため、
Kivy 環境下でのみ完全動作する。
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any

from katrain.core.constants import (
    OUTPUT_DEBUG,
    OUTPUT_EXTRA_DEBUG,
    OUTPUT_INFO,
    PRIORITY_ALTERNATIVES,
    PRIORITY_DEFAULT,
    PRIORITY_EQUALIZE,
    PRIORITY_EXTRA_ANALYSIS,
    PRIORITY_GAME_ANALYSIS,
    PRIORITY_SWEEP,
    STATUS_ANALYSIS,
    STATUS_INFO,
    STATUS_TEACHING,
    AnalysisMode,
    parse_analysis_mode,
)
from katrain.core.engine import KataGoEngine
from katrain.core.game_node import GameNode
from katrain.core.lang import i18n
from katrain.core.sgf_parser import Move
from katrain.core.utils import var_to_grid, weighted_selection_without_replacement

if TYPE_CHECKING:
    from katrain.core.game.facade import Game


class AnalysisOrchestrator:
    """解析オーケストレーション

    ``Game`` インスタンスへの参照を保持し、エンジンへの解析要求を管理する。
    全ての解析モード (STOP/PONDER/EXTRA/GAME/SWEEP/EQUALIZE/ALTERNATIVE/LOCAL)
    はここでディスパッチされる。

    Args:
        game: 操作対象の ``BaseGame`` インスタンス (``Game`` サブクラス)。
              ``engines`` / ``katrain`` / ``current_node`` / ``stones`` /
              ``set_current_node`` などを利用する。
    """

    def __init__(self, game: "Game") -> None:
        self._game = game

    # ------------------------------------------------------------------
    # 全ノード解析
    # ------------------------------------------------------------------

    def analyze_all_nodes(
        self,
        priority: int = PRIORITY_GAME_ANALYSIS,
        analyze_fast: bool = False,
        even_if_present: bool = True,
    ) -> None:
        """Analyze all nodes with throttling to avoid overwhelming the engine.

        Throttling logic:
        - Before each request, check if engine has capacity (headroom=10)
        - If at capacity, wait 0.1s and retry (up to 50 attempts = 5s max wait)
        - If still no capacity after waiting, skip the node to avoid blocking forever
        """
        game = self._game
        for sgf_node in game.root.nodes_in_tree:
            if not isinstance(sgf_node, GameNode):
                continue
            node: GameNode = sgf_node
            # forced, or not present, or something went wrong in loading
            if even_if_present or not node.analysis_from_sgf or not node.load_analysis():
                # Throttle: wait for engine capacity before sending request
                engine = game.engines[node.next_player]

                # Skip analysis if engine is disabled
                if not engine:
                    continue

                max_wait_attempts = 50  # 50 * 0.1s = 5s max wait per node
                for _ in range(max_wait_attempts):
                    if engine.has_query_capacity(headroom=10):
                        break
                    time.sleep(0.1)
                else:
                    # Timeout waiting for capacity - log and skip this node
                    game.katrain.log(
                        f"Skipping analysis for move {node.move_number}: engine at capacity",
                        OUTPUT_DEBUG,
                    )
                    continue

                node.clear_analysis()
                node.analyze(
                    engine,
                    priority=priority,
                    analyze_fast=analyze_fast,
                )

    # ------------------------------------------------------------------
    # 解析リセット
    # ------------------------------------------------------------------

    def reset_current_analysis(self) -> None:
        """現在のノードの解析をリセットして再解析する。"""
        game = self._game
        cn = game.current_node
        engine = game.engines[cn.next_player]
        engine.terminate_queries(cn)
        cn.clear_analysis()
        cn.analyze(engine)

    # ------------------------------------------------------------------
    # 解析対象領域
    # ------------------------------------------------------------------

    def set_region_of_interest(self, region_of_interest: tuple[int, int, int, int]) -> None:
        """解析対象領域を設定する。

        領域が盤全体と同等以上のサイズの場合、 ``None`` に設定される。
        """
        game = self._game
        x1, x2, y1, y2 = region_of_interest
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        szx, szy = game.board_size
        if not (xmin == xmax and ymin == ymax) and not (xmax - xmin + 1 >= szx and ymax - ymin + 1 >= szy):
            game.region_of_interest = [xmin, xmax, ymin, ymax]
        else:
            game.region_of_interest = None
        game.katrain.controls.set_status("", OUTPUT_INFO)

    # ------------------------------------------------------------------
    # analyze_extra() ハンドラ群 (Phase 70 リファクタ)
    # ------------------------------------------------------------------

    def _handle_stop_mode(self) -> None:
        """Handle STOP mode: stop pondering and terminate queries on all engines."""
        game = self._game
        game.katrain.pondering = False
        for e in set(game.engines.values()):
            e.stop_pondering()
            e.terminate_queries()

    def _handle_ponder_mode(self, cn: GameNode, engine: KataGoEngine) -> None:
        """Handle PONDER mode: start background pondering on current node."""
        game = self._game
        cn.analyze(
            engine,
            ponder=True,
            priority=PRIORITY_EXTRA_ANALYSIS,
            region_of_interest=game.region_of_interest,
            time_limit=False,
        )

    def _handle_extra_mode(self, cn: GameNode, engine: KataGoEngine) -> None:
        """Handle EXTRA mode: add more visits to current node analysis."""
        game = self._game
        visits = cn.analysis_visits_requested + engine.config["max_visits"]
        game.katrain.controls.set_status(i18n._("extra analysis").format(visits=visits), STATUS_ANALYSIS)
        cn.analyze(
            engine,
            visits=visits,
            priority=PRIORITY_EXTRA_ANALYSIS,
            region_of_interest=game.region_of_interest,
            time_limit=False,
        )

    def _wait_for_engine_capacity(self, engine: KataGoEngine, headroom: int = 10) -> bool:
        """Wait for engine capacity before sending requests.

        Args:
            engine: Engine to check capacity for.
            headroom: Minimum free slots required.

        Returns:
            True if capacity is available, False if timed out.
        """
        max_wait_attempts = 100  # 10s max wait
        for _ in range(max_wait_attempts):
            if engine.has_query_capacity(headroom=headroom):
                return True
            time.sleep(0.1)
        return False

    def _handle_game_mode(self, engine: KataGoEngine, **kwargs: Any) -> None:
        """Handle GAME mode: re-analyze all nodes in the game tree."""
        game = self._game
        nodes = [n for n in game.root.nodes_in_tree if isinstance(n, GameNode)]
        only_mistakes = kwargs.get("mistakes_only", False)
        move_range: tuple[int, int] | None = kwargs.get("move_range")
        if move_range and move_range[1] < move_range[0]:
            move_range = (move_range[1], move_range[0])  # Swap to ensure correct order
        threshold = game.katrain.config("trainer/eval_thresholds")[-4]
        if "visits" in kwargs:
            visits = kwargs["visits"]
        else:
            min_visits = min(node.analysis_visits_requested for node in nodes)
            visits = min_visits + engine.config["max_visits"]
        for node in nodes:
            max_point_loss = max(
                c.points_lost or 0 for c in [node] + [ch for ch in node.children if isinstance(ch, GameNode)]
            )
            if only_mistakes and max_point_loss <= threshold:
                continue
            if move_range and (node.depth - 1 not in range(move_range[0], move_range[1] + 1)):
                continue

            # Throttle: wait for engine capacity before sending request
            if not self._wait_for_engine_capacity(engine, headroom=10):
                game.katrain.log(
                    f"Skipping extra analysis for move {node.move_number}: engine at capacity",
                    OUTPUT_DEBUG,
                )
                continue

            node.analyze(engine, visits=visits, priority=-1_000_000, time_limit=False)
        if not move_range:
            game.katrain.controls.set_status(i18n._("game re-analysis").format(visits=visits), STATUS_ANALYSIS)
        else:
            game.katrain.controls.set_status(
                i18n._("move range analysis").format(start_move=move_range[0], end_move=move_range[1], visits=visits),
                STATUS_ANALYSIS,
            )

    def _handle_sweep_equalize_modes(
        self,
        cn: GameNode,
        engine: KataGoEngine,
        mode: AnalysisMode,
        stones: set[tuple[int, int] | None],
    ) -> None:
        """Handle SWEEP, EQUALIZE, ALTERNATIVE, and LOCAL modes.

        These modes share a common refinement loop at the end.
        """
        game = self._game
        analyze_moves: list[Move]
        visits: int
        priority: int

        if mode == AnalysisMode.SWEEP:
            board_size_x, board_size_y = game.board_size

            if cn.analysis_exists:
                policy_grid: list[list[float | None]] | None = (
                    var_to_grid(game.current_node.policy, size=(board_size_x, board_size_y))
                    if game.current_node.policy
                    else None
                )
                if policy_grid is not None:
                    # Sort by policy value when grid is available
                    moves_to_analyze: list[Move] = []
                    for x in range(board_size_x):
                        for y in range(board_size_y):
                            pval = policy_grid[y][x]
                            if pval is not None and pval >= 0:
                                moves_to_analyze.append(Move(coords=(x, y), player=cn.next_player))

                    def get_policy_key(mv: Move) -> float:
                        if mv.coords:
                            pval = policy_grid[mv.coords[1]][mv.coords[0]]
                            if pval is not None:
                                return -pval
                        return 0.0

                    analyze_moves = sorted(moves_to_analyze, key=get_policy_key)
                else:
                    # No policy grid - use all empty points
                    analyze_moves = [
                        Move(coords=(x, y), player=cn.next_player)
                        for x in range(board_size_x)
                        for y in range(board_size_y)
                        if (x, y) not in stones
                    ]
            else:
                analyze_moves = [
                    Move(coords=(x, y), player=cn.next_player)
                    for x in range(board_size_x)
                    for y in range(board_size_y)
                    if (x, y) not in stones
                ]
            visits = engine.config["fast_visits"]
            game.katrain.controls.set_status(i18n._("sweep analysis").format(visits=visits), STATUS_ANALYSIS)
            priority = PRIORITY_SWEEP

        elif mode in (AnalysisMode.EQUALIZE, AnalysisMode.ALTERNATIVE, AnalysisMode.LOCAL):
            if not cn.analysis_complete and mode != AnalysisMode.LOCAL:
                game.katrain.controls.set_status(i18n._("wait-before-extra-analysis"), STATUS_INFO, game.current_node)
                return
            if (
                mode == AnalysisMode.ALTERNATIVE
            ):  # also do a quick update on current candidates so it doesn't look too weird
                game.katrain.controls.set_status(i18n._("alternative analysis"), STATUS_ANALYSIS)
                cn.analyze(engine, priority=PRIORITY_ALTERNATIVES, time_limit=False, find_alternatives=True)
                visits = engine.config["fast_visits"]
            else:  # equalize or local
                visits = max(d["visits"] for d in cn.analysis["moves"].values())
                game.katrain.controls.set_status(i18n._("equalizing analysis").format(visits=visits), STATUS_ANALYSIS)
            priority = PRIORITY_EQUALIZE
            analyze_moves = [Move.from_gtp(gtp, player=cn.next_player) for gtp, _ in cn.analysis["moves"].items()]

        else:
            raise ValueError(f"Invalid analysis mode for sweep/equalize handler: {mode}")

        # Common refinement loop for SWEEP/EQUALIZE/ALTERNATIVE/LOCAL
        for move in analyze_moves:
            if cn.analysis["moves"].get(move.gtp(), {"visits": 0})["visits"] < visits:
                # Throttle: wait for engine capacity before sending request
                if not self._wait_for_engine_capacity(engine, headroom=5):
                    game.katrain.log(
                        f"Skipping refinement for move {move.gtp()}: engine at capacity",
                        OUTPUT_DEBUG,
                    )
                    continue
                cn.analyze(
                    engine, priority=priority, visits=visits, refine_move=move, time_limit=False
                )  # explicitly requested so take as long as you need

    # ---------------------------------------------------------------------------
    # analyze_extra() main dispatcher (Phase 70 refactoring)
    # ---------------------------------------------------------------------------

    def analyze_extra(self, mode: str | AnalysisMode, **kwargs: Any) -> None:
        """Dispatch to appropriate handler based on analysis mode.

        Phase 70: Refactored from 119-line monolithic method to dispatcher + 5 handlers.
        """
        game = self._game
        # Normalize mode to AnalysisMode at entry point
        parsed_mode = parse_analysis_mode(mode)

        stones = {s.coords for s in game.stones}
        cn = game.current_node

        if parsed_mode == AnalysisMode.STOP:
            self._handle_stop_mode()
            return

        engine = game.engines[cn.next_player]

        if parsed_mode == AnalysisMode.PONDER:
            self._handle_ponder_mode(cn, engine)
            return

        if parsed_mode == AnalysisMode.EXTRA:
            self._handle_extra_mode(cn, engine)
            return

        if parsed_mode == AnalysisMode.GAME:
            self._handle_game_mode(engine, **kwargs)
            return

        # SWEEP / EQUALIZE / ALTERNATIVE / LOCAL
        self._handle_sweep_equalize_modes(cn, engine, parsed_mode, stones)

    # ------------------------------------------------------------------
    # selfplay (自身対局)
    # ------------------------------------------------------------------

    def selfplay(self, until_move: int | str, target_b_advantage: float | None = None) -> None:
        """KataGo 同士の自己対局を実行する。"""
        game = self._game
        cn = game.current_node

        analysis_kwargs: dict[str, Any]
        engine_settings: dict[str, Any]
        if target_b_advantage is not None:
            analysis_kwargs = {"visits": max(25, game.katrain.config("engine/fast_visits"))}
            engine_settings = {"wideRootNoise": 0.03}
        else:
            analysis_kwargs = {}
            engine_settings = {}

        def set_analysis(node: GameNode, result: dict[str, Any]) -> None:
            node.set_analysis(result)
            analyze_and_play(node)

        def request_analysis_for_node(node: GameNode) -> None:
            engine = game.engines[node.player]
            if not engine:
                return
            engine.request_analysis(
                node,
                callback=lambda result, _partial: set_analysis(node, result),
                priority=PRIORITY_DEFAULT,
                analyze_fast=True,
                extra_settings=engine_settings,
                **analysis_kwargs,
            )

        def analyze_and_play(node: GameNode) -> None:
            nonlocal cn, engine_settings
            candidates = node.candidate_moves
            if game.katrain.game is not game:
                return  # a new game happened
            ai_thoughts = "Move generated by AI self-play\n"
            selected_move: Move
            if until_move != "end" and target_b_advantage is not None:  # setup pos
                assert isinstance(until_move, int)  # narrow type: not "end" means it's int
                if node.depth >= until_move or candidates[0]["move"] == "pass":
                    game.set_current_node(node)
                    return
                assert cn.score is not None and node.score is not None
                target_score = cn.score + (node.depth - cn.depth + 1) * (target_b_advantage - cn.score) / (
                    until_move - cn.depth
                )
                max_loss = 5
                stddev = min(3, 0.5 + (until_move - node.depth) * 0.15)
                ai_thoughts += f"Selecting moves aiming at score {target_score:.1f} +/- {stddev:.2f} with < {max_loss} points lost\n"
                if abs(node.score - target_score) < 3 * stddev:
                    weighted_cands = [
                        (
                            cand,
                            math.exp(-0.5 * (abs(cand["scoreLead"] - target_score) / stddev) ** 2)
                            * math.exp(-0.5 * (min(0, cand["pointsLost"]) / max_loss) ** 2),
                        )
                        for i, cand in enumerate(candidates)
                        if cand["pointsLost"] < max_loss or i == 0
                    ]
                    move_info = weighted_selection_without_replacement(weighted_cands, 1)[0][0]
                    for cand, wt in weighted_cands:
                        game.katrain.log(
                            f"{'* ' if move_info == cand else '  '} {cand['move']} {cand['scoreLead']} {wt}",
                            OUTPUT_EXTRA_DEBUG,
                        )
                        ai_thoughts += f"Move option: {cand['move']} score {cand['scoreLead']:.2f} loss {cand['pointsLost']:.2f} weight {wt:.3e}\n"
                else:  # we're a bit lost, far away from target, just push it closer
                    move_info = min(candidates, key=lambda m: abs(m["scoreLead"] - target_score))
                    game.katrain.log(
                        f"* Played {move_info['move']} {move_info['scoreLead']} because score deviation between current score {node.score} and target score {target_score} > {3 * stddev}",
                        OUTPUT_EXTRA_DEBUG,
                    )
                    ai_thoughts += f"Move played to close difference between score {node.score:.1f} and target {target_score:.1f} quickly."

                game.katrain.log(
                    f"Self-play until {until_move} target {target_b_advantage}: {len(candidates)} candidates -> move {move_info['move']} score {move_info['scoreLead']} point loss {move_info['pointsLost']}",
                    OUTPUT_DEBUG,
                )
                selected_move = Move.from_gtp(move_info["move"], player=node.next_player)
            elif candidates:  # just selfplay to end
                selected_move = Move.from_gtp(candidates[0]["move"], player=node.next_player)
            else:  # 1 visit etc
                polmoves = node.policy_ranking
                top_move = polmoves[0][1] if polmoves else None
                selected_move = top_move if top_move is not None else Move(None)
            if selected_move.is_pass:
                if game.current_node == cn:
                    game.set_current_node(node)
                return
            new_node = GameNode(parent=node, move=selected_move)
            new_node.ai_thoughts = ai_thoughts
            if until_move != "end" and target_b_advantage is not None:
                game.set_current_node(new_node)
                game.katrain.controls.set_status(
                    i18n._("setup game status message").format(move=new_node.depth, until_move=until_move),
                    STATUS_INFO,
                )
            else:
                if node != cn:
                    node.remove_shortcut()
                cn.add_shortcut(new_node)

            game.katrain.controls.move_tree.redraw_tree_trigger()
            request_analysis_for_node(new_node)

        request_analysis_for_node(cn)

    # ------------------------------------------------------------------
    # 自動 Undo
    # ------------------------------------------------------------------

    def analyze_undo(self, node: GameNode) -> None:
        """``auto_undo`` 設定に基づき、必要なら自動で undo する。"""
        game = self._game
        train_config = game.katrain.config("trainer")
        move = node.move
        if node != game.current_node or node.auto_undo is not None or not node.analysis_complete or not move:
            return
        points_lost = node.points_lost
        thresholds = train_config["eval_thresholds"]
        num_undo_prompts = train_config["num_undo_prompts"]
        i = 0
        while i < len(thresholds) and points_lost is not None and points_lost < thresholds[i]:
            i += 1
        num_undos = num_undo_prompts[i] if i < len(num_undo_prompts) else 0
        undo: bool
        parent = node.parent
        if num_undos == 0:
            undo = False
        elif num_undos < 1:  # probability
            undo = bool(node.undo_threshold < num_undos) and parent is not None and len(parent.children) == 1
        else:
            undo = parent is not None and len(parent.children) <= num_undos

        node.auto_undo = undo
        if undo:
            game.undo(1)
            game.katrain.controls.set_status(
                i18n._("teaching undo message").format(move=move.gtp(), points_lost=points_lost), STATUS_TEACHING
            )
            game.katrain.update_state()
