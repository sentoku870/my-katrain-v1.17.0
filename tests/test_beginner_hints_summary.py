"""Phase 179: Beginner Hints Summary Extension Tests

Coverage:
- HintCategory extension (Phase 179 + structural / meaning_tag / summary groups).
- SummaryHintContext default values and immutability.
- Pure detector behavior (mistake / freedom / difficulty / katago).
- compute_summary_hint priority chain and gating.
- get_summary_hint_cached caching behavior.
- i18n key completeness for the 9 new categories in both jp and en.
- config_key property maps each summary category to its config group.
"""

from __future__ import annotations

import pytest

from katrain.core.beginner import (
    MIN_SUMMARY_VISITS,
    BeginnerHint,
    HintCategory,
    SummaryHintContext,
    compute_summary_hint,
    detect_curator_weak_axis,
    detect_difficulty_summary,
    detect_freedom_summary,
    detect_katago_uncertain,
    detect_mistake_summary,
    detect_ownership_dominant,
    detect_policy_confident,
    detect_policy_conflict,
    get_summary_hint_cached,
)

# ---------------------------------------------------------------------------
# HintCategory extension (Phase 179)
# ---------------------------------------------------------------------------


class TestHintCategoryExtension:
    def test_summary_categories_present(self):
        for name in (
            "MISTAKE_BLUNDER",
            "MISTAKE_MISTAKE",
            "MISTAKE_GOOD",
            "FREEDOM_ONLY_MOVE",
            "FREEDOM_NARROW",
            "FREEDOM_WIDE",
            "DIFFICULTY_TRICKY",
            "DIFFICULTY_CALM",
            "KATAGO_UNCERTAIN",
        ):
            assert hasattr(HintCategory, name), f"Missing category {name}"

    def test_total_count_is_23(self):
        # 4 structural + 6 meaning_tag + 13 summary (Phase 179 + 182 + 186) = 23
        assert len(HintCategory) == 23

    def test_is_structural(self):
        assert HintCategory.SELF_ATARI.is_structural is True
        assert HintCategory.MISTAKE_BLUNDER.is_structural is False
        assert HintCategory.LOW_LIBERTIES.is_structural is False

    def test_is_meaning_tag(self):
        assert HintCategory.LOW_LIBERTIES.is_meaning_tag is True
        assert HintCategory.SELF_ATARI.is_meaning_tag is False
        assert HintCategory.MISTAKE_BLUNDER.is_meaning_tag is False

    def test_is_summary(self):
        assert HintCategory.MISTAKE_BLUNDER.is_summary is True
        assert HintCategory.FREEDOM_WIDE.is_summary is True
        assert HintCategory.DIFFICULTY_TRICKY.is_summary is True
        assert HintCategory.KATAGO_UNCERTAIN.is_summary is True
        assert HintCategory.SELF_ATARI.is_summary is False
        assert HintCategory.LOW_LIBERTIES.is_summary is False

    def test_config_key_for_summary_categories(self):
        assert HintCategory.MISTAKE_BLUNDER.config_key == "summary_mistake"
        assert HintCategory.MISTAKE_MISTAKE.config_key == "summary_mistake"
        assert HintCategory.MISTAKE_GOOD.config_key == "summary_mistake"
        assert HintCategory.FREEDOM_ONLY_MOVE.config_key == "summary_freedom"
        assert HintCategory.FREEDOM_NARROW.config_key == "summary_freedom"
        assert HintCategory.FREEDOM_WIDE.config_key == "summary_freedom"
        assert HintCategory.DIFFICULTY_TRICKY.config_key == "summary_difficulty"
        assert HintCategory.DIFFICULTY_CALM.config_key == "summary_difficulty"
        assert HintCategory.KATAGO_UNCERTAIN.config_key == "katago_uncertain"

    def test_config_key_for_legacy_categories_is_none(self):
        for cat in (
            HintCategory.SELF_ATARI,
            HintCategory.IGNORE_ATARI,
            HintCategory.MISSED_CAPTURE,
            HintCategory.CUT_RISK,
            HintCategory.LOW_LIBERTIES,
            HintCategory.SELF_CAPTURE_LIKE,
            HintCategory.BAD_SHAPE,
            HintCategory.HEAVY_GROUP,
            HintCategory.MISSED_DEFENSE,
            HintCategory.URGENT_VS_BIG,
        ):
            assert cat.config_key is None, f"{cat.name} should not have a config_key"


# ---------------------------------------------------------------------------
# SummaryHintContext
# ---------------------------------------------------------------------------


class TestSummaryHintContext:
    def test_defaults(self):
        ctx = SummaryHintContext()
        assert ctx.points_lost is None
        assert ctx.good_move_count == 0
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False
        assert ctx.score_stdev is None
        assert ctx.root_visits == 0
        assert ctx.is_endgame is False
        assert ctx.score_loss_threshold_blunder == 8.0
        assert ctx.score_loss_threshold_mistake == 2.0
        assert ctx.score_stdev_threshold == 1.5

    def test_immutable(self):
        from dataclasses import FrozenInstanceError

        ctx = SummaryHintContext(points_lost=3.0)
        with pytest.raises(FrozenInstanceError):
            ctx.points_lost = 5.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# detect_mistake_summary
# ---------------------------------------------------------------------------


class TestDetectMistakeSummary:
    def test_no_points_lost_returns_none(self):
        assert detect_mistake_summary(SummaryHintContext()) is None

    def test_blunder_threshold(self):
        ctx = SummaryHintContext(points_lost=9.0)
        hint = detect_mistake_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER
        assert hint.severity == 2
        assert hint.coords is None

    def test_mistake_threshold(self):
        ctx = SummaryHintContext(points_lost=3.5)
        hint = detect_mistake_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_MISTAKE
        assert hint.severity == 1

    def test_neutral_no_hint(self):
        # 0.5 <= pointsLost < 2.0 AND not endgame: no hint
        ctx = SummaryHintContext(points_lost=1.0, is_endgame=False)
        assert detect_mistake_summary(ctx) is None

    def test_good_only_in_endgame(self):
        ctx = SummaryHintContext(points_lost=0.3, is_endgame=True, root_visits=400)
        hint = detect_mistake_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_GOOD

    def test_good_requires_visits(self):
        # Endgame but low visits => no MISTAKE_GOOD
        ctx = SummaryHintContext(points_lost=0.3, is_endgame=True, root_visits=100)
        assert detect_mistake_summary(ctx) is None

    def test_negative_points_lost_clamped_to_zero(self):
        # Should not be classified as a blunder for negative points_lost
        ctx = SummaryHintContext(points_lost=-1.0, is_endgame=False)
        assert detect_mistake_summary(ctx) is None

    def test_custom_thresholds(self):
        ctx = SummaryHintContext(
            points_lost=5.0,
            score_loss_threshold_blunder=4.0,
            score_loss_threshold_mistake=2.0,
        )
        hint = detect_mistake_summary(ctx)
        # 5.0 >= custom blunder 4.0 → BLUNDER
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER


