"""Compatibility module for Python version differences."""
import enum
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    class StrEnum(str, enum.Enum):
        """Enum where members are also (and must be) strings."""

        def __str__(self) -> str:
            return self.value
