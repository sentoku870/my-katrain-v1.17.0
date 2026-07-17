"""Phase 247-A (L5): regression test for ``resolve_pv_filter_config_cached``.

The LRU-cached wrapper around :func:`get_pv_filter_config` powers the
hot path in :func:`prepare_hint_moves` — every hover re-render calls
it. We pin the memoization contract (same input → same object) so a
future refactor doesn't accidentally break the speedup.

The cache is process-wide; tests that mutate the cache must call
``cache_clear()`` to avoid bleed.
"""

from __future__ import annotations

import pytest

from katrain.core.analysis import (
    PVFilterConfig,
    get_pv_filter_config,
    resolve_pv_filter_config_cached,
)


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Each test gets a fresh cache so hit/miss counts are deterministic."""
    resolve_pv_filter_config_cached.cache_clear()
    yield
    resolve_pv_filter_config_cached.cache_clear()


class TestResolvePVFilterConfigCached:
    """``resolve_pv_filter_config_cached`` is an LRU-cached wrapper."""

    def test_returns_same_object_for_repeated_calls(self) -> None:
        """Memoization: identical input returns the *same* object."""
        c1 = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        c2 = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        assert c1 is c2, "Cache miss on identical input"

    def test_cache_hits_accumulate(self) -> None:
        """3 calls with same input → 1 miss + 2 hits."""
        for _ in range(3):
            resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        info = resolve_pv_filter_config_cached.cache_info()
        assert info.hits == 2
        assert info.misses == 1
        assert info.currsize == 1

    def test_different_inputs_dont_collide(self) -> None:
        """Different player_rank → different cache entries."""
        c_5d = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        c_7d = resolve_pv_filter_config_cached("auto", "standard", 19, "7d")
        # 5d → advanced → strong (cap 4)
        # 7d → pro → expert (cap 3)
        assert c_5d.max_candidates == 4
        assert c_7d.max_candidates == 3
        info = resolve_pv_filter_config_cached.cache_info()
        assert info.misses == 2
        assert info.currsize == 2

    def test_different_board_size_separate_cache_entries(self) -> None:
        """board_size participates in the cache key (Phase 246-D M1 scaling)."""
        c_19 = resolve_pv_filter_config_cached("strong", "standard", 19, "")
        c_9 = resolve_pv_filter_config_cached("strong", "standard", 9, "")
        # strong.max_pv_length = 6 → 6 (19路) vs 3 (9路)
        assert c_19.max_pv_length == 6
        assert c_9.max_pv_length == 3

    def test_off_returns_none_and_caches(self) -> None:
        """``off`` returns None — we still cache the result so the
        second call doesn't repeat the lookup."""
        c1 = resolve_pv_filter_config_cached("off", "standard", 19, "5d")
        c2 = resolve_pv_filter_config_cached("off", "standard", 19, "5d")
        assert c1 is None
        assert c2 is None
        info = resolve_pv_filter_config_cached.cache_info()
        assert info.misses == 1
        assert info.hits == 1

    def test_returns_pvfilter_config_instance(self) -> None:
        """Sanity: cached result is a PVFilterConfig (frozen dataclass)."""
        config = resolve_pv_filter_config_cached("medium", "standard", 19, "")
        assert isinstance(config, PVFilterConfig)
        assert config.max_candidates == 8
        assert config.max_points_lost == 2.0

    def test_matches_uncached_get_pv_filter_config(self) -> None:
        """Behavioural parity: cached wrapper returns the same value as
        the uncached function (just memoized)."""
        cached = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        uncached = get_pv_filter_config("auto", skill_preset="standard", board_size=19, player_rank="5d")
        assert cached == uncached

    def test_cache_clear_resets_stats(self) -> None:
        """``cache_clear()`` is the supported way to invalidate the cache
        (used by tests and by future config-change hooks)."""
        resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        before = resolve_pv_filter_config_cached.cache_info()
        assert before.currsize == 1
        resolve_pv_filter_config_cached.cache_clear()
        after = resolve_pv_filter_config_cached.cache_info()
        assert after.currsize == 0
        assert after.hits == 0
        assert after.misses == 0

    def test_maxsize_32_prevents_unbounded_growth(self) -> None:
        """The cache is bounded — 33 distinct inputs does not crash, and
        LRU eviction kicks in."""
        for i in range(40):
            resolve_pv_filter_config_cached("auto", "standard", 19, f"rank_{i}")
        info = resolve_pv_filter_config_cached.cache_info()
        # Bounded by maxsize=32
        assert info.currsize <= 32
        assert info.misses == 40  # all unique

    def test_pure_function_guarantee(self) -> None:
        """Documenting the contract: the function is pure w.r.t. its
        inputs. (No state, no side effects.)"""
        c1 = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        # Re-call with different unrelated inputs that share no key
        resolve_pv_filter_config_cached("auto", "standard", 19, "7d")
        c3 = resolve_pv_filter_config_cached("auto", "standard", 19, "5d")
        # c1 and c3 must be identical objects (deterministic + cached)
        assert c1 is c3