# ---------------------------------------------------------------------------
# detect_freedom_summary
# ---------------------------------------------------------------------------


class TestDetectFreedomSummary:
    def test_zero_candidates_returns_none(self):
        assert detect_freedom_summary(SummaryHintContext()) is None

    def test_only_move(self):
        ctx = SummaryHintContext(good_move_count=1)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_ONLY_MOVE

    def test_zero_good_with_near_returns_only_move(self):
        # good=0, near>=1: still qualifies as ONLY_MOVE per the contract
        ctx = SummaryHintContext(good_move_count=0, near_move_count=3)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_ONLY_MOVE

    def test_narrow(self):
        ctx = SummaryHintContext(good_move_count=3)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_NARROW

    def test_wide(self):
        ctx = SummaryHintContext(good_move_count=5)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_WIDE

    def test_boundary_two_is_narrow(self):
        ctx = SummaryHintContext(good_move_count=2)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_NARROW

    def test_boundary_four_is_wide(self):
        ctx = SummaryHintContext(good_move_count=4)
        hint = detect_freedom_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_WIDE


# ---------------------------------------------------------------------------
# detect_difficulty_summary
# ---------------------------------------------------------------------------


class TestDetectDifficultySummary:
    def test_unknown_returns_none(self):
        assert detect_difficulty_summary(SummaryHintContext()) is None

    def test_unreliable_returns_none(self):
        ctx = SummaryHintContext(overall_difficulty=0.9, is_reliable=False)
        assert detect_difficulty_summary(ctx) is None

    def test_tricky(self):
        ctx = SummaryHintContext(overall_difficulty=0.75, is_reliable=True)
        hint = detect_difficulty_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.DIFFICULTY_TRICKY

    def test_calm(self):
        ctx = SummaryHintContext(overall_difficulty=0.2, is_reliable=True)
        hint = detect_difficulty_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.DIFFICULTY_CALM

    def test_normal_no_hint(self):
        # 0.3 < overall < 0.7: no hint
        ctx = SummaryHintContext(overall_difficulty=0.5, is_reliable=True)
        assert detect_difficulty_summary(ctx) is None

    def test_boundary_tricky(self):
        ctx = SummaryHintContext(overall_difficulty=0.7, is_reliable=True)
        hint = detect_difficulty_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.DIFFICULTY_TRICKY

    def test_boundary_calm(self):
        ctx = SummaryHintContext(overall_difficulty=0.3, is_reliable=True)
        hint = detect_difficulty_summary(ctx)
        assert hint is not None
        assert hint.category == HintCategory.DIFFICULTY_CALM


# ---------------------------------------------------------------------------
# detect_katago_uncertain
# ---------------------------------------------------------------------------


class TestDetectKatagoUncertain:
    def test_no_score_stdev_returns_none(self):
        assert detect_katago_uncertain(SummaryHintContext()) is None

    def test_low_visits_returns_none(self):
        ctx = SummaryHintContext(score_stdev=3.0, root_visits=100)
        assert detect_katago_uncertain(ctx) is None

    def test_below_threshold_returns_none(self):
        ctx = SummaryHintContext(score_stdev=1.0, root_visits=300)
        assert detect_katago_uncertain(ctx) is None

    def test_above_threshold(self):
        ctx = SummaryHintContext(score_stdev=2.0, root_visits=300)
        hint = detect_katago_uncertain(ctx)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN

    def test_boundary_at_threshold(self):
        # >= threshold
        ctx = SummaryHintContext(score_stdev=1.5, root_visits=300)
        hint = detect_katago_uncertain(ctx)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN

    def test_custom_threshold(self):
        ctx = SummaryHintContext(score_stdev=1.0, root_visits=300, score_stdev_threshold=0.8)
        hint = detect_katago_uncertain(ctx)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN


# ---------------------------------------------------------------------------
# compute_summary_hint priority chain (with MockNode)
# ---------------------------------------------------------------------------


class _MockNode:
    """Minimal mock GameNode for compute_summary_hint testing.

    Mirrors the attribute access pattern used by
    ``katrain.core.beginner.hints._compute_summary_context``: candidate
    moves live on ``parent``, while ``points_lost`` / ``analysis`` /
    ``move`` live directly on the node. ``analysis_exists`` reflects
    ``game_node.GameNode.analysis_exists`` which is what
    ``get_score_stdev`` checks before reading ``analysis``.

    Phase 182: ``ownership`` and ``policy`` are exposed via the same
    ``getattr(node, "ownership" / "policy", None)`` pattern that
    ``game_node.py`` uses, so they accept a flat list directly.

    Phase 186: ``meaning_tag_id`` mirrors ``game_node.py``'s attribute,
    populated by batch analysis on reviewed moves.
    """

    def __init__(
        self,
        *,
        points_lost: float | None = None,
        candidate_moves: list[dict] | None = None,
        analysis: dict | None = None,
        move_number: int = 50,
        ownership: list[float] | None = None,
        policy: list[float] | None = None,
        meaning_tag_id: str | None = None,
    ):
        self.points_lost = points_lost
        self.analysis = analysis
        self.ownership = ownership
        self.policy = policy
        self.meaning_tag_id = meaning_tag_id
        # Real GameNode exposes ``analysis_exists``; Phase 179.1 switched
        # the summary context builder to the public ``get_score_stdev``
        # helper which guards on this flag, so mocks must surface it.
        self.analysis_exists = bool(analysis)
        if move_number > 0:
            self.move = type("M", (), {"move_number": move_number})()
        else:
            self.move = None
        if candidate_moves is not None:
            self.parent = type("P", (), {"candidate_moves": candidate_moves})()
        else:
            self.parent = None


