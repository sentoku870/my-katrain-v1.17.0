"""Popup for the Kifunarabe (棋譜並べ) feature.

Components:
- :class:`KifunarabeSetupContent`: side/hints chooser (shown after SGF pick).
- :func:`open_kifunarabe_sgf_selector`: shows the SGF file picker first, then
  chains into the setup popup.

Notes
-----
The file picker uses the dedicated config key ``kifunarabe/sgf_load`` so the
kifunarabe browsing folder is independent from the regular
``general/sgf_load`` ("自分の対局用") folder. The SGF load itself bypasses
``SGFManager.load_sgf_file`` and calls ``do_new_game`` directly with
``sgf_filename=None`` so the original file is never associated with the
session - subsequent "Save Game" therefore never overwrites the source.
"""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout

from katrain.gui.popups._base import I18NPopup

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe import KifunarabeConfig


# Config key for the dedicated kifunarabe SGF browsing folder.
KIFUNARABE_SGF_LOAD_KEY = "kifunarabe/sgf_load"


# Map from i18n-key (ref) to canonical KifunarabeConfig.turn value
_REF_TO_TURN: dict[str, str] = {
    "kifunarabe:setup:side_both": "both",
    "kifunarabe:setup:side_black": "B",
    "kifunarabe:setup:side_white": "W",
}

# Map from i18n-key (ref) to KifunarabeConfig.max_moves value (0 = all)
_REF_TO_MAX_MOVES: dict[str, int] = {
    "kifunarabe:setup:moves_50": 50,
    "kifunarabe:setup:moves_100": 100,
    "kifunarabe:setup:moves_150": 150,
    "kifunarabe:setup:moves_all": 0,
}


def _prefill_from_config(prefill_config: Any) -> tuple[int, int, int, bool]:
    """Phase 292-B: convert a previous KifunarabeConfig into spinner indices.

    Pure function so it can be unit-tested without Kivy (the spinner
    widget itself requires a display).

    Returns:
        ``(side_index, hints_index, max_moves_index, auto_export)`` tuple.
        Falls back to defaults (0, 3, 3, False) when the config is None
        or has unrecognised values, so an invalid prefill never crashes
        the popup open path.
    """
    side_index = 0
    hints_index = 3  # default: 3 hints
    max_moves_index = 3  # default: 全部 (0)
    auto_export = False
    if prefill_config is None:
        return side_index, hints_index, max_moves_index, auto_export

    turn = getattr(prefill_config, "turn", "both")
    side_index = {
        "both": 0,
        "B": 1,
        "W": 2,
    }.get(turn, 0)

    try:
        max_hints = int(getattr(prefill_config, "max_hints", 3))
        if max_hints in (0, 1, 2, 3, 4, 5):
            hints_index = max_hints
    except (TypeError, ValueError):
        pass

    try:
        max_moves = int(getattr(prefill_config, "max_moves", 0))
        max_moves_index = {
            50: 0,
            100: 1,
            150: 2,
            0: 3,  # all
        }.get(max_moves, 3)
    except (TypeError, ValueError):
        pass

    auto_export = bool(getattr(prefill_config, "auto_export_weaknesses", False))

    return side_index, hints_index, max_moves_index, auto_export


