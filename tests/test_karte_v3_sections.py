"""Tests for Phase 149 C-3 Karte JSON v3.0 + Phase 153 (3.1) extended sections.

Phase 153: Removed the following sections from v3.1 output:
- difficulty (per-MistakeItem field)
- practice_priorities
- common_difficult_positions
- urgent_misses (merged into mistake_streaks)
- meta.definitions (now opt-in via include_definitions=True)

Covers (Phase 149 C-3 originals, minus removed sections):
- weaknesses section structure
- mistake_streaks section structure
- critical_3 section structure
- data_quality section structure
- reason_tags_distribution section structure
- Schema version bumped to 3.1
"""

from __future__ import annotations


class TestKarteV3SchemaVersion:
    """Schema version should be 3.1 in v3.1 JSON output (Phase 153)."""

    def test_schema_version_is_3_1(self):
        from katrain.core.reports.karte import build_karte_json

        from tests.test_karte_json import create_mock_game_with_analysis

        game = create_mock_game_with_analysis()
        result = build_karte_json(game)
        assert result["schema_version"] == "3.1"


class TestKarteV3ExtendedSectionsPresent:
    """All v3.1 extended sections should be present in build_karte_json output."""

    def _get_karte_v3(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        return build_karte_json(create_mock_game_with_analysis())

    def test_weaknesses_section(self):
        result = self._get_karte_v3()
        assert "weaknesses" in result
        assert "black" in result["weaknesses"]
        assert "white" in result["weaknesses"]
        assert isinstance(result["weaknesses"]["black"], list)
        assert isinstance(result["weaknesses"]["white"], list)

    def test_mistake_streaks_section(self):
        result = self._get_karte_v3()
        assert "mistake_streaks" in result
        assert "black" in result["mistake_streaks"]
        assert "white" in result["mistake_streaks"]

    def test_critical_3_section(self):
        result = self._get_karte_v3()
        assert "critical_3" in result
        assert "black" in result["critical_3"]
        assert "white" in result["critical_3"]

    def test_data_quality_section(self):
        result = self._get_karte_v3()
        assert "data_quality" in result
        dq = result["data_quality"]
        # Required keys per DataQualityStats TypedDict
        required_keys = {
            "confidence_level",
            "total_moves",
            "moves_with_visits",
            "coverage_pct",
            "reliable_count",
            "reliability_pct",
            "low_confidence_count",
            "low_confidence_pct",
            "avg_visits",
            "max_visits",
            "effective_threshold",
            "is_low_reliability",
        }
        assert required_keys.issubset(set(dq.keys())), (
            f"Missing keys: {required_keys - set(dq.keys())}"
        )

    def test_reason_tags_distribution_section(self):
        result = self._get_karte_v3()
        assert "reason_tags_distribution" in result
        assert "black" in result["reason_tags_distribution"]
        assert "white" in result["reason_tags_distribution"]

    # --- Phase 153-B/C: removed sections should NOT be present ---
    def test_practice_priorities_removed(self):
        """Phase 153-B: practice_priorities removed from output."""
        result = self._get_karte_v3()
        assert "practice_priorities" not in result

    def test_common_difficult_positions_removed(self):
        """Phase 153-B: common_difficult_positions removed from output."""
        result = self._get_karte_v3()
        assert "common_difficult_positions" not in result

    def test_urgent_misses_removed(self):
        """Phase 153-C: urgent_misses merged into mistake_streaks."""
        result = self._get_karte_v3()
        assert "urgent_misses" not in result


class TestKarteV3WeaknessItemShape:
    """Validate WeaknessItem shape (Phase 149 C-3)."""

    def test_weakness_item_fields(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())

        # At least one weakness should exist (or empty list, both valid)
        for player in ("black", "white"):
            weaknesses = result["weaknesses"][player]
            for w in weaknesses:
                # Required fields
                assert "phase" in w
                assert "category" in w
                assert "count" in w
                assert "total_loss" in w
                assert "avg_loss" in w
                assert "confidence" in w
                assert "evidence" in w
                # Type checks
                assert w["phase"] in ("opening", "middle", "endgame", "yose")
                assert w["category"] in ("BLUNDER", "MISTAKE", "INACCURACY")
                assert w["confidence"] in ("low", "medium", "high")
                assert isinstance(w["count"], int)
                assert isinstance(w["evidence"], list)


class TestKarteV3Critical3ItemShape:
    """Validate CriticalMoveItem shape (Phase 149 C-3)."""

    def test_critical_3_item_fields(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())

        for player in ("black", "white"):
            items = result["critical_3"][player]
            for cm in items:
                assert "move_number" in cm
                assert "gtp_coord" in cm
                assert "player" in cm
                assert "score_loss" in cm
                assert "meaning_tag_id" in cm
                assert "game_phase" in cm
                assert "position_difficulty" in cm
                assert "area" in cm
                assert "reason_tags" in cm
                assert "complexity_discounted" in cm
                assert cm["player"] in ("B", "W")


class TestKarteV3StreakItemShape:
    """Validate StreakItem shape (Phase 149 C-3)."""

    def test_streak_item_fields(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())

        for player in ("black", "white"):
            streaks = result["mistake_streaks"][player]
            for s in streaks:
                assert "start_move" in s
                assert "end_move" in s
                assert "move_count" in s
                assert "total_loss" in s
                assert "avg_loss" in s
                assert "moves" in s
                assert isinstance(s["moves"], list)
                assert s["end_move"] >= s["start_move"]


class TestKarteV3BackwardsCompatibility:
    """v3.1 should still include v2.1 fields (additive change)."""

    def test_v21_fields_still_present(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())

        # v2.1 fields
        assert "schema_version" in result
        assert "meta" in result
        assert "summary" in result
        assert "important_moves" in result

        # meta fields
        meta = result["meta"]
        assert "schema_version" in meta
        assert "game_id" in meta
        assert "run_id" in meta
        assert "skill_preset" in meta

        # summary fields
        summary = result["summary"]
        assert "total_moves" in summary
        assert "total_points_lost" in summary
        assert "mistake_distribution" in summary


class TestKarteV3LangAgnostic:
    """v3.1 JSON output should be language-agnostic (no localized strings)."""

    def test_weaknesses_use_ids_only(self):
        """WeaknessItem should not contain localized strings."""
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis(), lang="ja")

        for player in ("black", "white"):
            for w in result["weaknesses"][player]:
                # phase and category should be IDs, not JP labels
                assert w["phase"] in ("opening", "middle", "endgame", "yose")
                # category should be uppercase enum value, not "ブランダー" etc.
                assert w["category"].isupper() or w["category"] == "GOOD"

    def test_critical_3_meaning_tag_label_present(self):
        """critical_3 may include localized meaning_tag_label for convenience."""
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis(), lang="ja")

        for player in ("black", "white"):
            for cm in result["critical_3"][player]:
                # meaning_tag_id is canonical
                assert "meaning_tag_id" in cm
                # meaning_tag_label is informational (may be None)
                assert "meaning_tag_label" in cm


class TestKarteV31DefinitionsOptIn:
    """Phase 153-D: `definitions` is opt-in via include_definitions=True."""

    def test_definitions_absent_by_default(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())
        assert result["meta"].get("definitions") is None

    def test_definitions_present_when_requested(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis(), include_definitions=True)
        definitions = result["meta"].get("definitions")
        assert definitions is not None
        assert "thresholds" in definitions
        assert "phases" in definitions
        # Phase 153-A: difficulty_levels should NOT be present (removed)
        assert "difficulty_levels" not in definitions


class TestKarteV31MistakeItemNoDifficulty:
    """Phase 153-A: MistakeItem no longer carries `difficulty` field."""

    def test_important_moves_no_difficulty_field(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())
        for mv in result["important_moves"]:
            assert "difficulty" not in mv, f"MistakeItem should not carry 'difficulty': {mv}"