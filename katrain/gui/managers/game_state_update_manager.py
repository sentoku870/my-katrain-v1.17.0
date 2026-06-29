"""Game state update manager (Phase 158+: extracted from KaTrainGui).

Phase 158+: Manages the per-tick ``_do_update_state`` logic that drives AI
moves, teaching undo, mistake sounds, pondering, and Leela analysis requests.
This was previously inline in ``KaTrainGui._do_update_state`` (~50 lines).

Dependencies are injected via constructor (DI pattern) to keep this module
testable without instantiating KaTrainGui.

Pattern follows other ``gui/managers/`` modules (e.g. GameStateManager):
the manager receives lambdas that resolve state at call time. This avoids
the need for complex Protocols and lets tests inject fakes easily.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kivy.clock import Clock


class GameStateUpdateManager:
    """Encapsulates the ``_do_update_state`` logic.

    The update flow runs after every message and on receiving analyses/config
    changes. It:

    1. Plays mistake sounds and triggers teaching undo in PLAY mode.
    2. Triggers AI moves when analysis is complete and it's the AI's turn.
    3. Manages pondering state (KataGo continual analysis).
    4. Manages Leela engine lifecycle based on config + UI hints.
    5. Schedules a follow-up GUI refresh.
    """

    def __init__(
        self,
        *,
        # Required state accessors
        get_game: Callable[[], Any],
        get_engine: Callable[[], Any],
        get_play_analyze_mode: Callable[[], str],
        get_pondering: Callable[[], bool],
        set_pondering: Callable[[bool], None],
        get_last_player_info: Callable[[], Any],
        get_next_player_info: Callable[[], Any],
        get_popups_open: Callable[[], Any],
        get_nav_drawer_open: Callable[[], bool],
        get_leela_manager: Callable[[], Any],
        get_config: Callable[[str], Any],  # GUI's config getter (for leela/enabled check)
        get_eval_thresholds: Callable[[], list[float]],
        get_analysis_controls: Callable[[], Any],
        # Callbacks (Kivy-side concerns)
        play_sound: Callable[[Any], None],
        ai_move: Callable[[Any], None],
        stone_sound: Callable[[Any], None],
        schedule_gui_update: Callable[[Any, bool], None],
        clock: Clock,
    ) -> None:
        self._get_game = get_game
        self._get_engine = get_engine
        self._get_play_analyze_mode = get_play_analyze_mode
        self._get_pondering = get_pondering
        self._set_pondering = set_pondering
        self._get_last_player_info = get_last_player_info
        self._get_next_player_info = get_next_player_info
        self._get_popups_open = get_popups_open
        self._get_nav_drawer_open = get_nav_drawer_open
        self._get_leela_manager = get_leela_manager
        self._get_config = get_config
        self._get_eval_thresholds = get_eval_thresholds
        self._get_analysis_controls = get_analysis_controls
        self._play_sound = play_sound
        self._ai_move = ai_move
        self._stone_sound = stone_sound
        self._schedule_gui_update = schedule_gui_update
        self._clock = clock

    def do_update_state(self, redraw_board: bool = False) -> None:
        """Run one update tick: teach undo, AI moves, pondering, Leela."""
        game = self._get_game()
        if not game or not game.current_node:
            return
        cn = game.current_node
        last_player = self._get_last_player_info()
        next_player = self._get_next_player_info()
        play_mode = self._get_play_analyze_mode()
        nav_drawer_open = self._get_nav_drawer_open()
        popups_open = self._get_popups_open()

        # PLAY-mode mistake sounds and teaching undo
        if play_mode == "play" and not nav_drawer_open and popups_open is None:
            points_lost = cn.points_lost
            thresholds = self._get_eval_thresholds()
            # Mistake sound when point loss exceeds 4th-from-last threshold
            if (
                last_player.human
                and cn.analysis_complete
                and points_lost is not None
                and len(thresholds) >= 4
                and points_lost > thresholds[-4]
            ):
                self._play_sound(cn)

            # Teaching undo (revert AI's bad move)
            teaching_undo = cn.player and last_player.being_taught and cn.parent
            if (
                teaching_undo
                and cn.analysis_complete
                and cn.parent is not None
                and hasattr(cn.parent, "analysis_complete")
                and cn.parent.analysis_complete
                and not cn.children
                and not game.end_result
            ):
                game.analyze_undo(cn)  # not via message loop

            # Trigger AI move when it's the AI's turn
            if (
                cn.analysis_complete
                and next_player.ai
                and not cn.children
                and not game.end_result
                and not (teaching_undo and cn.auto_undo is None)
            ):
                self._ai_move(cn)
                self._clock.schedule_once(self._stone_sound, 0.25)

        # Pondering control
        engine = self._get_engine()
        if engine:
            if self._get_pondering():
                game.analyze_extra("ponder")
            else:
                engine.stop_pondering()

        # Leela engine lifecycle
        leela = self._get_leela_manager()
        if not self._get_config("leela/enabled"):
            if leela.leela_engine:
                leela.shutdown_engine()
        else:
            analysis_controls = self._get_analysis_controls()
            if analysis_controls and analysis_controls.hints.active:
                leela.request_analysis(game.current_node, None)

        # GUI refresh
        self._schedule_gui_update(cn, redraw_board)

    def request_leela_analysis(self) -> None:
        """Request Leela analysis for the current node."""
        game = self._get_game()
        if not game:
            return
        self._get_leela_manager().request_analysis(game.current_node, None)

    def set_pondering(self, value: bool) -> None:
        """Convenience setter for pondering state (used by other modules)."""
        self._set_pondering(value)
