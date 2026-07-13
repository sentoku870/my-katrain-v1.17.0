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


class KifunarabeSetupContent(BoxLayout):
    """Body widget of the kifunarabe setup popup."""

    popup = ObjectProperty(None)  # type: ignore[assignment]
    side_spinner = ObjectProperty(None)  # type: ignore[assignment]
    hints_spinner = ObjectProperty(None)  # type: ignore[assignment]
    max_moves_spinner = ObjectProperty(None)  # type: ignore[assignment]

    def on_submit(self) -> None:
        """User clicked OK: validate inputs and propagate to controller."""
        from katrain.core.study.kifunarabe import (
            VALID_HINT_COUNTS,
            VALID_MAX_MOVES,
            KifunarabeConfig,
        )

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
            )
        except (ValueError, TypeError):
            # Fall back to defaults on invalid input (do not block)
            config = KifunarabeConfig()

        # A1 (Phase 177-A2): the controller's start_session() is the single
        # owner of toggle syncing and redraw scheduling. The popup must NOT
        # touch ``analysis_controls.hints`` directly any more.
        gui = self.popup.app_gui if self.popup else None
        controller = getattr(gui, "_kifunarabe_controller", None) if gui is not None else None
        if controller is not None:
            controller.start_session(config)
        if self.popup is not None:
            self.popup.dismiss()


def _open_setup_popup(gui: Any) -> None:
    """Open the side/hints chooser. Used after the SGF is selected."""
    from kivy.uix.label import Label

    from katrain.core.lang import i18n
    from katrain.gui.popups._base import LabelledSpinner
    from katrain.gui.theme import Theme
    from katrain.gui.widgets.factory import Button

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
        selected_index=0,
    )
    content.add_widget(side_spinner)
    content.side_spinner = side_spinner

    # Hints spinner (0..5). Ref is the digit-as-string, int()'d on submit.
    hints_spinner = LabelledSpinner(
        input_property="hints",
        value_refs=[str(n) for n in (0, 1, 2, 3, 4, 5)],
        selected_index=3,  # default: 3 hints
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
        selected_index=3,  # default: 全部 (0)
    )
    content.add_widget(max_moves_spinner)
    content.max_moves_spinner = max_moves_spinner

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
    from katrain.core.constants import OUTPUT_ERROR
    from katrain.core.game import KaTrainSGF
    from katrain.core.sgf_parser import ParseError

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
    return True


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


def open_kifunarabe_setup_popup(gui: Any) -> None:
    """Public entry: opens the setup popup directly (used by callers that
    already have a game loaded). The standard "棋譜並べ" button uses
    :func:`open_kifunarabe_sgf_selector` instead.
    """
    _open_setup_popup(gui)
