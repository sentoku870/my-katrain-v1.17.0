"""Phase 179-B1 / B-2: integration tests for Critical 3.

The tests cover two groups:

* **Critical 3 aggregation** (B-2): a session configured with a
  ``critical_3_set`` correctly accumulates
  ``critical_3_correct/wrong/skipped`` counters.
* **Critical 3 hit-rate summary** (B-2): ``KifunarabeSummary`` exposes
  ``critical_3_hit_rate`` derived from those counters.

These tests intentionally do **not** exercise the GUI (Kivy popup,
spinner wiring). The popup is unit-tested by importing its module to
verify the function reference resolves.

Phase 249-α: ``test_select_critical_raises_returns_empty`` is now a
real test (it used to be a no-op that only asserted the function
returned a list). We mock ``select_critical_moves`` at its import
site and confirm that exceptions are caught per player.
"""

from __future__ import annotations

import importlib
import unittest
from typing import Any
from unittest.mock import patch


class TestGetCritical3MoveNumbers(unittest.TestCase):
    def test_none_game_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import get_critical_3_move_numbers

        self.assertEqual(get_critical_3_move_numbers(None), [])

    def test_game_without_current_node_returns_empty(self) -> None:
        from katrain.core.study.kifunarabe import get_critical_3_move_numbers

        class _Game:
            current_node = None

        self.assertEqual(get_critical_3_move_numbers(_Game()), [])

    def test_select_critical_raises_returns_empty(self) -> None:
        """Phase 249-α: every per-player call to ``select_critical_moves``
        raises; the helper must still return an empty list (not
        propagate)."""
        import katrain.core.analysis.critical_moves as cm_mod
        from katrain.core.study import kifunarabe as kif_mod

        class _Node:
            pass

        class _Game:
            current_node = _Node()

        # ``kifunarabe.get_critical_3_move_numbers`` imports
        # ``select_critical_moves`` lazily inside the function body
        # (``from katrain.core.analysis.critical_moves import
        # select_critical_moves``). Patch the symbol at the
        # ``critical_moves`` module level - Python's import system
        # binds the local name at function-call time, so the patch
        # takes effect on the next call.
        with patch.object(cm_mod, "select_critical_moves", side_effect=RuntimeError("boom")):
            result = kif_mod.get_critical_3_move_numbers(_Game())

        self.assertEqual(result, [])

    def test_select_critical_per_player_isolated(self) -> None:
        """Phase 249-α: one player raising must not skip the other
        player's critical-move resolution."""
        import katrain.core.analysis.critical_moves as cm_mod
        from katrain.core.study import kifunarabe as kif_mod

        class _Node:
            pass

        class _Game:
            current_node = _Node()

        # Build a stand-in CriticalMove result with ``move_number`` so
        # the helper picks it up.
        class _CriticalMove:
            def __init__(self, n: int) -> None:
                self.move_number = n

        def _stub_select_critical_moves(*args: Any, **kwargs: Any) -> list[Any]:
            player_filter = kwargs.get("player_filter")
            if player_filter == "B":
                raise RuntimeError("simulated B-side failure")
            # W side: return 2 moves.
            return [_CriticalMove(7), _CriticalMove(15)]

        with patch.object(cm_mod, "select_critical_moves", side_effect=_stub_select_critical_moves):
            result = kif_mod.get_critical_3_move_numbers(_Game())

        # Even though the B side raised, the W side's two moves were
        # captured.
        self.assertEqual(result, [7, 15])

    def test_select_critical_ignores_non_int_move_numbers(self) -> None:
        """Phase 249-α: defensive against malformed move_number
        attributes (e.g. ``None``)."""
        import katrain.core.analysis.critical_moves as cm_mod
        from katrain.core.study import kifunarabe as kif_mod

        class _Node:
            pass

        class _Game:
            current_node = _Node()

        class _BadMove:
            move_number = None

        def _stub(*args: Any, **kwargs: Any) -> list[Any]:
            return [_BadMove()]

        with patch.object(cm_mod, "select_critical_moves", side_effect=_stub):
            result = kif_mod.get_critical_3_move_numbers(_Game())

        # Non-int move_number is silently dropped.
        self.assertEqual(result, [])