class KifunarabeSetupContent(BoxLayout):
    """Body widget of the kifunarabe setup popup."""

    popup = ObjectProperty(None)
    side_spinner = ObjectProperty(None)
    hints_spinner = ObjectProperty(None)
    max_moves_spinner = ObjectProperty(None)

    def on_submit(self) -> None:
        """User clicked OK: validate inputs and propagate to controller."""
        from katrain.core.study.kifunarabe import (
            VALID_HINT_COUNTS,
            VALID_MAX_MOVES,
            KifunarabeConfig,
        )

        # Phase 292-B (Bug 1 fix, rev3): last-mile dismissal of any
        # orphan kifunarabe summary popup. The popup was supposed to be
        # dismissed by ``on_replay`` before this popup opened, but the
        # user reported it stays visible. Forcing the dismissal here
        # happens just before ``start_session`` lands the new session,
        # so any leftover summary window disappears alongside the
        # setup popup we are about to close.
        gui = self.popup.app_gui if self.popup else None
        _dismiss_orphan_summary_popup(gui)

        # Phase 292-B: surface the previous auto_export_weaknesses flag
        # so re-played sessions preserve the user's opt-in choice.
        auto_export = bool(getattr(self, "_prefill_auto_export_weaknesses", False))

        try:
            turn_key = self.side_spinner.input_value
            turn = _REF_TO_TURN.get(turn_key, "both")
            hints_key = self.hints_spinner.input_value
            max_hints = int(hints_key)
            if max_hints not in VALID_HINT_COUNTS:
                raise ValueError(f"hint count must be one of {VALID_HINT_COUNTS}")
            moves_key = self.max_moves_spinner.input_value
            max_moves = _REF_TO_MAX_MOVES.get(moves_key, 0)
            if max_moves not in VALID_MAX_MOVES:
                raise ValueError(f"max_moves must be one of {VALID_MAX_MOVES}")
            config: KifunarabeConfig = KifunarabeConfig(
                turn=turn,
                max_hints=max_hints,
                max_moves=max_moves,
                auto_export_weaknesses=auto_export,
            )
        except (ValueError, TypeError):
            # Fall back to defaults on invalid input (do not block).
            # Note: we lose the pre-filled auto_export_weaknesses here
            # on purpose — a bad-input fallback should be conservative.
            config = KifunarabeConfig()

        # A1 (Phase 177-A2): the controller's start_session() is the single
        # owner of toggle syncing and redraw scheduling. The popup must NOT
        # touch ``analysis_controls.hints`` directly any more.
        controller = getattr(gui, "_kifunarabe_controller", None) if gui is not None else None
        if controller is not None:
            controller.start_session(config)
        if self.popup is not None:
            self.popup.dismiss()


def _open_setup_popup(gui: Any, prefill_config: Any = None) -> None:
    """Open the side/hints chooser. Used after the SGF is selected.

    Args:
        gui: KaTrainGui instance.
        prefill_config: Phase 292-B. Optional :class:`KifunarabeConfig`
            from a previous session. When provided, the side / hints /
            max_moves spinners are initialised to the previous
            values so the user only has to change what they actually
            want to change. When ``None``, defaults (both / 3 hints /
            all moves) are used.
    """
    from kivy.uix.label import Label

    from katrain.core.lang import i18n
    from katrain.gui.popups._base import LabelledSpinner
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button

    # Phase 292-B (rev3): best-effort dismissal of any orphan summary
    # popup BEFORE we touch the widget tree for the new setup popup.
    # The popup button handlers (``on_replay`` / ``on_next_sgf``)
    # already do a multi-layer close, but users still report seeing
    # the OLD summary window staying open after clicking 開始. The
    # ``on_replay`` handler schedules this same call after a 0.05s
    # delay, so by the time we get here the window should already be
    # closed — but if that path failed (e.g. Kivy animation got
    # stuck), this last-mile call makes sure we land on a clean slate.
    _dismiss_orphan_summary_popup(gui)

    # Phase 292-B: convert the previous config into spinner indices so
    # the re-opened popup lands on the user's last settings. Pure
    # function — see ``_prefill_from_config`` for the conversion rules.
    side_index, hints_index, max_moves_index, auto_export = _prefill_from_config(prefill_config)

    content = KifunarabeSetupContent(orientation="vertical", spacing=dp(8), padding=dp(10))

    # Title/body — font_name explicit so non-ASCII text doesn't tofu.
    body = Label(
        text=i18n._("kifunarabe:setup:body"),
        size_hint_y=None,
        height=dp(40),
        halign="center",
        valign="middle",
        font_name=Theme.DEFAULT_FONT,
    )
    body.bind(size=lambda _w, _s: setattr(body, "text_size", body.size))
    content.add_widget(body)

    # Side spinner - I18NSpinner reads ``value_refs`` and builds ``values``
    side_spinner = LabelledSpinner(
        input_property="side",
        value_refs=[
            "kifunarabe:setup:side_both",
            "kifunarabe:setup:side_black",
            "kifunarabe:setup:side_white",
        ],
        selected_index=side_index,
    )
    content.add_widget(side_spinner)
    content.side_spinner = side_spinner

    # Hints spinner (0..5). Ref is the digit-as-string, int()'d on submit.
    hints_spinner = LabelledSpinner(
        input_property="hints",
        value_refs=[str(n) for n in (0, 1, 2, 3, 4, 5)],
        selected_index=hints_index,
    )
    content.add_widget(hints_spinner)
    content.hints_spinner = hints_spinner

    # Moves spinner (50 / 100 / 150 / all). Ref maps to int via _REF_TO_MAX_MOVES.
    max_moves_spinner = LabelledSpinner(
        input_property="max_moves",
        value_refs=[
            "kifunarabe:setup:moves_50",
            "kifunarabe:setup:moves_100",
            "kifunarabe:setup:moves_150",
            "kifunarabe:setup:moves_all",
        ],
        selected_index=max_moves_index,
    )
    content.add_widget(max_moves_spinner)
    content.max_moves_spinner = max_moves_spinner

    # Phase 292-B: surface the previous ``auto_export_weaknesses`` value
    # so repeated replay-with-settings runs preserve the user's choice.
    # The popup doesn't expose a dedicated checkbox for this (it's a
    # config-store toggle), so we keep it on the content for the
    # submit handler to forward to ``start_session``.
    content._prefill_auto_export_weaknesses = auto_export

    submit_btn = Button(
        text=i18n._("kifunarabe:setup:start"),
        size_hint_y=None,
        height=dp(40),
        font_name=Theme.DEFAULT_FONT,
    )
    submit_btn.bind(on_release=lambda _b: content.on_submit())
    content.add_widget(submit_btn)

    popup = I18NPopup(
        title_key="kifunarabe:setup:title",
        size=[dp(360), dp(320)],
        content=content,
    ).__self__
    popup.size_hint = (None, None)
    popup.pos_hint = {"center_x": 0.5, "center_y": 0.5}
    content.popup = popup
    popup.app_gui = gui
    popup.open()


