"""
katrain.core.analysis.logic - 計算ロジック

このモジュールには全ての計算関数が含まれます:
- 損失計算（compute_canonical_loss, classify_mistake）
- スナップショット生成（snapshot_from_nodes, snapshot_from_game）
- 重要度計算（compute_importance_for_moves, pick_important_moves）
- 難易度評価（assess_position_difficulty_from_parent）
- その他の分析関数
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from typing import (
    TYPE_CHECKING,
    Any,
)

from katrain.core.analysis.models import (
    _CONFIDENCE_THRESHOLDS,
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    DEFAULT_SKILL_PRESET,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_UNKNOWN,
    MIN_COVERAGE_MOVES,
    POLICY_GAP_MAX,
    PRESET_ORDER,
    PV_FILTER_CONFIGS,
    RELIABILITY_RATIO,
    RELIABILITY_VISITS_THRESHOLD,
    SKILL_PRESETS,
    SKILL_TO_PV_FILTER,
    TRANSITION_DROP_MAX,
    URGENT_MISS_CONFIGS,
    VALID_REASON_TAGS,
    AutoConfidence,
    AutoRecommendation,
    ConfidenceLevel,
    DifficultyMetrics,
    EvalSnapshot,
    MistakeStreak,
    MoveEval,
    PhaseMistakeStats,
    PositionDifficulty,
    PVFilterConfig,
    ReliabilityStats,
    SkillEstimation,
    SkillPreset,
    UrgentMissConfig,
    get_canonical_loss_from_move,
)

if TYPE_CHECKING:
    from katrain.core.game_node import GameNode
else:
    GameNode = Any


# =============================================================================
# Skill preset helpers
# =============================================================================


def get_skill_preset(name: str) -> SkillPreset:
    """Return a skill preset, falling back to standard when unknown."""
    return SKILL_PRESETS.get(name, SKILL_PRESETS[DEFAULT_SKILL_PRESET])


def get_urgent_miss_config(skill_preset: str) -> UrgentMissConfig:
    """Return urgent miss detection config for the given skill preset."""
    return URGENT_MISS_CONFIGS.get(skill_preset, URGENT_MISS_CONFIGS[DEFAULT_SKILL_PRESET])


# =============================================================================
# Auto-strictness recommendation
# =============================================================================


def _distance_from_range(value: int, target_range: tuple[int, int]) -> int:
    """Calculate distance from target range (0 if within range)."""
    low, high = target_range
    if value < low:
        return low - value
    elif value > high:
        return value - high
    return 0


def recommend_auto_strictness(
    moves: list[MoveEval],
    *,
    game_count: int = 1,
    reliability_pct: float | None = None,
    target_blunder_per_game: tuple[int, int] = (3, 10),
    target_important_per_game: tuple[int, int] = (10, 30),
    reliability_threshold: float = 20.0,
) -> AutoRecommendation:
    """
    Recommend optimal strictness preset based on move statistics.

    This is NOT rank estimation - it finds the preset that yields a
    reasonable density of mistakes for review.

    Args:
        moves: List of MoveEval for the focus player
        game_count: Number of games included (1 for Karte, N for Player Summary)
        reliability_pct: Reliability percentage (if None, computed from moves)
        target_blunder_per_game: Target blunder count range per game
        target_important_per_game: Target important (mistake+blunder) count range per game
        reliability_threshold: Minimum reliability % to provide confident recommendation

    Returns:
        AutoRecommendation with preset name, confidence, counts, and score
    """
    # Compute reliability if not provided
    if reliability_pct is None:
        stats = compute_reliability_stats(moves)
        reliability_pct = stats.reliability_pct

    # Scale target ranges by game count
    blunder_range = (target_blunder_per_game[0] * game_count, target_blunder_per_game[1] * game_count)
    important_range = (target_important_per_game[0] * game_count, target_important_per_game[1] * game_count)

    # Evaluate each preset
    results: list[tuple[str, int, int, int]] = []  # (preset_name, score, blunders, important)
    for preset_name in PRESET_ORDER:
        preset = SKILL_PRESETS[preset_name]
        t1, t2, t3 = preset.score_thresholds

        # Use canonical loss: max(0, score_loss)
        blunders = sum(1 for m in moves if max(0.0, m.score_loss or 0.0) >= t3)
        important = sum(1 for m in moves if max(0.0, m.score_loss or 0.0) >= t2)

        # Calculate distance score (weight blunders more than important)
        b_score = _distance_from_range(blunders, blunder_range) * 2
        i_score = _distance_from_range(important, important_range) * 1
        total_score = b_score + i_score

        results.append((preset_name, total_score, blunders, important))

    # Sort by score, then by distance from "standard" (index 2) for tie-breaking
    # standard=0, advanced/beginner=1, pro/relaxed=2
    standard_idx = PRESET_ORDER.index("standard")
    results.sort(key=lambda x: (x[1], abs(PRESET_ORDER.index(x[0]) - standard_idx)))
    best_preset, best_score, best_blunders, best_important = results[0]

    # Reliability gate: if low reliability, force standard with LOW confidence
    if reliability_pct < reliability_threshold:
        # Still report counts using standard preset
        std_preset = SKILL_PRESETS["standard"]
        t2, t3 = std_preset.score_thresholds[1], std_preset.score_thresholds[2]
        std_blunders = sum(1 for m in moves if max(0.0, m.score_loss or 0.0) >= t3)
        std_important = sum(1 for m in moves if max(0.0, m.score_loss or 0.0) >= t2)

        return AutoRecommendation(
            recommended_preset="standard",
            confidence=AutoConfidence.LOW,
            blunder_count=std_blunders,
            important_count=std_important,
            score=best_score,
            reason=f"Low reliability ({reliability_pct:.1f}%)",
        )

    # Determine confidence based on score
    if best_score == 0:
        conf = AutoConfidence.HIGH
    elif best_score <= 5:
        conf = AutoConfidence.MEDIUM
    else:
        conf = AutoConfidence.LOW

    return AutoRecommendation(
        recommended_preset=best_preset,
        confidence=conf,
        blunder_count=best_blunders,
        important_count=best_important,
        score=best_score,
        reason=f"blunder={best_blunders}, important={best_important}",
    )


# =============================================================================
# Reason tag validation
# =============================================================================


def validate_reason_tag(tag: str) -> bool:
    """Check if a reason tag is defined in REASON_TAG_LABELS.

    Args:
        tag: The reason tag to validate

    Returns:
        True if the tag is defined, False otherwise
    """
    return tag in VALID_REASON_TAGS


# =============================================================================
# GameNode bridge
# =============================================================================


def move_eval_from_node(node: GameNode) -> MoveEval:
    """
    KaTrain の GameNode 1 個から MoveEval を生成する。

    - GameNode.comment() 等の文字列には依存せず、
      数値的な評価値だけを見るようにする。
    - before/after/delta は snapshot_from_nodes 側で埋める。
    """
    move = getattr(node, "move", None)
    player = getattr(move, "player", None)
    gtp = move.gtp() if move is not None and hasattr(move, "gtp") else None

    score = getattr(node, "score", None)
    winrate = getattr(node, "winrate", None)
    points_lost = getattr(node, "points_lost", None)
    realized_points_lost = getattr(node, "parent_realized_points_lost", None)
    root_visits = getattr(node, "root_visits", 0) or 0

    # Position difficulty 計算（親ノードの候補手から判定）
    difficulty, difficulty_score = assess_position_difficulty_from_parent(node)

    # move_number の取得
    _move_number = getattr(node, "depth", None)
    if _move_number is None:
        _move_number = getattr(node, "move_number", 0) or 0

    return MoveEval(
        move_number=_move_number,
        player=player,
        gtp=gtp,
        score_before=None,
        score_after=score,
        delta_score=None,
        winrate_before=None,
        winrate_after=winrate,
        delta_winrate=None,
        points_lost=points_lost,
        realized_points_lost=realized_points_lost,
        root_visits=int(root_visits),
        position_difficulty=difficulty,
        position_difficulty_score=difficulty_score,
    )


# =============================================================================
# Reliability functions (helpers extracted to logic_importance.py)
# =============================================================================

from katrain.core.analysis.logic_importance import (
    get_difficulty_modifier,
    get_reliability_scale,
)


def compute_effective_threshold(
    target_visits: int | None = None,
    max_threshold: int = RELIABILITY_VISITS_THRESHOLD,
    ratio: float = RELIABILITY_RATIO,
) -> int:
    """Compute effective reliability threshold based on target visits.

    Formula: max(1, min(max_threshold, round(target_visits * ratio)))

    When target_visits=100 and ratio=0.9: threshold=90
    When target_visits=300 and ratio=0.9: threshold=200 (capped)
    When target_visits=None or <=0: threshold=max_threshold (default 200)

    Args:
        target_visits: Configured/selected visits value (or None)
        max_threshold: Maximum threshold cap (default: 200)
        ratio: Fraction of target_visits to use (default: 0.9)

    Returns:
        Effective threshold for reliability determination.
    """
    if target_visits is not None and target_visits > 0:
        relative = max(1, round(target_visits * ratio))
        return min(max_threshold, relative)
    return max_threshold


def is_reliable_from_visits(
    root_visits: int,
    *,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
    target_visits: int | None = None,
) -> bool:
    """
    visits のみを根拠にした簡易信頼度判定。

    - threshold 未満は False（保守的）。
    - target_visits が指定された場合、effective threshold を使用。
    """
    effective = compute_effective_threshold(target_visits, threshold)
    return int(root_visits or 0) >= effective


def compute_reliability_stats(
    moves: Iterable[MoveEval],
    *,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
    target_visits: int | None = None,
) -> ReliabilityStats:
    """
    Compute reliability statistics for a collection of moves.

    Args:
        moves: Iterable of MoveEval objects
        threshold: Max visits threshold for reliability (default: RELIABILITY_VISITS_THRESHOLD=200)
        target_visits: Target/configured visits (for relative threshold calculation)

    Returns:
        ReliabilityStats with counts, percentages, and effective_threshold
    """
    effective = compute_effective_threshold(target_visits, threshold)
    stats = ReliabilityStats()
    stats.effective_threshold = effective

    for m in moves:
        stats.total_moves += 1
        visits = m.root_visits or 0

        if visits == 0:
            stats.zero_visits_count += 1
            stats.low_confidence_count += 1
        elif visits >= effective:
            stats.reliable_count += 1
            stats.total_visits += visits
            stats.moves_with_visits += 1
        else:
            stats.low_confidence_count += 1
            stats.total_visits += visits
            stats.moves_with_visits += 1

        # Track max visits
        if visits > stats.max_visits:
            stats.max_visits = visits

    return stats


# =============================================================================
# Confidence level
# =============================================================================


def compute_confidence_level(
    moves: Iterable[MoveEval],
    *,
    min_coverage: int = MIN_COVERAGE_MOVES,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
) -> ConfidenceLevel:
    """Compute confidence level for a set of moves.

    The confidence level determines how much trust we can place in the analysis
    results. It affects section visibility and wording in output.

    Args:
        moves: Iterable of MoveEval objects
        min_coverage: Minimum moves_with_visits required (default: 5)
        threshold: Visits threshold for reliability (default: RELIABILITY_VISITS_THRESHOLD)

    Returns:
        ConfidenceLevel (HIGH, MEDIUM, or LOW)

    Algorithm:
        1. If moves_with_visits < min_coverage: return LOW (coverage guard)
        2. HIGH if: (reliability_pct >= 50% OR avg_visits >= 400)
        3. MEDIUM if: (reliability_pct >= 30% OR avg_visits >= 150)
        4. Otherwise: LOW
    """
    stats = compute_reliability_stats(moves, threshold=threshold)

    # Coverage guard: too few analyzed moves = LOW
    if stats.moves_with_visits < min_coverage:
        return ConfidenceLevel.LOW

    reliability = stats.reliability_pct
    avg_visits = stats.avg_visits

    # HIGH: reliability >= 50% OR avg_visits >= 400
    if (
        reliability >= _CONFIDENCE_THRESHOLDS["high_reliability_pct"]
        or avg_visits >= _CONFIDENCE_THRESHOLDS["high_avg_visits"]
    ):
        return ConfidenceLevel.HIGH

    # MEDIUM: reliability >= 30% OR avg_visits >= 150
    if (
        reliability >= _CONFIDENCE_THRESHOLDS["medium_reliability_pct"]
        or avg_visits >= _CONFIDENCE_THRESHOLDS["medium_avg_visits"]
    ):
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW


# =============================================================================
# Phase thresholds
# =============================================================================


def get_phase_thresholds(board_size: int = 19) -> tuple[int, int]:
    """
    Get phase classification thresholds for a given board size.

    Args:
        board_size: Board size (9, 13, 19, etc.)

    Returns:
        Tuple of (opening_end, middle_end) move numbers.
    """
    thresholds = {
        9: (15, 50),
        13: (30, 100),
        19: (50, 200),
    }
    return thresholds.get(board_size, (50, 200))


def classify_game_phase(move_number: int, board_size: int = 19) -> str:
    """
    手数と盤サイズから対局のフェーズを判定する

    Args:
        move_number: 手数
        board_size: 盤サイズ（9, 13, 19 など）

    Returns:
        "opening" / "middle" / "yose"
    """
    thresholds = {
        9: (15, 50),
        13: (30, 100),
        19: (50, 200),
    }
    opening_end, middle_end = thresholds.get(board_size, (50, 200))

    if move_number < opening_end:
        return "opening"
    elif move_number < middle_end:
        return "middle"
    else:
        return "yose"


# =============================================================================
# Position difficulty assessment
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
    good_rel_threshold: float = 1.0,
    near_rel_threshold: float = 2.0,
    use_policy_fallback: bool = True,
) -> tuple[PositionDifficulty | None, float | None]:
    """
    親ノードの candidate_moves から局面難易度をざっくり評価する。
    """
    parent = getattr(node, "parent", None)
    if parent is None:
        return None, None

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
                label = PositionDifficulty.ONLY_MOVE
                score = 1.0
            elif n_good <= 2:
                label = PositionDifficulty.HARD
                score = 0.8
            elif n_good >= 4 or n_near >= 6:
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
# Loss calculation (extracted to logic_loss.py, re-exported for compatibility)
# =============================================================================

from katrain.core.analysis.logic_loss import (
    classify_mistake,
    compute_canonical_loss,
    compute_loss_from_delta,
)

# =============================================================================
# Snapshot creation
# =============================================================================


def snapshot_from_nodes(nodes: Iterable[GameNode]) -> EvalSnapshot:
    """
    任意の GameNode 群から EvalSnapshot を作成するユーティリティ。
    """
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

    node = root

    while True:
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


# =============================================================================
# Importance calculation (extracted to logic_importance.py, re-exported for compatibility)
# =============================================================================

from katrain.core.analysis.logic_importance import (
    compute_importance_for_moves,
    pick_important_moves,
)

# =============================================================================
# Skill estimation
# =============================================================================


def estimate_skill_level_from_tags(reason_tags_counts: dict[str, int], total_important_moves: int) -> SkillEstimation:
    """
    理由タグ分布から棋力を推定（Phase 13）
    """
    if total_important_moves < 5:
        return SkillEstimation(
            estimated_level="unknown", confidence=0.0, reason="重要局面数が不足（< 5手）", metrics={}
        )

    heavy_loss_count = reason_tags_counts.get("heavy_loss", 0)
    reading_failure_count = reason_tags_counts.get("reading_failure", 0)

    heavy_loss_rate = heavy_loss_count / total_important_moves
    reading_failure_rate = reading_failure_count / total_important_moves

    metrics = {
        "heavy_loss_rate": heavy_loss_rate,
        "reading_failure_rate": reading_failure_rate,
        "total_important_moves": float(total_important_moves),
    }

    if heavy_loss_rate >= 0.4:
        return SkillEstimation(
            estimated_level="beginner",
            confidence=min(0.9, heavy_loss_rate * 1.5),
            reason=f"大損失の出現率が高い（{heavy_loss_rate:.1%}）→ 大局観・判断力を強化する段階",
            metrics=metrics,
        )

    if heavy_loss_rate < 0.15 and reading_failure_rate < 0.1:
        confidence = 1.0 - (heavy_loss_rate + reading_failure_rate) * 2
        return SkillEstimation(
            estimated_level="advanced",
            confidence=min(0.9, max(0.5, confidence)),
            reason=f"大損失・読み抜けともに少ない（大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%}）→ 高段者レベル",
            metrics=metrics,
        )

    if reading_failure_rate >= 0.15:
        return SkillEstimation(
            estimated_level="standard",
            confidence=min(0.9, reading_failure_rate * 2),
            reason=f"読み抜けの出現率が高い（{reading_failure_rate:.1%}）→ 戦術的な読み・形判断を強化する段階",
            metrics=metrics,
        )

    confidence = 0.5
    return SkillEstimation(
        estimated_level="standard",
        confidence=confidence,
        reason=f"大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%} → 標準的な有段者レベル",
        metrics=metrics,
    )


# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


def get_pv_filter_config(
    pv_filter_level: str,
    skill_preset: str = DEFAULT_SKILL_PRESET,
) -> PVFilterConfig | None:
    """
    PVフィルタ設定を取得する。

    Args:
        pv_filter_level: "off", "weak", "medium", "strong", "auto"
        skill_preset: AUTOモード時に参照するskill_preset名

    Returns:
        PVFilterConfig または None（OFFの場合）
    """
    level = pv_filter_level.lower()

    if level == "off":
        return None

    if level == "auto":
        # skill_presetからpv_filter_levelを決定
        mapped_level = SKILL_TO_PV_FILTER.get(skill_preset, "medium")
        return PV_FILTER_CONFIGS.get(mapped_level)

    return PV_FILTER_CONFIGS.get(level)


def filter_candidates_by_pv_complexity(
    candidates: list[dict[str, Any]],
    config: PVFilterConfig,
) -> list[dict[str, Any]]:
    """
    候補手リストをPV複雑度でフィルタリングする（Phase 11）。

    データ仕様:
    - pv: 常にList[str]で存在（GTP座標の着手列）
    - pointsLost: 常に存在（game_node.pyで計算追加）
    - order: 常に存在（欠損時はADDITIONAL_MOVE_ORDER=999）

    上限ルール:
    - max_candidates はフィルタ通過手の上限（best_move は別枠）
    - best_move（order=0）は上限に含めず常に表示

    Args:
        candidates: candidate_moves から取得した候補手リスト
        config: PVFilterConfig（閾値設定）

    Returns:
        フィルタ済みの候補手リスト
    """
    if not candidates:
        return []

    # Step 1: order=0（最善手）を特定
    best_move = None
    for c in candidates:
        if c.get("order", 999) == 0:
            best_move = c
            break

    # Step 2: フィルタ条件でチェック（best_move以外）
    filtered = []
    for c in candidates:
        if c is best_move:
            continue  # best_moveは別枠で処理
        points_lost = c.get("pointsLost", 0.0)
        pv = c.get("pv", [])
        pv_length = len(pv) if pv else 0

        # 条件: 損失が閾値以下 AND PV長が閾値以下
        if points_lost <= config.max_points_lost and pv_length <= config.max_pv_length:
            filtered.append(c)

    # Step 3: max_candidates 制限（order順でカット、best_move除外済み）
    filtered = sorted(filtered, key=lambda c: c.get("order", 999))
    filtered = filtered[: config.max_candidates]

    # Step 4: best_moveを先頭に挿入（別枠、上限外）
    if best_move:
        filtered.insert(0, best_move)

    return filtered


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================

_difficulty_logger = logging.getLogger(__name__)


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


def compute_difficulty_metrics(
    candidates: list[dict[str, Any]],
    root_visits: int | None = None,
    include_debug: bool = False,
) -> DifficultyMetrics:
    """局面の難易度メトリクスを計算。

    scoreLead 欠損時も UNKNOWN 扱い。

    Args:
        candidates: KataGo moveInfos（未ソート可）
        root_visits: ルートの探索数（信頼性判定用）。
                     None の場合は unreliable 扱い。
        include_debug: デバッグ情報を含めるか（デフォルト False）

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

    # scoreLead 欠損時は UNKNOWN（policy/transition が None の場合）
    if policy is None or transition is None:
        return DIFFICULTY_UNKNOWN

    # overall 合成（max を使用）
    overall = max(policy, transition)

    # unreliable の場合は overall を減衰
    reliability_scale = 1.0 if is_reliable else 0.7
    overall *= reliability_scale

    # デバッグ情報の集約
    debug_factors = None
    if include_debug:
        debug_factors = {
            "policy": policy_debug,
            "transition": transition_debug,
            "state": state_debug,
            "reliability": {
                "root_visits": root_visits,
                "candidate_count": len(normalized),
                "is_reliable": is_reliable,
                "reason": reliability_reason,
                "scale": reliability_scale,
            },
            "overall_method": "max(policy, transition)",
        }

    return DifficultyMetrics(
        policy_difficulty=policy,
        transition_difficulty=transition,
        state_difficulty=state,
        overall_difficulty=overall,
        is_reliable=is_reliable,
        is_unknown=False,
        debug_factors=debug_factors,
    )


