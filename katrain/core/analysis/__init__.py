"""
katrain.core.analysis - 解析基盤パッケージ

このパッケージは eval_metrics.py の機能を整理したものです。
Phase B で models.py, logic.py, presentation.py に分離されました。

構成:
- models.py: Enum, Dataclass, 設定定数
- logic.py: 純粋計算関数（オーケストレーター）
  - logic_loss.py: 損失計算関数（PR #126）
  - logic_importance.py: 重要度計算関数（PR #127）
- presentation.py: 表示/フォーマット関数

後方互換性:
- 全てのシンボルはこの __init__.py から再エクスポートされます
- `from katrain.core.analysis import *` で全機能にアクセス可能
- logic.py は logic_*.py から再エクスポートするため、既存のインポートは変更不要

Note: シンボルの __module__ パスが変更されます。
      pickle/キャッシュでクラス参照を保存している場合、デシリアライズ失敗の可能性あり。
      （調査結果: リポジトリ内に pickle/cache 使用箇所なし）
"""

from __future__ import annotations

from typing import Any

# =============================================================================
# Explicit imports from board_context.py (Phase 80)
# =============================================================================
from katrain.core.analysis.board_context import (
    # Enums
    BoardArea,
    # Dataclasses
    OwnershipContext,
    # Functions
    classify_area,
    extract_ownership_context,
    get_area_name,
    get_score_stdev,
)

# =============================================================================
# Explicit imports from cluster_classifier.py (Phase 82)
# =============================================================================
from katrain.core.analysis.cluster_classifier import (
    # Dataclasses
    ClassifiedCluster,
    ClusterClassificationContext,
    # Enums
    ClusterSemantics,
    StoneCache,
    # Type aliases (exported for annotation)
    StonePosition,
    StoneSet,
    # Karte integration (private but exported for testing)
    _get_cluster_context_for_move,
    build_classification_context,
    # Classification
    classify_cluster,
    compute_cluster_ownership_avg,
    # Stone reconstruction
    compute_stones_at_node,
    # Context building
    get_ownership_context_pair,
    get_semantics_label,
    get_stones_in_cluster,
    # Classification helpers
    is_opponent_gain,
    should_inject,
)
from katrain.core.analysis.cluster_classifier import (
    compute_confidence as compute_cluster_confidence,
)

# =============================================================================
# Explicit imports from critical_moves.py (Phase 50)
# =============================================================================
from katrain.core.analysis.critical_moves import (
    COMPLEXITY_DISCOUNT_FACTOR,
    CRITICAL_SCORE_PRECISION,
    DEFAULT_MEANING_TAG_WEIGHT,
    DIVERSITY_PENALTY_FACTOR,
    # Constants (for testing)
    MEANING_TAG_WEIGHTS,
    # Phase 83 constants
    THRESHOLD_SCORE_STDEV_CHAOS,
    ComplexityFilterStats,  # Phase 83
    # Dataclass
    CriticalMove,
    _build_node_map,
    _classify_meaning_tags,
    _compute_complexity_discount,  # Phase 83
    _compute_critical_score,
    _compute_diversity_penalty,
    # Internal functions (exported for testing)
    _get_meaning_tag_weight,
    _get_score_stdev_for_move,
    _get_score_stdev_from_node,
    _sort_key,
    # Main function
    select_critical_moves,
)

