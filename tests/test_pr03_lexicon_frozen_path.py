"""PR-03: regression tests for the lexicon PyInstaller fallback.

PR-03 fixes the distributed Windows binary by:

1. Adding ``docs/resources`` to ``spec/KaTrain.spec`` so the YAML is
   bundled inside the binary at ``sys._MEIPASS/docs/resources``.
2. Adding ``_resolve_default_lexicon_path()`` to ``katrain.core.coach.lexicon``
   which prefers the frozen path when ``sys._MEIPASS`` is set.

These tests verify the resolution order without touching the real
PyInstaller artefact: we synthesise a temporary ``_MEIPASS`` tree and
check the loader picks it up.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from katrain.core.coach import lexicon as lexicon_mod
from katrain.core.coach.lexicon import (
    DEFAULT_LEXICON_PATH,
    _resolve_default_lexicon_path,
    load_lexicon,
)


@pytest.fixture
def fake_meipass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create a fake ``sys._MEIPASS`` with a copy of the canonical YAML.

    Yields the temp root so the test can inspect or clean up afterwards.
    """
    if not DEFAULT_LEXICON_PATH.is_file():
        pytest.skip(f"Canonical YAML missing at {DEFAULT_LEXICON_PATH}; PR-03 tests cannot synthesise a fake _MEIPASS.")
    meipass_root = tmp_path / "fake_meipass"
    target_dir = meipass_root / "docs" / "resources"
    target_dir.mkdir(parents=True)
    shutil.copy(DEFAULT_LEXICON_PATH, target_dir / DEFAULT_LEXICON_PATH.name)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_root), raising=False)
    return meipass_root


@pytest.fixture
def broken_meipass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Synthesise ``sys._MEIPASS`` but with NO YAML inside.

    This lets us assert the loader falls back to the source-tree path
    when the frozen path is missing (e.g. the spec was misconfigured).
    """
    meipass_root = tmp_path / "empty_meipass"
    meipass_root.mkdir()
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_root), raising=False)
    return meipass_root


class TestResolveDefaultLexiconPath:
    def test_default_path_used_when_no_meipass(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        assert _resolve_default_lexicon_path() == DEFAULT_LEXICON_PATH

    def test_meipass_none_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ``_MEIPASS`` is only set when ``frozen`` is also set. A bare
        # ``None`` means ``getattr`` returns None and the loader skips.
        monkeypatch.setattr(sys, "_MEIPASS", None, raising=False)
        assert _resolve_default_lexicon_path() == DEFAULT_LEXICON_PATH

    def test_frozen_path_wins_when_present(self, fake_meipass: Path) -> None:
        resolved = _resolve_default_lexicon_path()
        assert resolved == fake_meipass / "docs" / "resources" / DEFAULT_LEXICON_PATH.name
        assert resolved.is_file()

    def test_missing_frozen_yaml_falls_back(self, broken_meipass: Path) -> None:
        # The frozen tree exists but does NOT contain the YAML — we
        # expect the source-tree path to be returned so the caller sees
        # the same FileNotFoundError it would have seen before PR-03
        # (preserving the existing error contract).
        assert _resolve_default_lexicon_path() == DEFAULT_LEXICON_PATH


class TestLoadLexiconHonoursFrozenPath:
    def test_load_picks_up_frozen_yaml(self, fake_meipass: Path) -> None:
        # Reset the cached loader so the new _MEIPASS takes effect.
        lexicon_mod._load_default_cached.cache_clear()
        bundle = load_lexicon()
        assert bundle.schema_version
        assert len(bundle.entries) > 0
        # Sanity: at least one known entry from the canonical YAML.
        assert bundle.entry_by_id.get("liberty") is not None

    def test_default_path_used_after_meipass_cleared(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simulate the dev workflow again after a fake frozen run.
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        lexicon_mod._load_default_cached.cache_clear()
        resolved = _resolve_default_lexicon_path()
        assert resolved == DEFAULT_LEXICON_PATH
        # load_lexicon should still work — the canonical YAML is on disk.
        bundle = load_lexicon()
        assert bundle.entries


class TestSpecFileExposesDocsResources:
    """Static check that the PyInstaller spec bundles the YAML directory."""

    def test_spec_includes_docs_resources(self) -> None:
        spec_path = Path(__file__).resolve().parent.parent / "spec" / "KaTrain.spec"
        text = spec_path.read_text(encoding="utf-8")
        # The PR-03 entry exposes docs/resources under that exact name.
        assert '"../docs/resources", "docs/resources"' in text, (
            "spec/KaTrain.spec must bundle docs/resources/ alongside the "
            "katrain/ tree so LLM Coach works in the distributed Windows "
            "binary (PR-03 ⑤)."
        )
