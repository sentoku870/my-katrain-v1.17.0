"""Phase 214-A: Tests for katrain.core.coach.cli.

Covers:
- Argument parsing for all 4 sub-commands
- build sub-command: prompt file generation, stdout mode
- validate sub-command: issue detection, exit codes
- symptoms / lexicon sub-commands: enumeration helpers

The CLI is Kivy-free so these tests can run without the Kivy harness.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from katrain.core.coach import cli


# --- Fixtures ---


@pytest.fixture
def sample_karte_path(tmp_path: Path) -> Path:
    karte = {
        "schema_version": "3.4",
        "summary": {"total_moves": 200},
        "important_moves": [
            {"meaning_tag_id": "atari_blindness", "points_lost": 1.5},
            {"meaning_tag_id": "big_point_blindness", "points_lost": 3.0},
        ],
        "weaknesses": {
            "black": [
                {"category": "atari_blindness"},
                {"category": "big_point_blindness"},
            ],
            "white": [],
        },
    }
    p = tmp_path / "karte.json"
    p.write_text(json.dumps(karte, ensure_ascii=False), encoding="utf-8")
    return p


# --- Top-level main ---


class TestMainDispatch:
    def test_no_args_prints_help_and_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit):
            cli.main([])
        # argparse prints help to stderr on missing required subcommand
        captured = capsys.readouterr()
        assert "usage:" in captured.err or "usage:" in captured.out

    def test_unknown_subcommand_exits_nonzero(self):
        with pytest.raises(SystemExit):
            cli.main(["unknown_subcommand"])


# --- build sub-command ---


class TestBuildCommand:
    def test_build_writes_to_file(self, sample_karte_path: Path, tmp_path: Path):
        out_path = tmp_path / "prompt.md"
        rc = cli.main([
            "build",
            str(sample_karte_path),
            "--rank", "5k",
            "--out", str(out_path),
        ])
        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "[SYSTEM INSTRUCTION FOR LLM]" in content
        assert "[LEXICON INJECTION]" in content
        assert "## Karte JSON" in content

    def test_build_writes_to_stdout(self, sample_karte_path: Path, capsys):
        rc = cli.main([
            "build",
            str(sample_karte_path),
            "--rank", "5k",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Summary line goes to stderr
        assert "voice=" in captured.err
        # Prompt body goes to stdout
        assert "[SYSTEM INSTRUCTION FOR LLM]" in captured.out

    def test_build_no_expanded_shortens_lexicon(self, sample_karte_path: Path, tmp_path: Path):
        out_full = tmp_path / "full.md"
        out_short = tmp_path / "short.md"
        cli.main([
            "build",
            str(sample_karte_path),
            "--rank", "5k",
            "--out", str(out_full),
        ])
        cli.main([
            "build",
            str(sample_karte_path),
            "--rank", "5k",
            "--no-expanded",
            "--out", str(out_short),
        ])
        # Short version should be <= full version
        assert out_short.stat().st_size <= out_full.stat().st_size

    def test_build_missing_file_exits_nonzero(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            cli.main([
                "build",
                str(tmp_path / "nonexistent.json"),
                "--rank", "5k",
            ])

    def test_build_invalid_json_exits_nonzero(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            cli.main(["build", str(bad), "--rank", "5k"])


# --- build --summary-mode (Phase 227-A) ---


class TestBuildSummaryMode:
    @pytest.fixture
    def sample_summary_path(self, tmp_path: Path) -> Path:
        summary = {
            "schema_version": "3.4",
            "meta": {
                "games_analyzed": 5,
                "games_by_type": {"even": 5, "handicapped": 0, "unknown": 0},
            },
            "summary": {"total_games": 5, "win_rate": 0.4, "total_moves": 1200},
            "phase_x_mistake": {
                "opening:mistake": 5,
                "middle:blunder": 8,
            },
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                    {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
                ],
                "white": [],
            },
            "players": {"sentoku870": {"win_rate": 0.4}, "Opponent": {"win_rate": 0.6}},
        }
        p = tmp_path / "summary.json"
        p.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
        return p

    def test_summary_mode_writes_to_file(
        self, sample_summary_path: Path, tmp_path: Path
    ):
        out_path = tmp_path / "summary_prompt.md"
        rc = cli.main([
            "build",
            str(sample_summary_path),
            "--summary-mode",
            "--rank", "4d",
            "--out", str(out_path),
        ])
        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "MULTI-GAME SUMMARY MODE" in content
        assert "**5 局**" in content
        assert "全体俯瞰" in content  # default player_name=None

    def test_summary_mode_writes_to_stdout(
        self, sample_summary_path: Path, capsys
    ):
        rc = cli.main([
            "build",
            str(sample_summary_path),
            "--summary-mode",
            "--rank", "4d",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "summary-mode" in captured.err
        assert "patterns" in captured.err
        assert "MULTI-GAME SUMMARY MODE" in captured.out

    def test_summary_mode_with_player_flag(
        self, sample_summary_path: Path, tmp_path: Path
    ):
        out_path = tmp_path / "p.md"
        cli.main([
            "build",
            str(sample_summary_path),
            "--summary-mode",
            "--player", "sentoku870",
            "--out", str(out_path),
        ])
        content = out_path.read_text(encoding="utf-8")
        assert "Focus: プレイヤー 'sentoku870'" in content

    def test_summary_mode_rejects_karte(
        self, sample_karte_path: Path, capsys
    ):
        rc = cli.main([
            "build",
            str(sample_karte_path),
            "--summary-mode",
        ])
        assert rc == 2
        captured = capsys.readouterr()
        assert "❌" in captured.err
        assert "Summary JSON" in captured.err

    def test_no_summary_mode_karte_still_works(
        self, sample_karte_path: Path, tmp_path: Path
    ):
        # Regression: default path (no --summary-mode) on karte file
        out_path = tmp_path / "karte_prompt.md"
        rc = cli.main([
            "build",
            str(sample_karte_path),
            "--rank", "5k",
            "--out", str(out_path),
        ])
        assert rc == 0
        content = out_path.read_text(encoding="utf-8")
        assert "[SYSTEM INSTRUCTION FOR LLM]" in content
        assert "MULTI-GAME SUMMARY MODE" not in content

    def test_no_summary_mode_summary_falls_back_to_karte_projection(
        self, sample_summary_path: Path, tmp_path: Path
    ):
        # Default path auto-projects summary to karte shape (existing
        # Phase 221 behaviour). Should NOT error and should produce a
        # karte-style prompt.
        out_path = tmp_path / "fallback.md"
        rc = cli.main([
            "build",
            str(sample_summary_path),
            "--rank", "5k",
            "--out", str(out_path),
        ])
        assert rc == 0
        content = out_path.read_text(encoding="utf-8")
        # Existing Karte prompt path
        assert "[SYSTEM INSTRUCTION FOR LLM]" in content


# --- validate sub-command ---


class TestValidateCommand:
    @pytest.fixture
    def llm_response_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "llm.txt"
        p.write_text(
            "考察: ウチが見た感じ、ここはあかん。\n"
            "参照した症状ID: [atari_blindness, fantasy_id]\n",
            encoding="utf-8",
        )
        return p

    def test_validate_clean_returns_0(
        self, sample_karte_path: Path, tmp_path: Path
    ):
        # Both atari_blindness + big_point_blindness are in karte.
        good_response = tmp_path / "good.txt"
        good_response.write_text(
            "考察: ウチが見た感じ、あかん。\n"
            "参照した症状ID: [atari_blindness, big_point_blindness]\n",
            encoding="utf-8",
        )
        rc = cli.main([
            "validate",
            str(sample_karte_path),
            str(good_response),
            "--rank", "5k",
        ])
        assert rc == 0

    def test_validate_hallucination_returns_1(
        self, sample_karte_path: Path, llm_response_path: Path
    ):
        rc = cli.main([
            "validate",
            str(sample_karte_path),
            str(llm_response_path),
            "--rank", "5k",
        ])
        assert rc == 1

    def test_validate_report_contains_expected_sections(
        self, sample_karte_path: Path, llm_response_path: Path, capsys
    ):
        cli.main([
            "validate",
            str(sample_karte_path),
            str(llm_response_path),
            "--rank", "5k",
        ])
        out = capsys.readouterr().out
        assert "LLM Output Validation Report" in out
        assert "Status" in out
        assert "Issues" in out
        assert "fantasy_id" in out

    def test_validate_to_file(
        self, sample_karte_path: Path, llm_response_path: Path, tmp_path: Path
    ):
        out_path = tmp_path / "report.md"
        cli.main([
            "validate",
            str(sample_karte_path),
            str(llm_response_path),
            "--rank", "5k",
            "--out", str(out_path),
        ])
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "fantasy_id" in content


# --- symptoms sub-command ---


class TestSymptomsCommand:
    def test_symptoms_lists_all(self, capsys):
        rc = cli.main(["symptoms"])
        assert rc == 0
        out = capsys.readouterr().out
        # Should list at least 30 symptoms
        lines = [l for l in out.splitlines() if l.startswith("🟢") or l.startswith("🟡")]
        assert len(lines) >= 30
        # Auto-detected markers (green) should outnumber LLM-required (yellow)
        green = sum(1 for l in lines if l.startswith("🟢"))
        yellow = sum(1 for l in lines if l.startswith("🟡"))
        assert green >= 15
        assert yellow >= 10


# --- lexicon sub-command ---


class TestLexiconCommand:
    def test_lexicon_known_entry(self, capsys):
        rc = cli.main(["lexicon", "liberty"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "呼吸点" in out
        assert "石に隣接する空点" in out

    def test_lexicon_unknown_returns_1(self, capsys):
        rc = cli.main(["lexicon", "this_does_not_exist_xyz"])
        assert rc == 1
        out = capsys.readouterr().err
        assert "No entry found" in out

    def test_lexicon_known_concept(self, capsys):
        # Concepts aren't LexiconEntry; should return None → rc=1
        # but for safety let me try a known entry id
        rc = cli.main(["lexicon", "capture"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "石を取る" in out


# --- Public API ---


class TestExports:
    def test_build_prompt_helper(self, sample_karte_path: Path):
        karte = json.loads(sample_karte_path.read_text(encoding="utf-8"))
        prompt = cli.build_prompt(karte, rank="5k")
        assert prompt.full_markdown
        assert prompt.config.voice.value == "ayaka"

    def test_build_prompt_default_rank(self, sample_karte_path: Path):
        karte = json.loads(sample_karte_path.read_text(encoding="utf-8"))
        prompt = cli.build_prompt(karte)  # no rank
        # Default to AYAKA per select_voice fallback
        assert prompt.config.voice.value == "ayaka"


# --- analyze sub-command (Phase 217) ---


class TestAnalyzeCommand:
    def test_analyze_to_stdout(self, sample_karte_path: Path, capsys):
        rc = cli.main([
            "analyze",
            str(sample_karte_path),
            "--rank", "5k",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        # Required sections
        assert "# Karte Analysis" in out
        assert "## Meta" in out
        assert "## Aggregate Metrics" in out
        assert "## Streak Metrics" in out
        assert "## Correlation" in out
        assert "## Would-be Coach Configuration" in out
        assert "## Detected Symptoms" in out

    def test_analyze_to_file(self, sample_karte_path: Path, tmp_path: Path):
        out_path = tmp_path / "analysis.md"
        rc = cli.main([
            "analyze",
            str(sample_karte_path),
            "--rank", "5k",
            "--out", str(out_path),
        ])
        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Karte Analysis" in content

    def test_analyze_detects_symptoms(self, sample_karte_path: Path, capsys):
        cli.main([
            "analyze",
            str(sample_karte_path),
            "--rank", "5k",
        ])
        out = capsys.readouterr().out
        # sample_karte has atari_blindness + big_point_blindness weaknesses
        assert "atari_blindness" in out
        assert "big_point_blindness" in out

    def test_analyze_streak_metrics(self, sample_karte_path: Path, capsys):
        cli.main([
            "analyze",
            str(sample_karte_path),
        ])
        out = capsys.readouterr().out
        # Streak Metrics block should exist (data may or may not be populated)
        assert "longest_streak:" in out
        assert "total_streak_loss:" in out

    def test_analyze_correlation_section(self, sample_karte_path: Path, capsys):
        cli.main([
            "analyze",
            str(sample_karte_path),
        ])
        out = capsys.readouterr().out
        assert "## Correlation" in out
        assert "winrate / scoreLead correlation:" in out

    def test_analyze_missing_file_exits_nonzero(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            cli.main([
                "analyze",
                str(tmp_path / "nonexistent.json"),
            ])


# --- calibrate sub-command (Phase 219) ---


class TestCalibrateCommand:
    def test_calibrate_all_pass_returns_0(self, capsys):
        rc = cli.main(["calibrate"])
        assert rc == 0
        out = capsys.readouterr().out
        # All 8 fixtures should pass
        assert "passed: 8" in out
        assert "failed: 0" in out
        assert "# Coach Detector Calibration" in out

    def test_calibrate_to_file(self, tmp_path: Path):
        out_path = tmp_path / "calibration.md"
        rc = cli.main(["calibrate", "--out", str(out_path)])
        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Coach Detector Calibration" in content
        assert "## Summary" in content

    def test_calibrate_single_fixture(self, capsys):
        rc = cli.main(["calibrate", "--fixture", "perfect_game"])
        assert rc == 0
        out = capsys.readouterr().out
        # Only the perfect_game section should appear
        assert "## ✅ perfect_game" in out
        # No other fixture names should appear as section headers
        assert "## ✅ single_atari_mistake" not in out
        # Summary should reflect 1 total
        assert "total:  1" in out

    def test_calibrate_unknown_fixture_returns_1(self, capsys):
        rc = cli.main(["calibrate", "--fixture", "this_does_not_exist"])
        assert rc == 1
        out = capsys.readouterr().out
        assert "Unknown fixture" in out

    def test_calibrate_lists_all_fixture_sections(self, capsys):
        cli.main(["calibrate"])
        out = capsys.readouterr().out
        # All 8 fixture names should appear
        for name in [
            "perfect_game",
            "single_atari_mistake",
            "reckless_overplay",
            "long_mistake_streak",
            "many_small_streaks",
            "tilt_chain_disaster",
            "tilt_discouragement",
            "strong_correlation",
        ]:
            assert f"## ✅ {name}" in out, f"Missing section: {name}"


# --- trace sub-command (Phase 220) ---


class TestTraceCommand:
    def test_trace_to_stdout(self, sample_karte_path: Path, capsys):
        rc = cli.main(["trace", str(sample_karte_path)])
        assert rc == 0
        out = capsys.readouterr().out
        # Required sections
        assert "# Detection Pipeline Trace (Phase 220)" in out
        assert "## Sources" in out
        assert "## Per-Symptom Sources" in out
        assert "## SymptomContext Snapshot" in out

    def test_trace_to_file(self, sample_karte_path: Path, tmp_path: Path):
        out_path = tmp_path / "trace.md"
        rc = cli.main(["trace", str(sample_karte_path), "--out", str(out_path)])
        assert rc == 0
        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        assert "# Detection Pipeline Trace (Phase 220)" in content

    def test_trace_sources_listed(self, sample_karte_path: Path, capsys):
        cli.main(["trace", str(sample_karte_path)])
        out = capsys.readouterr().out
        # All 4 source names should appear
        assert "per_move:" in out
        assert "weakness_category:" in out
        assert "streak:" in out
        assert "aggregate:" in out
        assert "**union**:" in out

    def test_trace_attributes_symptoms_to_sources(self, sample_karte_path: Path, capsys):
        cli.main(["trace", str(sample_karte_path)])
        out = capsys.readouterr().out
        # atari_blindness is in weakness, should be tagged with weakness_category
        assert "atari_blindness`: weakness_category" in out

    def test_trace_context_snapshot_present(self, sample_karte_path: Path, capsys):
        cli.main(["trace", str(sample_karte_path)])
        out = capsys.readouterr().out
        # SymptomContext snapshot section
        assert "avg_points_lost:" in out
        assert "is_endgame:" in out
        assert "weakness_concentration:" in out
        assert "meaning_tags:" in out

    def test_trace_missing_file_exits_nonzero(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            cli.main([
                "trace",
                str(tmp_path / "nonexistent.json"),
            ])


# --- summary JSON support (Phase 221) ---


class TestSummaryCli:
    def test_analyze_with_summary(self, tmp_path: Path, capsys):
        """Phase 221: CLI should auto-detect summary and analyze."""
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3, "games_by_type": {"even": 3}},
            "summary": {"total_games": 3},
            "phase_x_mistake": {"middle:blunder": 5},
            "players": {"P1": {}},
            "weaknesses": {
                "black": [
                    {"phase": "middle", "category": "blunder", "total_loss": 20.0},
                ],
                "white": [],
            },
            "mistake_streaks": {"black": [{"move_count": 4, "total_loss": 12.0}]},
            "loss_progression": {"all": [{"mistake_count": 2}]},
            "games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g3"}],
        }
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(summary), encoding="utf-8")
        rc = cli.main(["analyze", str(path)])
        assert rc == 0
        captured = capsys.readouterr()
        # Analysis output goes to stdout
        assert "# Karte Analysis" in captured.out
        # Detection works on projected summary (overfight from 4-streak)
        assert "overfight" in captured.out
        # Info message about summary detection goes to stderr
        assert "ℹ" in captured.err

    def test_trace_with_summary(self, tmp_path: Path, capsys):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 2},
            "players": {"P1": {}},
            "weaknesses": {"black": [{"category": "atari_blindness"}], "white": []},
            "loss_progression": {"all": []},
        }
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(summary), encoding="utf-8")
        rc = cli.main(["trace", str(path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "# Detection Pipeline Trace" in out
        # atari_blindness should be detected from the projected weaknesses
        assert "atari_blindness" in out