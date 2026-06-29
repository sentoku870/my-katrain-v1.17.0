"""Message loop manager (Phase 158+: extracted from KaTrainGui).

Phase 158+: Manages the message queue consumer thread that serializes
game-state mutations and prevents the GUI from hanging on slow operations.

This was previously ``KaTrainGui._message_loop_thread`` (~25 lines).

The thread blocks on ``queue.get()`` and dispatches each message to the
matching ``_do_<msg>`` method on the GUI. Errors are funneled to the GUI's
``error_handler``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class MessageLoopManager:
    """Consumer thread for the GUI's message queue.

    Each message is dispatched to ``gui._do_<msg>(*args, **kwargs)``.
    After dispatch (except for the explicit ``update_state`` message),
    ``gui._do_update_state()`` is invoked to keep the GUI in sync.
    """

    def __init__(
        self,
        *,
        get_message_queue: Callable[[], Any],
        get_game_id: Callable[[], Any],
        get_gui: Callable[[], Any],  # returns the KaTrainGui instance
        log: Callable[[str, int], None],
        error_handler_handle: Callable[[Exception, bool, str], None],
    ) -> None:
        self._get_message_queue = get_message_queue
        self._get_game_id = get_game_id
        self._get_gui = get_gui
        self._log = log
        self._error_handler_handle = error_handler_handle
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the consumer thread (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Main loop: block on queue, dispatch message, handle errors."""
        # Import constants here to avoid heavy import at module load
        from katrain.core.constants import OUTPUT_EXTRA_DEBUG

        while True:
            msg_name = "<unknown>"  # Safe fallback for error message
            queue = self._get_message_queue()
            game, msg, args, kwargs = queue.get()
            try:
                msg_name = msg  # Capture for error handling
                self._log(f"Message Loop Received {msg}: {args} for Game {game}", OUTPUT_EXTRA_DEBUG)
                # Skip messages for stale game IDs (prevents race conditions)
                current_game = self._get_gui().game
                if not current_game or game != current_game.game_id:
                    self._log(
                        f"Message skipped as it is outdated (current game is {current_game.game_id if current_game else None}",
                        OUTPUT_EXTRA_DEBUG,
                    )
                    continue
                msg = msg.replace("-", "_")
                fn = getattr(self._get_gui(), f"_do_{msg}")
                fn(*args, **kwargs)
                if msg != "update_state":
                    self._get_gui()._do_update_state()
            except Exception as exc:
                self._error_handler_handle(
                    exc,
                    True,
                    f"Action '{msg_name}' failed",
                )
