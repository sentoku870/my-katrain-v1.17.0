"""Phase 91-92 + Phase 179: Beginner Hint System

Safety net for beginners to avoid self-sabotage moves, plus Phase 179
summary hints derived from Mistake / Freedom / Difficulty / KataGo metrics.

Public API (Phase 91-92):
    - compute_beginner_hint(game, node) -> BeginnerHint | None
    - get_beginner_hint_cached(game, node) -> BeginnerHint | None
    - HintCategory: Enum of hint types
    - BeginnerHint: Hint data class

Phase 179 additions:
    - SummaryHintContext: Snapshot of Mistake/Freedom/Difficulty metrics.
    - compute_summary_hint(ctx, config) -> BeginnerHint | None
    - detect_mistake_summary / detect_freedom_summary /
      detect_difficulty_summary / detect_katago_uncertain: Pure detectors.
"""

from __future__ import annotations

from katrain.core.beginner.detector_curator import detect_curator_weak_axis
from katrain.core.beginner.detector_difficulty import detect_difficulty_summary
from katrain.core.beginner.detector_freedom import detect_freedom_summary
from katrain.core.beginner.detector_katago import detect_katago_uncertain
from katrain.core.beginner.detector_mistake import detect_mistake_summary
from katrain.core.beginner.detector_ownership import detect_ownership_dominant
from katrain.core.beginner.detector_policy import detect_policy_confident, detect_policy_conflict
from katrain.core.beginner.hints import (
    MIN_RELIABLE_VISITS,
    MIN_SUMMARY_VISITS,
    compute_beginner_hint,
    compute_summary_hint,
    get_beginner_hint_cached,
    get_summary_hint_cached,
)
from katrain.core.beginner.models import BeginnerHint, DetectorInput, HintCategory, SummaryHintContext

__all__ = [
    # Phase 91-92 API
    "compute_beginner_hint",
    "get_beginner_hint_cached",
    "BeginnerHint",
    "HintCategory",
    "DetectorInput",
    "MIN_RELIABLE_VISITS",
    # Phase 179 API
    "SummaryHintContext",
    "compute_summary_hint",
    "get_summary_hint_cached",
    "detect_mistake_summary",
    "detect_freedom_summary",
    "detect_difficulty_summary",
    "detect_katago_uncertain",
    "MIN_SUMMARY_VISITS",
    # Phase 182 API
    "detect_ownership_dominant",
    "detect_policy_confident",
    "detect_policy_conflict",
    # Phase 186 API
    "detect_curator_weak_axis",
]
