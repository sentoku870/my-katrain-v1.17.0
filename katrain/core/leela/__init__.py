"""Leela Zero support package for myKatrain.

This package provides:
- Data models for Leela analysis results (LeelaCandidate, LeelaPositionEval)
- Parser for lz-analyze output
- Estimated loss calculation logic
- Engine wrapper for Leela Zero

Note: This is completely separate from KataGo functionality.
"""

from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval
from katrain.core.leela.parser import parse_lz_analyze, normalize_winrate_from_raw
from katrain.core.leela.logic import (
    LEELA_K_DEFAULT,
    LEELA_K_MIN,
    LEELA_K_MAX,
    LEELA_LOSS_EST_MAX,
    clamp_k,
    compute_estimated_loss,
    format_loss_est,
)
from katrain.core.leela.engine import LeelaEngine
from katrain.core.leela.presentation import (
    lerp_color,
    loss_to_color,
    format_winrate_pct,
    format_visits,
)
from katrain.core.leela.conversion import (
    leela_position_to_move_eval,
    leela_sequence_to_eval_snapshot,
)

__all__ = [
    # Models
    "LeelaCandidate",
    "LeelaPositionEval",
    # Parser
    "parse_lz_analyze",
    "normalize_winrate_from_raw",
    # Logic
    "LEELA_K_DEFAULT",
    "LEELA_K_MIN",
    "LEELA_K_MAX",
    "LEELA_LOSS_EST_MAX",
    "clamp_k",
    "compute_estimated_loss",
    "format_loss_est",
    # Engine
    "LeelaEngine",
    # Presentation
    "lerp_color",
    "loss_to_color",
    "format_winrate_pct",
    "format_visits",
    # Conversion
    "leela_position_to_move_eval",
    "leela_sequence_to_eval_snapshot",
]
