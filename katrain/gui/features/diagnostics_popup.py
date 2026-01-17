"""Diagnostics popup for viewing system info and generating bug reports.

Phase 29: Diagnostics + Bug Report Bundle.
"""

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from katrain.common.file_opener import open_file_in_folder
from katrain.common.sanitize import get_sanitization_context
from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.diagnostics import (
    DiagnosticsBundle,
    collect_app_info,
    collect_katago_info,
    collect_settings_snapshot,
    collect_system_info,
    create_diagnostics_zip,
    generate_diagnostics_filename,
)
from katrain.core.lang import i18n
from katrain.core.reports.package_export import resolve_output_directory
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def show_diagnostics_popup(ctx: "FeatureContext") -> None:
    """Show diagnostics popup with system info and bug report generation.

    Args:
        ctx: FeatureContext providing config, engine, log access.
    """
    Clock.schedule_once(lambda dt: _show_diagnostics_popup_impl(ctx), 0)


def _show_diagnostics_popup_impl(ctx: "FeatureContext") -> None:
    """Implementation of diagnostics popup display."""
    # Collect diagnostic information
    bundle = _collect_diagnostics(ctx)

    # Build popup content
    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

    # Info display area (scrollable)
    info_scroll = ScrollView(size_hint=(1, 1))
    info_content = _build_info_display(bundle)
    info_scroll.add_widget(info_content)
    content.add_widget(info_scroll)

    # Button area
    button_box = BoxLayout(
        orientation="horizontal",
        size_hint=(1, None),
        height=dp(50),
        spacing=dp(10),
    )

    generate_btn = Button(
        text=i18n._("Generate Bug Report"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(0.5, 1),
    )
    close_btn = Button(
        text=i18n._("Close"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(0.5, 1),
    )

    button_box.add_widget(generate_btn)
    button_box.add_widget(close_btn)
    content.add_widget(button_box)

    # Create popup
    popup = Popup(
        title=i18n._("Diagnostics"),
        content=content,
        size_hint=(0.8, 0.8),
    )

    # Bind buttons
    close_btn.bind(on_release=popup.dismiss)
    generate_btn.bind(
        on_release=lambda btn: _on_generate_zip(ctx, bundle, generate_btn, popup)
    )

    popup.open()


def _collect_diagnostics(ctx: "FeatureContext") -> DiagnosticsBundle:
    """Collect all diagnostic information.

    Args:
        ctx: FeatureContext for accessing app state.

    Returns:
        DiagnosticsBundle with all collected information.
    """
    # System info
    system_info = collect_system_info()

    # KataGo info - extract from engine if available
    engine = getattr(ctx, "engine", None)
    if engine is not None:
        katago_info = collect_katago_info(
            exe_path=getattr(engine, "katago", ""),
            model_path=getattr(engine, "model", ""),
            config_path=getattr(engine, "config", ""),
            is_running=getattr(engine, "katago_process", None) is not None,
            version=None,  # Version retrieval not implemented yet
        )
    else:
        katago_info = collect_katago_info(
            exe_path="",
            model_path="",
            config_path="",
            is_running=False,
            version=None,
        )

    # App info
    from katrain.core.constants import DATA_FOLDER

    # Note: ctx IS the KaTrainGui instance (FeatureContext protocol)
    app_info = collect_app_info(
        version=getattr(ctx, "version", "unknown"),
        config_path=getattr(ctx, "config_file", ""),
        data_folder=DATA_FOLDER,
    )

    # Settings snapshot
    config_data = {}
    if hasattr(ctx, "_config"):
        config_data = dict(ctx._config)
    settings = collect_settings_snapshot(config_data)

    # Logs
    logs = []
    if hasattr(ctx, "get_recent_logs"):
        logs = ctx.get_recent_logs()

    return DiagnosticsBundle(
        system_info=system_info,
        katago_info=katago_info,
        app_info=app_info,
        settings=settings,
        logs=logs,
    )


def _build_info_display(bundle: DiagnosticsBundle) -> BoxLayout:
    """Build the info display widget.

    Args:
        bundle: DiagnosticsBundle with collected information.

    Returns:
        BoxLayout containing formatted info display.
    """
    layout = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        spacing=dp(5),
        padding=dp(5),
    )
    layout.bind(minimum_height=layout.setter("height"))

    def add_section(title: str, lines: list[str]) -> None:
        # Section header
        header = Label(
            text=f"[b]{title}[/b]",
            markup=True,
            font_name=Theme.DEFAULT_FONT,
            size_hint_y=None,
            height=dp(30),
            halign="left",
            valign="middle",
        )
        header.bind(size=header.setter("text_size"))
        layout.add_widget(header)

        # Section content
        for line in lines:
            item = Label(
                text=f"  {line}",
                font_name=Theme.DEFAULT_FONT,
                size_hint_y=None,
                height=dp(24),
                halign="left",
                valign="middle",
            )
            item.bind(size=item.setter("text_size"))
            layout.add_widget(item)

    # System section
    sys_info = bundle.system_info
    add_section(
        i18n._("System"),
        [
            f"OS: {sys_info.os_name} {sys_info.os_release}",
            f"Python: {sys_info.python_version} ({sys_info.python_bits})",
            f"Machine: {sys_info.machine}",
        ],
    )

    # KataGo section
    kata_info = bundle.katago_info
    status = i18n._("Running") if kata_info.is_running else i18n._("Stopped")
    add_section(
        i18n._("KataGo"),
        [
            f"Status: {status}",
            f"Exe: {kata_info.exe_path or i18n._('Not configured')}",
            f"Model: {kata_info.model_path or i18n._('Not configured')}",
        ],
    )

    # Application section
    app_info = bundle.app_info
    add_section(
        i18n._("Application"),
        [
            f"Version: {app_info.version}",
            f"Config: {app_info.config_path}",
        ],
    )

    return layout


def _on_generate_zip(
    ctx: "FeatureContext",
    bundle: DiagnosticsBundle,
    generate_btn: Button,
    parent_popup: Popup,
) -> None:
    """Handle ZIP generation button click.

    Runs ZIP generation in background thread to avoid UI freeze.
    """
    generate_btn.disabled = True
    generate_btn.text = i18n._("Generating...")

    def generate_thread() -> None:
        # Get output directory from settings
        mykatrain_settings = ctx.config("mykatrain_settings") or {}
        config_dir = mykatrain_settings.get("karte_output_directory", "")
        output_dir = resolve_output_directory(config_dir)

        # Generate filename and path
        filename = generate_diagnostics_filename()
        output_path = output_dir / filename

        # Get sanitization context
        sanitization_ctx = get_sanitization_context(app_dir=str(Path.cwd()))

        # Create ZIP
        result = create_diagnostics_zip(bundle, output_path, sanitization_ctx)

        # Update UI on main thread
        Clock.schedule_once(
            lambda dt: _on_generate_complete(ctx, result, generate_btn, parent_popup), 0
        )

    threading.Thread(target=generate_thread, daemon=True).start()


def _on_generate_complete(
    ctx: "FeatureContext",
    result,
    generate_btn: Button,
    parent_popup: Popup,
) -> None:
    """Handle ZIP generation completion on main thread."""
    generate_btn.disabled = False
    generate_btn.text = i18n._("Generate Bug Report")

    if result.success:
        ctx.log(
            i18n._("Bug report generated: %s") % str(result.output_path),
            OUTPUT_INFO,
        )
        parent_popup.dismiss()
        _show_success_popup(result.output_path)
    else:
        ctx.log(
            f"Failed to generate bug report: {result.error_message}",
            OUTPUT_ERROR,
        )
        _show_error_popup(result.error_message)


def _show_success_popup(output_path: Path) -> None:
    """Show success popup with Open Folder button."""
    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

    message = Label(
        text=i18n._("Bug report saved to:\n%s") % str(output_path),
        font_name=Theme.DEFAULT_FONT,
        halign="center",
        valign="middle",
        size_hint=(1, 0.6),
    )
    message.bind(size=message.setter("text_size"))
    content.add_widget(message)

    button_box = BoxLayout(
        orientation="horizontal",
        size_hint=(1, 0.4),
        spacing=dp(10),
    )

    open_folder_btn = Button(
        text=i18n._("Open Folder"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(0.5, 1),
    )
    close_btn = Button(
        text=i18n._("Close"),
        font_name=Theme.DEFAULT_FONT,
        size_hint=(0.5, 1),
    )

    button_box.add_widget(open_folder_btn)
    button_box.add_widget(close_btn)
    content.add_widget(button_box)

    popup = Popup(
        title=i18n._("Bug Report Generated"),
        content=content,
        size_hint=(0.6, 0.4),
    )

    close_btn.bind(on_release=popup.dismiss)
    open_folder_btn.bind(
        on_release=lambda btn: (open_file_in_folder(output_path), popup.dismiss())
    )

    popup.open()


def _show_error_popup(error_message: str) -> None:
    """Show error popup."""
    content = Label(
        text=i18n._("Failed to generate bug report:\n%s") % error_message,
        font_name=Theme.DEFAULT_FONT,
        halign="center",
        valign="middle",
    )

    popup = Popup(
        title=i18n._("Error"),
        content=content,
        size_hint=(0.6, 0.3),
    )

    popup.open()
