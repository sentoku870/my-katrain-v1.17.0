"""Regression tests for Phase H-3 short-hash migration.

Phase H-3 migrated 4 non-cryptographic ``hashlib.md5`` call sites
(filename uniqueness, batch path hash, batch visit jitter, single
game id) to a centralised :func:`katrain.common.short_hash.short_hash`
helper built on top of :mod:`hashlib.blake2b`. The MD5 use cases are
purely for uniqueness; blake2b is faster on modern CPUs and ships in
the stdlib.

This test pins:
- ``short_hash`` is deterministic and length-bounded
- The migrated call sites use the helper
- The old raw ``hashlib.md5(...)[:6]`` pattern no longer appears
"""

from __future__ import annotations

import inspect

import pytest

from katrain.common.short_hash import short_hash


class TestShortHash:
    def test_deterministic(self) -> None:
        """Same input must always produce the same output."""
        assert short_hash("foo/bar.sgf") == short_hash("foo/bar.sgf")

    def test_different_inputs_differ(self) -> None:
        """Different inputs must produce different outputs (in the
        small sample we test)."""
        assert short_hash("a") != short_hash("b")

    @pytest.mark.parametrize("n", [1, 2, 3, 4, 6, 8, 12, 16, 64])
    def test_output_length(self, n: int) -> None:
        assert len(short_hash("test/path", n)) == n

    def test_output_is_hex(self) -> None:
        for c in short_hash("test/path", 12):
            assert c in "0123456789abcdef"

    @pytest.mark.parametrize("n", [0, -1, 65, 100])
    def test_invalid_length_rejected(self, n: int) -> None:
        with pytest.raises(ValueError, match="n_chars must be in 1\\.\\.64"):
            short_hash("test", n)

    def test_compatible_with_pre_md5_call_site_lengths(self) -> None:
        """The pre-Phase-H-3 call sites all used ``.hexdigest()[:6]``
        or ``[:8]`` or ``[:12]``. The helper supports these lengths."""
        for n in (6, 8, 12):
            assert len(short_hash("x", n)) == n

    def test_backward_compatible_outputs(self) -> None:
        """The blake2b output is not required to match the old MD5
        output byte-for-byte (the migration is a behaviour-equivalent
        change, not a byte-identical one). Verify the new helper is
        deterministic and that the inputs the old code hashed still
        produce stable outputs."""
        # Two calls in a row must agree.
        assert short_hash("tests/data/pro.sgf") == short_hash("tests/data/pro.sgf")
        assert short_hash("20260628-153000game_X.sgf") == short_hash("20260628-153000game_X.sgf")


class TestCallSitesMigrated:
    """Source-level checks: the migrated sites must use short_hash and
    must NOT contain the old ``hashlib.md5(...)[:6]`` pattern any more."""

    @pytest.mark.parametrize(
        "module_path",
        [
            "katrain.core.batch.filenames",
            "katrain.core.batch.orchestration",
            "katrain.core.game.base",
            "katrain.core.reports.karte.json_export",
            "katrain.core.reports.summary_json_export",
        ],
    )
    def test_module_uses_short_hash(self, module_path: str) -> None:
        import importlib
        import re

        module = importlib.import_module(module_path)
        source = inspect.getsource(module)
        # The module must import short_hash. Phase 232 reformatted the
        # import to multi-line (to attach an F401 suppression comment),
        # so we now match the import with a regex that allows newlines
        # between the ``from ... import`` clause and the name.
        assert re.search(
            r"from\s+katrain\.common\.short_hash\s+import\s+.*\bshort_hash\b",
            source,
            re.DOTALL,
        ), f"{module_path} does not import short_hash; Phase H-3 migration incomplete."
        # ...and must not contain the old ``hashlib.md5(...)`` pattern.
        assert "hashlib.md5" not in source, f"{module_path} still uses hashlib.md5; Phase H-3 migration incomplete."

    def test_visits_module_uses_blake2b_directly(self) -> None:
        """The visits module needs raw 32-bit int output (not hex), so
        it uses blake2b directly without going through ``short_hash``.
        It must NOT use MD5.
        """
        import importlib

        module = importlib.import_module("katrain.core.batch.visits")
        source = inspect.getsource(module)
        assert "hashlib.md5" not in source, (
            "katrain.core.batch.visits still uses hashlib.md5; Phase H-3 migration incomplete."
        )
        assert "blake2b" in source, "katrain.core.batch.visits should use blake2b after Phase H-3."

    def test_short_hash_centralised(self) -> None:
        """A single shared module defines the helper; no per-site
        re-implementations.

        Walks ``katrain/`` from the repository root using
        ``Path.rglob`` so the test does not depend on a Unix
        ``grep`` binary (the project supports Windows).
        """
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        count = 0
        canonical_path: str | None = None
        for py_file in repo_root.joinpath("katrain").rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "def short_hash" not in text:
                continue
            count += 1
            if canonical_path is None and py_file.name == "short_hash.py" and "common" in py_file.parts:
                canonical_path = str(py_file.relative_to(repo_root))

        assert count == 1, f"Expected exactly 1 'def short_hash' definition, found {count}."
        # Use forward slashes for cross-platform stability (Windows returns backslashes).
        assert canonical_path is not None and canonical_path.replace("\\", "/") == "katrain/common/short_hash.py", (
            f"The canonical helper must live at katrain/common/short_hash.py, found {canonical_path!r}."
        )
