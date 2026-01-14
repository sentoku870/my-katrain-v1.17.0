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
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from katrain.core.analysis.models import (
    AutoConfidence,
    AutoRecommendation,
    ConfidenceLevel,
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    DEFAULT_MIN_MOVE_NUMBER,
    DEFAULT_PV_FILTER_LEVEL,
    DEFAULT_QUIZ_ITEM_LIMIT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    DEFAULT_SKILL_PRESET,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    DIFFICULTY_UNKNOWN,
    DifficultyMetrics,
    EvalSnapshot,
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    ImportantMoveSettings,
    MistakeCategory,
    MistakeStreak,
    MoveEval,
    PhaseMistakeStats,
    POLICY_GAP_MAX,
    PositionDifficulty,
    PRESET_ORDER,
    PV_FILTER_CONFIGS,
    PVFilterConfig,
    PVFilterLevel,
    QuizItem,
    RELIABILITY_SCALE_THRESHOLDS,
    RELIABILITY_VISITS_THRESHOLD,
    ReliabilityStats,
    SCORE_THRESHOLDS,
    SKILL_PRESETS,
    SKILL_TO_PV_FILTER,
    SkillEstimation,
    SkillPreset,
    STREAK_START_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    TRANSITION_DROP_MAX,
    UrgentMissConfig,
    URGENT_MISS_CONFIGS,
    VALID_REASON_TAGS,
    WINRATE_THRESHOLDS,
    _CONFIDENCE_THRESHOLDS,
    MIN_COVERAGE_MOVES,
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


def _distance_from_range(value: int, target_range: Tuple[int, int]) -> int:
    """Calculate distance from target range (0 if within range)."""
    low, high = target_range
    if value < low:
        return low - value
    elif value > high:
        return value - high
    return 0


def recommend_auto_strictness(
    moves: List["MoveEval"],
    *,
    game_count: int = 1,
    reliability_pct: Optional[float] = None,
    target_blunder_per_game: Tuple[int, int] = (3, 10),
    target_important_per_game: Tuple[int, int] = (10, 30),
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
    blunder_range = (
        target_blunder_per_game[0] * game_count,
        target_blunder_per_game[1] * game_count
    )
    important_range = (
        target_important_per_game[0] * game_count,
        target_important_per_game[1] * game_count
    )

    # Evaluate each preset
    results: List[Tuple[str, int, int, int]] = []  # (preset_name, score, blunders, important)
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
            reason=f"Low reliability ({reliability_pct:.1f}%)"
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
        reason=f"blunder={best_blunders}, important={best_important}"
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
# Reliability functions
# =============================================================================


def get_difficulty_modifier(difficulty: Optional["PositionDifficulty"]) -> float:
    """
    Get the importance modifier based on position difficulty.

    - HARD: +1.0 (difficult positions have higher learning value)
    - ONLY_MOVE: -2.0 (no choices = low learning value)
    - EASY/NORMAL/UNKNOWN/None: 0.0 (no modifier)
    """
    if difficulty is None:
        return 0.0
    if difficulty == PositionDifficulty.HARD:
        return DIFFICULTY_MODIFIER_HARD
    if difficulty == PositionDifficulty.ONLY_MOVE:
        return DIFFICULTY_MODIFIER_ONLY_MOVE
    return 0.0


def get_reliability_scale(root_visits: int) -> float:
    """
    Get the reliability scale factor based on visit count.

    Returns a value between 0.3 and 1.0:
    - visits >= 500: 1.0 (full confidence)
    - visits >= 200: 0.8
    - visits >= 100: 0.5
    - visits < 100: 0.3 (low confidence)
    """
    visits = root_visits or 0
    for threshold, scale in RELIABILITY_SCALE_THRESHOLDS:
        if visits >= threshold:
            return scale
    return 0.3  # Default minimum


def is_reliable_from_visits(root_visits: int, *, threshold: int = RELIABILITY_VISITS_THRESHOLD) -> bool:
    """
    visits のみを根拠にした簡易信頼度判定。

    - threshold 未満は False（保守的）。
    """
    return int(root_visits or 0) >= threshold


def compute_reliability_stats(
    moves: Iterable[MoveEval],
    *,
    threshold: int = RELIABILITY_VISITS_THRESHOLD,
) -> ReliabilityStats:
    """
    Compute reliability statistics for a collection of moves.

    Args:
        moves: Iterable of MoveEval objects
        threshold: Visits threshold for reliability (default: RELIABILITY_VISITS_THRESHOLD=200)

    Returns:
        ReliabilityStats with counts and percentages
    """
    stats = ReliabilityStats()

    for m in moves:
        stats.total_moves += 1
        visits = m.root_visits or 0

        if visits == 0:
            stats.zero_visits_count += 1
            stats.low_confidence_count += 1
        elif visits >= threshold:
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


def get_phase_thresholds(board_size: int = 19) -> Tuple[int, int]:
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
    policy: List[float],
    *,
    board_size: Any = 19,
    entropy_easy_threshold: float = 2.5,
    entropy_hard_threshold: float = 1.0,
    top5_easy_threshold: float = 0.5,
    top5_hard_threshold: float = 0.9,
) -> Tuple[PositionDifficulty, float]:
    """
    Policy entropy から局面難易度を推定する（fallback用）。
    """
    if not policy:
        return PositionDifficulty.UNKNOWN, 0.5

    # Handle both int and tuple board_size
    if isinstance(board_size, tuple):
        board_points = board_size[0] * board_size[1]
    else:
        board_points = board_size * board_size

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
) -> Tuple[Optional[PositionDifficulty], Optional[float]]:
    """
    親ノードの candidate_moves から局面難易度をざっくり評価する。
    """
    parent = getattr(node, "parent", None)
    if parent is None:
        return None, None

    # 1. candidate_moves からの判定
    candidate_moves = getattr(parent, "candidate_moves", None)
    if candidate_moves is not None and len(candidate_moves) > 0:
        good_moves: List[float] = []
        near_moves: List[float] = []

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
# Loss calculation
# =============================================================================


