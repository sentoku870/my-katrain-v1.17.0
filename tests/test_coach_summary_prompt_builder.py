"""Phase 227-A: Tests for katrain.core.coach.summary_prompt_builder.

Covers:
- SummaryPromptConfig dataclass defaults
- SummaryPrompt container fields
- build_summary_weakness_prompt:
  * System instruction contains multi-game markers
  * Body header shows games count, focus, rank
  * Weakness patterns injected (sorted, capped)
  * phase_x_mistake buckets rendered
  * total_loss annotation appended when present
  * player_name None → "全体俯瞰" label
  * player_name set → "プレイヤー 'X'" label
  * Empty weaknesses → placeholder block
  * max_patterns cap respected
"""

from __future__ import annotations

import json

import pytest

from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.summary_prompt_builder import (
    SummaryPromptConfig,
    build_summary_weakness_prompt,
)

# --- Fixtures ---


@pytest.fixture
def sample_summary() -> dict:
    """A typical multi-game Summary JSON."""
    return {
        "schema_version": "3.4",
        "meta": {
            "games_analyzed": 5,
            "date_range": ["2026-07-10", "2026-07-15"],
            "games_by_type": {"even": 3, "handicapped": 2, "unknown": 0},
        },
        "summary": {"total_games": 5, "win_rate": 0.4, "total_moves": 1200},
        "phase_x_mistake": {
            "opening:mistake": 5,
            "middle:blunder": 8,
            "endgame:mistake": 2,
        },
        "weaknesses": {
            "black": [
                {"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0},
                {"phase": "opening", "category": "mistake", "count": 4, "total_loss": 12.0},
                {"phase": "endgame", "category": "endgame_slip", "count": 2, "total_loss": 4.0},
            ],
            "white": [
                {"phase": "middle", "category": "blunder", "count": 3, "total_loss": 18.0},
            ],
        },
        "mistake_streaks": {"black": [], "white": []},
        "loss_progression": {"all": [{"mistake_count": 2}]},
        "games": [{"game_id": "g1"}, {"game_id": "g2"}],
        "players": {"sentoku870": {"win_rate": 0.4}, "Opponent": {"win_rate": 0.6}},
    }


@pytest.fixture
def base_config(sample_summary) -> SummaryPromptConfig:
    return SummaryPromptConfig(
        voice=ToneVoice.TOMOKO,
        mode=CoachMode.DAN,
        games_analyzed=5,
    )


# --- SummaryPromptConfig ---


class TestSummaryPromptConfig:
    def test_defaults(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            games_analyzed=10,
        )
        assert cfg.player_name is None
        assert cfg.player_rank is None
        assert cfg.schema_version == "3.4"
        assert cfg.max_patterns == 10

    def test_frozen(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            games_analyzed=10,
        )
        # Frozen dataclass raises FrozenInstanceError on attribute assignment
        with pytest.raises(AttributeError):
            cfg.games_analyzed = 20  # type: ignore[misc]

    def test_player_name_set(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.AYAKA,
            mode=CoachMode.BEGINNER,
            games_analyzed=10,
            player_name="sentoku870",
        )
        assert cfg.player_name == "sentoku870"


# --- System instruction ---


class TestSystemInstruction:
    def test_contains_multi_game_marker(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "[SYSTEM INSTRUCTION FOR LLM — MULTI-GAME SUMMARY MODE]" in prompt.system_instruction

    def test_contains_games_count(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "Games: 5" in prompt.system_instruction

    def test_strict_rules_mention_pattern_extraction(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "recurring weakness" in prompt.system_instruction
        assert "DO NOT analyze the board independently" in prompt.system_instruction

    def test_player_name_appears_when_set(self, sample_summary):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert "sentoku870" in prompt.system_instruction

    def test_birds_eye_label_when_no_player(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "全体俯瞰" in prompt.system_instruction

    def test_explicit_output_contract(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "抽出した弱点パターン:" in prompt.system_instruction


# --- Body header ---


class TestBodyHeader:
    def test_games_in_body(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "**5 局**" in prompt.body_markdown

    def test_focus_in_body_player_set(self, sample_summary):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert "Focus: プレイヤー 'sentoku870'" in prompt.body_markdown

    def test_focus_in_body_birds_eye(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "Focus: 全体俯瞰" in prompt.body_markdown

    def test_rank_in_body(self, sample_summary):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
            player_rank="4d",
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert "Rank: 4d" in prompt.body_markdown

    def test_rank_unknown_when_unset(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "Rank: (不明)" in prompt.body_markdown


# --- Weakness patterns ---


class TestWeaknessPatterns:
    def test_patterns_injected_sorted_by_total_loss(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        # Patterns block should be in the body, sorted desc by total_loss:
        # 30.0 (black/middle/blunder) > 18.0 (white/middle/blunder) > 12.0 > 4.0
        assert "blunder** / phase=`middle` / color=`black`" in prompt.body_markdown
        assert "blunder** / phase=`middle` / color=`white`" in prompt.body_markdown
        # Black's blunder (30.0) should come before white's blunder (18.0)
        idx_black = prompt.body_markdown.find("color=`black`")
        idx_white = prompt.body_markdown.find("color=`white`")
        assert idx_black != -1 and idx_white != -1
        assert idx_black < idx_white

    def test_patterns_count_in_header(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "top 4" in prompt.body_markdown

    def test_frequency_ratio_displayed(self, sample_summary, base_config):
        # 5/5 = 100%, 3/5 = 60%
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "100.0%" in prompt.body_markdown
        assert "60.0%" in prompt.body_markdown

    def test_max_patterns_cap(self, sample_summary):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
            max_patterns=2,
        )
        prompt = build_summary_weakness_prompt(sample_summary, cfg)
        assert len(prompt.referenced_patterns) == 2
        # top 2 by total_loss: 30.0 and 18.0
        assert prompt.referenced_patterns[0]["total_loss"] == 30.0
        assert prompt.referenced_patterns[1]["total_loss"] == 18.0

    def test_empty_weaknesses_placeholder(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        assert "weakness データが見つかりませんでした" in prompt.body_markdown
        assert len(prompt.referenced_patterns) == 0


# --- Buckets / total_loss ---


class TestBucketsAndLoss:
    def test_buckets_rendered(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "`opening:mistake`: 5" in prompt.body_markdown
        assert "`middle:blunder`: 8" in prompt.body_markdown
        assert "`endgame:mistake`: 2" in prompt.body_markdown

    def test_buckets_empty_message(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        assert "phase_x_mistake データがありません" in prompt.body_markdown

    def test_total_loss_annotation(self, sample_summary, base_config):
        # Total: 30 + 12 + 4 + 18 = 64
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert "**集計総損失**: 64.0" in prompt.body_markdown

    def test_no_total_loss_when_absent(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        assert "集計総損失" not in prompt.body_markdown


# --- Full markdown structure ---


class TestFullMarkdown:
    def test_system_instruction_first(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert prompt.full_markdown.startswith("<!--")

    def test_body_after_system_instruction(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        sys_end = prompt.full_markdown.find(prompt.system_instruction) + len(prompt.system_instruction)
        body_start = prompt.full_markdown.find("# myKatrain 複数局サマリ")
        assert body_start >= sys_end

    def test_json_embedded_verbatim(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        # The JSON body should be parseable back into the same dict
        start = prompt.body_markdown.find("```json\n") + len("```json\n")
        end = prompt.body_markdown.find("\n```", start)
        extracted = json.loads(prompt.body_markdown[start:end])
        assert extracted == sample_summary


# --- SummaryPrompt container ---


class TestSummaryPromptContainer:
    def test_referenced_patterns_populated(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert isinstance(prompt.referenced_patterns, tuple)
        assert len(prompt.referenced_patterns) == 4  # 3 black + 1 white

    def test_referenced_patterns_pattern_dict_shape(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        p = prompt.referenced_patterns[0]
        assert set(p.keys()) == {
            "color", "phase", "category", "count",
            "total_loss", "frequency_ratio",
        }

    def test_config_echoed(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert prompt.config is base_config
