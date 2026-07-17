"""Phase 247-B (H3): regression test for ``compute_pv_filter_preview``.

The settings popup (and Phase 247-C controls panel) both consume
:class:`PVFilterPreview` to show the user the *actual* N → M
reduction for the current node. The dataclass + helper function are
Kivy-free so we can unit-test them without a display.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from katrain.core.analysis import (
    PVFilterConfig,
    PVFilterPreview,
    compute_pv_filter_preview,
    get_pv_filter_config,
)


def _node(analysis_exists: bool, candidates: list[dict]) -> SimpleNamespace:
    """Build a fake GameNode-like object for the preview helper."""
    return SimpleNamespace(analysis_exists=analysis_exists, candidate_moves=candidates)


class TestComputePVFilterPreview:
    """``compute_pv_filter_preview`` returns the right counts."""

    def test_no_node_returns_zero_counts(self) -> None:
        preview = compute_pv_filter_preview(None, get_pv_filter_config("strong"))
        assert preview == PVFilterPreview(0, 0, 0, False)

    def test_node_without_analysis_returns_zero_counts(self) -> None:
        node = _node(analysis_exists=False, candidates=[])
        preview = compute_pv_filter_preview(node, get_pv_filter_config("strong"))
        assert preview == PVFilterPreview(0, 0, 0, False)

    def test_empty_candidate_list(self) -> None:
        node = _node(analysis_exists=True, candidates=[])
        preview = compute_pv_filter_preview(node, get_pv_filter_config("strong"))
        assert preview == PVFilterPreview(0, 0, 0, True)

    def test_off_config_passes_all_through(self) -> None:
        """OFF level → no filter → filtered_count == raw_count."""
        node = _node(
            analysis_exists=True,
            candidates=[
                {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 1, "pointsLost": 5.0, "pv": ["B2"], "move": "B2"},
                {"order": 2, "pointsLost": 10.0, "pv": ["C3"], "move": "C3"},
            ],
        )
        config = get_pv_filter_config("off")  # None
        preview = compute_pv_filter_preview(node, config)
        assert preview.raw_count == 3
        assert preview.filtered_count == 3
        assert preview.best_count == 1
        assert preview.config_active is False

    def test_strong_filter_reduces_count(self) -> None:
        """STRONG level → filter applies → filtered_count < raw_count."""
        node = _node(
            analysis_exists=True,
            candidates=[
                {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 1, "pointsLost": 0.5, "pv": ["B2"], "move": "B2"},
                {"order": 2, "pointsLost": 2.0, "pv": ["C3"], "move": "C3"},  # > 1.0
                {"order": 3, "pointsLost": 5.0, "pv": ["D4"], "move": "D4"},  # > 1.0
            ],
        )
        config = get_pv_filter_config("strong")  # max_points_lost=1.0, max_pv_length=6
        preview = compute_pv_filter_preview(node, config)
        # best_move + 1 pass = 2
        assert preview.raw_count == 4
        assert preview.filtered_count == 2
        assert preview.best_count == 1
        assert preview.config_active is True

    def test_kifunarabe_bypass_keeps_all(self) -> None:
        """H4: kifunarabe mode → filter is bypassed → all candidates kept."""
        node = _node(
            analysis_exists=True,
            candidates=[
                {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 1, "pointsLost": 10.0, "pv": ["B2"], "move": "B2"},
                {"order": 2, "pointsLost": 100.0, "pv": ["C3"], "move": "C3"},
            ],
        )
        config = get_pv_filter_config("strong")
        preview = compute_pv_filter_preview(node, config, in_kifu=True)
        assert preview.raw_count == 3
        assert preview.filtered_count == 3  # bypassed
        assert preview.config_active is False  # reflects bypass

    def test_no_best_move(self) -> None:
        """All candidates with order=999 → best_count=0."""
        node = _node(
            analysis_exists=True,
            candidates=[
                {"order": 999, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 999, "pointsLost": 0.5, "pv": ["B2"], "move": "B2"},
            ],
        )
        config = get_pv_filter_config("medium")
        preview = compute_pv_filter_preview(node, config)
        assert preview.raw_count == 2
        assert preview.best_count == 0

    def test_returns_dataclass_instance(self) -> None:
        node = _node(analysis_exists=True, candidates=[{"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"}])
        preview = compute_pv_filter_preview(node, get_pv_filter_config("medium"))
        assert isinstance(preview, PVFilterPreview)
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            preview.raw_count = 999  # type: ignore[misc]

    def test_filter_with_custom_config(self) -> None:
        """Sanity: a custom PVFilterConfig produces the expected counts."""
        node = _node(
            analysis_exists=True,
            candidates=[
                {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 1, "pointsLost": 0.5, "pv": ["B2"], "move": "B2"},
                {"order": 2, "pointsLost": 1.5, "pv": ["C3"], "move": "C3"},
            ],
        )
        # Custom very-strict: max_points_lost=0.4 → only best_move survives
        config = PVFilterConfig(max_candidates=10, max_points_lost=0.4, max_pv_length=20)
        preview = compute_pv_filter_preview(node, config)
        assert preview.raw_count == 3
        assert preview.filtered_count == 1
        assert preview.best_count == 1

    def test_position_specific(self) -> None:
        """H3's whole point: different nodes → different previews."""
        # Node A: 5 candidates, all pass weak filter
        node_a = _node(
            analysis_exists=True,
            candidates=[{"order": i, "pointsLost": 0.0, "pv": [f"X{i}"], "move": f"X{i}"} for i in range(5)],
        )
        # Node B: 2 candidates, 1 of which fails strong filter
        node_b = _node(
            analysis_exists=True,
            candidates=[
                {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
                {"order": 1, "pointsLost": 5.0, "pv": ["B2"], "move": "B2"},
            ],
        )
        config = get_pv_filter_config("strong")
        preview_a = compute_pv_filter_preview(node_a, config)
        preview_b = compute_pv_filter_preview(node_b, config)
        # Different counts confirm position-aware behaviour
        assert preview_a.raw_count == 5
        assert preview_b.raw_count == 2
        assert preview_a.filtered_count >= preview_b.filtered_count


class TestPreviewWidgetIntegration:
    """Lightweight test that ``widget.last_pv_filter_preview`` is
    populated by :func:`prepare_hint_moves` (Phase 247-B / 247-C
    contract). Uses heavy mocking to avoid Kivy initialization."""

    @pytest.mark.skipif(
        True,  # Phase 226-D (D1): badukpan_hints imports kivy.metrics
        reason=(
            "badukpan_hints imports kivy.metrics at module load which "
            "crashes in headless test env. The preview contract is "
            "also pinned via test_pv_filter_kifunarabe_skip's AST check."
        ),
    )
    def test_prepare_hint_moves_stashes_preview(self) -> None:

        from katrain.gui.badukpan_hints import prepare_hint_moves

        katrain = MagicMock()
        katrain.config.side_effect = lambda key, *args: {
            "general/pv_filter_level": "strong",
            "general/skill_preset": "standard",
            "general/player_rank": "5d",
        }.get(key, args[0] if args else None)
        katrain.analysis_controls.hints.active = True
        katrain.analysis_controls.policy.active = False
        katrain.is_fog_active.return_value = False
        katrain.kifunarabe_mode = False
        katrain.game.end_result = None
        katrain.game.board_size = (19, 19)
        katrain._kifunarabe_controller = None
        katrain.get_trainer_config.return_value = MagicMock(low_visits=25)

        node = MagicMock()
        node.analysis_exists = True
        node.candidate_moves = [
            {"order": 0, "pointsLost": 0.0, "pv": ["A1"], "move": "A1"},
            {"order": 1, "pointsLost": 5.0, "pv": ["B2"], "move": "B2"},
        ]
        node.children = []
        katrain.game.current_node = node

        widget = MagicMock()
        widget.katrain = katrain
        prepare_hint_moves(widget, node, None)
        # Phase 247-B: widget.last_pv_filter_preview is a PVFilterPreview
        assert hasattr(widget, "last_pv_filter_preview")
        preview = widget.last_pv_filter_preview
        assert preview.raw_count == 2
        assert preview.best_count == 1
        assert preview.config_active is True
