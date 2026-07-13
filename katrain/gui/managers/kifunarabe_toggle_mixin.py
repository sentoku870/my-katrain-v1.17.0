"""Kifunarabe Controller — Auto-toggle / hint-toggle mixin.

Phase A3: extracted from the original 800-line KifunarabeController.
Owns the *masking* logic that hides the actual recorded move while the
user is being asked to guess it.

This mixin also owns the "Top Moves" candidate-marker toggle that the
kifunarabe popup does **not** own directly (the controller is the single
source of truth for whether ``hints`` show).

Cross-mixin attributes
----------------------

- ``_saved_analysis_toggles``: snapshot of the user's pre-session
  ``show_children.active`` / ``eval.active`` flags. ``None`` when no
  snapshot exists. Mirrored from :class:`_ToggleState`.
- ``_last_critical_3_highlight``: int set by ``start_session`` (reset to
  0) and incremented when a Critical 3 position fires its badge, so
  each position fires the badge at most once.
"""

import contextlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class KifunarabeToggleMixin:
    """Auto-toggle / hint-toggle helpers for kifunarabe sessions."""

    # Instance attributes managed by this mixin.
    _saved_analysis_toggles: tuple[bool, bool] | None
    _last_critical_3_highlight: int

    # -- auto toggle ---------------------------------------------------------

    def _is_auto_toggle_enabled(self: Any) -> bool:
        """Whether the user opted into automatic toggle masking for kifu.

        Reads ``kifunarabe/auto_toggle_markers`` from the gui config and
        defaults to True (Phase 177-H default behaviour).
        """
        from katrain.core.constants import (
            KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
            KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
        )

        ctx = self._get_ctx()
        if ctx is None:
            return True
        try:
            return bool(
                ctx.config(
                    KIFUNARABE_AUTO_TOGGLE_MARKERS_KEY,
                    KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT,
                )
            )
        except Exception:  # noqa: BLE001
            return KIFUNARABE_AUTO_TOGGLE_MARKERS_DEFAULT

    def _save_analysis_toggles(self: Any) -> None:
        """Snapshot ``show_children`` / ``eval`` flag state.

        Called by ``start_session`` *before* applying the mask so we
        can restore on every exit path (abort, end-of-mainline,
        SGF load).
        """
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            self._saved_analysis_toggles = None
            return
        try:
            self._saved_analysis_toggles = (
                bool(ac.show_children.active),
                bool(ac.eval.active),
            )
        except Exception:  # noqa: BLE001
            self._saved_analysis_toggles = None

    def _apply_kifu_toggle_mask(self: Any) -> None:
        """Force ``show_children`` / ``eval`` OFF.

        So the actual move is not visually revealed during the
        kifunarabe session.
        """
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            return
        with contextlib.suppress(Exception):
            ac.show_children.active = False
        with contextlib.suppress(Exception):
            ac.eval.active = False

    def _restore_analysis_toggles(self: Any) -> None:
        """Restore the original ``show_children`` / ``eval`` flag state.

        Idempotent: a second call after the saved state has been
        cleared is a no-op.
        """
        saved = getattr(self, "_saved_analysis_toggles", None)
        if saved is None:
            return
        self._saved_analysis_toggles = None
        ctx = self._get_ctx()
        ac = getattr(ctx, "analysis_controls", None) if ctx is not None else None
        if ac is None:
            return
        show_children, eval_dot = saved
        with contextlib.suppress(Exception):
            ac.show_children.active = show_children
        with contextlib.suppress(Exception):
            ac.eval.active = eval_dot

    # -- hint toggle (Top Moves candidate markers) ---------------------------

    def _apply_hint_toggle(self: Any, max_hints: int) -> None:
        """Reflect ``max_hints`` in the existing analysis-controls toggle.

        The popup does not own the "Top Moves" toggle widget; the
        controller is the single point that decides whether candidate
        markers show.

        Args:
            max_hints: Number of hint markers requested (0 = no hints).
        """
        from kivy.clock import Clock

        # Kivy widget property writes must happen on the main thread.
        # The popup ``on_submit`` already runs on the main thread, but
        # we schedule defensively in case this is invoked from
        # elsewhere.
        Clock.schedule_once(lambda _dt: self._do_apply_hint_toggle(max_hints), 0)

    def _do_apply_hint_toggle(self: Any, max_hints: int) -> None:
        """Belt-and-braces toggle work scheduled from ``_apply_hint_toggle``.

        See :meth:`_apply_hint_toggle` for an overview. This second
        stage runs on the main thread and tries the policy/hints
        analysis controls.
        """
        ctx = self._get_ctx()
        if ctx is None:
            return
        ac = getattr(ctx, "analysis_controls", None)
        if ac is None:
            # The KaTrainGui still hasn't finished wiring up the controls.
            # Retry shortly - the analysis_controls widget is created during
            # KV loading in ``build()`` which may not have completed yet.
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: self._do_apply_hint_toggle(max_hints), 0.05)
            return

        # 1) Force the policy toggle's underlying checkbox to False. The
        #    ``panels.kv:435`` binding ``disabled: policy.checkbox.active``
        #    reads the *checkbox*, so we must write through that path.
        policy = getattr(ac, "policy", None)
        policy_checkbox = getattr(policy, "checkbox", None) if policy is not None else None
        if policy_checkbox is not None and getattr(policy_checkbox, "active", False):
            with contextlib.suppress(Exception):
                policy_checkbox.active = False

        # 2) Set the hints toggle to whatever the session asks for.
        hints = getattr(ac, "hints", None)
        if hints is None:
            with contextlib.suppress(Exception):
                self._logger("kifunarabe: analysis_controls.hints not found", level=0)
            return

        hints_checkbox = getattr(hints, "checkbox", None)
        target_active = max_hints > 0
        try:
            if hints_checkbox is not None:
                if bool(hints_checkbox.active) != target_active:
                    hints_checkbox.active = target_active
            else:
                # Fallback: ``AnalysisToggle.active`` setter is now in
                # place.
                if bool(hints.active) != target_active:
                    hints.active = target_active
        except Exception as e:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._logger(
                    f"kifunarabe: failed to set hints={target_active}: {e}", level=0
                )

    def _schedule_redraw(self: Any) -> None:
        """Trigger a board redraw on the main thread.

        Candidate markers become visible only after ``BadukPanWidget.redraw``
        runs (or its hover-contents trigger). We can't safely call draw
        routines off the main thread, so we schedule it.
        """
        ctx = self._get_ctx()
        board_gui = getattr(ctx, "board_gui", None) if ctx is not None else None
        if board_gui is None:
            return
        try:
            from kivy.clock import Clock

            Clock.schedule_once(lambda _dt: self._safe_redraw_board(ctx, board_gui), 0)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._logger("kifunarabe: failed to schedule redraw", level=0)

    @staticmethod
    def _safe_redraw_board(ctx: Any, board_gui: Any) -> None:
        """Safely invoke BadukPanWidget redraw hooks from the main thread."""
        for name in ("redraw_hover_contents_trigger", "draw_board_contents", "redraw"):
            fn = getattr(board_gui, name, None)
            if not callable(fn):
                continue
            with contextlib.suppress(Exception):
                fn()
                return


__all__ = ["KifunarabeToggleMixin"]
