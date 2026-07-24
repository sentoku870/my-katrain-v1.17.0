# katrain/gui/features/commands/popup_commands.py
from __future__ import annotations

"""Popup-related command handlers extracted from KaTrainGui (Phase 41-B, 140, 173).

These functions handle opening various popup dialogs.
The ctx parameter is expected to be a KaTrainGui instance (satisfies FeatureContext).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui


def do_select_box(ctx: KaTrainGui) -> None:
    """Begin region-of-interest selection on the board.

    Args:
        ctx: KaTrainGui instance
    """
    from katrain.core.constants.output import STATUS_INFO
    from katrain.core.lang import i18n

    ctx.controls.set_status(i18n._("analysis:region:start"), STATUS_INFO)
    ctx.board_gui.selecting_region_of_interest = True


def do_engine_recovery_popup(ctx: KaTrainGui, error_message: str, code: Any) -> None:
    """Show the engine recovery popup after a KataGo crash.

    Args:
        ctx: KaTrainGui instance
        error_message: Human-readable error description
        code: Engine exit code (or similar)
    """
    ctx._popup_manager.open_engine_recovery_popup(error_message, code)


def do_config_popup(ctx: KaTrainGui) -> None:
    """Open the general settings popup.

    Args:
        ctx: KaTrainGui instance
    """
    from kivy.metrics import dp

    from katrain.gui.popups import ConfigPopup, I18NPopup
    from katrain.gui.popups._base import clamp_popup_size

    ctx.controls.timer.paused = True
    if not ctx.config_popup:
        content = ConfigPopup(ctx)
        # Phase 287-E: clamp to 90% of the current window so the
        # 1200x950 dp default does not overflow 1366x768 displays.
        new_popup = I18NPopup(
            title_key="general settings title",
            size=clamp_popup_size([dp(1200), dp(950)]),
            content=content,
        ).__self__
        # P2-A (H6): release the two language bindings on dismiss so
        # repeated open/close cycles don't accumulate callbacks.
        new_popup.bind(on_dismiss=lambda _instance: content.cleanup())
        # Phase 277.1: clear ``ctx.config_popup`` when dismissed so
        # the next ``do_config_popup`` call creates a fresh popup
        # rather than reopening the existing one. Previously the
        # title got ``+= ": {path}"`` appended every time the user
        # opened the settings, eventually rendering the popup header
        # as ": path: path: path: path".
        new_popup.bind(on_dismiss=lambda _instance: setattr(ctx, "config_popup", None))
        ctx.config_popup = new_popup

    assert ctx.config_popup is not None
    ctx.config_popup.content.popup = ctx.config_popup
    if ": " + ctx.config_file not in ctx.config_popup.title:
        ctx.config_popup.title += ": " + ctx.config_file
    ctx.config_popup.open()


# ---------------------------------------------------------------------------
# Phase 173: Popup opener commands.
#
# These were extracted from ``__main__.KaTrainGui`` during the
# God-Module cleanup. They each delegate to the appropriate manager.
# Keeping the wrappers here (rather than calling the manager directly
# from the GUI / Kv bindings) makes the command surface uniform:
# every popup / game / export action is reachable through ``commands``.
# ---------------------------------------------------------------------------


def do_new_game_popup(ctx: KaTrainGui) -> None:
    """Show the "new game" popup (game-setup dialog)."""
    ctx._popup_manager.open_new_game_popup()


def do_timer_popup(ctx: KaTrainGui) -> None:
    """Show the timer / clock settings popup."""
    ctx._popup_manager.open_timer_popup()


def do_teacher_popup(ctx: KaTrainGui) -> None:
    """Show the teacher (KataGo teaching settings) popup."""
    ctx._popup_manager.open_teacher_popup()


def do_ai_popup(ctx: KaTrainGui) -> None:
    """Show the AI opponent settings popup."""
    ctx._popup_manager.open_ai_popup()


def do_mykatrain_settings_popup(ctx: KaTrainGui) -> None:
    """Open the my-katrain / Kifu / report settings popup.

    The actual popup builder lives in
    ``katrain.gui.features.settings_popup``.
    """
    from katrain.gui.features.settings_popup import do_mykatrain_settings_popup as _build

    _build(ctx)


def do_batch_analyze_popup(ctx: KaTrainGui) -> None:
    """Show the batch analysis popup (multi-SGF processing)."""
    ctx._batch_analysis_controller.open_batch_analyze_popup()


def do_analyze_sgf_popup(ctx: KaTrainGui) -> None:
    """Show the "analyse an SGF file" popup (delegated to SGFManager)."""
    ctx._sgf_manager.do_analyze_sgf_popup(ctx)


def do_open_recent_sgf(ctx: KaTrainGui) -> None:
    """Show the recent-SGF dropdown (delegated to SGFManager)."""
    ctx._sgf_manager.open_recent_sgf()


def do_save_game_as_popup(ctx: KaTrainGui) -> None:
    """Show the "save game as..." popup (delegated to SGFManager)."""
    ctx._sgf_manager.do_save_game_as_popup(ctx)


def do_kifunarabe_popup(ctx: KaTrainGui) -> None:
    """Open the SGF selector for kifunarabe (棋譜並べ).

    The flow is: SGF picker -> load SGF -> side/hint chooser -> session start.
    Defined per user request: "棋譜並べボタンを押した段階で棋譜の選択".
    """
    from katrain.gui.popups.kifunarabe_setup_popup import open_kifunarabe_sgf_selector

    open_kifunarabe_sgf_selector(ctx)


def do_kifunarabe_abort(ctx: KaTrainGui) -> None:
    """Abort the current kifunarabe session (shows summary popup)."""
    controller = getattr(ctx, "_kifunarabe_controller", None)
    if controller is not None:
        controller.abort_session()


def do_llm_coach_popup(ctx: KaTrainGui) -> None:
    """Open the LLM Coach popup (Phase 225).

    The popup lets the user build an LLM prompt from a Karte JSON, copy it
    to the clipboard, paste the LLM response back, and run validation.
    No API integration — manual paste only. See ``docs/archive/specs-planned/phase203-llm-translator.md``
    for the underlying translation-specialisation design.
    """
    from katrain.gui.popups.llm_coach_popup import open_llm_coach_popup

    open_llm_coach_popup(ctx)


# Phase 250: 重要局面リスト popup は廃止。4 ボタン (黒前/黒次/白前/白次)
# で代替するため、``do_important_moves_popup`` と関連ファイル
# (gui/popups/important_moves_popup.py, gui/kv/important_moves_popup.kv,
# core/analysis/important_moves_popup.py) は削除済み。