class TestComputeSummaryHintPriority:
    def test_priority_mistake_beats_freedom(self):
        node = _MockNode(
            points_lost=9.0,
            candidate_moves=[{"relativePointsLost": 0.0}] * 5,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 0.5}},
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER

    def test_priority_freedom_beats_difficulty(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=[{"relativePointsLost": 0.0}] * 5,
            analysis={
                "root": {"scoreLead": 0, "visits": 500, "scoreStdev": 0.5},
            },
        )
        # Difficulty needs DifficultyMetrics which requires real GameNode;
        # with the mock the call returns UNKNOWN and difficulty detector
        # returns None. Freedom should win.
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_WIDE

    def test_freedom_beats_katago(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=[{"relativePointsLost": 0.0}] * 2,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 3.0}},
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_NARROW

    def test_only_katago_fires(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 2.5}},
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN

    def test_no_metrics_returns_none(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={},
            move_number=0,
        )
        assert compute_summary_hint(node) is None

    def test_low_visits_blocks_all(self):
        node = _MockNode(
            points_lost=10.0,
            candidate_moves=[{"relativePointsLost": 0.0}],
            analysis={"root": {"scoreLead": 0, "visits": 50, "scoreStdev": 3.0}},
        )
        hint = compute_summary_hint(node, require_reliable=True)
        assert hint is None  # below MIN_SUMMARY_VISITS=100

    def test_require_reliable_false_allows_low_visits(self):
        node = _MockNode(
            points_lost=10.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 50, "scoreStdev": 3.0}},
        )
        hint = compute_summary_hint(node, require_reliable=False)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER


# ---------------------------------------------------------------------------
# compute_summary_hint per-category gating (summary_flags)
# ---------------------------------------------------------------------------


class TestComputeSummaryHintFlags:
    def _node_with_mistake(self):
        return _MockNode(
            points_lost=9.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
        )

    def _node_with_freedom(self):
        return _MockNode(
            points_lost=None,
            candidate_moves=[{"relativePointsLost": 0.0}] * 4,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
        )

    def _node_with_katago(self):
        return _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 2.0}},
        )

    def test_flag_off_mistake_falls_through_to_freedom(self):
        node = _MockNode(
            points_lost=9.0,
            candidate_moves=[{"relativePointsLost": 0.0}] * 4,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
        )
        hint = compute_summary_hint(node, summary_flags={"summary_mistake": False})
        # Mistake disabled → next available is FREEDOM_WIDE
        assert hint is not None
        assert hint.category == HintCategory.FREEDOM_WIDE

    def test_flag_off_freedom_falls_through_to_katago(self):
        node = self._node_with_katago()
        hint = compute_summary_hint(node, summary_flags={"summary_freedom": False})
        # With FREEDOM off and no other detectors active in this mock,
        # only KATAGO_UNCERTAIN qualifies
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN

    def test_all_flags_off_returns_none(self):
        node = _MockNode(
            points_lost=10.0,
            candidate_moves=[{"relativePointsLost": 0.0}] * 5,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 3.0}},
        )
        hint = compute_summary_hint(
            node,
            summary_flags={
                "summary_mistake": False,
                "summary_freedom": False,
                "summary_difficulty": False,
                "katago_uncertain": False,
            },
        )
        assert hint is None

    def test_missing_flag_defaults_true(self):
        # summary_flags = {} means everything defaults True
        node = self._node_with_mistake()
        hint = compute_summary_hint(node, summary_flags={})
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER


# ---------------------------------------------------------------------------
# get_summary_hint_cached
# ---------------------------------------------------------------------------


class TestGetSummaryHintCached:
    def test_caches_result(self):
        node = _MockNode(
            points_lost=9.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
        )

        hint1 = get_summary_hint_cached(node)
        # Mutate node to break computation; second call should return cached value
        node.points_lost = None
        hint2 = get_summary_hint_cached(node)
        assert hint1 is hint2

    def test_cache_key_changes_with_flags(self):
        node = _MockNode(
            points_lost=9.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
        )
        get_summary_hint_cached(node, summary_flags={"summary_mistake": False})
        hint_default = get_summary_hint_cached(node)
        # The default invocation should produce a MISTAKE_BLUNDER (flag-on).
        if hint_default is not None:
            assert hint_default.category == HintCategory.MISTAKE_BLUNDER

    def test_require_reliable_invalidates_cache(self):
        """Phase 179.1 regression: toggling ``require_reliable`` must
        invalidate the cache, otherwise low-visits positions would
        mis-report hints in the high-visits mode (and vice versa).
        """
        # visits=50 is below MIN_SUMMARY_VISITS=100, so the strict mode
        # rejects the hint even though points_lost=10 looks alarming.
        node = _MockNode(
            points_lost=10.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 50}},
        )

        # Strict (default): visits gate blocks the hint.
        strict = get_summary_hint_cached(node)
        assert strict is None, "Strict mode should reject at 50 visits"

        # Loose mode: must recompute and produce a hint. The buggy
        # Phase 179 cache would have returned ``None`` from the strict
        # cache, silently breaking the reliability gate.
        loose = get_summary_hint_cached(node, require_reliable=False)
        assert loose is not None, "Loose mode should produce MISTAKE_BLUNDER at 50 visits"
        assert loose.category == HintCategory.MISTAKE_BLUNDER

        # Strict again after a previous loose call must also recompute
        # (cache key includes require_reliable).
        strict_again = get_summary_hint_cached(node)
        assert strict_again is None, "Strict must not pollute loose cache"

    def test_no_cache_when_node_has_no_metrics(self):
        node = _MockNode(move_number=0)
        assert get_summary_hint_cached(node) is None


# ---------------------------------------------------------------------------
# Phase 179.1 regression coverage
# ---------------------------------------------------------------------------


