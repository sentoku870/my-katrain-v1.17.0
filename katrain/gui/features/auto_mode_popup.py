# katrain/gui/features/auto_mode_popup.py
#
# Phase 89: Auto Mode Popup - "Just Make It Work" Mode
#
# This module provides the Auto Setup tab content for first-time users:
# - Test analysis with clear success/failure UI
# - CPU fallback when OpenCL fails
# - Lightweight model (b10c128) detection
#
# Key design decisions:
# - AutoModeState class for per-popup state (not module-global)
# - Clock.schedule_once() for thread-safe UI updates
# - Worker thread for non-blocking engine operations

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from katrain.core.auto_setup import (
    get_model_search_dirs,
    resolve_auto_engine_settings,
)
from katrain.core.constants import OUTPUT_DEBUG, OUTPUT_ERROR, STATUS_INFO
from katrain.core.lang import i18n
from katrain.core.test_analysis import (
    ErrorCategory,
    TestAnalysisResult,
    should_offer_cpu_fallback,
    should_offer_restart,
)
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# State Management (per-popup, not module-global)
# =============================================================================


class AutoModeState:
    """Auto mode popup state management (per-instance).

    Important: Use per-instance state, NOT module-global variables.
    This ensures correct behavior if multiple popups are opened.
    """

    def __init__(self):
        self._test_running = False
        self._lock = threading.Lock()

    def try_start_test(self) -> bool:
        """Try to start a test. Returns False if already running."""
        with self._lock:
            if self._test_running:
                return False
            self._test_running = True
            return True

    def finish_test(self) -> None:
        """Mark test as finished."""
        with self._lock:
            self._test_running = False


# =============================================================================
# Main Entry Point
# =============================================================================


def show_auto_mode_content(
    ctx: "FeatureContext",
    layout: BoxLayout,
    katrain: "any",  # KaTrainGui instance (for engine access)
) -> None:
    """Build Auto Setup tab content.

    Args:
        ctx: Feature context for config/logging.
        layout: Parent layout to add widgets to.
        katrain: KaTrainGui instance for engine operations.
    """
    state = AutoModeState()

    # Clear existing content
    layout.clear_widgets()

    # Header
    header = Label(
        text=i18n._("mykatrain:settings:auto_mode_header"),
        font_size="18sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
        valign="middle",
    )
    header.bind(size=header.setter("text_size"))
    layout.add_widget(header)

    # Description
    desc_text = i18n._("mykatrain:settings:auto_mode_description")
    desc = Label(
        text=desc_text,
        font_size="14sp",
        size_hint_y=None,
        height="60dp",
        halign="center",
        valign="top",
    )
    desc.bind(size=desc.setter("text_size"))
    layout.add_widget(desc)

    # Result area (scrollable)
    result_scroll = ScrollView(size_hint=(1, 1))
    result_area = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        padding=10,
        spacing=5,
    )
    result_area.bind(minimum_height=result_area.setter("height"))
    result_scroll.add_widget(result_area)
    layout.add_widget(result_scroll)

    # Test button
    test_btn = Button(
        text=i18n._("mykatrain:settings:test_analysis"),
        size_hint_y=None,
        height="48dp",
        background_color=Theme.PRIMARY_COLOR,
    )

    def on_test_clicked(btn):
        _on_test_analysis_clicked(ctx, katrain, state, result_area, btn)

    test_btn.bind(on_release=on_test_clicked)
    layout.add_widget(test_btn)


# =============================================================================
# Test Analysis Handler
# =============================================================================


