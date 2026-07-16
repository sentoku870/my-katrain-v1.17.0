"""Phase 229-B: tests for :func:`katrain.core.analysis.resolve_skill_preset`.

The resolver is the single decision point that turns the two
user-facing settings (``general/skill_preset`` and ``general/player_rank``)
into the analysis-side preset name.  The priority chain is:

1. ``preset_override`` if set, not ``"auto"``, and valid
2. ``player_rank`` if set and parseable
3. ``default`` (``"standard"``)

These tests pin all three branches plus the validation fallback.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import (
    DEFAULT_SKILL_PRESET,
    SKILL_PRESETS,
    rank_to_skill_preset,
    resolve_skill_preset,
)
from katrain.common.rank import Rank


# ---------------------------------------------------------------------------
# Priority 1: explicit override
# ---------------------------------------------------------------------------


class TestOverrideTakesPriority:
    @pytest.mark.parametrize(
        "override",
        ["relaxed", "beginner", "standard", "advanced", "pro"],
    )
    def test_valid_override_wins_over_rank(self, override: str) -> None:
        # Even an "inappropriate" rank (e.g. 9d + "beginner" preset) is
        # honoured because the user explicitly asked for it.
        assert resolve_skill_preset(override, "9d") == override

    def test_override_wins_when_rank_empty(self) -> None:
        assert resolve_skill_preset("advanced", "") == "advanced"
        assert resolve_skill_preset("advanced", None) == "advanced"

    def test_override_wins_when_rank_invalid(self) -> None:
        # Garbage rank must not silently demote the override.
        assert resolve_skill_preset("pro", "xyzzy") == "pro"

    def test_invalid_override_falls_through_to_rank(self) -> None:
        # An unrecognised preset name (e.g. legacy config key) should not
        # crash; we drop to the rank-based fallback instead.
        assert resolve_skill_preset("not-a-real-preset", "5k") == "beginner"


# ---------------------------------------------------------------------------
# Priority 2: rank-driven
# ---------------------------------------------------------------------------


class TestRankDerivation:
    @pytest.mark.parametrize(
        "rank_str,expected",
        [
            ("30k", "relaxed"),
            ("15k", "relaxed"),
            ("11k", "relaxed"),
            ("10k", "beginner"),
            ("7k", "beginner"),
            ("5k", "beginner"),
            ("4k", "standard"),
            ("1k", "standard"),
            ("1d", "standard"),
            ("2d", "advanced"),
            ("5d", "advanced"),
            ("6d", "pro"),
            ("9d", "pro"),
        ],
    )
    def test_rank_drives_preset(self, rank_str: str, expected: str) -> None:
        assert resolve_skill_preset(None, rank_str) == expected

    def test_kanji_rank_resolves(self) -> None:
        # rank_to_skill_preset accepts raw strings and parses them.
        assert resolve_skill_preset(None, "4段") == "advanced"
        assert resolve_skill_preset(None, "6級") == "beginner"
        assert resolve_skill_preset(None, "初段") == "standard"
        assert resolve_skill_preset(None, "10段") == "pro"  # 10段 -> 9d

    def test_rank_object_input(self) -> None:
        rank = Rank.parse("5k")
        assert rank is not None
        assert resolve_skill_preset(None, rank) == "beginner"


# ---------------------------------------------------------------------------
# Priority 3: default fallback
# ---------------------------------------------------------------------------


class TestDefaultFallback:
    def test_no_inputs_returns_default(self) -> None:
        assert resolve_skill_preset(None, None) == DEFAULT_SKILL_PRESET

    def test_empty_inputs_returns_default(self) -> None:
        assert resolve_skill_preset("", "") == DEFAULT_SKILL_PRESET

    def test_only_invalid_inputs_returns_default(self) -> None:
        assert resolve_skill_preset("garbage", "garbage") == DEFAULT_SKILL_PRESET
        assert resolve_skill_preset("auto", None) == DEFAULT_SKILL_PRESET

    def test_custom_default_argument(self) -> None:
        # Callers can pass an explicit default for tests / special flows.
        assert resolve_skill_preset(None, None, default="pro") == "pro"
        assert resolve_skill_preset(None, "", default="beginner") == "beginner"


# ---------------------------------------------------------------------------
# "auto" semantics (Phase 229 abolishes UI but keeps legacy compat)
# ---------------------------------------------------------------------------


class TestAutoSemantics:
    def test_auto_treated_as_no_override(self) -> None:
        # Phase 229-C removes "auto" from the UI but old config files may
        # still contain it.  resolve_skill_preset must treat it like None.
        assert resolve_skill_preset("auto", "5k") == "beginner"
        assert resolve_skill_preset("auto", None) == DEFAULT_SKILL_PRESET

    def test_auto_with_invalid_rank_falls_back(self) -> None:
        assert resolve_skill_preset("auto", "garbage") == DEFAULT_SKILL_PRESET


# ---------------------------------------------------------------------------
# rank_to_skill_preset direct API
# ---------------------------------------------------------------------------


class TestRankToSkillPresetDirect:
    def test_none_returns_default(self) -> None:
        assert rank_to_skill_preset(None) == DEFAULT_SKILL_PRESET

    def test_rank_string(self) -> None:
        assert rank_to_skill_preset("5k") == "beginner"

    def test_rank_object(self) -> None:
        rank = Rank.parse("4段")
        assert rank is not None
        assert rank_to_skill_preset(rank) == "advanced"

    def test_empty_string_returns_default(self) -> None:
        assert rank_to_skill_preset("") == DEFAULT_SKILL_PRESET


# ---------------------------------------------------------------------------
# Cross-cutting: full SKILL_PRESETS coverage via rank
# ---------------------------------------------------------------------------


class TestFullCoverage:
    @pytest.mark.parametrize("preset_name", list(SKILL_PRESETS.keys()))
    def test_every_preset_reachable_from_some_rank(self, preset_name: str) -> None:
        # Sanity check: there exists at least one rank that maps to each
        # preset (otherwise the rank->preset bridge is incomplete).
        matches = [
            r for r in ["30k", "11k", "10k", "5k", "4k", "1d", "2d", "5d", "6d", "9d"]
            if resolve_skill_preset(None, r) == preset_name
        ]
        assert matches, f"No rank maps to preset {preset_name!r}"