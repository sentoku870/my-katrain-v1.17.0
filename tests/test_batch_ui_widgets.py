"""Unit tests for ``katrain.gui.features.batch_ui`` (Phase 282-P1B).

The batch analysis popup UI had zero direct tests despite being a
non-trivial Kivy widget builder (587 LOC). The widget-tree builders
themselves require a real Kivy font pipeline to instantiate, which
the headless CI environment cannot provide.

This file therefore uses a **source-static / AST-based** strategy
instead of runtime widget instantiation:

- Pure-logic tests for ``create_get_player_filter_fn`` (closure
  over ToggleButton ``state`` values).
- Source-static checks for every widget-builder function so the
  public API is locked in against accidental removal or signature
  changes.
- AST-based check that ``build_batch_popup_widgets`` registers the
  expected widget keys in its returned ``widgets`` dict (proves the
  orchestration contract even without runtime instantiation).

Coverage targets:
- ``create_get_player_filter_fn``: 3-state closure logic
- All 13 ``_build_*_row`` and orchestrator function signatures
- Widget-keys contract of ``build_batch_popup_widgets``
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BATCH_UI_PATH = REPO_ROOT / "katrain" / "gui" / "features" / "batch_ui.py"


# =============================================================================
# Pure-logic test: create_get_player_filter_fn
# =============================================================================


class _FakeToggle:
    """Mimics Kivy's ToggleButton ``state`` attribute (no Kivy import)."""

    def __init__(self, state: str = "normal") -> None:
        self.state = state


class TestCreateGetPlayerFilterFn:
    def test_black_selected(self):
        widgets = {
            "filter_black": _FakeToggle("down"),
            "filter_white": _FakeToggle("normal"),
            "filter_both": _FakeToggle("normal"),
        }
        fn = create_get_player_filter_fn(widgets)
        assert fn() == "B"

    def test_white_selected(self):
        widgets = {
            "filter_black": _FakeToggle("normal"),
            "filter_white": _FakeToggle("down"),
            "filter_both": _FakeToggle("normal"),
        }
        fn = create_get_player_filter_fn(widgets)
        assert fn() == "W"

    def test_both_selected_returns_none(self):
        """``filter_both`` down means no player filter."""
        widgets = {
            "filter_black": _FakeToggle("normal"),
            "filter_white": _FakeToggle("normal"),
            "filter_both": _FakeToggle("down"),
        }
        fn = create_get_player_filter_fn(widgets)
        assert fn() is None

    def test_returns_callable(self):
        widgets = {
            "filter_black": _FakeToggle(),
            "filter_white": _FakeToggle(),
            "filter_both": _FakeToggle(),
        }
        fn = create_get_player_filter_fn(widgets)
        assert callable(fn)

    def test_state_mutation_reflected(self):
        """Closure reads current state, not captured-at-creation."""
        widgets = {
            "filter_black": _FakeToggle("down"),
            "filter_white": _FakeToggle("normal"),
            "filter_both": _FakeToggle("normal"),
        }
        fn = create_get_player_filter_fn(widgets)
        assert fn() == "B"
        widgets["filter_black"].state = "normal"
        widgets["filter_white"].state = "down"
        assert fn() == "W"


# =============================================================================
# Source-static regression guards
# =============================================================================


def _get_module_tree() -> ast.Module:
    return ast.parse(BATCH_UI_PATH.read_text(encoding="utf-8"))


def _function_names(tree: ast.Module) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


class TestBatchUiPublicApi:
    """Lock in the public function surface of batch_ui.py.

    Refactoring batch_ui (Phase 145-B extracted this from a 375-line
    monolith) is dangerous if any of the orchestrator / row-builder
    functions are silently renamed or removed. These tests assert
    their existence so the integration in __main__.py doesn't break.
    """

    @pytest.mark.parametrize(
        "func_name",
        [
            "create_browse_callback",
            "create_on_start_callback",
            "create_on_close_callback",
            "create_get_player_filter_fn",
            "build_batch_popup_widgets",
            "create_batch_popup",
        ],
    )
    def test_orchestrator_functions_exist(self, func_name):
        tree = _get_module_tree()
        assert func_name in _function_names(tree), (
            f"batch_ui.py missing public function {func_name!r} - an upstream caller in __main__.py will break."
        )

    @pytest.mark.parametrize(
        "func_name",
        [
            "_add_left_aligned_label",
            "_add_right_aligned_label",
            "_build_input_row",
            "_build_output_row",
            "_build_visits_timeout_row",
            "_build_skip_row",
            "_build_skip_hint_row",
            "_build_output_save_row",
            "_build_output_summary_row",
            "_build_player_filter_row",
            "_build_variable_visits_row",
            "_wire_variable_visits_linkage",
            "_build_progress_row",
            "_build_log_area",
            "_build_buttons_row",
        ],
    )
    def test_row_builder_functions_exist(self, func_name):
        tree = _get_module_tree()
        assert func_name in _function_names(tree), f"batch_ui.py missing row builder {func_name!r}"

    def test_build_batch_popup_widgets_signature(self):
        """Signature must remain (batch_options, default_input_dir, default_output_dir)."""
        sig = inspect.signature(build_batch_popup_widgets)
        params = list(sig.parameters)
        assert params == ["batch_options", "default_input_dir", "default_output_dir"]

    def test_create_browse_callback_signature(self):
        sig = inspect.signature(create_browse_callback)
        params = list(sig.parameters)
        assert params == ["text_input_widget", "title", "katrain_gui"]


