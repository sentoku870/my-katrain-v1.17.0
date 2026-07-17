"""Phase 248-C4: tests for ``compute_beginner_hint(aggregate=True)``.

The new ``aggregate`` keyword switches from "first non-None detector
wins" (Phase 91 short-circuit) to "run every detector, return the
highest-severity hint". These tests lock in the public contract:

- ``aggregate=False`` (default) preserves the legacy short-circuit
  behaviour so existing callers / golden files do not change.
- ``aggregate=True`` returns the hint with the largest ``severity``.
- Ties break in favour of the original priority order
  (self_atari → ignore_atari → missed_capture → cut_risk → meaning_tag).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.beginner.hints._dispatch import compute_beginner_hint
from katrain.core.beginner.models import BeginnerHint, HintCategory


def _stub_node(player: str = "B") -> MagicMock:
    """Build a minimal MagicMock that quacks like a GameNode."""
    n = MagicMock()
    n.move = MagicMock()
    n.move.is_pass = False
    n.move.coords = (3, 3)
    n.move.player = player
    n.parent = MagicMock()
    n.analysis_exists = True
    n.analysis = {"root": {"visits": 500}}
    n.meaning_tag_id = None
    return n


def _stub_game(current_node) -> MagicMock:
    g = MagicMock()
    g.current_node = current_node
    g.last_capture = []
    g.set_current_node = MagicMock()
    g.extract_groups_from_game = MagicMock(return_value=[])
    # ``detect_cut_risk`` reads ``game.board_size`` to size the chain
    # analysis. A MagicMock would yield a 0-tuple on unpacking and
    # raise; use a real tuple to bypass the analysis path entirely.
    g.board_size = (19, 19)
    return g


def _hint(category: HintCategory, severity: int) -> BeginnerHint:
    return BeginnerHint(
        category=category,
        coords=(1, 1),
        severity=severity,
        context={"synthetic": True},
    )


class TestAggregateDefault:
    """``aggregate=False`` (default) preserves the Phase 91 short-circuit."""

    def test_default_returns_first_non_none_hint(self):
        """When ``aggregate`` is not passed, the first detector to fire wins."""
        node = _stub_node()
        game = _stub_game(node)

        # self_atari fires; ignore_atari also fires; meaning_tag fires.
        # Legacy short-circuit: self_atari wins.
        sa_hint = _hint(HintCategory.SELF_ATARI, severity=2)
        ia_hint = _hint(HintCategory.IGNORE_ATARI, severity=3)  # higher, but ignored

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=sa_hint),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=ia_hint),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            result = compute_beginner_hint(game, node)

        assert result is sa_hint, "Legacy short-circuit must surface self_atari first"


class TestAggregateAllDetectors:
    """``aggregate=True`` returns the highest-severity hint."""

    def test_returns_highest_severity_among_fired(self):
        """All four structural detectors fire; the highest-severity one wins."""
        node = _stub_node()
        game = _stub_game(node)

        sa_hint = _hint(HintCategory.SELF_ATARI, severity=2)
        ia_hint = _hint(HintCategory.IGNORE_ATARI, severity=3)  # winner
        mc_hint = _hint(HintCategory.MISSED_CAPTURE, severity=1)
        cr_hint = _hint(HintCategory.CUT_RISK, severity=2)

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=sa_hint),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=ia_hint),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=mc_hint),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=cr_hint),
        ):
            result = compute_beginner_hint(game, node, aggregate=True)

        assert result is ia_hint, "Highest severity (3) wins regardless of priority order"

    def test_tie_break_in_priority_order(self):
        """Equal severity → original chain order wins (self_atari first)."""
        node = _stub_node()
        game = _stub_game(node)

        sa_hint = _hint(HintCategory.SELF_ATARI, severity=3)  # winner (priority)
        ia_hint = _hint(HintCategory.IGNORE_ATARI, severity=3)  # same severity, later
        cr_hint = _hint(HintCategory.CUT_RISK, severity=3)  # same severity, even later

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=sa_hint),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=ia_hint),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=cr_hint),
        ):
            result = compute_beginner_hint(game, node, aggregate=True)

        assert result is sa_hint, "Ties must break by original chain order (self_atari first)"

    def test_returns_none_when_nothing_fires(self):
        """No detector fires → ``None`` (same as the legacy path)."""
        node = _stub_node()
        game = _stub_game(node)

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
        ):
            result = compute_beginner_hint(game, node, aggregate=True)

        assert result is None

    def test_only_meaning_tag_fires(self):
        """When no structural detector fires, the meaning_tag fallback is the only candidate."""
        node = _stub_node()
        game = _stub_game(node)
        node.meaning_tag_id = "BAD_SHAPE_TAG"

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
            patch(
                "katrain.core.beginner.hints._dispatch._get_meaning_tag_hint",
                return_value=_hint(HintCategory.BAD_SHAPE, severity=1),
            ),
        ):
            result = compute_beginner_hint(game, node, aggregate=True)

        assert result is not None
        assert result.category == HintCategory.BAD_SHAPE

    def test_meaning_tag_gated_by_require_reliable(self):
        """``require_reliable=True`` with an unreliable node suppresses meaning_tag."""
        node = _stub_node()
        game = _stub_game(node)
        node.analysis = {"root": {"visits": 10}}  # below MIN_RELIABLE_VISITS
        node.analysis_exists = True
        node.meaning_tag_id = "BAD_SHAPE_TAG"

        with (
            patch("katrain.core.beginner.hints.detect_self_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_ignore_atari", return_value=None),
            patch("katrain.core.beginner.hints.detect_missed_capture", return_value=None),
            patch("katrain.core.beginner.hints.detect_cut_risk", return_value=None),
            patch(
                "katrain.core.beginner.hints._dispatch._get_meaning_tag_hint",
                return_value=_hint(HintCategory.BAD_SHAPE, severity=1),
            ),
        ):
            result = compute_beginner_hint(game, node, aggregate=True, require_reliable=True)

        # meaning_tag was suppressed → no hint
        assert result is None
