"""Phase 207: Tests for katrain.core.coach.master_db.

Covers:
- Enum completeness
- ModeConfig / ToneConfig data integrity
- estimate_mode_from_rank (kyu/dan parsing, edge cases)
- estimate_mode_from_loss (correction-only contract)
- Kansai dictionary coverage for AYAKA

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
        assert len(list(ToneVoice)) == 3  # §1-1 specifies 3 voices

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
        # §0-3: BEGINNER/INTERMEDIATE → AYAKA; DAN/ADVANCED → TOMOKO; EXPERT → TOMOKO_STRICT
        expected = {
            CoachMode.BEGINNER: ToneVoice.AYAKA,
            CoachMode.INTERMEDIATE: ToneVoice.AYAKA,
            CoachMode.DAN: ToneVoice.TOMOKO,
            CoachMode.ADVANCED: ToneVoice.TOMOKO,
            CoachMode.EXPERT: ToneVoice.TOMOKO_STRICT,
        }
        for mode, expected_voice in expected.items():
            assert get_mode_config(mode).voice == expected_voice


class TestToneConfig:
    def test_all_tones_returns_3(self):
        tones = all_tones()
        assert len(tones) == 3
        assert {t.voice for t in tones} == set(ToneVoice)

    def test_get_tone_config_roundtrip(self):
        for voice in ToneVoice:
            cfg = get_tone_config(voice)
            assert cfg.voice == voice
            assert isinstance(cfg, ToneConfig)
            assert cfg.label_jp
            assert cfg.characteristics_jp

    def test_ayaka_has_kansai_dictionary(self):
        ayaka = get_tone_config(ToneVoice.AYAKA)
        assert ayaka.dialect == "kansai"
        assert ayaka.kansai_dictionary
        assert "ダメ" in ayaka.kansai_dictionary
        assert ayaka.kansai_dictionary["ダメ"] == "あかん"

    def test_tomoko_lacks_kansai_dictionary(self):
        for voice in (ToneVoice.TOMOKO, ToneVoice.TOMOKO_STRICT):
            cfg = get_tone_config(voice)
            assert cfg.dialect.startswith("standard")
            assert cfg.kansai_dictionary == {}

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


class TestExports:
    def test_init_reexports_match_master_db(self):
        import katrain.core.coach as pkg
        import katrain.core.coach.master_db as md

        for name in [
            "CoachMode",
            "ToneVoice",
            "RankRange",
            "ModeConfig",
            "ToneConfig",
            "get_mode_config",
            "get_tone_config",
            "all_modes",
            "all_tones",
            "estimate_mode_from_rank",
            "estimate_mode_from_loss",
        ]:
            assert hasattr(pkg, name), f"__init__ missing {name}"
            assert hasattr(md, name), f"master_db missing {name}"


# --- Phase 242-A: Kansai dictionary sync tests ---


class TestKansaiDictionarySync:
    """Phase 242-A: every entry in _KANSAI_DICTIONARY must be substitutable.

    The user-facing dictionary in master_db.py is paired with the
    NORM regex pairs in tones.py. Before Phase 242-A there were 13
    sync gaps: 6 dict_keys with no NORM entry, 7 NORM entries with
    no dict entry. These tests pin the contract that ``apply_kansai_normalisation``
    must actually substitute every dictionary key.
    """

    def test_all_dict_keys_substitutable(self):
        """Every key in _KANSAI_DICTIONARY must be in NORM pairs.

        Previously: '〜ください' / '〜してた' / '〜である/〜だ' /
        '〜ですか？' / '〜ではない' / '良い/いい' were missing.
        """
        from katrain.core.coach.master_db import _KANSAI_DICTIONARY
        from katrain.core.coach.tones import _KANSAI_NORMALISATION_PAIRS

        pair_srcs = {src for src, _ in _KANSAI_NORMALISATION_PAIRS}
        # Split 良い/いい to handle the OR syntax
        for key in _KANSAI_DICTIONARY:
            alternatives = key.split("/")
            assert any(alt in pair_srcs for alt in alternatives), (
                f"dict_key {key!r} is not substitutable "
                f"(no NORM pair matches any of its alternatives {alternatives!r})"
            )

    def test_all_norm_entries_documented(self):
        """Every src in NORM pairs should be in the user-facing dict.

        Previously: 'だめ' / 'いい' / 'してください' / '本当' /
        '良い' / 'している' / 'ください' were in NORM but not in DICT.
        """
        from katrain.core.coach.master_db import _KANSAI_DICTIONARY
        from katrain.core.coach.tones import _KANSAI_NORMALISATION_PAIRS

        dict_keys = set(_KANSAI_DICTIONARY.keys())
        for src, _dst in _KANSAI_NORMALISATION_PAIRS:
            # 〜-prefixed sources are documented as a single OR key in dict
            base = src.lstrip("〜").split("/")[0]
            assert base in dict_keys or src in dict_keys, (
                f"NORM src {src!r} is not in the user-facing dictionary"
            )

    def test_normalise_with_tilde_prefix(self):
        """〜-prefixed patterns should be substitutable (Phase 242-A fix)."""
        from katrain.core.coach.tones import apply_kansai_normalisation

        out = apply_kansai_normalisation("私 が〜ください")
        assert "〜してな" in out or "〜しとき" in out
        out2 = apply_kansai_normalisation("私 が〜ですか？")
        assert "〜なん" in out2 or "〜か？" in out2

    def test_normalise_lowercase_dame(self):
        """Lowercase 'だめ' should be substituted (Phase 242-A fix)."""
        from katrain.core.coach.tones import apply_kansai_normalisation

        out = apply_kansai_normalisation("これがだめ")
        assert "あかん" in out

    def test_normalise_split_ii(self):
        """'いい' and '良い' both map to 'ええ' (Phase 242-A fix)."""
        from katrain.core.coach.tones import apply_kansai_normalisation

        out_good = apply_kansai_normalisation("これは良い")
        out_nice = apply_kansai_normalisation("これはいい")
        assert "ええ" in out_good
        assert "ええ" in out_nice

    def test_honma_ni_is_detected_as_marker(self):
        """Phase 242-A: 'ほんまに' should be a marker.

        Previously substring matching via 'ほんま' worked, but
        explicit marker entry is more robust and self-documenting.
        """
        from katrain.core.coach.tones import _AYAKA_MARKERS, has_kansai_markers

        assert "ほんまに" in _AYAKA_MARKERS
        assert has_kansai_markers("ほんまにええやん")
        assert has_kansai_markers("ほんまええやん")  # substring fallback

    def test_new_normalisation_targets_detectable(self):
        """All NORM destinations should be detected by has_kansai_markers.

        Substring-aware check: every destination must contain at least
        one marker as a substring. Previously 'ほんまに' lacked an
        explicit marker (worked only by substring luck).
        """
        from katrain.core.coach.tones import (
            _KANSAI_NORMALISATION_PAIRS,
            has_kansai_markers,
        )

        for _src, dst in _KANSAI_NORMALISATION_PAIRS:
            assert has_kansai_markers(dst), (
                f"destination {dst!r} has no marker substring"
            )
