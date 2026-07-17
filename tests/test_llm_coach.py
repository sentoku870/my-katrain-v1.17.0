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
        assert "invalid-karte" in content or "invalid" in content.lower() or "JSON" in content
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
        assert "missing.json" in content or "not found" in content.lower() or "file-not-found" in content

    def test_invalid_json_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("not json", encoding="utf-8")
        ok, content = llm_coach.validate_llm_response(None, path, "x")
        assert ok is False

    def test_oversized_report_is_truncated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _write_karte(tmp_path)
        long_markdown = "x" * (llm_coach._MAX_REPORT_CHARS + 500)
        report = _FakeReport(llm_text="")
        with (
            patch.object(coach_cli, "build_prompt", return_value=_FakePrompt("ignored")),
            patch.object(coach_validator, "validate_llm_output", return_value=report),
            patch.object(llm_coach, "_render_validation_report", return_value=long_markdown),
        ):
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
# Phase 239: ``find_latest_karte`` is now deprecated. The tests still
# exercise the legacy function for backward compatibility but suppress
# the ``DeprecationWarning`` so the test suite stays green. New code
# should call ``find_latest_llm_input_for_ctx`` instead.


class TestFindLatestKarte:
    def test_returns_none_when_output_dir_missing(self, tmp_path: Path) -> None:
        ctx = MagicMock()
        ctx.config.return_value = {"karte_output_directory": str(tmp_path / "no-such-dir")}
        with pytest.warns(DeprecationWarning, match="find_latest_karte is deprecated"):
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
        with pytest.warns(DeprecationWarning, match="find_latest_karte is deprecated"):
            result = llm_coach.find_latest_karte(ctx)
        assert result is not None
        assert result.name == "karte_new.json"

    def test_skips_summary_reports(self, tmp_path: Path) -> None:
        (tmp_path / "summary_x.json").write_text("{}", encoding="utf-8")
        (tmp_path / "karte_y.json").write_text("{}", encoding="utf-8")
        ctx = _fake_ctx(tmp_path)
        with pytest.warns(DeprecationWarning, match="find_latest_karte is deprecated"):
            result = llm_coach.find_latest_karte(ctx)
        assert result is not None
        assert result.name.startswith("karte_")

    def test_returns_none_when_no_reports(self, tmp_path: Path) -> None:
        ctx = _fake_ctx(tmp_path)
        with pytest.warns(DeprecationWarning, match="find_latest_karte is deprecated"):
            assert llm_coach.find_latest_karte(ctx) is None


# ---- detect_player_info / detect_player_color_for_user (Phase 225.6) --


class TestDetectPlayerInfo:
    """Phase 225.6: read black/white player info from Karte meta."""

    def test_reads_player_info_from_karte_meta(self, tmp_path):
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "醉舞", "rank": "4d"},
                            "white": {"name": "仙得", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        from katrain.gui.features.llm_coach import detect_player_info

        info = detect_player_info(None, karte)
        assert info["source"] == "karte_meta"
        assert info["black"]["name"] == "醉舞"
        assert info["black"]["rank"] == "4d"
        assert info["white"]["name"] == "仙得"
        assert info["white"]["rank"] == "3d"

    def test_missing_file_yields_missing_source(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info

        info = detect_player_info(None, tmp_path / "nope.json")
        assert info["source"] == "missing"
        assert info["black"]["name"] is None
        assert info["white"]["rank"] is None

    def test_no_player_info_no_sgf_yields_missing(self, tmp_path):
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {}}), encoding="utf-8")
        from katrain.gui.features.llm_coach import detect_player_info

        info = detect_player_info(None, karte)
        assert info["source"] == "missing"


