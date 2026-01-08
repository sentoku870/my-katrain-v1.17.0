"""
KaTrain Qt Analysis Package.

Provides KataGo integration for the Qt frontend.
"""

from .models import (
    CandidateMove,
    PositionSnapshot,
    AnalysisResult,
    gtp_to_internal,
    internal_to_gtp,
    coord_to_display,
)
from .katago_engine import (
    KataGoEngine,
    load_settings,
    save_settings,
    extract_root_score_lead,
    extract_root_winrate,
    parse_response,
    build_analysis_result,
)

__all__ = [
    "CandidateMove",
    "PositionSnapshot",
    "AnalysisResult",
    "gtp_to_internal",
    "internal_to_gtp",
    "coord_to_display",
    "KataGoEngine",
    "load_settings",
    "save_settings",
    "extract_root_score_lead",
    "extract_root_winrate",
    "parse_response",
    "build_analysis_result",
]
