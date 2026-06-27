"""Tests for Phase 149 C-3 Karte JSON v3.0 extended sections.

Covers:
- weaknesses section structure
- practice_priorities section structure
- mistake_streaks section structure
- urgent_misses section structure
- critical_3 section structure
- data_quality section structure
- common_difficult_positions section structure
- reason_tags_distribution section structure
- Schema version bumped to 3.0
"""

from __future__ import annotations


class TestKarteV3SchemaVersion:
    """Schema version should be 3.0 in v3.0 JSON output."""

    def test_schema_version_is_3_0(self):
        from katrain.core.reports.karte_report import build_karte_report

        # Verify build_karte_json produces 3.0
        from katrain.core.reports.karte import build_karte_json

        # Use the existing test helper
        from tests.test_karte_json import create_mock_game_with_analysis

        game = create_mock_game_with_analysis()
        result = build_karte_json(game)
        assert result["schema_version"] == "3.0"


class TestKarteV3ExtendedSectionsPresent:
    """All v3.0 extended sections should be present in build_karte_json output."""

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

    def test_practice_priorities_section(self):
        result = self._get_karte_v3()
        assert "practice_priorities" in result
        assert "black" in result["practice_priorities"]
        assert "white" in result["practice_priorities"]
        assert isinstance(result["practice_priorities"]["black"], list)
        assert isinstance(result["practice_priorities"]["white"], list)

    def test_mistake_streaks_section(self):
        result = self._get_karte_v3()
        assert "mistake_streaks" in result
        assert "black" in result["mistake_streaks"]
        assert "white" in result["mistake_streaks"]

    def test_urgent_misses_section(self):
        result = self._get_karte_v3()
        assert "urgent_misses" in result
        assert "black" in result["urgent_misses"]
        assert "white" in result["urgent_misses"]

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

    def test_common_difficult_positions_section(self):
        result = self._get_karte_v3()
        assert "common_difficult_positions" in result
        assert isinstance(result["common_difficult_positions"], list)

    def test_reason_tags_distribution_section(self):
        result = self._get_karte_v3()
        assert "reason_tags_distribution" in result
        assert "black" in result["reason_tags_distribution"]
        assert "white" in result["reason_tags_distribution"]


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


class TestKarteV3CommonDifficultShape:
    """Validate CommonDifficultItem shape (Phase 149 C-3)."""

    def test_common_difficult_item_fields(self):
        from katrain.core.reports.karte import build_karte_json
        from tests.test_karte_json import create_mock_game_with_analysis

        result = build_karte_json(create_mock_game_with_analysis())

        items = result["common_difficult_positions"]
        for item in items:
            assert "move_range" in item
            assert "black_loss" in item
            assert "white_loss" in item
            assert "total_loss" in item
            assert len(item["move_range"]) == 2


class TestKarteV3BackwardsCompatibility:
    """v3.0 should still include v2.1 fields (additive change)."""

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
    """v3.0 JSON output should be language-agnostic (no localized strings)."""

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