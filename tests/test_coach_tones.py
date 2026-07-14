"""Phase 210: Tests for katrain.core.coach.tones.

Covers:
- select_voice (BR/WR + loss-signal fallback chain)
- greeting_for_mode / greeting_for_voice (master doc §0-2 templates)
- has_kansai_markers (AYAKA detection)
- apply_kansai_normalisation (standard → Kansai substitution)
- check_prohibited (violation detection)
- voice_summary / modes_for_voice

No Kivy — pure core-layer tests.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.tones import (
    apply_kansai_normalisation,
    check_prohibited,
    greeting_for_mode,
    greeting_for_voice,
    has_kansai_markers,
    modes_for_voice,
    select_voice,
    voice_summary,
)


# --- select_voice ---


class TestSelectVoice:
    @pytest.mark.parametrize(
        "rank,expected",
        [
            ("25k", ToneVoice.AYAKA),
            ("10k", ToneVoice.AYAKA),
            ("5k", ToneVoice.AYAKA),
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

    def test_no_signal_returns_ayaka_default(self):
        # Per Phase 203 §6.1 priority: default = beginner / AYAKA
        assert select_voice() == ToneVoice.AYAKA
        assert select_voice(None) == ToneVoice.AYAKA
        assert select_voice("") == ToneVoice.AYAKA
        assert select_voice("garbage") == ToneVoice.AYAKA

    def test_loss_signal_only(self):
        # avg=10 → adjustment down → BEGINNER → AYAKA
        assert select_voice(avg_points_lost=10.0) == ToneVoice.AYAKA

    def test_rank_takes_priority_over_loss_correction(self):
        # 7d → EXPERT → TOMOKO_STRICT even if loss is high.
        # Currently rank-estimated mode never gets downgraded by select_voice,
        # so the rank signal wins.
        voice = select_voice("7d", avg_points_lost=20.0)
        # The current implementation re-uses rank estimate only
        # without applying the loss correction on top of it. This is
        # intentional (Phase 203 §6.1 priority chain); capture behaviour.
        assert voice == ToneVoice.TOMOKO_STRICT


# --- greeting_for_mode / greeting_for_voice ---


class TestGreeting:
    def test_greeting_for_mode_beginner(self):
        msg = greeting_for_mode(CoachMode.BEGINNER)
        assert "棋力教えてもらえる" in msg
        # AYAKA-flavored phrasing
        assert "目安はこんな感じやで" in msg

    def test_greeting_for_mode_dan(self):
        msg = greeting_for_mode(CoachMode.DAN)
        assert "教えていただけますか" in msg
        # TOMOKO-flavored (no Kansai markers)
        assert "やで" not in msg

    def test_greeting_for_mode_expert(self):
        msg = greeting_for_mode(CoachMode.EXPERT)
        assert "教えていただけますか" in msg

    @pytest.mark.parametrize("mode", list(CoachMode))
    def test_greeting_for_all_modes(self, mode):
        msg = greeting_for_mode(mode)
        assert isinstance(msg, str)
        # Every greeting must contain the rank-guide or be very brief.
        assert "棋力" in msg or "段" in msg or msg == ""

    def test_include_rank_guide_false(self):
        msg = greeting_for_mode(CoachMode.BEGINNER, include_rank_guide=False)
        # Should be just the first line, no bracket guide.
        assert "目安" not in msg

    def test_greeting_for_voice_routing(self):
        msg_ayaka = greeting_for_voice(ToneVoice.AYAKA)
        msg_tomoko = greeting_for_voice(ToneVoice.TOMOKO)
        msg_strict = greeting_for_voice(ToneVoice.TOMOKO_STRICT)
        # AYAKA-flavored
        assert "やで" in msg_ayaka
        # TOMOKO and EXPERT both standard-Japanese
        assert "教えていただけますか" in msg_tomoko
        assert "教えていただけますか" in msg_strict


# --- has_kansai_markers ---


class TestKansaiMarkers:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("ウチが見た", True),
            ("あかん", True),
            ("ほんまに", True),
            ("しとる", True),
            ("せやから", True),
            ("こんにちは", False),
            ("お疲れ様です", False),
            ("", False),
        ],
    )
    def test_marker_detection(self, text, expected):
        assert has_kansai_markers(text) == expected


# --- apply_kansai_normalisation ---


class TestNormalisation:
    def test_standard_replacements(self):
        out = apply_kansai_normalisation("私がダメな手を打つ")
        assert "ウチ" in out
        assert "あかん" in out

    def test_idempotent_when_already_kansai(self):
        out = apply_kansai_normalisation("ウチがあかん")
        # Should not double-substitute (the chains are "私→ウチ" and "ダメ→あかん"),
        # so reapplying on already-normalised text is a no-op for the markers we care about.
        assert out == "ウチがあかん"

    def test_custom_mapping(self):
        out = apply_kansai_normalisation(
            "thank you",
            mapping={"thank you": "おおきに"},
        )
        assert "おおきに" in out

    def test_empty_input(self):
        assert apply_kansai_normalisation("") == ""


# --- check_prohibited ---


class TestCheckProhibited:
    def test_clean_ayaka_no_violations(self):
        v = check_prohibited("ウチが見た、この手はええね", ToneVoice.AYAKA)
        assert v == []

    def test_ayaka_with_formal_pattern_violates(self):
        v = check_prohibited("お疲れ様です。", ToneVoice.AYAKA)
        assert any("敬語" in x for x in v)

    def test_character_setup_violates(self):
        v = check_prohibited("私は囲碁コーチです", ToneVoice.AYAKA)
        assert any("キャラクター" in x for x in v)

    def test_internal_facet_token_violates(self):
        v = check_prohibited("あなたのfacet:directionに問題", ToneVoice.TOMOKO)
        assert any("facet" in x for x in v)

    def test_unfilled_template_violates(self):
        v = check_prohibited("こんにちは、{{user_name}}さん", ToneVoice.AYAKA)
        assert any("テンプレート変数" in x for x in v)

    def test_tomoko_strict_no_gentle_phrases(self):
        v = check_prohibited(
            "これを〜してみてね！",
            ToneVoice.TOMOKO_STRICT,
        )
        assert any("優しい誘導表現" in x for x in v)

    def test_empty_text_returns_empty(self):
        assert check_prohibited("", ToneVoice.AYAKA) == []


# --- voice_summary / modes_for_voice ---


class TestVoiceUtilities:
    def test_voice_summary_all(self):
        for v in ToneVoice:
            s = voice_summary(v)
            assert isinstance(s, str)
            assert len(s) > 0

    def test_modes_for_voice(self):
        assert set(modes_for_voice(ToneVoice.AYAKA)) == {
            CoachMode.BEGINNER,
            CoachMode.INTERMEDIATE,
        }
        assert set(modes_for_voice(ToneVoice.TOMOKO)) == {
            CoachMode.DAN,
            CoachMode.ADVANCED,
        }
        assert modes_for_voice(ToneVoice.TOMOKO_STRICT) == (CoachMode.EXPERT,)


# --- Public API ---


class TestExports:
    def test_all_reexports(self):
        import katrain.core.coach as pkg

        for name in [
            "select_voice",
            "greeting_for_mode",
            "greeting_for_voice",
            "has_kansai_markers",
            "apply_kansai_normalisation",
            "check_prohibited",
            "voice_summary",
            "modes_for_voice",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
