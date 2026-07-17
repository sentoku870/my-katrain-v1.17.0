"""Phase 246-C (M5): regression test for ``clip_pv_for_animation``.

The helper lives in :mod:`katrain.core.analysis.logic_pv` (Kivy-free
so the tests don't have to boot a Kivy app) and is called from the
candidate-marker render path. We pin the clip limit and defensive
behaviour so a future refactor doesn't regress the "long PVs don't
crash the animation" contract.
"""

from __future__ import annotations


class TestClipPVForAnimation:
    """``clip_pv_for_animation`` must cap to 30 steps and survive bad input."""

    def test_short_pv_passes_through(self) -> None:
        from katrain.core.analysis import clip_pv_for_animation

        pv = ["A1", "B2", "C3"]
        assert clip_pv_for_animation(pv) == ["A1", "B2", "C3"]

    def test_exactly_30_pv_passes_through(self) -> None:
        from katrain.core.analysis import (
            PV_ANIMATION_MAX_STEPS,
            clip_pv_for_animation,
        )

        pv = [f"X{i}" for i in range(PV_ANIMATION_MAX_STEPS)]
        assert clip_pv_for_animation(pv) == pv
        assert len(clip_pv_for_animation(pv)) == PV_ANIMATION_MAX_STEPS

    def test_31_pv_is_clipped(self) -> None:
        from katrain.core.analysis import (
            PV_ANIMATION_MAX_STEPS,
            clip_pv_for_animation,
        )

        pv = [f"X{i}" for i in range(31)]
        result = clip_pv_for_animation(pv)
        assert len(result) == PV_ANIMATION_MAX_STEPS
        # First 30 are kept; the 31st is dropped.
        assert result[0] == "X0"
        assert result[-1] == f"X{PV_ANIMATION_MAX_STEPS - 1}"

    def test_long_100_pv_is_clipped(self) -> None:
        from katrain.core.analysis import (
            PV_ANIMATION_MAX_STEPS,
            clip_pv_for_animation,
        )

        pv = [f"X{i}" for i in range(100)]
        result = clip_pv_for_animation(pv)
        assert len(result) == PV_ANIMATION_MAX_STEPS

    def test_none_returns_empty(self) -> None:
        from katrain.core.analysis import clip_pv_for_animation

        assert clip_pv_for_animation(None) == []

    def test_non_list_returns_empty(self) -> None:
        from katrain.core.analysis import clip_pv_for_animation

        assert clip_pv_for_animation("A1") == []  # string
        assert clip_pv_for_animation(42) == []  # int
        assert clip_pv_for_animation(("A1", "B2")) == []  # tuple

    def test_empty_list_returns_empty(self) -> None:
        from katrain.core.analysis import clip_pv_for_animation

        assert clip_pv_for_animation([]) == []

    def test_non_string_elements_coerced_to_string(self) -> None:
        """Defensive: non-string elements must be str()'d so Move.from_gtp
        doesn't crash downstream."""
        from katrain.core.analysis import clip_pv_for_animation

        pv = ["A1", 42, None, "B2"]
        result = clip_pv_for_animation(pv)
        assert result == ["A1", "42", "None", "B2"]

    def test_input_list_not_mutated(self) -> None:
        """The helper must not mutate the caller's list."""
        from katrain.core.analysis import clip_pv_for_animation

        pv = [f"X{i}" for i in range(50)]
        original = list(pv)
        clip_pv_for_animation(pv)
        assert pv == original