def _get_candidates_from_node(node: GameNode) -> tuple[list[dict[str, Any]], int | None]:
    """GameNode から候補手リストと root_visits を取得。

    _get_root_visits() を使用して複数キーに対応。

    Args:
        node: 解析済み GameNode

    Returns:
        (candidates, root_visits) タプル。
        解析データがない場合は ([], None)。

    Note:
        candidate_moves プロパティは既にソート済み・拡張済みを返すが、
        compute_difficulty_metrics 内で再度 _normalize_candidates を呼ぶため
        二重ソートになる。ただし order フィールドがあれば同じ結果になるので問題なし。
    """
    if not node.analysis_exists:
        return [], None

    # candidate_moves プロパティはソート済み・拡張済みを返す
    candidates = node.candidate_moves

    # _get_root_visits() で複数キーに対応
    root_visits = _get_root_visits(node.analysis)

    return candidates, root_visits


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

        candidates, root_visits = _get_candidates_from_node(node)
        metrics = compute_difficulty_metrics(candidates, root_visits, include_debug)

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
    candidates, root_visits = _get_candidates_from_node(node)
    if not candidates:
        return DIFFICULTY_UNKNOWN
    return compute_difficulty_metrics(candidates, root_visits)


# =============================================================================
# __all__
# =============================================================================


