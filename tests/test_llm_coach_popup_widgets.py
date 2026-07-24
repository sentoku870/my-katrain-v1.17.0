"""Widget-text and Phase 2253/2255 regression tests for the LLM Coach popup.

Phase 5 of the test-suite audit extracts these from
``tests/test_llm_coach_popup.py``. They all exercise the popup's
``_read_text`` / ``_set_widget_text`` / ``_set_status`` / ``_set_result``
helpers and the Phase 225.3 / 225.5 fixes that route widget access
through ``self.ids`` instead of stale ``ObjectProperty`` references.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.llm_coach_popup_helpers import _make_content, kivy_required

pytestmark = kivy_required


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
