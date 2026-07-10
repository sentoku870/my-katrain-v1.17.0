"""katrain.core.analysis.models.enums - Enum definitions.

Phase 144-B: Extracted from models.py (1230 lines -> 6 focused modules).
Phase 171: KataGo-only path. ``EngineType.LEELA`` removed; only
``KATAGO`` and ``UNKNOWN`` survive. ``get_analysis_engine`` returns
``"katago"`` unconditionally, and the ``needs_leela_warning`` /
``LEELA_FAST_VISITS_MIN`` plumbing is removed.

Contains:
- 6 enum types (MistakeCategory, PVFilterLevel, PositionDifficulty,
  AutoConfidence, ConfidenceLevel, AnalysisStrength, EngineType)
- Engine visit resolution (resolve_visits) + constants
- KataGo-only analysis_engine helper
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Any

_log = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class MistakeCategory(Enum):
    """ミスの大きさを4段階で分類するカテゴリ。"""

    GOOD = "good"  # 実質問題なし
    INACCURACY = "inaccuracy"  # 軽い損
    MISTAKE = "mistake"  # はっきり損
    BLUNDER = "blunder"  # 大きな損

    def is_error(self) -> bool:
        """GOOD 以外ならミス扱い、といった判定用の補助メソッド。"""
        return self is not MistakeCategory.GOOD


class PVFilterLevel(Enum):
    """候補手フィルタのレベル（Phase 11）。

    盤面に表示するTop Movesをフィルタリングするための設定レベル。
    難解なPV（長い読み筋）や大きな損失の手を除外して、
    ユーザーにとって理解しやすい候補手のみを表示する。
    """

    OFF = "off"  # フィルタなし（全候補手を表示）
    WEAK = "weak"  # 緩め（候補手多め、激甘〜甘口向け）
    MEDIUM = "medium"  # 標準
    STRONG = "strong"  # 厳しめ（候補手少なめ、辛口〜激辛向け）
    AUTO = "auto"  # Skill Presetに連動


class PositionDifficulty(Enum):
    """局面難易度を表すラベル。"""

    EASY = "easy"  # 良い手が多く、多少ズレても致命傷になりにくい
    NORMAL = "normal"  # 標準的な難易度
    HARD = "hard"  # 良い手が少なく、正解の幅が狭い
    ONLY_MOVE = "only"  # ほぼ「この一手」に近い局面
    UNKNOWN = "unknown"  # 候補手情報が無いなどで評価不能


class AutoConfidence(Enum):
    """Confidence level for auto-strictness recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceLevel(Enum):
    """Confidence level for analysis results.

    Used to control section visibility and wording in Karte/Summary output.
    """

    HIGH = auto()  # Full output, assertive wording
    MEDIUM = auto()  # Reduced output, hedged wording
    LOW = auto()  # Minimal output, reference-only, re-analysis recommended


# =============================================================================
# Analysis Strength (Phase 30)
# =============================================================================


class AnalysisStrength(Enum):
    """解析強度レベル（エンジン共通抽象）。

    - QUICK: 高速解析（fast_visits使用、概要把握向け）
    - DEEP: 詳細解析（max_visits使用、精密評価向け）

    Note:
        Phase 30で追加。Phase 31以降でエンジン統合に使用予定。
        This is NOT related to player skill presets (G0-G4).
    """

    QUICK = "quick"
    DEEP = "deep"

    @property
    def is_fast(self) -> bool:
        """高速解析モードかどうか"""
        return self == AnalysisStrength.QUICK


class EngineType(Enum):
    """解析エンジン種別。

    MoveEvalから推定するために使用。
    - KATAGO: KataGo解析（score_loss設定あり、Phase 171 以降は事実上これだけ）
    - UNKNOWN: エンジン不明

    Note:
        Phase 32で追加。Phase 171 で ``LEELA`` を廃止し、KataGo 専用化。
    """

    KATAGO = "katago"
    UNKNOWN = "unknown"


# =============================================================================
# Analysis Engine Selection (Phase 33)
# =============================================================================

# Phase 171: KataGo-only. Previously a frozenset of {"katago", "leela"}.
VALID_ANALYSIS_ENGINES: frozenset[str] = frozenset({EngineType.KATAGO.value})
DEFAULT_ANALYSIS_ENGINE: str = EngineType.KATAGO.value


def get_analysis_engine(engine_config: dict[str, Any]) -> str:
    """設定から解析エンジンを取得する。

    Args:
        engine_config: engine セクションの設定dict

    Returns:
        str: 常に ``"katago"``（後方互換のため dict 受領シグネチャは維持）

    Note:
        Phase 171 で KataGo 専用化。``analysis_engine`` 設定値は
        読み込むが無視して ``"katago"`` を返す。古い設定に
        ``"leela"`` があっても自動的に KataGo にフォールバックする。
    """
    value = engine_config.get("analysis_engine", DEFAULT_ANALYSIS_ENGINE)
    if not isinstance(value, str) or value not in VALID_ANALYSIS_ENGINES:
        _log.warning(
            "Invalid analysis_engine %r, falling back to %r",
            value,
            DEFAULT_ANALYSIS_ENGINE,
        )
    return DEFAULT_ANALYSIS_ENGINE


# Engine-specific default visits values.
# These are HARD SAFETY DEFAULTS used when config.json is missing keys.
# User-facing defaults should be set in config.json itself.
ENGINE_VISITS_DEFAULTS: dict[str, dict[str, int]] = {
    "katago": {"max_visits": 500, "fast_visits": 25},
}


def resolve_visits(
    strength: AnalysisStrength,
    engine_config: dict[str, Any],
    engine_type: str = "katago",
) -> int:
    """解析強度からvisits数を解決する。

    Args:
        strength: 解析強度（QUICK/DEEP）
        engine_config: エンジン設定dict（max_visits, fast_visitsを含む可能性）
        engine_type: エンジン種別（常に ``"katago"``。後方互換のため受領する）

    Returns:
        int: visits数（1以上保証）

    Behavior:
        - engine_configにキーが存在しない場合はデフォルト値を使用
        - 不正な値（文字列、None等）の場合もデフォルトにフォールバック（防御的）
        - 文字列の場合はstrip()後にint変換を試行

    Note:
        この関数はconfig.jsonからの値読み取り用。単一の強度に対する値解決のみ行う。
        fast_visits <= max_visits の整合性チェックは呼び出し側の責務。
    """
    defaults = ENGINE_VISITS_DEFAULTS.get(engine_type, ENGINE_VISITS_DEFAULTS["katago"])
    key = "fast_visits" if strength == AnalysisStrength.QUICK else "max_visits"

    raw_value = engine_config.get(key)
    if raw_value is None:
        return defaults[key]

    try:
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
            if not raw_value:
                return defaults[key]
        visits = int(raw_value)
        return max(1, visits)
    except (ValueError, TypeError):
        return defaults[key]
