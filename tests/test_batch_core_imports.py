"""Test backward compatibility for batch module migration (Phase 42).

This module verifies that:
1. Imports from katrain.tools.batch_analyze_sgf still work (backward compat)
2. Imports from katrain.core.batch work correctly (new API)
3. Re-exported classes are identical (not copies)
4. Functions behave correctly (not just importable)
"""

from __future__ import annotations

import pytest


class TestBackwardCompatImports:
    """Verify imports from tools.batch_analyze_sgf still work."""

    def test_dataclass_imports_are_same_class(self):
        """Re-exported classes must be identical (not copies)."""
        from katrain.tools.batch_analyze_sgf import WriteError, BatchResult
        from katrain.core.batch import (
            WriteError as CoreWriteError,
            BatchResult as CoreBatchResult,
        )

        assert WriteError is CoreWriteError
        assert BatchResult is CoreBatchResult

    def test_function_imports_are_callable(self):
        """Key functions must be importable and callable."""
        from katrain.tools.batch_analyze_sgf import (
            has_analysis,
            parse_timeout_input,
            run_batch,
            analyze_single_file,
        )

        assert callable(has_analysis)
        assert callable(parse_timeout_input)
        assert callable(run_batch)
        assert callable(analyze_single_file)

    def test_private_aliases_work(self):
        """Private names must still work for existing code."""
        from katrain.tools.batch_analyze_sgf import (
            _get_canonical_loss,
            _safe_write_file,
            _sanitize_filename,
            _get_unique_filename,
            _normalize_player_name,
        )

        assert callable(_get_canonical_loss)
        assert callable(_safe_write_file)
        assert callable(_sanitize_filename)
        assert callable(_get_unique_filename)
        assert callable(_normalize_player_name)

    def test_stats_private_aliases_work(self):
        """Stats function private aliases must work."""
        from katrain.tools.batch_analyze_sgf import (
            _extract_game_stats,
            _build_batch_summary,
            _extract_players_from_stats,
            _build_player_summary,
        )

        assert callable(_extract_game_stats)
        assert callable(_build_batch_summary)
        assert callable(_extract_players_from_stats)
        assert callable(_build_player_summary)

    def test_leela_re_exports_work(self):
        """Leela-related re-exports must work for existing tests."""
        from katrain.tools.batch_analyze_sgf import (
            LeelaEngine,
            LeelaPositionEval,
            EvalSnapshot,
            MoveEval,
            leela_position_to_move_eval,
        )

        # These should be classes/functions, not None
        assert LeelaEngine is not None
        assert LeelaPositionEval is not None
        assert EvalSnapshot is not None
        assert MoveEval is not None
        assert callable(leela_position_to_move_eval)

    def test_constants_are_exported(self):
        """Constants must be available from old import path."""
        from katrain.tools.batch_analyze_sgf import (
            DEFAULT_TIMEOUT_SECONDS,
            ENCODINGS_TO_TRY,
        )

        assert isinstance(DEFAULT_TIMEOUT_SECONDS, float)
        assert DEFAULT_TIMEOUT_SECONDS > 0
        assert isinstance(ENCODINGS_TO_TRY, tuple)
        assert len(ENCODINGS_TO_TRY) > 0