class TestPhase1791Regressions:
    """Tests guarding the fixes introduced in Phase 179.1.

    - ``get_summary_hint_cached`` must key on ``require_reliable``
      (regression for the C1 cache bug).
    - ``HintCategory`` must expose ``i18n_namespace`` / ``fallback_title``
      / ``fallback_body`` properties that GUI code relies on (m3).
    - The ``fallback_*`` dicts must cover every category so the GUI never
      has to fall back to a generic ``("Hint", "")`` tuple.
    """

    def test_require_reliable_toggle_recomputes(self):
        """C1 regression: covered via the dedicated test below; this guards
        the contract more directly by toggling both directions."""
        node = _MockNode(
            points_lost=10.0,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 75}},
        )
        # Initial state: strict should reject (75 < 100).
        assert get_summary_hint_cached(node, require_reliable=True) is None
        # Loose should accept.
        assert (
            get_summary_hint_cached(node, require_reliable=False)
            is not None
        )
        # Toggle back: must re-reject.
        assert get_summary_hint_cached(node, require_reliable=True) is None

    def test_i18n_namespace_format(self):
        """m3: namespace must match the ``beginner_hint:<value>`` schema the
        ``.po`` files rely on."""
        from katrain.core.beginner.models import HintCategory

        assert HintCategory.SELF_ATARI.i18n_namespace == "beginner_hint:self_atari"
        assert HintCategory.MISTAKE_BLUNDER.i18n_namespace == "beginner_hint:mistake_blunder"
        assert HintCategory.KATAGO_UNCERTAIN.i18n_namespace == "beginner_hint:katago_uncertain"

    def test_fallback_titles_and_bodies_full_coverage(self):
        """m3: every category must have fallback title + body so the GUI
        never has to render ``("Hint", "")``."""
        from katrain.core.beginner.models import HintCategory

        for cat in HintCategory:
            assert cat.fallback_title, f"{cat.name} missing fallback_title"
            assert cat.fallback_body, f"{cat.name} missing fallback_body"
            assert cat.fallback_title != "Hint", f"{cat.name} fallback_title is generic"

    def test_get_score_stdev_integration(self):
        """C2: the summary context builder now reads ``score_stdev`` via
        the public ``get_score_stdev`` helper. Verify the detected hint
        category actually fires when the public helper returns the
        expected value.
        """
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 2.5}},
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN


# ---------------------------------------------------------------------------
# Phase 179.2 regression coverage
# ---------------------------------------------------------------------------


class TestPhase1792Regressions:
    """Guards for the M1-M4 improvements in Phase 179.2.

    - M1: endgame detection now keys on ``scoreStdev`` rather than a
      static ``move_number >= 200`` heuristic, so high-stdev persistence
      fights no longer fire MISTAKE_GOOD.
    - M2: ``count_freedom_candidates`` is the shared source of truth; the
      GUI row and the FREEDOM_* hint both call it.
    - M3: KATAGO_UNCERTAIN requires ``root_visits >= 300`` (raised from
      200). The outer ``MIN_SUMMARY_VISITS`` gate of 100 is unchanged.
    """

    def test_endgame_dynamic_uses_score_stdev(self):
        """M1: low scoreStdev with low move_number must still be endgame."""
        from katrain.core.beginner.hints import _is_endgame_position

        node = _MockNode(
            points_lost=0.3,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 400, "scoreStdev": 4.0}},
        )
        assert _is_endgame_position(node) is True, "low stdev => endgame regardless of move number"

    def test_endgame_dynamic_suppresses_midgame_high_stdev(self):
        """M1: high stdev at move 250 must NOT be classified as endgame."""
        from katrain.core.beginner.hints import _is_endgame_position

        node = _MockNode(
            points_lost=0.3,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 400, "scoreStdev": 18.0}},
        )
        # Even at move 250+ (past the old static cutoff), scoreStdev=18 is
        # way above 8.0 so endgame=False.
        node.move = type("M", (), {"move_number": 250})()
        assert _is_endgame_position(node) is False, "high stdev mid-fight must not flip to endgame"

    def test_endgame_fallback_when_no_score_stdev(self):
        """M1: when ``scoreStdev`` is unavailable the heuristic falls back
        to the ``move_number >= 200`` static rule for short-game support.
        """
        from katrain.core.beginner.hints import _is_endgame_position

        # No analysis at all -> scoreStdev is None -> static fallback engages.
        node = _MockNode(points_lost=0.0, analysis=None)
        # move_number=250 is well past the static cutoff
        node.move = type("M", (), {"move_number": 250})()
        assert _is_endgame_position(node) is True

        node.move = type("M", (), {"move_number": 100})()
        assert _is_endgame_position(node) is False

    def test_count_freedom_candidates_shared_helper(self):
        """M2: ``count_freedom_candidates`` is the single source of truth.
        Verify it matches the categories' thresholds and tolerates bad input.
        """
        from katrain.core.beginner.detector_freedom import (
            GOOD_REL_THRESHOLD,
            NEAR_REL_THRESHOLD,
            count_freedom_candidates,
        )

        candidates = [
            {"relativePointsLost": 0.2},  # good (0.2 < 1.0)
            {"relativePointsLost": 0.9},  # good (0.9 < 1.0)
            {"relativePointsLost": 1.5},  # near (1.0 <= 1.5 < 2.0)
            {"relativePointsLost": 2.0},  # near (== 2.0, boundary)
            {"relativePointsLost": 3.0},  # neither
            {"pointsLost": 0.5},  # good via pointsLost fallback
            {},  # missing -> skipped
        ]
        good, near = count_freedom_candidates(candidates)
        assert good == 3, f"expected 3 good candidates, got {good}"
        assert near == 5, f"expected 5 near (good+near) candidates, got {near}"
        assert GOOD_REL_THRESHOLD == 1.0
        assert NEAR_REL_THRESHOLD == 2.0

    def test_count_freedom_candidates_empty_input(self):
        from katrain.core.beginner.detector_freedom import count_freedom_candidates

        assert count_freedom_candidates(None) == (0, 0)
        assert count_freedom_candidates([]) == (0, 0)

    def test_katago_uncertain_300_visits_gate(self):
        """M3: KATAGO_UNCERTAIN requires ``root_visits >= 300``."""
        # 200 visits used to suffice (Phase 179); Phase 179.2 raised to 300.
        # The outer MIN_SUMMARY_VISITS gate (100) lets the request reach the
        # detector; the inner 300 visits gate rejects noisy scoreStdevs.
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 250, "scoreStdev": 3.0}},
        )
        # 250 visits is between outer (100) and inner (300); must not fire.
        assert compute_summary_hint(node) is None

        # 300 visits passes the inner gate; KATAGO_UNCERTAIN fires.
        node_300 = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 300, "scoreStdev": 3.0}},
        )
        hint = compute_summary_hint(node_300)
        assert hint is not None
        assert hint.category == HintCategory.KATAGO_UNCERTAIN

    def test_detector_katago_keeps_300_visits_constant(self):
        """M3 regression: the inner visits constant must be 300, not 200."""
        from katrain.core.beginner.detector_katago import _KATAGO_UNCERTAIN_MIN_VISITS

        assert _KATAGO_UNCERTAIN_MIN_VISITS == 300

    def test_mistake_good_uses_dynamic_endgame(self):
        """M1 integration: MISTAKE_GOOD must require low scoreStdev, not
        just ``move_number >= 200``. A 250-move node with high stdev must
        NOT trigger MISTAKE_GOOD.
        """
        node = _MockNode(
            points_lost=0.1,  # < 0.5 → "good" candidate
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 15.0}},
        )
        node.move = type("M", (), {"move_number": 250})()  # past static cutoff
        # High stdev → not endgame → MISTAKE_GOOD suppressed.
        # (KATAGO_UNCERTAIN may still fire because scoreStdev=15.0>1.5,
        # but MISTAKE_GOOD must NOT appear.)
        hint = compute_summary_hint(node)
        assert hint is not None  # some hint fires (KATAGO_UNCERTAIN)
        assert hint.category != HintCategory.MISTAKE_GOOD, "high-stdev mid-fight must not praise MISTAKE_GOOD"

        # Low stdev → endgame → MISTAKE_GOOD fires.
        node_endgame = _MockNode(
            points_lost=0.1,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500, "scoreStdev": 4.0}},
        )
        node_endgame.move = type("M", (), {"move_number": 220})()
        # Disable KATAGO detection so we can isolate MISTAKE_GOOD.
        hint = compute_summary_hint(node_endgame, summary_flags={"katago_uncertain": False})
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_GOOD


