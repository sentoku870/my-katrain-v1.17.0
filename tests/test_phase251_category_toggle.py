"""Tests for Phase 251: per-category hint toggles.

Verifies the per-category enable map (:func:`build_category_filter`),
the dispatch-layer filter (:func:`_category_enabled`), and the
``HintCategory.config_key`` change (structural / meaning-tag now
expose their own enum value, not ``None``).
"""

from __future__ import annotations

import pytest

from katrain.core.beginner.hints import (
    _category_enabled,
    build_category_filter,
    get_beginner_hint_cached,
)
from katrain.core.beginner.models import HintCategory


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
    """Phase 251: ``build_category_filter`` extracts the 17 known keys."""

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
                "curator_hint",
            )
        }
        result = build_category_filter(bh)
        assert len(result) == 17
        assert all(result[k] is True for k in result)

    def test_only_present_keys_returned(self):
        bh = {"self_atari": False, "cut_risk": True}
        result = build_category_filter(bh)
        assert result == {"self_atari": False, "cut_risk": True}

    def test_unknown_keys_ignored(self):
        """Keys outside the 17 known ones are silently dropped (forward-compat)."""
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
        # Phase 265: cache shape is now 4-tuple (require_reliable, filter_key, curator_key, hint)
        node._beginner_hint_cache = (True, None, None, "SENTINEL")

        # Same filter (None) → cache hit
        assert get_beginner_hint_cached(game_9x9, node) == "SENTINEL"

        # Different filter → cache miss → real recompute
        # (Should NOT return the sentinel.)
        result = get_beginner_hint_cached(game_9x9, node, category_filter={"self_atari": False})
        assert result != "SENTINEL"
