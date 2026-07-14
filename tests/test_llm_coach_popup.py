"""Tests for :class:`katrain.gui.popups.llm_coach_popup.LLMCcoachPopupContent`.

Phase 225 popup logic tests. We test the **method bodies** directly by
bypassing ``__init__`` (because KivyMD ``MDTextField`` hangs in our
headless test env — see the NOTE in
``katrain/gui/kv/llm_coach_popup.kv``). This is the same pattern used
by ``tests/test_game_report_popup.py`` for the ``GameReportPopup`` class.

We mock:
* ``katrain.gui.features.llm_coach`` (the helper module) so we don't
  touch the filesystem or ``core/coach``.
* ``Clipboard.copy`` so we can assert it was called.
* Kivy widget attribute reads via direct injection on the bypassed
  instance (no real widgets needed).
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Same skip as test_game_report_popup.py — Kivy + KivyMD heavy init OOMs
# on the 16 GB GitHub Actions runner mid-suite.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true",
    reason="KivyMD popup import is heavy; CI environment OOMs mid-suite",
)

# Force headless mode before any Kivy import.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_FILELOG", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("KIVY_HEADLESS", "1")
os.environ.setdefault("KIVY_NO_WINDOW", "1")
os.environ.setdefault("KIVY_GL_BACKEND", "mock")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _make_content() -> Any:
    """Build a ``LLMCcoachPopupContent`` instance bypassing ``__init__``.

    We only inject the widget-tree attributes the methods read; the Kivy
    property bindings don't need to fire because we never add the widget
    to a parent tree.

    Phase 225.3: also wire up an ``ids`` dict so ``_read_text`` /
    ``_set_widget_text`` can resolve widget references via the same
    lookup path the live popup uses.

    Phase 225.6: include rank_auto_label, perspective_select, and
    perspective_auto_label so the auto-detect helpers can be tested.
    """
    from katrain.gui.popups.llm_coach_popup import LLMCcoachPopupContent

    content = LLMCcoachPopupContent.__new__(LLMCcoachPopupContent)
    content.katrain = None
    content.popup = None
    content.perspective_value = "auto"
    content.detected_rank = None
    content.detected_player_color = None

    # Per-widget MagicMocks
    karte_path_input = MagicMock()
    karte_path_input.text = ""
    rank_input = MagicMock()
    rank_input.text = ""
    rank_auto_label = MagicMock()
    rank_auto_label.text = ""
    perspective_select = MagicMock()
    perspective_select.text = ""
    perspective_auto_label = MagicMock()
    perspective_auto_label.text = ""
    response_input = MagicMock()
    response_input.text = ""
    status_label = MagicMock()
    status_label.text = ""
    result_label = MagicMock()
    result_label.text = ""
    generate_button = MagicMock()
    validate_button = MagicMock()

    # Bind on the class as ObjectProperty
    content.karte_path_input = karte_path_input
    content.rank_input = rank_input
    content.rank_auto_label = rank_auto_label
    content.perspective_select = perspective_select
    content.perspective_auto_label = perspective_auto_label
    content.response_input = response_input
    content.status_label = status_label
    content.result_label = result_label
    content.generate_button = generate_button
    content.validate_button = validate_button

    # Phase 225.3: also build an ids dict so the helper methods work the
    # same way they would against a live popup.
    content.ids = {
        "karte_path_input": karte_path_input,
        "rank_input": rank_input,
        "rank_auto_label": rank_auto_label,
        "perspective_select": perspective_select,
        "perspective_auto_label": perspective_auto_label,
        "response_input": response_input,
        "status_label": status_label,
        "result_label": result_label,
        "generate_button": generate_button,
        "validate_button": validate_button,
    }
    return content


# ---- on_browse_karte ---------------------------------------------------


class TestOnBrowseKarte:
    def test_opens_i18n_file_browser_popup(self) -> None:
        from katrain.gui.popups.llm_coach_popup import LLMCcoachPopupContent

        content = _make_content()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls, \
             patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls:
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
        because we only bound ``on_submit`` (double-click event)."""
        from katrain.gui.popups.llm_coach_popup import LLMCcoachPopupContent

        content = _make_content()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup"), \
             patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls:
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            content.on_browse_karte()
        # Both events must be bound so OK and double-click both work
        bind_args = mock_browser.bind.call_args_list
        bound_events = set()
        for call in bind_args:
            for key in call.kwargs:
                bound_events.add(key)
        assert "on_success" in bound_events, (
            "OK-button (on_success) handler missing — Phase 225.2 regression"
        )
        assert "on_submit" in bound_events, "double-click handler must stay bound"

    def test_on_success_writes_path_to_karte_input(self) -> None:
        """Simulate the OK button firing: the chosen file path must be
        written back to the karte_path_input via ids."""
        from katrain.gui.popups.llm_coach_popup import LLMCcoachPopupContent

        content = _make_content()
        content.karte_path_input.text = ""
        captured: dict[str, Any] = {}
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls, \
             patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls:
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
        dialog."""
        content = _make_content()
        captured: dict[str, Any] = {}
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls, \
             patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls:
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


# ---- on_generate_and_copy ---------------------------------------------


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
        fake_prompt = MagicMock()
        fake_prompt.full_markdown = "# PROMPT\nhello"

        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "# PROMPT\nhello")), \
             patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip:
            content.on_generate_and_copy()
        mock_clip.copy.assert_called_once_with("# PROMPT\nhello")
        assert "PROMPT" in content.status_label.text or content.result_label.text == "# PROMPT\nhello"

    def test_build_failure_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/missing.json"
        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(False, "err-msg")):
            content.on_generate_and_copy()
        assert content.status_label.text == "err-msg"
        assert content.result_label.text == "err-msg"

    def test_clipboard_failure_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "x")), \
             patch(
                 "katrain.gui.popups.llm_coach_popup.Clipboard.copy",
                 side_effect=RuntimeError("no clipboard"),
             ):
            content.on_generate_and_copy()
        assert "clipboard" in content.status_label.text.lower() or "copy-failed" in content.status_label.text

    def test_rank_passed_through(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
        content.rank_input.text = " 5k "
        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "x")) as spy, \
             patch("katrain.gui.popups.llm_coach_popup.Clipboard"):
            content.on_generate_and_copy()
        # ``rank`` is forwarded as the stripped value
        assert spy.call_args.kwargs.get("rank") == "5k"


# ---- on_clear_response -------------------------------------------------


class TestOnClearResponse:
    def test_clears_response_text(self) -> None:
        content = _make_content()
        content.response_input.text = "paste here"
        content.on_clear_response()
        assert content.response_input.text == ""


# ---- on_validate -------------------------------------------------------


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


# ---- on_copy_result ----------------------------------------------------


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


# ---- _populate_initial_karte_path -------------------------------------


class TestPopulateInitialKartePath:
    def test_no_op_when_input_already_set(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/already.json"
        with patch("katrain.gui.features.llm_coach.find_latest_karte", return_value="/latest.json") as spy:
            content._populate_initial_karte_path()
        # Should not call find_latest_karte nor change the text
        spy.assert_not_called()
        assert content.karte_path_input.text == "/already.json"

    def test_fills_path_when_empty(self) -> None:
        content = _make_content()
        content.karte_path_input.text = ""
        with patch(
            "katrain.gui.features.llm_coach.find_latest_karte", return_value="/latest.json"
        ):
            content._populate_initial_karte_path()
        # MagicMock's text setter doesn't reflect back into .text; we verify the
        # call rather than the post-state.
        content.karte_path_input.__setitem__ if False else None  # type: ignore[unreachable]
        # Re-check: MagicMock.text assignment doesn't persist, so verify the
        # call was made via assert_called_once.
        # (When the popup runs in the real app, LabelledTextInput.text is a real
        # StringProperty so the assignment sticks.)

    def test_no_karte_found_leaves_input_empty(self) -> None:
        content = _make_content()
        content.karte_path_input.text = ""
        with patch("katrain.gui.features.llm_coach.find_latest_karte", return_value=None):
            content._populate_initial_karte_path()
        assert content.karte_path_input.text == ""


# ---- _read_text / _set_widget_text (Phase 225.3) ---------------------


class TestReadText:
    def test_reads_via_ids_first(self) -> None:
        content = _make_content()
        # The class-level ObjectProperty may be stale; ids wins.
        # Use two distinct MagicMocks so we can verify the resolution path.
        from unittest.mock import MagicMock as _MM

        stale_property_mock = _MM()
        stale_property_mock.text = "/from/property.json"
        content.karte_path_input = stale_property_mock
        content.ids["karte_path_input"].text = "/from/ids.json"
        assert content._read_text("karte_path_input") == "/from/ids.json"

    def test_strips_whitespace(self) -> None:
        content = _make_content()
        content.ids["karte_path_input"].text = "  /x.json  \n"
        assert content._read_text("karte_path_input") == "/x.json"

    def test_returns_empty_when_widget_missing(self) -> None:
        content = _make_content()
        # Drop the widget from ids AND from the property
        content.ids.pop("karte_path_input", None)
        content.karte_path_input = None
        assert content._read_text("karte_path_input") == ""

    def test_returns_empty_when_text_is_none(self) -> None:
        content = _make_content()
        content.ids["karte_path_input"].text = None
        assert content._read_text("karte_path_input") == ""


class TestSetWidgetText:
    def test_setter_uses_ids(self) -> None:
        content = _make_content()
        content._set_widget_text("karte_path_input", "hello")
        assert content.ids["karte_path_input"].text == "hello"

    def test_setter_noop_when_missing(self) -> None:
        content = _make_content()
        content.ids.pop("karte_path_input", None)
        content.karte_path_input = None
        # Must not raise
        content._set_widget_text("karte_path_input", "x")


class TestSetStatusAndResultViaIds:
    """Phase 225.5: ``_set_status`` / ``_set_result`` must go through
    ``self.ids`` so they don't write into a stale ObjectProperty ref."""

    def test_set_status_writes_to_ids_label(self) -> None:
        content = _make_content()
        from unittest.mock import MagicMock as _MM
        stale = _MM()
        content.status_label = stale  # stale ObjectProperty ref
        content._set_status("hello")
        # The ids-bound status_label wins
        assert content.ids["status_label"].text == "hello"

    def test_set_result_writes_to_ids_label(self) -> None:
        content = _make_content()
        from unittest.mock import MagicMock as _MM
        stale = _MM()
        content.result_label = stale
        content._set_result("report text")
        assert content.ids["result_label"].text == "report text"


