"""Phase 242-E: Tests for the Kivy-free popup logic helpers.

These tests run in headless CI without Kivy. They exercise the pure
decision logic that the LLM Coach popup uses internally, so the
popup's display-only behaviour is covered even when the popup
itself can't be instantiated in a window-less environment.
"""

from __future__ import annotations

import json
from pathlib import Path

from katrain.core.coach.popup_logic import (
    MAX_RESPONSE_INPUT_CHARS,
    PERSPECTIVE_AUTO,
    PERSPECTIVE_BLACK,
    PERSPECTIVE_WHITE,
    SUMMARY_BIRDSEYE_SENTINEL,
    _summary_index_to_internal,
    cap_response_text,
    count_issue_markers,
    detect_path_type_from_file,
    format_type_label,
    format_validation_status_summary,
    is_summary_birdseye_value,
    resolve_player_color_internal,
    resolve_summary_rank,
    resolve_summary_spinner_values,
    was_truncated,
)

# --- Constants ---------------------------------------------------------


class TestConstants:
    def test_perspective_auto_value(self):
        assert PERSPECTIVE_AUTO == "auto"

    def test_perspective_black_value(self):
        assert PERSPECTIVE_BLACK == "B"

    def test_perspective_white_value(self):
        assert PERSPECTIVE_WHITE == "W"

    def test_birdseye_sentinel_value(self):
        assert SUMMARY_BIRDSEYE_SENTINEL == "__birdseye__"

    def test_max_response_input_chars(self):
        # 100k is well above realistic LLM outputs (~10-30k) and
        # matches the validator's report size cap.
        assert MAX_RESPONSE_INPUT_CHARS == 100_000


# --- resolve_player_color_internal -------------------------------------


class TestResolvePlayerColor:
    def test_explicit_black(self):
        assert resolve_player_color_internal(PERSPECTIVE_BLACK, "W") == "B"

    def test_explicit_white(self):
        assert resolve_player_color_internal(PERSPECTIVE_WHITE, "B") == "W"

    def test_auto_with_detected_black(self):
        assert resolve_player_color_internal(PERSPECTIVE_AUTO, "B") == "B"

    def test_auto_with_detected_white(self):
        assert resolve_player_color_internal(PERSPECTIVE_AUTO, "W") == "W"

    def test_auto_without_detected(self):
        assert resolve_player_color_internal(PERSPECTIVE_AUTO, None) is None

    def test_empty_string_treated_as_auto(self):
        # StringProperty cannot store None so the popup uses "" as
        # a sentinel for auto. The helper normalises this.
        assert resolve_player_color_internal("", "B") == "B"
        assert resolve_player_color_internal("", None) is None

    def test_garbage_value_falls_back_to_detected(self):
        # Defensive: anything that's not B/W/auto falls back to
        # the detected color (so a stale spinner state doesn't
        # crash the popup).
        assert resolve_player_color_internal("garbage", "B") == "B"
        assert resolve_player_color_internal("garbage", None) is None


# --- is_summary_birdseye_value ------------------------------------------


class TestIsSummaryBirdseye:
    def test_sentinel_is_birdseye(self):
        assert is_summary_birdseye_value(SUMMARY_BIRDSEYE_SENTINEL) is True

    def test_none_is_not_birdseye(self):
        # No value at all is a bug state, not bird's-eye.
        assert is_summary_birdseye_value(None) is False

    def test_empty_string_is_not_birdseye(self):
        assert is_summary_birdseye_value("") is False

    def test_player_name_is_not_birdseye(self):
        assert is_summary_birdseye_value("alice") is False


# --- _summary_index_to_internal -----------------------------------------


