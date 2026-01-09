"""
KaTrain exception hierarchy.

Provides a base exception class with user-facing messages and debug context,
plus specialized subclasses for different error domains.
"""

from typing import Any, Dict, Optional


class KaTrainError(Exception):
    """Base exception for KaTrain application errors.

    Attributes:
        user_message: Safe, user-facing error message.
        context: Dictionary of debug information.
    """

    def __init__(
        self,
        message: str,
        *,
        user_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.user_message = user_message or message
        self.context = context or {}


class EngineError(KaTrainError):
    """KataGo engine errors (startup failure, communication errors, etc.)."""

    pass


class ConfigError(KaTrainError):
    """Configuration load/save/validation errors."""

    pass


class UIStateError(KaTrainError):
    """UI state save/restore errors."""

    pass


class SGFError(KaTrainError):
    """SGF load/parse errors."""

    pass
