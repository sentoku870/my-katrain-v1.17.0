"""Phase 198: AppContext — dataclass aggregating all GUI managers / controllers.

The :class:`AppContext` bundles every manager / controller / factory that
:class:`katrain.KaTrainGui` instantiated one by one during ``__init__``.
It exists so that:

* ``katrain.KaTrainGui.__init__`` is easier to read and reason about
  (one place to look up "who owns this responsibility?")
* test code can construct a context with a subset of managers
* the AppContext can be passed to helpers / commands that previously
  needed the full GUI instance

Backwards-compatibility: every Manager / Controller is *additionally*
still exposed on :class:`katrain.KaTrainGui` via ``self._<name>``.
Phase 198 Stage 1 does *not* remove any legacy attribute; it just adds
the dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.gui.controllers.analysis_controller import AnalysisController
    from katrain.gui.controllers.batch_analysis_controller import BatchAnalysisController
    from katrain.gui.dialog_factory import DialogFactory
    from katrain.gui.engine_bootstrap import EngineBootstrap
    from katrain.gui.error_handler import ErrorHandler
    from katrain.gui.managers.auto_setup_controller import AutoSetupController
    from katrain.gui.managers.config_manager import ConfigManager
    from katrain.gui.managers.game_state_manager import GameStateManager
    from katrain.gui.managers.game_state_update_manager import GameStateUpdateManager
    from katrain.gui.managers.gui_refresh_manager import GUIRefreshManager
    from katrain.gui.managers.keyboard_manager import KeyboardManager
    from katrain.gui.managers.kifunarabe_controller import KifunarabeController
    from katrain.gui.managers.message_loop_manager import MessageLoopManager
    from katrain.gui.managers.scroll_handler import ScrollHandler
    from katrain.gui.managers.summary_manager import SummaryManager
    from katrain.gui.managers.ui_update_manager import UIUpdateManager
    from katrain.gui.popup_manager import PopupManager
    from katrain.gui.sgf_manager import SGFManager


@dataclass
class AppContext:
    """Aggregate container for every manager / controller / factory KaTrainGui owns.

    Phase 198: existence only — no behavioural change for now. Stage 1
    keeps ``self._<manager_name>`` access working alongside
    ``self.ctx.<manager_name>``. Subsequent stages (tracked but not in
    this Phase) will start retiring the legacy attributes.
    """

    error_handler: ErrorHandler
    sgf_manager: SGFManager
    config_manager: ConfigManager
    summary_manager: SummaryManager
    keyboard_manager: KeyboardManager
    dialog_factory: DialogFactory
    popup_manager: PopupManager
    game_state_manager: GameStateManager
    ui_update_manager: UIUpdateManager
    auto_setup_controller: AutoSetupController
    analysis_controller: AnalysisController
    batch_analysis_controller: BatchAnalysisController
    gui_refresh_manager: GUIRefreshManager
    game_state_update_manager: GameStateUpdateManager
    message_loop_manager: MessageLoopManager
    scroll_handler: ScrollHandler
    kifunarabe_controller: KifunarabeController
    engine_bootstrap: EngineBootstrap | None = None
    # Plain state mirrored from KaTrainGui — kept here so phase-2 callers can
    # reach them via ``ctx.engine`` etc. without traversing the GUI.
    engine: Any = None
    pondering: bool = False
    show_move_num: bool = False
    message_queue: Any = None
    cancel_flag: list[bool] | None = None
