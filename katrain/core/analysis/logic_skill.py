"""Skill preset, auto-strictness, and skill estimation functions.

Phase 144-C: Extracted from logic.py (1494 lines → 6 focused modules).

Contains:
- get_skill_preset: Skill preset lookup with fallback
- get_urgent_miss_config: Urgent miss config lookup with fallback
- _distance_from_range: Distance calculation for auto-strictness
- recommend_auto_strictness: Auto-recommend strictness preset
- validate_reason_tag: Reason tag validation
- estimate_skill_level_from_tags: Skill estimation from reason tags
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from katrain.core.analysis.models import (
    DEFAULT_SKILL_PRESET,
    PRESET_ORDER,
    RANK_TO_PRESET_DEFAULT,
    SKILL_PRESETS,
    URGENT_MISS_CONFIGS,
    AutoConfidence,
    AutoRecommendation,
    SkillEstimation,
    SkillPreset,
    UrgentMissConfig,
)
from katrain.core.analysis.models.move_eval import MoveEval
from katrain.core.analysis.presentation import VALID_REASON_TAGS
from katrain.common.rank import Rank, canonical_rank_key

if TYPE_CHECKING:
    pass


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
# Phase 229: Rank -> skill preset bridge
# =============================================================================


def rank_to_skill_preset(rank: Rank | str | None) -> str:
    """Map a :py:class:`~katrain.common.rank.Rank` (or its raw string) to a skill preset.

    Accepts either a parsed ``Rank`` instance or a raw rank string in any
    notation supported by :func:`katrain.common.rank.canonical_rank_key`
    (ASCII ``"5k"`` / ``"7d"``, kanji ``"4段"`` / ``"5級"``, full-width
    digits, ``"4kyu"`` / ``"5dan"`` synonyms, etc.).

    Returns ``DEFAULT_SKILL_PRESET`` (``"standard"``) when the input is
    ``None`` / empty / unrecognised, so callers can chain without an
    explicit default.

    This is the bridge between the user-facing ``general/player_rank``
    setting (added in Phase 229) and the analysis-side ``skill_preset``
    thresholds: ``resolve_skill_preset()`` consults this function when
    the user has set ``player_rank`` but not an explicit preset override.
    """
    if rank is None:
        return DEFAULT_SKILL_PRESET
    if isinstance(rank, str):
        key = canonical_rank_key(rank)
        if not key:
            return DEFAULT_SKILL_PRESET
        from katrain.common.rank import _RANK_ORDER

        return RANK_TO_PRESET_DEFAULT.get(_RANK_ORDER[key], DEFAULT_SKILL_PRESET)
    return RANK_TO_PRESET_DEFAULT.get(rank.kyu_dan, DEFAULT_SKILL_PRESET)


def resolve_skill_preset(
    preset_override: str | None,
    player_rank: str | None,
    *,
    default: str | None = None,
) -> str:
    """Resolve the effective skill preset name (Phase 229 unification).

    Priority chain:

    1. ``preset_override`` if set and not ``"auto"`` (power user override).
    2. ``player_rank`` if set (auto-derive via :func:`rank_to_skill_preset`).
    3. ``default`` (defaults to :data:`DEFAULT_SKILL_PRESET` = ``"standard"``).

    Args:
        preset_override: Value of ``general/skill_preset``. ``None`` /
            empty / ``"auto"`` are all treated as "no override".
        player_rank: Value of ``general/player_rank``.  Any notation
            accepted by :func:`katrain.common.rank.canonical_rank_key`.
        default: Fallback when both override and rank are missing or
            unrecognised.  Defaults to ``DEFAULT_SKILL_PRESET``.

    Returns:
        A key in :data:`SKILL_PRESETS`.  Always returns a known preset
        name (never raises).

    Note:
        The ``"auto"`` value is *kept* here for backward compatibility
        with existing config files (Phase 226-J validation uses it), but
        Phase 229-C removes it from the UI.  All callers should treat
        ``"auto"`` the same as ``None`` from this point on.
    """
    fallback = default if default is not None else DEFAULT_SKILL_PRESET
    if preset_override and preset_override != "auto":
        # Validate: if the override is not in SKILL_PRESETS, fall through.
        if preset_override in SKILL_PRESETS:
            return preset_override
    if player_rank:
        derived = rank_to_skill_preset(player_rank)
        if derived and derived in SKILL_PRESETS:
            return derived
    return fallback


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
    # Lazy import to avoid circular dependency with logic_reliability
    from katrain.core.analysis.logic_reliability import compute_reliability_stats

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
