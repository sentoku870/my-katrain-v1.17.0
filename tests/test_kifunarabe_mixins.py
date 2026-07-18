"""Phase A3: KifunarabeController mixin unit tests.

Architecture Review follow-up: split the 800-line KifunarabeController
into four mixin modules and verify:

1. ``_safe_redraw_board`` (static method on
   :class:`KifunarabeToggleMixin`) - tries each candidate redraw
   method in priority order and falls back gracefully.
2. ``_expected_move_gtp`` (module-level helper in
   :mod:`katrain.core.study.kifunarabe`) - extracts the GTP coord of
   the mainline child of a node. Phase 249-α: the controller's
   ``_expected_gtp_from_node`` was consolidated into this core helper,
   so the tests now target the canonical implementation.
3. ``node_move_gtp`` (module-level helper in
   :mod:`kifunarabe_controller`) - converts (coords, player) into a
   GTP string, including ``"pass"`` for ``None``.
4. The facade's MRO and public-API surface stays intact across the
   refactor (so external callers and downstream mixins keep working).
   Phase 249-α: ``is_fog_active`` was removed from the facade (it was
   dead code; the live sites resolve through the ``KaTrainGui``
   stub).

The existing test_kifunarabe_controller.py suite continues to cover
the controller facade end-to-end; this file focuses on pieces that
are reachable without a Kivy clock or context.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from katrain.core.sgf_parser import Move
from katrain.gui.managers.kifunarabe_controller import (
    KifunarabeController,
    node_move_gtp,
)
from katrain.gui.managers.kifunarabe_guess_mixin import KifunarabeGuessMixin
from katrain.gui.managers.kifunarabe_session_mixin import KifunarabeSessionMixin
from katrain.gui.managers.kifunarabe_summary_mixin import KifunarabeSummaryMixin
from katrain.gui.managers.kifunarabe_toggle_mixin import KifunarabeToggleMixin

# ---------------------------------------------------------------------------
# Section 1: _safe_redraw_board (static method, Kivy-free)
# ---------------------------------------------------------------------------


class _FakeBoard:
    """Minimal stand-in for a BadukPanWidget.

    Records which render hook was invoked, in priority order:
    ``redraw_hover_contents_trigger`` > ``draw_board_contents`` > ``redraw``.
    """

    def __init__(self, *, available: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        for name in available:
            setattr(self, name, lambda n=name: self.calls.append(n))

    def __getattr__(self, name: str) -> Any:
        # Missing attributes must look NOT-callable so ``_safe_redraw_board``
        # skips them and tries the next candidate.
        raise AttributeError(name)


class TestSafeRedrawBoard:
    """``KifunarabeToggleMixin._safe_redraw_board`` preferred-name cascade."""

    def test_prefers_redraw_hover_contents_trigger(self) -> None:
        board = _FakeBoard(
            available=(
                "redraw_hover_contents_trigger",
                "draw_board_contents",
                "redraw",
            )
        )
        KifunarabeToggleMixin._safe_redraw_board(MagicMock(), board)
        assert board.calls == ["redraw_hover_contents_trigger"]

    def test_falls_back_to_draw_board_contents(self) -> None:
        board = _FakeBoard(available=("draw_board_contents", "redraw"))
        KifunarabeToggleMixin._safe_redraw_board(MagicMock(), board)
        assert board.calls == ["draw_board_contents"]

    def test_falls_back_to_redraw(self) -> None:
        board = _FakeBoard(available=("redraw",))
        KifunarabeToggleMixin._safe_redraw_board(MagicMock(), board)
        assert board.calls == ["redraw"]

    def test_handles_raising_callable(self) -> None:
        # A raising first-priority hook must NOT block the cascade.
        def raising() -> None:
            raise RuntimeError("simulated Kivy failure")

        board = _FakeBoard()
        board.redraw_hover_contents_trigger = raising  # type: ignore[attr-defined]
        # ``draw_board_contents`` doesn't exist on MagicMock-ish behaviour,
        # so we set it explicitly:
        board.draw_board_contents = lambda: board.calls.append("draw_board_contents")  # type: ignore[attr-defined]
        KifunarabeToggleMixin._safe_redraw_board(MagicMock(), board)
        assert "draw_board_contents" in board.calls

    def test_no_hooks_is_no_op(self) -> None:
        board = _FakeBoard(available=())
        # None of the three hooks exist as callable; should not raise.
        KifunarabeToggleMixin._safe_redraw_board(MagicMock(), board)
        assert board.calls == []


# ---------------------------------------------------------------------------
# Section 2: _expected_move_gtp (core helper, single source of truth)
# ---------------------------------------------------------------------------


class _MockChild:
    def __init__(self, coords: tuple[int, int] | None, player: str) -> None:
        self.move = MagicMock()
        self.move.coords = coords
        self.move.player = player
        self.move.gtp = lambda: Move(coords, player=player).gtp() if coords is not None else "pass"


class _MockChildNoMove:
    move = None


class _MockChildBadGtp:
    def __init__(self) -> None:
        self.move = MagicMock()
        self.move.gtp = lambda: 12345  # not a str


class _MockChildRaisingGtp:
    def __init__(self) -> None:
        self.move = MagicMock()
        self.move.gtp = lambda: (_ for _ in ()).throw(RuntimeError("simulated"))


class _MockNode:
    def __init__(self, children: list[Any]) -> None:
        self.ordered_children = children


class TestExpectedMoveGtp:
    """``katrain.core.study.kifunarabe._expected_move_gtp`` (Phase 249-α)."""

    def _helper(self) -> Any:
        from katrain.core.study.kifunarabe import _expected_move_gtp

        return _expected_move_gtp

    def test_returns_mainline_child_gtp(self) -> None:
        node = _MockNode([_MockChild((3, 4), "B")])
        assert self._helper()(node) == "D5"

    def test_no_children_returns_none(self) -> None:
        assert self._helper()(_MockNode([])) is None

    def test_child_without_move_returns_none(self) -> None:
        node = _MockNode([_MockChildNoMove()])
        assert self._helper()(node) is None

    def test_child_with_non_str_gtp_returns_none(self) -> None:
        node = _MockNode([_MockChildBadGtp()])
        assert self._helper()(node) is None

    def test_uses_mainline_first_child(self) -> None:
        node = _MockNode(
            [
                _MockChild((3, 4), "B"),  # mainline
                _MockChild((5, 5), "W"),
            ]
        )
        assert self._helper()(node) == "D5"

    def test_gtp_raising_returns_none(self) -> None:
        """Phase 249-α: a raising ``gtp()`` is swallowed."""
        node = _MockNode([_MockChildRaisingGtp()])
        assert self._helper()(node) is None

    def test_uses_getattr_for_ordered_children(self) -> None:
        """Phase 249-α: a node without ``ordered_children`` is a no-op,
        not an AttributeError."""

        class _Bare:
            pass

        assert self._helper()(_Bare()) is None


# ---------------------------------------------------------------------------
# Section 3: node_move_gtp (module-level helper)
# ---------------------------------------------------------------------------


class TestNodeMoveGtp:
    """``katrain.gui.managers.kifunarabe_controller.node_move_gtp``."""

    def test_none_coords_returns_pass(self) -> None:
        assert node_move_gtp(None, "B") == "pass"

    def test_specific_coords_b(self) -> None:
        assert node_move_gtp((3, 4), "B") == "D5"

    def test_specific_coords_w(self) -> None:
        assert node_move_gtp((0, 0), "W") == "A1"

    def test_corner_move(self) -> None:
        assert node_move_gtp((18, 18), "B") == "T19"


# ---------------------------------------------------------------------------
# Section 4: facade MRO / public-API surface
# ---------------------------------------------------------------------------


class _NoOpLogger:
    def __call__(self, *args: Any, **kwargs: Any) -> None:
        return None


def _noop_log(msg: Any, level: int = 0) -> None:
    return None


def _make_controller(
    *,
    mode: bool = False,
    session: Any = None,
    ctx: Any = None,
) -> KifunarabeController:
    """Build a minimal KifunarabeController for MRO / surface checks.

    No DI callables are exercised here - we only verify the class
    composition and surface.
    """
    return KifunarabeController(
        get_ctx=lambda: ctx,
        get_config=lambda *a, **kw: None,
        get_game=lambda: None,
        get_controls=lambda: None,
        get_mode=lambda: mode,
        set_mode=lambda v: None,
        logger=_noop_log,
    )


class TestFacadeStructure:
    """Composition order and surface that downstream callers rely on."""

    def test_mro_lists_four_mixins(self) -> None:
        mro = KifunarabeController.__mro__
        names = [c.__name__ for c in mro]
        assert "KifunarabeController" in names
        assert "KifunarabeSessionMixin" in names
        assert "KifunarabeGuessMixin" in names
        assert "KifunarabeSummaryMixin" in names
        assert "KifunarabeToggleMixin" in names
        # Session is listed FIRST in the MRO (it depends on all the
        # others), Toggle is listed LAST (it has no cross-mixin
        # dependencies). The two book-end the four-mixin chain.
        assert names.index("KifunarabeSessionMixin") < names.index("KifunarabeToggleMixin")

    def test_init_sets_default_state_attributes(self) -> None:
        ctrl = _make_controller()
        assert ctrl._session is None
        assert ctrl._summary_popup is None
        assert ctrl._saved_analysis_toggles is None
        assert ctrl._last_critical_3_highlight == 0
        # Phase 249-α: ``_source_sgf_path`` removed. Confirm it does
        # not exist any more (regression guard).
        assert not hasattr(ctrl, "_source_sgf_path")

    def test_public_accessors_present(self) -> None:
        ctrl = _make_controller(mode=True)
        assert hasattr(ctrl, "session")
        assert hasattr(ctrl, "is_active")
        # Phase 249-α: ``is_fog_active`` removed from the facade.
        assert not hasattr(ctrl, "is_fog_active")
        assert ctrl.is_active() is True

    def test_lifecycle_methods_present(self) -> None:
        ctrl = _make_controller()
        for name in (
            "disable_if_needed",
            "start_session",
            "abort_session",
            "on_mode_change",
            "handle_guess",
        ):
            assert callable(getattr(ctrl, name)), name

    def test_default_on_guess_resolved_swallow_errors(self) -> None:
        # No ctx attribute -> swallow and stay quiet.
        from katrain.gui.managers.kifunarabe_controller import (
            _default_on_guess_resolved,
        )

        _default_on_guess_resolved(object(), correct=True, expected_gtp="D5", guessed_gtp="D5")
        _default_on_guess_resolved(object(), correct=False, expected_gtp=None, guessed_gtp=None)


# ---------------------------------------------------------------------------
# Section 5: mixin slot membership (sanity)
# ---------------------------------------------------------------------------


class TestMixinSlots:
    """Each method lives in exactly one mixin - no cross-pollination."""

    def test_session_methods_belong_to_session_mixin(self) -> None:
        for name in (
            "disable_if_needed",
            "start_session",
            "abort_session",
            "on_mode_change",
            "_finish_position",
            "_check_session_ended",
            "_end_session",
        ):
            assert name in KifunarabeSessionMixin.__dict__, name

    def test_guess_methods_belong_to_guess_mixin(self) -> None:
        for name in (
            "handle_guess",
            "_record_wrong_guess",
            "_play_guessed",
            "_advance_after_user_turn",
            "_auto_advance_until_user_turn",
            "_play_move",
            "_notify_guess",
            "_highlight_critical_3_if_reached",
        ):
            assert name in KifunarabeGuessMixin.__dict__, name

    def test_toggle_methods_belong_to_toggle_mixin(self) -> None:
        for name in (
            "_is_auto_toggle_enabled",
            "_save_analysis_toggles",
            "_apply_kifu_toggle_mask",
            "_restore_analysis_toggles",
            "_apply_hint_toggle",
            "_do_apply_hint_toggle",
            "_schedule_redraw",
            "_safe_redraw_board",
        ):
            assert name in KifunarabeToggleMixin.__dict__, name

    def test_summary_methods_belong_to_summary_mixin(self) -> None:
        for name in (
            "_get_show_summary",
            "_dismiss_summary_popup_if_open",
            "_get_on_guess_resolved",
            "_show_session_summary",
        ):
            assert name in KifunarabeSummaryMixin.__dict__, name

    def test_facade_only_owns_constructor_and_public_accessors(self) -> None:
        # ``KifunarabeController.__dict__`` should contain exactly these
        # non-dunder methods (mixin methods live on the parents).
        # Phase 249-α: ``is_fog_active`` removed; only ``__init__`` and
        # the ``session`` property + ``is_active`` remain.
        implemented = {name for name, value in KifunarabeController.__dict__.items() if callable(value)}
        assert implemented == {"__init__", "is_active"}
