"""
katrain.core.analysis - 解析基盤パッケージ

このパッケージは eval_metrics.py の機能を整理したものです。
Phase B で models.py, logic.py, presentation.py に分離されました。

構成:
- models.py: Enum, Dataclass, 設定定数
- logic.py: 純粋計算関数（オーケストレーター）
  - logic_loss.py: 損失計算関数（PR #126）
  - logic_importance.py: 重要度計算関数（PR #127）
  - logic_quiz.py: クイズヘルパー関数（PR #128）
- presentation.py: 表示/フォーマット関数

後方互換性:
- 全てのシンボルはこの __init__.py から再エクスポートされます
- `from katrain.core.analysis import *` で全機能にアクセス可能
- logic.py は logic_*.py から再エクスポートするため、既存のインポートは変更不要

Note: シンボルの __module__ パスが変更されます。
      pickle/キャッシュでクラス参照を保存している場合、デシリアライズ失敗の可能性あり。
      （調査結果: リポジトリ内に pickle/cache 使用箇所なし）
"""

# =============================================================================
# Explicit imports from models.py
# =============================================================================

from katrain.core.analysis.models import (
    # Enums
    MistakeCategory,
    PositionDifficulty,
    AutoConfidence,
    ConfidenceLevel,
    PVFilterLevel,
    EngineType,
    # Analysis Engine Selection (Phase 33)
    VALID_ANALYSIS_ENGINES,
    DEFAULT_ANALYSIS_ENGINE,
    get_analysis_engine,
    # Dataclasses
    MoveEval,
    EvalSnapshot,
    GameSummaryData,
    SummaryStats,
    PhaseMistakeStats,
    ImportantMoveSettings,
    ReasonTagThresholds,
    QuizItem,
    QuizConfig,
    QuizChoice,
    QuizQuestion,
    SkillPreset,
    AutoRecommendation,
    UrgentMissConfig,
    ReliabilityStats,
    MistakeStreak,
    SkillEstimation,
    PVFilterConfig,
    # Phase 12: Difficulty Metrics
    DifficultyMetrics,
    DIFFICULTY_UNKNOWN,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_MIN_CANDIDATES,
    POLICY_GAP_MAX,
    TRANSITION_DROP_MAX,
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    # Preset dictionaries and lists
    SKILL_PRESETS,
    DEFAULT_SKILL_PRESET,
    PRESET_ORDER,
    URGENT_MISS_CONFIGS,
    PV_FILTER_CONFIGS,
    SKILL_TO_PV_FILTER,
    DEFAULT_PV_FILTER_LEVEL,
    # Settings dictionaries
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    # Quiz constants
    QUIZ_CONFIG_DEFAULT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    DEFAULT_QUIZ_ITEM_LIMIT,
    # Reliability/importance constants
    RELIABILITY_VISITS_THRESHOLD,
    UNRELIABLE_IMPORTANCE_SCALE,
    SWING_SCORE_SIGN_BONUS,
    SWING_WINRATE_CROSS_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    DIFFICULTY_MODIFIER_EASY,
    DIFFICULTY_MODIFIER_NORMAL,
    STREAK_START_BONUS,
    RELIABILITY_SCALE_THRESHOLDS,
    # Thresholds
    SCORE_THRESHOLDS,
    WINRATE_THRESHOLDS,
    MIN_COVERAGE_MOVES,
    _CONFIDENCE_THRESHOLDS,
    # Helper function
    get_canonical_loss_from_move,
)

# =============================================================================
# Explicit imports from logic.py
# =============================================================================

from katrain.core.analysis.logic import (
    # Skill preset helpers
    get_skill_preset,
    get_urgent_miss_config,
    # Auto-strictness
    _distance_from_range,
    recommend_auto_strictness,
    # Reason tag validation
    validate_reason_tag,
    # GameNode bridge
    move_eval_from_node,
    # Reliability functions
    get_difficulty_modifier,
    get_reliability_scale,
    is_reliable_from_visits,
    compute_reliability_stats,
    # Confidence level
    compute_confidence_level,
    # Phase functions
    get_phase_thresholds,
    classify_game_phase,
    # Position difficulty
    _assess_difficulty_from_policy,
    assess_position_difficulty_from_parent,
    # Loss calculation
    compute_loss_from_delta,
    compute_canonical_loss,
    classify_mistake,
    detect_engine_type,
    # Snapshot
    snapshot_from_nodes,
    iter_main_branch_nodes,
    snapshot_from_game,
    # Quiz
    quiz_items_from_snapshot,
    quiz_points_lost_from_candidate,
    # Phase mistake stats
    aggregate_phase_mistake_stats,
    # Mistake streaks
    detect_mistake_streaks,
    # Importance
    compute_importance_for_moves,
    pick_important_moves,
    # Skill estimation
    estimate_skill_level_from_tags,
    # PV Filter (Phase 11)
    get_pv_filter_config,
    filter_candidates_by_pv_complexity,
    # Difficulty Metrics (Phase 12)
    _normalize_candidates,
    _get_root_visits,
    _determine_reliability,
    _compute_policy_difficulty,
    _compute_transition_difficulty,
    _compute_state_difficulty,
    compute_difficulty_metrics,
    _get_candidates_from_node,
    extract_difficult_positions,
    # Difficulty Metrics Public API (Phase 12.5)
    difficulty_metrics_from_node,
)

# =============================================================================
# Explicit imports from presentation.py
# =============================================================================

from katrain.core.analysis.presentation import (
    # Label constants
    SKILL_PRESET_LABELS,
    CONFIDENCE_LABELS,
    REASON_TAG_LABELS,
    VALID_REASON_TAGS,
    # Functions
    get_confidence_label,
    get_auto_confidence_label,
    get_important_moves_limit,
    get_evidence_count,
    get_reason_tag_label,
    select_representative_moves,
    format_evidence_examples,
    get_practice_priorities_from_stats,
    # Difficulty Metrics Formatting (Phase 12.5)
    get_difficulty_label,
    format_difficulty_metrics,
    # Loss label formatting (Phase 32)
    format_loss_label,
)

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
    # Analysis Engine Selection (Phase 33)
    "VALID_ANALYSIS_ENGINES",
    "DEFAULT_ANALYSIS_ENGINE",
    "get_analysis_engine",
    # Dataclasses
    "MoveEval",
    "EvalSnapshot",
    "GameSummaryData",
    "SummaryStats",
    "PhaseMistakeStats",
    "ImportantMoveSettings",
    "ReasonTagThresholds",
    "QuizItem",
    "QuizConfig",
    "QuizChoice",
    "QuizQuestion",
    "SkillPreset",
    "AutoRecommendation",
    "UrgentMissConfig",
    "ReliabilityStats",
    "MistakeStreak",
    "SkillEstimation",
    "PVFilterConfig",
    # Phase 12: Difficulty Metrics
    "DifficultyMetrics",
    "DIFFICULTY_UNKNOWN",
    "DIFFICULTY_MIN_VISITS",
    "DIFFICULTY_MIN_CANDIDATES",
    "POLICY_GAP_MAX",
    "TRANSITION_DROP_MAX",
    "DEFAULT_DIFFICULT_POSITIONS_LIMIT",
    "DEFAULT_MIN_MOVE_NUMBER",
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
    # Quiz constants
    "QUIZ_CONFIG_DEFAULT",
    "DEFAULT_QUIZ_LOSS_THRESHOLD",
    "DEFAULT_QUIZ_ITEM_LIMIT",
    # Reliability/importance constants
    "RELIABILITY_VISITS_THRESHOLD",
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
    "detect_engine_type",
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
]
