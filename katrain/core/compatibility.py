"""Compatibility module for Python version differences (Phase 160)."""
from __future__ import annotations

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    import enum

    class StrEnum(str, enum.Enum):
        """Enum where members are also (and must be be) strings."""

        def __str__(self) -> str:
            return self.value


__all__ = ["StrEnum"]
