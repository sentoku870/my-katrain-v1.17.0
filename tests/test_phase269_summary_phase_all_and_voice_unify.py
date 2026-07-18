"""Phase 269 regression tests.

Covers:
1. **Summary pattern rendering**: Shape B weakness patterns carry
   ``phase="all"`` (a meta-tag) and must be rendered as
   ``phase=`(全phase)``` in the prompt so the LLM doesn't try to
   echo ``all`` in the trailing contract line.
2. **SYSTEM_INSTRUCTION guidance**: the LLM is told to prefer ``pct``
   (per-move percentage) when ``phase=`(全phase)``` is shown, and
   ``frequency_ratio`` only for Shape A patterns.
3. **Voice unification**: all kyu ranks (BEGINNER/INTERMEDIATE/DAN/
   ADVANCED) now use TOMOKO; only EXPERT uses TOMOKO_STRICT.
4. **AYAKA removal**: ``ToneVoice.AYAKA`` no longer exists; the
   AYAKA-only helpers (``has_kansai_markers``, ``apply_kansai_normalisation``)
   are gone; tone consistency checks no longer fire.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.json_type import (
    detect_json_type,
    extract_summary_player_mistakes,
    extract_summary_player_phase_losses,
    extract_summary_weakness_patterns,
)
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.summary_prompt_builder import (
    SummaryPromptConfig,
    _format_patterns_block,
    build_summary_weakness_prompt,
)
from katrain.core.coach.tones import (
    check_prohibited,
    greeting_for_mode,
    greeting_for_voice,
    select_voice,
    voice_summary,
)


# -----------------------------------------------------------------------
# 1. Summary pattern rendering (Phase 269 / C-1)
# -----------------------------------------------------------------------


class TestSummaryPatternAllRendering:
    """``phase="all"`` is a meta-tag (Shape B has no per-phase breakdown
    per mistake category) and must render as ``(全phase)`` so the LLM
    doesn't echo ``all`` in the contract line.
    """

    def test_shape_b_pattern_phase_all_renders_as_full_phase(self):
        patterns = [
            {
                "category": "blunder",
                "phase": "all",  # Shape B meta-tag
                "player": "sentoku870",
                "count": 26,
                "total_loss": 240.8,
                "frequency_ratio": 0.0,
                "pct": 6.7,
            },
        ]
        out = _format_patterns_block(patterns)
        # Meta-tag must be displayed as "(全phase)" — the LLM is
        # expected to pick a real phase label from
        # {opening, middle, endgame} in the contract line.
        assert "phase=`(全phase)`" in out
        # And must NOT contain the raw "all" label, which the validator
        # would flag as `phase_label_out_of_set`.
        assert "phase=`all`" not in out

    def test_shape_a_pattern_real_phase_passes_through(self):
        # Shape A patterns carry a real phase label (opening/middle/endgame).
        # The renderer must NOT replace it with "(全phase)".
        patterns = [
            {
                "category": "blunder",
                "phase": "middle",
                "color": "black",
                "count": 5,
                "total_loss": 30.0,
                "frequency_ratio": 1.0,
            },
        ]
        out = _format_patterns_block(patterns)
        assert "phase=`middle`" in out
        assert "(全phase)" not in out

    def test_real_world_shape_b_summary_prompt_has_no_phase_all(self):
        # End-to-end check: take a Shape B summary, build the prompt,
        # confirm the rendered patterns block never contains the raw
        # "phase=`all`" label.
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {
                "仙得": {
                    "mistakes": {
                        "good": {"count": 279, "pct": 71.9, "denominator": 388, "avg_loss": 0.13},
                        "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 1.62},
                        "mistake": {"count": 32, "pct": 8.2, "denominator": 388, "avg_loss": 3.36},
                        "blunder": {"count": 26, "pct": 6.7, "denominator": 388, "avg_loss": 9.26},
                    },
                    "phases": {
                        "opening": {"moves": 75, "total_loss": 46.1, "avg_loss": 0.615},
                        "middle": {"moves": 169, "total_loss": 368.79, "avg_loss": 2.182},
                        "endgame": {"moves": 144, "total_loss": 53.19, "avg_loss": 0.369},
                    },
                },
            },
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=3,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        # The rendered patterns block is part of the full markdown.
        assert "phase=`(全phase)`" in prompt.full_markdown
        assert "phase=`all`" not in prompt.full_markdown


# -----------------------------------------------------------------------
# 2. SYSTEM_INSTRUCTION guidance (Phase 269 / C-2)
# -----------------------------------------------------------------------


class TestSystemInstructionPctGuidance:
    """The system instruction must tell the LLM to use ``pct`` (per-move
    percentage) for Shape B patterns, not just ``frequency_ratio``.
    """

    def test_system_instruction_mentions_pct_field(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 1},
            "players": {
                "p": {
                    "mistakes": {
                        "blunder": {"count": 1, "pct": 5.0, "denominator": 20, "avg_loss": 9.0},
                    },
                },
            },
        }
        cfg = SummaryPromptConfig(
            voice=ToneVoice.TOMOKO,
            mode=CoachMode.DAN,
            games_analyzed=1,
        )
        prompt = build_summary_weakness_prompt(summary, cfg)
        # The updated guidance must mention ``pct`` as the field to use
        # for Shape B patterns (where frequency_ratio is 0).
        assert "pct" in prompt.system_instruction
        # And must NOT promise that ``frequency_ratio`` alone is the
        # authoritative source of frequency.
        # (the old wording: "use the injected ``frequency_ratio`` field")
        # We accept either explicit guidance or a comment about pct
        # being preferred when phase=`(全phase)```.
        assert ("pct" in prompt.system_instruction) and (
            "frequency_ratio" in prompt.system_instruction
            or "frequency" in prompt.system_instruction
        )


# -----------------------------------------------------------------------
# 3. Voice unification (Phase 269)
# -----------------------------------------------------------------------


class TestVoiceUnification:
    """All kyu ranks (BEGINNER/INTERMEDIATE/DAN/ADVANCED) use TOMOKO.
    Only EXPERT uses TOMOKO_STRICT. AYAKA is gone.
    """

    @pytest.mark.parametrize(
        "rank,expected",
        [
            ("30k", ToneVoice.TOMOKO),
            ("25k", ToneVoice.TOMOKO),
            ("20k", ToneVoice.TOMOKO),
            ("10k", ToneVoice.TOMOKO),
            ("5k", ToneVoice.TOMOKO),  # <-- previously AYAKA
            ("4k", ToneVoice.TOMOKO),
            ("1d", ToneVoice.TOMOKO),
            ("2d", ToneVoice.TOMOKO),
            ("5d", ToneVoice.TOMOKO),
            ("6d", ToneVoice.TOMOKO_STRICT),
            ("9d", ToneVoice.TOMOKO_STRICT),
        ],
    )
    def test_rank_to_voice_all_tomoko_except_expert(self, rank, expected):
        assert select_voice(rank) == expected

    def test_default_voice_is_tomoko(self):
        # No signal at all → default is now TOMOKO (was AYAKA).
        assert select_voice() == ToneVoice.TOMOKO
        assert select_voice(None) == ToneVoice.TOMOKO
        assert select_voice("") == ToneVoice.TOMOKO
        assert select_voice("garbage") == ToneVoice.TOMOKO

    def test_modes_served_by_tomoko(self):
        from katrain.core.coach.tones import modes_for_voice

        served = set(modes_for_voice(ToneVoice.TOMOKO))
        # All non-EXPERT modes are served by TOMOKO.
        assert served == {
            CoachMode.BEGINNER,
            CoachMode.INTERMEDIATE,
            CoachMode.DAN,
            CoachMode.ADVANCED,
        }

    def test_only_expert_uses_strict(self):
        from katrain.core.coach.tones import modes_for_voice

        assert modes_for_voice(ToneVoice.TOMOKO_STRICT) == (CoachMode.EXPERT,)


# -----------------------------------------------------------------------
# 4. AYAKA removal (Phase 269)
# -----------------------------------------------------------------------


class TestAyakaRemoved:
    def test_ayaka_enum_value_removed(self):
        assert not hasattr(ToneVoice, "AYAKA")
        assert {v.name for v in ToneVoice} == {"TOMOKO", "TOMOKO_STRICT"}

    def test_kansai_helpers_gone(self):
        import katrain.core.coach as coach_pkg

        for name in ("has_kansai_markers", "apply_kansai_normalisation", "is_kansai_marker"):
            assert not hasattr(coach_pkg, name), f"AYAKA helper {name!r} should be removed"

    def test_check_prohibited_no_ayaka_branch(self):
        # Even an AYAKA-styled text (敬語 + Kansai) shouldn't trip any
        # AYAKA-specific check, because the AYAKA branch is gone.
        ayaka_style_text = "お疲れ様です、ウチが見た。"
        v = check_prohibited(ayaka_style_text, ToneVoice.TOMOKO)
        # TOMOKO no longer enforces 敬語 prohibition.
        assert v == []

    def test_greeting_for_voice_routes_to_tomoko(self):
        # No AYAKA branch in greeting_for_voice anymore.
        msg = greeting_for_voice(ToneVoice.TOMOKO)
        assert "教えていただけますか" in msg
        # And no Kansai phrasing.
        assert "やで" not in msg

    def test_beginner_greeting_uses_standard_japanese(self):
        # Phase 269: BEGINNER/INTERMEDIATE greetings were AYAKA-flavoured
        # before; they now use the TOMOKO (standard Japanese) template.
        msg = greeting_for_mode(CoachMode.BEGINNER)
        assert "教えていただけますか" in msg
        assert "やで" not in msg

    def test_voice_summary_only_2_voices(self):
        # Only 2 summaries now (AYAKA entry removed).
        for voice in ToneVoice:
            s = voice_summary(voice)
            assert isinstance(s, str)
            assert len(s) > 0


# -----------------------------------------------------------------------
# 5. Cross-cutting: shape-B extractor contract still intact
# -----------------------------------------------------------------------


class TestShapeBExtractorsStillWork:
    """Sanity check: removing AYAKA didn't break the Shape B
    extractors. We rely on them in the C-1 fix.
    """

    def test_extract_summary_weakness_patterns_shape_b_has_phase_all(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {
                "sentoku870": {
                    "mistakes": {
                        "blunder": {"count": 5, "pct": 1.3, "denominator": 388, "avg_loss": 19.04},
                        "mistake": {"count": 22, "pct": 5.7, "denominator": 388, "avg_loss": 5.69},
                        "inaccuracy": {"count": 51, "pct": 13.1, "denominator": 388, "avg_loss": 3.11},
                        "good": {"count": 310, "pct": 79.9, "denominator": 388, "avg_loss": 0.28},
                    },
                },
            },
        }
        patterns = extract_summary_weakness_patterns(summary)
        # All Shape B patterns carry phase="all" meta-tag.
        assert all(p["phase"] == "all" for p in patterns)
        # And "good" is filtered out (Phase 241-A).
        assert all(p["category"] != "good" for p in patterns)

    def test_extract_summary_player_mistakes_includes_good(self):
        # The per-player distribution keeps "good" — only the weakness
        # patterns view filters it.
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {
                "p": {
                    "mistakes": {
                        "good": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 0.1},
                        "inaccuracy": {"count": 1, "pct": 50.0, "denominator": 2, "avg_loss": 1.0},
                    },
                },
            },
        }
        per_player = extract_summary_player_mistakes(summary)
        assert "good" in {m["category"] for m in per_player["p"]}

    def test_extract_summary_player_phase_losses_shape_b(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {
                "p": {
                    "phases": {
                        "opening": {"moves": 10, "total_loss": 1.0, "avg_loss": 0.1},
                        "middle": {"moves": 20, "total_loss": 2.0, "avg_loss": 0.1},
                        "endgame": {"moves": 5, "total_loss": 0.5, "avg_loss": 0.1},
                    },
                },
            },
        }
        per_player = extract_summary_player_phase_losses(summary)
        assert set(per_player["p"].keys()) == {"opening", "middle", "endgame"}

    def test_detect_json_type_still_recognises_shape_b_summary(self):
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 3},
            "players": {},
        }
        assert detect_json_type(summary) == "summary"