__all__ = [
    # Skill preset helpers
    "get_skill_preset",
    "get_urgent_miss_config",
    # Auto-strictness
    "_distance_from_range",
    "recommend_auto_strictness",
    # Reason tag validation
    "validate_reason_tag",
    # GameNode bridge
    "move_eval_from_node",
    # Reliability functions
    "get_difficulty_modifier",
    "get_reliability_scale",
    "is_reliable_from_visits",
    "compute_reliability_stats",
    # Confidence level
    "compute_confidence_level",
    # Phase functions
    "get_phase_thresholds",
    "classify_game_phase",
    # Position difficulty
    "_assess_difficulty_from_policy",
    "assess_position_difficulty_from_parent",
    # Loss calculation
    "compute_loss_from_delta",
    "compute_canonical_loss",
    "classify_mistake",
    # Snapshot
    "snapshot_from_nodes",
    "iter_main_branch_nodes",
    "snapshot_from_game",
    # Phase mistake stats
    "aggregate_phase_mistake_stats",
    # Mistake streaks
    "detect_mistake_streaks",
    # Importance
    "compute_importance_for_moves",
    "pick_important_moves",
    # Skill estimation
    "estimate_skill_level_from_tags",
    # PV Filter (Phase 11)
    "get_pv_filter_config",
    "filter_candidates_by_pv_complexity",
    # Difficulty Metrics (Phase 12)
    "_normalize_candidates",
    "_get_root_visits",
    "_determine_reliability",
    "_compute_policy_difficulty",
    "_compute_transition_difficulty",
    "_compute_state_difficulty",
    "compute_difficulty_metrics",
    "_get_candidates_from_node",
    "extract_difficult_positions",
    "difficulty_metrics_from_node",
]
