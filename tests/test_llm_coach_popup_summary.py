"""Summary-path tests for the LLM Coach popup.

Phase 5 of the test-suite audit extracts these from
``tests/test_llm_coach_popup.py``. They cover the popup's multi-game
summary mode added in Phase 227-D: path-type detection, summary
perspective spinner, and the ``on_generate_and_copy`` / ``on_validate``
dispatch between the karte and summary builders.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from tests.llm_coach_popup_helpers import _make_content, kivy_required

pytestmark = kivy_required


class TestDetectPathType:
    """Phase 227-D: ``_detect_path_type`` reads the JSON file and
    dispatches on the result. The set of recognised types is
    ``"karte"`` / ``"summary"`` / ``"unknown"``.
    """

    def test_karte_detected(self, tmp_path):
        from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "weaknesses": {"black": [], "white": []},
                    "important_moves": [{"meaning_tag_id": "x"}],
                }
            ),
            encoding="utf-8",
        )
        content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
        result = content._detect_path_type(str(karte))
        assert result == "karte"
        assert content.path_type == "karte"

    def test_summary_detected(self, tmp_path):
        from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 3},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {"p1": {}},
                }
            ),
            encoding="utf-8",
        )
        content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
        result = content._detect_path_type(str(summary))
        assert result == "summary"
        assert content.path_type == "summary"

    def test_missing_file_returns_unknown(self, tmp_path):
        from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

        content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
        result = content._detect_path_type(str(tmp_path / "nope.json"))
        assert result == "unknown"
        assert content.path_type == "unknown"

    def test_empty_string_returns_unknown(self):
        from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

        content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
        result = content._detect_path_type("")
        assert result == "unknown"
        assert content.path_type == "unknown"

    def test_malformed_json_returns_unknown(self, tmp_path):
        from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
        result = content._detect_path_type(str(bad))
        assert result == "unknown"


class TestRefreshTypeLabel:
    """Phase 227-D: ``_refresh_type_label`` updates the type label and
    generate button text based on the detected path type."""

    def test_empty_path_clears_label(self):
        content = _make_content()
        content._refresh_type_label()
        assert content.ids["type_label"].text == ""
        # Generate button text falls back to karte
        assert "プロンプト" in content.ids["generate_button"].text or "Prompt" in content.ids["generate_button"].text

    def test_karte_sets_single_label(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "weaknesses": {"black": [], "white": []},
                    "important_moves": [{"meaning_tag_id": "x"}],
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(karte)
        content._refresh_type_label()
        # The Japanese label or English label should be present
        label_text = content.ids["type_label"].text
        assert label_text in ("単局カルテ", "Single-game Karte")

    def test_summary_sets_multi_label_with_count(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 7},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {"p1": {}},
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(summary)
        content._refresh_type_label()
        label_text = content.ids["type_label"].text
        assert "7" in label_text
        # Generate button text changes for summary
        btn_text = content.ids["generate_button"].text
        assert "集約" in btn_text or "Summary" in btn_text

    def test_unknown_label_when_malformed(self, tmp_path):
        content = _make_content()
        bad = tmp_path / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        content.karte_path_input.text = str(bad)
        content._refresh_type_label()
        label_text = content.ids["type_label"].text
        assert label_text in ("(未確定)", "(unresolved)")


class TestUnknownPathEarlyReturn:
    """Phase 241-B: when the JSON is neither a Karte nor a Summary,
    the popup surfaces ``unknown-path`` and short-circuits.
    """

    def test_populate_rank_returns_for_unknown(self, tmp_path):
        content = _make_content(path_type="unknown")
        # Hand-written JSON that doesn't match either shape
        weird = tmp_path / "weird.json"
        weird.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        content.karte_path_input.text = str(weird)
        content._populate_rank_and_perspective()
        # Should NOT have fallen into the karte path (which would
        # call detect_player_info and overwrite the status).
        # The status label should show the unknown-path message.
        status_text = content.ids["status_label"].text
        assert "形式" in status_text or "Unrecognised" in status_text or "形式を認識" in status_text
        # path_type is set to unknown (no karte info loaded)
        assert content.path_type == "unknown"

    def test_generate_unknown_path_blocks_prompt(self, tmp_path):
        content = _make_content(path_type="unknown")
        weird = tmp_path / "weird.json"
        weird.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        content.karte_path_input.text = str(weird)
        content.on_generate_and_copy()
        status_text = content.ids["status_label"].text
        assert "形式" in status_text or "Unrecognised" in status_text or "形式を認識" in status_text
        # The result_label should not have been overwritten with a
        # prompt body
        assert content.ids["result_label"].text == ""

    def test_validate_unknown_path_blocks_validation(self, tmp_path):
        content = _make_content(path_type="unknown")
        weird = tmp_path / "weird.json"
        weird.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        content.karte_path_input.text = str(weird)
        content.ids["response_input"].text = "some LLM response"
        content.on_validate()
        status_text = content.ids["status_label"].text
        assert "形式" in status_text or "Unrecognised" in status_text or "形式を認識" in status_text


class TestPopulateSummaryPerspective:
    """Phase 227-D: ``_populate_summary_perspective`` loads the player
    list from the summary JSON and updates the perspective spinner."""

    def test_loads_players_and_poppulates_spinner(self, tmp_path):
        content = _make_content()
        # Configure the perspective spinner mock to accept .values assignment
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 3},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {
                        "sentoku870": {"rank": "4d"},
                        "Opponent1": {"rank": "3d"},
                    },
                }
            ),
            encoding="utf-8",
        )
        content._populate_summary_perspective(str(summary), default_user="sentoku870", default_user_rank="4d")
        # summary_players was populated
        names = [p[0] for p in content.summary_players]
        assert "sentoku870" in names
        assert "Opponent1" in names
        # Spinner values were updated: birdseye + 2 players = 3 entries
        spinner_values = content.ids["perspective_select"].values
        assert len(spinner_values) == 3
        # The matched player is the default user → index 1
        assert content.summary_perspective_index == 1

    def test_birdseye_default_when_no_default_user(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 2},
                    "phase_x_mistake": {"middle:blunder": 1},
                    "players": {"p1": {"rank": "5k"}},
                }
            ),
            encoding="utf-8",
        )
        content._populate_summary_perspective(str(summary), default_user=None, default_user_rank=None)
        # No default user → birdseye (index 0). ``perspective_value``
        # is the stable internal sentinel ``_PERSPECTIVE_AUTO_INTERNAL``
        # (= "auto") since the birdseye index maps to the auto
        # perspective (Phase 242-B). The empty string sentinel is no
        # longer used.
        from katrain.gui.popups.llm_coach_popup import _PERSPECTIVE_AUTO_INTERNAL

        assert content.summary_perspective_index == 0
        assert content.perspective_value == _PERSPECTIVE_AUTO_INTERNAL

    def test_rank_auto_filled_from_matched_player(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 3},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {"sentoku870": {"rank": "4d"}},
                }
            ),
            encoding="utf-8",
        )
        content._populate_summary_perspective(str(summary), default_user="sentoku870", default_user_rank=None)
        # rank_input should have "4d" set
        assert content.ids["rank_input"].text == "4d"
        assert content.detected_rank == "4d"

    def test_rank_falls_back_to_default_user_rank(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 1},
                    "phase_x_mistake": {},
                    "players": {"sentoku870": {}},  # no rank
                }
            ),
            encoding="utf-8",
        )
        content._populate_summary_perspective(str(summary), default_user="sentoku870", default_user_rank="3k")
        # rank_input should have "3k" (from default_user_rank fallback)
        assert content.ids["rank_input"].text == "3k"


class TestOnGenerateSummary:
    """Phase 227-D: ``on_generate_and_copy`` dispatches to the summary
    builder when the path is a summary JSON."""

    def test_summary_path_uses_summary_builder(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 3},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {"p1": {"rank": "4d"}},
                    "weaknesses": {
                        "black": [{"phase": "middle", "category": "blunder", "count": 3, "total_loss": 10.0}]
                    },
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(summary)
        content.path_type = "summary"
        with (
            patch("katrain.gui.features.llm_coach.build_summary_llm_prompt") as mock_build,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip,
        ):
            mock_build.return_value = (True, "# Summary prompt\n**3 局**")
            content.on_generate_and_copy()
        # build_summary_llm_prompt was called
        assert mock_build.called
        # Clipboard.copy was called with the prompt
        mock_clip.copy.assert_called_once()
        copied = mock_clip.copy.call_args[0][0]
        assert "3 局" in copied or "3 games" in copied

    def test_karte_path_uses_karte_builder(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "weaknesses": {"black": [], "white": []},
                    "important_moves": [{"meaning_tag_id": "x"}],
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(karte)
        content.path_type = "karte"
        content.ids["response_input"].text = ""
        with (
            patch("katrain.gui.features.llm_coach.build_llm_prompt") as mock_build,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip,
        ):
            mock_build.return_value = (True, "# Karte prompt")
            content.on_generate_and_copy()
        # build_llm_prompt was called (not build_summary)
        assert mock_build.called
        mock_clip.copy.assert_called_once()
        assert mock_clip.copy.call_args[0][0] == "# Karte prompt"

    def test_empty_path_shows_error(self):
        content = _make_content()
        content.karte_path_input.text = ""
        with patch("katrain.gui.features.llm_coach.build_llm_prompt") as mock_build:
            content.on_generate_and_copy()
        # Neither builder was called
        assert not mock_build.called


class TestOnValidateSummary:
    """Phase 227-D: ``on_validate`` dispatches to the summary validator
    when the path is a summary JSON."""

    def test_summary_path_uses_summary_validator(self, tmp_path):
        content = _make_content()
        summary = tmp_path / "s.json"
        summary.write_text(
            json.dumps(
                {
                    "meta": {"games_analyzed": 3},
                    "phase_x_mistake": {"middle:blunder": 5},
                    "players": {"p1": {"rank": "4d"}},
                    "weaknesses": {
                        "black": [{"phase": "middle", "category": "blunder", "count": 3, "total_loss": 10.0}]
                    },
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(summary)
        content.path_type = "summary"
        content.ids["response_input"].text = "考察: ...\n抽出した弱点パターン: [blunder]\n参照したphase: [middle]\n"
        with patch("katrain.gui.features.llm_coach.validate_summary_llm_response") as mock_validate:
            mock_validate.return_value = (True, "**Status**: clean")
            content.on_validate()
        assert mock_validate.called
        # The result label got the markdown
        assert content.ids["result_label"].text == "**Status**: clean"

    def test_karte_path_uses_karte_validator(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "weaknesses": {"black": [], "white": []},
                    "important_moves": [{"meaning_tag_id": "x"}],
                }
            ),
            encoding="utf-8",
        )
        content.karte_path_input.text = str(karte)
        content.path_type = "karte"
        content.ids["response_input"].text = "考察: テスト"
        with patch("katrain.gui.features.llm_coach.validate_llm_response") as mock_validate:
            mock_validate.return_value = (True, "**Status**: clean (karte)")
            content.on_validate()
        assert mock_validate.called

    def test_empty_response_shows_error(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"weaknesses": {}, "important_moves": []}), encoding="utf-8")
        content.karte_path_input.text = str(karte)
        content.path_type = "karte"
        content.ids["response_input"].text = ""
        content.on_validate()
        # Status label should show the no-response error
        status_text = content.ids["status_label"].text
        assert "応答" in status_text or "response" in status_text.lower()


class TestOnSummaryPerspectiveChanged:
    """Phase 227-D: the dedicated summary-perspective callback updates
    the index + rank hint when the user picks a different player."""

    def test_updates_index_and_rank(self):
        content = _make_content()
        content.summary_players = [("p1", "4d"), ("p2", "3d")]
        # Simulate the spinner showing the second player's text
        birdseye = "全体俯瞰"
        content.ids["perspective_select"].values = [
            birdseye,
            "p1 (4d)",
            "p2 (3d)",
        ]
        content.ids["perspective_select"].text = "p2 (3d)"
        content.on_summary_perspective_changed()
        assert content.summary_perspective_index == 2
        assert content.perspective_value == "p2"
        # rank_input should have "3d"
        assert content.ids["rank_input"].text == "3d"

    def test_birdseye_selection_clears_index(self):
        content = _make_content()
        content.summary_players = [("p1", "4d")]
        birdseye = "全体俯瞰"
        content.ids["perspective_select"].values = [birdseye, "p1 (4d)"]
        content.ids["perspective_select"].text = birdseye
        content.on_summary_perspective_changed()
        assert content.summary_perspective_index == 0
        # ``perspective_value`` is a StringProperty; bird's-eye is the
        # _PERSPECTIVE_AUTO_INTERNAL sentinel (= "auto", Phase 242-B).
        # The empty string sentinel is no longer used.
        from katrain.gui.popups.llm_coach_popup import _PERSPECTIVE_AUTO_INTERNAL

        assert content.perspective_value == _PERSPECTIVE_AUTO_INTERNAL


class TestOnPathChanged:
    """Phase 227-D: ``on_path_changed`` re-runs type detection +
    rank/perspective population when the user manually types a path
    and presses Enter."""

    def test_resets_retry_counter(self):
        content = _make_content()
        content._rank_detect_retries = 4  # near the cap
        content.karte_path_input.text = ""
        content.on_path_changed()
        # The retry counter should be reset so the next populate has
        # a fresh chance.
        assert content._rank_detect_retries == 0

    def test_runs_type_label_refresh(self):
        content = _make_content()
        content.karte_path_input.text = ""
        content.on_path_changed()
        # Empty path → type label cleared
        assert content.ids["type_label"].text == ""
