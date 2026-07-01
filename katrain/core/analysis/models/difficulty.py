"""katrain.core.analysis.models.difficulty - PV filter config and difficulty metrics.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- PVFilterConfig + PV_FILTER_CONFIGS: PV filter settings per level
- SKILL_TO_PV_FILTER: skill_preset → pv_filter_level mapping
- DEFAULT_PV_FILTER_LEVEL
- DifficultyMetrics + DIFFICULTY_UNKNOWN: 3-factor difficulty decomposition
- DIFFICULTY_MIN_VISITS, DIFFICULTY_MIN_CANDIDATES: reliability guards
- POLICY_GAP_MAX, TRANSITION_DROP_MAX: normalization parameters
- DEFAULT_DIFFICULT_POSITIONS_LIMIT, DEFAULT_MIN_MOVE_NUMBER
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# =============================================================================
# PV Filter (Phase 11)
# =============================================================================


@dataclass(frozen=True)
class PVFilterConfig:
    """候補手フィルタの設定（Phase 11）。

    Attributes:
        max_candidates: フィルタ後の最大候補手数（best_moveは別枠で上限外）
        max_points_lost: この値以下の損失の手のみ表示（<=比較）
        max_pv_length: この値以下のPV長の手のみ表示（<=比較）
    """

    max_candidates: int
    max_points_lost: float
    max_pv_length: int


# PVFilterLevelごとのプリセット設定
PV_FILTER_CONFIGS: dict[str, PVFilterConfig] = {
    "weak": PVFilterConfig(
        max_candidates=15,
        max_points_lost=4.0,
        max_pv_length=15,
    ),
    "medium": PVFilterConfig(
        max_candidates=8,
        max_points_lost=2.0,
        max_pv_length=10,
    ),
    "strong": PVFilterConfig(
        max_candidates=4,
        max_points_lost=1.0,
        max_pv_length=6,
    ),
}

# skill_preset から pv_filter_level へのマッピング（AUTO用）
# skill_presetは「ミス判定の厳しさ」: 激甘=大きな損失のみ指摘、激辛=小さな損失も指摘
# PVフィルタは逆方向: 激甘→候補手多め(WEAK)、激辛→候補手少なめ(STRONG)
SKILL_TO_PV_FILTER: dict[str, str] = {
    "relaxed": "weak",  # 激甘 → 候補手多め
    "beginner": "weak",  # 甘口 → 候補手多め
    "standard": "medium",  # 標準 → 標準
    "advanced": "strong",  # 辛口 → 候補手少なめ
    "pro": "strong",  # 激辛 → 候補手少なめ
}

DEFAULT_PV_FILTER_LEVEL = "auto"


# =============================================================================
# Phase 12: 難易度分解（Difficulty Metrics）
# =============================================================================


@dataclass(frozen=True)
class DifficultyMetrics:
    """局面難易度の3分解メトリクス（Phase 12）。

    MuZero風の難易度分解を提供。v1は難所抽出用のセンサーとして使用。
    「採点」ではなく、同一棋譜内の相対比較に使用。

    Attributes:
        policy_difficulty: 迷いやすさ（候補が拮抗）。0-1、高いほど難。
        transition_difficulty: 崩れやすさ（一手のミスが致命傷）。0-1、高いほど難。
        state_difficulty: 盤面の複雑さ。v1は常に0（将来用）。
        overall_difficulty: 合成値（抽出・表示の優先度用）。0-1。
        error_pressure: KataGo の短期 error 指標（Phase 154）。KataGo も読み切れない度合い。0-1。
        lcb_gap: 最善手と次善手の LCB 差（Phase 154）。KataGo の候補手信頼度差。0-1。
        is_reliable: 信頼性フラグ（visits/候補数が十分か）。
        is_unknown: UNKNOWN状態フラグ。欠損/計算不可を示す。
        debug_factors: 計算の内訳（デバッグ用、オプション）。

    Note:
        欠損時は DIFFICULTY_UNKNOWN（モジュールレベル定数）を使用。
        is_unknown フラグで判定（`is` 比較より堅牢）。
        error_pressure / lcb_gap は KataGo 生データの欠損時は None。
    """

    policy_difficulty: float
    transition_difficulty: float
    state_difficulty: float  # v1: always 0.0
    overall_difficulty: float
    error_pressure: float | None = None  # Phase 154
    lcb_gap: float | None = None  # Phase 154
    is_reliable: bool = False
    is_unknown: bool = False
    debug_factors: dict[str, Any] | None = None


# モジュールレベル定数（frozen dataclass + ClassVar 問題を回避）
DIFFICULTY_UNKNOWN = DifficultyMetrics(
    policy_difficulty=0.0,
    transition_difficulty=0.0,
    state_difficulty=0.0,
    overall_difficulty=0.0,
    error_pressure=None,
    lcb_gap=None,
    is_reliable=False,
    is_unknown=True,
    debug_factors={"reason": "unknown"},
)


# === Phase 12: 難易度計算の定数 ===

# 信頼性ガードの閾値
DIFFICULTY_MIN_VISITS: int = 500  # 最低探索数（root_visits が必要）
DIFFICULTY_MIN_CANDIDATES: int = 2  # 最低候補手数（計算可能な最小値）

# Policy難易度の正規化パラメータ
POLICY_GAP_MAX: float = 5.0  # この差（目数）以上は「迷いなし」(difficulty=0)

# Transition難易度の正規化パラメータ
TRANSITION_DROP_MAX: float = 8.0  # Top1→Top2の落差がこれ以上で最大難易度

# === Phase 154: KataGo error / LCB 系の正規化パラメータ ===

# 短期 error 系の最大値（KataGo 標準の shorttermScoreError のおおよその上限）
SHORTTERM_SCORE_ERROR_MAX: float = 5.0  # これ以上で error_pressure=1.0

# LCB 差の最大値（最善手と次善手の LCB 差がこの値で lcb_gap=1.0）
LCB_GAP_MAX: float = 2.0  # LCB は utility スケール（通常 0-2 程度）

# overall 合成時の重み（KataGo の不確実性を加成）
ERROR_PRESSURE_WEIGHT: float = 0.15
LCB_GAP_WEIGHT: float = 0.15

# 難所抽出のデフォルト設定
DEFAULT_DIFFICULT_POSITIONS_LIMIT: int = 10
DEFAULT_MIN_MOVE_NUMBER: int = 10  # 序盤を除外