def _on_test_analysis_clicked(
    ctx: "FeatureContext",
    katrain: "any",
    state: AutoModeState,
    result_area: BoxLayout,
    btn: Button,
) -> None:
    """Handle test analysis button click.

    Args:
        ctx: Feature context.
        katrain: KaTrainGui instance.
        state: Per-popup state instance.
        result_area: BoxLayout to show results.
        btn: The clicked button.
    """
    if not state.try_start_test():
        return  # Already running

    btn.disabled = True
    Clock.schedule_once(lambda dt: _show_testing_status(result_area), 0)

    def run_test():
        try:
            result = _execute_test_analysis(ctx, katrain)
        finally:
            state.finish_test()

        # Update UI on main thread
        Clock.schedule_once(
            lambda dt: _on_test_complete(result, result_area, btn, ctx, katrain, state),
            0,
        )

    threading.Thread(target=run_test, daemon=True).start()


def _show_testing_status(result_area: BoxLayout) -> None:
    """Show testing in progress status."""
    result_area.clear_widgets()
    status = Label(
        text=i18n._("mykatrain:settings:testing_in_progress"),
        font_size="16sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
    )
    status.bind(size=status.setter("text_size"))
    result_area.add_widget(status)


def _execute_test_analysis(
    ctx: "FeatureContext",
    katrain: "any",
    timeout_seconds: float = 15.0,
) -> TestAnalysisResult:
    """Execute test analysis.

    Args:
        ctx: Feature context.
        katrain: KaTrainGui instance.
        timeout_seconds: Timeout for analysis response.

    Returns:
        TestAnalysisResult with success/failure details.
    """
    # First check if lightweight model exists
    base_engine = ctx.config("engine", {})
    settings, error_result = resolve_auto_engine_settings(base_engine)

    if error_result is not None:
        return error_result

    # Use katrain's verification method
    return katrain._verify_engine_works(timeout_seconds)


def _on_test_complete(
    result: TestAnalysisResult,
    result_area: BoxLayout,
    btn: Button,
    ctx: "FeatureContext",
    katrain: "any",
    state: AutoModeState,
) -> None:
    """Handle test completion.

    Args:
        result: Test analysis result.
        result_area: BoxLayout to show results.
        btn: Test button to re-enable.
        ctx: Feature context.
        katrain: KaTrainGui instance.
        state: Per-popup state instance.
    """
    btn.disabled = False
    result_area.clear_widgets()

    # Save result to config
    katrain.save_auto_setup_result(result.success)

    if result.success:
        _render_success_ui(result, result_area, katrain)
    elif result.error_category == ErrorCategory.LIGHTWEIGHT_MISSING:
        _render_lightweight_missing_ui(result_area, ctx)
    elif result.error_category == ErrorCategory.TIMEOUT:
        _render_timeout_ui(result, result_area, ctx, katrain, state)
    else:
        _render_failure_ui(result, result_area, ctx, katrain, state)


# =============================================================================
# Result UI Renderers
# =============================================================================


def _render_success_ui(
    result: TestAnalysisResult,
    layout: BoxLayout,
    katrain: "any",
) -> None:
    """Render success UI.

    Args:
        result: Test analysis result.
        layout: BoxLayout to add widgets to.
        katrain: KaTrainGui instance.
    """
    # Success icon and message
    backend = katrain.engine.get_backend_type() if katrain.engine else "Unknown"
    success_text = i18n._("mykatrain:settings:test_success").format(engine=backend)

    success_label = Label(
        text=f"✓ {success_text}",
        font_size="16sp",
        size_hint_y=None,
        height="60dp",
        halign="center",
        valign="middle",
        color=(0.2, 0.8, 0.2, 1),  # Green
    )
    success_label.bind(size=success_label.setter("text_size"))
    layout.add_widget(success_label)


