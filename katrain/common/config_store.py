# katrain/common/config_store.py
"""JSON-based configuration store (Kivy-independent).

This module provides a JsonStore-compatible API without Kivy dependency.
It implements Mapping protocol to allow dict(store) conversion.

Usage:
    from katrain.common.config_store import JsonFileConfigStore

    store = JsonFileConfigStore("config.json", indent=4)
    store.put("general", version="1.0", language="en")
    value = store.get("general")["version"]
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from collections.abc import Iterator, Mapping
from datetime import datetime
from threading import Lock
from typing import Any


def _get_logger() -> logging.Logger:
    """Get module logger (lazy to avoid side effect at import time)."""
    return logging.getLogger(__name__)


class JsonFileConfigStore(Mapping[str, dict[str, Any]]):
    """JSON file-based configuration store compatible with kivy.storage.jsonstore.JsonStore.

    Implements Mapping protocol to support dict(store) conversion.
    Thread-safe for concurrent access.

    Args:
        filename: Path to JSON file
        indent: JSON indentation (default 4)
    """

    def __init__(self, filename: str, indent: int = 4):
        self._filename = filename
        self._indent = indent
        self._lock = Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load data from JSON file."""
        if os.path.exists(self._filename):
            try:
                with open(self._filename, encoding="utf-8") as f:
                    self._data = json.load(f)
                # Runtime guard: verify all values are dicts (invariant enforcement)
                if isinstance(self._data, dict):
                    for key, value in list(self._data.items()):
                        if not isinstance(value, dict):
                            _get_logger().warning(
                                "Config section %s is not a dict (got %s), removing", key, type(value).__name__
                            )
                            del self._data[key]
            except (OSError, json.JSONDecodeError) as e:
                _get_logger().warning("Corrupt config file %s: %s", self._filename, e, exc_info=True)
                # Preserve corrupt file for manual recovery with timestamp
                try:
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    corrupt_path = f"{self._filename}.corrupt.{timestamp}"
                    os.rename(self._filename, corrupt_path)
                except OSError:
                    pass  # Already logged above
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save data to JSON file atomically.

        Uses temp file + os.replace for atomic write.
        This prevents data loss if the process crashes during save.

        Raises:
            OSError: If file operations fail (caller handles).
            TypeError: If JSON serialization fails.
        """
        dirname = os.path.dirname(self._filename)
        # Use current directory if filename has no directory component
        save_dir = dirname if dirname else "."
        os.makedirs(save_dir, exist_ok=True)

        # Atomic write: temp file in same directory + os.replace
        fd = None
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".tmp", dir=save_dir)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fd = None  # os.fdopen took ownership
                json.dump(self._data, f, indent=self._indent, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self._filename)
            temp_path = None  # Success, don't delete
        finally:
            # Clean up on any failure
            if fd is not None:
                os.close(fd)
            if temp_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(temp_path)

    def get(self, key: str) -> dict[str, Any] | None:  # type: ignore[override]
        """Get a section by key.

        Args:
            key: Section name

        Returns:
            Section data as dict (shallow copy), or None if not found
        """
        with self._lock:
            value = self._data.get(key)
            return dict(value) if value is not None else None

    def put(self, key: str, **kwargs: Any) -> None:
        """Store a section.

        Args:
            key: Section name
            **kwargs: Key-value pairs to store
        """
        with self._lock:
            self._data[key] = kwargs
            self._save()

    def delete(self, key: str) -> bool:
        """Delete a section.

        Args:
            key: Section name

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save()
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if a section exists.

        Args:
            key: Section name

        Returns:
            True if exists
        """
        with self._lock:
            return key in self._data

    def keys(self) -> Iterator[str]:  # type: ignore[override]
        """Return iterator over section names."""
        with self._lock:
            return iter(list(self._data.keys()))

    def __contains__(self, key: object) -> bool:
        """Check if key exists."""
        if not isinstance(key, str):
            return False
        with self._lock:
            return key in self._data

    def __getitem__(self, key: str) -> dict[str, Any]:
        """Get section by key (Mapping protocol)."""
        with self._lock:
            return dict(self._data[key])

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys (Mapping protocol)."""
        with self._lock:
            return iter(list(self._data.keys()))

    def __len__(self) -> int:
        """Return number of sections (Mapping protocol)."""
        with self._lock:
            return len(self._data)

    def __repr__(self) -> str:
        return f"JsonFileConfigStore({self._filename!r})"