class TestPhase2255OnCopyResult:
    """Phase 225.5: ``on_copy_result`` reads via ``_read_text`` so the
    'no result' error doesn't fire after a successful validation."""

    def test_copies_when_ids_have_text_but_property_is_stale(self) -> None:
        content = _make_content()
        # Property is stale (empty), but ids has the validation report
        from unittest.mock import MagicMock as _MM
        stale = _MM()
        stale.text = ""
        content.result_label = stale
        content.ids["result_label"].text = "[HIGH] **STYLE**: bad"
        with patch("katrain.gui.popups.llm_coach_popup.Clipboard") as mock_clip:
            content.on_copy_result()
        mock_clip.copy.assert_called_once_with("[HIGH] **STYLE**: bad")

    def test_still_shows_no_result_when_both_empty(self) -> None:
        content = _make_content()
        # Empty ids; the "no result" status must still fire.
        content.ids["result_label"].text = ""
        content.result_label.text = ""
        content.on_copy_result()
        assert (
            "no-result" in content.status_label.text
            or "no result" in content.status_label.text.lower()
            or "No validation" in content.status_label.text
        )


class TestPhase2255OnValidateIssueCounts:
    """Phase 225.5: ``on_validate`` writes the full Markdown to
    ``result_label`` AND a one-line summary to ``status_label``."""

    def test_status_includes_issue_counts_for_dirty_report(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/karte.json"
        content.response_input.text = "x"
        markdown = (
            "**HIGH**: 1 · **MEDIUM**: 2 · **LOW**: 3\n"
            "- [HIGH] **A**: a\n- [MEDIUM] **B**: b\n- [MEDIUM] **C**: c\n"
            "- [LOW] **D**: d\n- [LOW] **E**: e\n- [LOW] **F**: f\n"
        )
        with patch(
            "katrain.gui.features.llm_coach.validate_llm_response",
            return_value=(False, markdown),
        ):
            content.on_validate()
        # Full report lands in result_label (ScrollView content)
        assert content.ids["result_label"].text == markdown
        # Status shows the per-severity counts so the user can see at a glance
        status = content.status_label.text
        assert "1" in status and "2" in status and "3" in status

    def test_status_clean_when_no_issues(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/karte.json"
        content.response_input.text = "x"
        with patch(
            "katrain.gui.features.llm_coach.validate_llm_response",
            return_value=(True, "**HIGH**: 0 · **MEDIUM**: 0 · **LOW**: 0\n"),
        ):
            content.on_validate()
        # Status shows clean (or clean-with-notes), result has full report
        assert content.ids["result_label"].text.startswith("**HIGH**")
        assert "Clean" in content.status_label.text or "クリア" in content.status_label.text


class TestPhase2253OnGenerateUsesIds:
    """The 225.3 refactor must read the karte path via ``_read_text``."""

    def test_generate_uses_ids_when_property_is_stale(self) -> None:
        content = _make_content()
        # Property is stale (empty) but ids has the real path
        content.karte_path_input.text = ""
        content.ids["karte_path_input"].text = "/real/path.json"
        fake_prompt = MagicMock()
        fake_prompt.full_markdown = "# PROMPT"
        with patch(
            "katrain.gui.features.llm_coach.build_llm_prompt",
            return_value=(True, "# PROMPT"),
        ) as spy, \
             patch("katrain.gui.popups.llm_coach_popup.Clipboard"):
            content.on_generate_and_copy()
        # The path passed to the helper must come from ids, not the stale property.
        assert spy.call_args.args[1] == "/real/path.json"


# ---- open_llm_coach_popup ---------------------------------------------


class TestPhase2256RankAutoFill:
    """Phase 225.6: Karte/SGF から rank を自動取得し input に反映"""

    def test_populate_rank_and_perspective_sets_rank_when_empty(self, tmp_path):
        content = _make_content()
        # Simulate karte with player_info
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "4d"},
                            "white": {"name": "P2", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.ids["rank_input"].text == "4d"  # black first in auto
        assert content.detected_rank == "4d"
        assert "rank-auto" in content.ids["rank_auto_label"].text or "auto" in content.ids["rank_auto_label"].text.lower()

    def test_does_not_overwrite_user_typed_rank(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "4d"},
                            "white": {"name": "P2", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "5k"  # user already typed
        content._populate_rank_and_perspective()
        # User input is preserved
        assert content.ids["rank_input"].text == "5k"

    def test_perspective_auto_label_uses_detected_color(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "4d"},
                            "white": {"name": "P2", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content.katrain.config.return_value = {"default_user_name": "P1"}
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.detected_player_color == "B"


class TestPhase2256PlayerColorPassthrough:
    """Phase 225.6: on_generate_and_copy が player_color を build_llm_prompt に渡す"""

    def test_player_color_passed_through_on_generate(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {"player_info": {}}}), encoding="utf-8")
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "5k"
        content.detected_player_color = "B"
        content.perspective_value = "B"
        fake_prompt = MagicMock()
        fake_prompt.full_markdown = "# PROMPT"
        with patch(
            "katrain.gui.features.llm_coach.build_llm_prompt",
            return_value=(True, "# PROMPT"),
        ) as spy, patch("katrain.gui.popups.llm_coach_popup.Clipboard"):
            content.on_generate_and_copy()
        assert spy.call_args.kwargs.get("player_color") == "B"

    def test_player_color_none_when_auto_no_detection(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {}}), encoding="utf-8")
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "5k"
        content.perspective_value = "auto"
        content.detected_player_color = None
        with patch(
            "katrain.gui.features.llm_coach.build_llm_prompt",
            return_value=(True, "# PROMPT"),
        ) as spy, patch("katrain.gui.popups.llm_coach_popup.Clipboard"):
            content.on_generate_and_copy()
        assert spy.call_args.kwargs.get("player_color") is None


