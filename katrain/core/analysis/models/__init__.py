"""katrain.core.analysis.models - データモデル定義

Phase 144-B: 1230 行の単一ファイル models.py を 6 つの焦点化モジュールに分割:
- enums.py: 7 enum + engine 設定 helper + visits 解決
- move_eval.py: MoveEval + EvalSnapshot + canonical_loss helper
- quiz.py: QuizConfig/Item/Choice/Question + ImportantMove 設定
- skill.py: GameSummaryData + SummaryStats + PhaseMistakeStats + SkillPreset
  + AutoRecommendation + UrgentMiss + MistakeStreak + SkillEstimation
- reliability.py: ReliabilityStats + 信頼性定数
- difficulty.py: PVFilterConfig + DifficultyMetrics + 難易度定数

後方互換性のため、この __init__.py は以下のシンボルをすべて再エクスポート:
- 既存: `from katrain.core.analysis.models import X` パス
- 遅延 import: SKILL_PRESET_LABELS, CONFIDENCE_LABELS などは
  presentation.py から透過的に取得（__getattr__）

Note: EvalSnapshot.worst_canonical_move などは logic.py の関数を使用するため、
      一部のメソッドはプロパティ内でインポートを遅延実行しています。
"""
from __future__ import annotations

from typing import Any

from katrain.core.analysis.models.difficulty import (
    DEFAULT_DIFFICULT_POSITIONS_LIMIT,
    DEFAULT_MIN_MOVE_NUMBER,
    DEFAULT_PV_FILTER_LEVEL,
    DIFFICULTY_MIN_CANDIDATES,
    DIFFICULTY_MIN_VISITS,
    DIFFICULTY_UNKNOWN,
    ERROR_PRESSURE_WEIGHT,
    LCB_GAP_MAX,
    LCB_GAP_WEIGHT,
    POLICY_GAP_MAX,
    PV_FILTER_CONFIGS,
    SHORTTERM_SCORE_ERROR_MAX,
    SKILL_TO_PV_FILTER,
    TRANSITION_DROP_MAX,
    DifficultyMetrics,
    PVFilterConfig,
)
from katrain.core.analysis.models.enums import (
    DEFAULT_ANALYSIS_ENGINE,
    ENGINE_VISITS_DEFAULTS,
    LEELA_FAST_VISITS_MIN,
    VALID_ANALYSIS_ENGINES,
    AnalysisStrength,
    AutoConfidence,
    ConfidenceLevel,
    EngineType,
    MistakeCategory,
    PositionDifficulty,
    PVFilterLevel,
    get_analysis_engine,
    needs_leela_warning,
    resolve_visits,
)
from katrain.core.analysis.models.move_eval import (
    EvalSnapshot,
    MoveEval,
    get_canonical_loss_from_move,
)
from katrain.core.analysis.models.quiz import (
    DEFAULT_IMPORTANT_MOVE_LEVEL,
    DEFAULT_QUIZ_ITEM_LIMIT,
    DEFAULT_QUIZ_LOSS_THRESHOLD,
    IMPORTANT_MOVE_SETTINGS_BY_LEVEL,
    MIN_LOSS_DISPLAY,
    ImportantMoveSettings,
    QuizChoice,
    QuizConfig,
    QuizItem,
    QuizQuestion,
)
from katrain.core.analysis.models.reliability import (
    _CONFIDENCE_THRESHOLDS,
    DIFFICULTY_MODIFIER_EASY,
    DIFFICULTY_MODIFIER_HARD,
    DIFFICULTY_MODIFIER_NORMAL,
    DIFFICULTY_MODIFIER_ONLY_MOVE,
    DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS,
    DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD,
    MIN_COVERAGE_MOVES,
    RELIABILITY_RATIO,
    RELIABILITY_SCALE_THRESHOLDS,
    RELIABILITY_VISITS_THRESHOLD,
    STREAK_START_BONUS,
    SWING_MAGNITUDE_WEIGHT,
    SWING_SCORE_SIGN_BONUS,
    SWING_WINRATE_CROSS_BONUS,
    UNRELIABLE_IMPORTANCE_SCALE,
    ReliabilityStats,
)
from katrain.core.analysis.models.skill import (
    DEFAULT_SKILL_PRESET,
    PRESET_ORDER,
    SCORE_THRESHOLDS,
    SKILL_PRESETS,
    URGENT_MISS_CONFIGS,
    WINRATE_THRESHOLDS,
    AutoRecommendation,
    GameSummaryData,
    MistakeStreak,
    PhaseMistakeStats,
    ReasonTagThresholds,
    SkillEstimation,
    SkillPreset,
    SummaryStats,
    UrgentMissConfig,
)