class TestSummaryIndexToInternal:
    def test_index_zero_is_birdseye(self):
        players = [("alice", "5k"), ("bob", None)]
        assert _summary_index_to_internal(0, players) == SUMMARY_BIRDSEYE_SENTINEL

    def test_negative_index_is_birdseye(self):
        players = [("alice", "5k")]
        assert _summary_index_to_internal(-1, players) == SUMMARY_BIRDSEYE_SENTINEL

    def test_index_one_maps_to_first_player(self):
        players = [("alice", "5k"), ("bob", None)]
        assert _summary_index_to_internal(1, players) == "alice"

    def test_index_n_maps_to_nth_player(self):
        players = [("alice", "5k"), ("bob", None), ("carol", "3d")]
        assert _summary_index_to_internal(2, players) == "bob"
        assert _summary_index_to_internal(3, players) == "carol"

    def test_index_out_of_range_returns_none(self):
        players = [("alice", "5k")]
        assert _summary_index_to_internal(2, players) is None
        assert _summary_index_to_internal(100, players) is None

    def test_empty_players_returns_none(self):
        assert _summary_index_to_internal(1, []) is None
        assert _summary_index_to_internal(0, []) == SUMMARY_BIRDSEYE_SENTINEL


# --- resolve_summary_spinner_values -------------------------------------


class TestResolveSummarySpinnerValues:
    def test_no_players_no_match(self):
        values, default_index = resolve_summary_spinner_values(players=[], matched_player=None)
        assert values == ["全体俯瞰"]
        assert default_index == 0

    def test_single_player_no_match(self):
        players = [("alice", "5k")]
        values, default_index = resolve_summary_spinner_values(players=players)
        assert values == ["全体俯瞰", "alice (5k)"]
        assert default_index == 0  # no matched_player, birdseye

    def test_single_player_with_match(self):
        players = [("alice", "5k")]
        values, default_index = resolve_summary_spinner_values(players=players, matched_player="alice")
        assert values == ["全体俯瞰", "alice (5k)"]
        assert default_index == 1  # match → focus

    def test_multiple_players_with_match(self):
        players = [("alice", "5k"), ("bob", None), ("carol", "3d")]
        values, default_index = resolve_summary_spinner_values(players=players, matched_player="carol")
        # carol is placed first
        assert values == ["全体俯瞰", "carol (3d)", "alice (5k)", "bob"]
        assert default_index == 1

    def test_no_rank_in_label(self):
        players = [("alice", None)]
        values, _ = resolve_summary_spinner_values(players=players)
        assert values == ["全体俯瞰", "alice"]

    def test_custom_birdseye_label(self):
        values, _ = resolve_summary_spinner_values(players=[("alice", "5k")], birdseye_label="Bird's-eye")
        assert values[0] == "Bird's-eye"


# --- detect_path_type_from_file -----------------------------------------


class TestDetectPathTypeFromFile:
    def test_karte_file(self, tmp_path: Path) -> None:
        karte = {
            "schema_version": "3.4",
            "weaknesses": {"black": [{"category": "foo", "count": 1}]},
            "important_moves": [{"meaning_tag_id": "x", "color": "black"}],
        }
        p = tmp_path / "karte.json"
        p.write_text(json.dumps(karte), encoding="utf-8")
        result = detect_path_type_from_file(str(p))
        assert result.path_type == "karte"
        assert result.schema_version == "3.4"
        assert result.games_analyzed == 0

    def test_summary_file(self, tmp_path: Path) -> None:
        summary = {
            "schema_version": "3.4",
            "meta": {"games_analyzed": 5},
            "players": {"alice": {}},
        }
        p = tmp_path / "summary.json"
        p.write_text(json.dumps(summary), encoding="utf-8")
        result = detect_path_type_from_file(str(p))
        assert result.path_type == "summary"
        assert result.schema_version == "3.4"
        assert result.games_analyzed == 5

    def test_unknown_file(self, tmp_path: Path) -> None:
        p = tmp_path / "unknown.json"
        p.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        result = detect_path_type_from_file(str(p))
        assert result.path_type == "unknown"
        assert result.schema_version is None
        assert result.games_analyzed == 0

    def test_missing_file(self) -> None:
        result = detect_path_type_from_file("/nonexistent/path.json")
        assert result.path_type == "unknown"

    def test_malformed_json(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("not json {", encoding="utf-8")
        result = detect_path_type_from_file(str(p))
        assert result.path_type == "unknown"

    def test_empty_path(self) -> None:
        result = detect_path_type_from_file("")
        assert result.path_type == "unknown"

    def test_non_dict_json(self, tmp_path: Path) -> None:
        p = tmp_path / "list.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        result = detect_path_type_from_file(str(p))
        assert result.path_type == "unknown"

    def test_schema_version_as_int(self, tmp_path: Path) -> None:
        p = tmp_path / "karte.json"
        p.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "weaknesses": {"black": []},
                    "important_moves": [{}],
                }
            ),
            encoding="utf-8",
        )
        result = detect_path_type_from_file(str(p))
        assert result.schema_version == "3"


