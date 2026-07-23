"""Phase 210: Tests for katrain.core.coach.tones.

Covers:
- select_voice (BR/WR + loss-signal fallback chain)
- greeting_for_mode / greeting_for_voice (master doc §0-2 templates)
- check_prohibited (violation detection)
- voice_summary / modes_for_voice

Phase 269: AYAKA voice removed. All ranks are now mapped to either
TOMOKO (beginner through advanced) or TOMOKO_STRICT (expert).
Kansai-related helpers (has_kansai_markers, apply_kansai_normalisation)
are removed from the public API.

No Kivy — pure core-layer tests.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.tones import (
    check_prohibited,
    greeting_for_mode,
    greeting_for_voice,
    modes_for_voice,
    select_voice,
    voice_summary,
)

# --- select_voice ---


class TestSelectVoice:
    @pytest.mark.parametrize(
        "rank,expected",
        [
            # Phase 269: BEGINNER/INTERMEDIATE → TOMOKO (unified).
            ("25k", ToneVoice.TOMOKO),
            ("10k", ToneVoice.TOMOKO),
            ("5k", ToneVoice.TOMOKO),
            ("4k", ToneVoice.TOMOKO),
            ("1k", ToneVoice.TOMOKO),
            ("2d", ToneVoice.TOMOKO),
            ("5d", ToneVoice.TOMOKO),
            ("6d", ToneVoice.TOMOKO_STRICT),
            ("9d", ToneVoice.TOMOKO_STRICT),
        ],
    )
    def test_rank_to_voice(self, rank, expected):
        assert select_voice(rank) == expected

    def test_no_signal_returns_tomoko_default(self):
        # Phase 269: default = beginner / TOMOKO (unified).
        assert select_voice() == ToneVoice.TOMOKO
        assert select_voice(None) == ToneVoice.TOMOKO
        assert select_voice("") == ToneVoice.TOMOKO
        assert select_voice("garbage") == ToneVoice.TOMOKO

    def test_loss_signal_only(self):
        # avg=10 → adjustment down → BEGINNER → TOMOKO (Phase 269).
        assert select_voice(avg_points_lost=10.0) == ToneVoice.TOMOKO

    def test_rank_takes_priority_over_loss_correction(self):
        # 7d → EXPERT → TOMOKO_STRICT even if loss is high.
        voice = select_voice("7d", avg_points_lost=20.0)
        assert voice == ToneVoice.TOMOKO_STRICT


# --- greeting_for_mode / greeting_for_voice ---


class TestGreeting:
    def test_greeting_for_mode_beginner(self):
        # Phase 269: all modes now use standard Japanese phrasing.
        msg = greeting_for_mode(CoachMode.BEGINNER)
        assert "教えていただけますか" in msg
        # TOMOKO-flavored (no Kansai markers).
        assert "やで" not in msg

    def test_greeting_for_mode_dan(self):
        msg = greeting_for_mode(CoachMode.DAN)
        assert "教えていただけますか" in msg
        assert "やで" not in msg

    def test_greeting_for_mode_expert(self):
        msg = greeting_for_mode(CoachMode.EXPERT)
        assert "教えていただけますか" in msg

    @pytest.mark.parametrize("mode", list(CoachMode))
    def test_greeting_for_all_modes(self, mode):
        msg = greeting_for_mode(mode)
        assert isinstance(msg, str)
        assert "棋力" in msg or "段" in msg or msg == ""

    def test_include_rank_guide_false(self):
        msg = greeting_for_mode(CoachMode.BEGINNER, include_rank_guide=False)
        assert "目安" not in msg

    def test_greeting_for_voice_routing(self):
        # Phase 269: no AYAKA in the public API.
        msg_tomoko = greeting_for_voice(ToneVoice.TOMOKO)
        msg_strict = greeting_for_voice(ToneVoice.TOMOKO_STRICT)
        # Both standard-Japanese.
        assert "教えていただけますか" in msg_tomoko
        assert "教えていただけますか" in msg_strict
        assert "やで" not in msg_tomoko
        assert "やで" not in msg_strict


# --- check_prohibited ---


class TestCheckProhibited:
    def test_clean_tomoko_no_violations(self):
        v = check_prohibited("ウチが見た、この手はええね", ToneVoice.TOMOKO)
        # "ウチ" / "ええね" are Kansai markers but Phase 269 removed
        # the AYAKA-only formal-language check. TOMOKO doesn't enforce
        # a Kansai-free style.
        assert v == []

    def test_character_setup_violates(self):
        v = check_prohibited("私は囲碁コーチです", ToneVoice.TOMOKO)
        assert any("キャラクター" in x for x in v)

    def test_internal_facet_token_violates(self):
        v = check_prohibited("あなたのfacet:directionに問題", ToneVoice.TOMOKO)
        assert any("facet" in x for x in v)

    def test_unfilled_template_violates(self):
        v = check_prohibited("こんにちは、{{user_name}}さん", ToneVoice.TOMOKO)
        assert any("テンプレート変数" in x for x in v)

    def test_tomoko_strict_no_gentle_phrases(self):
        v = check_prohibited(
            "これを〜してみてね！",
            ToneVoice.TOMOKO_STRICT,
        )
        assert any("優しい誘導表現" in x for x in v)

    def test_empty_text_returns_empty(self):
        assert check_prohibited("", ToneVoice.TOMOKO) == []


# --- voice_summary / modes_for_voice ---


class TestVoiceUtilities:
    def test_voice_summary_all(self):
        for v in ToneVoice:
            s = voice_summary(v)
            assert isinstance(s, str)
            assert len(s) > 0

    def test_modes_for_voice(self):
        # Phase 269: all non-EXPERT modes are TOMOKO; only EXPERT is STRICT.
        assert set(modes_for_voice(ToneVoice.TOMOKO)) == {
            CoachMode.BEGINNER,
            CoachMode.INTERMEDIATE,
            CoachMode.DAN,
            CoachMode.ADVANCED,
        }
        assert modes_for_voice(ToneVoice.TOMOKO_STRICT) == (CoachMode.EXPERT,)


# --- Public API ---


class TestAyakaRemoved:
    """Phase 269: AYAKA voice removed entirely."""

    def test_ayaka_removed_from_enum(self):
        assert not hasattr(ToneVoice, "AYAKA")
        assert {v.name for v in ToneVoice} == {"TOMOKO", "TOMOKO_STRICT"}