# =============================================================================
# Lazy import for label constants from presentation module (backward compat)
# =============================================================================


def __getattr__(name: str) -> Any:
    """Lazy import for label constants from presentation module.

    These labels are re-exported from presentation.py to maintain backward
    compatibility with code that imports them from models.
    """
    if name in ("SKILL_PRESET_LABELS", "CONFIDENCE_LABELS", "REASON_TAG_LABELS", "VALID_REASON_TAGS"):
        from katrain.core.analysis.presentation import (
            CONFIDENCE_LABELS,
            REASON_TAG_LABELS,
            SKILL_PRESET_LABELS,
            VALID_REASON_TAGS,
        )

        return {
            "SKILL_PRESET_LABELS": SKILL_PRESET_LABELS,
            "CONFIDENCE_LABELS": CONFIDENCE_LABELS,
            "REASON_TAG_LABELS": REASON_TAG_LABELS,
            "VALID_REASON_TAGS": VALID_REASON_TAGS,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Enums
    "MistakeCategory",
    "PositionDifficulty",
    "AutoConfidence",
    "ConfidenceLevel",
    "PVFilterLevel",
    "AnalysisStrength",
    "EngineType",
    # Engine config helpers
    "get_analysis_engine",
    "needs_leela_warning",
    "resolve_visits",
    "VALID_ANALYSIS_ENGINES",
    "DEFAULT_ANALYSIS_ENGINE",
    "ENGINE_VISITS_DEFAULTS",
    "LEELA_FAST_VISITS_MIN",
    # MoveEval and EvalSnapshot
    "MoveEval",
    "EvalSnapshot",
    "get_canonical_loss_from_move",
    # Quiz
    "QuizConfig",
    "QuizItem",
    "QuizChoice",
    "QuizQuestion",
    "DEFAULT_QUIZ_LOSS_THRESHOLD",
    "DEFAULT_QUIZ_ITEM_LIMIT",
    "ImportantMoveSettings",
    "IMPORTANT_MOVE_SETTINGS_BY_LEVEL",
    "DEFAULT_IMPORTANT_MOVE_LEVEL",
    "MIN_LOSS_DISPLAY",
    # Summary
    "GameSummaryData",
    "SummaryStats",
    "PhaseMistakeStats",
    "ReasonTagThresholds",
    "SkillPreset",
    "SKILL_PRESETS",
    "DEFAULT_SKILL_PRESET",
    "PRESET_ORDER",
    "AutoRecommendation",
    "UrgentMissConfig",
    "URGENT_MISS_CONFIGS",
    "SCORE_THRESHOLDS",
    "WINRATE_THRESHOLDS",
    "MistakeStreak",
    "SkillEstimation",
    # Reliability
    "ReliabilityStats",
    "RELIABILITY_VISITS_THRESHOLD",
    "RELIABILITY_RATIO",
    "UNRELIABLE_IMPORTANCE_SCALE",
    "SWING_SCORE_SIGN_BONUS",
    "SWING_WINRATE_CROSS_BONUS",
    "SWING_MAGNITUDE_WEIGHT",
    "STREAK_START_BONUS",
    "DIFFICULTY_MODIFIER_HARD",
    "DIFFICULTY_MODIFIER_ONLY_MOVE",
    "DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_BONUS",
    "DIFFICULTY_MODIFIER_ONLY_MOVE_LARGE_LOSS_THRESHOLD",
    "DIFFICULTY_MODIFIER_EASY",
    "DIFFICULTY_MODIFIER_NORMAL",
    "RELIABILITY_SCALE_THRESHOLDS",
    "MIN_COVERAGE_MOVES",
    "_CONFIDENCE_THRESHOLDS",
    # Difficulty
    "PVFilterConfig",
    "PV_FILTER_CONFIGS",
    "SKILL_TO_PV_FILTER",
    "DEFAULT_PV_FILTER_LEVEL",
    "DifficultyMetrics",
    "DIFFICULTY_UNKNOWN",
    "DIFFICULTY_MIN_VISITS",
    "DIFFICULTY_MIN_CANDIDATES",
    "POLICY_GAP_MAX",
    "TRANSITION_DROP_MAX",
    "DEFAULT_DIFFICULT_POSITIONS_LIMIT",
    "DEFAULT_MIN_MOVE_NUMBER",
    # Phase 154: KataGo error / LCB
    "SHORTTERM_SCORE_ERROR_MAX",
    "LCB_GAP_MAX",
    "ERROR_PRESSURE_WEIGHT",
    "LCB_GAP_WEIGHT",
    # Labels (lazy)
    "REASON_TAG_LABELS",
    "VALID_REASON_TAGS",
    "SKILL_PRESET_LABELS",
    "CONFIDENCE_LABELS",
]
