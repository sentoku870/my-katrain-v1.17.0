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


# Phase 241-C: tests for the new ``loss_progression`` block fallback.
class TestLossProgressionBlock:
    """Phase 241-C: ``loss_progression`` is rendered with a placeholder
    when absent, and aggregated to a single row per game type when
    present."""

    def test_loss_progression_dict_with_all(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
            "loss_progression": {
                "all": [
                    {"start_move": 1, "end_move": 10, "move_count": 30, "total_loss": 5.0, "avg_loss": 0.167, "mistake_count": 2},
                    {"start_move": 11, "end_move": 20, "move_count": 30, "total_loss": 8.0, "avg_loss": 0.267, "mistake_count": 3},
                ]
            },
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        # The "all" game type is rendered with aggregated stats.
        assert "**all**" in prompt.body_markdown
        assert "総損失=13.00" in prompt.body_markdown
        assert "ミス数=5" in prompt.body_markdown

    def test_loss_progression_dict_with_multiple_game_types(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "weaknesses": {},
            "phase_x_mistake": {},
            "loss_progression": {
                "all": [{"start_move": 1, "end_move": 10, "move_count": 50, "total_loss": 10.0, "avg_loss": 0.2, "mistake_count": 4}],
                "even": [{"start_move": 1, "end_move": 10, "move_count": 30, "total_loss": 6.0, "avg_loss": 0.2, "mistake_count": 2}],
                "handicapped": [{"start_move": 1, "end_move": 10, "move_count": 20, "total_loss": 4.0, "avg_loss": 0.2, "mistake_count": 2}],
            },
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        for game_type in ("all", "even", "handicapped"):
            assert f"**{game_type}**" in prompt.body_markdown

    def test_loss_progression_legacy_flat_list(self):
        # Pre-Phase 157-C summary JSONs may have loss_progression as
        # a flat list. The helper normalises this into {"all": [...].
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
            "loss_progression": [
                {"start_move": 1, "end_move": 10, "move_count": 30, "total_loss": 5.0, "avg_loss": 0.167, "mistake_count": 1},
            ],
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        assert "**all**" in prompt.body_markdown

    def test_loss_progression_missing_shows_placeholder(self):
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
        assert "loss_progression データがありません" in prompt.body_markdown

    def test_loss_progression_empty_dict_shows_placeholder(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
            "loss_progression": {},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        assert "loss_progression データがありません" in prompt.body_markdown

    def test_loss_progression_empty_bucket_list(self):
        # Game type key exists but value is an empty list
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "weaknesses": {},
            "phase_x_mistake": {},
            "loss_progression": {"all": []},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        # The "all" key with an empty list shows "(空)" rather than
        # being silently dropped (the LLM needs to know the data is
        # present but empty vs. entirely missing).
        assert "**all**: (空)" in prompt.body_markdown

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
            "color",
            "phase",
            "category",
            "count",
            "total_loss",
            "frequency_ratio",
        }

    def test_config_echoed(self, sample_summary, base_config):
        prompt = build_summary_weakness_prompt(sample_summary, base_config)
        assert prompt.config is base_config


# --- Phase 228-B: Real-shape player stats in the prompt body ---


def real_shape_summary() -> dict:
    """A summary JSON shaped like the real ``summary_json_export.py`` output.

    Used by the Phase 228-B tests below to verify that the prompt
    body populates the Player Mistake Distribution and Player Phase
    Loss Distribution sections.
    """
    return {
        "schema_version": "3.4",
        "meta": {"games_analyzed": 3, "games_by_type": {"even": 3, "handicapped": 0, "unknown": 0}},
        "games": [{"game_id": "g1"}, {"game_id": "g2"}, {"game_id": "g3"}],
        "players": {
            "sentoku870": {
                "mistakes": {
                    "good": {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28},
                    "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 3.11},
                    "mistake": {"count": 22, "pct": 5.7, "denominator": 388, "avg_loss": 5.69},
                    "blunder": {"count": 5, "pct": 1.3, "denominator": 388, "avg_loss": 19.04},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 47.01, "avg_loss": 0.627},
                    "middle": {"moves": 173, "total_loss": 370.78, "avg_loss": 2.143},
                    "endgame": {"moves": 140, "total_loss": 48.6, "avg_loss": 0.347},
                },
            },
            "opponent1": {
                "mistakes": {
                    "good": {"count": 350, "pct": 90.2, "denominator": 388, "avg_loss": 0.22},
                    "blunder": {"count": 2, "pct": 0.5, "denominator": 388, "avg_loss": 18.0},
                },
                "phases": {
                    "opening": {"moves": 75, "total_loss": 30.0, "avg_loss": 0.4},
                    "middle": {"moves": 173, "total_loss": 150.0, "avg_loss": 0.87},
                    "endgame": {"moves": 140, "total_loss": 25.0, "avg_loss": 0.18},
                },
            },
        },
        "loss_progression": {"all": [{"mistake_count": 5}] * 3},
    }


class TestResolveFocusedPlayer:
    """Phase 228-B: ``_resolve_focused_player`` picks which player
    to show in the per-player stat blocks."""

    def test_configured_player_matching(self):
        from katrain.core.coach.summary_prompt_builder import (
            _resolve_focused_player,
        )

        data = real_shape_summary()
        assert _resolve_focused_player(data, "sentoku870") == "sentoku870"

    def test_configured_player_unknown_falls_back_to_birdseye(self):
        # Phase 228-B: when the configured player doesn't match any
        # key in ``players``, fall back to birdseye mode (None)
        # rather than auto-picking a player (which would mislead the LLM
        # about whose perspective it's reviewing).
        from katrain.core.coach.summary_prompt_builder import (
            _resolve_focused_player,
        )

        data = real_shape_summary()
        assert _resolve_focused_player(data, "NonExistent") is None

    def test_no_player_configured_returns_none_for_birdseye(self):
        # Phase 228-B: when no player is configured (birdseye), the
        # resolver returns ``None`` so the section header renders
        # "全体俯瞰" rather than auto-picking a player.
        from katrain.core.coach.summary_prompt_builder import (
            _resolve_focused_player,
        )

        data = real_shape_summary()
        assert _resolve_focused_player(data, None) is None

    def test_no_players_block_returns_none(self):
        from katrain.core.coach.summary_prompt_builder import (
            _resolve_focused_player,
        )

        assert _resolve_focused_player({}, None) is None

    def test_empty_players_block_returns_none(self):
        from katrain.core.coach.summary_prompt_builder import (
            _resolve_focused_player,
        )

        assert _resolve_focused_player({"players": {}}, None) is None


class TestFormatPlayerMistakesBlock:
    """Phase 228-B: ``_format_player_mistakes_block`` renders the
    Player Mistake Distribution section."""

    def test_focused_player_full_breakdown(self):
        from katrain.core.coach.json_type import extract_summary_player_mistakes
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_mistakes_block,
        )

        data = real_shape_summary()
        mistakes = extract_summary_player_mistakes(data)
        block = _format_player_mistakes_block(mistakes, "sentoku870")
        # All 4 categories rendered
        assert "**blunder**: 5/388 (1.3%) - avg_loss 19.04" in block
        assert "**mistake**: 22/388 (5.7%) - avg_loss 5.69" in block
        assert "**inaccuracy**: 51/388 (13.1%) - avg_loss 3.11" in block
        assert "**good**: 310/388 (79.9%) - avg_loss 0.28" in block

    def test_severity_order(self):
        from katrain.core.coach.json_type import extract_summary_player_mistakes
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_mistakes_block,
        )

        data = real_shape_summary()
        mistakes = extract_summary_player_mistakes(data)
        block = _format_player_mistakes_block(mistakes, "sentoku870")
        # blunder should come before mistake, which comes before good
        b_pos = block.find("**blunder**")
        m_pos = block.find("**mistake**")
        g_pos = block.find("**good**")
        assert b_pos < m_pos < g_pos
        assert b_pos >= 0

    def test_no_mistakes_data_returns_placeholder(self):
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_mistakes_block,
        )

        block = _format_player_mistakes_block({}, "any_player")
        assert "mistakes データがありません" in block

    def test_birdseye_shows_per_player_top_category(self):
        from katrain.core.coach.json_type import extract_summary_player_mistakes
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_mistakes_block,
        )

        data = real_shape_summary()
        mistakes = extract_summary_player_mistakes(data)
        block = _format_player_mistakes_block(mistakes, None)
        # Should show one line per player (top category only)
        assert "**sentoku870**" in block
        assert "**opponent1**" in block
        # Bird's-eye line shows the top (most severe) category per player
        assert "top=blunder" in block

    def test_unknown_focused_player_falls_back_to_birdseye(self):
        from katrain.core.coach.json_type import extract_summary_player_mistakes
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_mistakes_block,
        )

        data = real_shape_summary()
        mistakes = extract_summary_player_mistakes(data)
        block = _format_player_mistakes_block(mistakes, "NonExistent")
        # Falls back to per-player overview
        assert "**sentoku870**" in block