def _render_failure_ui(
    result: TestAnalysisResult,
    layout: BoxLayout,
    ctx: "FeatureContext",
    katrain: "any",
    state: AutoModeState,
) -> None:
    """Render failure UI with recovery options.

    Args:
        result: Test analysis result.
        layout: BoxLayout to add widgets to.
        ctx: Feature context.
        katrain: KaTrainGui instance.
        state: Per-popup state instance.
    """
    # Error message
    error_msg = result.error_message or i18n._("mykatrain:settings:unknown_error")
    error_label = Label(
        text=f"✗ {error_msg}",
        font_size="14sp",
        size_hint_y=None,
        height="80dp",
        halign="center",
        valign="top",
        color=(0.9, 0.3, 0.3, 1),  # Red
    )
    error_label.bind(size=error_label.setter("text_size"))
    layout.add_widget(error_label)

    # Recovery buttons
    btn_layout = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height="48dp",
        spacing=10,
        padding=(20, 0),
    )

    # CPU fallback button (only for BACKEND_ERROR)
    if should_offer_cpu_fallback(result):
        cpu_btn = Button(
            text=i18n._("mykatrain:settings:try_cpu_fallback"),
            background_color=Theme.SECONDARY_COLOR,
        )
        cpu_btn.bind(
            on_release=lambda btn: _on_retry_cpu(ctx, katrain, layout, btn, state)
        )
        btn_layout.add_widget(cpu_btn)

    # Copy diagnostics button
    diag_btn = Button(
        text=i18n._("mykatrain:settings:copy_diagnostics"),
    )
    diag_btn.bind(on_release=lambda btn: _copy_diagnostics(result, ctx))
    btn_layout.add_widget(diag_btn)

    layout.add_widget(btn_layout)


def _render_timeout_ui(
    result: TestAnalysisResult,
    layout: BoxLayout,
    ctx: "FeatureContext",
    katrain: "any",
    state: AutoModeState,
) -> None:
    """Render timeout UI with restart option.

    TIMEOUT may be caused by:
    - Engine hung
    - Model loading slow
    - Resource exhaustion

    Recovery: Restart engine (NOT CPU fallback).

    Args:
        result: Test analysis result.
        layout: BoxLayout to add widgets to.
        ctx: Feature context.
        katrain: KaTrainGui instance.
        state: Per-popup state instance.
    """
    # Mark engine as unhealthy
    katrain.engine_unhealthy = True

    # Timeout message
    timeout_label = Label(
        text=f"⏰ {i18n._('mykatrain:settings:timeout_title')}",
        font_size="16sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
        valign="middle",
        color=(0.9, 0.6, 0.2, 1),  # Orange
    )
    timeout_label.bind(size=timeout_label.setter("text_size"))
    layout.add_widget(timeout_label)

    desc_label = Label(
        text=i18n._("mykatrain:settings:timeout_description"),
        font_size="14sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
    )
    desc_label.bind(size=desc_label.setter("text_size"))
    layout.add_widget(desc_label)

    # Recovery buttons
    btn_layout = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height="48dp",
        spacing=10,
        padding=(20, 0),
    )

    # Restart engine button
    restart_btn = Button(
        text=i18n._("mykatrain:settings:restart_engine"),
        background_color=Theme.PRIMARY_COLOR,
    )
    restart_btn.bind(
        on_release=lambda btn: _on_restart_engine(ctx, katrain, layout, btn, state)
    )
    btn_layout.add_widget(restart_btn)

    # Copy diagnostics button
    diag_btn = Button(
        text=i18n._("mykatrain:settings:copy_diagnostics"),
    )
    diag_btn.bind(on_release=lambda btn: _copy_diagnostics(result, ctx))
    btn_layout.add_widget(diag_btn)

    layout.add_widget(btn_layout)

    # Note about CPU fallback
    note_label = Label(
        text=i18n._("mykatrain:settings:timeout_note"),
        font_size="12sp",
        size_hint_y=None,
        height="30dp",
        halign="center",
        color=(0.6, 0.6, 0.6, 1),  # Gray
    )
    note_label.bind(size=note_label.setter("text_size"))
    layout.add_widget(note_label)


