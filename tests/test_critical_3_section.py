"""Phase 248-F1: tests for ``critical_3_section_for`` exception handling.

Before Phase 248 the function swallowed all ``KeyError`` exceptions and
logged at ``OUTPUT_DEBUG``, so users with default logging never saw
"Critical 3: 0 件" had an actual cause. This test locks in the
"log at INFO + return empty list" contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from katrain.core.constants import OUTPUT_INFO


def _build_minimal_ctx(katrain_log: MagicMock | None = None):
    """Build a minimal KarteContext for ``critical_3_section_for``.

    Only the fields the section actually touches are populated. The
    ``game`` field is the only one the section uses directly, so we
    provide a MagicMock that pretends to have ``katrain.log``.
    """
    from katrain.core.reports.karte.sections.context import KarteContext

    katrain = MagicMock()
    katrain.log = katrain_log if katrain_log is not None else MagicMock()
    game = MagicMock()
    game.katrain = katrain

    # snapshot is passed through to many other sections but
    # critical_3_section_for only uses game + important_moves + lang.
    snapshot = MagicMock()
    important_moves: list = []

    # We rely on KarteContext being frozen=True + required positional
    # arguments. To avoid the full field list, bypass __init__ and
    # build a "shaped" object via __new__.
    ctx = object.__new__(KarteContext)
    # Set only the fields actually read by critical_3_section_for.
    object.__setattr__(ctx, "game", game)
    object.__setattr__(ctx, "important_moves", important_moves)
    object.__setattr__(ctx, "lang", "ja")
    # Snapshot is unused in the function body but downstream imports
    # sometimes touch it; provide a stub just in case.
    object.__setattr__(ctx, "snapshot", snapshot)
    return ctx


class TestCritical3SectionExceptionHandling:
    """Phase 248-F1: ``KeyError`` is now logged at INFO, not silently swallowed."""

    def test_keyerror_logs_at_info_level(self):
        """A ``KeyError`` from ``select_critical_moves`` must be logged at INFO
        and the function must return an empty list (not raise).
        """
        log_mock = MagicMock()
        ctx = _build_minimal_ctx(katrain_log=log_mock)

        with patch(
            "katrain.core.reports.karte.sections.important_moves.select_critical_moves",
            side_effect=KeyError("missing-node-attribute"),
        ):
            from katrain.core.reports.karte.sections.important_moves import critical_3_section_for

            result = critical_3_section_for(ctx, player="B", level="normal")

        assert result == []
        log_mock.assert_called_once()
        args, _ = log_mock.call_args
        # First arg: message, second arg: log level
        assert "Critical 3 skipped" in args[0]
        assert args[1] == OUTPUT_INFO
        # Player must be in the message so users know which side is empty.
        assert "B" in args[0]

    def test_keyerror_with_no_katrain_still_returns_empty(self):
        """When ``ctx.game.katrain`` is None (e.g. test fixtures), the
        function must not crash on the ``log`` call.
        """
        game = MagicMock()
        game.katrain = None
        snapshot = MagicMock()

        from katrain.core.reports.karte.sections.context import KarteContext

        ctx = object.__new__(KarteContext)
        object.__setattr__(ctx, "game", game)
        object.__setattr__(ctx, "important_moves", [])
        object.__setattr__(ctx, "lang", "ja")
        object.__setattr__(ctx, "snapshot", snapshot)

        with patch(
            "katrain.core.reports.karte.sections.important_moves.select_critical_moves",
            side_effect=KeyError("missing"),
        ):
            from katrain.core.reports.karte.sections.important_moves import critical_3_section_for

            # Must not raise (the ``if ctx.game.katrain`` guard protects the log call).
            result = critical_3_section_for(ctx, player="W", level="strict")
        assert result == []

    def test_no_log_call_on_success(self):
        """When ``select_critical_moves`` returns without raising, the
        section must not log an error.
        """
        from katrain.core.analysis.critical_moves import CriticalMove

        # Build a CriticalMove for player B and an empty list for player W.
        cm = CriticalMove(
            move_number=10,
            player="B",
            gtp_coord="D4",
            score_loss=5.0,
            delta_winrate=0.0,
            meaning_tag_id="overplay",
            meaning_tag_label="過大",
            position_difficulty="normal",
            reason_tags=(),
            score_stdev=2.0,
            game_phase="middle",
            importance_score=5.0,
            critical_score=5.0,
            complexity_discounted=False,
        )

        log_mock = MagicMock()
        ctx = _build_minimal_ctx(katrain_log=log_mock)

        with patch(
            "katrain.core.reports.karte.sections.important_moves.select_critical_moves",
            return_value=[cm],
        ):
            from katrain.core.reports.karte.sections.important_moves import (
                critical_3_section_for,
            )

            result = critical_3_section_for(ctx, player="B", level="normal")

        # Success path: no log call (the function may or may not call
        # log on the success path for debug purposes; we only check
        # that the *error* log is silent here).
        for call in log_mock.call_args_list:
            args, _ = call
            assert "Critical 3 skipped" not in args[0], "Success path must not log skip messages"
        # And the result should not be empty (we returned a CriticalMove).
        assert len(result) >= 1
