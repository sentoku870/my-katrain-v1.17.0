"""Position difficulty and difficulty metrics computation.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- _assess_difficulty_from_policy: Policy entropy fallback
- assess_position_difficulty_from_parent: Main entry point for difficulty assessment
- _normalize_candidates: Normalize candidate list (sort by order)
- _get_root_visits: Extract root_visits from various analysis formats
- _determine_reliability: Reliability check for difficulty computation
- _compute_policy_difficulty: Policy difficulty (competition between top moves)
- _compute_transition_difficulty: Transition difficulty (drop from best to second)
- _compute_state_difficulty: State difficulty (v1: always 0.0)
- compute_difficulty_metrics: Aggregate difficulty into DifficultyMetrics
- _get_candidates_from_node: Extract candidates and root_visits from GameNode
- extract_difficult_positions: Find difficult positions in a move list
- difficulty_metrics_from_node: Public API for GUI to compute difficulty
"""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

from katrain.core.analysis.models import (
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_UNKNOWN,
    ERROR_PRESSURE_WEIGHT,
    LCB_GAP_MAX,
    LCB_GAP_WEIGHT,
    POLICY_GAP_MAX,
    SHORTTERM_SCORE_ERROR_MAX,
    TRANSITION_DROP_MAX,
    DifficultyMetrics,
    PositionDifficulty,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode

_difficulty_logger = logging.getLogger(__name__)


# =============================================================================
# Position difficulty assessment (heuristic)
# =============================================================================


def _assess_difficulty_from_policy(
    policy: list[float],
    *,
    board_size: Any = 19,
    entropy_easy_threshold: float = 2.5,
    entropy_hard_threshold: float = 1.0,
    top5_easy_threshold: float = 0.5,
    top5_hard_threshold: float = 0.9,
) -> tuple[PositionDifficulty, float]:
    """
    Policy entropy から局面難易度を推定する（fallback用）。
    """
    if not policy:
        return PositionDifficulty.UNKNOWN, 0.5

    # Handle both int and tuple board_size
    board_points = board_size[0] * board_size[1] if isinstance(board_size, tuple) else board_size * board_size

    # Safety check
    if board_points < 9:
        board_points = 361

    REF_BOARD_POINTS = 361
    ref_max_entropy = math.log(REF_BOARD_POINTS)
    current_max_entropy = math.log(board_points + 1)
    scale_factor = current_max_entropy / ref_max_entropy

    adjusted_easy = entropy_easy_threshold * scale_factor
    adjusted_hard = entropy_hard_threshold * scale_factor

    # Policy entropy 計算
    entropy = 0.0
    for p in policy:
        if p > 0:
            entropy -= p * math.log(p)

    # Top-5 cumulative mass
    sorted_probs = sorted(policy, reverse=True)
    top5_mass = sum(sorted_probs[:5])

    if entropy >= adjusted_easy and top5_mass <= top5_easy_threshold:
        return PositionDifficulty.EASY, 0.2
    elif entropy <= adjusted_hard or top5_mass >= top5_hard_threshold:
        if sorted_probs[0] >= 0.8:
            return PositionDifficulty.ONLY_MOVE, 1.0
        return PositionDifficulty.HARD, 0.8
    elif entropy >= (adjusted_easy + adjusted_hard) / 2:
        return PositionDifficulty.EASY, 0.3
    else:
        return PositionDifficulty.NORMAL, 0.5


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
                return _assess_difficulty_from_policy(list(policy), board_size=board_size)

    return PositionDifficulty.UNKNOWN, None


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================


def _normalize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """候補手リストを正規化（ソート + バリデーション）。

    order 欠損時は UNKNOWN（手番依存のソートを回避）。

    Args:
        candidates: KataGo moveInfos（未ソートの可能性あり）

    Returns:
        order フィールドでソート済みのリスト。
        - order がある → order でソート
        - order がない → None（UNKNOWN扱い）

    Note:
        scoreLead は BLACK 視点なので、WHITE 手番では降順が「最悪手順」になる。
        手番情報なしでは正しくソートできないため、order 欠損時は UNKNOWN 扱い。
    """
    if not candidates:
        return []

    # order フィールドの存在チェック
    has_order = all("order" in c for c in candidates)

    if has_order:
        # order でソート（0=最善）
        return sorted(candidates, key=lambda c: c.get("order", 999))

    # order がない場合は UNKNOWN（手番依存のソートを回避）
    return None


def _get_root_visits(analysis: dict[str, Any] | None) -> int | None:
    """analysis から root_visits を取得（複数キーに対応）。

    KaTrain/KataGo の複数フォーマットに対応。

    Args:
        analysis: GameNode.analysis（辞書または None）

    Returns:
        root_visits 値。取得できない場合は None。

    Note:
        優先順位:
        1. rootInfo.visits（KataGo 標準）
        2. root.visits（KaTrain 内部フォーマット）
        3. visits（直接参照、一部のカスタムフォーマット）
    """
    if not analysis:
        return None

    # KataGo 標準: rootInfo.visits
    root_info = analysis.get("rootInfo", {})
    if "visits" in root_info:
        visits_value = root_info.get("visits")
        return int(visits_value) if visits_value is not None else None

    # KaTrain 内部フォーマット: root.visits
    root = analysis.get("root", {})
    if "visits" in root:
        visits_value = root.get("visits")
        return int(visits_value) if visits_value is not None else None

    # 直接参照（一部のカスタムフォーマット対応）
    if "visits" in analysis:
        visits_value = analysis.get("visits")
        return int(visits_value) if visits_value is not None else None

    return None


def _determine_reliability(
    root_visits: int | None,
    candidate_count: int,
) -> tuple[bool, str]:
    """信頼性を判定。

    フォールバック係数なし、シンプルなルール。

    Args:
        root_visits: root_visits 値（None の場合は unreliable）
        candidate_count: 候補手の数

    Returns:
        (is_reliable, reason) タプル。
    """
    # root_visits が None の場合は unreliable
    if root_visits is None:
        return False, "root_visits_missing"

    # visits 不足
    if root_visits < DIFFICULTY_MIN_VISITS:
        return False, f"visits_insufficient ({root_visits} < {DIFFICULTY_MIN_VISITS})"

    # 候補不足
    if candidate_count < DIFFICULTY_MIN_CANDIDATES:
        return False, f"candidates_insufficient ({candidate_count} < {DIFFICULTY_MIN_CANDIDATES})"

    return True, "reliable"


def _compute_policy_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """候補手の拮抗度から Policy 難易度を計算。

    scoreLead 欠損時は None を返す（UNKNOWN 扱い）。

    Top1 と Top2 の scoreLead 差が小さいほど「迷いやすい」。
    差の絶対値を使用（scoreLead の符号は BLACK 視点だが、
    差を取れば手番に関係なく評価できる）。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。
        difficulty: 0-1 の難易度値。候補が拮抗しているほど高い。
                    scoreLead 欠損時は None。
    """
    if len(candidates) < 2:
        debug = {"reason": "insufficient_candidates", "count": len(candidates)} if include_debug else None
        return 0.0, debug

    # scoreLead を取得（存在しない場合は None）
    top1_score = candidates[0].get("scoreLead")
    top2_score = candidates[1].get("scoreLead")

    # None チェック → UNKNOWN 扱い
    if top1_score is None or top2_score is None:
        debug = {"reason": "missing_scoreLead"} if include_debug else None
        return None, debug

    # 差の絶対値を使用（符号に依存しない）
    gap = abs(top1_score - top2_score)

    # gap が 0 なら difficulty=1、POLICY_GAP_MAX 以上なら difficulty=0
    difficulty = max(0.0, min(1.0, 1.0 - gap / POLICY_GAP_MAX))

    debug = (
        {
            "top1_score": top1_score,
            "top2_score": top2_score,
            "gap": gap,
            "normalized": difficulty,
        }
        if include_debug
        else None
    )

    return difficulty, debug


def _compute_transition_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """評価の急落度から Transition 難易度を計算。

    scoreLead 欠損時は None を返す（UNKNOWN 扱い）。

    Top1 と Top2 の scoreLead 差が大きいほど「崩れやすい」。

    意味:
    - 最善手を逃すとどれだけ損するか
    - 差が大きい = 一手の選択が重要 = 崩れやすい

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。
        difficulty: 0-1 の難易度値。少し外すと急に悪化するほど高い。
                    scoreLead 欠損時は None。
    """
    if len(candidates) < 2:
        debug = {"reason": "insufficient_candidates", "count": len(candidates)} if include_debug else None
        return 0.0, debug

    top1_score = candidates[0].get("scoreLead")
    top2_score = candidates[1].get("scoreLead")

    # None チェック → UNKNOWN 扱い
    if top1_score is None or top2_score is None:
        debug = {"reason": "missing_scoreLead"} if include_debug else None
        return None, debug

    # Top1 と Top2 の差（絶対値）
    drop = abs(top1_score - top2_score)

    # drop が TRANSITION_DROP_MAX 以上なら difficulty=1
    difficulty = max(0.0, min(1.0, drop / TRANSITION_DROP_MAX))

    debug = (
        {
            "top1_score": top1_score,
            "top2_score": top2_score,
            "drop": drop,
            "normalized": difficulty,
        }
        if include_debug
        else None
    )

    return difficulty, debug


def _compute_state_difficulty(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float, dict[str, Any] | None]:
    """盤面の複雑さから State 難易度を計算。

    v1: 仕様書の「控えめに扱う」に従い、常に 0.0 を返す。
    将来の拡張で候補数・分岐多様性を考慮予定。

    Args:
        candidates: 正規化済み候補手リスト
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。v1 では常に (0.0, debug)。
    """
    debug = (
        {
            "v1_note": "state_difficulty disabled in v1",
            "candidate_count": len(candidates),
        }
        if include_debug
        else None
    )

    return 0.0, debug


# =============================================================================
# Phase 154: KataGo error / LCB 系の追加指標
# =============================================================================


def _compute_error_pressure(
    candidates: list[dict[str, Any]],
    root_info: dict[str, Any] | None = None,
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """KataGo 自身の短期 error から error_pressure を計算。

    shorttermScoreError を SHORTTERM_SCORE_ERROR_MAX で正規化。
    KataGo も読み切れない局面 = ユーザーも迷うはず、という仮説に基づく。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        root_info: KataGo rootInfo（shorttermScoreError, rawStdev などを含む）
        include_debug: デバッグ情報を含めるか

    Returns:
        (error_pressure, debug_info) タプル。
        error_pressure: 0-1、値が大きいほど KataGo も読み切れない。
                        shorttermScoreError 欠損時は None。
    """
    if not candidates:
        return None, {"reason": "no_candidates"} if include_debug else None

    ste: Any = None
    if isinstance(root_info, dict):
        ste = root_info.get("shorttermScoreError")

    if ste is None:
        return None, {"reason": "missing_shorttermScoreError"} if include_debug else None

    try:
        ste_val = float(ste)
    except (TypeError, ValueError):
        return None, {"reason": "invalid_shorttermScoreError"} if include_debug else None

    error_pressure = max(0.0, min(1.0, abs(ste_val) / SHORTTERM_SCORE_ERROR_MAX))

    debug = (
        {
            "shorttermScoreError": ste_val,
            "normalized": error_pressure,
        }
        if include_debug
        else None
    )

    return error_pressure, debug


def _compute_lcb_gap(
    candidates: list[dict[str, Any]],
    include_debug: bool = False,
) -> tuple[float | None, dict[str, Any] | None]:
    """最善手と次善手の LCB 差から lcb_gap を計算。

    lcb_gap が大きい = 最善手が他より明確に信頼できる（KataGo の自信）。
    小さい = 候補手が拮抗していてKataGoも自信がない。

    注: 現状は「KataGoの候補手信頼度差」として利用。
    絶対値が大きいほど「KataGoは明確に読み切っている」と解釈可能。

    Args:
        candidates: 正規化済み候補手リスト（order順）
        include_debug: デバッグ情報を含めるか

    Returns:
        (lcb_gap, debug_info) タプル。
        lcb_gap: 0-1、値が大きいほどKataGoの候補手信頼度差が大きい。
                 lcb 欠損時は None。
    """
    if len(candidates) < 2:
        return None, {"reason": "insufficient_candidates"} if include_debug else None

    top1 = candidates[0]
    top2 = candidates[1]
    if not isinstance(top1, dict) or not isinstance(top2, dict):
        return None, {"reason": "invalid_candidate_format"} if include_debug else None

    top1_lcb = top1.get("lcb")
    top2_lcb = top2.get("lcb")

    if top1_lcb is None or top2_lcb is None:
        return None, {"reason": "missing_lcb"} if include_debug else None

    try:
        top1_val = float(top1_lcb)
        top2_val = float(top2_lcb)
    except (TypeError, ValueError):
        return None, {"reason": "invalid_lcb"} if include_debug else None

    lcb_diff = abs(top1_val - top2_val)
    lcb_gap = max(0.0, min(1.0, lcb_diff / LCB_GAP_MAX))

    debug = (
        {
            "top1_lcb": top1_val,
            "top2_lcb": top2_val,
            "diff": lcb_diff,
            "normalized": lcb_gap,
        }
        if include_debug
        else None
    )

    return lcb_gap, debug


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
    normalized = _normalize_candidates(candidates)
    if normalized is None:
        return DIFFICULTY_UNKNOWN

    # 信頼性チェック（フォールバック係数なし）
    is_reliable, reliability_reason = _determine_reliability(root_visits, len(normalized))

    # 各成分の計算
    policy, policy_debug = _compute_policy_difficulty(normalized, include_debug)
    transition, transition_debug = _compute_transition_difficulty(normalized, include_debug)
    state, state_debug = _compute_state_difficulty(normalized, include_debug)

    # Phase 154: KataGo error / LCB 系の追加指標
    error_pressure, error_pressure_debug = _compute_error_pressure(normalized, root_info, include_debug)
    lcb_gap, lcb_gap_debug = _compute_lcb_gap(normalized, include_debug)

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


def _get_candidates_from_node(
    node: GameNode,
) -> tuple[list[dict[str, Any]], int | None, dict[str, Any] | None]:
    """GameNode から候補手リストと root_visits と rootInfo を取得。

    _get_root_visits() を使用して複数キーに対応。

    Args:
        node: 解析済み GameNode

    Returns:
        (candidates, root_visits, root_info) タプル。
        解析データがない場合は ([], None, None)。

    Note:
        candidate_moves プロパティは既にソート済み・拡張済みを返すが、
        compute_difficulty_metrics 内で再度 _normalize_candidates を呼ぶため
        二重ソートになる。ただし order フィールドがあれば同じ結果になるので問題なし。
    """
    if not node.analysis_exists:
        return [], None, None

    # candidate_moves プロパティはソート済み・拡張済みを返す
    candidates = node.candidate_moves

    # _get_root_visits() で複数キーに対応
    root_visits = _get_root_visits(node.analysis)

    # Phase 154: rootInfo も渡す（error 系指標の計算用）
    analysis = getattr(node, "analysis", None) or {}
    root_info = analysis.get("rootInfo") if isinstance(analysis, dict) else None
    if root_info is not None and not isinstance(root_info, dict):
        root_info = None

    return candidates, root_visits, root_info


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

        candidates, root_visits, root_info = _get_candidates_from_node(node)
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
    _difficulty_logger.debug(
        f"extract_difficult_positions: total={total_processed}, "
        f"unknown={unknown_count}, unreliable={unreliable_count}, "
        f"valid={len(results)}, limit={limit}"
    )

    # overall 降順 → move_number 昇順（タイブレーク）
    results.sort(key=lambda x: (-x[2].overall_difficulty, x[0]))

    return results[:limit]


def difficulty_metrics_from_node(node: GameNode) -> DifficultyMetrics:
    """GameNode から難易度メトリクスを計算。

    Public API: GUIから呼び出す用。内部で_get_candidates_from_nodeを使用。

    Args:
        node: 解析済み GameNode

    Returns:
        DifficultyMetrics。解析なしの場合は DIFFICULTY_UNKNOWN。
    """
    candidates, root_visits, root_info = _get_candidates_from_node(node)
    if not candidates:
        return DIFFICULTY_UNKNOWN
    return compute_difficulty_metrics(candidates, root_visits, root_info=root_info)
