"""Import compatibility tests for Phase 72 karte package split, updated for Phase 171 (Leela 削除) and Phase 232 (シム削除).

Phase 171: ``MixedEngineSnapshotError`` / ``KARTE_ERROR_CODE_MIXED_ENGINE`` /
``KARTE_ERROR_CODE_NON_KATAGO`` / ``format_loss_with_engine_suffix`` /
``is_single_engine_snapshot`` を削除。
Phase 232: ``katrain.core.reports.karte_report`` 互換シムを完全削除。
            ``build_karte_report`` 旧名での import は ImportError になる。
"""


class TestBackwardCompatibleImports:
    """Verify old import paths still work (shim functionality, Phase 171 削除後)。"""

    def test_import_build_karte_json_string_from_builder(self):
        """Phase 231: canonical name in ``karte.builder`` is now ``build_karte_json_string``."""
        from katrain.core.reports.karte.builder import build_karte_json_string

        assert callable(build_karte_json_string)

    def test_import_build_karte_json_from_old_path(self):
        from katrain.core.reports.karte.json_export import build_karte_json

        assert callable(build_karte_json)

    def test_import_build_critical_3_prompt_from_old_path(self):
        from katrain.core.reports.karte.llm_prompt import build_critical_3_prompt

        assert callable(build_critical_3_prompt)

    def test_import_exceptions_from_old_path(self):
        from katrain.core.reports.karte.models import KarteGenerationError

        assert issubclass(KarteGenerationError, Exception)

    def test_import_constants_from_old_path(self):
        from katrain.core.reports.karte.models import (
            CRITICAL_3_PROMPT_TEMPLATE,
            KARTE_ERROR_CODE_GENERATION_FAILED,
            STYLE_CONFIDENCE_THRESHOLD,
        )

        assert isinstance(KARTE_ERROR_CODE_GENERATION_FAILED, str)
        assert isinstance(CRITICAL_3_PROMPT_TEMPLATE, str)
        assert isinstance(STYLE_CONFIDENCE_THRESHOLD, float)

    def test_import_helpers_from_old_path(self):
        from katrain.core.reports.karte.helpers import has_loss_data

        assert callable(has_loss_data)

    def test_leela_helpers_removed(self):
        """Phase 171: Leela 専用 helper は削除済み。
        Phase 232: ``karte_report`` 互換シム自体が削除されたので、
        旧モジュールからの import は ImportError になる。
        """
        import pytest

        with pytest.raises(ImportError):
            from katrain.core.reports.karte_report import format_loss_with_engine_suffix  # noqa: F401

        with pytest.raises(ImportError):
            from katrain.core.reports.karte_report import is_single_engine_snapshot  # noqa: F401

    def test_legacy_shim_removed(self):
        """Phase 232: ``katrain.core.reports.karte_report`` 互換シムは完全削除。

        ``build_karte_report`` 旧名での import は
        ``ImportError: No module named 'katrain.core.reports.karte_report'``
        になる。``build_karte_json_string`` 経由での import のみが有効。
        """
        import pytest

        with pytest.raises(ImportError):
            from katrain.core.reports.karte_report import build_karte_report  # noqa: F401

        with pytest.raises(ImportError):
            import katrain.core.reports.karte_report  # noqa: F401


class TestNewPackageImports:
    """Verify new package imports work."""

    def test_import_from_karte_package(self):
        from katrain.core.reports.karte import (
            KarteGenerationError,
            build_critical_3_prompt,
            build_karte_json,
            build_karte_json_string,
        )

        assert callable(build_karte_json_string)
        assert callable(build_karte_json)
        assert callable(build_critical_3_prompt)
        assert issubclass(KarteGenerationError, Exception)

    def test_import_karte_context(self):
        from katrain.core.reports.karte.sections.context import KarteContext

        assert KarteContext is not None


class TestNoCircularImports:
    """Verify no circular import issues - modules import independently.

    Note: These tests use direct module imports (not via karte/__init__.py)
    to verify that each module can be imported standalone.
    """

    def test_import_models_standalone(self):
        """models.py should import without triggering builder/sections."""
        # Direct import, bypassing karte/__init__.py
        import katrain.core.reports.karte.models as models

        assert hasattr(models, "KarteGenerationError")

    def test_import_helpers_standalone(self):
        """helpers.py should import without triggering builder/sections."""
        # Direct import, bypassing karte/__init__.py
        import katrain.core.reports.karte.helpers as helpers

        assert hasattr(helpers, "has_loss_data")

    def test_import_context_standalone(self):
        """context.py should import without triggering builder."""
        # Direct import, bypassing sections/__init__.py
        import katrain.core.reports.karte.sections.context as context

        assert hasattr(context, "KarteContext")