def compute_loss_from_delta(
    delta_score: Optional[float],
    delta_winrate: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """
    手番視点の delta_score / delta_winrate から損失量 (>=0) を計算する。
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    if delta_score is not None:
        score_loss = max(0.0, -delta_score)

    if delta_winrate is not None:
        winrate_loss = max(0.0, -delta_winrate)

    return score_loss, winrate_loss


def compute_canonical_loss(
    points_lost: Optional[float],
    delta_score: Optional[float] = None,
    delta_winrate: Optional[float] = None,
    player: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """
    正準的な損失量 (>=0) を計算する。

    優先順位:
      1) points_lost が利用可能なら max(points_lost, 0) を使用
      2) delta_score/delta_winrate が利用可能ならフォールバック
    """
    score_loss: Optional[float] = None
    winrate_loss: Optional[float] = None

    # Primary: use points_lost if available
    if points_lost is not None:
        score_loss = max(0.0, points_lost)

    # Fallback: use delta with perspective correction
    if score_loss is None and delta_score is not None:
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        side_to_move_delta = player_sign * delta_score
        score_loss = max(0.0, -side_to_move_delta)

    # Winrate loss
    if delta_winrate is not None:
        player_sign = {"B": 1, "W": -1, None: 1}.get(player, 1)
        side_to_move_delta = player_sign * delta_winrate
        winrate_loss = max(0.0, -side_to_move_delta)

    return score_loss, winrate_loss


def classify_mistake(
    score_loss: Optional[float],
    winrate_loss: Optional[float],
    *,
    score_thresholds: Tuple[float, float, float] = SCORE_THRESHOLDS,
    winrate_thresholds: Tuple[float, float, float] = WINRATE_THRESHOLDS,
) -> MistakeCategory:
    """
    損失量から MistakeCategory を決定する。
    """
    if score_loss is not None:
        loss = max(score_loss, 0.0)
        t1, t2, t3 = score_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    if winrate_loss is not None:
        loss = max(winrate_loss, 0.0)
        t1, t2, t3 = winrate_thresholds
        if loss < t1:
            return MistakeCategory.GOOD
        if loss < t2:
            return MistakeCategory.INACCURACY
        if loss < t3:
            return MistakeCategory.MISTAKE
        return MistakeCategory.BLUNDER

    return MistakeCategory.GOOD


# =============================================================================
# Snapshot creation
# =============================================================================


def snapshot_from_nodes(nodes: Iterable[GameNode]) -> EvalSnapshot:
    """
    任意の GameNode 群から EvalSnapshot を作成するユーティリティ。
    """
    # GameNode と MoveEval のペアを保持
    node_evals: List[Tuple[GameNode, MoveEval]] = []
    node_list = list(nodes)

    # 解析済みSGFの場合、load_analysis() を呼び出し
    loaded_nodes: set = set()
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
    prev: Optional[MoveEval] = None
    for node, m in node_evals:
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
            yield node  # type: ignore[misc]

        children = getattr(node, "children", None)
        if not children:
            break

        main_children = [
            c for c in children if getattr(c, "is_mainline", False)
        ]
        if not main_children:
            main_children = [
                c for c in children if getattr(c, "is_main", False)
            ]

        next_node = main_children[0] if main_children else children[0]
        node = next_node


def snapshot_from_game(game: Any) -> EvalSnapshot:
    """
    Game 全体（メイン分岐）から EvalSnapshot を生成するヘルパー。
    """
    nodes_iter = iter_main_branch_nodes(game)
    return snapshot_from_nodes(nodes_iter)


# =============================================================================
# Quiz helpers
# =============================================================================


def quiz_items_from_snapshot(
    snapshot: EvalSnapshot,
    *,
    loss_threshold: float = DEFAULT_QUIZ_LOSS_THRESHOLD,
    limit: int = DEFAULT_QUIZ_ITEM_LIMIT,
    preset: Optional[str] = None,
) -> List[QuizItem]:
    """
    EvalSnapshot から「大きなミス」をクイズ形式で取り出す簡易ヘルパー。
    """
    if not snapshot.moves or limit <= 0:
        return []

    if preset is not None:
        preset_cfg = get_skill_preset(preset).quiz
        loss_threshold = preset_cfg.loss_threshold
        limit = preset_cfg.limit

    items: List[QuizItem] = []
    for move in snapshot.moves:
        if move.score_loss is None and move.points_lost is None:
            continue
        loss_val = get_canonical_loss_from_move(move)
        if loss_val < loss_threshold:
            continue
        items.append(
            QuizItem(
                move_number=move.move_number,
                player=move.player,
                loss=float(loss_val),
            )
        )

    items.sort(key=lambda qi: qi.loss, reverse=True)
    return items[:limit]


def quiz_points_lost_from_candidate(
    candidate_move: Dict[str, Any],
    *,
    root_score: Optional[float],
    next_player: Optional[str],
) -> Optional[float]:
    """
    Extract a points-lost style metric from an existing candidate move entry.
    """
    if candidate_move.get("pointsLost") is not None:
        return float(candidate_move["pointsLost"])

    if candidate_move.get("relativePointsLost") is not None:
        return float(candidate_move["relativePointsLost"])

    if (
        root_score is not None
        and next_player is not None
        and candidate_move.get("scoreLead") is not None
    ):
        sign = 1 if next_player == "B" else -1
        return sign * (root_score - float(candidate_move["scoreLead"]))

    return None


# =============================================================================
# Phase mistake stats
# =============================================================================


def aggregate_phase_mistake_stats(
    moves: Iterable[MoveEval],
    *,
    score_thresholds: Optional[Tuple[float, float, float]] = None,
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
    moves: List[MoveEval],
    *,
    loss_threshold: float = 2.0,
    min_consecutive: int = 2,
) -> List[MistakeStreak]:
    """
    同一プレイヤーの連続ミスを検出する（Go-aware streak detection）
    """
    if not moves:
        return []

    player_moves: Dict[str, List[MoveEval]] = {"B": [], "W": []}
    for m in moves:
        if m.player in player_moves:
            player_moves[m.player].append(m)

    streaks = []

    for player, pmoves in player_moves.items():
        if not pmoves:
            continue

        sorted_moves = sorted(pmoves, key=lambda m: m.move_number)
        current_streak: List[MoveEval] = []

        for m in sorted_moves:
            if m.points_lost is None:
                if len(current_streak) >= min_consecutive:
                    total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
                    streaks.append(MistakeStreak(
                        player=player,
                        start_move=current_streak[0].move_number,
                        end_move=current_streak[-1].move_number,
                        move_count=len(current_streak),
                        total_loss=total_loss,
                        moves=list(current_streak),
                    ))
                current_streak = []
                continue

            loss = max(0.0, m.points_lost)
            if loss >= loss_threshold:
                current_streak.append(m)
            else:
                if len(current_streak) >= min_consecutive:
                    total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
                    streaks.append(MistakeStreak(
                        player=player,
                        start_move=current_streak[0].move_number,
                        end_move=current_streak[-1].move_number,
                        move_count=len(current_streak),
                        total_loss=total_loss,
                        moves=list(current_streak),
                    ))
                current_streak = []

        if len(current_streak) >= min_consecutive:
            total_loss = sum(get_canonical_loss_from_move(mv) for mv in current_streak)
            streaks.append(MistakeStreak(
                player=player,
                start_move=current_streak[0].move_number,
                end_move=current_streak[-1].move_number,
                move_count=len(current_streak),
                total_loss=total_loss,
                moves=list(current_streak),
            ))

    streaks.sort(key=lambda s: s.start_move)
    return streaks


# =============================================================================
# Importance calculation
# =============================================================================


def compute_importance_for_moves(
    moves: Iterable[MoveEval],
    *,
    streak_start_moves: Optional[Set[int]] = None,
    confidence_level: Optional["ConfidenceLevel"] = None,
) -> None:
    """
    各 MoveEval について重要度スコアを計算し、importance_score に格納する。
    """
    # Default to HIGH if not specified
    if confidence_level is None:
        confidence_level = ConfidenceLevel.HIGH

    # Determine which components to use based on confidence
    use_all_components = confidence_level == ConfidenceLevel.HIGH
    use_swing = confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    if streak_start_moves is None:
        streak_start_moves = set()

    for m in moves:
        # 1. Canonical loss (主成分) - always used
        canonical_loss = m.score_loss if m.score_loss is not None else 0.0
        canonical_loss = max(0.0, canonical_loss)

        # 2. Swing magnitude (ターニングポイント)
        swing_magnitude = 0.0
        if use_swing and m.score_before is not None and m.score_after is not None:
            score_sign_changed = (
                (m.score_before > 0) != (m.score_after > 0)
                or m.score_before == 0.0
                or m.score_after == 0.0
            )
            if score_sign_changed:
                swing_magnitude = abs(m.score_before - m.score_after)

        # 3. Difficulty modifier - only for HIGH confidence
        difficulty_modifier = 0.0
        if use_all_components:
            difficulty_modifier = get_difficulty_modifier(m.position_difficulty)

        # 4. Streak start bonus - only for HIGH confidence
        streak_bonus = 0.0
        if use_all_components and m.move_number in streak_start_moves:
            streak_bonus = STREAK_START_BONUS

        # Compute base importance
        base_importance = (
            1.0 * canonical_loss +
            SWING_MAGNITUDE_WEIGHT * swing_magnitude +
            difficulty_modifier +
            streak_bonus
        )

        # Apply reliability scale
        reliability_scale = get_reliability_scale(m.root_visits)
        final_importance = base_importance * reliability_scale

        m.importance_score = max(0.0, final_importance)


def pick_important_moves(
    snapshot: EvalSnapshot,
    level: str = DEFAULT_IMPORTANT_MOVE_LEVEL,
    settings: Optional[ImportantMoveSettings] = None,
    recompute: bool = True,
    streak_start_moves: Optional[Set[int]] = None,
    confidence_level: Optional["ConfidenceLevel"] = None,
) -> List[MoveEval]:
    """
    snapshot から重要局面の手数だけを抽出して返す。
    """
    if settings is None:
        settings = IMPORTANT_MOVE_SETTINGS_BY_LEVEL.get(
            level, IMPORTANT_MOVE_SETTINGS_BY_LEVEL[DEFAULT_IMPORTANT_MOVE_LEVEL]
        )

    threshold = settings.importance_threshold
    max_moves = settings.max_moves

    moves = snapshot.moves
    if not moves:
        return []

    if recompute:
        compute_importance_for_moves(
            moves,
            streak_start_moves=streak_start_moves,
            confidence_level=confidence_level,
        )

    # 1) 通常ルート: importance_score ベース
    candidates: List[Tuple[float, int, MoveEval]] = []
    for move in moves:
        importance = move.importance_score or 0.0
        if importance > threshold:
            candidates.append((importance, move.move_number, move))

    # 2) フォールバック
    if not candidates:
        def raw_score(m: MoveEval) -> float:
            score_term = abs(m.delta_score or 0.0)
            winrate_term = 50.0 * abs(m.delta_winrate or 0.0)
            pl_term = get_canonical_loss_from_move(m)
            base = score_term + winrate_term + pl_term
            base *= get_reliability_scale(m.root_visits)
            return base

        for move in moves:
            raw_sc = raw_score(move)
            if raw_sc > 0.0:
                candidates.append((raw_sc, move.move_number, move))

    # Sort and pick top
    candidates.sort(key=lambda x: (-x[0], x[1]))
    top = candidates[:max_moves]

    important_moves = sorted([m for _, _, m in top], key=lambda m: m.move_number)
    return important_moves


# =============================================================================
# Skill estimation
# =============================================================================


def estimate_skill_level_from_tags(
    reason_tags_counts: Dict[str, int],
    total_important_moves: int
) -> SkillEstimation:
    """
    理由タグ分布から棋力を推定（Phase 13）
    """
    if total_important_moves < 5:
        return SkillEstimation(
            estimated_level="unknown",
            confidence=0.0,
            reason="重要局面数が不足（< 5手）",
            metrics={}
        )

    heavy_loss_count = reason_tags_counts.get("heavy_loss", 0)
    reading_failure_count = reason_tags_counts.get("reading_failure", 0)

    heavy_loss_rate = heavy_loss_count / total_important_moves
    reading_failure_rate = reading_failure_count / total_important_moves

    metrics = {
        "heavy_loss_rate": heavy_loss_rate,
        "reading_failure_rate": reading_failure_rate,
        "total_important_moves": float(total_important_moves)
    }

    if heavy_loss_rate >= 0.4:
        return SkillEstimation(
            estimated_level="beginner",
            confidence=min(0.9, heavy_loss_rate * 1.5),
            reason=f"大損失の出現率が高い（{heavy_loss_rate:.1%}）→ 大局観・判断力を強化する段階",
            metrics=metrics
        )

    if heavy_loss_rate < 0.15 and reading_failure_rate < 0.1:
        confidence = 1.0 - (heavy_loss_rate + reading_failure_rate) * 2
        return SkillEstimation(
            estimated_level="advanced",
            confidence=min(0.9, max(0.5, confidence)),
            reason=f"大損失・読み抜けともに少ない（大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%}）→ 高段者レベル",
            metrics=metrics
        )

    if reading_failure_rate >= 0.15:
        return SkillEstimation(
            estimated_level="standard",
            confidence=min(0.9, reading_failure_rate * 2),
            reason=f"読み抜けの出現率が高い（{reading_failure_rate:.1%}）→ 戦術的な読み・形判断を強化する段階",
            metrics=metrics
        )

    confidence = 0.5
    return SkillEstimation(
        estimated_level="standard",
        confidence=confidence,
        reason=f"大損失{heavy_loss_rate:.1%}、読み抜け{reading_failure_rate:.1%} → 標準的な有段者レベル",
        metrics=metrics
    )


# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


def get_pv_filter_config(
    pv_filter_level: str,
    skill_preset: str = DEFAULT_SKILL_PRESET,
) -> Optional[PVFilterConfig]:
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
    candidates: List[Dict],
    config: PVFilterConfig,
) -> List[Dict]:
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
    filtered = filtered[:config.max_candidates]

    # Step 4: best_moveを先頭に挿入（別枠、上限外）
    if best_move:
        filtered.insert(0, best_move)

    return filtered


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================

_difficulty_logger = logging.getLogger(__name__)


def _normalize_candidates(candidates: List[Dict]) -> Optional[List[Dict]]:
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


def _get_root_visits(analysis: Optional[Dict]) -> Optional[int]:
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
        return root_info.get("visits")

    # KaTrain 内部フォーマット: root.visits
    root = analysis.get("root", {})
    if "visits" in root:
        return root.get("visits")

    # 直接参照（一部のカスタムフォーマット対応）
    if "visits" in analysis:
        return analysis.get("visits")

    return None


def _determine_reliability(
    root_visits: Optional[int],
    candidate_count: int,
) -> Tuple[bool, str]:
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
    candidates: List[Dict],
    include_debug: bool = False,
) -> Tuple[Optional[float], Optional[Dict]]:
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

    debug = {
        "top1_score": top1_score,
        "top2_score": top2_score,
        "gap": gap,
        "normalized": difficulty,
    } if include_debug else None

    return difficulty, debug


def _compute_transition_difficulty(
    candidates: List[Dict],
    include_debug: bool = False,
) -> Tuple[Optional[float], Optional[Dict]]:
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

    debug = {
        "top1_score": top1_score,
        "top2_score": top2_score,
        "drop": drop,
        "normalized": difficulty,
    } if include_debug else None

    return difficulty, debug


def _compute_state_difficulty(
    candidates: List[Dict],
    include_debug: bool = False,
) -> Tuple[float, Optional[Dict]]:
    """盤面の複雑さから State 難易度を計算。

    v1: 仕様書の「控えめに扱う」に従い、常に 0.0 を返す。
    将来の拡張で候補数・分岐多様性を考慮予定。

    Args:
        candidates: 正規化済み候補手リスト
        include_debug: デバッグ情報を含めるか

    Returns:
        (difficulty, debug_info) タプル。v1 では常に (0.0, debug)。
    """
    debug = {
        "v1_note": "state_difficulty disabled in v1",
        "candidate_count": len(candidates),
    } if include_debug else None

    return 0.0, debug


def compute_difficulty_metrics(
    candidates: List[Dict],
    root_visits: Optional[int] = None,
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
    is_reliable, reliability_reason = _determine_reliability(
        root_visits, len(normalized)
    )

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


def _get_candidates_from_node(node: "GameNode") -> Tuple[List[Dict], Optional[int]]:
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
    nodes: List["GameNode"],
    limit: int = DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    min_move_number: int = DEFAULT_MIN_MOVE_NUMBER,
    exclude_unreliable: bool = False,
    include_debug: bool = False,
) -> List[Tuple[int, "GameNode", DifficultyMetrics]]:
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
        move_number = node.move_number if hasattr(node, 'move_number') else 0

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
    # Quiz
    "quiz_items_from_snapshot",
    "quiz_points_lost_from_candidate",
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
]
