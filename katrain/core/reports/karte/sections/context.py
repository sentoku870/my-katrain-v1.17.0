"""KarteContext dataclass - explicit context for section generators.

This replaces the closure variables previously used in _build_karte_json_string_impl().
All section generators receive this context explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.analysis.models import (
        ConfidenceLevel,
        EvalSnapshot,
        ImportantMoveSettings,
        MoveEval,
    )


@dataclass(frozen=True)
class KarteContext:
    """Explicit context for karte section generators.

    This dataclass replaces closure variables, making dependencies explicit
    and enabling easier testing and maintenance.

    Phase 238: removed three fields that were always populated with
    ``None`` and never read by any section generator:

    - ``auto_recommendation: AutoRecommendation | None`` (was always None)
    - ``pacing_map: dict[int, PacingMetrics] | None`` (was always None)
    - ``histogram: list[Any] | None`` (was always None)

    All section generators (``weakness_hypothesis_for``,
    ``mistake_streaks_for``, ``critical_3_section_for``,
    ``data_quality_section``) only access the remaining fields, so
    the dataclass can stay frozen and its API is now half the size.

    The corresponding ``TYPE_CHECKING`` imports
    (``AutoRecommendation``, ``PacingMetrics``) were also removed.
    """

    # Core data
    snapshot: EvalSnapshot
    game: Any  # Game object (duck-typed to avoid circular import)

    # Thresholds and presets
    thresholds: list[float]  # Raw thresholds from config
    effective_thresholds: tuple[float, float, float]  # Score thresholds for classification
    effective_preset: str  # "beginner" / "standard" / "advanced"

    # Computed metadata
    confidence_level: ConfidenceLevel

    # Board and player info
    board_x: int
    board_y: int
    pb: str  # Black player name
    pw: str  # White player name
    focus_color: str | None  # "B" / "W" / None

    # Important moves
    important_moves: list[MoveEval]
    total_moves: int
    settings: ImportantMoveSettings  # Important move settings

    # Parameters
    skill_preset: str
    target_visits: int | None
    lang: str  # "ja" or "en" (ISO codes, matching existing karte output)