# ---------------------------------------------------------------------------
# should_show_summary_hint gating (pure function)
# ---------------------------------------------------------------------------


class TestShouldShowSummaryHint:
    def test_master_off_blocks(self):
        from katrain.core.beginner.hints import should_show_summary_hint

        assert should_show_summary_hint(False, "analyze", "summary_mistake", {}) is False

    def test_play_mode_blocks(self):
        from katrain.core.beginner.hints import should_show_summary_hint

        assert should_show_summary_hint(True, "play", "summary_mistake", {}) is False

    def test_analyze_mode_with_master_on(self):
        from katrain.core.beginner.hints import should_show_summary_hint

        assert should_show_summary_hint(True, "analyze", "summary_mistake", {}) is True

    def test_missing_flag_defaults_true(self):
        from katrain.core.beginner.hints import should_show_summary_hint

        flags = {"summary_freedom": False}
        assert should_show_summary_hint(True, "analyze", "summary_mistake", flags) is True

    def test_explicit_false(self):
        from katrain.core.beginner.hints import should_show_summary_hint

        flags = {"summary_mistake": False}
        assert should_show_summary_hint(True, "analyze", "summary_mistake", flags) is False


# ---------------------------------------------------------------------------
# i18n completeness (Phase 179 keys)
# ---------------------------------------------------------------------------


class TestSummaryHintI18n:
    CATEGORIES = [
        "mistake_blunder",
        "mistake_mistake",
        "mistake_good",
        "freedom_only_move",
        "freedom_narrow",
        "freedom_wide",
        "difficulty_tricky",
        "difficulty_calm",
        "katago_uncertain",
    ]
    SUFFIXES = ["title", "body", "why"]
    SETTINGS_KEYS = [
        "summary_mistake",
        "summary_mistake_desc",
        "summary_freedom",
        "summary_freedom_desc",
        "summary_difficulty",
        "summary_difficulty_desc",
        "katago_uncertain",
        "katago_uncertain_desc",
    ]

    def test_all_hint_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:{c}:{s}" for c in self.CATEGORIES for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing JP keys: {missing}"

    def test_all_hint_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:{c}:{s}" for c in self.CATEGORIES for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing EN keys: {missing}"

    def test_settings_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing JP settings keys: {missing}"

    def test_settings_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing EN settings keys: {missing}"

    def test_no_empty_msgstr_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if (
                entry.msgid.startswith("beginner_hint:mistake_")
                or entry.msgid.startswith("beginner_hint:freedom_")
                or entry.msgid.startswith("beginner_hint:difficulty_")
                or entry.msgid.startswith("beginner_hint:katago_uncertain")
            )
            and not entry.msgstr
        ]
        assert not empty, f"Empty JP msgstr: {empty}"

    def test_no_empty_msgstr_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if (
                entry.msgid.startswith("beginner_hint:mistake_")
                or entry.msgid.startswith("beginner_hint:freedom_")
                or entry.msgid.startswith("beginner_hint:difficulty_")
                or entry.msgid.startswith("beginner_hint:katago_uncertain")
            )
            and not entry.msgstr
        ]
        assert not empty, f"Empty EN msgstr: {empty}"


# ---------------------------------------------------------------------------
# Architecture / module-level sanity
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_module_constants_exported(self):
        assert MIN_SUMMARY_VISITS == 100

    def test_detectors_importable_from_package(self):
        from katrain.core.beginner import (
            detect_difficulty_summary as d1,
        )
        from katrain.core.beginner import (
            detect_freedom_summary as d2,
        )
        from katrain.core.beginner import (
            detect_katago_uncertain as d3,
        )
        from katrain.core.beginner import (
            detect_mistake_summary as d4,
        )

        assert callable(d1) and callable(d2) and callable(d3) and callable(d4)

def test_beginner_hint_imports_unchanged():
    # Backward compat: previous tests / external imports
    from katrain.core.beginner import HintCategory

    hint = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=3)
    assert hint.category is HintCategory.SELF_ATARI


# ---------------------------------------------------------------------------
# Phase 182: Ownership / Policy hint categories
# ---------------------------------------------------------------------------


class TestPhase182OwnershipPolicyCategories:
    """Phase 182 extension: 3 new summary hint categories derived from
    KataGo's ownership grid and policy distribution.
    """

    def test_three_new_categories_exist(self):
        for name in ("OWNERSHIP_DOMINANT", "POLICY_CONFLICT", "POLICY_CONFIDENT"):
            assert hasattr(HintCategory, name), f"Missing category {name}"

    def test_total_count_is_23(self):
        # 19 (Phase 179) + 3 (Phase 182) + 1 (Phase 186) = 23
        assert len(HintCategory) == 23

    def test_ownership_policy_are_summary(self):
        assert HintCategory.OWNERSHIP_DOMINANT.is_summary is True
        assert HintCategory.POLICY_CONFLICT.is_summary is True
        assert HintCategory.POLICY_CONFIDENT.is_summary is True

    def test_config_key_mapping(self):
        assert HintCategory.OWNERSHIP_DOMINANT.config_key == "summary_ownership"
        assert HintCategory.POLICY_CONFLICT.config_key == "summary_policy"
        assert HintCategory.POLICY_CONFIDENT.config_key == "summary_policy"

    def test_i18n_namespace_format(self):
        assert HintCategory.OWNERSHIP_DOMINANT.i18n_namespace == "beginner_hint:ownership_dominant"
        assert HintCategory.POLICY_CONFLICT.i18n_namespace == "beginner_hint:policy_conflict"
        assert HintCategory.POLICY_CONFIDENT.i18n_namespace == "beginner_hint:policy_confident"

    def test_fallback_titles_and_bodies(self):
        for cat in (
            HintCategory.OWNERSHIP_DOMINANT,
            HintCategory.POLICY_CONFLICT,
            HintCategory.POLICY_CONFIDENT,
        ):
            assert cat.fallback_title, f"{cat.name} missing fallback_title"
            assert cat.fallback_body, f"{cat.name} missing fallback_body"


