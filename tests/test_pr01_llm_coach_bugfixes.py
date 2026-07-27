"""Regression tests for the LLM Coach PR-01 fixes.

PR-01 covers four user-facing / pipeline bugs found during the LLM
Coach investigation:

- ③ ``on_perspective_changed`` previously ran its body twice (a merge
  residue duplicated the block) — the second invocation executed
  ``_populate_rank_and_perspective`` again and, for the summary path,
  fired ``on_summary_perspective_changed`` twice. We assert the body
  runs exactly once per call.
- ④ ``_build_karte_json_string_impl`` dropped ``target_visits`` (and
  the pre-computed ``snapshot``) on its way to ``build_karte_json``,
  so batch callers could not influence the effective reliability
  threshold and the snapshot was rebuilt internally. We assert that
  the wrapper forwards both arguments.
- ⑥ The browse button wrote the chosen file path via
  ``_set_widget_text`` (which does NOT fire ``on_text_validate``),
  so the popup kept showing the previous file's player info / rank.
  We assert that browse now invalidates the path-bound cache and
  triggers ``on_path_changed``.
- H-a ``_VALIDATE_COOLDOWN_SECS`` was defined but never consulted —
  double-clicking the validate button ran the validator twice. We
  assert the cooldown drops the second call within the window.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from tests.llm_coach_popup_helpers import _make_content, kivy_required

pytestmark = kivy_required


class TestPerspectiveChangedRunsOnce:
    """PR-01 ③: the merge-residue duplicate block is gone."""

    def test_body_executes_once_per_call(self) -> None:
        content = _make_content()
        # path_type "karte" exercises the non-summary branch we want to
        # assert runs exactly once (before PR-01 it ran twice).
        content.path_type = "karte"
        with (
            patch.object(content, "_populate_rank_and_perspective") as mock_populate,
            patch.object(content, "_get_widget", return_value=MagicMock(text="黒 (B)")),
        ):
            content.on_perspective_changed()
        assert mock_populate.call_count == 1, (
            "on_perspective_changed should call _populate_rank_and_perspective once; "
            f"got {mock_populate.call_count} (PR-01 ③ regression — duplicate block)."
        )


class TestBuilderForwardsTargetVisitsAndSnapshot:
    """PR-01 ④: ``_build_karte_json_string_impl`` now forwards both args."""

    def test_target_visits_and_snapshot_are_passed_through(self) -> None:
        # Use a dummy snapshot to verify the new ``snapshot=`` kwarg
        # is forwarded (was previously silently dropped).
        sentinel_snapshot = object()
        captured: dict[str, Any] = {}

        def fake_build_karte_json(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {}

        # ``builder.py`` imports ``build_karte_json`` lazily inside
        # ``_build_karte_json_string_impl``, so patching at the module
        # where it is *looked up* (json_export) is the reliable hook.
        with patch(
            "katrain.core.reports.karte.json_export.build_karte_json",
            side_effect=fake_build_karte_json,
        ):
            from katrain.core.reports.karte.builder import _build_karte_json_string_impl

            _build_karte_json_string_impl(
                game=MagicMock(),
                snapshot=sentinel_snapshot,
                level="",
                player_filter=None,
                target_visits=400,
                lang="ja",
                max_critical_3_moves=3,
            )
        assert captured.get("target_visits") == 400, (
            "_build_karte_json_string_impl must forward target_visits to build_karte_json "
            f"(got {captured.get('target_visits')!r}). PR-01 ④ regression."
        )
        assert captured.get("snapshot") is sentinel_snapshot, (
            "_build_karte_json_string_impl must forward the pre-computed snapshot "
            "so build_karte_json does not rebuild it internally. PR-01 ④ regression."
        )


class TestBrowseInvalidatesPathBoundCache:
    """PR-01 ⑥: browse must trigger ``on_path_changed`` and clear stale cache."""

    def test_browse_triggers_on_path_changed(self) -> None:
        content = _make_content()
        with (
            patch("katrain.gui.popups.llm_coach_popup.I18NPopup"),
            patch("katrain.gui.popups.llm_coach_popup.I18NFileBrowser") as mock_browser_cls,
        ):
            mock_browser = MagicMock()
            mock_browser_cls.return_value = mock_browser
            with patch.object(content, "on_path_changed") as mock_on_path:
                content.on_browse_karte()
                # Simulate the OK button click on the bound callback.
                on_success = None
                for call in mock_browser.bind.call_args_list:
                    if "on_success" in call.kwargs:
                        on_success = call.kwargs["on_success"]
                        break
                assert on_success is not None, "on_success not bound — on_browse_karte regression"
                # File picker returned a path.
                mock_browser.filename = "/tmp/dummy_karte.json"
                mock_browser.selection = []
                on_success(mock_browser)
        mock_on_path.assert_called_once_with()

    def test_on_path_changed_clears_stale_player_info(self) -> None:
        content = _make_content()
        # Pretend the user previously opened file A; the cache now
        # references A. When the path changes (Enter or browse) the
        # cache must be cleared so the generate/validate guards do
        # not silently reuse A's data for B.
        content._last_player_info = {"source": "karte_meta", "black_name": "OldName"}
        content._last_player_info_path = "/old/karte_A.json"
        # No readable path populated in the input — the helper short-
        # circuits the populate call but still runs the cache-clear.
        with patch.object(content, "_populate_rank_and_perspective"):
            content.on_path_changed()
        assert content._last_player_info == {}, (
            "on_path_changed must clear _last_player_info to prevent stale reuse "
            f"(got {content._last_player_info!r}). PR-01 ⑥ regression."
        )
        assert content._last_player_info_path == "", (
            "on_path_changed must clear _last_player_info_path "
            f"(got {content._last_player_info_path!r}). PR-01 ⑥ regression."
        )


class TestValidateCooldown:
    """PR-01 H-a: double-click validate is dropped within the cooldown window."""

    def test_second_call_within_window_returns_false(self) -> None:
        content = _make_content()
        # First call must succeed and stamp the timestamp.
        assert content._respect_validate_cooldown() is True
        # Immediate second call must be rejected.
        assert content._respect_validate_cooldown() is False

    def test_call_after_window_succeeds(self) -> None:
        content = _make_content()
        # Rewind the last stamp so the next call is well outside the
        # window — uses ``time.monotonic`` so no real wall-clock wait.
        content._last_validate_at = 0.0
        assert content._respect_validate_cooldown() is True
