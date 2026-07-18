"""Phase 249-β: tests for the persistent kifunarabe history store.

The store is Kivy-independent so it can be exercised without a
display, even on machines where the popup layer is not importable.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from katrain.core.study.kifunarabe import KifunarabeConfig, KifunarabeSummary
from katrain.core.study.kifunarabe_history import (
    KifunarabeHistoryEntry,
    KifunarabeHistoryStore,
    default_history_dir,
)


def _sample_config() -> KifunarabeConfig:
    return KifunarabeConfig(turn="both", max_hints=3, max_moves=50)


def _sample_summary() -> KifunarabeSummary:
    return KifunarabeSummary(
        total_positions=10,
        correct_count=7,
        wrong_count=2,
        auto_advance_count=1,
        skipped_count=0,
        max_moves_reached=False,
        critical_3_total=3,
        critical_3_correct=2,
        critical_3_wrong=1,
        critical_3_skipped=0,
    )


class TestKifunarabeHistoryStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = KifunarabeHistoryStore(directory=self.tmp.name)

    def test_append_creates_file(self) -> None:
        path = self.store.append(_sample_summary(), _sample_config(), sgf_path="Z:/games/game01.sgf")
        self.assertTrue(path.exists())
        self.assertTrue(path.name.endswith(".json"))
        # Timestamp prefix: 2026-07-18_093014.
        self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}_\d{6}_.+")

    def test_append_uses_safe_suffix(self) -> None:
        path = self.store.append(_sample_summary(), _sample_config(), sgf_path="Z:/games/My SGF (1).sgf")
        # Spaces / parens are replaced with underscores.
        self.assertNotIn(" ", path.name)
        self.assertNotIn("(", path.name)
        self.assertNotIn(")", path.name)

    def test_append_with_no_sgf_uses_manual_suffix(self) -> None:
        path = self.store.append(_sample_summary(), _sample_config(), sgf_path=None)
        self.assertIn("_manual.json", path.name)

    def test_round_trip_preserves_summary(self) -> None:
        self.store.append(_sample_summary(), _sample_config(), sgf_path="x.sgf", critical_3_set=[5, 11, 27])
        entries = self.store.list_entries()
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e.sgf_path, "x.sgf")
        self.assertEqual(e.critical_3_set, [5, 11, 27])
        # Summary fields survive the round trip.
        s = e.summary
        self.assertEqual(s["total_positions"], 10)
        self.assertEqual(s["correct_count"], 7)
        self.assertEqual(s["wrong_count"], 2)
        self.assertEqual(s["auto_advance_count"], 1)
        self.assertEqual(s["critical_3_total"], 3)
        self.assertEqual(s["critical_3_correct"], 2)
        # Config fields survive.
        self.assertEqual(e.config["turn"], "both")
        self.assertEqual(e.config["max_hints"], 3)
        self.assertEqual(e.config["max_moves"], 50)

    def test_list_entries_newest_first(self) -> None:
        # Three appends in quick succession; the last one wins.
        self.store.append(_sample_summary(), _sample_config(), sgf_path="a.sgf")
        self.store.append(_sample_summary(), _sample_config(), sgf_path="b.sgf")
        self.store.append(_sample_summary(), _sample_config(), sgf_path="c.sgf")
        entries = self.store.list_entries()
        self.assertEqual(len(entries), 3)
        # Each entry has a timestamp string; the sort is newest-first.
        timestamps = [e.timestamp for e in entries]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_list_entries_respects_limit(self) -> None:
        for i in range(5):
            self.store.append(_sample_summary(), _sample_config(), sgf_path=f"game{i}.sgf")
        self.assertEqual(len(self.store.list_entries(limit=2)), 2)
        self.assertEqual(len(self.store.list_entries(limit=10)), 5)
        self.assertEqual(len(self.store.list_entries(limit=0)), 0)

    def test_list_entries_skips_malformed_files(self) -> None:
        # Write a garbage JSON file directly into the directory.
        bad = Path(self.tmp.name) / "2026-07-18_120000_bogus.json"
        bad.write_text("not json at all", encoding="utf-8")
        # And a valid one.
        self.store.append(_sample_summary(), _sample_config(), sgf_path="ok.sgf")
        entries = self.store.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].sgf_path, "ok.sgf")

    def test_count(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.store.append(_sample_summary(), _sample_config(), sgf_path="a.sgf")
        self.assertEqual(self.store.count(), 1)

    def test_list_entries_empty_dir(self) -> None:
        self.assertEqual(self.store.list_entries(), [])

    def test_default_history_dir(self) -> None:
        path = default_history_dir()
        self.assertIn(".katrain", str(path))
        self.assertTrue(str(path).endswith("kifunarabe_history"))


class TestKifunarabeHistoryEntry(unittest.TestCase):
    def test_to_dict_round_trip(self) -> None:
        entry = KifunarabeHistoryEntry(
            timestamp="2026-07-18T09:30:14",
            sgf_path="Z:/games/a.sgf",
            config={"turn": "B", "max_hints": 2, "max_moves": 0},
            summary={"total_positions": 5, "correct_count": 3, "wrong_count": 2, "auto_advance_count": 0, "skipped_count": 0},
            critical_3_set=[3, 7],
        )
        d = entry.to_dict()
        self.assertEqual(d["timestamp"], "2026-07-18T09:30:14")
        self.assertEqual(d["critical_3_set"], [3, 7])
        back = KifunarabeHistoryEntry.from_dict(d)
        self.assertEqual(back.sgf_path, "Z:/games/a.sgf")
        self.assertEqual(back.critical_3_set, [3, 7])

    def test_from_dict_defaults(self) -> None:
        back = KifunarabeHistoryEntry.from_dict({})
        self.assertEqual(back.timestamp, "")
        self.assertIsNone(back.sgf_path)
        self.assertEqual(back.config, {})
        self.assertEqual(back.summary, {})
        self.assertEqual(back.critical_3_set, [])


if __name__ == "__main__":
    unittest.main()
