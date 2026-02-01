"""KarteContext dataclass - explicit context for section generators.

This replaces the closure variables previously used in _build_karte_report_impl().
All section generators receive this context explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from katrain.core.analysis.models import (
        ConfidenceLevel,
        EvalSnapshot,
        ImportantMoveSettings,
        MoveEval,
    )
    from katrain.core.analysis.time import PacingMetrics
    from katrain.core.analysis.models import AutoRecommendation


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
    thresholds: List[float]  # Raw thresholds from config
    effective_thresholds: Tuple[float, float, float]  # Score thresholds for classification
    effective_preset: str  # "beginner" / "standard" / "advanced"
    auto_recommendation: Optional["AutoRecommendation"]

    # Computed metadata
    confidence_level: ConfidenceLevel
    pacing_map: Optional[Dict[int, PacingMetrics]]
    histogram: Optional[List[Any]]

    # Board and player info
    board_x: int
    board_y: int
    pb: str  # Black player name
    pw: str  # White player name
    focus_color: Optional[str]  # "B" / "W" / None

    # Important moves
    important_moves: List[MoveEval]
    total_moves: int
    settings: ImportantMoveSettings  # Important move settings

    # Parameters
    skill_preset: str
    target_visits: Optional[int]
    lang: str  # "ja" or "en" (ISO codes, matching existing karte output)
