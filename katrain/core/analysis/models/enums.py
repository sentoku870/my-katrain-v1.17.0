"""katrain.core.analysis.models.enums - Enum definitions and engine configuration.

Phase 144-B: Extracted from models.py (1230 lines → 6 focused modules).

Contains:
- 7 enum types (MistakeCategory, PVFilterLevel, PositionDifficulty,
  AutoConfidence, ConfidenceLevel, AnalysisStrength, EngineType)
- Analysis engine selection helpers (get_analysis_engine, needs_leela_warning)
- Engine visit resolution (resolve_visits) + constants
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
    - KATAGO: KataGo解析（score_loss設定あり）
    - LEELA: Leela Zero解析（leela_loss_est設定あり）
    - UNKNOWN: エンジン不明（両方None）

    Note:
        Phase 32で追加。損失ラベルの区別表示に使用。
    """

    KATAGO = "katago"
    LEELA = "leela"
    UNKNOWN = "unknown"


# =============================================================================
# Analysis Engine Selection (Phase 33)
# =============================================================================

# Derive from EngineType to prevent drift (EngineType.UNKNOWN excluded)
VALID_ANALYSIS_ENGINES: frozenset[str] = frozenset(
    {
        EngineType.KATAGO.value,
        EngineType.LEELA.value,
    }
)
DEFAULT_ANALYSIS_ENGINE: str = EngineType.KATAGO.value


def get_analysis_engine(engine_config: dict[str, Any]) -> str:
    """設定から解析エンジンを取得する。

    Args:
        engine_config: engine セクションの設定dict

    Returns:
        str: "katago" or "leela"（無効値/未設定は "katago" にフォールバック）

    Behavior:
        - キーなし: DEFAULT_ANALYSIS_ENGINE を返す
        - 無効値（大文字、typo、None、非文字列等）: warning log + フォールバック
        - 大文字小文字は厳格（"LEELA" は無効）

    Note:
        Phase 33で追加。Phase 34でUI連携・エンジン起動ロジックに使用予定。
        leela/enabled との整合性チェックは Phase 34 の責務。
    """
    value = engine_config.get("analysis_engine", DEFAULT_ANALYSIS_ENGINE)
    # Type guard: unhashable types (list, dict) would crash `in frozenset`
    if not isinstance(value, str) or value not in VALID_ANALYSIS_ENGINES:
        _log.warning(
            "Invalid analysis_engine %r, falling back to %r",
            value,
            DEFAULT_ANALYSIS_ENGINE,
        )
        return DEFAULT_ANALYSIS_ENGINE
    return value


def needs_leela_warning(selected_engine: str, leela_enabled: bool) -> bool:
    """Leela選択時にLeela未有効の警告が必要かどうかを判定する。

    Args:
        selected_engine: 選択されたエンジン ("katago" or "leela")
        leela_enabled: Leelaが有効かどうか

    Returns:
        True if warning should be shown (Leela selected but not enabled)

    Note:
        Phase 34で追加。UIとテストで共有するための純粋関数。
    """
    return selected_engine == EngineType.LEELA.value and not leela_enabled


# Engine-specific default visits values.
# These are HARD SAFETY DEFAULTS used when config.json is missing keys.
# User-facing defaults should be set in config.json itself.
ENGINE_VISITS_DEFAULTS: dict[str, dict[str, int]] = {
    "katago": {"max_visits": 500, "fast_visits": 25},
    "leela": {"max_visits": 1000, "fast_visits": 200},
}

# UI minimum for leela fast_visits (practical lower bound for meaningful analysis)
LEELA_FAST_VISITS_MIN = 50


def resolve_visits(
    strength: AnalysisStrength,
    engine_config: dict[str, Any],
    engine_type: str = "katago",
) -> int:
    """解析強度からvisits数を解決する。

    Args:
        strength: 解析強度（QUICK/DEEP）
        engine_config: エンジン設定dict（max_visits, fast_visitsを含む可能性）
        engine_type: エンジン種別 ("katago" or "leela")

    Returns:
        int: visits数（1以上保証）

    Behavior:
        - engine_configにキーが存在しない場合はデフォルト値を使用
        - 不明なengine_typeの場合はkatagoのデフォルトにフォールバック（warning log出力）
        - 不正な値（文字列、None等）の場合もデフォルトにフォールバック（防御的）
        - 文字列の場合はstrip()後にint変換を試行

    Note:
        この関数はconfig.jsonからの値読み取り用。単一の強度に対する値解決のみ行う。
        fast_visits <= max_visits の整合性チェックは呼び出し側の責務。
        UIでのユーザー入力バリデーション（例: Leelaは50以上）も呼び出し側の責務。
    """
    if engine_type not in ENGINE_VISITS_DEFAULTS:
        _log.warning("Unknown engine_type '%s', falling back to katago defaults", engine_type)
    defaults = ENGINE_VISITS_DEFAULTS.get(engine_type, ENGINE_VISITS_DEFAULTS["katago"])
    key = "fast_visits" if strength == AnalysisStrength.QUICK else "max_visits"

    raw_value = engine_config.get(key)
    if raw_value is None:
        return defaults[key]

    try:
        # 文字列の場合はstrip()してから変換
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
            if not raw_value:  # 空文字列
                return defaults[key]
        visits = int(raw_value)
        return max(1, visits)
    except (ValueError, TypeError):
        # 不正な値の場合はデフォルトにフォールバック
        return defaults[key]
