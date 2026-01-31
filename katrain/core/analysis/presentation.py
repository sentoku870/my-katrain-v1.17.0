"""
katrain.core.analysis.presentation - 表示/フォーマット関数

このモジュールには表示・フォーマット用の関数が含まれます:
- ラベル取得関数（get_confidence_label, get_reason_tag_label）
- 証拠フォーマット関数（format_evidence_examples, select_representative_moves）
- 練習優先項目関数（get_practice_priorities_from_stats）
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)

if TYPE_CHECKING:
    from katrain.core.analysis.models import DifficultyMetrics

from katrain.core.analysis.models import (
    ConfidenceLevel,
    EngineType,
    MistakeCategory,
    MoveEval,
    PhaseMistakeStats,
    get_canonical_loss_from_move,
)
from katrain.core.analysis.logic_loss import detect_engine_type


# =============================================================================
# Label Constants (moved from models.py in PR#56)
# =============================================================================


# Japanese labels for skill presets
SKILL_PRESET_LABELS: Dict[str, str] = {
    "relaxed": "激甘",
    "beginner": "甘口",
    "standard": "標準",
    "advanced": "辛口",
    "pro": "激辛",
    "auto": "自動",
}

# Japanese labels for confidence levels
CONFIDENCE_LABELS: Dict[str, str] = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

# 理由タグの日本語ラベル（カルテ・サマリーで使用）
REASON_TAG_LABELS: Dict[str, str] = {
    "atari": "アタリ (atari)",
    "low_liberties": "呼吸点少 (low liberties)",
    "cut_risk": "切断リスク (cut risk)",
    "need_connect": "連絡必要 (need connect)",
    "thin": "薄い形 (thin)",
    "chase_mode": "追込モード (chase mode)",
    "too_many_choices": "候補多数 (many choices)",
    "endgame_hint": "ヨセ局面 (endgame)",
    "heavy_loss": "大損失 (heavy loss)",
    "reading_failure": "読み抜け (reading failure)",
    "unknown": "不明 (unknown)",
}

# All valid reason tags that can be emitted
VALID_REASON_TAGS: Set[str] = set(REASON_TAG_LABELS.keys())


# =============================================================================
# Confidence label
# =============================================================================


def get_confidence_label(level: ConfidenceLevel, lang: str = "ja") -> str:
    """Get human-readable label for confidence level.

    Args:
        level: ConfidenceLevel enum value
        lang: Language code ("ja" or "en")

    Returns:
        Localized label string
    """
    labels = {
        "ja": {
            ConfidenceLevel.HIGH: "信頼度: 高",
            ConfidenceLevel.MEDIUM: "信頼度: 中",
            ConfidenceLevel.LOW: "信頼度: 低",
        },
        "en": {
            ConfidenceLevel.HIGH: "Confidence: High",
            ConfidenceLevel.MEDIUM: "Confidence: Medium",
            ConfidenceLevel.LOW: "Confidence: Low",
        },
    }
    return labels.get(lang, labels["en"]).get(level, str(level))


def get_auto_confidence_label(confidence_value: str, lang: str = "ja") -> str:
    """Get human-readable label for auto-strictness recommendation confidence.

    This label (推定確度/Certainty) differs from data reliability (信頼度/Confidence):
    - 推定確度: How confident the auto-strictness recommendation is
    - 信頼度: How reliable the data is based on visits/analysis depth

    Args:
        confidence_value: "high", "medium", or "low"
        lang: Language code ("ja" or "en")

    Returns:
        Localized label string with full prefix (e.g., "推定確度: 高")
    """
    # Phase 53: Use 推定確度 (certainty) not 信頼度 (reliability) for auto-strictness
    labels = {
        "ja": {"high": "推定確度: 高", "medium": "推定確度: 中", "low": "推定確度: 低"},
        "en": {"high": "Certainty: High", "medium": "Certainty: Medium", "low": "Certainty: Low"},
    }
    return labels.get(lang, labels["ja"]).get(confidence_value, confidence_value)


# =============================================================================
# Important moves limit
# =============================================================================


def get_important_moves_limit(level: ConfidenceLevel) -> int:
    """Get the maximum number of important moves to show based on confidence.

    Args:
        level: ConfidenceLevel enum value

    Returns:
        Maximum number of important moves to display
    """
    limits = {
        ConfidenceLevel.HIGH: 20,
        ConfidenceLevel.MEDIUM: 10,
        ConfidenceLevel.LOW: 5,
    }
    return limits.get(level, 5)


# =============================================================================
# Evidence count
# =============================================================================


def get_evidence_count(level: ConfidenceLevel) -> int:
    """Get the number of evidence examples to show based on confidence level.

    Args:
        level: ConfidenceLevel enum value

    Returns:
        Number of examples per category (HIGH: 3, MEDIUM: 2, LOW: 1)
    """
    counts = {
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.LOW: 1,
    }
    return counts.get(level, 1)


# =============================================================================
# Reason tag label
# =============================================================================


def get_reason_tag_label(tag: str, fallback_to_raw: bool = True) -> str:
    """Get the display label for a reason tag.

    Args:
        tag: The reason tag key
        fallback_to_raw: If True, return the raw tag if not found.
                        If False, return "??? (tag)" for undefined tags.

    Returns:
        The display label for the tag
    """
    if tag in REASON_TAG_LABELS:
        return REASON_TAG_LABELS[tag]
    if fallback_to_raw:
        return tag
    return f"??? ({tag})"


# =============================================================================
# Mistake category label (Phase 66)
# =============================================================================


def get_mistake_category_label(category: MistakeCategory) -> str:
    """Get localized label for mistake category.

    Uses current app language via i18n._().
    Key format: "mistake:{category.value}" (category.value is lowercase)

    Args:
        category: MistakeCategory enum value

    Returns:
        Localized label (e.g., "大悪手" for BLUNDER in Japanese)
    """
    from katrain.core.lang import i18n

    key = f"mistake:{category.value}"  # e.g., "mistake:blunder"
    return i18n._(key)


# =============================================================================
# Evidence selection and formatting
# =============================================================================


def select_representative_moves(
    moves: List[MoveEval],
    *,
    max_count: int = 3,
    category_filter: Optional[Callable[[MoveEval], bool]] = None,
) -> List[MoveEval]:
    """Select representative moves for evidence attachment.

    Uses score_loss as the canonical loss metric. Moves with score_loss=None
    are skipped (never converted to 0.0).

    Args:
        moves: List of MoveEval objects
        max_count: Maximum number of moves to return
        category_filter: Optional filter function (e.g., lambda mv: mv.tag == "opening")

    Returns:
        List of representative MoveEval objects, sorted by score_loss descending,
        with move_number ascending as tie-breaker for deterministic ordering.
    """
    # Filter moves if filter function provided
    filtered = moves if category_filter is None else [m for m in moves if category_filter(m)]

    # Skip moves with score_loss=None (NEVER convert to 0.0)
    with_loss = [m for m in filtered if m.score_loss is not None]

    def _sort_key(m: MoveEval) -> tuple[float, int]:
        # Invariant: with_loss only contains moves where score_loss is not None
        assert m.score_loss is not None
        return (-m.score_loss, m.move_number)

    # Sort by score_loss descending, then move_number ascending for determinism
    sorted_moves = sorted(with_loss, key=_sort_key)

    return sorted_moves[:max_count]


# =============================================================================
# Loss label formatting (Phase 32)
# =============================================================================


def format_loss_label(
    loss: float,
    engine_type: EngineType,
    lang: str = "ja",
) -> str:
    """損失値のラベルをエンジン種別に応じてフォーマット。

    Args:
        loss: 損失値（>= 0 を想定、負の場合は 0 扱い）
        engine_type: エンジン種別
        lang: 言語コード ("ja" or "en")

    Returns:
        フォーマット済みラベル

    Examples:
        KataGo JA: "-3.5目", "0.0目"
        KataGo EN: "-3.5 pts", "0.0 pts"
        Leela JA:  "-3.5目(推定)", "0.0目(推定)"
        Leela EN:  "-3.5 pts(est.)", "0.0 pts(est.)"

    Note:
        - loss <= 0.0 の場合はマイナス符号なし（"0.0目"）
        - 正の損失のみマイナス符号付き（"-3.5目"）
        - UNKNOWN は KataGo と同じフォーマット
    """
    # 単位とサフィックスを言語別に定義
    if lang == "ja":
        unit = "目"
        suffix = "(推定)" if engine_type == EngineType.LEELA else ""
    else:
        unit = " pts"
        suffix = "(est.)" if engine_type == EngineType.LEELA else ""

    # ゼロ以下は符号なし
    if loss <= 0.0:
        return f"0.0{unit}{suffix}"

    # 正の損失は符号付き
    return f"-{loss:.1f}{unit}{suffix}"


def format_evidence_examples(
    moves: List[MoveEval],
    *,
    lang: str = "ja",
) -> str:
    """Format evidence moves as a compact inline string.

    Args:
        moves: List of MoveEval objects (already selected as representatives)
        lang: Language code ("ja" or "en")

    Returns:
        Formatted string like "例: #12 Q16 (-8.5目), #45 R4 (-4.2目)"
        or "e.g.: #12 Q16 (-8.5 pts), #45 R4 (-4.2 pts)"
        For Leela: "例: #12 Q16 (-8.5目(推定)), #45 R4 (-4.2目(推定))"

    Note:
        Phase 32: Updated to use format_loss_label() for engine-aware formatting.
    """
    if not moves:
        return ""

    prefix = "例: " if lang == "ja" else "e.g.: "

    parts = []
    for mv in moves:
        engine_type = detect_engine_type(mv)
        loss = get_canonical_loss_from_move(mv)
        loss_label = format_loss_label(loss, engine_type, lang=lang)
        parts.append(f"#{mv.move_number} {mv.gtp or '-'} ({loss_label})")

    return prefix + ", ".join(parts)


# =============================================================================
# Practice priorities
# =============================================================================


def get_practice_priorities_from_stats(
    stats: PhaseMistakeStats,
    *,
    max_priorities: int = 3,
) -> List[str]:
    """
    PhaseMistakeStats から練習優先項目を導出する。

    SummaryStats.get_practice_priorities() と同等のロジックだが、
    単局用にも使用できるよう分離した関数。

    Args:
        stats: 集計結果
        max_priorities: 最大優先項目数

    Returns:
        優先項目のリスト（日本語）
    """
    priorities = []
    phase_name_ja = {"opening": "序盤", "middle": "中盤", "yose": "ヨセ"}
    cat_names_ja = {
        "BLUNDER": "大悪手",
        "MISTAKE": "悪手",
        "INACCURACY": "軽微なミス",
    }

    # 1. Phase × Mistake で最悪の組み合わせを特定（GOODは除外）
    non_good_losses = [
        (k, v) for k, v in stats.phase_mistake_loss.items()
        if k[1] != "GOOD" and v > 0
    ]
    if non_good_losses:
        sorted_combos = sorted(non_good_losses, key=lambda x: x[1], reverse=True)
        # 上位2つを抽出
        for i, (key, loss) in enumerate(sorted_combos[:2]):
            phase, category = key
            count = stats.phase_mistake_counts.get(key, 0)
            priorities.append(
                f"**{phase_name_ja.get(phase, phase)}の{cat_names_ja.get(category, category)}を減らす**"
                f"（{count}回、損失{loss:.1f}目）"
            )

    # フォールバック: Phase別損失から最悪のフェーズを提案
    if not priorities and stats.phase_loss:
        worst_phase = max(stats.phase_loss.items(), key=lambda x: x[1], default=None)
        if worst_phase and worst_phase[1] > 0:
            priorities.append(
                f"**{phase_name_ja.get(worst_phase[0], worst_phase[0])}の大きなミスを減らす**"
                f"（損失: {worst_phase[1]:.1f}目）"
            )

    return priorities[:max_priorities]


# =============================================================================
# Difficulty Metrics Formatting (Phase 12.5)
# =============================================================================


def get_difficulty_label(overall: float) -> str:
    """overall値から難易度ラベルを返す。

    Args:
        overall: 0-1の難易度値

    Returns:
        "易" / "中" / "難"
    """
    if overall < 0.3:
        return "易"
    elif overall < 0.6:
        return "中"
    else:
        return "難"


def format_difficulty_metrics(metrics: "DifficultyMetrics") -> List[str]:
    """DifficultyMetricsを表示用文字列リストに変換。

    Args:
        metrics: 難易度メトリクス

    Returns:
        表示用の文字列リスト。is_unknownの場合は空リスト。
    """
    if metrics.is_unknown:
        return []  # unknown時は表示しない

    label = get_difficulty_label(metrics.overall_difficulty)
    reliability_marker = "" if metrics.is_reliable else "⚠"

    lines = [
        f"局面難易度: {label}（{metrics.overall_difficulty:.2f}）{reliability_marker}",
        f"  迷い={metrics.policy_difficulty:.2f} 崩れ={metrics.transition_difficulty:.2f}",
    ]

    if not metrics.is_reliable:
        lines[-1] += " [信頼度低]"

    return lines


# =============================================================================
# __all__
# =============================================================================


__all__ = [
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
    # Difficulty Metrics (Phase 12.5)
    "get_difficulty_label",
    "format_difficulty_metrics",
]
