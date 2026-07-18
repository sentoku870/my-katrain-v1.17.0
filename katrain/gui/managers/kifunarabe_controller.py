"""Kifunarabe (棋譜並べ) Controller facade.

Phase A3 (Architecture Review follow-up): the original 800-line God Class
was split into four responsibility-focused mixin classes:

- :class:`KifunarabeSessionMixin`: lifecycle (start / end / abort /
  disable_if_needed / finish_position / check_session_ended).
- :class:`KifunarabeToggleMixin`: auto-toggle save/restore for
  ``show_children`` / ``eval``, and "Top Moves" hint toggle.
- :class:`KifunarabeGuessMixin`: click handling, correct/wrong guess
  recording, opponent auto-advance, Critical 3 highlight.
- :class:`KifunarabeSummaryMixin`: summary popup callback resolution and
  dismissal.

The four mixins all inherit from ``object`` (no shared base), so the
composite :class:`KifunarabeController` does **not** need an ``__init__``
chore that calls ``super().__init__()`` — Python's C3 linearization
keeps method resolution deterministic across the four modules.

Responsibilities retained by the facade:

- ``__init__`` wiring (``get_ctx`` / ``get_config`` / ``get_game`` /
  ``get_controls`` / ``get_mode`` / ``set_mode`` / ``logger``), and
  initialisation of the mixin-owned attributes (e.g. ``_session``,
  ``_summary_popup``, ``_saved_analysis_toggles``).
- Public accessors: ``session`` property, ``is_active``, ``is_fog_active``.
- Convenience module-level helpers (``disable_kifunarabe_if_active``,
  ``node_move_gtp``, ``_default_on_guess_resolved``) used by the rest of
  the GUI.

External import path (``from katrain.gui.managers.kifunarabe_controller
import KifunarabeController``) is **unchanged** so the existing
integration tests and modules keep working without modification.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.gui.managers.kifunarabe_guess_mixin import KifunarabeGuessMixin
from katrain.gui.managers.kifunarabe_session_mixin import KifunarabeSessionMixin
from katrain.gui.managers.kifunarabe_summary_mixin import KifunarabeSummaryMixin
from katrain.gui.managers.kifunarabe_toggle_mixin import KifunarabeToggleMixin

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.core.study.kifunarabe import KifunarabeSession, KifunarabeSummary
    from katrain.core.study.kifunarabe_history import KifunarabeHistoryStore
    from katrain.core.study.kifunarabe_weakness_export import KifunarabeWeaknessExporter
    from katrain.gui.controlspanel import ControlsPanel


# Callback signatures (UI callbacks injected via DI for testability).
# Re-declared here for backward compatibility with code that imports the
# type aliases from this module. The "real" definition lives in
# ``kifunarabe_summary_mixin``.
OnGuessResolvedFn = Callable[
    [Any, bool, str | None, str | None],
    None,
]
"""Signature: ``on_guess_resolved(ctx, correct, expected_gtp, guessed_gtp)``.