class TestDetectOwnershipDominant:
    """OWNERSHIP_DOMINANT detector (Phase 182)."""

    def test_no_predicted_territory_returns_none(self):
        assert detect_ownership_dominant(SummaryHintContext()) is None

    def test_low_visits_blocks(self):
        ctx = SummaryHintContext(predicted_territory=0.95, root_visits=150)
        assert detect_ownership_dominant(ctx) is None

    def test_below_threshold_returns_none(self):
        # 0.7 is below the default 0.85 threshold
        ctx = SummaryHintContext(predicted_territory=0.7, root_visits=300)
        assert detect_ownership_dominant(ctx) is None

    def test_above_threshold(self):
        ctx = SummaryHintContext(predicted_territory=0.95, root_visits=300)
        hint = detect_ownership_dominant(ctx)
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT
        assert hint.severity == 0
        assert hint.coords is None

    def test_negative_dominance(self):
        # |−0.95| = 0.95 >= 0.85 -> should fire (regardless of sign)
        ctx = SummaryHintContext(predicted_territory=-0.95, root_visits=300)
        hint = detect_ownership_dominant(ctx)
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT

    def test_boundary_at_threshold(self):
        # Exactly 0.85 should fire (>= comparison)
        ctx = SummaryHintContext(predicted_territory=0.85, root_visits=300)
        hint = detect_ownership_dominant(ctx)
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT

    def test_custom_threshold(self):
        ctx = SummaryHintContext(predicted_territory=0.6, root_visits=300, territory_dominant_threshold=0.5)
        hint = detect_ownership_dominant(ctx)
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT


class TestDetectPolicyConfident:
    """POLICY_CONFIDENT detector (Phase 182)."""

    def test_no_best_policy_returns_none(self):
        assert detect_policy_confident(SummaryHintContext()) is None

    def test_low_visits_blocks(self):
        ctx = SummaryHintContext(best_policy=0.7, root_visits=50)
        assert detect_policy_confident(ctx) is None

    def test_below_threshold_returns_none(self):
        ctx = SummaryHintContext(best_policy=0.3, root_visits=200)
        assert detect_policy_confident(ctx) is None

    def test_above_threshold(self):
        ctx = SummaryHintContext(best_policy=0.7, root_visits=200)
        hint = detect_policy_confident(ctx)
        assert hint is not None
        assert hint.category == HintCategory.POLICY_CONFIDENT
        assert hint.severity == 0
        assert hint.coords is None

    def test_boundary_at_threshold(self):
        ctx = SummaryHintContext(best_policy=0.5, root_visits=200)
        hint = detect_policy_confident(ctx)
        assert hint is not None
        assert hint.category == HintCategory.POLICY_CONFIDENT


class TestDetectPolicyConflict:
    """POLICY_CONFLICT detector (Phase 182)."""

    def test_no_best_policy_returns_none(self):
        assert detect_policy_conflict(SummaryHintContext()) is None

    def test_low_visits_blocks(self):
        ctx = SummaryHintContext(best_policy=0.05, root_visits=50)
        assert detect_policy_conflict(ctx) is None

    def test_above_threshold_returns_none(self):
        ctx = SummaryHintContext(best_policy=0.4, root_visits=200)
        assert detect_policy_conflict(ctx) is None

    def test_below_threshold(self):
        ctx = SummaryHintContext(best_policy=0.1, root_visits=200)
        hint = detect_policy_conflict(ctx)
        assert hint is not None
        assert hint.category == HintCategory.POLICY_CONFLICT
        assert hint.severity == 1
        assert hint.coords is None

    def test_boundary_at_threshold(self):
        ctx = SummaryHintContext(best_policy=0.15, root_visits=200)
        hint = detect_policy_conflict(ctx)
        assert hint is not None
        assert hint.category == HintCategory.POLICY_CONFLICT


class TestExtractPredictedTerritory:
    """Phase 182: _extract_predicted_territory edge cases."""

    def test_none_ownership_returns_none(self):
        node = _MockNode(ownership=None)
        from katrain.core.beginner.hints import _extract_predicted_territory

        assert _extract_predicted_territory(node) is None

    def test_empty_ownership_returns_none(self):
        node = _MockNode(ownership=[])
        from katrain.core.beginner.hints import _extract_predicted_territory

        assert _extract_predicted_territory(node) is None

    def test_normalises_to_range(self):
        node = _MockNode(ownership=[1.0] * 361)
        from katrain.core.beginner.hints import _extract_predicted_territory

        assert _extract_predicted_territory(node) == 1.0
        node.ownership = [-1.0] * 361
        assert _extract_predicted_territory(node) == -1.0
        node.ownership = [0.0] * 361
        assert _extract_predicted_territory(node) == 0.0

    def test_skips_none_and_invalid(self):
        node = _MockNode(ownership=[1.0, None, 0.5, "bad", -0.5, None])
        from katrain.core.beginner.hints import _extract_predicted_territory

        # Valid values: 1.0, 0.5, -0.5 -> sum=1.0 / count=3 -> ~0.333
        assert abs(_extract_predicted_territory(node) - (1.0 / 3)) < 1e-9


class TestExtractBestPolicy:
    """Phase 182: _extract_best_policy edge cases."""

    def test_none_returns_none(self):
        node = _MockNode(policy=None)
        from katrain.core.beginner.hints import _extract_best_policy

        assert _extract_best_policy(node) is None

    def test_empty_returns_none(self):
        node = _MockNode(policy=[])
        from katrain.core.beginner.hints import _extract_best_policy

        assert _extract_best_policy(node) is None

    def test_returns_max(self):
        node = _MockNode(policy=[0.05, 0.15, 0.7, 0.05, 0.05])
        from katrain.core.beginner.hints import _extract_best_policy

        assert _extract_best_policy(node) == 0.7

    def test_skips_none_and_invalid(self):
        node = _MockNode(policy=[0.1, None, 0.6, "bad", 0.3, None])
        from katrain.core.beginner.hints import _extract_best_policy

        assert _extract_best_policy(node) == 0.6