# =============================================================================
# Explicit imports from logic.py
# =============================================================================
from katrain.core.analysis.logic import (
    # Position difficulty
    _assess_difficulty_from_policy,
    _compute_policy_difficulty,
    _compute_state_difficulty,
    _compute_transition_difficulty,
    _determine_reliability,
    # Auto-strictness
    _distance_from_range,
    _get_candidates_from_node,
    _get_root_visits,
    # Difficulty Metrics (Phase 12)
    _normalize_candidates,
    # Phase mistake stats
    aggregate_phase_mistake_stats,
    assess_position_difficulty_from_parent,
    classify_game_phase,
    classify_mistake,
    compute_canonical_loss,
    # Confidence level
    compute_confidence_level,
    compute_difficulty_metrics,
    compute_effective_threshold,  # Phase 44: relative threshold calculation
    # Importance
    compute_importance_for_moves,
    # Loss calculation
    compute_loss_from_delta,
    compute_reliability_stats,
    # Mistake streaks
    detect_mistake_streaks,
    # Difficulty Metrics Public API (Phase 12.5)
    difficulty_metrics_from_node,
    # Skill estimation
    estimate_skill_level_from_tags,
    extract_difficult_positions,
    filter_candidates_by_pv_complexity,
    # Reliability functions
    get_difficulty_modifier,
    # Phase functions
    get_phase_thresholds,
    # PV Filter (Phase 11)
    get_pv_filter_config,
    get_reliability_scale,
    # Skill preset helpers
    get_skill_preset,
    get_urgent_miss_config,
    is_reliable_from_visits,
    iter_main_branch_nodes,
    # GameNode bridge
    move_eval_from_node,
    pick_important_moves,
    recommend_auto_strictness,
    snapshot_from_game,
    # Snapshot
    snapshot_from_nodes,
    # Reason tag validation
    move_eval_from_node,
    pick_important_moves,
    recommend_auto_strictness,
    snapshot_from_game,
    # Snapshot
    snapshot_from_nodes,
    # Reason tag validation
    validate_reason_tag,
)

# =============================================================================
# Explicit imports from logic_quiz.py (Phase 98)
# =============================================================================
from katrain.core.analysis.logic_quiz import (
    get_skill_preset_quiz_config,
    quiz_items_from_snapshot,
    quiz_points_lost_from_candidate,
)

# =============================================================================
# Explicit imports from logic_loss.py (Phase B split)
# =============================================================================
from katrain.core.analysis.logic_loss import (
    detect_engine_type,
)

# =============================================================================
# Explicit imports from models.py
# =============================================================================
from katrain.core.analysis.models import (
    _CONFIDENCE_THRESHOLDS,
    DEFAULT_ANALYSIS_ENGINE,
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    DEFAULT_MIN_MOVE_NUMBER,
    DEFAULT_PV_FILTER_LEVEL,
    DEFAULT_QUIZ_ITEM_LIMIT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    DEFAULT_SKILL_PRESET,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_MODIFIER_EASY,
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_NORMAL,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    DIFFICULTY_UNKNOWN,
    # Settings dictionaries
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    MIN_COVERAGE_MOVES,
    POLICY_GAP_MAX,
    PRESET_ORDER,
    PV_FILTER_CONFIGS,
    RELIABILITY_RATIO,  # Phase 44: 90% ratio for relative threshold
    RELIABILITY_SCALE_THRESHOLDS,
    # Reliability/importance constants
    RELIABILITY_VISITS_THRESHOLD,
    # Thresholds
    SCORE_THRESHOLDS,
    # Preset dictionaries and lists
    SKILL_PRESETS,
    SKILL_TO_PV_FILTER,
    STREAK_START_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    SWING_SCORE_SIGN_BONUS,
    SWING_WINRATE_CROSS_BONUS,
    TRANSITION_DROP_MAX,
    UNRELIABLE_IMPORTANCE_SCALE,
    URGENT_MISS_CONFIGS,
    # Analysis Engine Selection (Phase 33-34)
    VALID_ANALYSIS_ENGINES,
    WINRATE_THRESHOLDS,
    AutoConfidence,
    AutoRecommendation,
    ConfidenceLevel,
    # Phase 12: Difficulty Metrics
    DifficultyMetrics,
    EngineType,
    EvalSnapshot,
    GameSummaryData,
    ImportantMoveSettings,
    # Enums
    MistakeCategory,
    MistakeStreak,
    # Dataclasses
    MoveEval,
    PhaseMistakeStats,
    PositionDifficulty,
    PVFilterConfig,
    PVFilterLevel,
    QuizConfig,
    QuizItem,
    QuizChoice,
    QuizQuestion,
    ReasonTagThresholds,
    ReliabilityStats,
    SkillEstimation,
    SkillPreset,
    SummaryStats,
    UrgentMissConfig,
    get_analysis_engine,
    # Helper function
    get_canonical_loss_from_move,
    needs_leela_warning,  # Phase 34
)