class TestCoreImports:
    """Verify new core.batch imports work correctly."""

    def test_eager_exports(self):
        """Models and helpers are eagerly available."""
        from katrain.core.batch import (
            WriteError,
            BatchResult,
            DEFAULT_TIMEOUT_SECONDS,
            ENCODINGS_TO_TRY,
            has_analysis,
            parse_timeout_input,
            safe_write_file,
            sanitize_filename,
            get_unique_filename,
            normalize_player_name,
            safe_int,
            needs_leela_karte_warning,
        )

        # Verify against actual value, not hardcoded
        assert isinstance(DEFAULT_TIMEOUT_SECONDS, float)
        assert DEFAULT_TIMEOUT_SECONDS > 0
        assert isinstance(ENCODINGS_TO_TRY, tuple)

        # Functions are callable
        assert callable(has_analysis)
        assert callable(parse_timeout_input)
        assert callable(safe_write_file)
        assert callable(sanitize_filename)
        assert callable(get_unique_filename)
        assert callable(normalize_player_name)
        assert callable(safe_int)
        assert callable(needs_leela_karte_warning)

    def test_lazy_exports_via_getattr(self):
        """Heavy functions available via lazy __getattr__."""
        from katrain.core.batch import (
            run_batch,
            analyze_single_file,
            analyze_single_file_leela,
        )

        assert callable(run_batch)
        assert callable(analyze_single_file)
        assert callable(analyze_single_file_leela)

    def test_lazy_stats_exports(self):
        """Stats functions available via lazy __getattr__."""
        from katrain.core.batch import (
            extract_game_stats,
            build_batch_summary,
            extract_players_from_stats,
            build_player_summary,
        )

        assert callable(extract_game_stats)
        assert callable(build_batch_summary)
        assert callable(extract_players_from_stats)
        assert callable(build_player_summary)

    def test_explicit_submodule_import(self):
        """Direct submodule import works."""
        from katrain.core.batch.orchestration import run_batch
        from katrain.core.batch.analysis import (
            analyze_single_file,
            analyze_single_file_leela,
        )
        from katrain.core.batch.stats import (
            extract_game_stats,
            build_batch_summary,
        )

        assert callable(run_batch)
        assert callable(analyze_single_file)
        assert callable(analyze_single_file_leela)
        assert callable(extract_game_stats)
        assert callable(build_batch_summary)

    def test_lazy_and_explicit_are_same_function(self):
        """Lazy import returns the same function object as explicit import."""
        from katrain.core.batch import run_batch as lazy_run_batch
        from katrain.core.batch.orchestration import run_batch as explicit_run_batch

        assert lazy_run_batch is explicit_run_batch

    def test_lazy_caching_works(self):
        """Lazy imports are cached after first access."""
        import katrain.core.batch as batch_module

        # First access triggers __getattr__
        first_access = batch_module.run_batch

        # Second access should return cached value
        second_access = batch_module.run_batch

        assert first_access is second_access


class TestFunctionBehavior:
    """Verify actual function behavior, not just importability."""

    def test_parse_timeout_behavior(self):
        """Verify timeout parsing behavior."""
        from katrain.tools.batch_analyze_sgf import parse_timeout_input

        assert parse_timeout_input("300", default=600.0) == 300.0
        assert parse_timeout_input("None", default=600.0) is None
        assert parse_timeout_input("", default=600.0) == 600.0
        assert parse_timeout_input("invalid", default=600.0) == 600.0

    def test_get_canonical_loss_behavior(self):
        """Verify loss clamping behavior."""
        from katrain.tools.batch_analyze_sgf import _get_canonical_loss

        assert _get_canonical_loss(None) == 0.0
        assert _get_canonical_loss(-1.5) == 0.0
        assert _get_canonical_loss(2.5) == 2.5
        assert _get_canonical_loss(0.0) == 0.0

    def test_safe_int_behavior(self):
        """Verify safe_int parsing behavior."""
        from katrain.core.batch import safe_int

        assert safe_int("100", default=50) == 100
        assert safe_int("", default=50) == 50
        assert safe_int("invalid", default=50) == 50
        assert safe_int(None, default=50) == 50

    def test_sanitize_filename_behavior(self):
        """Verify filename sanitization."""
        from katrain.core.batch import sanitize_filename

        # Should remove/replace invalid characters
        result = sanitize_filename("test<>file:name")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_has_analysis_with_nonexistent_file(self):
        """has_analysis returns False for non-existent files."""
        from katrain.core.batch import has_analysis

        assert has_analysis("/nonexistent/path/file.sgf") is False


class TestModuleAllAttribute:
    """Verify __all__ is correctly defined."""

    def test_all_contains_expected_exports(self):
        """__all__ should list all public exports."""
        from katrain.core.batch import __all__

        expected_exports = [
            # Models
            "WriteError",
            "BatchResult",
            # Constants
            "DEFAULT_TIMEOUT_SECONDS",
            "ENCODINGS_TO_TRY",
            # Helpers
            "has_analysis",
            "parse_timeout_input",
            "safe_int",
            # Lazy exports
            "run_batch",
            "analyze_single_file",
            "analyze_single_file_leela",
            "extract_game_stats",
            "build_player_summary",
        ]

        for name in expected_exports:
            assert name in __all__, f"{name} should be in __all__"

    def test_all_exports_are_importable(self):
        """Every name in __all__ should be importable."""
        from katrain.core.batch import __all__
        import katrain.core.batch as batch_module

        for name in __all__:
            obj = getattr(batch_module, name, None)
            assert obj is not None, f"{name} in __all__ but not importable"