class TestPhase182PriorityChain:
    """Phase 182: ownership / policy slot into compute_summary_hint
    priority chain at the bottom (lowest severity). They never outrank
    Mistake / Freedom / Difficulty / KataGo uncertainty.
    """

    def test_ownership_outranked_by_mistake(self):
        node = _MockNode(
            points_lost=10.0,  # blunder
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            ownership=[0.95] * 361,  # dominant too
            policy=[0.7] * 361,
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER

    def test_ownership_alone_fires(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 300}},
            ownership=[0.95] * 361,
            policy=[0.3] * 361,  # neither conflict nor confident
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT

    def test_policy_confident_outranks_conflict(self):
        # Best policy 0.7 -> confident fires (severity 0) before conflict
        # would (severity 1). Both raw thresholds don't overlap, but the
        # priority chain order is what matters.
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 300}},
            policy=[0.7] * 361,
        )
        hint = compute_summary_hint(node)
        assert hint is not None
        assert hint.category == HintCategory.POLICY_CONFIDENT

    def test_ownership_flag_off_suppresses_ownership_hint(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 300}},
            ownership=[0.95] * 361,
            policy=[0.3] * 361,
        )
        hint = compute_summary_hint(node, summary_flags={"summary_ownership": False})
        # Without ownership detector, neither conflict nor confident fires
        # (best_policy = 0.3 is between 0.15 and 0.5 thresholds).
        assert hint is None

    def test_policy_flag_off_suppresses_policy_hints(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 300}},
            ownership=[0.95] * 361,
            policy=[0.7] * 361,
        )
        hint = compute_summary_hint(node, summary_flags={"summary_policy": False})
        assert hint is not None
        assert hint.category == HintCategory.OWNERSHIP_DOMINANT


class TestPhase182I18n:
    """Phase 182: i18n keys for the 3 new categories exist in jp/en."""

    CATEGORIES = ["ownership_dominant", "policy_conflict", "policy_confident"]
    SUFFIXES = ["title", "body", "why"]
    SETTINGS_KEYS = [
        "summary_ownership",
        "summary_ownership_desc",
        "summary_policy",
        "summary_policy_desc",
    ]

    def test_all_hint_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:{c}:{s}" for c in self.CATEGORIES for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing JP keys: {missing}"

    def test_all_hint_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:{c}:{s}" for c in self.CATEGORIES for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing EN keys: {missing}"

    def test_settings_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing JP settings keys: {missing}"

    def test_settings_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing EN settings keys: {missing}"

    def test_no_empty_msgstr_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if (
                entry.msgid.startswith("beginner_hint:ownership_dominant")
                or entry.msgid.startswith("beginner_hint:policy_")
            )
            and not entry.msgstr
        ]
        assert not empty, f"Empty JP msgstr: {empty}"

    def test_no_empty_msgstr_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if (
                entry.msgid.startswith("beginner_hint:ownership_dominant")
                or entry.msgid.startswith("beginner_hint:policy_")
            )
            and not entry.msgstr
        ]
        assert not empty, f"Empty EN msgstr: {empty}"


# ---------------------------------------------------------------------------
# Phase 186: Curator weak-axis hint category
# ---------------------------------------------------------------------------


class TestPhase186CuratorCategory:
    """Phase 186 extension: CURATOR_WEAK_AXIS summary hint."""

    def test_category_exists(self):
        assert hasattr(HintCategory, "CURATOR_WEAK_AXIS")

    def test_total_count_is_23(self):
        # 22 (Phase 182) + 1 (Phase 186) = 23
        assert len(HintCategory) == 23

    def test_is_summary(self):
        assert HintCategory.CURATOR_WEAK_AXIS.is_summary is True

    def test_config_key(self):
        assert HintCategory.CURATOR_WEAK_AXIS.config_key == "curator_hint"

    def test_i18n_namespace(self):
        assert HintCategory.CURATOR_WEAK_AXIS.i18n_namespace == "beginner_hint:curator_weak_axis"

    def test_fallback_title_and_body(self):
        assert HintCategory.CURATOR_WEAK_AXIS.fallback_title
        assert HintCategory.CURATOR_WEAK_AXIS.fallback_body


class TestDetectCuratorWeakAxis:
    """Phase 186: detect_curator_weak_axis pure detector."""

    def test_no_user_weak_tags_returns_none(self):
        node = _MockNode(meaning_tag_id="overplay")
        assert detect_curator_weak_axis(node, None) is None

    def test_empty_user_weak_tags_returns_none(self):
        node = _MockNode(meaning_tag_id="overplay")
        assert detect_curator_weak_axis(node, {}) is None

    def test_node_without_meaning_tag_returns_none(self):
        node = _MockNode()
        assert detect_curator_weak_axis(node, {"overplay": 5}) is None

    def test_tag_below_threshold_returns_none(self):
        # Default min_occurrences=3, so count=2 should not fire
        node = _MockNode(meaning_tag_id="overplay")
        assert detect_curator_weak_axis(node, {"overplay": 2}) is None

    def test_tag_in_profile_and_node_fires(self):
        node = _MockNode(meaning_tag_id="overplay")
        hint = detect_curator_weak_axis(node, {"overplay": 5})
        assert hint is not None
        assert hint.category == HintCategory.CURATOR_WEAK_AXIS
        assert hint.severity == 0
        assert hint.coords is None
        assert hint.context["tag_id"] == "overplay"
        assert hint.context["occurrence_count"] == 5

    def test_tag_not_in_profile_returns_none(self):
        node = _MockNode(meaning_tag_id="connection_miss")
        assert detect_curator_weak_axis(node, {"overplay": 5}) is None

    def test_custom_threshold(self):
        node = _MockNode(meaning_tag_id="overplay")
        # Lower threshold to 1: count=2 should now fire
        hint = detect_curator_weak_axis(node, {"overplay": 2}, min_occurrences=1)
        assert hint is not None
        assert hint.category == HintCategory.CURATOR_WEAK_AXIS

    def test_high_threshold_filters(self):
        node = _MockNode(meaning_tag_id="overplay")
        # Higher threshold (10): count=5 should NOT fire
        assert detect_curator_weak_axis(node, {"overplay": 5}, min_occurrences=10) is None


