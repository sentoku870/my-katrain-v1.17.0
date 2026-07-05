"""Settings popup import/export (Phase 173).

Extracted from ``katrain.gui.features.settings_popup`` so the orchestrator
file can stay focused on popup layout and tab wiring.

Public surface (kept intact for backward compatibility):

- ``_do_export_settings`` — opens a file dialog and serialises the current
  configuration to a JSON file via ``settings_export.export_settings``.
- ``_do_import_settings`` — reads a JSON file, validates its content, takes
  a backup of the live ``config.json`` and atomically swaps in the new
  contents; rolls back on failure.

Both functions still import ``tkinter`` lazily inside the function body so
importing this module does not open Tk windows during unit tests.
"""

from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from katrain.common.settings_export import (
    EXCLUDED_SECTIONS,
    atomic_save_config,
    create_backup_path,
    export_settings,
    parse_exported_settings,
)
from katrain.core.constants import STATUS_ERROR, STATUS_INFO
from katrain.core.lang import i18n

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext
    from katrain.gui.widgets.factory import Popup


def _do_export_settings(
    ctx: "FeatureContext",
    popup: "Popup",
) -> None:
    """設定をJSONファイルにエクスポート (Phase 27 / Phase 173 でファイル分割)

    Opens a file save dialog and exports current settings to a JSON file.
    Uses the export_settings function from settings_export module.

    Args:
        ctx: FeatureContext providing config, controls
        popup: 親ポップアップ（エクスポート後も開いたまま）
    """
    from tkinter import Tk, filedialog

    # Create hidden Tk root for file dialog
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        file_path = filedialog.asksaveasfilename(
            title=i18n._("mykatrain:settings:export"),
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="katrain_settings.json",
        )
    finally:
        root.destroy()

    if not file_path:
        return  # User cancelled

    try:
        # Get current config and app version
        config_dict = dict(ctx._config)  # type: ignore[attr-defined]
        app_version = ctx.config("general", {}).get("version", "unknown")

        # Export to JSON string
        json_str = export_settings(config_dict, app_version)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_str)

        ctx.controls.set_status(
            i18n._("mykatrain:settings:export_success").format(path=file_path),
            STATUS_INFO,
        )
    except OSError as e:
        # File write failure: permission denied, disk full, invalid path
        logging.warning(f"Settings export failed to {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Export failed: {e}", STATUS_ERROR)
    except Exception as e:
        # Boundary fallback: unexpected error during settings export
        logging.error(f"Unexpected error exporting settings to {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Export failed: {e}", STATUS_ERROR)


def _do_import_settings(
    ctx: "FeatureContext",
    popup: "Popup",
    on_import_complete: Callable[[], None],
) -> None:
    """設定をJSONファイルからインポート (Phase 27 / Phase 173 でファイル分割)

    Opens a file selection dialog and imports settings from a JSON file.
    Creates a backup before modifying config and uses atomic save.

    Args:
        ctx: FeatureContext providing config, config_file, controls, _config_store
        popup: 親ポップアップ（インポート後に閉じてリロード用）
        on_import_complete: インポート完了後に呼ばれるコールバック
    """
    from tkinter import Tk, filedialog

    # Create hidden Tk root for file dialog
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    try:
        file_path = filedialog.askopenfilename(
            title=i18n._("mykatrain:settings:import_title"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
    finally:
        root.destroy()

    if not file_path:
        return  # User cancelled

    try:
        # Read JSON file
        with open(file_path, encoding="utf-8") as f:
            json_str = f.read()

        # Parse and validate
        imported = parse_exported_settings(json_str)

    except ValueError as e:
        # JSON parse or validation error
        logging.warning(f"Settings import validation failed: {e}")
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return
    except (OSError, UnicodeDecodeError) as e:
        # File read failure: file not found, permission denied, encoding error
        logging.warning(f"Settings import read failed from {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error during settings import
        logging.error(f"Unexpected error importing settings from {file_path}: {e}", exc_info=True)
        ctx.controls.set_status(f"Import failed: {e}", STATUS_ERROR)
        return

    # Create backup
    backup_path = create_backup_path(ctx.config_file)
    try:
        shutil.copy2(ctx.config_file, backup_path)
    except OSError as e:
        # Backup failure: permission denied, disk full
        logging.warning(f"Settings import backup failed: {e}", exc_info=True)
        ctx.controls.set_status(f"Backup failed: {e}", STATUS_ERROR)
        return

    # Save original config for rollback
    # Note: Accessing private _config is intentional (Phase 111 scope-out)
    original_config = {
        k: dict(v) if isinstance(v, dict) else v
        for k, v in ctx._config.items()  # type: ignore[attr-defined]
    }

    try:
        # Update config in memory
        for section, values in imported.sections.items():
            if section in EXCLUDED_SECTIONS:
                continue
            if section not in ctx._config:  # type: ignore[attr-defined]
                ctx._config[section] = {}  # type: ignore[attr-defined]
            ctx._config[section].update(values)  # type: ignore[attr-defined]

        # Atomic save
        atomic_save_config(ctx._config, ctx.config_file)  # type: ignore[attr-defined]

        # Reload store (reload-then-sync pattern)
        ctx._config_store._load()  # type: ignore[attr-defined]
        ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]

    except (OSError, json.JSONDecodeError) as e:
        # Atomic save or reload failure
        logging.error(f"Settings import save failed: {e}", exc_info=True)
        # Rollback on failure
        ctx._config = original_config  # type: ignore[attr-defined]
        rollback_failed = False
        try:
            shutil.copy2(backup_path, ctx.config_file)
            ctx._config_store._load()  # type: ignore[attr-defined]
            ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]
        except Exception as rollback_err:
            # Boundary fallback: rollback itself failed.
            # At this point the config may be in an inconsistent state.
            # We log but cannot recover - user must restart or manually fix.
            logging.error(
                f"CRITICAL: Settings rollback failed after import error. "
                f"Config may be inconsistent. Error: {rollback_err}",
                exc_info=True,
            )
            rollback_failed = True
        if rollback_failed:
            ctx.controls.set_status(
                f"Import failed, restore may be incomplete. Restart recommended. Error: {e}",
                STATUS_ERROR,
            )
        else:
            ctx.controls.set_status(f"Import failed, restored: {e}", STATUS_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error during save
        logging.error(f"Unexpected error during settings save: {e}", exc_info=True)
        # Rollback on failure
        ctx._config = original_config  # type: ignore[attr-defined]
        rollback_failed = False
        try:
            shutil.copy2(backup_path, ctx.config_file)
            ctx._config_store._load()  # type: ignore[attr-defined]
            ctx._config = dict(ctx._config_store)  # type: ignore[attr-defined]
        except Exception as rollback_err:
            logging.error(
                f"CRITICAL: Settings rollback failed after import error. "
                f"Config may be inconsistent. Error: {rollback_err}",
                exc_info=True,
            )
            rollback_failed = True
        if rollback_failed:
            ctx.controls.set_status(
                f"Import failed, restore may be incomplete. Restart recommended. Error: {e}",
                STATUS_ERROR,
            )
        else:
            ctx.controls.set_status(f"Import failed, restored: {e}", STATUS_ERROR)
        return

    ctx.controls.set_status(
        i18n._("mykatrain:settings:import_success").format(backup=backup_path),
        STATUS_INFO,
    )

    # Reload settings popup
    popup.dismiss()
    on_import_complete()
