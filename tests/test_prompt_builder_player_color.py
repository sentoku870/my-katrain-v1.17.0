"""Phase 225.6: prompt_builder player_color integration tests.

The :class:`PromptConfig` gained a ``player_color`` field that is
rendered into the SystemInstruction block so the LLM knows which
side's weaknesses to focus on. These tests pin the rendering.
"""

from __future__ import annotations

from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.prompt_builder import (
    PromptConfig,
    build_translation_prompt,
)


def _minimal_karte() -> dict:
    return {
        "schema_version": "3.4",
        "meta": {"player_info": {}},
        "summary": {},
        "weaknesses": {"black": [], "white": []},
        "important_moves": [],
    }


class TestPromptConfigPlayerColorRendering:
    def test_player_color_black_renders(self):
        karte = _minimal_karte()
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
            player_color="B",
        )
        prompt = build_translation_prompt(karte, cfg)
        assert "PlayerColor: black" in prompt.system_instruction

    def test_player_color_white_renders(self):
        karte = _minimal_karte()
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
            player_color="W",
        )
        prompt = build_translation_prompt(karte, cfg)
        assert "PlayerColor: white" in prompt.system_instruction

    def test_no_player_color_renders_unknown(self):
        karte = _minimal_karte()
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
            player_color=None,
        )
        prompt = build_translation_prompt(karte, cfg)
        assert "PlayerColor: unknown" in prompt.system_instruction

    def test_strict_rule_mentions_player_color_side(self):
        """The strict-rule 3 in the SystemInstruction must reference
        ``weaknesses[<player_color>]`` so the LLM filters symptoms by
        the chosen side."""
        karte = _minimal_karte()
        cfg = PromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.BEGINNER,
            detected_symptom_ids=(),
            player_color="B",
        )
        prompt = build_translation_prompt(karte, cfg)
        assert "weaknesses[<player_color>]" in prompt.system_instruction