def _kifunarabe_load_dir(gui: Any) -> str:
    """Resolve the SGF browse directory used for kifunarabe.

    Resolution order:
    1. ``kifunarabe/sgf_load`` config (if set and a directory exists)
    2. ``general/sgf_load`` config (main "自分の対局" folder)
    3. Current working directory

    The directory is *not* written back: the user adjusts ``kifunarabe/sgf_load``
    in :func:`open_kifunarabe_sgf_setup_popup` if they want to persist it.
    """
    kifunarabe_path = gui.config(KIFUNARABE_SGF_LOAD_KEY, None)
    if kifunarabe_path and os.path.isdir(os.path.expanduser(str(kifunarabe_path))):
        return str(kifunarabe_path)
    fallback = gui.config("general/sgf_load", ".") or "."
    return str(fallback)


def _load_sgf_into_new_game(gui: Any, filename: str) -> bool:
    """Parse ``filename`` and start a new game *without* recording the source path.

    Bypassing ``SGFManager.load_sgf_file`` lets us pass
    ``sgf_filename=None`` to ``do_new_game`` so subsequent "Save Game"
    cannot overwrite the original SGF file.

    Args:
        gui: KaTrainGui instance.
        filename: Path to the SGF file.

    Returns:
        True if the load succeeded, False otherwise.
    """
    from katrain.core.constants.output import OUTPUT_ERROR
    from katrain.core.game import KaTrainSGF
    from katrain.core.sgf_parser import ParseError

    # Phase 292-B (Bug 1 fix): before loading the new SGF, dismiss any
    # kifunarabe summary popup that may still be visible from the previous
    # session. The previous ``on_next_sgf`` already calls
    # ``popup.dismiss()``, but Kivy's transition leaves the widget on
    # screen for a few frames — enough for the user to see the OLD
    # results alongside the new setup popup. We go through the
    # controller's tracker so both the widget reference and the
    # tracking attribute are cleared synchronously, then ``dismiss()``
    # is fired twice with a small gap so the closing transition finishes
    # before the new game state takes over.
    _dismiss_orphan_summary_popup(gui)

    try:
        move_tree = KaTrainSGF.parse_file(os.path.abspath(filename))
    except (ParseError, OSError) as e:
        with contextlib.suppress(Exception):
            gui.log(f"kifunarabe: failed to load SGF {filename}: {e}", int(OUTPUT_ERROR))
        return False

    # ``sgf_filename=None`` is the key bit: the original file is decoupled
    # from the session, so any future "Save Game" treats this as a brand
    # new game and never overwrites the source.
    gui("new-game", move_tree, analyze_fast=False, sgf_filename=None)

    # Kick an analysis pass on the current node so the candidate-marker
    # layer has data to render as soon as the setup popup is dismissed.
    # ``Game.play(analyze=True)`` covers all subsequent moves, but the
    # initial root node would otherwise stay un-analysed.
    _kick_root_analysis(gui)
    # Phase 292-B (Bug 1 fix, second line of defence): trigger another
    # dismissal after the new-game dispatch so the OLD widget is
    # closed even if Kivy's first ``dismiss()`` was overridden by an
    # animation or a queued redraw that reattached the popup.
    _dismiss_orphan_summary_popup(gui)
    return True