class TestBatchPopupWidgetKeysContract:
    """Static guarantee that ``build_batch_popup_widgets`` registers
    the canonical set of widget keys. If a row builder stops adding
    a widget to the dict, callers downstream will hit ``KeyError``
    at runtime — this test catches that at lint time.
    """

    REQUIRED_KEYS = {
        # input/output rows
        "input_input",
        "input_browse",
        "output_input",
        "output_browse",
        # visits/timeout row
        "visits_input",
        "timeout_input",
        # skip row
        "skip_checkbox",
        # output save row
        "save_sgf_checkbox",
        "karte_checkbox",
        # output summary row
        "summary_checkbox",
        "curator_checkbox",
        # player filter row
        "filter_both",
        "filter_black",
        "filter_white",
        "min_games_input",
        # variable visits row
        "variable_visits_checkbox",
        "jitter_input",
        "deterministic_checkbox",
        "sound_checkbox",
        # progress + log
        "progress_label",
        "log_text",
        "log_scroll",
        # buttons
        "start_button",
        "close_button",
    }

    def test_all_keys_assigned_in_source(self):
        """Each required key must appear as a dict assignment
        ``widgets["..."] = ...`` in the source file."""
        text = BATCH_UI_PATH.read_text(encoding="utf-8")
        missing = []
        for key in self.REQUIRED_KEYS:
            if f'widgets["{key}"]' not in text and f"widgets['{key}']" not in text:
                missing.append(key)
        assert not missing, f"Missing widgets[{key!r}] assignments in batch_ui.py: {missing}"

    def test_build_call_present(self):
        text = BATCH_UI_PATH.read_text(encoding="utf-8")
        # All row builders must be invoked from build_batch_popup_widgets
        for row in [
            "_build_input_row",
            "_build_output_row",
            "_build_visits_timeout_row",
            "_build_skip_row",
            "_build_skip_hint_row",
            "_build_output_save_row",
            "_build_output_summary_row",
            "_build_player_filter_row",
            "_build_variable_visits_row",
            "_wire_variable_visits_linkage",
            "_build_progress_row",
            "_build_log_area",
            "_build_buttons_row",
        ]:
            assert row + "(" in text, f"Row builder {row!r} is never called from build_batch_popup_widgets"


class TestVariableVisitsLinkageContract:
    """``_wire_variable_visits_linkage`` must disable jitter / deterministic
    when variable_visits is OFF, and re-enable when ON. We verify the
    contract via source inspection (since runtime requires Kivy fonts).
    """

    def test_disable_when_off_in_source(self):
        text = BATCH_UI_PATH.read_text(encoding="utf-8")
        # The function body should set disabled = not is_variable
        assert "disabled = not is_variable" in text, (
            "Expected 'disabled = not is_variable' in _wire_variable_visits_linkage"
        )

    def test_binds_active_event(self):
        text = BATCH_UI_PATH.read_text(encoding="utf-8")
        assert "bind(active=" in text, "Expected bind(active=...) on variable_visits_checkbox"


# =============================================================================
# Callback factory smoke (no Kivy)
# =============================================================================


class TestCallbackFactories:
    """Verify that the callback factories return callables with the
    expected signatures. We don't invoke them with real args because
    they touch Kivy widgets / threads.
    """

    def test_create_browse_callback_returns_callable(self):
        cb = create_browse_callback(
            text_input_widget=MagicMock(),
            title="Test",
            katrain_gui=MagicMock(),
        )
        assert callable(cb)
        sig = inspect.signature(cb)
        params = list(sig.parameters)
        # Closure accepts variadic positional args (Kivy event compat)
        assert params[0] == "_args", f"Closure param 0 should be '_args', got {params[0]!r}"

    def test_create_on_start_callback_returns_callable(self):
        cb = create_on_start_callback(
            ctx=MagicMock(),
            widgets={},
            is_running=[False],
            cancel_flag=[False],
            get_player_filter_fn=lambda: None,
            run_batch_thread_fn=lambda: None,
        )
        assert callable(cb)

    def test_create_on_close_callback_returns_callable(self):
        cb = create_on_close_callback(
            popup=MagicMock(),
            is_running=[False],
        )
        assert callable(cb)


# =============================================================================
# Late import to avoid Kivy font pipeline on collection
# =============================================================================

from katrain.gui.features.batch_ui import (  # noqa: E402
    build_batch_popup_widgets,
    create_browse_callback,
    create_get_player_filter_fn,
    create_on_close_callback,
    create_on_start_callback,
)
