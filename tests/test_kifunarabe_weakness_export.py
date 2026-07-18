"""Phase 249-γ: tests for the kifunarabe weakness exporter.

The exporter is Kivy-independent and writes one JSON file per
session containing the WRONG_GUESS results. Tests cover the
collection step (``collect_weaknesses``), the on-disk format
(``KifunarabeWeaknessExporter.export``), and the empty-session
short-circuit.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from katrain.core.study.kifunarabe import (
    KifunarabeConfig,
    KifunarabeSession,
)
from katrain.core.study.kifunarabe_weakness_export import (
    SEVERITY_CRITICAL_3_WRONG,
    SEVERITY_WRONG_GUESS,
    KifunarabeWeaknessExporter,
    collect_weaknesses,
    default_export_dir,
)


def _session_with_results() -> KifunarabeSession:
    """Build a session with a mix of correct / wrong / auto outcomes.

    Move numbers:
        1: correct (not in critical_3)
        2: wrong (in critical_3 → CRITICAL_3_WRONG)
        3: wrong (not in critical_3 → WRONG_GUESS)
        4: auto-advance (not weakness)
        5: skipped (not weakness)
    """
    s = KifunarabeSession(
        KifunarabeConfig(turn="B", max_hints=3, max_moves=0),
        critical_3_move_numbers=[2],
    )
    s.record_guess(1, "D4", "D4", hints_shown=3)  # correct
    s.record_guess(2, "D5", "E6", hints_shown=3)  # wrong (critical_3)
    s.record_guess(3, "Q16", "Q4", hints_shown=3)  # wrong
    s.record_auto_advance(4)  # auto-advance
    s.record_skipped_no_move(5)  # skipped
    return s


class TestCollectWeaknesses(unittest.TestCase):
    def test_picks_up_wrong_guesses(self) -> None:
        s = _session_with_results()
        weaknesses = collect_weaknesses(s, sgf_path="Z:/games/game01.sgf")
        self.assertEqual(len(weaknesses), 2)
        # First wrong guess is at move 2 (critical_3).
        self.assertEqual(weaknesses[0].move_number, 2)
        self.assertEqual(weaknesses[0].severity, SEVERITY_CRITICAL_3_WRONG)
        # Second wrong guess is at move 3 (regular).
        self.assertEqual(weaknesses[1].move_number, 3)
        self.assertEqual(weaknesses[1].severity, SEVERITY_WRONG_GUESS)

    def test_empty_session_no_weaknesses(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        self.assertEqual(collect_weaknesses(s, sgf_path=None), [])

    def test_correct_only_no_weaknesses(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "D4")
        s.record_guess(2, "Q16", "Q16")
        self.assertEqual(collect_weaknesses(s, sgf_path=None), [])

    def test_auto_advance_excluded(self) -> None:
        """AUTO_ADVANCE is not a real user failure."""
        s = KifunarabeSession(KifunarabeConfig(turn="B"))
        for i in range(1, 11):
            s.record_auto_advance(i)
        self.assertEqual(collect_weaknesses(s, sgf_path=None), [])

    def test_sgf_path_propagated(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "E5")  # wrong
        ws = collect_weaknesses(s, sgf_path="Z:/some/path.sgf")
        self.assertEqual(ws[0].sgf_path, "Z:/some/path.sgf")
        self.assertEqual(ws[0].expected_gtp, "D4")
        self.assertEqual(ws[0].guessed_gtp, "E5")

    def test_hints_shown_preserved(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "E5", hints_shown=4)
        ws = collect_weaknesses(s, sgf_path=None)
        self.assertEqual(ws[0].hints_shown, 4)


class TestKifunarabeWeaknessExporter(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exporter = KifunarabeWeaknessExporter(directory=self.tmp.name)

    def test_export_writes_json_file(self) -> None:
        s = _session_with_results()
        path = self.exporter.export(s, sgf_path="Z:/games/g.sgf")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        # Filename pattern: timestamp + safe suffix.
        self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}_\d{6}_g\.json$")

    def test_export_empty_session_returns_none(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        path = self.exporter.export(s, sgf_path=None)
        self.assertIsNone(path)
        # No file written.
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.json"))), 0)

    def test_export_correct_only_returns_none(self) -> None:
        """No WRONG_GUESS → no export."""
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "D4")
        s.record_guess(2, "Q16", "Q16")
        path = self.exporter.export(s, sgf_path=None)
        self.assertIsNone(path)

    def test_export_payload_shape(self) -> None:
        s = _session_with_results()
        path = self.exporter.export(s, sgf_path="Z:/g.sgf")
        self.assertIsNotNone(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["session_summary"]["wrong_count"], 2)
        self.assertEqual(payload["session_summary"]["config"]["turn"], "B")
        self.assertEqual(len(payload["weaknesses"]), 2)
        # Order is the order of the session's results list.
        severities = [w["severity"] for w in payload["weaknesses"]]
        self.assertEqual(severities, [SEVERITY_CRITICAL_3_WRONG, SEVERITY_WRONG_GUESS])

    def test_export_creates_directory(self) -> None:
        # Point at a non-existent directory; the exporter must create it.
        nested = Path(self.tmp.name) / "nested" / "deeper"
        exporter = KifunarabeWeaknessExporter(directory=nested)
        s = _session_with_results()
        path = exporter.export(s, sgf_path="x.sgf")
        self.assertIsNotNone(path)
        self.assertTrue(nested.is_dir())

    def test_safe_suffix(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "E5")  # wrong
        # Filename: timestamp + safe suffix of stem.
        path = self.exporter.export(s, sgf_path="Z:/My SGF (1).sgf")
        self.assertIsNotNone(path)
        self.assertNotIn(" ", path.name)
        self.assertNotIn("(", path.name)

    def test_no_sgf_uses_manual_suffix(self) -> None:
        s = KifunarabeSession(KifunarabeConfig())
        s.record_guess(1, "D4", "E5")  # wrong
        path = self.exporter.export(s, sgf_path=None)
        self.assertIsNotNone(path)
        self.assertIn("_manual.json", path.name)


class TestDefaultExportDir(unittest.TestCase):
    def test_default(self) -> None:
        path = default_export_dir()
        self.assertIn(".katrain", str(path))
        self.assertTrue(str(path).endswith("kifunarabe_weaknesses"))


if __name__ == "__main__":
    unittest.main()