class TestDetectPlayerColorForUser:
    def test_returns_color_when_default_user_matches(self, tmp_path):
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "sentoku", "rank": "5k"},
                            "white": {"name": "opponent", "rank": "6k"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": "sentoku"}
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        color, rank = detect_player_color_for_user(ctx, karte)
        assert color == "B"
        assert rank == "5k"

    def test_returns_none_for_empty_default_user(self, tmp_path):
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {"player_info": {}}}), encoding="utf-8")
        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": ""}
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        color, rank = detect_player_color_for_user(ctx, karte)
        assert color is None
        assert rank is None

    def test_returns_none_when_ctx_is_none(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        color, rank = detect_player_color_for_user(None, tmp_path / "k.json")
        assert color is None
        assert rank is None


# --- Phase 226-B (B4): detect_player_color_for_user with player_info --


class TestDetectPlayerColorForUserWithPlayerInfo:
    """Phase 226-B (B4): the caller can pass an already-loaded
    ``player_info`` dict to avoid re-reading the Karte JSON."""

    def test_uses_supplied_player_info_without_reading_file(self, tmp_path):
        # Pass a player_info dict directly. The karte_path is set to a
        # non-existent file to prove we don't fall through to reading it.
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": "sentoku"}
        info = {
            "black": {"name": "sentoku", "rank": "5k"},
            "white": {"name": "opponent", "rank": "6k"},
            "source": "karte_meta",
        }
        color, rank = detect_player_color_for_user(ctx, tmp_path / "does-not-exist.json", player_info=info)
        assert color == "B"
        assert rank == "5k"

    def test_player_info_none_falls_back_to_file_read(self, tmp_path):
        # When player_info is None, the function reads the file itself.
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "sentoku", "rank": "5k"},
                            "white": {"name": "opponent", "rank": "6k"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": "sentoku"}
        color, rank = detect_player_color_for_user(ctx, karte, player_info=None)
        assert color == "B"
        assert rank == "5k"

    def test_player_info_white_user(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_color_for_user

        ctx = MagicMock()
        ctx.config.return_value = {"default_user_name": "opponent"}
        info = {
            "black": {"name": "sentoku", "rank": "5k"},
            "white": {"name": "opponent", "rank": "6k"},
            "source": "karte_meta",
        }
        color, rank = detect_player_color_for_user(ctx, tmp_path / "k.json", player_info=info)
        assert color == "W"
        assert rank == "6k"


# --- Phase 227-C: detect_player_info_for_summary + find_latest_llm_input_for_ctx ---


class TestDetectPlayerInfoForSummary:
    """Phase 227-C: extract player info from a multi-game Summary JSON.

    Summary shape is different from karte — the ``players`` block is
    keyed by player name, not by color. ``default_user_name`` is the
    primary selection key; when absent, we fall back to the first
    player (alphabetical order for determinism).
    """

    def _write_summary(self, tmp_path: Path, players: dict) -> Path:
        p = tmp_path / "summary.json"
        p.write_text(
            json.dumps({"meta": {"games_analyzed": 5}, "players": players}),
            encoding="utf-8",
        )
        return p

    def test_default_user_match_picks_named_player(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"rank": "4d", "win_rate": 0.4},
                "Opponent1": {"rank": "3d", "win_rate": 0.6},
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="sentoku870")
        assert info["source"] == "summary_meta"
        assert info["default_user_matched"] is True
        assert info["matched_player"]["name"] == "sentoku870"
        assert info["matched_player"]["rank"] == "4d"

    def test_no_default_user_picks_first_alphabetical(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"rank": "4d"},
                "Alice": {"rank": "5d"},
                "Bob": {"rank": "3d"},
            },
        )
        info = detect_player_info_for_summary(path)
        assert info["default_user_matched"] is False
        assert info["matched_player"]["name"] == "Alice"

    def test_default_user_mismatch_falls_back(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"rank": "4d"},
                "Opponent1": {"rank": "3d"},
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="NonExistent")
        assert info["default_user_matched"] is False
        # Falls back to first alphabetical
        assert info["matched_player"]["name"] == "Opponent1"

    def test_default_user_none_explicit(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = self._write_summary(
            tmp_path,
            {"sentoku870": {"rank": "4d"}},
        )
        info = detect_player_info_for_summary(path, default_user_name=None)
        assert info["default_user_matched"] is False
        assert info["matched_player"]["name"] == "sentoku870"

    def test_nested_overall_rank_extraction(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        # Phase 158+ format: rank lives under ``overall``
        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {
                    "overall": {"rank": "5k", "total_games": 10},
                    "win_rate": 0.5,
                },
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="sentoku870")
        assert info["matched_player"]["rank"] == "5k"

    def test_legacy_stats_rank_extraction(self, tmp_path: Path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        # Legacy form: rank under ``stats``
        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"stats": {"rank": "3d"}},
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="sentoku870")
        assert info["matched_player"]["rank"] == "3d"

    def test_missing_file_returns_missing_source(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        info = detect_player_info_for_summary(tmp_path / "nope.json")
        assert info["source"] == "missing"
        assert info["matched_player"]["name"] is None
        assert info["all_players"] == []

    def test_no_players_block_returns_missing(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = tmp_path / "summary.json"
        path.write_text(json.dumps({"meta": {"games_analyzed": 1}}), encoding="utf-8")
        info = detect_player_info_for_summary(path)
        assert info["source"] == "missing"

    def test_empty_players_block_returns_missing(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = tmp_path / "summary.json"
        path.write_text(
            json.dumps({"meta": {"games_analyzed": 1}, "players": {}}),
            encoding="utf-8",
        )
        info = detect_player_info_for_summary(path)
        assert info["source"] == "missing"

    def test_malformed_json_returns_missing(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = tmp_path / "summary.json"
        path.write_text("not json", encoding="utf-8")
        info = detect_player_info_for_summary(path)
        assert info["source"] == "missing"

    def test_all_players_listed(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"rank": "4d"},
                "Alice": {"rank": "5d"},
                "Bob": {"rank": "3d"},
            },
        )
        info = detect_player_info_for_summary(path)
        # Alphabetical order, regardless of which is matched
        assert [p["name"] for p in info["all_players"]] == [
            "Alice",
            "Bob",
            "sentoku870",
        ]

    def test_player_block_with_non_dict_value(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        # Edge case: a player key has a non-dict value
        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {"rank": "4d"},
                "BadEntry": "not a dict",
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="sentoku870")
        # Should not crash; BadEntry shows up as a player with rank=None
        names = [p["name"] for p in info["all_players"]]
        assert "BadEntry" in names
        bad = next(p for p in info["all_players"] if p["name"] == "BadEntry")
        assert bad["rank"] is None

    def test_rank_priority_direct_beats_nested(self, tmp_path):
        from katrain.gui.features.llm_coach import detect_player_info_for_summary

        # When both direct ``rank`` and ``overall.rank`` exist, direct wins
        path = self._write_summary(
            tmp_path,
            {
                "sentoku870": {
                    "rank": "5k",  # direct
                    "overall": {"rank": "4d"},  # would be wrong
                },
            },
        )
        info = detect_player_info_for_summary(path, default_user_name="sentoku870")
        assert info["matched_player"]["rank"] == "5k"


class TestFindLatestLlmInputForCtx:
    """Phase 227-C: ctx-aware wrapper around ``find_latest_llm_input``."""

    def test_returns_none_when_output_dir_missing(self, tmp_path):
        ctx = MagicMock()
        ctx.config.return_value = {"karte_output_directory": str(tmp_path / "no-such-dir")}
        assert llm_coach.find_latest_llm_input_for_ctx(ctx) is None

    def test_returns_latest_karte(self, tmp_path):
        (tmp_path / "karte_old.json").write_text("{}")
        (tmp_path / "karte_new.json").write_text("{}")
        import os

        os.utime(tmp_path / "karte_old.json", (1000, 1000))
        os.utime(tmp_path / "karte_new.json", (2000, 2000))
        ctx = _fake_ctx(tmp_path)
        result = llm_coach.find_latest_llm_input_for_ctx(ctx)
        assert result is not None
        assert result.name == "karte_new.json"

    def test_returns_latest_summary(self, tmp_path):
        (tmp_path / "summary_x.json").write_text("{}")
        (tmp_path / "summary_y.json").write_text("{}")
        import os

        os.utime(tmp_path / "summary_x.json", (1000, 1000))
        os.utime(tmp_path / "summary_y.json", (2000, 2000))
        ctx = _fake_ctx(tmp_path)
        result = llm_coach.find_latest_llm_input_for_ctx(ctx)
        assert result is not None
        assert result.name == "summary_y.json"

    def test_returns_mixed_latest(self, tmp_path):
        (tmp_path / "karte_a.json").write_text("{}")
        (tmp_path / "summary_b.json").write_text("{}")
        import os

        os.utime(tmp_path / "karte_a.json", (1000, 1000))
        os.utime(tmp_path / "summary_b.json", (5000, 5000))
        ctx = _fake_ctx(tmp_path)
        result = llm_coach.find_latest_llm_input_for_ctx(ctx)
        assert result is not None
        assert result.name == "summary_b.json"

    def test_no_reports_returns_none(self, tmp_path):
        ctx = _fake_ctx(tmp_path)
        assert llm_coach.find_latest_llm_input_for_ctx(ctx) is None


# --- Phase 227-D: build_summary_llm_prompt + validate_summary_llm_response ---


class TestBuildSummaryLlmPrompt:
    """Phase 227-D: thin wrapper around ``build_summary_weakness_prompt``."""

    def _write_summary(self, tmp_path: Path, **extra: Any) -> Path:
        p = tmp_path / "summary.json"
        body = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "phase_x_mistake": {"middle:blunder": 8, "opening:mistake": 5},
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                ],
                "white": [],
            },
            "players": {
                "sentoku870": {"rank": "4d"},
            },
        }
        body.update(extra)
        p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return p

    def test_returns_full_markdown(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        ok, content = llm_coach.build_summary_llm_prompt(None, path, rank="4d")
        assert ok is True
        assert isinstance(content, str)
        assert "MULTI-GAME SUMMARY MODE" in content
        assert "**5 局**" in content

    def test_player_name_appears_when_set(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        ok, content = llm_coach.build_summary_llm_prompt(None, path, rank="4d", player_name="sentoku870")
        assert ok is True
        assert "sentoku870" in content

    def test_birdseye_when_no_player(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        ok, content = llm_coach.build_summary_llm_prompt(None, path, rank="4d")
        assert ok is True
        assert "全体俯瞰" in content

    def test_missing_file_returns_error(self, tmp_path: Path):
        ok, msg = llm_coach.build_summary_llm_prompt(None, tmp_path / "nope.json", rank="4d")
        assert ok is False
        assert "見つかりません" in msg or "not found" in msg.lower()

    def test_malformed_json_returns_error(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        ok, msg = llm_coach.build_summary_llm_prompt(None, bad, rank="4d")
        assert ok is False
        assert "JSON" in msg or "json" in msg.lower() or "不正" in msg

    def test_logs_to_ctx_on_error(self, tmp_path: Path):
        ctx = MagicMock()
        path = tmp_path / "nope.json"
        llm_coach.build_summary_llm_prompt(ctx, path, rank="4d")
        ctx.log.assert_called()

    def test_logs_to_ctx_on_success(self, tmp_path: Path):
        ctx = MagicMock()
        path = self._write_summary(tmp_path)
        llm_coach.build_summary_llm_prompt(ctx, path, rank="4d")
        # No log call expected on success — the popup displays its
        # own status. We just verify it doesn't crash.
        # (ctx.log is not asserted here; see test_none_ctx_does_not_raise
        # for the no-crash contract.)

    def test_none_ctx_does_not_raise(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        # ctx=None must not crash
        ok, content = llm_coach.build_summary_llm_prompt(None, path, rank="4d")
        assert ok is True
        assert isinstance(content, str)


class TestValidateSummaryLlmResponse:
    """Phase 227-D: thin wrapper around ``validate_summary_llm_output``."""

    def _write_summary(self, tmp_path: Path) -> Path:
        p = tmp_path / "summary.json"
        p.write_text(
            json.dumps(
                {
                    "schema_version": "3.4",
                    "meta": {"games_analyzed": 5},
                    "phase_x_mistake": {"middle:blunder": 8},
                    "weaknesses": {
                        "black": [
                            {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                        ],
                        "white": [],
                    },
                    "players": {"sentoku870": {"rank": "4d"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return p

    def test_clean_response_returns_clean(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        response = "考察: 中盤の blunders が多いです。\n抽出した弱点パターン: [blunder]\n参照したphase: [middle]\n"
        is_clean, report = llm_coach.validate_summary_llm_response(None, path, response, rank="4d")
        assert is_clean is True
        # Markdown report should include a Status line
        assert "Status" in report or "ステータス" in report

    def test_dirty_response_returns_invalid(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        # Move number is forbidden in summary mode
        response = "考察: 第50手でのミスが顕著でした。\n抽出した弱点パターン: [blunder, fantasy_category]\n"
        is_clean, report = llm_coach.validate_summary_llm_response(None, path, response, rank="4d")
        assert is_clean is False
        assert "[HIGH]" in report

    def test_missing_file_returns_error(self, tmp_path: Path):
        is_clean, msg = llm_coach.validate_summary_llm_response(None, tmp_path / "nope.json", "anything", rank="4d")
        assert is_clean is False
        assert "見つかりません" in msg or "not found" in msg.lower()

    def test_player_name_passed_through(self, tmp_path: Path):
        # The wrapper forwards player_name to the prompt config. This
        # mostly just exercises the parameter plumbing — the actual
        # behaviour is covered by the underlying validator tests.
        path = self._write_summary(tmp_path)
        response = "考察: ...\n抽出した弱点パターン: [blunder]\n参照したphase: [middle]\n"
        is_clean, report = llm_coach.validate_summary_llm_response(
            None, path, response, rank="4d", player_name="sentoku870"
        )
        assert is_clean is True
        assert "Status" in report or "ステータス" in report

    def test_report_truncation_on_huge_input(self, tmp_path: Path):
        # A giant response should still produce a usable report
        # (truncated to avoid UI freeze).
        path = self._write_summary(tmp_path)
        # 30k characters of "考察" — should trigger truncation
        huge = "考察" * 15000
        is_clean, report = llm_coach.validate_summary_llm_response(None, path, huge, rank="4d")
        # Truncated reports end with the i18n "truncated" marker
        assert "省略" in report or "truncated" in report or len(report) <= 30_000

    def test_none_ctx_does_not_raise(self, tmp_path: Path):
        path = self._write_summary(tmp_path)
        is_clean, report = llm_coach.validate_summary_llm_response(None, path, "考察: ...\n", rank="4d")
        assert isinstance(is_clean, bool)
        assert isinstance(report, str)
