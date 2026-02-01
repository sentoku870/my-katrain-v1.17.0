"""
Centralized error handling for KaTrain GUI.

Provides consistent logging, user notification, and thread-safe status updates.
The handler itself is designed to never throw exceptions.
"""

import traceback
from typing import Any, Callable, Optional, TYPE_CHECKING, TypeVar

from kivy.clock import Clock

from katrain.core.constants import OUTPUT_ERROR, OUTPUT_DEBUG, STATUS_ERROR
from katrain.core.errors import KaTrainError

if TYPE_CHECKING:
    from katrain.__main__ import KaTrainGui

T = TypeVar("T")

# Max traceback lines to log
_MAX_TRACEBACK_LINES = 50


class ErrorHandler:
    """Centralized error handling for KaTrain GUI.

    Ensures exceptions are logged, optionally shown to users,
    and never crash the Kivy event loop or background threads.

    IMPORTANT: The handle() method is designed to NEVER throw exceptions.
    """

    def __init__(self, katrain: "KaTrainGui"):
        self._katrain = katrain

    def handle(
        self,
        error: Exception,
        *,
        notify_user: bool = True,
        log_level: float = OUTPUT_ERROR,
        fallback_message: str = "An error occurred",
    ) -> None:
        """Handle an exception with logging and optional user notification.

        This method is guaranteed to never throw exceptions itself.

        Args:
            error: The exception to handle.
            notify_user: If True, show message in status bar (thread-safe).
            log_level: Log level for the error message.
            fallback_message: Message to show user if error is not KaTrainError.
        """
        try:
            self._handle_impl(error, notify_user, log_level, fallback_message)
        except Exception as fatal_err:
            # Last resort: handle() itself failed
            self._fallback_log(f"ErrorHandler.handle() failed: {fatal_err}")

    def _handle_impl(
        self,
        error: Exception,
        notify_user: bool,
        log_level: float,
        fallback_message: str,
    ) -> None:
        """Internal implementation of handle()."""
        # 1. Determine messages
        if isinstance(error, KaTrainError):
            log_msg = str(error)
            user_msg = error.user_message
            context = error.context
        else:
            log_msg = f"{type(error).__name__}: {error}"
            user_msg = fallback_message
            context = {}

        # 2. Log error message
        self._katrain.log(log_msg, log_level)

        # 3. Log context if present
        if context:
            self._katrain.log(f"Context: {context}", OUTPUT_DEBUG)

        # 4. Log traceback at DEBUG level (truncate by lines)
        if error.__traceback__:
            try:
                tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
                # Flatten and split by newlines, then truncate
                all_lines = "".join(tb_lines).splitlines(keepends=True)
                if len(all_lines) > _MAX_TRACEBACK_LINES:
                    all_lines = all_lines[:_MAX_TRACEBACK_LINES]
                    all_lines.append(f"... (truncated, showing first {_MAX_TRACEBACK_LINES} lines)\n")
                tb_str = "".join(all_lines)
                self._katrain.log(f"Traceback:\n{tb_str}", OUTPUT_DEBUG)
            except Exception:
                pass  # Ignore traceback formatting errors

        # 5. Notify user (must be on main thread for Kivy)
        if notify_user:
            # Capture user_msg in closure
            msg_to_show = user_msg

            def _notify(dt: float) -> None:
                # Guard: controls may not exist during early startup
                if not hasattr(self._katrain, "controls") or self._katrain.controls is None:
                    self._katrain.log(
                        "ErrorHandler: controls not ready, skipping notification",
                        OUTPUT_DEBUG,
                    )
                    return
                try:
                    self._katrain.controls.set_status(msg_to_show, STATUS_ERROR)
                except Exception as notify_err:
                    # Never let notification crash the UI
                    self._katrain.log(
                        f"ErrorHandler: notification failed: {notify_err}",
                        OUTPUT_DEBUG,
                    )

            Clock.schedule_once(_notify, 0)

    def _fallback_log(self, message: str) -> None:
        """Last-resort logging when normal logging might fail."""
        try:
            self._katrain.log(message, OUTPUT_ERROR)
        except Exception:
            # Absolute last resort: print to console
            print(f"[KaTrain ErrorHandler FATAL] {message}")

    def safe_call(
        self,
        func: Callable[..., T],
        *args: Any,
        notify_user: bool = True,
        fallback_message: str = "Operation failed",
        default: Optional[T] = None,
        **kwargs: Any,
    ) -> Optional[T]:
        """Execute func with exception handling.

        Args:
            func: Function to call.
            *args: Positional arguments for func.
            notify_user: If True, notify user on error.
            fallback_message: Message to show on error.
            default: Value to return on failure (default: None).
            **kwargs: Keyword arguments for func.

        Returns:
            Result of func on success, default on failure.
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.handle(e, notify_user=notify_user, fallback_message=fallback_message)
            return default
