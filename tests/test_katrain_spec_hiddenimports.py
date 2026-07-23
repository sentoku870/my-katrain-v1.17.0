"""Regression tests for spec/KaTrain.spec hiddenimports.

Phase 284: After Phase 283 was merged to main, users reported
``ModuleNotFoundError: No module named 'kivy.uix.tabbedpanel'`` and
``kivy.uix.checkbox'`` when opening the MyKatrain settings popup or
batch analyze popup. Both widgets are part of standard Kivy 2.3.1, but
PyInstaller's static analyser never sees them because they are only
imported via Clock-scheduled lazy imports triggered after startup:

    Clock.schedule_once(
        lambda _dt: dispatch(self, message, *args, **kwargs), -1
    )
    ...
    def do_mykatrain_settings_popup(ctx):  # popup_commands.py:104
        from katrain.gui.features.settings_popup import ...

The Python module loader never reaches these imports during
PyInstaller freeze(), so the symbols are missing from the bundle.

Fix: explicitly list ``kivy.uix.tabbedpanel`` and ``kivy.uix.checkbox``
in ``hiddenimports`` in spec/KaTrain.spec.

These tests are source-static (no PyInstaller invocation, no Kivy
runtime) and run unconditionally on CI. They guard against:
- accidental removal of the Phase 284 hiddenimports entries
- import name typos
- drift between the spec and the actual import sites in the codebase
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = REPO_ROOT / "spec" / "KaTrain.spec"
SETTINGS_POPUP = REPO_ROOT / "katrain" / "gui" / "features" / "settings_popup.py"
BATCH_UI = REPO_ROOT / "katrain" / "gui" / "features" / "batch_ui.py"


class TestKaTrainSpecHiddenImports:
    """Phase 284 regression guard: spec must declare legacy widget imports."""

    def _read_spec(self) -> str:
        return SPEC_FILE.read_text(encoding="utf-8")

    def _extract_hiddenimports_extend_blocks(self, spec_source: str) -> list[str]:
        """Return the bodies (as strings) of every ``hiddenimports.extend([ ... ])``
        block in the spec. The spec adds to the list returned by
        ``kivy_deps.get('hiddenimports', [])`` via several ``extend()`` calls;
        we want to verify the modules are added somewhere.
        """
        return re.findall(
            r"hiddenimports\.extend\(\s*\[(.*?)\]\s*\)",
            spec_source,
            re.DOTALL,
        )

    def test_phase_284_comment_present(self):
        """The spec must carry a comment explaining the Phase 284 rationale so
        future contributors don't think the legacy widget list is stray.
        """
        spec_source = self._read_spec()
        assert "Phase 284" in spec_source, (
            "spec/KaTrain.spec must carry a `Phase 284` comment explaining why "
            "`kivy.uix.tabbedpanel` and `kivy.uix.checkbox` are in hiddenimports. "
            "Without this explanation a future refactor is likely to remove the "
            "entries and silently re-break frozen builds."
        )

    def test_phase_284_extend_block_exists(self):
        """There must be a dedicated hiddenimports.extend block for Phase 284
        (rather than mixing into an existing block, which can be overlooked
        in PR reviews)."""
        blocks = self._extract_hiddenimports_extend_blocks(self._read_spec())
        phase284_blocks = [b for b in blocks if "kivy.uix.tabbedpanel" in b and "kivy.uix.checkbox" in b]
        assert phase284_blocks, (
            "spec/KaTrain.spec must have a hiddenimports.extend([...]) block "
            "that lists both `kivy.uix.tabbedpanel` and `kivy.uix.checkbox` "
            "(Phase 284 fix). Found the following blocks: "
            f"{[b.strip()[:50] for b in blocks]}"
        )

    def test_tabbedpanel_in_hiddenimports(self):
        """``kivy.uix.tabbedpanel`` must be listed as a hidden import so the
        settings popup (which lazily imports it) does not crash on first open.
        """
        blocks = self._extract_hiddenimports_extend_blocks(self._read_spec())
        joined = "\n".join(blocks)
        assert '"kivy.uix.tabbedpanel"' in joined or "'kivy.uix.tabbedpanel'" in joined, (
            "spec/KaTrain.spec must declare `kivy.uix.tabbedpanel` as a "
            "hiddenimports entry. PyInstaller's static analyser never sees "
            "the lazy import inside popup_commands.do_mykatrain_settings_popup."
        )

    def test_checkbox_in_hiddenimports(self):
        """``kivy.uix.checkbox`` must be listed as a hidden import so the batch
        analyze popup (which lazily imports it) does not crash on first open.
        """
        blocks = self._extract_hiddenimports_extend_blocks(self._read_spec())
        joined = "\n".join(blocks)
        assert '"kivy.uix.checkbox"' in joined or "'kivy.uix.checkbox'" in joined, (
            "spec/KaTrain.spec must declare `kivy.uix.checkbox` as a "
            "hiddenimports entry. PyInstaller's static analyser never sees "
            "the lazy import inside batch_analysis_controller.open_batch_analyze_popup."
        )

    def test_no_duplicate_kivy_uix_entries(self):
        """Regression guard: each legacy module must appear exactly once across
        all hiddenimports.extend blocks (duplicates generate PyInstaller warnings).
        """
        spec_source = self._read_spec()
        # Strip comments first — module names should only be counted when they
        # actually appear inside a hiddenimports.extend(...) call.
        blocks = self._extract_hiddenimports_extend_blocks(spec_source)
        joined = "\n".join(blocks)
        for mod in ("kivy.uix.tabbedpanel", "kivy.uix.checkbox"):
            count = len(re.findall(rf"['\"]{re.escape(mod)}['\"]", joined))
            assert count == 1, (
                f"{mod} appears {count} times across hiddenimports.extend "
                f"blocks in spec/KaTrain.spec; expected exactly 1."
            )


class TestImportSitesReferenceSpecEntries:
    """Source-static verification: the modules declared in the spec are
    actually imported somewhere in the codebase, so the spec entry is not
    drift / typo."""

    def test_tabbedpanel_imported_in_settings_popup(self):
        src = SETTINGS_POPUP.read_text(encoding="utf-8")
        assert "from kivy.uix.tabbedpanel import" in src, (
            "settings_popup.py must still import from kivy.uix.tabbedpanel; "
            "if you migrate this file to KivyMD alternatives, also update "
            "spec/KaTrain.spec to drop the corresponding hiddenimports entry."
        )

    def test_checkbox_imported_in_batch_ui(self):
        src = BATCH_UI.read_text(encoding="utf-8")
        assert "from kivy.uix.checkbox import" in src, (
            "batch_ui.py must still import from kivy.uix.checkbox; "
            "if you migrate this file to KivyMD alternatives, also update "
            "spec/KaTrain.spec to drop the corresponding hiddenimports entry."
        )

    def test_checkbox_imported_everywhere_in_source(self):
        """All kivy.uix.checkbox import sites in the codebase remain
        consistent (used as ground truth to detect subtle regressions).

        Walks ``katrain/`` via ``Path.rglob`` and inspects file
        contents with a plain ``str`` search; previously this relied
        on ``grep -rln``, which is not available on stock Windows.
        """
        files: list[str] = []
        needle = "from kivy.uix.checkbox import"
        for py_file in REPO_ROOT.joinpath("katrain").rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if needle in text:
                files.append(str(py_file.relative_to(REPO_ROOT)))

        assert files, "Expected at least one file to import kivy.uix.checkbox; rglob returned none."
        assert any("batch_ui.py" in f for f in files), (
            f"batch_ui.py should be among the files importing kivy.uix.checkbox; found: {files}"
        )
