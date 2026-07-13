"""Kifunarabe Controller — Summary popup mixin.

Phase A3: extracted from the original 800-line KifunarabeController.
Owns the *summary-popup* logic: resolving the optional
``show_summary`` callback (with Phase 181-B tracking), dismissing any
visible popup, and the in-session summary display path
(``_show_session_summary`` used by ``_check_session_ended``).

Cross-mixin attributes
----------------------

- ``_summary_popup``: the currently-visible summary popup instance, or
  ``None`` when no popup is open. Initialised by the facade's
  ``__init__``. Set by ``_get_show_summary``'s wrapped default impl
  via the ``on_popup_opened`` callback, and cleared by
  ``_dismiss_summary_popup_if_open``.

Helper methods from other mixins (``_get_on_guess_resolved`` etc.)
are resolved via the facade's MRO.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# Callback type aliases -- declared here so the public ``node_move_gtp``
# helper in the facade module can stay in one place without circular
# imports. The aliases mirror the definitions in kifunarabe_controller.py
# and are kept identical; the facade re-exports the public names.
ShowSummaryFn = Callable[[Any, "KifunarabeSummary"], None]
"""Signature: ``show_summary(ctx, summary)``. Called when the session
ends with results."""


class KifunarabeSummaryMixin:
    """Summary popup + callback resolution for kifunarabe sessions."""

    # -- summary callback resolution ----------------------------------------

    def _get_show_summary(self: Any) -> ShowSummaryFn:
        """Get summary UI function (lazy import if not injected)."""
        if self._show_summary_fn is not None:
            return self._show_summary_fn  # type: ignore[no-any-return]  # _show_summary_fn is Callable[..., None] | None (injected); ShowSummaryFn is narrower but compatible at runtime

        # Phase 181-B: wrap the default impl so the controller can
        # track the popup instance for later dismissal from the panel
        # button.
        def _tracked_show_summary(ctx: Any, summary: Any) -> None:
            from katrain.gui.features.kifunarabe_summary import (
                show_kifunarabe_summary as _impl,
            )

            _impl(
                ctx,
                summary,
                on_popup_opened=lambda p: setattr(self, "_summary_popup", p),
            )

        return _tracked_show_summary

    def _dismiss_summary_popup_if_open(self: Any) -> None:
        """Phase 181-B: dismiss any visible summary popup and clear tracking.

        Called from ``abort_session`` so a single panel-button press
        closes the popup regardless of whether the session is still
        active. Also called from ``disable_if_needed`` to keep the
        controller's state consistent.
        """
        popup = self._summary_popup
        if popup is None:
            return
        with contextlib.suppress(Exception):
            popup.dismiss()
        self._summary_popup = None

    def _get_on_guess_resolved(self: Any) -> Any:
        """Get guess-resolved UI function (lazy import if not injected)."""
        if self._on_guess_resolved_fn is not None:
            return self._on_guess_resolved_fn
        # Lazy import to avoid pulling kivy at module import time.
        from katrain.gui.managers.kifunarabe_controller import _default_on_guess_resolved

        return _default_on_guess_resolved

    # -- summary display -----------------------------------------------------

    def _show_session_summary(self: Any) -> None:
        """Show the summary popup without changing the kifunarabe mode.

        Called when the session ended (e.g. via ``_finalize_at_limit``).
        The mode property remains True so the user can pick another
        SGF from the summary popup.
        """
        if self._session is None or self._session.results is None:
            return
        if not self._session.results:
            return
        with contextlib.suppress(Exception):
            summary = self._session.get_summary()
            self._get_show_summary()(self._get_ctx(), summary)


__all__ = ["KifunarabeSummaryMixin", "ShowSummaryFn"]


# Late import for the type alias (the Protocol depends on a type that's
# exported by the core. Resolved at module-load time; safe because we
# import only types.).
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe import KifunarabeSummary