# --- format_type_label -------------------------------------------------


class TestFormatTypeLabel:
    def test_karte_no_version(self):
        assert format_type_label("karte") == "単局カルテ"

    def test_karte_with_version(self):
        assert format_type_label("karte", schema_version="3.4") == "単局カルテ · Schema 3.4"

    def test_summary_no_version(self):
        assert format_type_label("summary", games_analyzed=5) == "複数局サマリ (5局)"

    def test_summary_with_version(self):
        assert format_type_label("summary", games_analyzed=5, schema_version="3.4") == "複数局サマリ (5局) · Schema 3.4"

    def test_unknown(self):
        assert format_type_label("unknown") == "(未確定)"

    def test_unknown_with_version(self):
        # Even unknown paths surface the schema version so the user
        # can see which JSON they have open.
        assert format_type_label("unknown", schema_version="3.4") == "(未確定) · Schema 3.4"

    def test_custom_labels(self):
        assert format_type_label("karte", single_label="Single Game") == "Single Game"
        assert format_type_label("summary", games_analyzed=10, multi_label="Multi ({games})") == "Multi (10)"


# --- count_issue_markers -----------------------------------------------


class TestCountIssueMarkers:
    def test_empty(self):
        assert count_issue_markers("") == (0, 0, 0)

    def test_single_high(self):
        h, m, low = count_issue_markers("- [HIGH] unknown: foo")
        assert h == 1
        assert m == 0
        assert low == 0

    def test_mixed(self):
        md = """
- [HIGH] unknown: foo
- [MEDIUM] outlier: bar
- [LOW] tone: baz
- [HIGH] unknown: qux
"""
        h, m, low = count_issue_markers(md)
        assert h == 2
        assert m == 1
        assert low == 1


# --- was_truncated ------------------------------------------------------


class TestWasTruncated:
    def test_truncated_marker_detected(self):
        from katrain.core.lang import i18n

        marker = i18n._("mykatrain:llm-coach:truncated")
        assert marker
        assert was_truncated(f"content\n\n{marker}")

    def test_clean_report_not_detected(self):
        assert not was_truncated("normal report without truncation")

    def test_empty_string(self):
        assert not was_truncated("")


# --- format_validation_status_summary -----------------------------------


class TestFormatValidationStatusSummary:
    def test_clean_no_issues(self):
        s = format_validation_status_summary(is_clean=True, high=0, medium=0, low=0)
        # Clean status is a positive message (Japanese: "検証クリア" / English: "Clean").
        # We don't assert specific text (i18n) but we assert it doesn't
        # include any issue count.
        assert "0" not in s
        assert "件" not in s  # Japanese for "issues"

    def test_clean_with_notes(self):
        s = format_validation_status_summary(is_clean=True, high=0, medium=0, low=1)
        assert "1" in s  # 1 issue still mentioned as a note

    def test_dirty_with_issues(self):
        s = format_validation_status_summary(is_clean=False, high=2, medium=3, low=1)
        assert "2" in s
        assert "3" in s
        assert "1" in s
        # The "total=6" pattern is also expected
        assert "6" in s

    def test_truncation_warning_prepended(self):
        clean = format_validation_status_summary(is_clean=True, high=0, medium=0, low=0)
        truncated = format_validation_status_summary(is_clean=True, high=0, medium=0, low=0, truncated=True)
        # Truncation warning is prepended/wrapped
        assert len(truncated) > len(clean)
        # The base status should still be in the truncated version
        assert clean in truncated


