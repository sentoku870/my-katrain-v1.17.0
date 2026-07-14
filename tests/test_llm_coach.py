"""Unit tests for :mod:`katrain.gui.features.llm_coach`.

Phase 225 logic-layer tests. The GUI popup itself is exercised in
``tests/test_llm_coach_popup.py``. These tests focus on the three
wrappers (``build_llm_prompt`` / ``validate_llm_response`` /
``find_latest_karte``) which intentionally have **no Kivy import** so
they run in CI without the heavy Kivy init.

The mock strategy is:

* ``core.coach.cli.build_prompt`` is patched so the tests don't have to
  construct a full Karte JSON. We only verify the wrapper reads the file,
  passes through ``rank`` / ``avg_points_lost`` and forwards the
  resulting Markdown.
* ``core.coach.llm_validator.validate_llm_output`` is patched to return
  a synthetic :class:`ValidationReport`. The wrapper test then verifies
  the Markdown rendering (i18n labels, issue rendering, truncation).
* :func:`find_latest_karte` is exercised against a temporary directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.coach import cli as coach_cli
from katrain.core.coach import llm_validator as coach_validator
from katrain.gui.features import llm_coach


# --- Helpers -----------------------------------------------------------


@dataclass
class _FakePrompt:
    """Mimics :class:`katrain.core.coach.prompt_builder.LlmPrompt`."""

    full_markdown: str
    referenced_symptom_ids: tuple[str, ...] = ()
    config: Any = None


@dataclass
class _FakeIssue:
    severity: Any
    kind: str
    message: str


class _FakeSeverity:
    def __init__(self, value: str) -> None:
        self.value = value


@dataclass
class _FakeReport:
    """Mimics :class:`katrain.core.coach.llm_validator.ValidationReport`."""

    llm_text: str
    issues: tuple[Any, ...] = ()
    referenced_symptom_ids: tuple[str, ...] = ()
    referenced_move_numbers: tuple[int, ...] = ()
    referenced_points_lost: tuple[float, ...] = ()
    referenced_lexicon_ids: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.value == "high")

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.value == "medium")

    @property
    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity.value == "low")

    def summary_line(self) -> str:
        if self.is_clean:
            return "✅ Clean"
        return "⚠️ Issues"


def _write_karte(tmp_path: Path, name: str = "karte_sample.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"meta": {}, "summary": {}}), encoding="utf-8")
    return path


def _fake_ctx(tmp_path: Path) -> Any:
    """A minimal FeatureContext mock with a log() no-op."""
    ctx = MagicMock()
    ctx.config.return_value = {"karte_output_directory": str(tmp_path)}
    return ctx


# --- build_llm_prompt --------------------------------------------------


class TestBuildLlmPrompt:
    def test_returns_full_markdown_on_success(self, tmp_path: Path) -> None:
        path = _write_karte(tmp_path)
        fake_prompt = _FakePrompt(full_markdown="# PROMPT\n")
        with patch.object(coach_cli, "build_prompt", return_value=fake_prompt):
            ok, content = llm_coach.build_llm_prompt(None, path)
        assert ok is True
        assert content == "# PROMPT\n"

    def test_forwards_rank_and_avg_points_lost(self, tmp_path: Path) -> None:
        path = _write_karte(tmp_path)
        fake_prompt = _FakePrompt(full_markdown="x")
        with patch.object(coach_cli, "build_prompt", return_value=fake_prompt) as spy:
            llm_coach.build_llm_prompt(None, path, rank="5k", avg_points_lost=-2.5)
        kwargs = spy.call_args.kwargs
        assert kwargs["rank"] == "5k"
        assert kwargs["avg_points_lost"] == -2.5

    def test_missing_file_returns_user_facing_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.json"
        ctx = _fake_ctx(tmp_path)
        ok, content = llm_coach.build_llm_prompt(ctx, missing)
        assert ok is False
        # Message either contains the path or the i18n key (when .po is not loaded)
        assert "nope.json" in content or "not found" in content.lower() or "file-not-found" in content
        ctx.log.assert_called_once()

    def test_invalid_json_returns_user_facing_error(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        ctx = _fake_ctx(tmp_path)
        ok, content = llm_coach.build_llm_prompt(ctx, path)
        assert ok is False
        # The error path-key "invalid-karte" must appear if translations
        # aren't loaded; otherwise the localised error includes "JSON" or "invalid".
        assert (
            "invalid-karte" in content
            or "invalid" in content.lower()
            or "JSON" in content
        )
        ctx.log.assert_called_once()

    def test_none_ctx_does_not_raise(self, tmp_path: Path) -> None:
        path = _write_karte(tmp_path)
        fake_prompt = _FakePrompt(full_markdown="ok")
        with patch.object(coach_cli, "build_prompt", return_value=fake_prompt):
            ok, _ = llm_coach.build_llm_prompt(None, path)
        assert ok is True


# --- validate_llm_response --------------------------------------------


class TestValidateLlmResponse:
    def _patch_pipeline(self, fake_report: _FakeReport) -> Any:
        return (
            patch.object(coach_cli, "build_prompt", return_value=_FakePrompt("ignored")),
            patch.object(coach_validator, "validate_llm_output", return_value=fake_report),
        )

    def test_clean_report_returns_markdown(self, tmp_path: Path) -> None:
        path = _write_karte(tmp_path)
        report = _FakeReport(llm_text="clean")
        p1, p2 = self._patch_pipeline(report)
        with p1, p2:
            is_clean, markdown = llm_coach.validate_llm_response(None, path, "clean")
        assert is_clean is True
        assert "Clean" in markdown
        assert "HIGH" in markdown and "MEDIUM" in markdown and "LOW" in markdown

    def test_dirty_report_renders_issue_lines(self, tmp_path: Path) -> None:
        path = _write_karte(tmp_path)
        report = _FakeReport(
            llm_text="x",
            issues=(
                _FakeIssue(_FakeSeverity("high"), "UNKNOWN_SYMPTOM", "hallucinated-id"),
                _FakeIssue(_FakeSeverity("low"), "STYLE", "minor phrasing"),
            ),
            referenced_symptom_ids=("miss_a", "miss_b"),
            referenced_move_numbers=(42, 50),
            referenced_points_lost=(-2.5,),
            referenced_lexicon_ids=("lex_1",),
        )
        p1, p2 = self._patch_pipeline(report)
        with p1, p2:
            is_clean, markdown = llm_coach.validate_llm_response(None, path, "x")
        assert is_clean is False
        assert "miss_a" in markdown and "miss_b" in markdown
        assert "42" in markdown and "50" in markdown
        assert "-2.5" in markdown
        assert "lex_1" in markdown
        assert "[HIGH]" in markdown
        assert "[LOW]" in markdown

    def test_missing_karte_returns_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.json"
        ok, content = llm_coach.validate_llm_response(None, missing, "x")
        assert ok is False
        assert (
            "missing.json" in content
            or "not found" in content.lower()
            or "file-not-found" in content
        )

    def test_invalid_json_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("not json", encoding="utf-8")
        ok, content = llm_coach.validate_llm_response(None, path, "x")
        assert ok is False

    def test_oversized_report_is_truncated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _write_karte(tmp_path)
        long_markdown = "x" * (llm_coach._MAX_REPORT_CHARS + 500)
        report = _FakeReport(llm_text="")
        with patch.object(coach_cli, "build_prompt", return_value=_FakePrompt("ignored")), \
             patch.object(coach_validator, "validate_llm_output", return_value=report), \
             patch.object(llm_coach, "_render_validation_report", return_value=long_markdown):
            _, markdown = llm_coach.validate_llm_response(None, path, "")
        assert len(markdown) <= llm_coach._MAX_REPORT_CHARS + 200


# --- _render_validation_report ----------------------------------------


class TestRenderValidationReport:
    def test_includes_status_and_counts(self) -> None:
        report = _FakeReport(llm_text="x")
        md = llm_coach._render_validation_report(report)
        assert "Clean" in md
        assert "HIGH" in md
        assert "MEDIUM" in md
        assert "LOW" in md

    def test_includes_issues_when_dirty(self) -> None:
        report = _FakeReport(
            llm_text="x",
            issues=(_FakeIssue(_FakeSeverity("medium"), "STYLE", "msg"),),
        )
        md = llm_coach._render_validation_report(report)
        assert "[MEDIUM]" in md
        assert "STYLE" in md
        assert "msg" in md


# --- find_latest_karte -------------------------------------------------


class TestFindLatestKarte:
    def test_returns_none_when_output_dir_missing(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.config.return_value = {"karte_output_directory": str(tmp_path / "no-such-dir")}
        assert llm_coach.find_latest_karte(ctx) is None

    def test_returns_latest_karte_json(self, tmp_path: Path) -> None:
        (tmp_path / "karte_old.json").write_text("{}", encoding="utf-8")
        latest = tmp_path / "karte_new.json"
        latest.write_text("{}", encoding="utf-8")
        # mtime ordering: force latest to be newer
        import os

        os.utime(tmp_path / "karte_old.json", (1000, 1000))
        os.utime(latest, (2000, 2000))

        ctx = _fake_ctx(tmp_path)
        result = llm_coach.find_latest_karte(ctx)
        assert result is not None
        assert result.name == "karte_new.json"

    def test_skips_summary_reports(self, tmp_path: Path) -> None:
        (tmp_path / "summary_x.json").write_text("{}", encoding="utf-8")
        (tmp_path / "karte_y.json").write_text("{}", encoding="utf-8")
        ctx = _fake_ctx(tmp_path)
        result = llm_coach.find_latest_karte(ctx)
        assert result is not None
        assert result.name.startswith("karte_")

    def test_returns_none_when_no_reports(self, tmp_path: Path) -> None:
        ctx = _fake_ctx(tmp_path)
        assert llm_coach.find_latest_karte(ctx) is None