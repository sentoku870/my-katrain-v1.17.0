"""KarteContext dataclass - explicit context for section generators.

This replaces the closure variables previously used in _build_karte_report_impl().
All section generators receive this context explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.analysis.models import (
        AutoRecommendation,
        ConfidenceLevel,
        EvalSnapshot,
        ImportantMoveSettings,
        MoveEval,
    )
    from katrain.core.analysis.time import PacingMetrics


@dataclass(frozen=True)
class KarteContext:
    """Explicit context for karte section generators.

    This dataclass replaces closure variables, making dependencies explicit
    and enabling easier testing and maintenance.
    """

    # Core data
    snapshot: EvalSnapshot
    game: Any  # Game object (duck-typed to avoid circular import)

    # Thresholds and presets
    thresholds: list[float]  # Raw thresholds from config
    effective_thresholds: tuple[float, float, float]  # Score thresholds for classification
    effective_preset: str  # "beginner" / "standard" / "advanced"
    auto_recommendation: AutoRecommendation | None

    # Computed metadata
    confidence_level: ConfidenceLevel
    pacing_map: dict[int, PacingMetrics] | None
    histogram: list[Any] | None

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
