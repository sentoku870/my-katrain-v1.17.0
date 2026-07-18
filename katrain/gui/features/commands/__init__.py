# katrain/gui/features/commands/__init__.py
from __future__ import annotations

"""Command handlers extracted from KaTrainGui (Phase 41-B).

Phase 172: Added ``DISPATCH_TABLE`` which maps message names (as received
from KV bindings, keyboard shortcuts, and the message-loop consumer
thread) to the concrete ``do_*`` functions in the submodules.

The dispatcher lookup replaces the legacy ``getattr(self, f"_do_{...}")``
chain on ``KaTrainGui`` so the 34 thin ``_do_*`` wrappers on the GUI can
be removed without breaking any caller.
"""

from collections.abc import Callable
from typing import Any

from katrain.gui.features.commands import (
    analyze_commands,
    export_commands,
    game_commands,
    popup_commands,
)

# Map of message-source module → keys handled by that module. The
# ``dispatch`` function resolves a key by searching these modules at
# call time so that monkey-patching tests can swap individual
# ``do_*`` functions without rebuilding a static lookup table.
_DISPATCH_MODULES: tuple[Any, ...] = (
    analyze_commands,
    export_commands,
    game_commands,
    popup_commands,
)

# Static set of every key that ``dispatch`` knows about. Used by tests
# and the architecture test to assert there are no missing registrations.
_DISPATCH_KEYS: frozenset[str] = frozenset(
    {
        # ---- analyze_commands ----
        "analyze_extra",
        "insert_mode",
        "reset_analysis",
        "resign",
        "redo",
        "prev_important",
        "next_important",
        # Phase 250: 4-button color-split important-move navigation
        # (黒の前の重要局面 / 黒の次の重要局面 / 白の前の重要局面 / 白の次の重要局面)
        "prev_important_black",
        "next_important_black",
        "prev_important_white",
        "next_important_white",
        # ---- export_commands ----
        "save_game",
        "export_karte",
        # Phase 230-A.2: open_latest_report / open_output_folder /
        # export_summary / export_summary_ui を完全削除。
        # ---- game_commands ----
        "new_game",
        "ai_move",
        "undo",
        "rotate",
        "find_mistake",
        "switch_branch",
        "play",
        "selfplay_setup",
        "tsumego_frame",
        # ---- popup_commands ----
        "select_box",
        "new_game_popup",
        "timer_popup",
        "teacher_popup",
        "config_popup",
        "ai_popup",
        "engine_recovery_popup",
        "analyze_sgf_popup",
        "open_recent_sgf",
        "save_game_as_popup",
        "mykatrain_settings_popup",
        "batch_analyze_popup",
        # Phase 230-D: diagnostics_popup moved into mykatrain settings tab
        # ---- Phase 225: LLM Coach popup ----
        "llm_coach_popup",
        # Phase 250: 重要局面リスト popup は廃止 (4 ボタン化で代替)。
        # kifunarabe summary からも削除 (Phase 250-F)。
        # ---- kifunarabe (棋譜並べ) ----
        "kifunarabe_popup",
        "kifunarabe_abort",
    }
)


# Some keys don't map to ``do_<key>`` literally because the public
# action name in the menu/KV differs from the function name. The
# override table makes the relationship explicit and keeps the
# tests' ``do_<key>`` discovery simple.
_KEY_TO_FUNC_NAME: dict[str, str] = {
    "selfplay_setup": "do_start_selfplay",
}


def _resolve(key: str) -> Callable[..., None] | None:
    """Look up a command function by key, returning None if absent.

    The lookup is performed against the live modules at call time
    (rather than a captured-at-import-time dict) so the test suite
    can monkey-patch individual ``do_*`` functions.
    """
    func_name = _KEY_TO_FUNC_NAME.get(key, f"do_{key}")
    for module in _DISPATCH_MODULES:
        fn: Callable[..., None] | None = getattr(module, func_name, None)
        if fn is not None and callable(fn):
            return fn
    return None


# Compatibility: tests and external callers still see ``DISPATCH_TABLE``
# as a name. We expose a small adapter so test code that iterates over
# ``DISPATCH_TABLE.items()`` keeps working without touching every test.
def _build_view() -> dict[str, Callable[..., None]]:
    view: dict[str, Callable[..., None]] = {}
    for key in _DISPATCH_KEYS:
        fn = _resolve(key)
        if fn is not None:
            view[key] = fn
    return view


DISPATCH_TABLE: dict[str, Callable[..., None]] = _build_view()


def dispatch(ctx: Any, message: str, *args: Any, **kwargs: Any) -> None:
    """Resolve ``message`` via :data:`DISPATCH_TABLE` and invoke the command.

    Args:
        ctx: KaTrainGui instance (passed as first positional arg).
        message: Action name with ``-`` or ``_`` separators (normalised internally).
        *args: Forwarded to the resolved command.
        **kwargs: Forwarded to the resolved command.

    Raises:
        KeyError: If ``message`` is not registered.

    Note:
        Lookups happen against the live modules (``analyze_commands``,
        ``game_commands``, etc.) at call time so tests can monkey-patch
        a single ``do_*`` function without having to rebuild
        ``DISPATCH_TABLE``.
    """
    key = message.replace("-", "_")
    fn = _resolve(key)
    if fn is None:
        raise KeyError(key)
    fn(ctx, *args, **kwargs)