class TestFormatPlayerPhasesBlock:
    """Phase 228-B: ``_format_player_phases_block`` renders the
    Player Phase Loss Distribution section."""

    def test_focused_player_phases_sorted_by_total_loss_desc(self):
        from katrain.core.coach.json_type import extract_summary_player_phase_losses
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_phases_block,
        )

        data = real_shape_summary()
        phases = extract_summary_player_phase_losses(data)
        block = _format_player_phases_block(phases, "sentoku870")
        # middle (370.78) should come before endgame (48.6) which
        # comes before opening (47.01)
        middle_pos = block.find("**middle**")
        endgame_pos = block.find("**endgame**")
        opening_pos = block.find("**opening**")
        assert middle_pos < endgame_pos < opening_pos
        assert middle_pos >= 0

    def test_focused_player_shows_all_three_phases(self):
        from katrain.core.coach.json_type import extract_summary_player_phase_losses
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_phases_block,
        )

        data = real_shape_summary()
        phases = extract_summary_player_phase_losses(data)
        block = _format_player_phases_block(phases, "sentoku870")
        assert "173手" in block
        assert "370.78損失" in block
        assert "75手" in block
        assert "140手" in block

    def test_no_phases_data_returns_placeholder(self):
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_phases_block,
        )

        block = _format_player_phases_block({}, "any_player")
        assert "phases データがありません" in block

    def test_birdseye_shows_per_player_worst_phase(self):
        from katrain.core.coach.json_type import extract_summary_player_phase_losses
        from katrain.core.coach.summary_prompt_builder import (
            _format_player_phases_block,
        )

        data = real_shape_summary()
        phases = extract_summary_player_phase_losses(data)
        block = _format_player_phases_block(phases, None)
        # Bird's-eye line shows the worst phase per player
        assert "**sentoku870**" in block
        assert "**opponent1**" in block
        assert "worst phase" in block
        # sentoku870's worst phase is middle (370.78)
        assert "phase=`middle`" in block


