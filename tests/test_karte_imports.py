"""Import compatibility tests for Phase 72 karte package split."""

import subprocess
import sys
import textwrap


class TestBackwardCompatibleImports:
    """Verify old import paths still work (shim functionality)."""

    def test_import_build_karte_report_from_old_path(self):
        from katrain.core.reports.karte_report import build_karte_report

        assert callable(build_karte_report)

    def test_import_build_karte_json_from_old_path(self):
        from katrain.core.reports.karte_report import build_karte_json

        assert callable(build_karte_json)

    def test_import_build_critical_3_prompt_from_old_path(self):
        from katrain.core.reports.karte_report import build_critical_3_prompt

        assert callable(build_critical_3_prompt)

    def test_import_exceptions_from_old_path(self):
        from katrain.core.reports.karte_report import (
            KarteGenerationError,
            MixedEngineSnapshotError,
        )

        # Both should be Exception subclasses
        assert issubclass(KarteGenerationError, Exception)
        assert issubclass(MixedEngineSnapshotError, Exception)
        # MixedEngineSnapshotError is specifically a ValueError subclass
        assert issubclass(MixedEngineSnapshotError, ValueError)

    def test_import_constants_from_old_path(self):
        from katrain.core.reports.karte_report import (
            CRITICAL_3_PROMPT_TEMPLATE,
            KARTE_ERROR_CODE_GENERATION_FAILED,
            KARTE_ERROR_CODE_MIXED_ENGINE,
            STYLE_CONFIDENCE_THRESHOLD,
        )

        assert isinstance(KARTE_ERROR_CODE_MIXED_ENGINE, str)
        assert isinstance(KARTE_ERROR_CODE_GENERATION_FAILED, str)
        assert isinstance(CRITICAL_3_PROMPT_TEMPLATE, str)
        assert isinstance(STYLE_CONFIDENCE_THRESHOLD, float)

    def test_import_helpers_from_old_path(self):
        from katrain.core.reports.karte_report import (
            format_loss_with_engine_suffix,
            has_loss_data,
            is_single_engine_snapshot,
        )

        assert callable(format_loss_with_engine_suffix)
        assert callable(has_loss_data)
        assert callable(is_single_engine_snapshot)


class TestNewPackageImports:
    """Verify new package imports work."""

    def test_import_from_karte_package(self):
        from katrain.core.reports.karte import (
            KarteGenerationError,
            MixedEngineSnapshotError,
            build_critical_3_prompt,
            build_karte_json,
            build_karte_report,
        )

        assert callable(build_karte_report)
        assert callable(build_karte_json)
        assert callable(build_critical_3_prompt)
        assert issubclass(KarteGenerationError, Exception)
        assert issubclass(MixedEngineSnapshotError, ValueError)

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
        assert hasattr(models, "MixedEngineSnapshotError")

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

    def test_karte_package_import_does_not_eagerly_load_builder(self):
        """Importing karte package directly should NOT eagerly import builder/sections.

        Guarantee 1: `import katrain.core.reports.karte` does not load builder.
        """
        code = textwrap.dedent(
            """
            import sys

            # Import karte package directly
            from katrain.core.reports import karte

            # Verify exceptions/constants are available (direct import in karte/__init__.py)
            assert hasattr(karte, 'KarteGenerationError')
            assert hasattr(karte, 'MixedEngineSnapshotError')
            assert hasattr(karte, 'STYLE_CONFIDENCE_THRESHOLD')

            # Verify callable APIs are available (lazy wrappers)
            assert hasattr(karte, 'build_karte_report')
            assert callable(karte.build_karte_report)

            # Verify builder was NOT eagerly loaded
            builder_module = "katrain.core.reports.karte.builder"
            sections_modules = [
                "katrain.core.reports.karte.sections.summary",
                "katrain.core.reports.karte.sections.important_moves",
                "katrain.core.reports.karte.sections.diagnosis",
                "katrain.core.reports.karte.sections.metadata",
            ]

            assert builder_module not in sys.modules, f"{builder_module} was eagerly loaded"
            for mod in sections_modules:
                assert mod not in sys.modules, f"{mod} was eagerly loaded"

            print("PASS: karte package lazy import verified")
            """
        ).strip()

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Lazy import check failed:\n{result.stderr}"
        assert "PASS" in result.stdout

    def test_reports_package_import_does_not_eagerly_load_builder(self):
        """Importing reports package should NOT eagerly import builder/sections.

        Guarantee 2: `import katrain.core.reports` does not load builder.
        This depends on reports/__init__.py importing from karte (lazy wrappers).
        """
        code = textwrap.dedent(
            """
            import sys

            # Import the parent package (katrain.core.reports)
            from katrain.core import reports

            # Verify karte-related symbols are available via reports
            assert hasattr(reports, 'KarteGenerationError')
            assert hasattr(reports, 'build_karte_report')

            # Verify builder was NOT eagerly loaded
            builder_module = "katrain.core.reports.karte.builder"
            sections_modules = [
                "katrain.core.reports.karte.sections.summary",
                "katrain.core.reports.karte.sections.important_moves",
                "katrain.core.reports.karte.sections.diagnosis",
                "katrain.core.reports.karte.sections.metadata",
            ]

            assert builder_module not in sys.modules, f"{builder_module} was eagerly loaded"
            for mod in sections_modules:
                assert mod not in sys.modules, f"{mod} was eagerly loaded"

            print("PASS: reports package lazy import verified")
            """
        ).strip()

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Lazy import check failed:\n{result.stderr}"
        assert "PASS" in result.stdout
