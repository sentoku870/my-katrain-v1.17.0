"""Tests for the GamePhase enum (Phase B-5).

The :class:`GamePhase` enum is the single source of truth for the four
phase buckets used to aggregate loss / move counts in the summary
report. The enum's string values match the historical literals used
in ``summary_logic.phase_moves`` / ``summary_logic.phase_loss`` so
that JSON round-trips remain backward compatible.
"""

from __future__ import annotations

import pytest

from katrain.core.reports.constants import GamePhase


class TestGamePhaseValues:
    def test_values_match_historical_string_keys(self) -> None:
        """The .value strings must match what summary_logic used to hardcode."""
        assert GamePhase.OPENING.value == "opening"
        assert GamePhase.MIDDLE.value == "middle"
        assert GamePhase.YOSE.value == "yose"
        assert GamePhase.UNKNOWN.value == "unknown"

    def test_all_four_buckets_present(self) -> None:
        """Exactly four phases; no extras."""
        assert len(GamePhase) == 4

    def test_buckets_are_distinct(self) -> None:
        values = {p.value for p in GamePhase}
        assert len(values) == 4


class TestGamePhaseFromTag:
    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("opening", GamePhase.OPENING),
            ("middle", GamePhase.MIDDLE),
            ("yose", GamePhase.YOSE),
            ("endgame", GamePhase.YOSE),  # public-facing alias
            ("unknown", GamePhase.UNKNOWN),
            ("", GamePhase.UNKNOWN),
            (None, GamePhase.UNKNOWN),
            ("fuseki", GamePhase.UNKNOWN),  # not in our 4 buckets
            ("ENDGAME", GamePhase.YOSE),  # case insensitive
            ("  yose  ", GamePhase.YOSE),  # whitespace trimmed
        ],
    )
    def test_from_tag_mapping(self, tag: str | None, expected: GamePhase) -> None:
        assert GamePhase.from_tag(tag) == expected


class TestGamePhaseJsonRoundtrip:
    """The .value strings must remain stable because the summary JSON
    and downstream tools key by them. Pinning here means a rename
    shows up as a test failure instead of a silent data shift."""

    @pytest.mark.parametrize("phase", list(GamePhase))
    def test_value_is_pinned(self, phase: GamePhase) -> None:
        # If you change a .value, downstream JSON consumers will break.
        # Bump the JSON schema version when you intentionally change this.
        assert phase.value in {"opening", "middle", "yose", "unknown"}