class TestSessionCritical3Counters(unittest.TestCase):
    def _config(self) -> Any:
        from katrain.core.study.kifunarabe import KifunarabeConfig

        return KifunarabeConfig()

    def _session(self) -> Any:
        from katrain.core.study.kifunarabe import KifunarabeSession

        return KifunarabeSession(self._config(), critical_3_move_numbers=[3, 7, 12])

    def test_correct_guess_in_critical3_increments_correct(self) -> None:
        s = self._session()
        s.record_guess(move_number=3, expected_gtp="D4", guessed_gtp="D4")
        s.record_guess(move_number=7, expected_gtp="Q16", guessed_gtp="R16")
        s.record_guess(move_number=12, expected_gtp="D16", guessed_gtp="D16")
        self.assertEqual(s.critical_3_correct, 2)
        self.assertEqual(s.critical_3_wrong, 1)
        self.assertEqual(s.critical_3_skipped, 0)

    def test_auto_advance_in_critical3_increments_skipped(self) -> None:
        s = self._session()
        s.record_auto_advance(3)
        s.record_auto_advance(7)
        self.assertEqual(s.critical_3_skipped, 2)
        self.assertEqual(s.critical_3_correct, 0)
        self.assertEqual(s.critical_3_wrong, 0)

    def test_skipped_no_move_in_critical3_increments_skipped(self) -> None:
        s = self._session()
        s.record_skipped_no_move(12)
        self.assertEqual(s.critical_3_skipped, 1)

    def test_non_critical3_guess_does_not_change_critical_counters(self) -> None:
        s = self._session()
        s.record_guess(move_number=4, expected_gtp="D4", guessed_gtp="D4")  # not in set
        s.record_guess(move_number=5, expected_gtp="Q16", guessed_gtp="R16")
        self.assertEqual(s.critical_3_correct, 0)
        self.assertEqual(s.critical_3_wrong, 0)
        self.assertEqual(s.critical_3_skipped, 0)

    def test_summary_aggregates_critical3(self) -> None:
        s = self._session()
        s.record_guess(3, "D4", "D4")  # correct
        s.record_guess(7, "Q16", "R16")  # wrong
        s.record_auto_advance(12)  # skipped
        s.record_guess(4, "D5", "D5")  # not in set, correct (regular)
        s.record_guess(5, "D6", "D7")  # not in set, wrong (regular)
        summary = s.get_summary()
        self.assertEqual(summary.critical_3_total, 3)
        self.assertEqual(summary.critical_3_correct, 1)
        self.assertEqual(summary.critical_3_wrong, 1)
        self.assertEqual(summary.critical_3_skipped, 1)
        self.assertAlmostEqual(summary.critical_3_hit_rate, 1 / 3 * 100.0, places=4)
        # Aggregate numbers still correct.
        self.assertEqual(summary.correct_count, 2)
        self.assertEqual(summary.wrong_count, 2)
        self.assertEqual(summary.auto_advance_count, 1)

    def test_clear_resets_critical3_counters(self) -> None:
        s = self._session()
        s.record_guess(3, "D4", "D4")
        s.clear()
        self.assertEqual(s.critical_3_correct, 0)
        self.assertEqual(s.critical_3_wrong, 0)
        self.assertEqual(s.critical_3_skipped, 0)


class TestSummaryCritical3HitRate(unittest.TestCase):
    def test_no_critical3_total_returns_zero(self) -> None:
        from katrain.core.study.kifunarabe import KifunarabeSummary

        s = KifunarabeSummary(10, 5, 2, 1, 2)
        self.assertEqual(s.critical_3_hit_rate, 0.0)

    def test_critical3_hit_rate_with_data(self) -> None:
        """Phase 182: ``critical_3_hit_rate`` is the only "aggregate" property
        that was added in Phase 179-B2 (to_dict was removed in Phase 182-B)."""
        from katrain.core.study.kifunarabe import KifunarabeSummary

        s = KifunarabeSummary(
            total_positions=10,
            correct_count=5,
            wrong_count=2,
            auto_advance_count=1,
            skipped_count=2,
            max_moves_reached=False,
            critical_3_total=4,
            critical_3_correct=2,
            critical_3_wrong=1,
            critical_3_skipped=1,
        )
        # 2 correct out of 4 total critical positions → 50%.
        self.assertAlmostEqual(s.critical_3_hit_rate, 50.0, places=4)


class TestPopupModuleImportable(unittest.TestCase):
    def test_critical3_popup_module_imports(self) -> None:
        """Phase 179-B1: the popup module must be importable without raising."""
        # The import path is what the controller uses inside its
        # ``_highlight_critical_3_if_reached`` method, so a regression here
        # would silently break the badge feature.
        mod = importlib.import_module("katrain.gui.popups.kifunarabe_critical3_popup")
        self.assertTrue(callable(getattr(mod, "show_critical_3_badge", None)))


if __name__ == "__main__":
    unittest.main()
