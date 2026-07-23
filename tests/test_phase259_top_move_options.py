"""Tests for the top-move hint marker key assembly (Phase 259 I-11).

The keys dict used to populate the Kivy markup was assembled inline
inside ``katrain.gui.badukpan_hints.draw_kata_hint_marker``, which
forced headless tests to copy the block verbatim. The copy had
already drifted from the production code once (missing the
``format_loss_str`` call for the delta-score column, and a different
ownership-resolution policy).

Phase E moves the key-population logic into the Kivy-independent
helper :mod:`katrain.core.gui_utils.top_move_keys`. This file imports
that helper directly and verifies the assembled dict.

The ``TOP_MOVE_OPTIONS`` constant and ``TOP_MOVE_*`` key names live
in :mod:`katrain.core.constants`; we re-export them through the core
helper so callers can index the assembled dict with the same names
they use everywhere else.
"""

from __future__ import annotations

from katrain.core.constants import (
    TOP_MOVE_DELTA_SCORE,
    TOP_MOVE_DELTA_WINRATE,
    TOP_MOVE_OPTIONS,
    TOP_MOVE_OWNERSHIP,
    TOP_MOVE_POLICY,
    TOP_MOVE_SCORE,
    TOP_MOVE_SCORE_STDEV,
    TOP_MOVE_VISITS,
    TOP_MOVE_WINRATE,
)
from katrain.core.gui_utils.top_move_keys import assemble_top_move_keys


class TestTopMoveOptionsExtended:
    """Phase 259: TOP_MOVE_OPTIONS now includes 3 new entries."""

    def test_includes_score_stdev(self) -> None:
        assert TOP_MOVE_SCORE_STDEV in TOP_MOVE_OPTIONS

    def test_includes_policy(self) -> None:
        assert TOP_MOVE_POLICY in TOP_MOVE_OPTIONS

    def test_includes_ownership(self) -> None:
        assert TOP_MOVE_OWNERSHIP in TOP_MOVE_OPTIONS

    def test_total_options_count(self) -> None:
        """5 original (excluding TOP_MOVE_NOTHING) + 3 new = 8 functional + 1 NOTHING."""
        functional = [o for o in TOP_MOVE_OPTIONS if o != "top_move_nothing"]
        assert len(functional) == 8

    def test_nothing_still_present(self) -> None:
        """Backward compat: TOP_MOVE_NOTHING must remain in the list."""
        assert "top_move_nothing" in TOP_MOVE_OPTIONS


