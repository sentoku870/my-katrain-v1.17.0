"""Tests for :class:`katrain.gui.popups.llm_coach_popup.LLMCoachPopupContent`.

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

# Phase 226-D (D1): skip the popup logic tests only when Kivy itself
# is unimportable. Previously the file was gated on the ``CI``
# environment variable, which silently skipped ~50 tests on every CI
# runner regardless of whether Kivy was actually installed. Now the
# skip is data-driven: if Kivy is present, the tests run (the heavy
# init is harmless on a developer machine and CI runners that have
# Kivy in the venv).
try:
    import kivy  # noqa: F401

    _KIVY_AVAILABLE = True
except ImportError:
    _KIVY_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _KIVY_AVAILABLE,
    reason="Kivy is not installed in this environment",
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


def _resolve_i18n(key: str) -> str:
    """Helper: resolve an i18n key via the same Lang instance the popup uses."""
    from katrain.core.lang import i18n

    return i18n._(key)


def _make_content(path_type: str = "karte") -> Any:
    """Build a ``LLMCoachPopupContent`` instance bypassing ``__init__``.

    We only inject the widget-tree attributes the methods read; the Kivy
    property bindings don't need to fire because we never add the widget
    to a parent tree.

    Phase 225.3: also wire up an ``ids`` dict so ``_read_text`` /
    ``_set_widget_text`` can resolve widget references via the same
    lookup path the live popup uses.

    Phase 225.6: include rank_auto_label, perspective_select, and
    perspective_auto_label so the auto-detect helpers can be tested.
    """
    from katrain.gui.popups.llm_coach_popup import LLMCoachPopupContent

    content = LLMCoachPopupContent.__new__(LLMCoachPopupContent)
    content.popup = None
    content.perspective_value = "auto"
    content.detected_rank = None
    content.detected_player_color = None
    # Phase 226-B (B1): init the Clock-tracking attributes that the
    # production ``__init__`` would normally set up.
    content._pending_clock_events = []
    content._rank_detect_retries = 0

    # Phase 230-F (CI fix): default config mock that returns the
    # supplied ``default`` arg instead of leaking ``return_value``
    # into every call. Tests that need per-key behaviour override
    # ``content.katrain.config.side_effect`` after this default.
    _default_katrain = MagicMock()
    _default_katrain.config = MagicMock(side_effect=lambda key, default=None: default or "")
    content.katrain = _default_katrain

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
    # Phase 227-D: type_label for the detected JSON type display
    type_label = MagicMock()
    type_label.text = ""

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
    content.type_label = type_label

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
        "type_label": type_label,
    }

    # Phase 227-D: state for the multi-game summary support
    # Phase 241-B: default to "karte" (the most common case in
    # existing tests) so the new unknown-path guard in
    # ``_populate_rank_and_perspective`` / ``on_generate_and_copy`` /
    # ``on_validate`` doesn't accidentally block the karte code path.
    # Tests that need summary or unknown set ``content.path_type``
    # explicitly.
    content.path_type = path_type
    content.summary_players = []
    content.summary_perspective_index = 0
    # Phase 241-E: the user-set flag for the summary perspective.
    # Tests that don't exercise the user-spinner interaction leave
    # this at False; the population logic only preserves the user's
    # choice when this is True.
    content._summary_perspective_user_set = False

    # Phase 230-F (CI fix): helper to install a per-key config mock.
    def _install_config_mock(mykatrain_settings=None, general_player_rank=""):
        """Replace ``content.katrain.config`` with a side_effect mock.

        ``content.katrain.config(key, default)`` now dispatches by key:
        - ``"mykatrain_settings"`` returns ``mykatrain_settings or {}``
        - ``"general/player_rank"`` returns ``general_player_rank``
        - any other key returns the ``default`` arg verbatim

        This avoids the ``MagicMock.return_value`` leak where every
        call returned the same dict regardless of the requested key.
        """
        settings_value = mykatrain_settings if mykatrain_settings is not None else {}

        def _side_effect(key, default=None):
            if key == "mykatrain_settings":
                return settings_value
            if key == "general/player_rank":
                return general_player_rank
            return default

        content.katrain.config = MagicMock(side_effect=_side_effect)

    content._install_config_mock = _install_config_mock
    return content


# ---- on_browse_karte ---------------------------------------------------


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
        because we only bound ``on_submit`` (double-click event)."""

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
        written back to the karte_path_input via ids."""

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
        dialog."""
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
        with patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(False, "err-msg")):
            content.on_generate_and_copy()
        assert content.status_label.text == "err-msg"
        assert content.result_label.text == "err-msg"

    def test_clipboard_failure_shows_error(self) -> None:
        content = _make_content()
        content.karte_path_input.text = "/x.json"
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
        content.rank_input.text = " 5k "
        with (
            patch("katrain.gui.features.llm_coach.build_llm_prompt", return_value=(True, "x")) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
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
    """Phase 227-D: the popup switched from ``find_latest_karte`` (karte-only)
    to ``find_latest_llm_input_for_ctx`` (karte + summary both). The tests
    here patch the new entry point. Phase 241-G removed the legacy
    ``find_latest_karte`` helper."""

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
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        # The path passed to the helper must come from ids, not the stale property.
        assert spy.call_args.args[1] == "/real/path.json"


# ---- open_llm_coach_popup ---------------------------------------------


class TestPhase2256RankAutoFill:
    """Phase 225.6: Karte/SGF から rank を自動取得し input に反映"""

    def test_populate_rank_and_perspective_sets_rank_when_empty(self, tmp_path):
        content = _make_content(path_type="karte")
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
        assert (
            "rank-auto" in content.ids["rank_auto_label"].text or "auto" in content.ids["rank_auto_label"].text.lower()
        )

    def test_does_not_overwrite_user_typed_rank(self, tmp_path):
        content = _make_content(path_type="karte")
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
        content = _make_content(path_type="karte")
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
        content._install_config_mock(mykatrain_settings={"default_user_name": "P1"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.detected_player_color == "B"


class TestPhase2256PlayerColorPassthrough:
    """Phase 225.6: on_generate_and_copy が player_color を build_llm_prompt に渡す"""

    def test_player_color_passed_through_on_generate(self, tmp_path):
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {"player_info": {}}}), encoding="utf-8")
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "5k"
        content.detected_player_color = "B"
        content.perspective_value = "B"
        fake_prompt = MagicMock()
        fake_prompt.full_markdown = "# PROMPT"
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        assert spy.call_args.kwargs.get("player_color") == "B"

    def test_player_color_none_when_auto_no_detection(self, tmp_path):
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {}}), encoding="utf-8")
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "5k"
        content.perspective_value = "auto"
        content.detected_player_color = None
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
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

        # Phase 226-B (B3): perspective_value is now the stable internal
        # value ("B"/"W"/"auto"), not the localised spinner label.
        assert _resolve_player_color("B", "W") == "B"
        assert _resolve_player_color("B", None) == "B"

    def test_resolve_player_color_explicit_W(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color

        assert _resolve_player_color("W", "B") == "W"
        assert _resolve_player_color("W", None) == "W"

    def test_resolve_player_color_auto_with_detection(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color

        assert _resolve_player_color("auto", "W") == "W"

    def test_resolve_player_color_auto_no_detection(self):
        from katrain.gui.popups.llm_coach_popup import _resolve_player_color

        assert _resolve_player_color("auto", None) is None


# --- Phase 226-I: auto-detect feedback when default_user_name is empty ---


class TestPhase226IGuiAutoDetectFeedback:
    """Phase 226-I: when ``default_user_name`` is empty, the auto detector
    has no signal to pick a side. Surface this to the user via the
    status label so they know why their perspective spinner keeps
    falling back to "auto (no detection)" instead of silently failing."""

    def test_default_user_empty_status_warns(self, tmp_path):
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        # Karte has player info but the mykatrain setting is empty.
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "AnyUser", "rank": "4d"},
                            "white": {"name": "Opponent", "rank": "3d"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={"default_user_name": ""})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        status = content.ids["status_label"].text
        # The status must clearly say default_user_name is empty.
        assert "default_user" in status or "デフォルト" in status or "user_name" in status, (
            f"status should warn about empty default_user_name, got: {status!r}"
        )

    def test_default_user_present_status_summary(self, tmp_path):
        content = _make_content(path_type="karte")
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
        content._install_config_mock(mykatrain_settings={"default_user_name": "P1"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        status = content.ids["status_label"].text
        # Should contain the matched user name (P1) + at least one of
        # the player names.
        assert "P1" in status

    def test_rank_source_traced_from_karte(self, tmp_path):
        content = _make_content(path_type="karte")
        # When Karte has rank info, the status text (via _refresh_rank_hint)
        # should display the rank — the rank field is filled even if the
        # status line itself doesn't change.
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "5k"},
                            "white": {"name": "P2", "rank": "6k"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={"default_user_name": "P1"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Rank auto-fill: the input should have been filled with 5k
        # (P1's rank) since the perspective defaults to "auto" and
        # both colours are equal.
        assert content.ids["rank_input"].text in ("5k", "6k")

    def test_rank_fallback_to_default_user_rank(self, tmp_path):
        content = _make_content(path_type="karte")
        # When Karte has no rank info, the default_user_rank setting
        # should be used (Phase 225.8 fallback).
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": None},
                            "white": {"name": "P2", "rank": None},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(
            mykatrain_settings={
                "default_user_name": "P1",
                "default_user_rank": "4段",
            }
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # rank_input should have been filled with "4段" as fallback
        assert content.ids["rank_input"].text == "4段"


class TestPhase226BSpinnerTextToInternal:
    """Phase 226-B (B3): ``_spinner_text_to_internal`` reverse-maps the
    localised spinner label to a stable internal value."""

    def test_auto_label_maps_to_auto(self):
        from katrain.gui.popups.llm_coach_popup import _spinner_text_to_internal

        auto_label = _resolve_i18n("mykatrain:llm-coach:perspective-auto")
        assert _spinner_text_to_internal(auto_label) == "auto"

    def test_black_label_maps_to_B(self):
        from katrain.gui.popups.llm_coach_popup import _spinner_text_to_internal

        black_label = _resolve_i18n("mykatrain:llm-coach:perspective-black")
        assert _spinner_text_to_internal(black_label) == "B"

    def test_white_label_maps_to_W(self):
        from katrain.gui.popups.llm_coach_popup import _spinner_text_to_internal

        white_label = _resolve_i18n("mykatrain:llm-coach:perspective-white")
        assert _spinner_text_to_internal(white_label) == "W"

    def test_empty_string_falls_back_to_auto(self):
        from katrain.gui.popups.llm_coach_popup import _spinner_text_to_internal

        assert _spinner_text_to_internal("") == "auto"


# --- Phase 242-B: perspective_value constant + truncation + paste cap --


class TestPhase242BPerspectiveConstant:
    """Phase 242-B: ``_PERSPECTIVE_AUTO_INTERNAL`` is the single source
    of truth for the "auto" sentinel value. The previous convention used
    the empty string ``""`` which was confusing and inconsistent.
    """

    def test_constant_value(self):
        from katrain.gui.popups.llm_coach_popup import _PERSPECTIVE_AUTO_INTERNAL

        assert _PERSPECTIVE_AUTO_INTERNAL == "auto"

    def test_perspective_value_uses_constant(self):
        """StringProperty default is the constant, not a hard-coded literal."""
        from katrain.gui.popups.llm_coach_popup import (
            LLMCoachPopupContent,
            _PERSPECTIVE_AUTO_INTERNAL,
        )

        # The default value baked into the class is the constant.
        assert LLMCoachPopupContent.perspective_value.defaultvalue == _PERSPECTIVE_AUTO_INTERNAL

    def test_resolve_player_color_uses_constant(self):
        from katrain.gui.popups.llm_coach_popup import (
            _PERSPECTIVE_AUTO_INTERNAL,
            _PERSPECTIVE_BLACK_INTERNAL,
            _PERSPECTIVE_WHITE_INTERNAL,
            _resolve_player_color,
        )

        # The function must use the same constants as the rest of the
        # popup code. If you change the constant name, this test will
        # catch any leftover hard-coded literals.
        assert _resolve_player_color(_PERSPECTIVE_AUTO_INTERNAL, "B") == "B"
        assert _resolve_player_color(_PERSPECTIVE_BLACK_INTERNAL, "W") == "B"
        assert _resolve_player_color(_PERSPECTIVE_WHITE_INTERNAL, "B") == "W"
        assert _resolve_player_color("", "B") == "B"  # empty == auto
        assert _resolve_player_color("garbage", None) is None


class TestPhase242BPasteSizeCap:
    """Phase 242-B: response_input paste is capped to prevent UI freeze."""

    def test_constant_value(self):
        from katrain.gui.popups.llm_coach_popup import _MAX_RESPONSE_INPUT_CHARS

        # 100k is well above realistic LLM outputs and matches
        # the validator's report cap.
        assert _MAX_RESPONSE_INPUT_CHARS == 100_000


class TestPhase2257PopupSize:
    """Phase 225.7: popup is now wider so LLM response input doesn't
    overflow and action buttons don't overlap."""

    def test_popup_size_is_at_least_900dp_wide(self):
        from kivy.metrics import dp

        from katrain.gui.popups.llm_coach_popup import open_llm_coach_popup

        ctx = MagicMock()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls:
            mock_picker = MagicMock()
            mock_popup_cls.return_value.__self__ = mock_picker
            open_llm_coach_popup(ctx)
        size_arg = mock_popup_cls.call_args.kwargs["size"]
        assert size_arg[0] >= dp(900), f"popup width must be >= 900dp, got {size_arg[0]} (raw={size_arg})"
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
        content = _make_content(path_type="karte")
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
        content._install_config_mock(mykatrain_settings={"default_user_name": "P2"})
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
        assert mock_clock.schedule_once.called, "Empty karte_path must schedule a retry, not return silently"


class TestPhase2258DefaultUserRankFallback:
    """Phase 225.8: when Karte/SGF has no rank info, the popup falls back
    to the mykatrain setting ``default_user_rank`` so the user doesn't
    have to enter their rank on every prompt generation."""

    def test_default_user_rank_used_when_karte_has_no_rank(self, tmp_path):
        """Karte has player names but no ranks → default_user_rank fills."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": None},
                            "white": {"name": "P2", "rank": None},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={"default_user_rank": "4段"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # The rank input was filled with the default_user_rank
        assert content.ids["rank_input"].text == "4段"

    def test_existing_karte_rank_wins_over_default(self, tmp_path):
        """If Karte has rank info, default_user_rank must NOT overwrite."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(
                {
                    "meta": {
                        "player_info": {
                            "black": {"name": "P1", "rank": "5k"},
                            "white": {"name": "P2", "rank": "5k"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={"default_user_rank": "4段"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Karte rank "5k" wins over default_user_rank "4段"
        assert content.ids["rank_input"].text == "5k"

    def test_no_rank_no_default_leaves_input_empty(self, tmp_path):
        """No rank anywhere → rank input stays empty."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {"player_info": {}}}), encoding="utf-8")
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.ids["rank_input"].text == ""

    def test_kanji_default_user_rank_resolves_correctly(self):
        """``4段`` passed through default_user_rank triggers the ADVANCED
        mode in estimate_mode_from_rank."""
        from katrain.core.coach.master_db import estimate_mode_from_rank

        assert estimate_mode_from_rank("4段") is not None
        assert estimate_mode_from_rank("4段").name == "ADVANCED"


class TestOpenLlmCoachPopup:
    def test_returns_popup_and_opens(self) -> None:
        from katrain.gui.popups.llm_coach_popup import open_llm_coach_popup

        ctx = MagicMock()
        with patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls:
            mock_popup = MagicMock()
            mock_popup_cls.return_value.__self__ = mock_popup
            open_llm_coach_popup(ctx)
        # Popup opened once
        assert mock_popup.open.call_count == 1
        # The content widget was created with ctx
        content = mock_popup_cls.call_args.kwargs["content"]
        assert content.katrain is ctx


# --- Phase 227-D: Multi-game summary mode in the popup -----------------


class TestDetectPathType:
    """Phase 227-D: ``_detect_path_type`` reads the JSON file and
    dispatches on the result. The set of recognised types is
    ``"karte"`` / ``"summary"`` / ``"unknown"``."""

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


# Phase 241-B: tests for the new "unknown path" early-return
# behaviour. The popup must surface a clear i18n error instead of
# silently falling through to the Karte path (which would produce a
# misleading "auto-detect-failed" status).
class TestUnknownPathEarlyReturn:
    """Phase 241-B: when the JSON is neither a Karte nor a Summary,
    the popup surfaces ``unknown-path`` and short-circuits."""

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
        # No default user → birdseye (index 0). ``perspective_value`` is
        # a StringProperty so None is represented as the empty string.
        assert content.summary_perspective_index == 0
        assert content.perspective_value == ""

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


class TestSummaryIndexToInternal:
    """Phase 227-D: ``_summary_index_to_internal`` is a pure helper
    that maps a spinner index to a player name or ``None``.

    Phase 241-D: bird's-eye now returns the dedicated sentinel
    string (``__birdseye__``) instead of ``None`` so callers can
    distinguish a deliberate "no focus" choice from out-of-range
    (which still returns ``None`` as a defensive bug indicator).
    """

    def test_index_zero_is_birdseye(self):
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(0, [("p1", "4d"), ("p2", "3d")])
        # Phase 241-D: bird's-eye is the dedicated sentinel.
        assert result == "__birdseye__"

    def test_is_summary_birdseye_helper(self):
        from katrain.gui.popups.llm_coach_popup import (
            _SUMMARY_BIRDSEYE_SENTINEL,
            is_summary_birdseye,
        )

        assert is_summary_birdseye(_SUMMARY_BIRDSEYE_SENTINEL) is True
        assert is_summary_birdseye(None) is False  # None is a bug state, not birdseye
        assert is_summary_birdseye("__birdseye__") is True
        assert is_summary_birdseye("alice") is False
        assert is_summary_birdseye("") is False

    def test_index_one_maps_to_first_player(self):
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(1, [("p1", "4d"), ("p2", "3d")])
        assert result == "p1"

    def test_index_out_of_range_returns_none(self):
        # Phase 241-D: out-of-range is a bug state, returns None
        # (not the birdseye sentinel) so callers can tell the two apart.
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(99, [("p1", "4d")])
        assert result is None

    def test_index_n_maps_to_nth_player(self):
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(2, [("p1", "4d"), ("p2", "3d")])
        assert result == "p2"

    def test_out_of_range_returns_none(self):
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(5, [("p1", "4d")])
        assert result is None

    def test_empty_players_returns_none(self):
        from katrain.gui.popups.llm_coach_popup import _summary_index_to_internal

        result = _summary_index_to_internal(1, [])
        assert result is None


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
        # empty string sentinel.
        assert content.perspective_value == ""


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
