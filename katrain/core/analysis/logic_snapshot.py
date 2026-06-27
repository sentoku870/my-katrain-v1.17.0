"""Snapshot creation, phase mistake stats, and mistake streak detection.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- snapshot_from_nodes: Create EvalSnapshot from iterable of GameNodes
- iter_main_branch_nodes: Iterate main branch nodes of a Game
- snapshot_from_game: Create EvalSnapshot from a full Game
- aggregate_phase_mistake_stats: Phase × Mistake cross-tabulation
- detect_mistake_streaks: Go-aware consecutive mistake detection
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models import (
    EvalSnapshot,
    MistakeStreak,
    MoveEval,
    PhaseMistakeStats,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode


# =============================================================================
# Snapshot creation
# =============================================================================


def snapshot_from_nodes(nodes: Iterable[GameNode]) -> EvalSnapshot:
    """
    任意の GameNode 群から EvalSnapshot を作成するユーティリティ。
    """
    # Lazy imports to avoid circular dependencies
    from katrain.core.analysis.logic_loss import classify_mistake, compute_canonical_loss
    from katrain.core.analysis.logic_reliability import (
        is_reliable_from_visits,
        move_eval_from_node,
    )
    from katrain.core.analysis.logic_importance import compute_importance_for_moves

    # GameNode と MoveEval のペアを保持
    node_evals: list[tuple[GameNode, MoveEval]] = []
    node_list = list(nodes)

    # 解析済みSGFの場合、load_analysis() を呼び出し
    loaded_nodes: set[int] = set()
    for node in node_list:
        node_id = id(node)
        if node_id not in loaded_nodes:
            if hasattr(node, "analysis_from_sgf") and node.analysis_from_sgf:
                if hasattr(node, "load_analysis"):
                    node.load_analysis()
            loaded_nodes.add(node_id)
        parent = getattr(node, "parent", None)
        if parent is not None:
            parent_id = id(parent)
            if parent_id not in loaded_nodes:
                if hasattr(parent, "analysis_from_sgf") and parent.analysis_from_sgf:
                    if hasattr(parent, "load_analysis"):
                        parent.load_analysis()
                loaded_nodes.add(parent_id)

    for node in node_list:
        if getattr(node, "move", None) is None:
            continue
        mv = move_eval_from_node(node)
        node_evals.append((node, mv))

    # 手数順に並べる
    node_evals.sort(key=lambda pair: pair[1].move_number)

    # 連続する手から before / delta を埋める
    prev: MoveEval | None = None
    for _node, m in node_evals:
        if prev is not None:
            m.score_before = prev.score_after
            m.winrate_before = prev.winrate_after

            if m.score_before is not None and m.score_after is not None:
                m.delta_score = m.score_after - m.score_before
            else:
                m.delta_score = None

            if m.winrate_before is not None and m.winrate_after is not None:
                m.delta_winrate = m.winrate_after - m.winrate_before
            else:
                m.delta_winrate = None

        # score_loss / winrate_loss を計算
        score_loss, winrate_loss = compute_canonical_loss(
            points_lost=m.points_lost,
            delta_score=m.delta_score,
            delta_winrate=m.delta_winrate,
            player=m.player,
        )
        m.score_loss = score_loss
        m.winrate_loss = winrate_loss

        # ミス分類
        m.mistake_category = classify_mistake(
            score_loss=score_loss,
            winrate_loss=winrate_loss,
        )
        m.is_reliable = is_reliable_from_visits(m.root_visits)

        prev = m

    # importance を自動計算
    all_moves = [m for _, m in node_evals]
    compute_importance_for_moves(all_moves)

    return EvalSnapshot(moves=all_moves)


def iter_main_branch_nodes(game: Any) -> Iterable[GameNode]:
    """
    KaTrain の Game インスタンスから、
    ルートからメイン分岐のノード列を順に返す。
    """
    root = getattr(game, "root", None)
    if root is None:
        return

    # Phase 148-B'1: 本物の GameNode ツリーでない（Mock 等）場合は処理しない。
    # MagicMock の children は反復可能に見えるが実態と異なり、アクセスのたびに
    # 新しい Mock を生成して極端に重くなる/ハングするため list/tuple でなければ早期リターン。
    root_children = getattr(root, "children", None)
    if not isinstance(root_children, (list, tuple)):
        return

    node = root

    # Phase 148-B'1: 安全上限。循環参照や不完全なゲームオブジェクト（Mock 等）に
    # よる無限ループを防ぐ。Go の1局は実質数百手だが余裕を見て 2000 とする。
    for _ in range(2000):
        if getattr(node, "move", None) is not None:
            yield node

        children = getattr(node, "children", None)
        if not children:
            break

        main_children = [c for c in children if getattr(c, "is_mainline", False)]
        if not main_children:
            main_children = [c for c in children if getattr(c, "is_main", False)]

        next_node = main_children[0] if main_children else children[0]
        node = next_node


def snapshot_from_game(game: Any) -> EvalSnapshot:
    """
    Game 全体（メイン分岐）から EvalSnapshot を生成するヘルパー。
    """
    nodes_iter = iter_main_branch_nodes(game)
    return snapshot_from_nodes(nodes_iter)


# =============================================================================
# Phase mistake stats
# =============================================================================


def aggregate_phase_mistake_stats(
    moves: Iterable[MoveEval],
    *,
    score_thresholds: tuple[float, float, float] | None = None,
    board_size: int = 19,
) -> PhaseMistakeStats:
    """
    手のリストから Phase × Mistake クロス集計を行う共有アグリゲータ。
    """
    # Lazy import to avoid circular dependency with logic_phase
    from katrain.core.analysis.logic_phase import classify_game_phase

    if score_thresholds is None:
        score_thresholds = (1.0, 3.0, 7.0)

    inaccuracy_th, mistake_th, blunder_th = score_thresholds

    result = PhaseMistakeStats()

    for mv in moves:
        if mv.points_lost is None:
            continue

        phase = classify_game_phase(mv.move_number, board_size=board_size)

        loss = max(0.0, mv.points_lost)
        if loss < inaccuracy_th:
            category = "GOOD"
        elif loss < mistake_th:
            category = "INACCURACY"
        elif loss < blunder_th:
            category = "MISTAKE"
        else:
            category = "BLUNDER"

        key = (phase, category)
        result.phase_mistake_counts[key] = result.phase_mistake_counts.get(key, 0) + 1
        if loss > 0:
            result.phase_mistake_loss[key] = result.phase_mistake_loss.get(key, 0.0) + loss

        result.phase_moves[phase] = result.phase_moves.get(phase, 0) + 1
        if loss > 0:
            result.phase_loss[phase] = result.phase_loss.get(phase, 0.0) + loss

        result.total_moves += 1
        result.total_loss += loss

    return result


# =============================================================================
# Mistake streaks
# =============================================================================


def detect_mistake_streaks(
    moves: list[MoveEval],
    *,
    loss_threshold: float = 2.0,
    min_consecutive: int = 2,
) -> list[MistakeStreak]:
    """
    同一プレイヤーの連続ミスを検出する（Go-aware streak detection）
    """
    if not moves:
        return []

    # Lazy import to avoid circular dependency
    from katrain.core.analysis.models.move_eval import get_canonical_loss_from_move

    player_moves: dict[str, list[MoveEval]] = {"B": [], "W": []}
    for m in moves:
        if m.player in player_moves:
            player_moves[m.player].append(m)

    streaks = []

    for player, pmoves in player_moves.items():
        if not pmoves:
            continue

        sorted_moves = sorted(pmoves, key=lambda m: m.move_number)
        current_streak: list[MoveEval] = []

        for m in sorted_moves:
            if m.points_lost is None:
                if len(current_streak) >= min_consecutive:
                    total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
                    streaks.append(
                        MistakeStreak(
                            player=player,
                            start_move=current_streak[0].move_number,
                            end_move=current_streak[-1].move_number,
                            move_count=len(current_streak),
                            total_loss=total_loss,
                            moves=list(current_streak),
                        )
                    )
                current_streak = []
                continue

            loss = max(0.0, m.points_lost)
            if loss >= loss_threshold:
                current_streak.append(m)
            else:
                if len(current_streak) >= min_consecutive:
                    total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
                    streaks.append(
                        MistakeStreak(
                            player=player,
                            start_move=current_streak[0].move_number,
                            end_move=current_streak[-1].move_number,
                            move_count=len(current_streak),
                            total_loss=total_loss,
                            moves=list(current_streak),
                        )
                    )
                current_streak = []

        if len(current_streak) >= min_consecutive:
            total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
            streaks.append(
                MistakeStreak(
                    player=player,
                    start_move=current_streak[0].move_number,
                    end_move=current_streak[-1].move_number,
                    move_count=len(current_streak),
                    total_loss=total_loss,
                    moves=list(current_streak),
                )
            )

    streaks.sort(key=lambda s: s.start_move)
    return streaks