class TestPlayerSectionsInPromptBody:
    """Phase 228-B: end-to-end verification that the prompt body
    contains the new sections when the real-shape data is available."""

    def test_player_mistakes_section_present(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        assert "### Player Mistake Distribution (sentoku870)" in prompt.body_markdown

    def test_player_mistakes_section_values(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # The key metrics from the real JSON should appear verbatim
        assert "5/388 (1.3%)" in prompt.body_markdown  # blunder
        assert "22/388 (5.7%)" in prompt.body_markdown  # mistake
        assert "370.78" in prompt.body_markdown  # middle phase total_loss

    def test_player_phases_section_present(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        assert "### Player Phase Loss Distribution (sentoku870)" in prompt.body_markdown

    def test_player_phases_sorted_with_middle_first(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # Middle should appear first (worst phase by total_loss)
        body = prompt.body_markdown
        player_phases_idx = body.find("### Player Phase Loss Distribution")
        next_section_idx = body.find("### Weakness Patterns")
        phase_block = body[player_phases_idx:next_section_idx]
        middle_pos = phase_block.find("**middle**")
        endgame_pos = phase_block.find("**endgame**")
        opening_pos = phase_block.find("**opening**")
        assert middle_pos < endgame_pos < opening_pos

    def test_birdseye_label_in_sections(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name=None,
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # Bird's-eye: header shows "(全体俯瞰)"
        assert "### Player Mistake Distribution (全体俯瞰)" in prompt.body_markdown
        assert "### Player Phase Loss Distribution (全体俯瞰)" in prompt.body_markdown

    def test_system_instruction_updated_for_player_blocks(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # The system instruction should mention the new section as a
        # valid source of weakness patterns.
        assert "Player Mistake Distribution" in prompt.system_instruction

    def test_weakness_patterns_use_pct_for_shape_b(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # Shape B patterns should NOT show misleading 1700% frequency
        assert "1700.0%" not in prompt.body_markdown
        assert "733.3%" not in prompt.body_markdown
        # Instead they should use the per-move pct
        assert "全体に占める割合" in prompt.body_markdown
        assert "13.1%" in prompt.body_markdown

    def test_backward_compat_with_legacy_shape(self):
        # Existing fixture: top-level weaknesses (Phase 227-A legacy)
        legacy = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "weaknesses": {
                "black": [{"phase": "middle", "category": "blunder", "count": 5, "total_loss": 30.0}],
            },
            "phase_x_mistake": {"middle:blunder": 8},
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=5,
        )
        prompt = build_summary_weakness_prompt(legacy, cfg)
        # Old-shape patterns still render correctly
        assert "phase=`middle`" in prompt.body_markdown
        assert "color=`black`" in prompt.body_markdown
        # frequency_ratio still works for Shape A
        assert "頻度=100.0%" in prompt.body_markdown
        # Player Mistake / Phase Loss sections show their placeholder
        assert "mistakes データがありません" in prompt.body_markdown
        assert "phases データがありません" in prompt.body_markdown

    def test_player_name_section_label(self):
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
            player_name="sentoku870",
        )
        prompt = build_summary_weakness_prompt(real_shape_summary(), cfg)
        # Section labels include the player name
        assert "### Player Mistake Distribution (sentoku870)" in prompt.body_markdown
        assert "### Player Phase Loss Distribution (sentoku870)" in prompt.body_markdown

    def test_no_players_block_shows_placeholders(self):
        # Edge case: no players block at all
        no_players = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "games": [],
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(no_players, cfg)
        # Placeholder messages instead of empty blocks
        assert "mistakes データがありません" in prompt.body_markdown
        assert "phases データがありません" in prompt.body_markdown