Called after every click so the GUI can play a sound / show a status hint.
"""

ShowSummaryFn = Callable[[Any, "KifunarabeSummary"], None]
"""Signature: ``show_summary(ctx, summary)``. Called when the session
ends with results."""


class KifunarabeController(
    KifunarabeSessionMixin,
    KifunarabeGuessMixin,
    KifunarabeSummaryMixin,
    KifunarabeToggleMixin,
):
    """Facade composing the four kifunarabe responsibility mixins.

    Composition order (left = first in MRO):

    1. :class:`KifunarabeSessionMixin` — lifecycle, talks to every
       other mixin.
    2. :class:`KifunarabeGuessMixin` — clicks / guess recording, talks
       to ``_finish_position`` / ``_check_session_ended`` (Session) and
       ``_get_on_guess_resolved`` (Summary).
    3. :class:`KifunarabeSummaryMixin` — popup callback resolution,
       talks to ``_end_session`` callers (Session).
    4. :class:`KifunarabeToggleMixin` — toggle save/restore, called by
       Session (``start_session`` / ``disable_if_needed`` /
       ``_end_session`` / ``abort_session``).

    Public API surface (unchanged across the Phase A3 refactor):

    - ``__init__`` (DI wiring)
    - ``session`` property, ``is_active()``, ``is_fog_active()``
    - ``start_session(config)``
    - ``disable_if_needed()``
    - ``abort_session()``
    - ``on_mode_change(value: bool)``
    - ``handle_guess(coords)``
    """

    def __init__(
        self,
        get_ctx: Callable[[], Any],
        get_config: Callable[..., Any],
        get_game: Callable[[], Game | None],
        get_controls: Callable[[], ControlsPanel | None],
        get_mode: Callable[[], bool],
        set_mode: Callable[[bool], None],
        logger: Callable[..., None],
        show_summary_fn: ShowSummaryFn | None = None,
        on_guess_resolved_fn: OnGuessResolvedFn | None = None,
        history_store: KifunarabeHistoryStore | None = None,
        weakness_exporter: KifunarabeWeaknessExporter | None = None,
    ) -> None:
        """Initialize with dependency injection.

        Args:
            get_ctx: Returns KaTrainGui instance (for UI callbacks).
            get_config: ``config(setting, default=None)`` accessor.
            get_game: Returns current Game or None.
            get_controls: Returns ControlsPanel or None.
            get_mode: Returns ``kifunarabe_mode`` value.
            set_mode: Sets ``kifunarabe_mode`` value.
            logger: ``log(message, level)`` function.
            show_summary_fn: UI callback for end-of-session summary.
            on_guess_resolved_fn: UI callback for guess resolution
                events.
            history_store: Phase 249-β. Optional persistent history
                store. When provided, every finished session is
                appended to a JSON file under ``history_store.directory``.
            weakness_exporter: Phase 249-γ. Optional exporter for
                WRONG_GUESS results. When provided, every finished
                session is appended to a JSON file under
                ``weakness_exporter.directory``. The session's
                ``config.auto_export_weaknesses`` must also be True
                for the export to fire.
        """
        self._get_ctx = get_ctx
        self._get_config = get_config
        self._get_game = get_game
        self._get_controls = get_controls
        self._get_mode = get_mode
        self._set_mode = set_mode
        self._logger = logger

        self._show_summary_fn = show_summary_fn
        self._on_guess_resolved_fn = on_guess_resolved_fn
        self._history_store: KifunarabeHistoryStore | None = history_store
        self._weakness_exporter: KifunarabeWeaknessExporter | None = weakness_exporter

        # Mixin-owned attributes — initialised here so attribute access
        # doesn't rely on dynamic attribute creation, which would
        # confuse mypy and tooling.
        self._session: KifunarabeSession | None = None
        # Phase 181-B: tracks the currently-visible summary popup so the
        # panel "Abort" button can dismiss it even after the natural
        # end has already cleared ``_session`` and toggled mode off.
        # Without this, the user has to click the popup's own "abort"
        # button to dismiss it after a max_moves cap run.
        self._summary_popup: Any = None
        # Phase 177-H: holds the snapshot of the user's
        # ``show_children`` / ``eval`` flags during a kifunarabe
        # session, so they can be restored on every exit path. Cleared
        # by ``KifunarabeToggleMixin._restore_analysis_toggles``.
        self._saved_analysis_toggles: tuple[bool, bool] | None = None
        # Tracks the last move_number that fired a Critical 3 badge, so
        # each position fires at most once. Reset by
        # ``KifunarabeSessionMixin.start_session``.
        self._last_critical_3_highlight: int = 0
        # Phase 181-B: tracks the path of the SGF that started the
        # most recent session, so exit paths can clean it up. Set/cleared
        # by start_session / _end_session; declared here so mypy sees it.
        self._source_sgf_path: str | None = None

    # -- public accessors (the only methods living on the facade) ----------

    @property
    def session(self) -> KifunarabeSession | None:
        """Current session, or None if mode is off."""
        return self._session

    def is_active(self) -> bool:
        """True iff the mode is currently on (UI-level state)."""
        return self._get_mode()

    def is_fog_active(self) -> bool:
        """KV compatibility shim - mirrors ActiveReviewController.

        Returns True if kifunarabe mode is ON.
        """
        return self._get_mode()


# ---------------------------------------------------------------------------
# Module-level helpers used by the rest of the GUI (kept here so the
# kifunarabe controller facade stays the canonical import path).
# ---------------------------------------------------------------------------


def disable_kifunarabe_if_active(katrain: Any) -> None:
    """Phase 178: centralised helper to disable kifunarabe from any
    exit path.

    Looks up the kifunarabe controller on ``katrain`` and calls
    ``disable_if_needed()``. Errors are swallowed because this helper
    is used from "cleanup" call sites (regular SGF load, future
    popup-manager dismissals, save-game-as-after-kifunarabe, etc.)
    where a kifunarabe failure must never block the main flow.

    Callers should use this function instead of repeating the
    ``getattr(katrain, "_kifunarabe_controller", None)`` lookup +
    nested ``if`` + try/except dance.
    """
    controller = getattr(katrain, "_kifunarabe_controller", None)
    if controller is None:
        return
    with contextlib.suppress(Exception):
        controller.disable_if_needed()


def node_move_gtp(coords: tuple[int, int] | None, player: str) -> str | None:
    """Return the GTP representation of a ``(coords, player)`` click.

    Args:
        coords: Board coordinates (col, row) zero-based; or ``None``
            for a pass move.
        player: "B" or "W".

    Returns:
        GTP coordinate string (``"D4"``) or "pass" for None coords.
    """
    from katrain.core.sgf_parser import Move

    if coords is None:
        return "pass"
    return Move(coords, player=player).gtp()


def _default_on_guess_resolved(
    ctx: Any,
    correct: bool,
    expected_gtp: str | None,
    guessed_gtp: str | None,
) -> None:
    """Default guess-resolved callback (plays a stone sound on correct)."""
    if correct and hasattr(ctx, "_play_stone_sound"):
        with contextlib.suppress(Exception):
            ctx._play_stone_sound()


__all__ = [
    "KifunarabeController",
    "OnGuessResolvedFn",
    "ShowSummaryFn",
    "disable_kifunarabe_if_active",
    "node_move_gtp",
]
