"""Phase 68: Command Executor for KataGo engine operations.

This module provides the CommandExecutor class that manages the lifecycle
of analysis commands, including submission, result delivery, and cancellation.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from katrain.core.engine_cmd.commands import AnalysisCommand

if TYPE_CHECKING:
    from katrain.core.engine import KataGoEngine


class CommandExecutor:
    """Manages the lifecycle of analysis commands.

    Invariants:
        1. _pending_commands: Contains only ACTIVE commands without query_id.
           - Added by submit()
           - Removed when query_id is received
           - Removed by cancel/clear_all

        2. commands: Contains only ACTIVE commands with query_id assigned.
           - Added when query_id is received from callback
           - Removed on completion (final non-partial result)
           - Removed on error
           - Removed by cancel/clear_all
           - NEVER grows unbounded

        3. history: All submitted commands (deque with maxlen).
           - Added by submit()
           - Automatically evicts oldest entries

        4. PONDER_KEY: Set only in submit() method.
           - prepare() does not set it
           - This is the single source of truth

    Delivery Guarantee: Option A (At Most One Late Delivery)
        - After cancel, on_result/on_error usually won't be called
        - In rare timing, at most one late delivery may occur
        - Callbacks should guard with is_cancelled() if needed

    Thread Safety:
        - All state mutations protected by _lock
        - Callbacks called outside lock to prevent deadlock
        - Double-check pattern for cancel detection in callbacks
    """

    MAX_HISTORY_SIZE = 100

    def __init__(self, engine: KataGoEngine):
        """Initialize the executor.

        Args:
            engine: The KataGoEngine instance to send queries to.
        """
        self.engine = engine
        self.commands: dict[str, AnalysisCommand] = {}
        self._pending_commands: set[AnalysisCommand] = set()
        self._lock = threading.Lock()
        self._history: deque[AnalysisCommand] = deque(maxlen=self.MAX_HISTORY_SIZE)

    @property
    def history(self) -> list[AnalysisCommand]:
        """Return a snapshot of the command history.

        Returns:
            A list copy of the history deque.
        """
        with self._lock:
            return list(self._history)

    def submit(self, command: AnalysisCommand) -> AnalysisCommand:
        """Submit a command for execution.

        The command goes through the following lifecycle:
        1. Added to _pending_commands (no query_id yet)
        2. prepare() is called to build the query
        3. PONDER_KEY is set by executor (not by prepare)
        4. If cancelled during prepare, send_query is skipped
        5. send_query is called with callback wrappers
        6. When callback receives query_id, command moves to self.commands

        Args:
            command: The AnalysisCommand to submit.

        Returns:
            The same command (for chaining or as a cancel handle).

        Note:
            If the command is cancelled between prepare() and send_query(),
            the query will not be sent.
        """
        command.status = "pending"
        command.start_time = time.time()

        with self._lock:
            self._pending_commands.add(command)
            self._history.append(command)

        # Build the query (may take time for complex nodes)
        query_dict = command.prepare()

        # PONDER_KEY is set ONLY here (single ownership)
        if hasattr(command, "ponder") and hasattr(self.engine, "PONDER_KEY"):
            query_dict[self.engine.PONDER_KEY] = command.ponder

        # Check if cancelled during prepare()
        if command.is_cancelled():
            return command

        def callback_wrapper(analysis: dict[str, Any], partial: bool) -> None:
            """Wrap the command's on_result with lifecycle management."""
            query_id = analysis.get("id")

            # Ignore results without query_id (semantic decision)
            if not query_id:
                return

            with self._lock:
                if command.is_cancelled():
                    return

                # Move from pending to commands on first result with id
                if command in self._pending_commands:
                    self._pending_commands.discard(command)
                    command.query_id = query_id
                    self.commands[query_id] = command

                # Gate: not tracked means already completed/cancelled
                if query_id not in self.commands:
                    return

            # Double-check after lock release
            if command.is_cancelled():
                return

            # Deliver result to command
            accepted = command.on_result(analysis, partial)

            if accepted:
                with self._lock:
                    # Update status based on result
                    if command.status == "pending":
                        command.status = "executing"

                    # On final result, complete and cleanup
                    if not partial and command.status == "executing":
                        command.status = "completed"
                        # Invariant: commands contains only ACTIVE
                        if command.query_id is not None:
                            self.commands.pop(command.query_id, None)

        def error_wrapper(error: dict[str, Any]) -> None:
            """Wrap the command's on_error with lifecycle management."""
            # Use error["id"] or fallback to command.query_id
            query_id = error.get("id") or command.query_id

            with self._lock:
                if command.is_cancelled():
                    return

                # Always remove from pending
                self._pending_commands.discard(command)

                # Remove from commands if tracked
                if query_id and query_id in self.commands:
                    del self.commands[query_id]

            # Double-check after lock release
            if command.is_cancelled():
                return

            # Deliver error to command
            command.on_error(error)

        # Send to engine
        self.engine.send_query(
            query_dict,
            callback_wrapper,
            error_wrapper,
            getattr(command, "next_move", None),
            command.node,
        )

        return command

    def cancel_command(
        self,
        command: AnalysisCommand,
        terminate: bool = False,
    ) -> bool:
        """Cancel a command.

        Args:
            command: The command to cancel.
            terminate: If True, also send terminate_query to engine.

        Returns:
            True if the command was successfully cancelled.
            False if the command was already completed/failed/cancelled.

        Note:
            The _cancelled Event is only set if cancellation succeeds.
            Completed commands will not have their _cancelled flag changed.
        """
        with self._lock:
            # Cannot cancel terminal states
            if command.status in ("completed", "failed", "cancelled"):
                return False

            # Check if tracked
            was_pending = command in self._pending_commands
            self._pending_commands.discard(command)

            was_active = False
            if command.query_id and command.query_id in self.commands:
                del self.commands[command.query_id]
                was_active = True

            # Not tracked means already processed
            if not was_pending and not was_active:
                return False

            # Successfully cancelling
            command.status = "cancelled"
            command.mark_cancelled()

        # Call on_cancel outside lock
        command.on_cancel()

        # Optionally terminate the engine query
        if terminate and command.query_id:
            self.engine.terminate_query(command.query_id, ignore_further_results=True)

        return True

    def ignore_results(self, query_id: str) -> bool:
        """Cancel a command by query_id (backward compatibility).

        Args:
            query_id: The query ID to cancel.

        Returns:
            True if found and cancelled, False otherwise.
        """
        with self._lock:
            command = self.commands.get(query_id)
        if command:
            return self.cancel_command(command, terminate=False)
        return False

    def terminate(self, query_id: str) -> bool:
        """Terminate a command by query_id (backward compatibility).

        Args:
            query_id: The query ID to terminate.

        Returns:
            True if found and terminated, False otherwise.
        """
        with self._lock:
            command = self.commands.get(query_id)
        if command:
            return self.cancel_command(command, terminate=True)
        return False

    def clear_all(self, cancel_pending: bool = True) -> int:
        """Clear all tracked commands.

        Args:
            cancel_pending: If True, mark non-terminal commands as cancelled.

        Returns:
            The number of commands that were cleared.

        Note:
            Completed/failed commands do NOT get their _cancelled flag set.
            This preserves the distinction between "finished" and "cancelled".
        """
        with self._lock:
            count = len(self._pending_commands) + len(self.commands)

            if cancel_pending:
                # Mark pending commands as cancelled
                for cmd in self._pending_commands:
                    if cmd.status not in ("completed", "failed", "cancelled"):
                        cmd.status = "cancelled"
                        cmd.mark_cancelled()

                # Mark active commands as cancelled
                for cmd in self.commands.values():
                    if cmd.status not in ("completed", "failed", "cancelled"):
                        cmd.status = "cancelled"
                        cmd.mark_cancelled()

            self._pending_commands.clear()
            self.commands.clear()

        return count

    def get_command(self, query_id: str) -> AnalysisCommand | None:
        """Get a command by query_id.

        Args:
            query_id: The query ID to look up.

        Returns:
            The command if found, None otherwise.
        """
        with self._lock:
            return self.commands.get(query_id)

    def get_pending_count(self) -> int:
        """Get the number of pending commands (no query_id yet)."""
        with self._lock:
            return len(self._pending_commands)

    def get_active_count(self) -> int:
        """Get the number of active commands (with query_id)."""
        with self._lock:
            return len(self.commands)

    # ============================================================
    # Pondering convenience methods (Phase 68-C)
    # ============================================================

    @property
    def is_pondering(self) -> bool:
        """Check if any pondering command is currently active.

        A command is considered pondering if it has ponder=True attribute
        and is either pending or active.

        Returns:
            True if a pondering command is active, False otherwise.
        """
        with self._lock:
            # Check pending commands
            for cmd in self._pending_commands:
                if getattr(cmd, "ponder", False):
                    return True
            # Check active commands
            return any(getattr(cmd, "ponder", False) for cmd in self.commands.values())

    def get_ponder_command(self) -> AnalysisCommand | None:
        """Get the current pondering command, if any.

        Searches both pending and active commands for one with ponder=True.

        Returns:
            The pondering command if found, None otherwise.

        Note:
            If multiple pondering commands exist (shouldn't normally happen),
            returns the first one found (pending checked before active).
        """
        with self._lock:
            # Check pending commands first
            for cmd in self._pending_commands:
                if getattr(cmd, "ponder", False):
                    return cmd
            # Check active commands
            for cmd in self.commands.values():
                if getattr(cmd, "ponder", False):
                    return cmd
            return None

    def stop_pondering(self, terminate: bool = True) -> bool:
        """Stop the current pondering command, if any.

        This is a convenience method that finds the current pondering command
        and cancels it. It also calls engine.stop_pondering() to ensure
        proper cleanup of the engine's ponder_query state.

        Args:
            terminate: If True, also send terminate_query to engine.
                      Defaults to True for pondering.

        Returns:
            True if pondering was stopped, False if no pondering was active.

        Note:
            This method calls engine.stop_pondering() to ensure the engine's
            internal ponder_query tracking is also cleared.
        """
        ponder_cmd = self.get_ponder_command()

        if ponder_cmd:
            # Cancel the command through executor
            self.cancel_command(ponder_cmd, terminate=terminate)

            # Also call engine's stop_pondering to clear ponder_query state
            # This ensures both executor and engine are in sync
            self.engine.stop_pondering()

            return True

        return False