def _render_lightweight_missing_ui(
    layout: BoxLayout,
    ctx: "FeatureContext",
) -> None:
    """Render lightweight model missing UI.

    Args:
        layout: BoxLayout to add widgets to.
        ctx: Feature context.
    """
    # Error message
    error_label = Label(
        text=f"⚠ {i18n._('mykatrain:settings:error_lightweight_missing')}",
        font_size="16sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
        valign="middle",
        color=(0.9, 0.6, 0.2, 1),  # Orange
    )
    error_label.bind(size=error_label.setter("text_size"))
    layout.add_widget(error_label)

    # Get user models directory for guidance
    search_dirs = get_model_search_dirs()
    models_dir = search_dirs[0] if search_dirs else "~/.katrain/models/"

    instructions = i18n._("mykatrain:settings:lightweight_model_instructions").format(
        models_dir=models_dir
    )
    instr_label = Label(
        text=instructions,
        font_size="14sp",
        size_hint_y=None,
        height="80dp",
        halign="center",
        valign="top",
    )
    instr_label.bind(size=instr_label.setter("text_size"))
    layout.add_widget(instr_label)


# =============================================================================
# Recovery Actions
# =============================================================================


def _on_retry_cpu(
    ctx: "FeatureContext",
    katrain: "any",
    result_area: BoxLayout,
    btn: Button,
    state: AutoModeState,
) -> None:
    """Handle CPU fallback retry.

    Args:
        ctx: Feature context.
        katrain: KaTrainGui instance.
        result_area: BoxLayout for results.
        btn: The clicked button.
        state: Per-popup state instance.
    """
    if not state.try_start_test():
        return  # Already running

    btn.disabled = True
    Clock.schedule_once(
        lambda dt: _show_status(result_area, i18n._("mykatrain:settings:trying_cpu_fallback")),
        0,
    )

    def run_fallback():
        try:
            success, result = katrain.restart_engine_with_fallback("cpu")
        finally:
            state.finish_test()

        Clock.schedule_once(
            lambda dt: _on_fallback_complete(success, result, result_area, btn, ctx, katrain),
            0,
        )

    threading.Thread(target=run_fallback, daemon=True).start()


def _on_fallback_complete(
    success: bool,
    result: TestAnalysisResult,
    result_area: BoxLayout,
    btn: Button,
    ctx: "FeatureContext",
    katrain: "any",
) -> None:
    """Handle CPU fallback completion.

    Args:
        success: Whether fallback succeeded.
        result: Test analysis result.
        result_area: BoxLayout for results.
        btn: Button to re-enable.
        ctx: Feature context.
        katrain: KaTrainGui instance.
    """
    btn.disabled = False
    result_area.clear_widgets()

    if success:
        # Show success with CPU mode note
        backend = katrain.engine.get_backend_type() if katrain.engine else "CPU"
        success_text = i18n._("mykatrain:settings:test_success").format(engine=backend)

        success_label = Label(
            text=f"✓ {success_text}",
            font_size="16sp",
            size_hint_y=None,
            height="60dp",
            halign="center",
            valign="middle",
            color=(0.2, 0.8, 0.2, 1),
        )
        success_label.bind(size=success_label.setter("text_size"))
        result_area.add_widget(success_label)

        # Save success result
        katrain.save_auto_setup_result(True)
    else:
        # CPU fallback also failed
        error_label = Label(
            text=f"✗ {i18n._('mykatrain:settings:cpu_fallback_also_failed')}",
            font_size="14sp",
            size_hint_y=None,
            height="60dp",
            halign="center",
            color=(0.9, 0.3, 0.3, 1),
        )
        error_label.bind(size=error_label.setter("text_size"))
        result_area.add_widget(error_label)

        if result.error_message:
            detail_label = Label(
                text=result.error_message[:200],
                font_size="12sp",
                size_hint_y=None,
                height="40dp",
                halign="center",
            )
            detail_label.bind(size=detail_label.setter("text_size"))
            result_area.add_widget(detail_label)


