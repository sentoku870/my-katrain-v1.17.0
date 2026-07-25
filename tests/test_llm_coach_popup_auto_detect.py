"""Auto-detect / open-popup tests for the LLM Coach popup.

Phase 5 of the test-suite audit extracts these from
``tests/test_llm_coach_popup.py``. They cover the popup's auto-detect
pipeline (rank, perspective, default-user fallback) and the
``open_llm_coach_popup`` factory function.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from tests.conftest import make_karte_with_player_info
from tests.llm_coach_popup_helpers import _make_content, _resolve_i18n, kivy_required

pytestmark = kivy_required


class TestPhase2256RankAutoFill:
    """Phase 225.6: Karte/SGF から rank を自動取得し input に反映"""

    def test_populate_rank_and_perspective_sets_rank_when_empty(self, tmp_path):
        content = _make_content(path_type="karte")
        # Simulate karte with player_info
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", "4d", "P2", "3d")),
            encoding="utf-8",
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Phase 272-B: rank_input is now a Spinner. The detected rank
        # "4d" (auto perspective → black) is converted to its mode key
        # "advanced", then to the localised label.
        assert content.ids["rank_input"].text == "ADVANCED（三段〜五段）"
        # ``detected_rank`` keeps the raw value so downstream consumers
        # (refresh hint, status) can display the original notation.
        assert content.detected_rank == "4d"
        assert (
            "rank-auto" in content.ids["rank_auto_label"].text or "auto" in content.ids["rank_auto_label"].text.lower()
        )

    def test_does_not_overwrite_user_typed_rank(self, tmp_path):
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", "4d", "P2", "3d")),
            encoding="utf-8",
        )
        content.ids["karte_path_input"].text = str(karte)
        # Phase 272-B: simulate user selecting ADVANCED in the Spinner.
        content.ids["rank_input"].text = "ADVANCED（三段〜五段）"
        content._populate_rank_and_perspective()
        # User Spinner selection is preserved.
        assert content.ids["rank_input"].text == "ADVANCED（三段〜五段）"

    def test_perspective_auto_label_uses_detected_color(self, tmp_path):
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", "4d", "P2", "3d")),
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
        # Phase 272-B: Spinner stores localised label.
        content.ids["rank_input"].text = "INTERMEDIATE（9級〜4級）"
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

    def test_player_color_none_when_auto_no_detection_blocks_generate(self, tmp_path):
        """Phase 272-B: when auto mode + no detection, generation is BLOCKED
        (not silently allowed with PlayerColor=unknown)."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {}}), encoding="utf-8")
        content.ids["karte_path_input"].text = str(karte)
        content.ids["rank_input"].text = "INTERMEDIATE（9級〜4級）"
        content.perspective_value = "auto"
        content.detected_player_color = None
        # Cache the player info so the error message can name them.
        content._last_player_info = {
            "black": {"name": "Alice"},
            "white": {"name": "Bob"},
        }
        # Stub the player-settings reader so default_user is populated.
        content._read_player_settings = lambda: {
            "default_user": "Carol",
            "default_user_rank": "",
            "general_player_rank": "",
        }
        with (
            patch(
                "katrain.gui.features.llm_coach.build_llm_prompt",
                return_value=(True, "# PROMPT"),
            ) as spy,
            patch("katrain.gui.popups.llm_coach_popup.Clipboard"),
        ):
            content.on_generate_and_copy()
        # Generation was blocked — build_llm_prompt was NOT called.
        assert not spy.called


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
            json.dumps(make_karte_with_player_info("AnyUser", "4d", "Opponent", "3d")),
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
            json.dumps(make_karte_with_player_info("P1", "4d", "P2", "3d")),
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
            json.dumps(make_karte_with_player_info("P1", "5k", "P2", "6k")),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={"default_user_name": "P1"})
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Phase 272-B: rank_input stores the Spinner label. 5k / 6k both
        # map to "INTERMEDIATE（9級〜4級）".
        assert content.ids["rank_input"].text == "INTERMEDIATE（9級〜4級）"

    def test_rank_fallback_to_general_player_rank(self, tmp_path):
        content = _make_content(path_type="karte")
        # Phase 272-B: when Karte has no rank info, the analysis-tab
        # Spinner value (general_player_rank) is the highest-priority
        # fallback. ``default_user_rank`` is the legacy third slot.
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", None, "P2", None)),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(
            mykatrain_settings={"default_user_name": "P1"},
            general_player_rank="advanced",
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.ids["rank_input"].text == "ADVANCED（三段〜五段）"


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


