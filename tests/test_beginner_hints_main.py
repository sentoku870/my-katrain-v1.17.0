"""Phase A1: Beginner Hint Main Pipeline Coverage Tests

Architecture Review follow-up: lift ``core/beginner/hints`` package
coverage from 16.5% to a target of ~50% by exercising the main
pipeline entry points and the internal helpers that the existing
test files don't cover in depth.

What this file adds beyond the two existing test files
(``test_beginner_hints.py`` and ``test_beginner_hints_summary.py``):

- Branch coverage for the **public gate functions** (master switch,
  summary flag gate, board-highlight gate, coord validation).
- **Pure-function tests** for the three internal extractors
  (``_extract_predicted_territory``, ``_extract_best_policy``,
  ``_is_endgame_position``) covering their defensive paths (empty
  list, mixed None, malformed numbers, scoreStdev-unavailable).
- Branch coverage for ``_compute_summary_context`` including the
  ``try/except Exception`` fallback around
  ``difficulty_metrics_from_node`` and the move-number fallback to
  ``node.depth``.
- Cache invalidate scenarios for ``get_summary_hint_cached`` across
  all four cache-key dimensions (flags, require_reliable,
  user_weak_tags, curator_min_occurrences) — Phase 186 widening.
- ``compute_beginner_hint`` ``finally``-block restore path and
  ``move.is_pass`` short-circuit.
- Priority-chain end-to-end smoke for ``compute_summary_hint`` with
  multiple detector groups simultaneously applicable.

Kivy imports are deliberately avoided at module level to comply with
Phase 173 (kivy mkdir side effect → CI exit-102). The module under
test (``hints`` package) is core-layer and Kivy-free.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.beginner import (
    MIN_RELIABLE_VISITS,
    MIN_SUMMARY_VISITS,
    BeginnerHint,
    HintCategory,
)
from katrain.core.beginner.hints import (
    _DETECTOR_CATEGORIES,
    _NOT_COMPUTED,
    _compute_summary_context,
    _extract_best_policy,
    _extract_predicted_territory,
    _is_endgame_position,
    _normalize_board_size,
    compute_beginner_hint,
    compute_summary_hint,
    get_beginner_hint_cached,
    get_summary_hint_cached,
    is_coords_valid,
    should_draw_board_highlight,
    should_show_beginner_hints,
    should_show_summary_hint,
)

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockNode:
    """Minimal GameNode stand-in for ``_compute_summary_context`` tests.

    Mirrors the attribute access pattern of ``test_beginner_hints_summary._MockNode``
    but lives here as a small, locally-scoped helper to keep this file
    self-contained.
    """

    def __init__(
        self,
        *,
        analysis: dict[str, Any] | None = None,
        ownership: list[Any] | None = None,
        policy: list[Any] | None = None,
        points_lost: float | None = None,
        move_number: int = 50,
        depth: int = 0,
        candidate_moves: list[dict[str, Any]] | None = None,
        meaning_tag_id: str | None = None,
    ) -> None:
        self.analysis = analysis
        self.ownership = ownership
        self.policy = policy
        self.points_lost = points_lost
        self.meaning_tag_id = meaning_tag_id
        # get_score_stdev guards on analysis_exists, so surface it.
        self.analysis_exists = bool(analysis)
        self.depth = depth
        self.move: MagicMock | None
        self.parent: MagicMock | None
        if move_number > 0 or candidate_moves is not None:
            self.move = MagicMock()
            self.move.move_number = move_number
        else:
            self.move = None
        if candidate_moves is not None:
            self.parent = MagicMock()
            self.parent.candidate_moves = candidate_moves
        else:
            self.parent = None


# ---------------------------------------------------------------------------
# Section 1: Public gate functions
# ---------------------------------------------------------------------------


class TestShouldShowBeginnerHints:
    """Phase 92: master switch + mode gate (4-way matrix)."""

    @pytest.mark.parametrize(
        "enabled,mode,expected",
        [
            (True, "analyze", True),
            (True, "play", False),
            (False, "analyze", False),
            (False, "play", False),
        ],
    )
    def test_matrix(self, enabled: bool, mode: str, expected: bool) -> None:
        assert should_show_beginner_hints(enabled, mode) is expected


class TestShouldShowSummaryHint:
    """Phase 179: master gate + summary_flag gate."""

    def test_disabled_master(self) -> None:
        assert should_show_summary_hint(False, "analyze", "summary_mistake", None) is False

    def test_play_mode_blocks(self) -> None:
        assert should_show_summary_hint(True, "play", "summary_mistake", None) is False

    def test_no_flags_dict_defaults_true(self) -> None:
        assert should_show_summary_hint(True, "analyze", "summary_mistake", None) is True
        assert should_show_summary_hint(True, "analyze", "summary_freedom", None) is True
        assert should_show_summary_hint(True, "analyze", "katago_uncertain", None) is True

    def test_empty_flags_dict_defaults_true(self) -> None:
        assert should_show_summary_hint(True, "analyze", "summary_mistake", {}) is True

    def test_explicit_flag_true(self) -> None:
        assert (
            should_show_summary_hint(
                True,
                "analyze",
                "summary_mistake",
                {"summary_mistake": True},
            )
            is True
        )

    def test_explicit_flag_false(self) -> None:
        assert (
            should_show_summary_hint(
                True,
                "analyze",
                "summary_mistake",
                {"summary_mistake": False},
            )
            is False
        )

    def test_unknown_flag_key_defaults_true(self) -> None:
        # Unknown keys must not block - the helper is key-driven.
        flags = {"summary_mistake": False, "unknown_future_flag": False}
        assert should_show_summary_hint(True, "analyze", "katago_uncertain", flags) is True

    @pytest.mark.parametrize(
        "key",
        [
            "summary_mistake",
            "summary_freedom",
            "summary_difficulty",
            "katago_uncertain",
            "summary_ownership",
            "summary_policy",
        ],
    )
    def test_each_known_key_respects_false(self, key: str) -> None:
        flags = {key: False}
        assert should_show_summary_hint(True, "analyze", key, flags) is False


class TestShouldDrawBoardHighlight:
    """Phase 92: master + board_highlight flag."""

    def test_disabled_master_blocks(self) -> None:
        assert should_draw_board_highlight(False, "analyze", True) is False

    def test_play_mode_blocks(self) -> None:
        assert should_draw_board_highlight(True, "play", True) is False

    def test_enabled_master_flag_on(self) -> None:
        assert should_draw_board_highlight(True, "analyze", True) is True

    def test_enabled_master_flag_off(self) -> None:
        assert should_draw_board_highlight(True, "analyze", False) is False


class TestIsCoordsValid:
    """Phase 92: bounds check."""

    def test_none_coords_invalid(self) -> None:
        assert is_coords_valid(None, 19) is False

    def test_within_bounds_int(self) -> None:
        assert is_coords_valid((3, 4), 19) is True

    def test_out_of_bounds_negative(self) -> None:
        assert is_coords_valid((-1, 5), 19) is False

    def test_out_of_bounds_too_large(self) -> None:
        assert is_coords_valid((19, 19), 19) is False

    def test_rectangular_board_inside(self) -> None:
        assert is_coords_valid((5, 5), (10, 20)) is True
        assert is_coords_valid((9, 19), (10, 20)) is True

    def test_rectangular_board_outside(self) -> None:
        # x=10 is out of 10-wide board (strict-less-than)
        assert is_coords_valid((10, 5), (10, 20)) is False
        # y=20 is out of 20-tall board
        assert is_coords_valid((5, 20), (10, 20)) is False


class TestNormalizeBoardSize:
    """Phase 92: int -> (n, n)"""

    def test_int_passes_through_squared(self) -> None:
        assert _normalize_board_size(19) == (19, 19)

    def test_tuple_passes_through(self) -> None:
        assert _normalize_board_size((9, 13)) == (9, 13)


# ---------------------------------------------------------------------------
# Section 2: Pure extractors
# ---------------------------------------------------------------------------


class TestExtractPredictedTerritory:
    """Phase 182: ownership grid -> single signed scalar."""

    def test_none_ownership(self) -> None:
        node = _MockNode()
        assert _extract_predicted_territory(node) is None

    def test_empty_ownership(self) -> None:
        node = _MockNode(ownership=[])
        assert _extract_predicted_territory(node) is None

    def test_uniform_black(self) -> None:
        node = _MockNode(ownership=[1.0] * 81)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_uniform_white(self) -> None:
        node = _MockNode(ownership=[-1.0] * 81)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(-1.0)

    def test_balanced_returns_zero(self) -> None:
        node = _MockNode(ownership=[1.0, -1.0] * 40)
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(0.0)

    def test_none_entries_skipped(self) -> None:
        node = _MockNode(ownership=[None, 1.0, None, 1.0])
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_non_numeric_entries_skipped(self) -> None:
        node = _MockNode(ownership=["junk", 0.5, "x", 1.5])
        result = _extract_predicted_territory(node)
        assert result is not None and result == pytest.approx(1.0)

    def test_all_invalid_returns_none(self) -> None:
        node = _MockNode(ownership=[None, None, "x"])
        assert _extract_predicted_territory(node) is None


class TestExtractBestPolicy:
    """Phase 182: policy list -> maximum probability."""

    def test_none_policy(self) -> None:
        node = _MockNode()
        assert _extract_best_policy(node) is None

    def test_empty_policy(self) -> None:
        node = _MockNode(policy=[])
        assert _extract_best_policy(node) is None

    def test_single_value(self) -> None:
        node = _MockNode(policy=[0.42])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.42)

    def test_max_extracted(self) -> None:
        node = _MockNode(policy=[0.1, 0.5, 0.3, 0.05])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.5)

    def test_none_entries_skipped(self) -> None:
        node = _MockNode(policy=[None, 0.4, None])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.4)

    def test_all_zero_returns_none(self) -> None:
        # best stays at 0.0 and the function returns None in that case.
        node = _MockNode(policy=[0.0, 0.0, 0.0])
        assert _extract_best_policy(node) is None

    def test_invalid_entries_skipped(self) -> None:
        node = _MockNode(policy=["x", 0.25, "y"])
        result = _extract_best_policy(node)
        assert result is not None and result == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Section 3: Summary context builder
# ---------------------------------------------------------------------------


class TestComputeSummaryContext:
    """Phase 179.1/182/186: build SummaryHintContext from a GameNode."""

    def test_minimal_node_yields_none_metrics(self) -> None:
        ctx = _compute_summary_context(_MockNode())
        assert ctx.points_lost is None
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False
        assert ctx.root_visits == 0
        assert ctx.score_stdev is None
        assert ctx.is_endgame is False
        assert ctx.predicted_territory is None
        assert ctx.best_policy is None

    def test_points_lost_passed_through(self) -> None:
        ctx = _compute_summary_context(_MockNode(points_lost=3.5))
        assert ctx.points_lost == pytest.approx(3.5)

    def test_move_number_falls_back_to_depth(self) -> None:
        node = _MockNode(move_number=0, depth=120)
        ctx = _compute_summary_context(node)
        assert ctx.move_number == 120

    def test_metrics_exception_returns_none_and_unreliable(self) -> None:
        # difficulty_metrics_from_node raises -> overall_difficulty=None,
        # is_reliable=False. Patch at the ``katrain.core.analysis`` import
        # location (this is where the hints package binds the symbol).
        node = _MockNode(points_lost=1.0)
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            side_effect=RuntimeError("boom"),
        ):
            ctx = _compute_summary_context(node)
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False

    def test_metrics_unknown_returns_none_and_unreliable(self) -> None:
        # ``is_unknown`` attribute present and True -> overall_difficulty=None
        fake_metrics = MagicMock(spec=["is_unknown", "is_reliable", "overall_difficulty"])
        fake_metrics.is_unknown = True
        fake_metrics.is_reliable = True
        fake_metrics.overall_difficulty = 0.5
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            return_value=fake_metrics,
        ):
            ctx = _compute_summary_context(_MockNode())
        assert ctx.overall_difficulty is None
        assert ctx.is_reliable is False

    def test_metrics_known_returns_values(self) -> None:
        fake_metrics = MagicMock(spec=["is_unknown", "is_reliable", "overall_difficulty"])
        fake_metrics.is_unknown = False
        fake_metrics.is_reliable = True
        fake_metrics.overall_difficulty = 0.6
        with patch(
            "katrain.core.analysis.difficulty_metrics_from_node",
            return_value=fake_metrics,
        ):
            ctx = _compute_summary_context(_MockNode())
        assert ctx.overall_difficulty == pytest.approx(0.6)
        assert ctx.is_reliable is True

    def test_thresholds_forwarded(self) -> None:
        ctx = _compute_summary_context(
            _MockNode(),
            threshold_blunder=12.0,
            threshold_mistake=3.0,
            threshold_score_stdev=2.0,
        )
        assert ctx.score_loss_threshold_blunder == 12.0
        assert ctx.score_loss_threshold_mistake == 3.0
        assert ctx.score_stdev_threshold == 2.0

    def test_ownership_and_policy_forwarded(self) -> None:
        node = _MockNode(ownership=[1.0] * 4, policy=[0.1, 0.6, 0.05, 0.2])
        ctx = _compute_summary_context(node)
        assert ctx.predicted_territory == pytest.approx(1.0)
        assert ctx.best_policy == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Section 4: Endgame heuristic
# ---------------------------------------------------------------------------


class TestIsEndgamePosition:
    """Phase 179.2: scoreStdev-based dynamic + move-number fallback."""

    def test_no_analysis_returns_false(self) -> None:
        # No analysis -> get_score_stdev returns None -> falls back to move
        # heuristic. move_number=0 + depth=0 => False.
        assert _is_endgame_position(_MockNode()) is False

    def test_static_fallback_move_at_200(self) -> None:
        # Patch get_score_stdev to return None to force fallback
        with patch("katrain.core.analysis.get_score_stdev", return_value=None):
            assert _is_endgame_position(_MockNode(move_number=200)) is True

    def test_static_fallback_move_below_200(self) -> None:
        with patch("katrain.core.analysis.get_score_stdev", return_value=None):
            assert _is_endgame_position(_MockNode(move_number=150)) is False

    def test_dynamic_stdev_below_threshold(self) -> None:
        # scoreStdev <= 8.0 => True (threshold from logic_phase_dynamic)
        with patch("katrain.core.analysis.get_score_stdev", return_value=7.5):
            assert _is_endgame_position(_MockNode()) is True

    def test_dynamic_stdev_above_threshold(self) -> None:
        with patch("katrain.core.analysis.get_score_stdev", return_value=12.0):
            assert _is_endgame_position(_MockNode()) is False


# ---------------------------------------------------------------------------
# Section 5: Cache wrappers
# ---------------------------------------------------------------------------


class TestGetBeginnerHintCached:
    """Phase 92 cache key includes require_reliable."""

    def test_cache_miss_then_hit(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        # First call: cache attr missing -> compute and store
        # Second call: cache attr present -> return cached value
        sentinel = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=sentinel) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node)
            h2 = get_beginner_hint_cached(MagicMock(), node)
        assert h1 is sentinel
        assert h2 is sentinel
        assert mock.call_count == 1

    def test_require_reliable_change_invalidates(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        sentinel_a = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        sentinel_b = None
        with patch("katrain.core.beginner.hints.compute_beginner_hint", side_effect=[sentinel_a, sentinel_b]) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node, require_reliable=True)
            h2 = get_beginner_hint_cached(MagicMock(), node, require_reliable=False)
        assert h1 is sentinel_a
        assert h2 is sentinel_b
        assert mock.call_count == 2

    def test_none_is_cached_not_recomputed(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=None) as mock:
            h1 = get_beginner_hint_cached(MagicMock(), node)
            h2 = get_beginner_hint_cached(MagicMock(), node)
        assert h1 is None
        assert h2 is None
        # Sentinel-vs-None distinction: must NOT re-call compute on None hit.
        assert mock.call_count == 1

    def test_not_computed_sentinel_triggers_recompute(self) -> None:
        # When the cache attribute exists but equals the sentinel, the
        # wrapper must recompute (not return the sentinel).
        node = MagicMock(spec=["move", "parent", "_beginner_hint_cache"])
        node.move = MagicMock()
        node.move.is_pass = False
        node.move.coords = (3, 3)
        node.parent = MagicMock()
        # Pre-set cache to the sentinel - should still recompute
        node._beginner_hint_cache = _NOT_COMPUTED
        sentinel = BeginnerHint(category=HintCategory.SELF_ATARI, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_beginner_hint", return_value=sentinel) as mock:
            h = get_beginner_hint_cached(MagicMock(), node)
        assert h is sentinel
        assert mock.call_count == 1


class TestGetSummaryHintCached:
    """Phase 179.1/186: cache invalidates on flags / require_reliable /
    user_weak_tags / curator_min_occurrences."""

    def test_cache_miss_then_hit(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        sentinel = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=sentinel) as mock:
            h1 = get_summary_hint_cached(node)
            h2 = get_summary_hint_cached(node)
        assert h1 is sentinel
        assert h2 is sentinel
        assert mock.call_count == 1

    def test_flags_change_invalidates(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        sentinel_a = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        sentinel_b = None
        with patch("katrain.core.beginner.hints.compute_summary_hint", side_effect=[sentinel_a, sentinel_b]) as mock:
            h1 = get_summary_hint_cached(node, summary_flags={"summary_mistake": True})
            h2 = get_summary_hint_cached(node, summary_flags={"summary_mistake": False})
        assert h1 is sentinel_a
        assert h2 is sentinel_b
        assert mock.call_count == 2

    def test_require_reliable_change_invalidates(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=None) as mock:
            get_summary_hint_cached(node, require_reliable=True)
            get_summary_hint_cached(node, require_reliable=False)
        assert mock.call_count == 2

    # Phase 270: ``user_weak_tags`` / ``curator_min_occurrences`` were
    # removed from the dispatcher; the curator-cache invalidation tests
    # are intentionally dropped with them.

    def test_none_cache_hit_does_not_recompute(self) -> None:
        node = _MockNode(analysis={"root": {"visits": 200}})
        with patch("katrain.core.beginner.hints.compute_summary_hint", return_value=None) as mock:
            h1 = get_summary_hint_cached(node)
            h2 = get_summary_hint_cached(node)
        assert h1 is None
        assert h2 is None
        assert mock.call_count == 1


# ---------------------------------------------------------------------------
# Section 6: compute_beginner_hint main paths
# ---------------------------------------------------------------------------


class TestComputeBeginnerHintShortCircuits:
    """Top-of-function guards in compute_beginner_hint."""

    def test_no_move_returns_none(self) -> None:
        node = MagicMock()
        node.move = None
        node.parent = MagicMock()
        assert compute_beginner_hint(MagicMock(), node) is None

    def test_no_parent_returns_none(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = False
        node.parent = None
        assert compute_beginner_hint(MagicMock(), node) is None

    def test_pass_move_returns_none(self) -> None:
        node = MagicMock()
        node.move = MagicMock()
        node.move.is_pass = True
        node.parent = MagicMock()
        assert compute_beginner_hint(MagicMock(), node) is None


class TestComputeBeginnerHintNodeRestoration:
    """The finally-block must restore the original current_node."""

    def test_restores_original_node_when_different(self) -> None:
        # Patch extract_groups_from_game to a no-op so we don't need a
        # fully-shaped game. This isolates the dispatch+restore logic.
        game = MagicMock()
        original_node = MagicMock()
        target_node = MagicMock()
        target_node.move = MagicMock()
        target_node.move.is_pass = False
        target_node.move.coords = (3, 3)
        target_node.parent = MagicMock()
        game.current_node = original_node

        call_order: list[str] = []

        def fake_set_current_node(node: Any) -> None:
            call_order.append(getattr(node, "_label", ""))
            game.current_node = node

        game.set_current_node.side_effect = fake_set_current_node
        original_node._label = "original"
        target_node._label = "target"

        with (
            patch("katrain.core.beginner.hints.extract_groups_from_game", return_value=[]),
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            compute_beginner_hint(game, target_node)

        # The last call must restore the original_node
        assert call_order[-1] == "original"

    def test_no_restore_when_already_at_target(self) -> None:
        game = MagicMock()
        target_node = MagicMock()
        target_node.move = MagicMock()
        target_node.move.is_pass = False
        target_node.move.coords = (3, 3)
        # Pre-populate parent with a sentinel _label so we can observe calls
        target_node.parent = MagicMock()
        target_node.parent._label = "parent"
        target_node._label = "target"
        game.current_node = target_node

        set_calls: list[str] = []

        def fake_set_current_node(node: Any) -> None:
            set_calls.append(getattr(node, "_label", ""))

        game.set_current_node.side_effect = fake_set_current_node

        with (
            patch("katrain.core.beginner.hints.extract_groups_from_game", return_value=[]),
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            compute_beginner_hint(game, target_node)

        # compute_beginner_hint moves to parent (Step 3) then back to
        # target (Step 4, required for CUT_RISK). Restore is skipped
        # because original_node == target_node.
        assert set_calls == ["parent", "target"]


# ---------------------------------------------------------------------------
# Section 7: compute_summary_hint priority chain
# ---------------------------------------------------------------------------


class TestComputeSummaryHintPriorityChain:
    """Phase 179+182+186 priority order: Mistake > Freedom > Difficulty >
    KataGo > Ownership > Policy > Curator."""

    @staticmethod
    def _node_with_visits(visits: int = 200) -> _MockNode:
        # root visits is extracted from analysis.get('root', {}).get('visits')
        return _MockNode(analysis={"root": {"visits": visits}})

    def test_unreliable_visits_returns_none(self) -> None:
        # visits < MIN_SUMMARY_VISITS (100) and require_reliable=True => None
        node = self._node_with_visits(50)
        assert compute_summary_hint(node, require_reliable=True) is None

    def test_low_visits_but_require_reliable_false_runs(self) -> None:
        # visits < MIN_SUMMARY_VISITS but require_reliable=False => runs
        # None of the detectors should fire on an empty node -> still None
        node = self._node_with_visits(50)
        assert compute_summary_hint(node, require_reliable=False) is None

    def test_mistake_outranks_freedom(self) -> None:
        node = self._node_with_visits()
        mistake_hint = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        freedom_hint = BeginnerHint(category=HintCategory.FREEDOM_NARROW, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=mistake_hint),
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=freedom_hint),
        ):
            hint = compute_summary_hint(node)
        assert hint is mistake_hint

    def test_freedom_outranks_difficulty(self) -> None:
        node = self._node_with_visits()
        freedom_hint = BeginnerHint(category=HintCategory.FREEDOM_NARROW, coords=(0, 0), severity=1)
        difficulty_hint = BeginnerHint(category=HintCategory.DIFFICULTY_TRICKY, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=None),
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=freedom_hint),
            patch("katrain.core.beginner.hints.detect_difficulty_summary", return_value=difficulty_hint),
        ):
            hint = compute_summary_hint(node)
        assert hint is freedom_hint

    def test_policy_confident_outranks_policy_conflict(self) -> None:
        node = self._node_with_visits()
        confident = BeginnerHint(category=HintCategory.POLICY_CONFIDENT, coords=(0, 0), severity=0)
        conflict = BeginnerHint(category=HintCategory.POLICY_CONFLICT, coords=(0, 0), severity=1)
        with (
            patch("katrain.core.beginner.hints.detect_policy_confident", return_value=confident),
            patch("katrain.core.beginner.hints.detect_policy_conflict", return_value=conflict),
        ):
            hint = compute_summary_hint(node)
        assert hint is confident

    def test_flag_off_skips_detector(self) -> None:
        node = self._node_with_visits()
        mistake_hint = BeginnerHint(category=HintCategory.MISTAKE_BLUNDER, coords=(0, 0), severity=2)
        with patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=mistake_hint) as mock:
            hint = compute_summary_hint(node, summary_flags={"summary_mistake": False})
        assert hint is None
        assert mock.call_count == 0

    def test_flags_none_defaults_all_true(self) -> None:
        # Pass flags=None: every detector should be called exactly once.
        node = self._node_with_visits()
        with (
            patch("katrain.core.beginner.hints.detect_mistake_summary", return_value=None) as m,
            patch("katrain.core.beginner.hints.detect_freedom_summary", return_value=None) as f,
            patch("katrain.core.beginner.hints.detect_difficulty_summary", return_value=None) as d,
            patch("katrain.core.beginner.hints.detect_katago_uncertain", return_value=None) as k,
            patch("katrain.core.beginner.hints.detect_ownership_dominant", return_value=None) as o,
            patch("katrain.core.beginner.hints.detect_policy_confident", return_value=None) as pc,
            patch("katrain.core.beginner.hints.detect_policy_conflict", return_value=None) as px,
        ):
            hint = compute_summary_hint(node, summary_flags=None)
        assert hint is None
        assert m.call_count == 1
        assert f.call_count == 1
        assert d.call_count == 1
        assert k.call_count == 1
        assert o.call_count == 1
        assert pc.call_count == 1
        assert px.call_count == 1

    # Phase 270: the four ``test_user_weak_tags_*`` /
    # ``test_curator_hint_*`` / ``test_curator_flag_off_*`` tests were
    # removed along with the Curator weak-axis hint. The dispatcher
    # no longer accepts ``user_weak_tags`` / ``curator_min_occurrences``.


# ---------------------------------------------------------------------------
# Section 8: i18n integration sanity
# ---------------------------------------------------------------------------


class TestHintCategoryI18nNamespaces:
    """All HintCategories must produce non-empty i18n namespaces."""

    @pytest.mark.parametrize("category", list(HintCategory))
    def test_namespace_non_empty(self, category: HintCategory) -> None:
        ns = category.i18n_namespace
        assert isinstance(ns, str)
        assert len(ns) > 0

    @pytest.mark.parametrize("category", list(HintCategory))
    def test_fallback_titles_non_empty(self, category: HintCategory) -> None:
        title = category.fallback_title
        body = category.fallback_body
        assert isinstance(title, str) and len(title) > 0
        assert isinstance(body, str) and len(body) > 0

    def test_structural_categories_have_per_category_config_key(self) -> None:
        """Phase 251: structural categories now expose an individual
        toggle via ``HintCategory.config_key`` (returns the category's
        own enum value). Previously this returned ``None`` and the
        category was gated only by the master ``beginner_hints/enabled``
        switch.
        """
        for c in HintCategory:
            if c.is_structural:
                assert c.config_key == c.value, (
                    f"Structural category {c} should map config_key to its own value, got {c.config_key!r}"
                )

    def test_meaning_tag_categories_have_per_category_config_key(self) -> None:
        """Phase 251: meaning-tag fallback categories also expose a
        per-category key (returns the category's own enum value).
        """
        for c in HintCategory:
            if c.is_meaning_tag:
                assert c.config_key == c.value, (
                    f"Meaning-tag category {c} should map config_key to its own value, got {c.config_key!r}"
                )

    def test_summary_categories_have_config_key(self) -> None:
        for c in HintCategory:
            if c.is_summary:
                assert c.config_key is not None


# ---------------------------------------------------------------------------
# Section 9: Constants sanity
# ---------------------------------------------------------------------------


class TestHintConstants:
    """Phase 91/92/179 constants must hold reasonable values."""

    def test_min_reliable_visits_is_positive(self) -> None:
        assert MIN_RELIABLE_VISITS > 0

    def test_min_summary_visits_is_less_than_reliable(self) -> None:
        # Summary hints are more permissive than structural hints.
        assert MIN_SUMMARY_VISITS < MIN_RELIABLE_VISITS

    def test_detector_categories_frozenset_matches_priority_group(self) -> None:
        # The 4 priority detectors must always be in this set.
        expected = {
            HintCategory.SELF_ATARI,
            HintCategory.IGNORE_ATARI,
            HintCategory.MISSED_CAPTURE,
            HintCategory.CUT_RISK,
        }
        assert expected == _DETECTOR_CATEGORIES

    def test_not_computed_is_singleton(self) -> None:
        # The sentinel object must be unique per process.
        from katrain.core.beginner.hints import _NOT_COMPUTED as _NC2

        assert _NOT_COMPUTED is _NC2
