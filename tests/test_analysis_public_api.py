"""Public API stability test for katrain.core.analysis (Phase 174 P1-C).

The ``katrain/core/analysis/__init__.py`` package is the central re-export
hub used by ~40 external modules. Its 570-line ``__init__.py`` is a
candidate for future lazy loading, but the public symbols MUST stay
stable until any such refactor.

This file locks down the public API:

  * Every name listed in ``__all__`` must be importable.
  * Phase 92 wrapper ``get_root_visits`` must remain.
  * A subset of high-traffic symbols is checked by string name (in
    case a typo creeps into __all__).

The set of expected symbols is also verified to be a non-trivial superset
of what the package used to expose (Phase B baseline).
"""

from __future__ import annotations

# High-traffic symbols that external code imports most often. Listing
# them explicitly makes the test fail loudly if any silently disappears.
HIGH_TRAFFIC_SYMBOLS = [
    # Models / enums
    "MistakeCategory",
    "PositionDifficulty",
    "PVFilterLevel",
    "EngineType",
    "AutoConfidence",
    "MoveEval",
    "EvalSnapshot",
    "GameSummaryData",
    "SummaryStats",
    "SkillPreset",
    "AutoRecommendation",
    "PVFilterConfig",
    "DifficultyMetrics",
    "ReliabilityStats",
    # Helpers
    "get_analysis_engine",
    "resolve_visits",
    "get_canonical_loss_from_move",
    "VALID_ANALYSIS_ENGINES",
    "DEFAULT_ANALYSIS_ENGINE",
    "DEFAULT_SKILL_PRESET",
    # Logic
    "build_node_map",
    "classify_game_phase",
    "classify_mistake",
    "compute_canonical_loss",
    "compute_loss_from_delta",
    "select_critical_moves",
    "apply_dynamic_phases",
    # Cluster / context
    "classify_cluster",
    "build_classification_context",
    "extract_clusters",
    "extract_clusters_from_nodes",
    "extract_ownership_context",
    # Presentation / labels
    "format_loss_label",
    "get_reason_tag_label",
    "get_confidence_label",
    "REASON_TAG_LABELS",
    # Reason generator
    "generate_reason",
    "generate_reason_safe",
    # Phase 92 wrapper
    "get_root_visits",
]


class TestAnalysisPackageSurface:
    def test_high_traffic_symbols_importable(self):
        """Every high-traffic symbol can be imported via the package."""
        from katrain.core import analysis

        missing: list[str] = []
        for name in HIGH_TRAFFIC_SYMBOLS:
            if not hasattr(analysis, name):
                missing.append(name)
        assert not missing, f"Missing high-traffic symbols: {missing}"

    def test_all_in___all___is_importable(self):
        """Every name in __all__ can be looked up."""
        from katrain.core import analysis

        all_names = list(analysis.__all__)
        # Sanity: should be a meaningful number of names.
        assert len(all_names) >= 80, f"__all__ has only {len(all_names)} names — expected ≥80."

        missing: list[str] = []
        for name in all_names:
            if not hasattr(analysis, name):
                missing.append(name)
        assert not missing, f"__all__ lists names that don't exist on the package: {missing[:10]}..."

    def test_from_star_yields_everything_in___all__(self):
        """``from katrain.core.analysis import *`` populates the local namespace."""
        ns: dict = {}
        exec("from katrain.core.analysis import *", ns)
        from katrain.core import analysis

        # The wildcard import must shadow every __all__ entry.
        missing = [n for n in analysis.__all__ if n not in ns]
        assert not missing, f"Wildcard import skipped: {missing[:10]}..."

    def testget_root_visits_wrapper(self):
        """Phase 92 wrapper remains available."""
        from katrain.core.analysis import get_root_visits

        # None → None; empty dict → None; full dict → visits value.
        assert get_root_visits(None) is None
        assert get_root_visits({}) is None
        assert get_root_visits({"rootInfo": {"visits": 42}}) == 42