def _dismiss_orphan_summary_popup(gui: Any) -> None:
    """Phase 292-B (Bug 1 fix, rev4): belt-and-braces dismissal of any
    orphan kifunarabe summary popup that may still be visible.

    Two-pronged approach — the controller's tracker is the easy path
    (and is run first so the sticky reference is cleared), then we
    walk the application's actual widget tree to close any popup that
    slipped past the tracker (e.g. when the user double-clicks through
    the summary → setup → start sequence fast enough that the original
    ``self.popup.dismiss()`` was overridden by an animation):

    1. ``controller._dismiss_summary_popup_if_open()`` — clears the
       controller's ``_summary_popup`` sticky reference and dismisses
       whatever widget that reference points at.
    2. ``_brutal_close_visible_kifunarabe_popups()`` — walks the live
       widget tree looking for ANY ``I18NPopup`` whose ``.children``
       include a ``KifunarabeSummaryContent``. Any match is dismissed
       via three independent paths: ``dismiss()``,
       ``_window_dismiss()``, and ``parent.remove_widget(...)``.

    Used at the start of SGF load (so the OLD summary is gone before
    the new game's setup popup opens), inside ``_open_setup_popup``
    (last-mile defence before the setup popup opens), and inside
    ``setup_popup.on_submit`` (last-mile defence before ``start_session``).

    Errors at every layer are swallowed because a failed dismissal is
    always preferable to a hard crash mid-flow.
    """
    controller = getattr(gui, "_kifunarabe_controller", None)
    with contextlib.suppress(Exception):
        dismiss_fn = getattr(controller, "_dismiss_summary_popup_if_open", None)
        if callable(dismiss_fn):
            dismiss_fn()
    # Re-arm the belt-and-braces: even if the controller's tracking was
    # just cleared, fall back to walking the widget tree for any
    # visible kifunarabe summary that survived the tracker-based
    # dismissal.
    _brutal_close_visible_kifunarabe_popups(gui, controller)