# --- cap_response_text --------------------------------------------------


class TestCapResponseText:
    def test_within_limit(self):
        text = "a" * 1000
        result, status = cap_response_text(text)
        assert result == text
        assert status is None

    def test_at_limit(self):
        text = "a" * MAX_RESPONSE_INPUT_CHARS
        result, status = cap_response_text(text)
        assert result == text
        assert status is None

    def test_over_limit(self):
        text = "a" * (MAX_RESPONSE_INPUT_CHARS + 1000)
        result, status = cap_response_text(text)
        assert len(result) == MAX_RESPONSE_INPUT_CHARS
        assert status is not None
        assert str(MAX_RESPONSE_INPUT_CHARS + 1000) in status

    def test_empty(self):
        result, status = cap_response_text("")
        assert result == ""
        assert status is None


# --- Phase 269 follow-up: resolve_summary_rank ------------------------


class TestResolveSummaryRank:
    """Priority chain for the Summary path:

    1. general_player_rank (the analysis-tab global setting) — what
       the user explicitly told the engine to use
    2. info["matched_player"].rank (Summary JSON's matched player) —
       fallback inferred rank
    3. default_user_rank (Phase 225.8 legacy fallback)

    These tests pin the contract that prevents a "5k" inferred from
    the Summary JSON from clobbering the user's "4d" global setting.
    """

    def test_general_player_rank_wins_over_matched_rank(self):
        # Direct regression for the user bug report
        # 「解析設定の棋力欄に 4d と入力してあっても INTERMEDIATE になる」
        info = {"matched_player": {"name": "仙得", "rank": "5k"}}
        assert resolve_summary_rank(info, general_player_rank="4d", default_user_rank="1k") == "4d"

    def test_matched_player_rank_used_when_no_general(self):
        info = {"matched_player": {"name": "仙得", "rank": "5k"}}
        assert resolve_summary_rank(info, general_player_rank="", default_user_rank="1k") == "5k"

    def test_default_user_rank_used_when_no_general_no_matched(self):
        info = {"matched_player": {"name": "仙得"}}  # no rank
        assert resolve_summary_rank(info, general_player_rank="", default_user_rank="1k") == "1k"

    def test_all_empty_returns_none(self):
        info = {"matched_player": {"name": "仙得"}}
        assert resolve_summary_rank(info, general_player_rank="", default_user_rank="") is None

    def test_none_info_falls_through_to_general(self):
        assert resolve_summary_rank(None, general_player_rank="4d", default_user_rank="1k") == "4d"

    def test_none_info_no_general_falls_through_to_default(self):
        assert resolve_summary_rank(None, general_player_rank="", default_user_rank="1k") == "1k"

    def test_user_reported_bug_4d_settings_honoured(self):
        # Direct regression: 4d in analysis settings wins over 5k
        # inferred from the Summary JSON.
        info = {"matched_player": {"name": "仙得", "rank": "5k"}}
        result = resolve_summary_rank(info, general_player_rank="4d", default_user_rank="")
        assert result == "4d"
        assert result != "5k"

    def test_empty_matched_rank_falls_through_to_general(self):
        info = {"matched_player": {"name": "仙得", "rank": ""}}
        assert resolve_summary_rank(info, general_player_rank="4d", default_user_rank="1k") == "4d"

    def test_kanji_rank_preserved(self):
        info = {"matched_player": {"rank": "4段"}}
        # We don't parse — just pass through.
        assert resolve_summary_rank(info) == "4段"


# --- Public API export check --------------------------------------------
