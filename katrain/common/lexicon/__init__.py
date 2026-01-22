"""
Go Lexicon Store - Kivy-independent lexicon management.

This package provides a thread-safe store for loading and searching
Go terminology entries from YAML files.

Public API:
    LexiconStore: Main store class for loading and searching entries.
    LexiconEntry: Immutable dataclass representing a single entry.
    DiagramInfo: Immutable dataclass for diagram information.
    AIPerspective: Immutable dataclass for AI perspective.
    ValidationResult: Result of validation with issues and statistics.
    ValidationIssue: A single validation issue (error or warning).
    LexiconError: Base exception for lexicon operations.
    LexiconParseError: Raised when YAML cannot be parsed.
    LexiconNotLoadedError: Raised when accessing store before loading.
    get_default_lexicon_path: Get the default lexicon YAML path.

Example:
    from katrain.common.lexicon import LexiconStore, get_default_lexicon_path

    store = LexiconStore(get_default_lexicon_path())
    result = store.load()

    if result.has_errors:
        print(result.format_report())
    else:
        entry = store.get("atari")
        print(f"Found: {entry.ja_term}")
"""

import os
from pathlib import Path

from .models import AIPerspective, DiagramInfo, LexiconEntry
from .store import LexiconStore
from .validation import (
    LexiconError,
    LexiconNotLoadedError,
    LexiconParseError,
    ValidationIssue,
    ValidationResult,
)

__all__ = [
    # Main classes
    "LexiconStore",
    "LexiconEntry",
    "DiagramInfo",
    "AIPerspective",
    # Validation
    "ValidationResult",
    "ValidationIssue",
    # Exceptions
    "LexiconError",
    "LexiconParseError",
    "LexiconNotLoadedError",
    # Utilities
    "get_default_lexicon_path",
]


def get_default_lexicon_path() -> Path:
    """Get default lexicon YAML path for dev/test environments.

    Resolution order:
    1. LEXICON_PATH environment variable (if set and non-empty)
    2. Repository-relative path: <repo_root>/docs/resources/go_lexicon_master_last.yaml

    Returns:
        Resolved absolute Path to the lexicon YAML file.

    Raises:
        FileNotFoundError: If the resolved path does not exist.

    Note:
        This is a dev/test convenience function. For packaged distributions,
        use importlib.resources or pass explicit paths to LexiconStore.
    """
    # 1. Check environment variable override
    env_path = os.environ.get("LEXICON_PATH", "").strip()
    if env_path:
        path = Path(env_path).resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"LEXICON_PATH points to non-existent file: {path}"
            )
        return path

    # 2. Repository-relative path (dev/test default)
    # katrain/common/lexicon/__init__.py -> repo_root/docs/resources/...
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parent.parent.parent
    path = repo_root / "docs" / "resources" / "go_lexicon_master_last.yaml"

    if not path.exists():
        raise FileNotFoundError(
            f"Default lexicon file not found: {path}\n"
            f"Set LEXICON_PATH environment variable to specify an alternate location."
        )

    return path
