"""Phase 207: Tests for katrain.core.coach.master_db.

Covers:
- Enum completeness
- ModeConfig / ToneConfig data integrity
- estimate_mode_from_rank (kyu/dan parsing, edge cases)
- estimate_mode_from_loss (correction-only contract)

Phase 269: AYAKA voice removed. Kansai-related data structures and
dictionary coverage tests are gone with it.

No Kivy / no external deps — pure core-layer tests.
"""

from __future__ import annotations

import pytest

from katrain.core.coach.master_db import (
    CoachMode,
    ModeConfig,
    RankRange,
    ToneConfig,
    ToneVoice,
    all_modes,
    all_tones,
    estimate_mode_from_loss,
    estimate_mode_from_rank,
    get_mode_config,
    get_tone_config,
)

# --- Enum completeness ---


class TestEnums:
    def test_coach_mode_count(self):
        assert len(list(CoachMode)) == 5  # §0-1 specifies 5 modes

    def test_coach_mode_values_unique(self):
        values = [m.value for m in CoachMode]
        assert len(values) == len(set(values))

    def test_tone_voice_count(self):
        # Phase 269: 2 voices (TOMOKO + TOMOKO_STRICT) — AYAKA removed.
        assert len(list(ToneVoice)) == 2

    def test_tone_voice_values_unique(self):
        values = [v.value for v in ToneVoice]
        assert len(values) == len(set(values))


# --- ModeConfig / ToneConfig ---


class TestModeConfig:
    def test_all_modes_returns_5(self):
        modes = all_modes()
        assert len(modes) == 5
        assert {m.mode for m in modes} == set(CoachMode)

    def test_get_mode_config_roundtrip(self):
        for mode in CoachMode:
            cfg = get_mode_config(mode)
            assert cfg.mode == mode
            assert isinstance(cfg, ModeConfig)
            assert isinstance(cfg.rank_range, RankRange)
            assert isinstance(cfg.voice, ToneVoice)
            assert cfg.label_jp  # non-empty
            assert cfg.description_jp  # non-empty

    def test_mode_voice_mapping_matches_section_0_3(self):
        # Phase 269: BEGINNER/INTERMEDIATE/DAN/ADVANCED → TOMOKO;
        # EXPERT → TOMOKO_STRICT. AYAKA removed.
        expected = {
            CoachMode.BEGINNER: ToneVoice.TOMOKO,
            CoachMode.INTERMEDIATE: ToneVoice.TOMOKO,
            CoachMode.DAN: ToneVoice.TOMOKO,
            CoachMode.ADVANCED: ToneVoice.TOMOKO,
            CoachMode.EXPERT: ToneVoice.TOMOKO_STRICT,
        }
        for mode, expected_voice in expected.items():
            assert get_mode_config(mode).voice == expected_voice


class TestToneConfig:
    def test_all_tones_returns_2(self):
        # Phase 269: 2 voices (TOMOKO + TOMOKO_STRICT).
        tones = all_tones()
        assert len(tones) == 2
        assert {t.voice for t in tones} == set(ToneVoice)

    def test_get_tone_config_roundtrip(self):
        for voice in ToneVoice:
            cfg = get_tone_config(voice)
            assert cfg.voice == voice
            assert isinstance(cfg, ToneConfig)
            assert cfg.label_jp
            assert cfg.characteristics_jp

    def test_voices_use_standard_dialect(self):
        # Phase 269: kansai_dictionary removed from ToneConfig entirely;
        # all remaining voices use a standard-Japanese dialect.
        for voice in ToneVoice:
            cfg = get_tone_config(voice)
            assert cfg.dialect.startswith("standard")

    def test_prohibited_contains_no_internal_facets(self):
        # §1-4: "内部タグ（facet等）をユーザーへの出力に含めること" prohibited
        for voice in ToneVoice:
            cfg = get_tone_config(voice)
            assert any("facet" in p for p in cfg.prohibited), f"{voice.value} missing 'facet' prohibition"


# --- estimate_mode_from_rank ---


class TestEstimateFromRank:
    @pytest.mark.parametrize(
        "rank,expected",
        [
            ("30k", CoachMode.BEGINNER),
            ("20k", CoachMode.BEGINNER),
            ("11k", CoachMode.BEGINNER),
            ("10k", CoachMode.INTERMEDIATE),
            ("9k", CoachMode.INTERMEDIATE),
            ("5k", CoachMode.INTERMEDIATE),
            ("4k", CoachMode.DAN),
            ("1k", CoachMode.DAN),
            ("1d", CoachMode.DAN),
            ("2d", CoachMode.ADVANCED),
            ("5d", CoachMode.ADVANCED),
            ("6d", CoachMode.EXPERT),
            ("9d", CoachMode.EXPERT),
        ],
    )
    def test_boundary_values(self, rank, expected):
        assert estimate_mode_from_rank(rank) == expected

    @pytest.mark.parametrize("bad", [None, "", "abc", "10D", "k10", "100k"])
    def test_invalid_returns_none(self, bad):
        assert estimate_mode_from_rank(bad) is None

    def test_case_and_whitespace_normalisation(self):
        # "  5K  " should map to INTERMEDIATE
        assert estimate_mode_from_rank("  5K  ") == CoachMode.INTERMEDIATE


# --- estimate_mode_from_loss ---


class TestEstimateFromLoss:
    def test_unknown_loss_returns_default_intermediate(self):
        # No rank, no loss → defaults to INTERMEDIATE
        # Default base is estimate_mode_from_rank("10k") = INTERMEDIATE
        result = estimate_mode_from_loss(avg_points_lost=None)
        assert result == CoachMode.INTERMEDIATE

    def test_neutral_loss_keeps_intermediate(self):
        # avg_points_lost = 5.0 → no adjustment (only > 8.0 / > 15.0 trigger)
        result = estimate_mode_from_loss(avg_points_lost=5.0)
        assert result == CoachMode.INTERMEDIATE

    def test_high_loss_pulls_down_one_step(self):
        # avg_points_lost = 10.0 → adjustment += 1 → BEGINNER
        result = estimate_mode_from_loss(avg_points_lost=10.0)
        assert result == CoachMode.BEGINNER

    def test_very_high_loss_pulls_down_two_steps(self):
        # avg_points_lost = 20.0 → adjustment += 2 → BEGINNER (already at min)
        result = estimate_mode_from_loss(avg_points_lost=20.0)
        assert result == CoachMode.BEGINNER

    def test_winrate_drop_combines_with_loss(self):
        # avg=9.0 (>8.0) + winrate_drop=25% → adjustments=2
        result = estimate_mode_from_loss(avg_points_lost=9.0, winrate_drop_pct=25.0)
        assert result == CoachMode.BEGINNER

    def test_critical_moves_with_loss(self):
        # avg=6.0 (>5.0) + critical=6 (>5) → adjustments=1
        result = estimate_mode_from_loss(avg_points_lost=6.0, critical_move_count=6)
        assert result == CoachMode.BEGINNER

    def test_critical_without_loss_signal_does_not_adjust(self):
        # avg=3.0 (no loss trigger) + critical=6 → no adjustment
        result = estimate_mode_from_loss(avg_points_lost=3.0, critical_move_count=6)
        assert result == CoachMode.INTERMEDIATE

    def test_never_upgrades_player(self):
        # Contract (Phase 203 §6.3): loss correction only downgrades.
        # Even winrate_drop alone should not move us UP from INTERMEDIATE.
        result = estimate_mode_from_loss(avg_points_lost=0.5, winrate_drop_pct=5.0)
        assert result == CoachMode.INTERMEDIATE


# --- Public API surface ---