class TestPhase242BPerspectiveConstant:
    """Phase 242-B: ``_PERSPECTIVE_AUTO_INTERNAL`` is the single source
    of truth for the "auto" sentinel value. The previous convention used
    the empty string ``""`` which was confusing and inconsistent."""

    def test_constant_value(self):
        from katrain.gui.popups.llm_coach_popup import _PERSPECTIVE_AUTO_INTERNAL

        assert _PERSPECTIVE_AUTO_INTERNAL == "auto"

    def test_perspective_value_uses_constant(self):
        """StringProperty default is the constant, not a hard-coded literal."""
        from katrain.gui.popups.llm_coach_popup import (
            _PERSPECTIVE_AUTO_INTERNAL,
            LLMCoachPopupContent,
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
        # Phase 287-E follow-up: clamp_popup_size shrinks the popup on
        # small windows (CI's headless backend reports 800x600). Patch
        # Window via the ``clamp_popup_size`` lookup path. The helper
        # does ``getattr(Window, "width", None)`` at call time, so we
        # patch ``kivy.core.window`` rather than the symbol.
        fake_window = type("FakeWindow", (), {"width": 1920, "height": 1080})()
        fake_module = type("M", (), {"Window": fake_window})()
        with (
            patch.dict("sys.modules", {"kivy.core.window": fake_module}),
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup") as mock_popup_cls,
        ):
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
            json.dumps(make_karte_with_player_info("P1", "4d", "P2", "3d")),
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
    """Phase 225.8 + Phase 272-B: Karte/SGF or ``default_user_rank`` fallback.

    Phase 272-B reordered the priority chain so ``general_player_rank``
    (analysis tab Spinner) wins first; Karte/SGF and ``default_user_rank``
    remain as the 2nd and 3rd slots respectively.
    """

    def test_default_user_rank_used_when_no_karte_no_general(self, tmp_path):
        """Karte has player names but no ranks; general_player_rank is empty.
        ``default_user_rank`` fills the rank_input Spinner with the
        corresponding mode key label."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", None, "P2", None)),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(
            mykatrain_settings={"default_user_rank": "4段"},
            general_player_rank="",  # Phase 272-B: must be empty for the legacy fallback to fire
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Phase 272-B: 4段 → "advanced" → Spinner label.
        assert content.ids["rank_input"].text == "ADVANCED（三段〜五段）"

    def test_existing_karte_rank_wins_over_default(self, tmp_path):
        """If Karte has rank info, default_user_rank must NOT overwrite."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", "5k", "P2", "5k")),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(
            mykatrain_settings={"default_user_rank": "4段"},
            general_player_rank="",
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # Phase 272-B: 5k → "intermediate" → Spinner label.
        assert content.ids["rank_input"].text == "INTERMEDIATE（9級〜4級）"

    def test_general_player_rank_wins_over_karte(self, tmp_path):
        """Phase 272-B: analysis-tab Spinner is the top priority, beats Karte."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(
            json.dumps(make_karte_with_player_info("P1", "5k", "P2", "5k")),
            encoding="utf-8",
        )
        content.katrain = MagicMock()
        content._install_config_mock(
            mykatrain_settings={"default_user_rank": "4段"},
            general_player_rank="advanced",
        )
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        # general_player_rank "advanced" beats Karte "5k" and
        # default_user_rank "4段".
        assert content.ids["rank_input"].text == "ADVANCED（三段〜五段）"

    def test_no_rank_no_default_leaves_input_empty(self, tmp_path):
        """No rank anywhere → rank input stays empty."""
        content = _make_content(path_type="karte")
        karte = tmp_path / "k.json"
        karte.write_text(json.dumps({"meta": {"player_info": {}}}), encoding="utf-8")
        content.katrain = MagicMock()
        content._install_config_mock(mykatrain_settings={}, general_player_rank="")
        content.ids["karte_path_input"].text = str(karte)
        content._populate_rank_and_perspective()
        assert content.ids["rank_input"].text == ""

    def test_kanji_default_user_rank_resolves_correctly(self):
        """``4段`` passed through default_user_rank triggers the ADVANCED
        mode in estimate_mode_from_rank.
        """
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
