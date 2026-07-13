"""Phase B2: Position difficulty — public API.

This module aggregates the four difficulty axes (policy, transition,
state, error_pressure, lcb_gap) — see ``_io.py`` / ``_policy.py`` /
``_transition.py`` / ``_state.py`` / ``_error_pressure.py`` /
``_lcb_gap.py`` — and exposes the four entry points documented for
GUI / batch consumers:

- :func:`assess_position_difficulty_from_parent`
- :func:`compute_difficulty_metrics`
- :func:`extract_difficult_positions`
- :func:`difficulty_metrics_from_node`

History: extracted from ``katrain.core.analysis.logic_difficulty``
(Phase 144-C) in Phase B2.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.difficulty._error_pressure import compute_error_pressure
from katrain.core.analysis.difficulty._io import (
    _difficulty_logger,
    determine_reliability,
    get_candidates_from_node,
    normalize_candidates,
)
from katrain.core.analysis.difficulty._lcb_gap import compute_lcb_gap
from katrain.core.analysis.difficulty._policy import (
    assess_difficulty_from_policy,
    compute_policy_difficulty,
)
from katrain.core.analysis.difficulty._state import compute_state_difficulty
from katrain.core.analysis.difficulty._transition import (
    compute_transition_difficulty,
)
from katrain.core.analysis.models import (
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_UNKNOWN,
    ERROR_PRESSURE_WEIGHT,
    LCB_GAP_WEIGHT,
    DifficultyMetrics,
    PositionDifficulty,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

_logger = _difficulty_logger or logging.getLogger(__name__)


__all__ = [
    "assess_position_difficulty_from_parent",
    "compute_difficulty_metrics",
    "extract_difficult_positions",
    "difficulty_metrics_from_node",
]


# =============================================================================
# Position difficulty assessment (heuristic)
# =============================================================================


def assess_position_difficulty_from_parent(
    node: GameNode,
    *,
    root_visits: int = 0,
    good_rel_threshold: float = 1.0,
    near_rel_threshold: float = 2.0,
    use_policy_fallback: bool = True,
) -> tuple[PositionDifficulty | None, float | None]:
    """
    親ノードの candidate_moves から局面難易度をざっくり評価する。

    Phase 148-B1: root_visits ガード追加。探索が浅い（< DIFFICULTY_MIN_VISITS）
    場合は候補手の relativePointsLost が信頼できず、ONLY_MOVE の誤判定
    （実質的に1手しか読んでいないだけ）を招くため UNKNOWN を返す。
    """
    parent = getattr(node, "parent", None)
    if parent is None:
        return None, None

    # B1: visits ガード（root_visits=0 は未指定扱いでスキップ＝後方互換）
    if root_visits and root_visits < DIFFICULTY_MIN_VISITS:
        return PositionDifficulty.UNKNOWN, None

    # 1. candidate_moves からの判定
    candidate_moves = getattr(parent, "candidate_moves", None)
    if candidate_moves is not None and len(candidate_moves) > 0:
        good_moves: list[float] = []
        near_moves: list[float] = []

        for mv in candidate_moves:
            rel = mv.get("relativePointsLost")
            if rel is None:
                rel = mv.get("pointsLost")
            if rel is None:
                continue
            rel_f = float(rel)

            if rel_f <= good_rel_threshold:
                good_moves.append(rel_f)
            if rel_f <= near_rel_threshold:
                near_moves.append(rel_f)

        if good_moves or near_moves:
            n_good = len(good_moves)
            n_near = len(near_moves)

            if n_good <= 1 and n_near <= 2:
                # Forced move or single solution
                label = PositionDifficulty.ONLY_MOVE
                score = 1.0
            elif n_good <= 2:
                label = PositionDifficulty.HARD
                score = 0.8
            elif n_good >= 5 or n_near >= 6:  # Changed from >=4 to >=5 to allow NORMAL for 3-4 good moves
                label = PositionDifficulty.EASY
                score = 0.2
            else:
                label = PositionDifficulty.NORMAL
                score = 0.5

            return label, score

    # 2. Policy fallback
    if use_policy_fallback:
        analysis = getattr(parent, "analysis", None)
        if analysis is not None:
            policy = analysis.get("policy")
            if policy is not None and len(policy) > 0:
                root = getattr(node, "root", None)
                board_size = getattr(root, "board_size", (19, 19)) if root else (19, 19)
                return assess_difficulty_from_policy(list(policy), board_size=board_size)

    return PositionDifficulty.UNKNOWN, None


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================


def compute_difficulty_metrics(
    candidates: list[dict[str, Any]],
    root_visits: int | None = None,
    include_debug: bool = False,
    root_info: dict[str, Any] | None = None,
) -> DifficultyMetrics:
    """局面の難易度メトリクスを計算。

    scoreLead 欠損時も UNKNOWN 扱い。

    Args:
        candidates: KataGo moveInfos（未ソート可）
        root_visits: ルートの探索数（信頼性判定用）。
                     None の場合は unreliable 扱い。
        include_debug: デバッグ情報を含めるか（デフォルト False）
        root_info: KataGo rootInfo（Phase 154: shorttermScoreError などの error 系）

    Returns:
        DifficultyMetrics インスタンス。
        candidates が空/None、正規化不可、またはscoreLead欠損の場合は
        DIFFICULTY_UNKNOWN を返す。
    """
    # 欠損データチェック
    if not candidates:
        return DIFFICULTY_UNKNOWN

    # 入力の正規化（order 欠損時は UNKNOWN）
    normalized = normalize_candidates(candidates)
    if normalized is None:
        return DIFFICULTY_UNKNOWN

    # 信頼性チェック（フォールバック係数なし）
    is_reliable, reliability_reason = determine_reliability(root_visits, len(normalized))

    # 各成分の計算
    policy, policy_debug = compute_policy_difficulty(normalized, include_debug)
    transition, transition_debug = compute_transition_difficulty(normalized, include_debug)
    state, state_debug = compute_state_difficulty(normalized, include_debug)

    # Phase 154: KataGo error / LCB 系の追加指標
    error_pressure, error_pressure_debug = compute_error_pressure(normalized, root_info, include_debug)
    lcb_gap, lcb_gap_debug = compute_lcb_gap(normalized, include_debug)

    # scoreLead 欠損時は UNKNOWN（policy/transition が None の場合）
    if policy is None or transition is None:
        return DIFFICULTY_UNKNOWN

    # overall 合成（max を使用）
    overall = max(policy, transition)

    # unreliable の場合は overall を減衰
    reliability_scale = 1.0 if is_reliable else 0.7
    overall *= reliability_scale

    # Phase 154: KataGo error / LCB 系の加成（KataGo の不確実性を難易度に加味）
    if error_pressure is not None:
        overall += ERROR_PRESSURE_WEIGHT * error_pressure
    if lcb_gap is not None:
        overall += LCB_GAP_WEIGHT * lcb_gap
    overall = max(0.0, min(1.0, overall))

    # デバッグ情報の集約
    debug_factors = None
    if include_debug:
        debug_factors = {
            "policy": policy_debug,
            "transition": transition_debug,
            "state": state_debug,
            "error_pressure": error_pressure_debug,
            "lcb_gap": lcb_gap_debug,
            "reliability": {
                "root_visits": root_visits,
                "candidate_count": len(normalized),
                "is_reliable": is_reliable,
                "reason": reliability_reason,
                "scale": reliability_scale,
            },
            "overall_method": (
                "max(policy, transition) * reliability_scale"
                " + ERROR_PRESSURE_WEIGHT * error_pressure"
                " + LCB_GAP_WEIGHT * lcb_gap"
            ),
        }

    return DifficultyMetrics(
        policy_difficulty=policy,
        transition_difficulty=transition,
        state_difficulty=state,
        overall_difficulty=overall,
        error_pressure=error_pressure,
        lcb_gap=lcb_gap,
        is_reliable=is_reliable,
        is_unknown=False,
        debug_factors=debug_factors,
    )


def extract_difficult_positions(
    nodes: list[GameNode],
    limit: int = DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    min_move_number: int = DEFAULT_MIN_MOVE_NUMBER,
    exclude_unreliable: bool = False,
    include_debug: bool = False,
) -> list[tuple[int, GameNode, DifficultyMetrics]]:
    """複数局面から難所候補を抽出。

    exclude_unreliable=False がデフォルト（unreliable も含めて結果を返す）。

    Args:
        nodes: 解析済み GameNode リスト
        limit: 抽出する最大局面数
        min_move_number: この手数以降のみ対象（序盤を除外）
        exclude_unreliable: 信頼性の低い局面を除外するか（デフォルト False）
        include_debug: デバッグ情報を含めるか

    Returns:
        (move_number, GameNode, DifficultyMetrics) のリスト（overall降順）。
        同じ overall の場合は move_number 昇順（早い手を優先）。
    """
    results = []
    unknown_count = 0
    unreliable_count = 0

    for node in nodes:
        move_number = node.move_number if hasattr(node, "move_number") else 0

        if move_number < min_move_number:
            continue

        candidates, root_visits, root_info = get_candidates_from_node(node)
        metrics = compute_difficulty_metrics(candidates, root_visits, include_debug, root_info)

        # is_unknown フラグで判定（`is` 比較より堅牢）
        if metrics.is_unknown:
            unknown_count += 1
            continue

        if not metrics.is_reliable:
            unreliable_count += 1
            if exclude_unreliable:
                continue

        results.append((move_number, node, metrics))

    # テレメトリ出力（デバッグ支援）
    total_processed = len(nodes)
    _logger.debug(
        f"extract_difficult_positions: total={total_processed}, "
        f"unknown={unknown_count}, unreliable={unreliable_count}, "
        f"valid={len(results)}, limit={limit}"
    )

    # overall 降順 → move_number 昇順（タイブレーク）
    results.sort(key=lambda x: (-x[2].overall_difficulty, x[0]))

    return results[:limit]


def difficulty_metrics_from_node(node: GameNode) -> DifficultyMetrics:
    """GameNode から難易度メトリクスを計算。

    Public API: GUIから呼び出す用。内部でget_candidates_from_nodeを使用。

    Args:
        node: 解析済み GameNode

    Returns:
        DifficultyMetrics。解析なしの場合は DIFFICULTY_UNKNOWN。
    """
    candidates, root_visits, root_info = get_candidates_from_node(node)
    if not candidates:
        return DIFFICULTY_UNKNOWN
    return compute_difficulty_metrics(candidates, root_visits, root_info=root_info)