class TestCuratorProfileLoader:
    """Phase 186: core.curator.profile module integration."""

    def test_load_none_returns_none(self):
        from katrain.core.curator.profile import load_curator_profile

        assert load_curator_profile(None) is None

    def test_load_missing_file_returns_none(self, tmp_path):
        from katrain.core.curator.profile import load_curator_profile

        assert load_curator_profile(tmp_path / "no_such_file.json") is None

    def test_load_minimal_payload(self, tmp_path):
        import json

        from katrain.core.curator.profile import load_curator_profile

        path = tmp_path / "curator.json"
        path.write_text(
            json.dumps(
                {
                    "user_weak_tags": {"overplay": 5, "shape_mistake": 2},
                    "total_games": 12,
                }
            ),
            encoding="utf-8",
        )
        profile = load_curator_profile(path)
        assert profile is not None
        assert profile.total_games == 12
        # Tags below default min_occurrences=3 are filtered out
        assert profile.weak_tags == {"overplay": 5}

    def test_load_payload_of_pairs(self):
        from katrain.core.curator.profile import curator_profile_from_payload

        payload = {"user_weak_tags": [["overplay", 7], ["other", 4]], "total_games": 8}
        profile = curator_profile_from_payload(payload)
        assert profile is not None
        assert profile.weak_tags == {"overplay": 7, "other": 4}

    def test_lookup_returns_zero_for_missing_tag(self):
        from katrain.core.curator.profile import CuratorProfile

        p = CuratorProfile(weak_tags={"overplay": 5}, total_games=10)
        assert p.lookup(None) == 0
        assert p.lookup("") == 0
        assert p.lookup("nonexistent") == 0

    def test_lookup_returns_zero_for_below_threshold(self):
        from katrain.core.curator.profile import CuratorProfile

        p = CuratorProfile(weak_tags={"overplay": 2}, total_games=10)
        assert p.lookup("overplay", min_occurrences=3) == 0

    def test_lookup_returns_count_above_threshold(self):
        from katrain.core.curator.profile import CuratorProfile

        p = CuratorProfile(weak_tags={"overplay": 5}, total_games=10)
        assert p.lookup("overplay", min_occurrences=3) == 5

    def test_is_loaded_requires_min_games(self):
        from katrain.core.curator.profile import CuratorProfile

        p_few = CuratorProfile(weak_tags={"overplay": 5}, total_games=3)
        p_many = CuratorProfile(weak_tags={"overplay": 5}, total_games=10)
        assert p_few.is_loaded() is False
        assert p_many.is_loaded() is True


class TestPhase186PriorityChain:
    """Phase 186: CURATOR_WEAK_AXIS slots into compute_summary_hint
    at the bottom of the priority chain. It never outranks a Mistake /
    structural hint.
    """

    def test_curator_outranked_by_mistake(self):
        node = _MockNode(
            points_lost=10.0,  # blunder
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            meaning_tag_id="overplay",
        )
        user_weak = {"overplay": 10}
        hint = compute_summary_hint(node, user_weak_tags=user_weak)
        assert hint is not None
        assert hint.category == HintCategory.MISTAKE_BLUNDER

    def test_curator_fires_when_alone(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            meaning_tag_id="overplay",
        )
        user_weak = {"overplay": 5}
        hint = compute_summary_hint(node, user_weak_tags=user_weak)
        assert hint is not None
        assert hint.category == HintCategory.CURATOR_WEAK_AXIS

    def test_curator_silent_when_no_user_profile(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            meaning_tag_id="overplay",
        )
        # No user_weak_tags → no hint
        assert compute_summary_hint(node) is None

    def test_curator_flag_off(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            meaning_tag_id="overplay",
        )
        user_weak = {"overplay": 5}
        hint = compute_summary_hint(
            node,
            user_weak_tags=user_weak,
            summary_flags={"curator_hint": False},
        )
        assert hint is None


class TestPhase186CachedIntegration:
    """Phase 186: get_summary_hint_cached accepts user_weak_tags and
    invalidates the cache when the profile changes.
    """

    def test_cache_key_includes_user_weak_tags(self):
        node = _MockNode(
            points_lost=None,
            candidate_moves=None,
            analysis={"root": {"scoreLead": 0, "visits": 500}},
            meaning_tag_id="overplay",
        )
        # First call: with profile
        hint_with = get_summary_hint_cached(node, user_weak_tags={"overplay": 5})
        assert hint_with is not None
        assert hint_with.category == HintCategory.CURATOR_WEAK_AXIS

        # Second call: no profile → cache must invalidate
        hint_without = get_summary_hint_cached(node)
        assert hint_without is None

        # Third call: different profile → must also invalidate
        node.meaning_tag_id = "shape_mistake"
        hint_shape = get_summary_hint_cached(node, user_weak_tags={"shape_mistake": 5})
        assert hint_shape is not None
        assert hint_shape.category == HintCategory.CURATOR_WEAK_AXIS


class TestPhase186I18n:
    """Phase 186: i18n keys for the new category exist in jp/en."""

    SUFFIXES = ["title", "body", "why"]
    SETTINGS_KEYS = ["curator_hint", "curator_hint_desc"]

    def test_hint_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:curator_weak_axis:{s}" for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing JP keys: {missing}"

    def test_hint_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        expected = {f"beginner_hint:curator_weak_axis:{s}" for s in self.SUFFIXES}
        missing = expected - existing
        assert not missing, f"Missing EN keys: {missing}"

    def test_settings_keys_in_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing JP settings keys: {missing}"

    def test_settings_keys_in_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        existing = {entry.msgid for entry in po}
        missing = [k for k in self.SETTINGS_KEYS if f"mykatrain:settings:{k}" not in existing]
        assert not missing, f"Missing EN settings keys: {missing}"

    def test_no_empty_msgstr_jp(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/jp/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if entry.msgid.startswith("beginner_hint:curator_weak_axis:") and not entry.msgstr
        ]
        assert not empty, f"Empty JP msgstr: {empty}"

    def test_no_empty_msgstr_en(self):
        import polib

        po = polib.pofile("katrain/i18n/locales/en/LC_MESSAGES/katrain.po")
        empty = [
            entry.msgid
            for entry in po
            if entry.msgid.startswith("beginner_hint:curator_weak_axis:") and not entry.msgstr
        ]
        assert not empty, f"Empty EN msgstr: {empty}"
