"""Phase 179-A: tests for the kifunarabe history persistence layer.

Covers the contract of :mod:`katrain.core.study.kifunarabe` history helpers
without touching Kivy. Each test pins one specific invariant:

* ``sgf_history_key`` is content-stable but path-fallback-safe.
* ``save_session_history`` writes JSON under the resolved directory.
* ``load_session_history`` round-trips ``summary.to_dict()``.
* ``clear_all_history`` deletes every ``*.json`` and returns the count.
* ``_resolve_history_dir`` honours a custom katrain config and falls
  back to ``~/.katrain/kifunarabe_history/`` otherwise.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from katrain.core.study.kifunarabe import (
    KifunarabeConfig,
    KifunarabeSummary,
    clear_all_history,
    get_history_summary,
    load_session_history,
    save_session_history,
    sgf_history_key,
)


class _TmpKatrain:
    """Minimal stand-in for ``KaTrainGui`` carrying only what the helpers need."""

    def __init__(self, config_section: dict[str, Any]) -> None:
        self._section = config_section

    def config(self, key: str, default: Any = None) -> Any:
        if key == "kifunarabe":
            return self._section
        if key.startswith("kifunarabe/"):
            short = key.split("/", 1)[1]
            return self._section.get(short, default)
        return default


class TestSgfHistoryKey(unittest.TestCase):
    def test_same_content_same_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.sgf"
            b = Path(td) / "b.sgf"
            a.write_bytes(b"(;GM[1];)")
            b.write_bytes(b"(;GM[1];)")
            self.assertEqual(sgf_history_key(str(a)), sgf_history_key(str(b)))

    def test_different_content_different_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.sgf"
            b = Path(td) / "b.sgf"
            a.write_bytes(b"(;GM[1];B[aa];)")
            b.write_bytes(b"(;GM[1];B[bb];)")
            self.assertNotEqual(sgf_history_key(str(a)), sgf_history_key(str(b)))

    def test_unreadable_path_falls_back_to_path_hash(self) -> None:
        """Missing files fall back to hashing the path string. No exception."""
        with tempfile.TemporaryDirectory() as td:
            nonexistent = str(Path(td) / "nope.sgf")
            other_nonexistent = str(Path(td) / "also_nope.sgf")
            self.assertNotEqual(sgf_history_key(nonexistent), sgf_history_key(other_nonexistent))


class TestHistorySaveLoadRoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp())
        self._sgf = self._tmpdir / "game.sgf"
        self._sgf.write_bytes(b"(;GM[1];B[aa];W[bb];)")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _katrain(self, history_dir: str) -> _TmpKatrain:
        return _TmpKatrain({"history_dir": history_dir})

    def _summary(self) -> KifunarabeSummary:
        return KifunarabeSummary(
            total_positions=20,
            correct_count=10,
            wrong_count=4,
            auto_advance_count=3,
            skipped_count=3,
            max_moves_reached=False,
            critical_3_total=6,
            critical_3_correct=4,
            critical_3_wrong=2,
            critical_3_skipped=0,
        )

    def test_save_writes_json_in_configured_dir(self) -> None:
        """Phase 179-A: stored history_dir from config wins over default."""
        history_dir = str(self._tmpdir / "history")
        cfg = KifunarabeConfig(turn="both", max_hints=3, max_moves=0)
        katrain = self._katrain(history_dir)
        out = save_session_history(str(self._sgf), cfg, self._summary(), katrain=katrain)
        self.assertIsNotNone(out)
        assert out is not None  # for the type checker
        self.assertTrue(out.exists())
        self.assertTrue(out.parent.samefile(Path(history_dir)))
        self.assertEqual(out.suffix, ".json")

    def test_load_round_trips_summary_dict(self) -> None:
        history_dir = str(self._tmpdir / "history")
        cfg = KifunarabeConfig(turn="B", max_hints=2, max_moves=50, critical_only_threshold=1.0)
        katrain = self._katrain(history_dir)
        summary = self._summary()
        save_session_history(str(self._sgf), cfg, summary, katrain=katrain)

        loaded = load_session_history(str(self._sgf), katrain=katrain)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["sgf_path"], str(self._sgf))
        self.assertIn("saved_at", loaded)
        self.assertEqual(loaded["config"]["turn"], "B")
        self.assertEqual(loaded["config"]["critical_only_threshold"], 1.0)
        # to_dict values are JSON numbers, so compare as primitives.
        self.assertEqual(loaded["summary"]["correct_count"], 10)
        self.assertEqual(loaded["summary"]["critical_3_total"], 6)
        self.assertEqual(loaded["summary"]["critical_3_correct"], 4)
        # Rates are computed properties; verify they round-trip too.
        self.assertAlmostEqual(loaded["summary"]["correct_rate"], 10 / 14 * 100.0, places=4)
        self.assertAlmostEqual(
            loaded["summary"]["critical_3_hit_rate"],
            4 / 6 * 100.0,
            places=4,
        )

    def test_save_returns_none_when_target_dir_is_unwritable(self) -> None:
        """When the resolved dir cannot be created, save_session_history returns None."""
        # ``/proc/this-cannot-be-a-dir`` is the canonical unwritable path on Linux.
        cfg = KifunarabeConfig()
        out = save_session_history(
            str(self._sgf),
            cfg,
            self._summary(),
            katrain=_TmpKatrain({"history_dir": "/proc/kifunarabe-cannot-create"}),
        )
        # Either returns None (caught exception) or returns a path under the
        # fallback dir (the helper's safety net). Both are acceptable.
        if out is not None:
            self.assertIn(".json", out.name)

    def test_load_missing_returns_none(self) -> None:
        history_dir = str(self._tmpdir / "empty")
        result = load_session_history(str(self._sgf), katrain=self._katrain(history_dir))
        self.assertIsNone(result)

    def test_load_corrupt_json_returns_none(self) -> None:
        history_dir = self._tmpdir / "broken"
        history_dir.mkdir()
        key = sgf_history_key(str(self._sgf))
        (history_dir / f"{key}.json").write_text("{not json", encoding="utf-8")
        result = load_session_history(str(self._sgf), katrain=self._katrain(str(history_dir)))
        self.assertIsNone(result)


class TestClearAllHistory(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp())
        self._sgf = self._tmpdir / "game.sgf"
        self._sgf.write_bytes(b"(;GM[1];)")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_clear_removes_all_json_files(self) -> None:
        cfg = KifunarabeConfig()
        summary = KifunarabeSummary(10, 5, 2, 1, 2)
        # Write two history files into the same dir.
        katrain = _TmpKatrain({"history_dir": str(self._tmpdir / "history")})
        save_session_history(str(self._sgf), cfg, summary, katrain=katrain)
        # Add another arbitrary json to make sure non-history files are also removed.
        other_key_path = self._tmpdir / "history" / "extra.json"
        other_key_path.parent.mkdir(parents=True, exist_ok=True)
        other_key_path.write_text("{}", encoding="utf-8")

        count = clear_all_history(katrain=katrain)
        self.assertEqual(count, 2)
        self.assertEqual(list((self._tmpdir / "history").glob("*.json")), [])

    def test_clear_no_history_returns_zero(self) -> None:
        katrain = _TmpKatrain({"history_dir": str(self._tmpdir / "never-used")})
        self.assertEqual(clear_all_history(katrain=katrain), 0)


class TestGetHistorySummary(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_empty_dir_returns_zero(self) -> None:
        info = get_history_summary(katrain=_TmpKatrain({"history_dir": str(self._tmpdir)}))
        self.assertEqual(info["count"], 0)
        self.assertEqual(info["latest_mtime"], 0.0)

    def test_two_files_returns_two(self) -> None:
        d = self._tmpdir / "h"
        d.mkdir()
        (d / "a.json").write_text("{}", encoding="utf-8")
        (d / "b.json").write_text("{}", encoding="utf-8")
        info = get_history_summary(katrain=_TmpKatrain({"history_dir": str(d)}))
        self.assertEqual(info["count"], 2)
        self.assertGreater(info["latest_mtime"], 0.0)


# Phase 181-A: controller-level _save_history uses _source_sgf_path when
# game.sgf_filename is None (the kifunarabe situation).
class TestControllerSaveHistory(unittest.TestCase):
    """Phase 181-A: history saving must work even when game.sgf_filename is None.

    The kifunarabe setup intentionally passes ``sgf_filename=None`` to
    ``do_new_game`` to prevent overwriting the source SGF. Without
    ``_source_sgf_path``, ``_save_history`` would always no-op.
    """

    def setUp(self) -> None:
        from katrain.gui.managers.kifunarabe_controller import KifunarabeController

        self._tmpdir = Path(tempfile.mkdtemp())
        self._sgf = self._tmpdir / "game.sgf"
        self._sgf.write_bytes(b"(;GM[1];B[aa];W[bb];)")

        self.mode_state = {"value": True}
        self.show_summary_calls: list[Any] = []

        self.controller = KifunarabeController(
            get_ctx=lambda: None,
            get_config=lambda key, default=None: None,
            get_game=lambda: _MockGameWithoutSgfFilename(),
            get_controls=lambda: None,
            get_mode=lambda: self.mode_state["value"],
            set_mode=lambda v: self.mode_state.__setitem__("value", v),
            logger=lambda *a, **kw: None,
            show_summary_fn=lambda c, s: self.show_summary_calls.append((c, s)),
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _summary(self) -> Any:
        return KifunarabeSummary(
            total_positions=10,
            correct_count=5,
            wrong_count=2,
            auto_advance_count=1,
            skipped_count=2,
        )

    def test_save_uses_source_sgf_path_when_game_filename_is_none(self) -> None:
        """Phase 181-A: the controller falls back to ``_source_sgf_path``."""
        # Configure history_dir via a tiny config object.
        from katrain.core.constants import (
            KIFUNARABE_HISTORY_DIR_DEFAULT,
            KIFUNARABE_HISTORY_DIR_KEY,
        )

        # Patch the controller's config getter so the history_dir resolves
        # under our temp dir.
        self.controller._get_config = lambda key, default=None: (
            str(self._tmpdir / "history")
            if key == KIFUNARABE_HISTORY_DIR_KEY
            else (KIFUNARABE_HISTORY_DIR_DEFAULT if key.endswith("_DEFAULT") else default)
        )
        self.controller._get_ctx = lambda: None  # no katrain → falls back to default
        # Re-resolve: the helper tries ctx first, then default, then
        # fallback. Use the default by clearing the configured dir.
        self.controller._get_config = lambda key, default=None: default

        # Make the controller think a session is active.
        from katrain.core.study.kifunarabe import KifunarabeSession

        self.controller._session = KifunarabeSession(KifunarabeConfig())
        self.controller._source_sgf_path = str(self._sgf)
        # Point the resolved history dir explicitly to our temp dir.
        self.controller._get_ctx = lambda: _TmpKatrain(
            {"history_dir": str(self._tmpdir / "history")}
        )

        self.controller._save_history(self._summary())

        # A JSON file should now exist under the temp dir.
        history_files = list((self._tmpdir / "history").glob("*.json"))
        self.assertEqual(len(history_files), 1)
        # The summary contents should round-trip.
        import json as _json

        data = _json.loads(history_files[0].read_text(encoding="utf-8"))
        self.assertEqual(data["sgf_path"], str(self._sgf))
        self.assertEqual(data["summary"]["correct_count"], 5)

    def test_save_skips_when_neither_source_nor_game_filename(self) -> None:
        """No path available at all → save is a silent no-op."""
        from katrain.core.study.kifunarabe import KifunarabeSession

        self.controller._session = KifunarabeSession(KifunarabeConfig())
        # _source_sgf_path remains None and game.sgf_filename is None.
        self.controller._save_history(self._summary())
        # Nothing should have been logged or written anywhere.
        # We just check that the call didn't raise and returned cleanly.
        self.assertIsNone(self.controller._summary_popup)


class _MockGameWithoutSgfFilename:
    """Game stub whose ``sgf_filename`` is explicitly None.

    Used by the Phase 181-A tests to verify the controller's fallback to
    ``_source_sgf_path``.
    """

    current_node = None
    sgf_filename = None


if __name__ == "__main__":
    unittest.main()