class TestAssembleTopMoveKeys:
    """Phase 259: score_stdev / policy / ownership keys are populated by
    the Kivy-independent core helper. The GUI wrapper passes the themed
    ``format_loss_str`` / ``format_visits`` strings; here we exercise
    the pure-Python defaults.
    """

    def test_score_stdev_formatted(self) -> None:
        keys = assemble_top_move_keys({"scoreStdev": 3.5, "visits": 100})
        assert keys[TOP_MOVE_SCORE_STDEV] == "3.5"

    def test_score_stdev_missing_defaults_to_zero(self) -> None:
        keys = assemble_top_move_keys({})
        assert keys[TOP_MOVE_SCORE_STDEV] == "0.0"

    def test_score_stdev_none_defaults_to_zero(self) -> None:
        """KataGo can send scoreStdev=None when visits are too low."""
        keys = assemble_top_move_keys({"scoreStdev": None})
        assert keys[TOP_MOVE_SCORE_STDEV] == "0.0"

    def test_policy_formatted_as_percent(self) -> None:
        keys = assemble_top_move_keys({"prior": 0.5})
        assert keys[TOP_MOVE_POLICY] == "50.0%"

    def test_policy_zero(self) -> None:
        keys = assemble_top_move_keys({"prior": 0.0})
        assert keys[TOP_MOVE_POLICY] == "0.0%"

    def test_policy_one_hundred_percent(self) -> None:
        keys = assemble_top_move_keys({"prior": 1.0})
        assert keys[TOP_MOVE_POLICY] == "100.0%"

    def test_policy_missing_defaults_to_zero(self) -> None:
        keys = assemble_top_move_keys({})
        assert keys[TOP_MOVE_POLICY] == "0.0%"

    def test_ownership_black_dominant(self) -> None:
        keys = assemble_top_move_keys({"ownership": 0.78})
        assert keys[TOP_MOVE_OWNERSHIP] == "B78"

    def test_ownership_white_dominant(self) -> None:
        keys = assemble_top_move_keys({"ownership": -0.82})
        assert keys[TOP_MOVE_OWNERSHIP] == "W82"

    def test_ownership_zero_shows_B0(self) -> None:
        keys = assemble_top_move_keys({"ownership": 0.0})
        # 0.0 is non-negative, so shows B0 (not W0).
        assert keys[TOP_MOVE_OWNERSHIP] == "B0"

    def test_ownership_missing_defaults_to_zero(self) -> None:
        keys = assemble_top_move_keys({})
        assert keys[TOP_MOVE_OWNERSHIP] == "B0"

    def test_all_previous_keys_still_present(self) -> None:
        """Phase 259 must NOT regress the pre-existing 5 columns."""
        keys = assemble_top_move_keys(
            {
                "pointsLost": 1.5,
                "scoreLead": -0.3,
                "winrate": 0.55,
                "winrateLost": 0.02,
                "visits": 200,
                "scoreStdev": 2.0,
                "prior": 0.4,
                "ownership": 0.3,
            }
        )
        for key in (
            TOP_MOVE_DELTA_SCORE,
            TOP_MOVE_SCORE,
            TOP_MOVE_WINRATE,
            TOP_MOVE_DELTA_WINRATE,
            TOP_MOVE_VISITS,
        ):
            assert key in keys, f"regression: pre-Phase 259 key {key} missing"

    def test_pre_formatted_delta_score_and_visits_overrides(self) -> None:
        """The GUI wrapper passes themed ``format_loss_str`` /
        ``format_visits`` strings via ``delta_score_formatted`` /
        ``visits_formatted``. Verify they are used verbatim.
        """
        keys = assemble_top_move_keys(
            {"pointsLost": 1.5, "visits": 42},
            delta_score_formatted="−1.5",
            visits_formatted="42 visits",
        )
        assert keys[TOP_MOVE_DELTA_SCORE] == "−1.5"
        assert keys[TOP_MOVE_VISITS] == "42 visits"

    def test_player_sign_affects_winrate_and_score(self) -> None:
        """``player_sign`` flips both ``winrate`` and ``scoreLead`` so the
        opponent view shows the same board state from the other side.
        Keys that are sign-invariant (visits, scoreStdev, prior,
        ownership, delta_winrate) keep the same value either way.
        """
        black = assemble_top_move_keys({"winrate": 0.6, "scoreLead": 3.0}, player_sign=1)
        white = assemble_top_move_keys({"winrate": 0.6, "scoreLead": 3.0}, player_sign=-1)
        # winrate is mirrored around 0.5.
        assert black[TOP_MOVE_WINRATE] == "60.0"
        assert white[TOP_MOVE_WINRATE] == "40.0"
        # scoreLead is sign-flipped.
        assert black[TOP_MOVE_SCORE] == "3.0"
        assert white[TOP_MOVE_SCORE] == "-3.0"
        # visits / scoreStdev / prior / ownership are sign-invariant.
        black_full = assemble_top_move_keys(
            {
                "winrate": 0.6,
                "scoreLead": 3.0,
                "visits": 200,
                "scoreStdev": 2.5,
                "prior": 0.4,
                "ownership": 0.3,
            },
            player_sign=1,
        )
        white_full = assemble_top_move_keys(
            {
                "winrate": 0.6,
                "scoreLead": 3.0,
                "visits": 200,
                "scoreStdev": 2.5,
                "prior": 0.4,
                "ownership": 0.3,
            },
            player_sign=-1,
        )
        for key in (
            TOP_MOVE_VISITS,
            TOP_MOVE_SCORE_STDEV,
            TOP_MOVE_POLICY,
            TOP_MOVE_OWNERSHIP,
        ):
            assert black_full[key] == white_full[key], (
                f"sign-invariant key {key} unexpectedly differs: black={black_full[key]!r} white={white_full[key]!r}"
            )

    def test_none_move_dict_returns_empty_dict(self) -> None:
        """Defensive: ``None`` input yields ``{}`` rather than raising."""
        assert assemble_top_move_keys(None) == {}  # type: ignore[arg-type]


class TestProductionCodeUsesNewKeys:
    """AST guard: production code uses the core helper and the
    TOP_MOVE_* constants from :mod:`katrain.core.constants`.

    Phase E moved the key-population logic into the Kivy-independent
    helper ``assemble_top_move_keys``; the GUI file no longer
    contains the literal ``"scoreStdev"`` / ``"prior"`` /
    ``"ownership"`` references (those live in the core helper). We
    therefore guard on the helper import + the constant references,
    which is the production-wiring that has to be maintained.
    """

    @staticmethod
    def _source() -> str:
        from pathlib import Path

        return (Path(__file__).parent.parent / "katrain" / "gui" / "badukpan_hints.py").read_text(encoding="utf-8")

    def test_uses_core_helper(self) -> None:
        text = self._source()
        assert "from katrain.core.gui_utils.top_move_keys import assemble_top_move_keys" in text
        assert "assemble_top_move_keys(" in text

    def test_top_move_constants_still_imported(self) -> None:
        """The GUI references the ``TOP_MOVE_*`` constants for the
        "show this column" option list (``TOP_MOVE_OPTIONS``) and for
        the ``TOP_MOVE_NOTHING`` sentinel that disables the marker.

        The Kivy markup template in this file uses ``{size}`` and
        ``{smallsize}`` placeholders, not the ``TOP_MOVE_*``
        constants directly; the constants are consumed only by the
        core helper that produces the ``keys`` dict. So this guard
        is restricted to the constants the GUI actually uses.
        """
        text = self._source()
        for constant in ("TOP_MOVE_NOTHING", "TOP_MOVE_OPTIONS"):
            assert constant in text, (
                f"{constant} missing from badukpan_hints.py; the GUI needs it for the option-list filter."
            )
