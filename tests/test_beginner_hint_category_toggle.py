"""Tests for Phase 251: per-category beginner-hint toggles.

Phase 251 split the single ``enabled`` flag into 16 individual
category toggles (10 structural + 6 summary/group). These tests
verify:

- :class:`HintCategory.config_key` (structural + meaning-tag now
  expose their own enum value, not ``None``).
- :func:`build_category_filter` extracts the known keys from a
  config dict and ignores unknown keys.
- :func:`_category_enabled` consults the per-category map and
  defaults to ``True`` for missing keys.
- The per-category filter is part of the cache key.
- :func:`_save_beginner_hints_settings` (settings popup) persists
  every per-category toggle.

Phase 3 of the test-suite audit merged two pre-existing files
(``test_phase251_category_toggle.py`` and ``test_phase251_savers.py``)
since both target the same Phase 251 contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from katrain.core.beginner.hints import (
    _category_enabled,
    build_category_filter,
    get_beginner_hint_cached,
)
from katrain.core.beginner.models import HintCategory
from katrain.gui.features.settings_popup_savers import _save_beginner_hints_settings


@pytest.fixture
def mock_ctx() -> MagicMock:
    """Minimal FeatureContext stand-in: only ``config`` / ``set_config_section`` / ``save_config`` are used."""
    ctx = MagicMock()
    ctx.config.return_value = {}
    return ctx


class TestHintCategoryConfigKey:
    """Phase 251: every category exposes a config_key."""

    @pytest.mark.parametrize(
        "category",
        [
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
        ],
    )
    def test_structural_and_meaning_tag_have_per_category_key(self, category):
        """Structural + meaning-tag categories now return their own value."""
        assert category.config_key == category.value

    def test_all_categories_have_non_none_config_key(self):
        """Defensive: no category returns None anymore."""
        for c in HintCategory:
            assert c.config_key is not None
            assert isinstance(c.config_key, str)
            assert c.config_key  # non-empty


class TestBuildCategoryFilter:
    """Phase 251: ``build_category_filter`` extracts the 16 known keys."""

    def test_empty_config_returns_empty_dict(self):
        assert build_category_filter({}) == {}

    def test_none_config_returns_empty_dict(self):
        assert build_category_filter(None) == {}

    def test_all_true(self):
        bh = {
            k: True
            for k in (
                "self_atari",
                "ignore_atari",
                "missed_capture",
                "cut_risk",
                "low_liberties",
                "self_capture_like",
                "bad_shape",
                "heavy_group",
                "missed_defense",
                "urgent_vs_big",
                "summary_mistake",
                "summary_freedom",
                "summary_difficulty",
                "katago_uncertain",
                "summary_ownership",
                "summary_policy",
            )
        }
        result = build_category_filter(bh)
        assert len(result) == 16
        assert all(result[k] is True for k in result)

    def test_only_present_keys_returned(self):
        bh = {"self_atari": False, "cut_risk": True}
        result = build_category_filter(bh)
        assert result == {"self_atari": False, "cut_risk": True}

    def test_unknown_keys_ignored(self):
        """Keys outside the 16 known ones are silently dropped (forward-compat)."""
        bh = {"self_atari": True, "future_category_xyz": False}
        result = build_category_filter(bh)
        assert "future_category_xyz" not in result
        assert result == {"self_atari": True}

    def test_non_dict_returns_empty(self):
        """Defensive: a corrupted config (e.g. list) returns empty filter."""
        assert build_category_filter([1, 2, 3]) == {}  # type: ignore[arg-type]

    def test_disabled_category_appears_as_false(self):
        bh = {"self_atari": False, "summary_mistake": True}
        result = build_category_filter(bh)
        assert result["self_atari"] is False
        assert result["summary_mistake"] is True


class TestCategoryEnabled:
    """Phase 251: ``_category_enabled`` consults the per-category map."""

    def test_missing_key_defaults_to_enabled(self):
        """A category whose key is not in the filter is treated as enabled."""
        assert _category_enabled(HintCategory.SELF_ATARI, {"cut_risk": False}) is True

    def test_empty_filter_means_all_enabled(self):
        assert _category_enabled(HintCategory.SELF_ATARI, None) is True
        assert _category_enabled(HintCategory.SELF_ATARI, {}) is True

    def test_explicit_false_disables(self):
        filter_ = {"self_atari": False}
        assert _category_enabled(HintCategory.SELF_ATARI, filter_) is False

    def test_explicit_true_enables(self):
        filter_ = {"self_atari": True}
        assert _category_enabled(HintCategory.SELF_ATARI, filter_) is True

    def test_group_key_resolves_via_config_key(self):
        """``MISTAKE_BLUNDER`` config_key is ``summary_mistake``."""
        filter_ = {"summary_mistake": False}
        assert _category_enabled(HintCategory.MISTAKE_BLUNDER, filter_) is False
        assert _category_enabled(HintCategory.MISTAKE_MISTAKE, filter_) is False
        assert _category_enabled(HintCategory.MISTAKE_GOOD, filter_) is False


class TestPerCategoryCacheKey:
    """Phase 251: the per-category filter is part of the cache key."""

    def test_different_filter_invalidates_cache(self, game_9x9):
        """Different ``category_filter`` → cache must be re-computed."""
        from katrain.core.game import Move

        game_9x9.play(Move.from_gtp("D4", "B"), analyze=False)
        game_9x9.play(Move.from_gtp("E5", "W"), analyze=False)
        node = game_9x9.current_node

        # Pre-seed cache with a sentinel
        # Phase 251: cache shape is (require_reliable, filter_key, hint).
        # Phase 270: the curator_key was removed; the 3-tuple is current.
        node._beginner_hint_cache = (True, None, "SENTINEL")

        # Same filter (None) → cache hit
        assert get_beginner_hint_cached(game_9x9, node) == "SENTINEL"

        # Different filter → cache miss → real recompute
        # (Should NOT return the sentinel.)
        result = get_beginner_hint_cached(game_9x9, node, category_filter={"self_atari": False})
        assert result != "SENTINEL"


class TestSaveBeginnerHintsSettingsPhase251:
    """Phase 251: 10 individual category toggles are persisted."""

    def test_all_individual_keys_persisted(self, mock_ctx):
        _save_beginner_hints_settings(
            mock_ctx,
            enabled=True,
            summary_mistake=True,
            summary_freedom=True,
            summary_difficulty=True,
            katago_uncertain=True,
            summary_ownership=True,
            summary_policy=True,
            self_atari=False,
            ignore_atari=False,
            missed_capture=True,
            cut_risk=False,
            low_liberties=True,
            self_capture_like=True,
            bad_shape=False,
            heavy_group=True,
            missed_defense=True,
            urgent_vs_big=False,
        )
        call_args, _ = mock_ctx.set_config_section.call_args
        # call_args is a positional tuple: ("beginner_hints", dict)
        assert call_args[0] == "beginner_hints"
        bh = call_args[1]
        # Group toggles
        assert bh["summary_mistake"] is True
        assert bh["summary_freedom"] is True
        # Individual toggles (Phase 251)
        assert bh["self_atari"] is False
        assert bh["ignore_atari"] is False
        assert bh["missed_capture"] is True
        assert bh["cut_risk"] is False
        assert bh["low_liberties"] is True
        assert bh["self_capture_like"] is True
        assert bh["bad_shape"] is False
        assert bh["heavy_group"] is True
        assert bh["missed_defense"] is True
        assert bh["urgent_vs_big"] is False

    def test_all_defaults_keep_keys(self, mock_ctx):
        """Default values (True for everything) still persist the keys so
        a fresh export contains the per-category booleans.
        """
        _save_beginner_hints_settings(mock_ctx, enabled=True)
        call_args, _ = mock_ctx.set_config_section.call_args
        bh = call_args[1]
        for key in (
            "self_atari",
            "ignore_atari",
            "missed_capture",
            "cut_risk",
            "low_liberties",
            "self_capture_like",
            "bad_shape",
            "heavy_group",
            "missed_defense",
            "urgent_vs_big",
        ):
            assert key in bh, f"missing {key} in persisted beginner_hints"
            assert bh[key] is True, f"{key} default must be True"

    def test_preserves_pre_existing_keys(self, mock_ctx):
        """Existing keys (e.g. ``board_highlight``) are preserved through save."""
        mock_ctx.config.return_value = {
            "enabled": True,
            "board_highlight": True,  # legacy key, still in use
            "require_reliable": True,  # another legacy key
        }
        _save_beginner_hints_settings(mock_ctx, enabled=True, cut_risk=False)
        call_args, _ = mock_ctx.set_config_section.call_args
        bh = call_args[1]
        assert bh["board_highlight"] is True
        assert bh["require_reliable"] is True
        assert bh["cut_risk"] is False
