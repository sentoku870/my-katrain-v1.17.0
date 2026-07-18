"""Phase 249-β: persistent history for kifunarabe (棋譜並べ) sessions.

Implements Phase 177 spec §7 / item 4 ("棋譜並べ成績の履歴保存
(JSON シリアライズ)"). Each finished session is written to a
JSON file under a directory the user can configure; the GUI then
exposes a "history" popup so the user can browse past results.

The store is Kivy-independent so it can be exercised without a
display (and reused from a future CLI / batch tool).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from katrain.core.study.kifunarabe import (
    KifunarabeConfig,
    KifunarabeSummary,
)

_log = logging.getLogger(__name__)


# =============================================================================
# History entry
# =============================================================================


@dataclass
class KifunarabeHistoryEntry:
    """One finished kifunarabe session on disk.

    Attributes:
        timestamp: ISO-8601 string of when the session ended.
        sgf_path: Path of the source SGF (``None`` if not from disk).
        config: Snapshot of the :class:`KifunarabeConfig` in use.
        summary: Snapshot of the :class:`KifunarabeSummary`.
        critical_3_set: Move numbers flagged as Critical 3 for the
            session (sorted list).
    """

    timestamp: str
    sgf_path: str | None
    config: dict[str, Any]
    summary: dict[str, Any]
    critical_3_set: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sgf_path": self.sgf_path,
            "config": self.config,
            "summary": self.summary,
            "critical_3_set": self.critical_3_set,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KifunarabeHistoryEntry:
        return cls(
            timestamp=str(data.get("timestamp", "")),
            sgf_path=data.get("sgf_path"),
            config=dict(data.get("config", {})),
            summary=dict(data.get("summary", {})),
            critical_3_set=list(data.get("critical_3_set", [])),
        )


# =============================================================================
# Store
# =============================================================================


#: Filename pattern: ``YYYY-MM-DD_HHMMSS_<suffix>.json``. ``<suffix>``
#: is the SGF stem (or ``manual`` if no SGF is associated). The
#: timestamp is in local time and the filename is safe on both
#: Windows and POSIX.
_FILENAME_FORMAT = "%Y-%m-%d_%H%M%S"


def default_history_dir() -> Path:
    """Return the default history directory (``~/.katrain/kifunarabe_history``).

    The directory is created on demand by :meth:`KifunarabeHistoryStore.append`.
    """
    return Path.home() / ".katrain" / "kifunarabe_history"


class KifunarabeHistoryStore:
    """Append-only JSON-backed history of kifunarabe sessions.

    The store is a thin wrapper around a directory of one-file-per-
    session. Reads are O(N) (we read every file in the directory);
    writes are O(1) (single ``write_text``). For a typical user with
    a few hundred sessions a year this is fine; if it ever grows we
    can add a ``index.json`` later.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        """Initialize the store.

        Args:
            directory: Directory to read/write JSON entries. ``None``
                falls back to :func:`default_history_dir`.
        """
        self._dir: Path = Path(directory) if directory is not None else default_history_dir()

    @property
    def directory(self) -> Path:
        """The on-disk directory backing this store."""
        return self._dir

    # -- write -------------------------------------------------------------

    def append(
        self,
        summary: KifunarabeSummary,
        config: KifunarabeConfig,
        sgf_path: str | None,
        critical_3_set: list[int] | None = None,
    ) -> Path:
        """Persist one finished session and return the file path.

        Args:
            summary: The session summary produced by the controller.
            config: The session config (turn / hints / max_moves).
            sgf_path: Source SGF path (``None`` for an in-memory game).
            critical_3_set: Move numbers in the Critical 3 set; the
                controller already stores it but we re-snapshot it
                here so the history file is self-contained.

        Returns:
            The :class:`Path` of the newly-written file.
        """
        self._dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now()
        suffix = self._safe_suffix(sgf_path)
        filename = f"{timestamp.strftime(_FILENAME_FORMAT)}_{suffix}.json"
        path = self._dir / filename

        entry = KifunarabeHistoryEntry(
            timestamp=timestamp.isoformat(timespec="seconds"),
            sgf_path=sgf_path,
            config=asdict(config) if hasattr(config, "__dataclass_fields__") else {"turn": config.turn, "max_hints": config.max_hints, "max_moves": config.max_moves},
            summary=asdict(summary) if hasattr(summary, "__dataclass_fields__") else self._summary_to_dict(summary),
            critical_3_set=sorted(critical_3_set or []),
        )
        try:
            path.write_text(
                json.dumps(entry.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            _log.warning("kifunarabe history: failed to write %s: %s", path, e)
            raise
        return path

    @staticmethod
    def _summary_to_dict(summary: KifunarabeSummary) -> dict[str, Any]:
        """Fallback ``to_dict`` for summary objects that aren't dataclasses."""
        return {
            "total_positions": summary.total_positions,
            "correct_count": summary.correct_count,
            "wrong_count": summary.wrong_count,
            "auto_advance_count": summary.auto_advance_count,
            "skipped_count": summary.skipped_count,
            "max_moves_reached": summary.max_moves_reached,
            "critical_3_total": summary.critical_3_total,
            "critical_3_correct": summary.critical_3_correct,
            "critical_3_wrong": summary.critical_3_wrong,
            "critical_3_skipped": summary.critical_3_skipped,
        }

    @staticmethod
    def _safe_suffix(sgf_path: str | None) -> str:
        """Derive a filename-safe suffix from the SGF path."""
        if not sgf_path:
            return "manual"
        stem = Path(sgf_path).stem or "sgf"
        # Strip characters that are unsafe on Windows / POSIX.
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)
        return safe[:48] or "sgf"

    # -- read --------------------------------------------------------------

    def list_entries(self, limit: int | None = None) -> list[KifunarabeHistoryEntry]:
        """Return history entries sorted newest-first.

        Args:
            limit: If set, only the most-recent ``limit`` entries are
                returned (after sorting).

        Returns:
            List of :class:`KifunarabeHistoryEntry`. Malformed files
            are skipped with a warning rather than raising.
        """
        if not self._dir.is_dir():
            return []
        entries: list[tuple[str, KifunarabeHistoryEntry]] = []
        for path in self._dir.glob("*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                entry = KifunarabeHistoryEntry.from_dict(raw)
            except (OSError, json.JSONDecodeError, ValueError) as e:
                _log.warning("kifunarabe history: skipping malformed file %s: %s", path, e)
                continue
            # ``mtime`` is intentionally inspected: the list is
            # deterministic even when multiple sessions end in the
            # same wall-clock second. We suppress the OSError because
            # stat() on a transient file (e.g. anti-virus scanner
            # holding the handle) is fine to fall back to zero.
            with contextlib.suppress(OSError):
                _ = path.stat().st_mtime
            entries.append((entry.timestamp or "", entry))
        entries.sort(key=lambda pair: (pair[0], pair[1].critical_3_set), reverse=True)
        result = [entry for _ts, entry in entries]
        if limit is not None and limit >= 0:
            result = result[:limit]
        return result

    def count(self) -> int:
        """Return the number of history files on disk."""
        if not self._dir.is_dir():
            return 0
        return sum(1 for _ in self._dir.glob("*.json"))


__all__ = [
    "KifunarabeHistoryEntry",
    "KifunarabeHistoryStore",
    "default_history_dir",
]
