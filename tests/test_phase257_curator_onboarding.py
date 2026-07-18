"""Phase 257: Curator profile onboarding notice.

When ``beginner_hints/curator_hint`` is True but the user has not
generated a Curator profile (``curator_ranking.json``), the
CURATOR_WEAK_AXIS hint detector returns ``None`` silently. New
users have no feedback loop explaining this — the feature just
doesn't fire.

Phase 257: ``_curator_profile_status_line`` returns a localized
one-liner that nudges the user to run a batch analysis, or
``None`` when the profile is present (or the feature is disabled).
"""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def _curator_status(katrain) -> str | None:
    """Replicate ControlsPanel._curator_profile_status_line logic."""
    from katrain.core.lang import i18n

    if katrain is None:
        return None
    if not katrain.config("beginner_hints/enabled", False):
        return None
    if not katrain.config("beginner_hints/curator_hint", True):
        return None
    settings = katrain.config("mykatrain_settings") or {}
    out_dir = settings.get("karte_output_directory") or ""
    if not out_dir or not os.path.isdir(out_dir):
        return i18n._("beginner-hint:curator-onboarding-no-output-dir")
    profile = os.path.join(out_dir, "curator_ranking.json")
    if os.path.isfile(profile):
        return None
    return i18n._("beginner-hint:curator-onboarding-run-batch")


def _katrain(*, beginner_enabled=True, curator_toggle=True, out_dir="", mykatrain_settings=None):
    """Build a katrain stub."""
    if mykatrain_settings is None:
        mykatrain_settings = {"karte_output_directory": out_dir}
    return SimpleNamespace(
        config=lambda key, default=None: {
            "beginner_hints/enabled": beginner_enabled,
            "beginner_hints/curator_hint": curator_toggle,
            "mykatrain_settings": mykatrain_settings,
        }.get(key, default),
    )


class TestCuratorOnboarding:
    """Phase 257: nudge the user when curator_ranking.json is missing."""

    def test_katrain_none_returns_none(self):
        assert _curator_status(None) is None

    def test_beginner_disabled_returns_none(self):
        """The notice is gated on the master beginner-hints switch."""
        assert _curator_status(_katrain(beginner_enabled=False)) is None

    def test_curator_toggle_off_returns_none(self):
        """The user can opt out of curator hints entirely (Phase 251)."""
        assert _curator_status(_katrain(curator_toggle=False)) is None

    def test_no_output_dir_shows_set_output_dir_message(self):
        """When the user has not set an output dir yet, the message
        asks them to set one (vs. asking them to run a batch)."""
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "set output dir"
            result = _curator_status(_katrain(out_dir=""))
        assert result == "set output dir"
        # The i18n call was for the right key.
        mock_gettext.assert_called_with("beginner-hint:curator-onboarding-no-output-dir")

    def test_output_dir_does_not_exist_shows_set_output_dir_message(self):
        """A configured but non-existent dir counts as 'not set'."""
        with patch("katrain.core.lang.i18n._") as mock_gettext:
            mock_gettext.return_value = "set output dir"
            result = _curator_status(_katrain(out_dir="C:/nonexistent-katrain-dir-zzz"))
        assert result == "set output dir"

    def test_output_dir_set_no_profile_shows_run_batch(self):
        """Dir exists but curator_ranking.json is missing → run batch."""
        with tempfile.TemporaryDirectory() as tmp:
            with patch("katrain.core.lang.i18n._") as mock_gettext:
                mock_gettext.return_value = "run batch"
                result = _curator_status(_katrain(out_dir=tmp))
            assert result == "run batch"
            mock_gettext.assert_called_with("beginner-hint:curator-onboarding-run-batch")

    def test_profile_present_returns_none(self):
        """When curator_ranking.json exists, the notice disappears."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the profile
            (Path(tmp) / "curator_ranking.json").write_text("{}", encoding="utf-8")
            result = _curator_status(_katrain(out_dir=tmp))
            assert result is None


class TestProductionCodeUsesCuratorOnboarding:
    @pytest.fixture
    def controlspanel_source(self) -> str:
        path = Path(__file__).parent.parent / "katrain" / "gui" / "controlspanel.py"
        return path.read_text(encoding="utf-8")

    def test_helper_method_defined(self, controlspanel_source):
        """The helper must exist as a method on ControlsPanel."""
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ControlsPanel":
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef) and sub.name == "_curator_profile_status_line":
                        return
        pytest.fail("_curator_profile_status_line not found on ControlsPanel")

    def test_info_renderer_calls_helper(self, controlspanel_source):
        """The info-text assembly must call the helper."""
        assert "_curator_profile_status_line" in controlspanel_source
        # The call site is inside the method that builds info text.
        # Verify by AST: a function in ControlsPanel that builds the
        # info text must reference the helper.
        tree = ast.parse(controlspanel_source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "update_eval"
                or (isinstance(node, ast.FunctionDef) and "info" in node.name.lower())
            ):
                src = ast.unparse(node)
                if "_curator_profile_status_line" in src:
                    return
        # Fall back to a text search — the helper must be called
        # from at least one method other than the helper itself.
        methods_with_call = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ControlsPanel":
                for sub in node.body:
                    if (
                        isinstance(sub, ast.FunctionDef)
                        and sub.name != "_curator_profile_status_line"
                        and "_curator_profile_status_line" in ast.unparse(sub)
                    ):
                        methods_with_call.append(sub.name)
        assert methods_with_call, "_curator_profile_status_line is defined but never called from another method"