# =============================================================================
# Explicit imports from ownership_cluster.py (Phase 81)
# =============================================================================
from katrain.core.analysis.ownership_cluster import (
    # Constants
    DEFAULT_NEUTRAL_EPSILON,
    ClusterExtractionConfig,
    ClusterExtractionResult,
    # Enums
    ClusterType,
    OwnershipCluster,
    # Dataclasses
    OwnershipDelta,
    # Functions
    compute_ownership_delta,
    extract_clusters,
    extract_clusters_from_nodes,
)

# =============================================================================
# Explicit imports from presentation.py
# =============================================================================
from katrain.core.analysis.presentation import (
    CONFIDENCE_LABELS,
    REASON_TAG_LABELS,
    # Label constants
    SKILL_PRESET_LABELS,
    VALID_REASON_TAGS,
    format_difficulty_metrics,
    format_evidence_examples,
    # Loss label formatting (Phase 32)
    format_loss_label,
    get_auto_confidence_label,
    # Functions
    get_confidence_label,
    # Difficulty Metrics Formatting (Phase 12.5)
    get_difficulty_label,
    get_evidence_count,
    get_important_moves_limit,
    get_practice_priorities_from_stats,
    get_reason_tag_label,
    select_representative_moves,
)

# =============================================================================
# Explicit imports from reason_generator.py (Phase 86)
# =============================================================================
from katrain.core.analysis.reason_generator import (
    AREA_VOCABULARY,
    COMBINATION_REASONS,
    PHASE_VOCABULARY,
    SINGLE_TAG_REASONS,
    # Constants
    SUPPORTED_TAGS,
    # Dataclass
    ReasonTemplate,
    # Functions
    generate_reason,
    generate_reason_safe,
)



# =============================================================================
# Explicit imports from skill_radar.py (Phase 48)
# =============================================================================
from katrain.core.analysis.skill_radar import (
    APL_TIER_THRESHOLDS,
    BLUNDER_RATE_TIER_THRESHOLDS,
    ENDGAME_START_MOVE,
    GARBAGE_TIME_WINRATE_HIGH,
    GARBAGE_TIME_WINRATE_LOW,
    INT_TO_TIER,
    MATCH_RATE_TIER_THRESHOLDS,
    MIN_MOVES_FOR_RADAR,
    # Phase 49 constants
    MIN_VALID_AXES_FOR_OVERALL,
    NEUTRAL_DISPLAY_SCORE,
    NEUTRAL_TIER,
    OPENING_END_MOVE,
    OPTIONAL_RADAR_DICT_KEYS,
    REQUIRED_RADAR_DICT_KEYS,
    # Constants
    TIER_TO_INT,
    AggregatedRadarResult,  # Phase 49
    # Enums
    RadarAxis,
    # Dataclass
    RadarMetrics,
    SkillTier,
    aggregate_radar,
    # Conversion functions
    apl_to_tier_and_score,
    blunder_rate_to_tier_and_score,
    compute_awareness_axis,
    compute_endgame_axis,
    compute_fighting_axis,
    # Axis computation functions
    compute_opening_axis,
    compute_overall_tier,
    # Main entry point
    compute_radar_from_moves,
    compute_stability_axis,
    # Detection functions
    is_garbage_time,
    match_rate_to_tier_and_score,
    radar_from_dict,
    # Phase 49: Aggregation functions
    round_score,
)

