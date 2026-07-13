"""Phase 186 followup: Regression tests for None-safety in public analysis
extractors.

In Phase 179.1 we migrated ``_compute_summary_context`` to use the
public ``get_root_visits`` / ``get_score_stdev`` helpers (instead of
rolling our own ``analysis.get(...)`` traversal). The trade-off was
that those helpers must tolerate every shape the analysis dict takes
during startup — including ``{"root": None}`` when KataGo hasn't
populated the analysis payload yet.

Without defensive coercion the helpers raise
``TypeError: argument of type 'NoneType' is not iterable`` from
``if "visits" in root:`` which propagated through every Beginner Hint
update tick and crashed the GUI.
"""

from __future__ import annotations

import pytest


class TestGetRootVisitsNoneSafety:
    """``get_root_visits`` must never raise on plausible analysis states."""

    @pytest.mark.parametrize(
        "analysis",
        [
            None,
            {},
            {"root": None},
            {"rootInfo": None},
            {"root": None, "rootInfo": None},
            {"root": {}},
            {"rootInfo": {}},
            {"root": {"visits": 0}},  # valid edge: zero visits
            {"rootInfo": {"visits": 0}},
        ],
    )
    def test_does_not_raise(self, analysis):
        from katrain.core.analysis import get_root_visits

        # Must not raise — defensive coercion handles missing / null roots.
        result = get_root_visits(analysis)
        # Either None (no data) or 0 (valid zero visits).
        assert result is None or result == 0

    def test_valid_root(self):
        from katrain.core.analysis import get_root_visits

        assert get_root_visits({"root": {"visits": 123}}) == 123

    def test_valid_rootInfo(self):
        from katrain.core.analysis import get_root_visits

        assert get_root_visits({"rootInfo": {"visits": 456}}) == 456


class TestGetScoreStdevNoneSafety:
    """``get_score_stdev`` must handle the same None-analysis states."""

    @pytest.mark.parametrize(
        "analysis_exists,analysis",
        [
            (False, None),
            (True, None),
            (True, {}),
            (True, {"root": None}),
            (True, {"root": {}}),
        ],
    )
    def test_does_not_raise(self, analysis_exists, analysis):
        from katrain.core.analysis import get_score_stdev

        class _N:
            pass

        node = _N()
        node.analysis_exists = analysis_exists
        node.analysis = analysis
        # Must not raise.
        result = get_score_stdev(node)
        assert result is None

    def test_valid_root(self):
        from katrain.core.analysis import get_score_stdev

        class _N:
            pass

        node = _N()
        node.analysis_exists = True
        node.analysis = {"root": {"scoreStdev": 3.5}}
        assert get_score_stdev(node) == 3.5


class TestComputeSummaryContextNoneAnalysis:
    """Regression: ``_compute_summary_context`` must not raise when the
    node has ``analysis=None`` (the situation observed in the user's
    log right after KataGo startup before the first analysis completes).
    """

    def test_compute_summary_context_with_no_analysis(self):
        from katrain.core.beginner.hints import _compute_summary_context
        from katrain.core.beginner.models import SummaryHintContext

        class _N:
            analysis = None
            analysis_exists = False
            ownership = None
            policy = None
            meaning_tag_id = None
            move = None
            points_lost = None
            depth = 0

            def __init__(self):
                self.parent = None

        node = _N()
        ctx = _compute_summary_context(node)
        assert isinstance(ctx, SummaryHintContext)
        assert ctx.root_visits == 0
        assert ctx.score_stdev is None
        assert ctx.predicted_territory is None
        assert ctx.best_policy is None

    def test_compute_summary_context_with_root_none(self):
        from katrain.core.beginner.hints import _compute_summary_context
        from katrain.core.beginner.models import SummaryHintContext

        class _N:
            analysis_exists = True
            ownership = None
            policy = None
            meaning_tag_id = None
            move = None
            points_lost = None
            depth = 0

            def __init__(self):
                self.analysis = {"root": None}
                self.parent = None

        node = _N()
        ctx = _compute_summary_context(node)
        assert isinstance(ctx, SummaryHintContext)
        assert ctx.root_visits == 0  # The bug: this used to raise TypeError


class TestComputeSummaryHintDoesNotRaise:
    """End-to-end: the public entry point must not raise on partial state."""

    def test_compute_summary_hint_with_no_analysis(self):
        from katrain.core.beginner import compute_summary_hint

        class _N:
            analysis = None
            analysis_exists = False
            ownership = None
            policy = None
            meaning_tag_id = None
            move = None
            points_lost = None

            def __init__(self):
                self.parent = None

        node = _N()
        # Must not raise; expected outcome is None (not enough info).
        assert compute_summary_hint(node) is None