def _brutal_close_visible_kifunarabe_popups(gui: Any, controller: Any) -> None:
    """Phase 292-B (Bug 1 fix, rev4): walk ``gui``'s widget tree and
    dismiss ANY popup whose content is a
    :class:`KifunarabeSummaryContent`. This catches the case where
    ``_summary_popup`` tracking has been cleared but the widget
    is still attached somewhere in the tree (which happens when the
    popup's ``dismiss()`` is short-circuited by a state cache glitch).

    The walk uses Kivy's standard ``Window.children`` iteration; we
    never raise — every operation is wrapped in ``contextlib.suppress``.
    """
    import contextlib as _contextlib

    # Pick up the right import path (works whether kivy is loaded with
    # or without kivymd-specific patches).
    try:
        from kivy.core.window import Window as _KivyWindow

        Window = _KivyWindow
    except ImportError:
        Window = None  # noqa: F841

    popup_class = None
    summary_class = None
    try:
        from katrain.gui.popups._base import I18NPopup as _I18NPopup

        popup_class = _I18NPopup
    except ImportError:
        pass
    try:
        from katrain.gui.features.kifunarabe_summary import KifunarabeSummaryContent

        summary_class = KifunarabeSummaryContent
    except ImportError:
        pass

    candidates: list[Any] = []

    # 1. Walk the Kivy Window's children — that's where Kivy puts
    #    every open Popup.
    with _contextlib.suppress(Exception):
        if Window is not None:
            for child in list(getattr(Window, "children", []) or []):
                if popup_class is not None and isinstance(child, popup_class):
                    candidates.append(child)
    # 2. Walk the gui widget tree itself — defensive.
    with _contextlib.suppress(Exception):
        if gui is not None:
            for descendant in _walk_all_widgets(gui):
                if popup_class is not None and isinstance(descendant, popup_class):
                    candidates.append(descendant)

    for popup in candidates:
        # Make sure this popup actually IS a kifunarabe summary
        # before we touch it. ``Popup.content`` is the loaded widget.
        if summary_class is not None:
            content = getattr(popup, "content", None)
            if content is None or not isinstance(content, summary_class):
                continue
        # Multi-layer close (see the brutal_close_summary docstring
        # in kifunarabe_summary.py for the rationale).
        with _contextlib.suppress(Exception):
            popup.dismiss()
        with _contextlib.suppress(Exception):
            popup._window_dismiss()
        with _contextlib.suppress(Exception):
            parent = getattr(popup, "parent", None)
            if parent is not None:
                parent.remove_widget(popup)

    # And finally — the controller's tracker, no matter what state
    # it's in. Belt and braces. Even if the above walks missed
    # something (kivy destroyed the widget tree before we got to
    # it), the tracker should know about a popup that *was* visible
    # moments ago. Clear it so future dismissal attempts are no-ops.
    with _contextlib.suppress(Exception):
        if controller is not None:
            controller._summary_popup = None


def _walk_all_widgets(root: Any) -> list[Any]:
    """Yield every descendant of ``root`` via a depth-first walk.

    Helper used by
    :func:`_brutal_close_visible_kifunarabe_popups` to enumerate the
    application's widget tree without depending on a specific Kivy
    layout API. Returns a flat list (the collected widgets) rather
    than yielding so the caller does not need to manage generator
    state across the ``contextlib.suppress(Exception)`` wrappers.
    """
    seen: list[Any] = []
    stack: list[Any] = [root]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        seen.append(node)
        children = getattr(node, "children", None)
        if children:
            for child in list(children):
                stack.append(child)
    return seen


def _kick_root_analysis(gui: Any) -> None:
    """Submit the current node for analysis on the main thread.

    Phase 178-A: the previous 0.2s single-shot delay sometimes left the
    root node without analysis by the time the setup popup was
    dismissed, so the choice-marker layer had no candidates to render.

    We now:
    - Initial delay so the worker thread that handles ``new-game`` has
      populated ``gui.game`` (unchanged).
    - Bail out early if ``node.analysis_exists`` is already True.
    - On a failed ``node.analyze()`` call, log at level=1 so the user
      can see the cause without a stack trace.
    - Schedule a verification tick that retries up to ``MAX_ATTEMPTS``
      total kicks, each separated by ``RETRY_DELAY`` seconds.

    The kivy.clock import is kept inside the function (Phase 173
    pattern) so that ``import katrain.gui.popups.kifunarabe_setup_popup``
    in test environments never touches the kivy ``__init__`` side
    effects (which mkdir ``~/.kivy`` and would race in CI).
    """
    import contextlib

    MAX_ATTEMPTS = 5
    RETRY_DELAY = 0.5  # seconds

    def _resolve_engine(game: Any, node: Any) -> Any:
        engines = getattr(game, "engines", {}) or {}
        engine = engines.get(node.next_player)
        if engine is not None:
            return engine
        # Fall back: any registered engine.
        for v in engines.values():
            return v
        return None

    def _do_kick(attempt: int = 1) -> None:
        game = getattr(gui, "game", None)
        if game is None:
            return
        node = getattr(game, "current_node", None)
        if node is None:
            return
        if getattr(node, "analysis_exists", False):
            return  # already analysed - nothing to do

        engine = _resolve_engine(game, node)
        if engine is None:
            return

        try:
            node.analyze(engine)
        except Exception as e:
            with contextlib.suppress(Exception):
                gui.log(f"kifunarabe: root analysis attempt {attempt} failed: {e}", 1)
            return

        # Verify the analysis landed; if not, schedule another kick.
        from kivy.clock import Clock

        def _verify(_dt: float) -> None:
            if getattr(node, "analysis_exists", False):
                return
            if attempt < MAX_ATTEMPTS:
                Clock.schedule_once(lambda _d: _do_kick(attempt + 1), RETRY_DELAY)

        Clock.schedule_once(_verify, RETRY_DELAY)

    from kivy.clock import Clock

    Clock.schedule_once(lambda _dt: _do_kick(), 0.2)