# =============================================================================
# Explicit imports from style/ (Phase 56)
# =============================================================================
from katrain.core.analysis.style import (
    CONFIDENCE_NORMALIZATION,
    # Constants
    DEVIATION_HIGH_THRESHOLD,
    DEVIATION_LOW_THRESHOLD,
    SCORE_TOLERANCE,
    # Registry
    STYLE_ARCHETYPES,
    TAG_SIGNIFICANT_COUNT,
    # Dataclasses
    StyleArchetype,
    # Enums
    StyleArchetypeId,
    StyleResult,
    # Helper functions
    compute_confidence,
    # Main function
    determine_style,
    scores_are_tied,
)

# =============================================================================
# Explicit imports from user_aggregate.py (Phase 55)
# =============================================================================
from katrain.core.analysis.user_aggregate import (
    # Constants
    DEFAULT_HISTORY_SIZE,
    # Dataclasses
    GameRadarEntry,
    # Store class
    UserAggregateStore,
    UserRadarAggregate,
)

# =============================================================================
# Phase 92: Public Wrapper Functions
# =============================================================================


def get_root_visits(analysis: dict[str, Any] | None) -> int | None:
    """Get root visits from analysis dict (public API).

    This is the public wrapper for _get_root_visits().
    Use this function instead of _get_root_visits() in external modules.

    Supports multiple formats:
    - rootInfo.visits (KataGo standard)
    - root.visits (KaTrain internal)
    - visits (direct reference)

    Args:
        analysis: Analysis dictionary from node, or None

    Returns:
        Number of visits, or None if analysis is None or visits not found.
    """
    return _get_root_visits(analysis)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # === models.py ===
    # Enums
    "MistakeCategory",
    "PositionDifficulty",
    "AutoConfidence",
    "ConfidenceLevel",
    "PVFilterLevel",
    "EngineType",
    # Analysis Engine Selection (Phase 33-34)
    "VALID_ANALYSIS_ENGINES",
    "DEFAULT_ANALYSIS_ENGINE",
    "get_analysis_engine",
    "needs_leela_warning",  # Phase 34
    # Dataclasses
    "MoveEval",
    "EvalSnapshot",
    "GameSummaryData",
    "SummaryStats",
    "PhaseMistakeStats",
    "ImportantMoveSettings",
    "ReasonTagThresholds",
    "SkillPreset",
    "AutoRecommendation",
    "UrgentMissConfig",
    "ReliabilityStats",
    "MistakeStreak",
    "SkillEstimation",
    "PVFilterConfig",
    "QuizConfig",  # Phase 98
    "QuizItem",  # Phase 98
    "QuizChoice",  # Phase 98
    "QuizQuestion",  # Phase 98
    # Phase 12: Difficulty Metrics
    "DifficultyMetrics",
    "DIFFICULTY_UNKNOWN",
    "DIFFICULTY_MIN_VISITS",
    "DIFFICULTY_MIN_CANDIDATES",
    "POLICY_GAP_MAX",
    "TRANSITION_DROP_MAX",
    "DEFAULT_DIFFICULT_POSITIONS_LIMIT",
    "DEFAULT_MIN_MOVE_NUMBER",
    "DEFAULT_QUIZ_LOSS_THRESHOLD",  # Phase 98
    "DEFAULT_QUIZ_ITEM_LIMIT",  # Phase 98
    # Preset dictionaries and lists
    "SKILL_PRESETS",
    "DEFAULT_SKILL_PRESET",
    "PRESET_ORDER",
    "URGENT_MISS_CONFIGS",
    "PV_FILTER_CONFIGS",
    "SKILL_TO_PV_FILTER",
    "DEFAULT_PV_FILTER_LEVEL",
    # Settings dictionaries
    "IMPORTANT_MOVE_SETTINGS_BY_LEVEL",
    "DEFAULT_IMPORTANT_MOVE_LEVEL",
    # Reliability/importance constants
    "RELIABILITY_VISITS_THRESHOLD",
    "RELIABILITY_RATIO",  # Phase 44
    "UNRELIABLE_IMPORTANCE_SCALE",
    "SWING_SCORE_SIGN_BONUS",
    "SWING_WINRATE_CROSS_BONUS",
    "SWING_MAGNITUDE_WEIGHT",
    "DIFFICULTY_MODIFIER_HARD",
    "DIFFICULTY_MODIFIER_ONLY_MOVE",
    "DIFFICULTY_MODIFIER_EASY",
    "DIFFICULTY_MODIFIER_NORMAL",
    "STREAK_START_BONUS",
    "RELIABILITY_SCALE_THRESHOLDS",
    # Thresholds
    "SCORE_THRESHOLDS",
    "WINRATE_THRESHOLDS",
    "MIN_COVERAGE_MOVES",
    "_CONFIDENCE_THRESHOLDS",
    # Helper function
    "get_canonical_loss_from_move",
    # === logic.py ===
    # Skill preset helpers
    "get_skill_preset",
    "get_urgent_miss_config",
    # Auto-strictness
    "_distance_from_range",
    "recommend_auto_strictness",
    # Reason tag validation
    "validate_reason_tag",
    "validate_reason_tag",
    # GameNode bridge
    "move_eval_from_node",
    # Logic Quiz (Phase 98)
    "get_skill_preset_quiz_config",
    "quiz_items_from_snapshot",
    "quiz_points_lost_from_candidate",
    # Reliability functions
    "get_difficulty_modifier",
    "get_reliability_scale",
    "is_reliable_from_visits",
    "compute_reliability_stats",
    "compute_effective_threshold",  # Phase 44
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
    "detect_engine_type",
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
    "get_root_visits",  # Phase 92: Public wrapper
    "_determine_reliability",
    "_compute_policy_difficulty",
    "_compute_transition_difficulty",
    "_compute_state_difficulty",
    "compute_difficulty_metrics",
    "_get_candidates_from_node",
    "extract_difficult_positions",
    # Difficulty Metrics Public API (Phase 12.5)
    "difficulty_metrics_from_node",
    # === presentation.py ===
    # Label constants
    "SKILL_PRESET_LABELS",
    "CONFIDENCE_LABELS",
    "REASON_TAG_LABELS",
    "VALID_REASON_TAGS",
    # Functions
    "get_confidence_label",
    "get_auto_confidence_label",
    "get_important_moves_limit",
    "get_evidence_count",
    "get_reason_tag_label",
    "select_representative_moves",
    "format_evidence_examples",
    "get_practice_priorities_from_stats",
    # Difficulty Metrics Formatting (Phase 12.5)
    "get_difficulty_label",
    "format_difficulty_metrics",
    # Loss label formatting (Phase 32)
    "format_loss_label",
    # === skill_radar.py (Phase 48) ===
    # Enums
    "RadarAxis",
    "SkillTier",
    # Dataclass
    "RadarMetrics",
    "AggregatedRadarResult",  # Phase 49
    # Constants
    "TIER_TO_INT",
    "INT_TO_TIER",
    "APL_TIER_THRESHOLDS",
    "BLUNDER_RATE_TIER_THRESHOLDS",
    "MATCH_RATE_TIER_THRESHOLDS",
    "GARBAGE_TIME_WINRATE_HIGH",
    "GARBAGE_TIME_WINRATE_LOW",
    "OPENING_END_MOVE",
    "ENDGAME_START_MOVE",
    "NEUTRAL_DISPLAY_SCORE",
    "NEUTRAL_TIER",
    # Phase 49 constants
    "MIN_VALID_AXES_FOR_OVERALL",
    "MIN_MOVES_FOR_RADAR",
    "REQUIRED_RADAR_DICT_KEYS",
    "OPTIONAL_RADAR_DICT_KEYS",
    # Conversion functions
    "apl_to_tier_and_score",
    "blunder_rate_to_tier_and_score",
    "match_rate_to_tier_and_score",
    # Detection functions
    "is_garbage_time",
    "compute_overall_tier",
    # Axis computation functions
    "compute_opening_axis",
    "compute_fighting_axis",
    "compute_endgame_axis",
    "compute_stability_axis",
    "compute_awareness_axis",
    # Main entry point
    "compute_radar_from_moves",
    # Phase 49: Aggregation functions
    "round_score",
    "radar_from_dict",
    "aggregate_radar",
    # === critical_moves.py (Phase 50) ===
    # Dataclass
    "CriticalMove",
    "ComplexityFilterStats",  # Phase 83
    # Main function
    "select_critical_moves",
    # Constants (for testing)
    "MEANING_TAG_WEIGHTS",
    "DEFAULT_MEANING_TAG_WEIGHT",
    "DIVERSITY_PENALTY_FACTOR",
    "CRITICAL_SCORE_PRECISION",
    # Phase 83 constants
    "THRESHOLD_SCORE_STDEV_CHAOS",
    "COMPLEXITY_DISCOUNT_FACTOR",
    # Internal functions (exported for testing)
    "_get_meaning_tag_weight",
    "_compute_diversity_penalty",
    "_compute_complexity_discount",  # Phase 83
    "_compute_critical_score",
    "_sort_key",
    "_build_node_map",
    "_get_score_stdev_from_node",
    "_get_score_stdev_for_move",
    "_classify_meaning_tags",
    # === user_aggregate.py (Phase 55) ===
    # Constants
    "DEFAULT_HISTORY_SIZE",
    # Dataclasses
    "GameRadarEntry",
    "UserRadarAggregate",
    # Store class
    "UserAggregateStore",
    # === style/ (Phase 56) ===
    # Enums
    "StyleArchetypeId",
    # Dataclasses
    "StyleArchetype",
    "StyleResult",
    # Registry
    "STYLE_ARCHETYPES",
    # Main function
    "determine_style",
    # Helper functions
    "compute_confidence",
    "scores_are_tied",
    # Constants
    "DEVIATION_HIGH_THRESHOLD",
    "DEVIATION_LOW_THRESHOLD",
    "TAG_SIGNIFICANT_COUNT",
    "SCORE_TOLERANCE",
    "CONFIDENCE_NORMALIZATION",

    # === board_context.py (Phase 80) ===
    # Enums
    "BoardArea",
    # Dataclasses
    "OwnershipContext",
    # Functions
    "classify_area",
    "get_area_name",
    "extract_ownership_context",
    "get_score_stdev",
    # === ownership_cluster.py (Phase 81) ===
    # Constants
    "DEFAULT_NEUTRAL_EPSILON",
    # Enums
    "ClusterType",
    # Dataclasses
    "OwnershipDelta",
    "OwnershipCluster",
    "ClusterExtractionConfig",
    "ClusterExtractionResult",
    # Functions
    "compute_ownership_delta",
    "extract_clusters",
    "extract_clusters_from_nodes",
    # === cluster_classifier.py (Phase 82) ===
    # Type aliases
    "StonePosition",
    "StoneSet",
    # Enums
    "ClusterSemantics",
    # Dataclasses
    "ClassifiedCluster",
    "ClusterClassificationContext",
    # Stone reconstruction
    "compute_stones_at_node",
    "StoneCache",
    # Classification helpers
    "is_opponent_gain",
    "get_stones_in_cluster",
    "compute_cluster_ownership_avg",
    "compute_cluster_confidence",
    "should_inject",
    "get_semantics_label",
    # Classification
    "classify_cluster",
    # Context building
    "get_ownership_context_pair",
    "build_classification_context",
    # Karte integration
    "_get_cluster_context_for_move",
    # === reason_generator.py (Phase 86) ===
    # Dataclass
    "ReasonTemplate",
    # Constants
    "SUPPORTED_TAGS",
    "PHASE_VOCABULARY",
    "AREA_VOCABULARY",
    "SINGLE_TAG_REASONS",
    "COMBINATION_REASONS",
    # Functions
    "generate_reason",
    "generate_reason_safe",
]