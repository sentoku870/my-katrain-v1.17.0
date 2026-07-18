"""Phase 249-γ: WRONG_GUESS export for kifunarabe (棋譜並べ) sessions.

When a user opts in via ``kifunarabe/auto_export_weaknesses`` the
finished session's WRONG_GUESS results are appended to a JSON file
under a configurable directory. The file is a flat list of
weakness entries; downstream consumers (Karte export, LLM
analysis, batch dashboards) can iterate over the directory.

The format is intentionally simple so the file is grep-friendly
and can be tailed / wc'd from the command line.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from katrain.core.study.kifunarabe import (
    GuessOutcome,
    KifunarabeSession,
)

_log = logging.getLogger(__name__)


SEVERITY_WRONG_GUESS = "WRONG_GUESS"
SEVERITY_CRITICAL_3_WRONG = "CRITICAL_3_WRONG"


@dataclass
class KifunarabeWeakness:
    """A single WRONG_GUESS exported for downstream analysis.

    Attributes:
        timestamp: ISO-8601 string of the export time.
        sgf_path: Source SGF (or None).
        move_number: 1-indexed tree position of the wrong guess.
        expected_gtp: GTP coordinate the user should have clicked.
        guessed_gtp: GTP coordinate the user actually clicked.
        hints_shown: Number of hint markers visible.
        severity: ``WRONG_GUESS`` (regular) or
            ``CRITICAL_3_WRONG`` (the position was on the Critical 3
            set for the session).
    """

    timestamp: str
    sgf_path: str | None
    move_number: int
    expected_gtp: str
    guessed_gtp: str
    hints_shown: int
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sgf_path": self.sgf_path,
            "move_number": self.move_number,
            "expected_gtp": self.expected_gtp,
            "guessed_gtp": self.guessed_gtp,
            "hints_shown": self.hints_shown,
            "severity": self.severity,
        }


def collect_weaknesses(session: KifunarabeSession, sgf_path: str | None) -> list[KifunarabeWeakness]:
    """Return the WRONG_GUESS entries from ``session`` as weaknesses.

    Entries that are not WRONG_GUESS (CORRECT, AUTO_ADVANCE,
    SKIPPED) are silently skipped. Auto-advanced positions do not
    represent a real user failure and are excluded.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    critical_3_set = session.critical_3_set
    out: list[KifunarabeWeakness] = []
    for r in session.results:
        if r.outcome != GuessOutcome.WRONG_GUESS:
            continue
        if not r.expected_gtp or not r.guessed_gtp:
            continue
        severity = (
            SEVERITY_CRITICAL_3_WRONG
            if r.move_number in critical_3_set
            else SEVERITY_WRONG_GUESS
        )
        out.append(
            KifunarabeWeakness(
                timestamp=timestamp,
                sgf_path=sgf_path,
                move_number=r.move_number,
                expected_gtp=r.expected_gtp,
                guessed_gtp=r.guessed_gtp,
                hints_shown=r.hints_shown,
                severity=severity,
            )
        )
    return out


def default_export_dir() -> Path:
    """Default directory for weakness exports."""
    return Path.home() / ".katrain" / "kifunarabe_weaknesses"


class KifunarabeWeaknessExporter:
    """Append-only writer of :class:`KifunarabeWeakness` records.

    One file per session (mirroring :class:`KifunarabeHistoryStore`).
    Filename: ``YYYY-MM-DD_HHMMSS_<safe_suffix>.json``.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        self._dir: Path = Path(directory) if directory is not None else default_export_dir()

    @property
    def directory(self) -> Path:
        return self._dir

    def export(
        self,
        session: KifunarabeSession,
        sgf_path: str | None,
    ) -> Path | None:
        """Append the session's WRONG_GUESS results to a new file.

        Returns the file path, or ``None`` if there was nothing to
        export (a session with zero wrong guesses leaves no
        artifact). Existing files in the directory are not touched.
        """
        weaknesses = collect_weaknesses(session, sgf_path)
        if not weaknesses:
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now()
        suffix = self._safe_suffix(sgf_path)
        path = self._dir / f"{timestamp.strftime('%Y-%m-%d_%H%M%S')}_{suffix}.json"
        payload = {
            "schema_version": 1,
            "session_summary": {
                "total_positions": len(session.results),
                "wrong_count": sum(1 for r in session.results if r.outcome == GuessOutcome.WRONG_GUESS),
                "sgf_path": sgf_path,
                "config": {
                    "turn": session.config.turn,
                    "max_hints": session.config.max_hints,
                    "max_moves": session.config.max_moves,
                },
            },
            "weaknesses": [w.to_dict() for w in weaknesses],
        }
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            _log.warning("kifunarabe weakness export: failed to write %s: %s", path, e)
            raise
        return path

    @staticmethod
    def _safe_suffix(sgf_path: str | None) -> str:
        if not sgf_path:
            return "manual"
        stem = Path(sgf_path).stem or "sgf"
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)
        return safe[:48] or "sgf"


__all__ = [
    "KifunarabeWeakness",
    "KifunarabeWeaknessExporter",
    "SEVERITY_WRONG_GUESS",
    "SEVERITY_CRITICAL_3_WRONG",
    "collect_weaknesses",
    "default_export_dir",
]