def open_kifunarabe_sgf_selector(gui: Any) -> None:
    """Open the SGF file selector (separate folder from main SGF loader),
    then chain into the setup popup.

    Flow:
        SGF picker -> load file (without recording its path) -> setup popup.

    Args:
        gui: KaTrainGui instance.
    """
    from katrain.gui.popups.sgf_popups import LoadSGFPopup

    # B2 (Phase 177): use a *dedicated* popup slot so we never overwrite
    # the main "SGF 読込" dialog slot (``sgf_manager.fileselect_popup``).
    # Without this, opening the regular file picker later could close our
    # file picker's ``on_submit`` callback mid-typing, and conversely our
    # popup could dismiss the user's main SGF picker.
    existing = getattr(gui, "_kifunarabe_fileselect_popup", None)

    popup_contents = LoadSGFPopup(gui)
    start_dir = os.path.abspath(os.path.expanduser(_kifunarabe_load_dir(gui)))
    if os.path.isdir(start_dir):
        popup_contents.filesel.path = start_dir
    popup_contents.filesel.file_must_exist = True

    fileselect_popup = I18NPopup(
        title_key="load sgf title",
        size=[dp(1200), dp(800)],
        content=popup_contents,
    ).__self__
    gui._kifunarabe_fileselect_popup = fileselect_popup
    # If there was a previously created popup still alive, dismiss it.
    if existing is not None and existing is not fileselect_popup:
        with contextlib.suppress(Exception):
            existing.dismiss()

    def readfile(*_args: Any) -> None:
        filename = popup_contents.filesel.filename
        my_popup = getattr(gui, "_kifunarabe_fileselect_popup", None)
        if my_popup:
            my_popup.dismiss()

        path, _file = os.path.split(filename)
        # Persist kifunarabe-specific folder separately from the main one.
        if path and path != gui.config(KIFUNARABE_SGF_LOAD_KEY, None):
            with contextlib.suppress(Exception):
                gui.log(f"Updating kifunarabe/sgf_load default to {path}", 0)
                kif_section = dict(gui.config("kifunarabe", {}) or {})
                kif_section["sgf_load"] = path
                gui.set_config_section("kifunarabe", kif_section)
                gui.save_config("kifunarabe")

        # Read without overwriting: original file path is intentionally NOT
        # handed to ``do_new_game``.
        if not _load_sgf_into_new_game(gui, filename):
            return

        # Slight delay so the file picker closes before the setup popup opens.
        from kivy.clock import Clock

        Clock.schedule_once(lambda _dt: _open_setup_popup(gui), 0.1)

    popup_contents.filesel.on_success = readfile
    popup_contents.filesel.on_submit = readfile
    fileselect_popup.open()
    fileselect_popup.content.filesel.ids.list_view._trigger_update()


def open_kifunarabe_setup_popup(gui: Any, prefill_config: Any = None) -> None:
    """Public entry: opens the setup popup directly (used by callers that
    already have a game loaded). The standard "棋譜並べ" button uses
    :func:`open_kifunarabe_sgf_selector` instead.

    Args:
        gui: KaTrainGui instance.
        prefill_config: Phase 292-B. Optional KifunarabeConfig from a
            previous session to pre-fill the spinners. See
            :func:`_open_setup_popup`.
    """
    _open_setup_popup(gui, prefill_config=prefill_config)
