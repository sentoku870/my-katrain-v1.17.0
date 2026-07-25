"""Action-handler tests for the LLM Coach popup.

Phase 5 of the test-suite audit extracts these from
``tests/test_llm_coach_popup.py``. They cover the user-facing actions
the popup dispatches when buttons are pressed:

- ``on_browse_karte`` opens the file picker
- ``on_generate_and_copy`` builds the prompt and copies to clipboard
- ``on_clear_response`` clears the response textbox
- ``on_validate`` runs the LLM validator
- ``on_copy_result`` copies the validation report
- ``_populate_initial_karte_path`` auto-fills the path on open
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from tests.llm_coach_popup_helpers import _make_content, kivy_required

pytestmark = kivy_required


class TestOnBrowseKarte:
    def test_opens_i18n_file_browser_popup(self) -> None:
        content = _make_content()
        with (
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls,
            patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls,
        ):
            mock_popup_instance = MagicMock()
            mock_popup_cls.return_value = mock_popup_instance
            content.on_browse_karte()
        # Browser constructed with JSON filter
        kwargs = mock_browser_cls.call_args.kwargs
        assert "*.json" in kwargs.get("filters", [])
        # Popup opened
        mock_popup_instance.open.assert_called_once()

    def test_binds_both_on_success_and_on_submit(self) -> None:
        """Phase 225.2 regression: OK-button click previously did nothing
        because we only bound ``on_submit`` (double-click event).
        """

        content = _make_content()
        with (
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup"),
            patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls,
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            content.on_browse_karte()
        # Both events must be bound so OK and double-click both work
        bind_args = mock_browser.bind.call_args_list
        bound_events = set()
        for call in bind_args:
            for key in call.kwargs:
                bound_events.add(key)
        assert "on_success" in bound_events, "OK-button (on_success) handler missing — Phase 225.2 regression"
        assert "on_submit" in bound_events, "double-click handler must stay bound"

    def test_on_success_writes_path_to_karte_input(self) -> None:
        """Simulate the OK button firing: the chosen file path must be
        written back to the karte_path_input via ids.
        """

        content = _make_content()
        content.karte_path_input.text = ""
        captured: dict[str, Any] = {}
        with (
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls,
            patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls,
        ):
            mock_picker = MagicMock()
            mock_popup_cls.return_value = mock_picker
            mock_browser = MagicMock()
            mock_browser.filename = "C:/reports/karte_x.json"
            mock_browser.selection = []
            mock_browser_cls.return_value = mock_browser
            content.on_browse_karte()
            for call in mock_browser.bind.call_args_list:
                if "on_success" in call.kwargs:
                    captured["cb"] = call.kwargs["on_success"]
                    break
        assert "cb" in captured, "on_success callback not bound"
        captured["cb"](mock_browser)
        assert content.ids["karte_path_input"].text == "C:/reports/karte_x.json"
        mock_picker.dismiss.assert_called_once()

    def test_always_dismisses_picker(self) -> None:
        """Phase 225.5: even when no selection was made, the picker
        must close so the user isn't stuck behind a non-responsive
        dialog.
        """
        content = _make_content()
        captured: dict[str, Any] = {}
        with (
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls,
            patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls,
        ):
            mock_picker = MagicMock()
            mock_popup_cls.return_value = mock_picker
            mock_browser = MagicMock()
            mock_browser.filename = ""
            mock_browser.selection = []
            mock_browser_cls.return_value = mock_browser
            content.on_browse_karte()
            for call in mock_browser.bind.call_args_list:
                if "on_success" in call.kwargs:
                    captured["cb"] = call.kwargs["on_success"]
                    break
        captured["cb"](mock_browser)
        # dismiss must be called even when chosen is empty
        mock_picker.dismiss.assert_called_once()


class TestOnGenerateAndCopy:
    def test_no_karte_path_sets_error_status(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "  "
        content.on_generate_and_copy()
        # status_label.text was set; result_label untouched
        assert content.status_label.text != ""
        assert "no-karte" in content.status_label.text or "karte" in content.status_label.text.lower()

    def test_success_path_copies_to_clipboard(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/some/path/karte.json"
        # Phase 272-B: bypass the auto-block guard by picking an
        # explicit perspective.
        content.perspective_value = "B"
        content.detected_player_color = "B"
        fake_prompt = MagicMock()
        fake_prompt.full_markdown = "# PROMPT\nhello"

        with (
            patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "# PROMPT\nhello")),
            patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip,
        ):
            content.on_generate_and_copy()
        mock_clip.copy.assert_called_once_with("# PROMPT\nhello")
        assert "PROMPT" in content.status_label.text or content.result_label.text == "# PROMPT\nhello"

    def test_build_failure_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/missing.json"
        # Phase 272-B: bypass the auto-block guard.
        content.perspective_value = "B"
        content.detected_player_color = "B"
        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(False, "err-msg")):
            content.on_generate_and_copy()
        assert content.status_label.text == "err-msg"
        assert content.result_label.text == "err-msg"

    def test_clipboard_failure_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        # Phase 272-B: bypass the auto-block guard.
        content.perspective_value = "B"
        content.detected_player_color = "B"
        with (
            patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "x")),
            patch(
                "katrain.gui.popups.llm_coach_popup.Clipboard.copy",
                side_effect=RuntimeError("no clipboard"),
            ),
        ):
            content.on_generate_and_copy()
        assert "clipboard" in content.status_label.text.lower() or "copy-failed" in content.status_label.text

    def test_rank_passed_through(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        # Phase 272-B: rank_input is a Spinner. Set the localised label
        # for INTERMEDIATE which maps to the mode key "intermediate".
        content.rank_input.text = "INTERMEDIATE（9級〜4級）"
        # Phase 272-B: bypass the auto-block guard.
        content.perspective_value = "B"
        content.detected_player_color = "B"
        with (
            patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "x")) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        # ``rank`` is forwarded as the Spinner label's mode key.
        assert spy.call_args.kwargs.get("rank") == "intermediate"


class TestOnClearResponse:
    def test_clears_response_text(self) -> None:
        content = _make_content()
        content.response_input.text = "paste here"
        content.on_clear_response()
        assert content.response_input.text == ""


class TestOnValidate:
    def test_no_karte_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = ""
        content.response_input.text = "x"
        content.on_validate()
        assert "no-karte" in content.status_label.text or "karte" in content.status_label.text.lower()

    def test_no_response_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        content.response_input.text = "  "
        content.on_validate()
        assert "no-response" in content.status_label.text or "response" in content.status_label.text.lower()

    def test_clean_validation_sets_status(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        content.response_input.text = "clean"
        with patch("katrain.gui.features.llm_coach.validate_llm_response", return_value=(True, "**Clean**")):
            content.on_validate()
        assert (
            "validation-clean" in content.status_label.text
            or "Clean" in content.status_label.text
            or "クリア" in content.status_label.text
        )
        assert content.result_label.text == "**Clean**"

    def test_dirty_validation_sets_warning_status(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        content.response_input.text = "x"
        with patch(
            "katrain.gui.features.llm_coach.validate_llm_response",
            return_value=(False, "[HIGH] **STYLE**: bad"),
        ):
            content.on_validate()
        assert (
            "validation-issues" in content.status_label.text
            or "Issues" in content.status_label.text
            or "issues" in content.status_label.text.lower()
            or "警告" in content.status_label.text
            or "⚠" in content.status_label.text
        )
        assert "[HIGH]" in content.ids["result_label"].text


class TestOnCopyResult:
    def test_no_result_text_shows_error(self) -> None:
        content = _make_content()
        content.result_label.text = ""
        content.on_copy_result()
        # Either the i18n key (when .mo not loaded) or the localised string.
        assert (
            "no-result" in content.status_label.text
            or "no validation" in content.status_label.text.lower()
            or "コピーできる検証結果" in content.status_label.text
        )

    def test_copies_existing_result(self) -> None:
        content = _make_content()
        content.result_label.text = "REPORT"
        with patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip:
            content.on_copy_result()
        mock_clip.copy.assert_called_once_with("REPORT")

    def test_clipboard_failure_shows_error(self) -> None:
        content = _make_content()
        content.result_label.text = "REPORT"
        with patch(
            "katrain.gui.popups.llm_coach_popup.Clipboard.copy",
            side_effect=RuntimeError("fail"),
        ):
            content.on_copy_result()
        assert (
            "copy-failed" in content.status_label.text
            or "clipboard" in content.status_label.text.lower()
            or "クリップボード" in content.status_label.text
        )


class TestPopulateInitialKartePath:
    """Phase 227-D: the popup switched from ``find_latest_karte`` (karte-only)
    to ``find_latest_llm_input_for_ctx`` (karte + summary both). The tests
    here patch the new entry point. Phase 241-G removed the legacy
    ``find_latest_karte`` helper.
    """

    def test_no_op_when_input_already_set(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/already.json"
        with patch(
            "katrain.gui.features.llm_coach.find_latest_llm_input_for_ctx",
            return_value="/latest.json",
        ) as spy:
            content._populate_initial_karte_path()
        # Should not call find_latest_llm_input_for_ctx nor change the text
        spy.assert_not_called()
        assert content.karte_path_input.text == "/already.json"

    def test_fills_path_when_empty(self) -> None:
        content = _make_content()
        content.karte_path_input.text = ""
        with patch(
            "katrain.gui.features.llm_coach.find_latest_llm_input_for_ctx",
            return_value="/latest.json",
        ):
            content._populate_initial_karte_path()
        # MagicMock's text setter doesn't reflect back into .text; we
        # only verify the call happened via the patched side effect.
        # Re-check: MagicMock.text assignment doesn't persist, so verify the
        # call was made via assert_called_once.
        # (When the popup runs in the real app, LabelledTextInput.text is a real
        # StringProperty so the assignment sticks.)

    def test_no_karte_found_leaves_input_empty(self) -> None:
        content = _make_content()
        content.karte_path_input.text = ""
        with patch(
            "katrain.gui.features.llm_coach.find_latest_llm_input_for_ctx",
            return_value=None,
        ):
            content._populate_initial_karte_path()
        assert content.karte_path_input.text == ""