def _on_restart_engine(
    ctx: "FeatureContext",
    katrain: "any",
    result_area: BoxLayout,
    btn: Button,
    state: AutoModeState,
) -> None:
    """Handle engine restart for TIMEOUT recovery.

    Args:
        ctx: Feature context.
        katrain: KaTrainGui instance.
        result_area: BoxLayout for results.
        btn: The clicked button.
        state: Per-popup state instance.
    """
    if not state.try_start_test():
        return  # Already running

    btn.disabled = True
    Clock.schedule_once(
        lambda dt: _show_status(result_area, i18n._("mykatrain:settings:restarting_engine")),
        0,
    )

    def run_restart():
        try:
            success = katrain.restart_engine()
        finally:
            state.finish_test()

        Clock.schedule_once(
            lambda dt: _on_restart_complete(success, result_area, btn, ctx, katrain),
            0,
        )

    threading.Thread(target=run_restart, daemon=True).start()


def _on_restart_complete(
    success: bool,
    result_area: BoxLayout,
    btn: Button,
    ctx: "FeatureContext",
    katrain: "any",
) -> None:
    """Handle engine restart completion.

    Args:
        success: Whether restart succeeded.
        result_area: BoxLayout for results.
        btn: Button to re-enable.
        ctx: Feature context.
        katrain: KaTrainGui instance.
    """
    btn.disabled = False
    result_area.clear_widgets()

    if success:
        status_label = Label(
            text=f"✓ {i18n._('mykatrain:settings:engine_restarted')}",
            font_size="16sp",
            size_hint_y=None,
            height="40dp",
            halign="center",
            color=(0.2, 0.8, 0.2, 1),
        )
        status_label.bind(size=status_label.setter("text_size"))
        result_area.add_widget(status_label)

        hint_label = Label(
            text=i18n._("mykatrain:settings:try_test_again"),
            font_size="14sp",
            size_hint_y=None,
            height="30dp",
            halign="center",
        )
        hint_label.bind(size=hint_label.setter("text_size"))
        result_area.add_widget(hint_label)
    else:
        error_label = Label(
            text=f"✗ {i18n._('mykatrain:settings:engine_restart_failed')}",
            font_size="14sp",
            size_hint_y=None,
            height="40dp",
            halign="center",
            color=(0.9, 0.3, 0.3, 1),
        )
        error_label.bind(size=error_label.setter("text_size"))
        result_area.add_widget(error_label)


# =============================================================================
# Utility Functions
# =============================================================================


def _show_status(layout: BoxLayout, message: str) -> None:
    """Show a status message.

    Args:
        layout: BoxLayout to update.
        message: Status message.
    """
    layout.clear_widgets()
    label = Label(
        text=message,
        font_size="14sp",
        size_hint_y=None,
        height="40dp",
        halign="center",
    )
    label.bind(size=label.setter("text_size"))
    layout.add_widget(label)


def _copy_diagnostics(result: TestAnalysisResult, ctx: "FeatureContext") -> None:
    """Copy diagnostic information to clipboard.

    Args:
        result: Test analysis result.
        ctx: Feature context.
    """
    from kivy.core.clipboard import Clipboard

    diag_lines = [
        "=== KaTrain Auto Mode Diagnostics ===",
        f"Success: {result.success}",
        f"Error Category: {result.error_category.value if result.error_category else 'None'}",
        f"Error Message: {result.error_message or 'None'}",
    ]

    # Add engine info if available (Phase 100: typed config)
    engine_config = ctx.get_engine_config()
    diag_lines.extend([
        "",
        "=== Engine Config ===",
        f"KataGo: {engine_config.katago or ''}",
        f"Model: {engine_config.model or ''}",
    ])

    diag_text = "\n".join(diag_lines)
    Clipboard.copy(diag_text)

    ctx.log(f"Diagnostics copied to clipboard", OUTPUT_DEBUG)