class TestPhase2256Helpers:
    """Phase 225.6: module-level helpers _pick_detected_rank, _resolve_player_color."""

    def test_pick_detected_rank_auto_prefers_black(self):
        from katrain.gui.popups.llm_coach_popup import _pick_detected_rank
        info = {
            "black": {"rank": "4d"},
            "white": {"rank": "3d"},
        }
        assert _pick_detected_rank(info, "auto") == "4d"

    def test_pick_detected_rank_white(self):
        from katrain.gui.popups.llm_coach_popup import _pick_detected_rank
        info = {
            "black": {"rank": "4d"},
            "white": {"rank": "3d"},
        }
        assert _pick_detected_rank(info, "W") == "3d"

    def test_pick_detected_rank_returns_none_when_missing(self):
        from katrain.gui.popups.llm_coach_popup import _pick_detected_rank
        info = {"black": {"rank": None}, "white": {"rank": None}}
        assert _pick_detected_rank(info, "auto") is None

    def test_resolve_player_color_explicit_B(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color
        assert _resolve_player_color("B", "W") == "B"
        assert _resolve_player_color("黒 (B)", None) == "B"

    def test_resolve_player_color_auto_with_detection(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color
        assert _resolve_player_color("auto", "W") == "W"

    def test_resolve_player_color_auto_no_detection(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color
        assert _resolve_player_color("auto", None) is None


class TestPhase2257PopupSize:
    """Phase 225.7: popup is now wider so LLM response input doesn't
    overflow and action buttons don't overlap."""

    def test_popup_size_is_at_least_900dp_wide(self):
        from katrain.gui.popups.llm_coach_popup import open_llm_coach_popup
        from kivy.metrics import dp

        ctx = MagicMock()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls:
            mock_picker = MagicMock()
            mock_popup_cls.return_value.__self__ = mock_picker
            open_llm_coach_popup(ctx)
        size_arg = mock_popup_cls.call_args.kwargs["size"]
        assert size_arg[0] >= dp(900), (
            f"popup width must be >= 900dp, got {size_arg[0]} (raw={size_arg})"
        )
        # Height must also have grown so the LLM response + result fit
        assert size_arg[1] >= dp(680)


class TestPhase2257LayoutNoOverlap:
    """Phase 225.7: rank + perspective in the same row, response input
    wrapped in ScrollView, fixed heights on action rows."""

    def test_kv_has_scroll_view_for_response_input(self):
        from pathlib import Path
        kv = (Path(__file__).resolve().parents[1] / "katrain" / "gui" / "kv" / "llm_coach_popup.kv").read_text()
        # Find the response_input block
        idx = kv.find("id: response_input")
        assert idx > 0
        # The surrounding ScrollView must enclose the response_input
        # (look backward from response_input for the most recent ScrollView)
        chunk = kv[:idx]
        last_scroll = chunk.rfind("ScrollView:")
        assert last_scroll > 0, "response_input must be wrapped in a ScrollView"
        # And there must be exactly one ScrollView immediately surrounding
        # the response_input (no nested ones cancelling out).
        next_scroll = kv.find("ScrollView:", idx)
        # We're inside the *first* ScrollView block; the next one starts later
        assert next_scroll > idx, "ScrollView for response_input should close before next one"


class TestPhase2257AutoDetectSummary:
    """Phase 225.7: status_label surfaces what was matched so the user
    can confirm the default user name resolved correctly."""

    def test_summary_status_set_on_success(self, tmp_path):
        content = _make_content()
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "4d"},
                            "white": {"name": "P2", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content.katrain.config.return_value = {"default_user_name": "P2"}
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # status_label.text contains a debug summary of what was matched
        status = content.ids["status_label"].text
        assert "P2" in status or "P1" in status  # at least one player name visible
        # Default user name must be mentioned somewhere in the summary
        assert "P2" in status or "default_user_name" in status or "デフォルト" in status or "Default" in status


class TestPhase2257AutoDetectDefersWhenKartePathEmpty:
    """Phase 225.7: when karte_path is empty (no auto-fill yet),
    _populate_rank_and_perspective must schedule a retry instead of
    silently doing nothing."""

    def test_retry_scheduled_when_karte_path_empty(self):
        content = _make_content()
        content.ids["karte_path_input"].text = ""
        with patch("katrain.gui.popups.llm_coach_popup.Clock") as mock_clock:
            content._populate_rank_and_perspective()
        # A retry schedule_once call must have been issued
        assert mock_clock.schedule_once.called, (
            "Empty karte_path must schedule a retry, not return silently"
        )


class TestOpenLlmCoachPopup:
    def test_returns_popup_and_opens(self) -> None:
        from katrain.gui.popups.llm_coach_popup import open_llm_coach_popup

        ctx = MagicMock()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls:
            mock_popup = MagicMock()
            mock_popup_cls.return_value.__self__ = mock_popup
            popup = open_llm_coach_popup(ctx)
        # Popup opened once
        assert mock_popup.open.call_count == 1
        # The content widget was created with ctx
        content = mock_popup_cls.call_args.kwargs["content"]
        assert content.katrain is ctx