"""
katrain.core.analysis.presentation - 表示/フォーマット関数

このモジュールには表示・フォーマット用の関数が含まれます:
- ラベル取得関数（get_confidence_label, get_reason_tag_label）
- 証拠フォーマット関数（format_evidence_examples, select_representative_moves）
- 練習優先項目関数（get_practice_priorities_from_stats）
"""

from __future__ import annotations

from typing import (
    Callable,
    List,
    Optional,
)

from katrain.core.analysis.models import (
    CONFIDENCE_LABELS,
    ConfidenceLevel,
    MoveEval,
    PhaseMistakeStats,
    REASON_TAG_LABELS,
)


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
    """Get human-readable label for auto-confidence level.

    Args:
        confidence_value: "high", "medium", or "low"
        lang: Language code ("ja" or "en")

    Returns:
        Localized label string
    """
    if lang == "ja":
        return CONFIDENCE_LABELS.get(confidence_value, confidence_value)
    else:
        return confidence_value.capitalize()


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

    # Sort by score_loss descending, then move_number ascending for determinism
    sorted_moves = sorted(
        with_loss,
        key=lambda m: (-m.score_loss, m.move_number),
    )

    return sorted_moves[:max_count]


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
    """
    if not moves:
        return ""

    prefix = "例: " if lang == "ja" else "e.g.: "
    unit = "目" if lang == "ja" else " pts"

    parts = []
    for mv in moves:
        loss = mv.score_loss if mv.score_loss is not None else 0.0
        parts.append(f"#{mv.move_number} {mv.gtp or '-'} (-{loss:.1f}{unit})")

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
# __all__
# =============================================================================


__all__ = [
    "get_confidence_label",
    "get_auto_confidence_label",
    "get_important_moves_limit",
    "get_evidence_count",
    "get_reason_tag_label",
    "select_representative_moves",
    "format_evidence_examples",
    "get_practice_priorities_from_stats",
]
