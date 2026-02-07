"""Recovery actions for error popups (Phase 90).

Uses FeatureContext protocol for testability.
Calls only PUBLIC APIs - no underscore/private function imports.
Python 3.9 compatible - uses Optional/Dict instead of PEP604.

Thread safety:
    - trigger_auto_dump() captures ALL data on main thread first
    - Background thread ONLY performs file I/O (create_diagnostics_zip)
    - NO ctx.log() calls in background thread (not thread-safe)
    - Success logging done via Kivy Clock.schedule_once on main thread
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard

from katrain.common.sanitize import get_sanitization_context, sanitize_text
from katrain.core.auto_setup import prepare_reset_to_auto
from katrain.core.constants import DATA_FOLDER, OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.diagnostics import (
    collect_diagnostics_bundle,  # PUBLIC API
    create_diagnostics_zip,
    format_llm_diagnostics_text,  # PUBLIC API
    generate_diagnostics_filename,
)
from katrain.core.error_recovery import (
    DiagnosticsTrigger,
    RecoveryEvent,
    should_auto_dump,
)
from katrain.core.utils import resolve_output_directory

if TYPE_CHECKING:
    from katrain.core.diagnostics import DiagnosticsBundle
    from katrain.gui.features.context import FeatureContext

LOG_COPY_LINES = 200  # Bounded tail


def _build_bundle(ctx: FeatureContext) -> DiagnosticsBundle:
    """Build DiagnosticsBundle from FeatureContext using PUBLIC API.

    Uses only public methods - no private attribute access.
    """
    engine = ctx.engine
    if engine is not None:
        engine_info = (
            getattr(engine, "katago", ""),
            getattr(engine, "model", ""),
            getattr(engine, "config", ""),
            getattr(engine, "katago_process", None) is not None,
            None,  # version
        )
    else:
        engine_info = None

    # Use public API instead of ctx._config
    config_data = ctx.get_config_snapshot()

    logs = ctx.get_recent_logs()

    return collect_diagnostics_bundle(
        engine_info=engine_info,
        app_version=ctx.version,
        config_path=ctx.config_file,
        data_folder=DATA_FOLDER,
        config_data=config_data,
        logs=logs,
    )


def copy_for_llm(ctx: FeatureContext, error_context: str = "") -> bool:
    """Copy LLM-ready diagnostics to clipboard.

    Thread-safe: Only accesses Clipboard (Kivy main thread safe).

    Returns:
        True if successful, False on error.
    """
    try:
        bundle = _build_bundle(ctx)
        san_ctx = get_sanitization_context()
        text = format_llm_diagnostics_text(bundle, san_ctx, error_context)
        Clipboard.copy(text)
        return True
    except Exception as e:
        ctx.log(f"Failed to copy diagnostics: {e}", OUTPUT_ERROR)
        return False


def copy_log_tail(ctx: FeatureContext) -> bool:
    """Copy sanitized log tail to clipboard.

    Thread-safe: Only accesses Clipboard (Kivy main thread safe).

    Returns:
        True if successful.
    """
    try:
        logs = ctx.get_recent_logs()[-LOG_COPY_LINES:]
        san_ctx = get_sanitization_context()
        sanitized = [sanitize_text(line, san_ctx) for line in logs]
        Clipboard.copy("\n".join(sanitized))
        return True
    except Exception as e:
        ctx.log(f"Failed to copy logs: {e}", OUTPUT_ERROR)
        return False


def reset_to_auto_mode(ctx: FeatureContext) -> bool:
    """Reset to auto mode and restart engine.

    Uses real KaTrainGui APIs via FeatureContext protocol.

    Returns:
        True if successful.
    """
    try:
        changes = prepare_reset_to_auto()
        ctx.set_config_section("auto_setup", changes["auto_setup"])
        ctx.save_config("auto_setup")
        return ctx.restart_engine()
    except Exception as e:
        ctx.log(f"Failed to reset to auto mode: {e}", OUTPUT_ERROR)
        return False


def save_diagnostics_zip(
    ctx: FeatureContext,
    error_context: str = "",
    include_llm_prompt: bool = True,
) -> Path | None:
    """Save diagnostics ZIP (reuses existing infrastructure).

    Args:
        ctx: FeatureContext for accessing app state.
        error_context: Error description to include.
        include_llm_prompt: If True, add llm_prompt.txt to ZIP.

    Returns:
        Output path if successful, None on failure.
    """
    try:
        bundle = _build_bundle(ctx)

        # Get output directory (cross-platform)
        mykatrain_settings = ctx.config("mykatrain_settings") or {}
        config_dir = mykatrain_settings.get("karte_output_directory", "")
        output_dir = resolve_output_directory(config_dir)

        filename = generate_diagnostics_filename()
        output_path = output_dir / filename

        san_ctx = get_sanitization_context()

        # Prepare extra files
        extra_files: dict[str, str] | None = None
        if include_llm_prompt:
            llm_text = format_llm_diagnostics_text(bundle, san_ctx, error_context)
            extra_files = {"llm_prompt.txt": llm_text}

        result = create_diagnostics_zip(bundle, output_path, san_ctx, extra_files=extra_files)

        if result.success:
            return result.output_path
        else:
            ctx.log(f"Failed to save diagnostics: {result.error_message}", OUTPUT_ERROR)
            return None
    except Exception as e:
        ctx.log(f"Failed to save diagnostics: {e}", OUTPUT_ERROR)
        return None


def trigger_auto_dump(
    ctx: FeatureContext,
    trigger: DiagnosticsTrigger,
    code: str,
    error_message: str,
) -> None:
    """Trigger auto-dump in background if not already dumped for this event.

    Thread safety:
        - should_auto_dump() is thread-safe (uses Lock)
        - Background thread only performs file I/O
        - NO ctx.log() calls in background (not thread-safe)
        - Success/failure logging done via Kivy Clock on main thread

    This is the ONLY entry point for auto-dump. Uses should_auto_dump() as
    the single gate to prevent double dumps.
    """
    event = RecoveryEvent.create(trigger, code, error_message)

    if not should_auto_dump(event):
        return  # Already dumped for this event

    # Capture data on main thread (thread-safe)
    try:
        bundle = _build_bundle(ctx)
        mykatrain_settings = ctx.config("mykatrain_settings") or {}
        config_dir = mykatrain_settings.get("karte_output_directory", "")
        output_dir = resolve_output_directory(config_dir)
        filename = generate_diagnostics_filename()
        output_path = output_dir / filename
        san_ctx = get_sanitization_context()
        llm_text = format_llm_diagnostics_text(bundle, san_ctx, error_message)
    except Exception:
        return  # Silently fail if data capture fails

    def dump_thread() -> None:
        """Background thread: file I/O only, no UI calls."""
        try:
            extra_files = {"llm_prompt.txt": llm_text}
            result = create_diagnostics_zip(bundle, output_path, san_ctx, extra_files=extra_files)

            # Schedule logging on main thread
            if result.success:
                Clock.schedule_once(
                    lambda dt: ctx.log(f"Auto-saved diagnostics: {result.output_path}", OUTPUT_INFO),
                    0,
                )
        except Exception:
            pass  # Silently ignore dump failures

    threading.Thread(target=dump_thread, daemon=True).start()
