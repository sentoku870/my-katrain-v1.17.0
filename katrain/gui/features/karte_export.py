# katrain/gui/features/karte_export.py
#
# カルテエクスポート機能モジュール
#
# __main__.py から抽出したカルテ関連の関数を配置します。
# - Pure関数: determine_user_color
# - UI関数: do_export_karte_ui (FeatureContext経由)
#
# Phase 234: Kivy import consolidation via ``_ensure_kivy_imports()``.
# 以前は ``do_export_karte`` / ``do_export_karte_ui`` 関数の先頭で
# 個別に ``from kivy.X import Y`` を書いていたが、Clock 追加忘れの
# NameError 修正（Phase 225.2）等、再発リスクが高かった。
# 1 つのヘルパーに集約し、新しい Kivy シンボルを追加するときは
# ヘルパー内のみを更新すればよい。

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from katrain.core import analysis
from katrain.core.constants.output import OUTPUT_ERROR, STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from kivy.clock import Clock  # noqa: F401
    from kivy.core.clipboard import Clipboard  # noqa: F401
    from kivy.metrics import dp  # noqa: F401
    from kivy.uix.boxlayout import BoxLayout  # noqa: F401
    from kivy.uix.button import Button  # noqa: F401
    from kivy.uix.label import Label  # noqa: F401
    from kivy.uix.popup import Popup  # noqa: F401

    from katrain.core.game import Game
    from katrain.gui.features.context import FeatureContext


def determine_user_color(game: Game, username: str) -> str | None:
    """Determine user's color based on player names in SGF.

    Args:
        game: Game instance containing SGF root properties
        username: Username to match against player names

    Returns:
        "B" for black, "W" for white, None if no match or ambiguous

    Example:
        >>> color = determine_user_color(game, "sentoku")
        >>> if color == "B":
        ...     print("User played as Black")
    """
    if not username or not game:
        return None

    def normalize_name(name: str | None) -> str:
        """Normalize player name for matching.

        Removes non-alphanumeric characters and converts to lowercase.
        """
        if not name:
            return ""
        return re.sub(r"[^0-9a-z]+", "", str(name).casefold())

    pb = game.root.get_property("PB", None)
    pw = game.root.get_property("PW", None)

    user_norm = normalize_name(username)
    pb_norm = normalize_name(pb)
    pw_norm = normalize_name(pw)

    match_black = pb_norm and user_norm in pb_norm
    match_white = pw_norm and user_norm in pw_norm

    if match_black and not match_white:
        return "B"
    elif match_white and not match_black:
        return "W"
    else:
        # Ambiguous or no match
        return None


# ---------------------------------------------------------------------------
# Phase 234: Kivy import consolidation
# ---------------------------------------------------------------------------
# Previously, ``do_export_karte`` and ``do_export_karte_ui`` each declared
# their own per-symbol ``from kivy.X import Y`` lines. Phase 173 added
# the lazy import to avoid pulling kivy at module-load time, and Phase
# 225.2 added a missing ``Clock`` import to fix a NameError. Adding any
# new Kivy symbol in the future required hunting through both functions
# to add the corresponding import line.
#
# The ``_ensure_kivy_imports`` helper centralises the lazy import: a
# single call resolves all known Kivy symbols and binds them to this
# module's ``globals()`` so closures (``copy_path`` etc.) can resolve
# them by name. The helper is idempotent and is the only place that
# needs updating when a new Kivy symbol is introduced.

_KIVY_IMPORTS_DONE = False


def _ensure_kivy_imports() -> None:
    """Lazy-load Kivy symbols and bind them to module globals (Phase 234).

    Called from every entry point that touches the UI (``do_export_karte``
    and ``do_export_karte_ui``). After the first call the module
    globals carry the following names, all of which the inner closures
    resolve against ``globals()``:

    - ``Clock``        (kivy.clock)
    - ``Clipboard``    (kivy.core.clipboard)
    - ``dp``           (kivy.metrics)
    - ``BoxLayout``    (kivy.uix.boxlayout)
    - ``Button``       (kivy.uix.button)
    - ``Label``        (kivy.uix.label)
    - ``Popup``        (kivy.uix.popup)

    Idempotent: subsequent calls are no-ops.
    """
    global _KIVY_IMPORTS_DONE
    if _KIVY_IMPORTS_DONE:
        return
    from kivy.clock import Clock
    from kivy.core.clipboard import Clipboard
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup

    globals().update(
        {
            "Clock": Clock,
            "Clipboard": Clipboard,
            "dp": dp,
            "BoxLayout": BoxLayout,
            "Button": Button,
            "Label": Label,
            "Popup": Popup,
        }
    )
    _KIVY_IMPORTS_DONE = True


def do_export_karte(ctx: FeatureContext, open_settings_callback: Any) -> None:
    """Schedule karte export on the main Kivy thread.

    Args:
        ctx: FeatureContext providing game, config, controls, log
        open_settings_callback: Callback to open settings dialog if needed
    """
    # export_karte is executed from _message_loop_thread (NOT the main Kivy thread).
    # Any Kivy UI creation must happen on the main thread.
    # Phase 173: lazy-import kivy here so importing karte_export does
    # not pull in kivy at module load time (the kivy __init__ mkdir's
    # ~/.kivy, which causes FileExistsError on a reused GHA runner).
    # Phase 234: consolidate the import via _ensure_kivy_imports().
    _ensure_kivy_imports()
    Clock.schedule_once(lambda dt: do_export_karte_ui(ctx, open_settings_callback), 0)


def do_export_karte_ui(ctx: FeatureContext, open_settings_callback: Any) -> None:
    """Export karte using myKatrain settings.

    Args:
        ctx: FeatureContext providing game, config, controls, log
        open_settings_callback: Callback to open settings dialog if needed
    """
    # Phase 234: import the consolidated kivy symbols via the helper.
    # All Kivy names used below (``Clock``, ``Clipboard``, ``dp``,
    # ``BoxLayout``, ``Button``, ``Label``, ``Popup``) are bound to
    # this module's globals by ``_ensure_kivy_imports()`` and resolved
    # by closures via globals() lookup.
    _ensure_kivy_imports()

    if not ctx.game:
        return

    # Load settings
    settings = ctx.config("mykatrain_settings") or {}
    output_dir = settings.get("karte_output_directory", "")
    karte_format = settings.get("karte_format", "both")
    default_user = settings.get("default_user_name", "")

    # Validate output directory
    if not output_dir or not os.path.isdir(output_dir):
        Popup(
            title=i18n._("dialog:title:error"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=i18n._("mykatrain:error:output_dir_not_configured"),
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.5, 0.3),
        ).open()
        # Open settings dialog
        open_settings_callback()
        return

    # Generate filename base
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    root_name = ctx.game.root.get_property("GN", None)
    base_name = (
        os.path.splitext(os.path.basename(ctx.game.sgf_filename or ""))[0]
        or (root_name if root_name not in [None, ""] else None)
        or ctx.game.game_id
    )
    base_name = base_name[:50]  # Truncate to avoid overly long filenames
    # Sanitize filename: replace problematic characters
    base_name = re.sub(r'[<>:"/\\|?*]', "_", base_name)

    # Check if analysis data exists
    snapshot = ctx.game.build_eval_snapshot()
    if not snapshot.moves:
        Popup(
            title=i18n._("dialog:title:error"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=i18n._("mykatrain:error:no_analysis_data"),
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.5, 0.3),
        ).open()
        return

    # Determine player filter(s) and filename(s)
    exports: list[tuple[str | None, str]] = []

    if karte_format == "both":
        # Both players in one file (player_filter=None)
        exports = [(None, f"karte_{base_name}_{timestamp}.json")]
    elif karte_format == "black_only":
        exports = [("B", f"karte_{base_name}_black_{timestamp}.json")]
    elif karte_format == "white_only":
        exports = [("W", f"karte_{base_name}_white_{timestamp}.json")]
    elif karte_format == "default_user_only":
        # Determine user's color
        player_color = determine_user_color(ctx.game, default_user)
        if player_color:
            color_label = "black" if player_color == "B" else "white"
            exports = [(player_color, f"karte_{base_name}_{color_label}_{timestamp}.json")]
        else:
            # Fallback to both in one file
            Popup(
                title=i18n._("Warning"),
                title_font=Theme.DEFAULT_FONT,
                content=Label(
                    text=i18n._("Could not determine color for '{default_user}'.\nExporting both players.").format(
                        default_user=default_user
                    ),
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            exports = [(None, f"karte_{base_name}_{timestamp}.json")]

    # Generate and save karte(s)
    # Phase 229: derive from override + player_rank via resolve_skill_preset.
    skill_preset = analysis.resolve_skill_preset(
        ctx.config("general/skill_preset"),
        ctx.config("general/player_rank"),
    )
    # Phase 248-B1: pull the user-configured important-moves level so
    # ``pick_important_moves`` / ``select_critical_moves`` use the
    # same threshold/max_moves the user picked in the analysis tab.
    # Defaults to "normal" so empty/legacy configs keep Phase 50 behaviour.
    important_moves_level = (settings.get("important_moves_level") or "normal").strip()
    if important_moves_level not in {"easy", "normal", "strict"}:
        important_moves_level = "normal"
    # Phase 248-B2: pull the critical_3 selection count. Defaults to 3
    # so empty/legacy configs keep the Phase 50 baseline.
    try:
        critical_3_max_moves = int(settings.get("critical_3_max_moves") or 3)
    except (TypeError, ValueError):
        critical_3_max_moves = 3
    if critical_3_max_moves < 1 or critical_3_max_moves > 10:
        critical_3_max_moves = 3
    # Phase 270: the Curator profile loader (and the weak-tag boost
    # that consumed it) was removed. ``user_weak_tags`` is therefore
    # always empty and the call sites downstream carry ``None``.
    saved_files = []
    for player_filter, filename in exports:
        full_path = os.path.join(output_dir, filename)
        try:
            text = ctx.game.build_karte_json_string(
                player_filter=player_filter,
                skill_preset=skill_preset,
                level=important_moves_level,
                max_critical_3_moves=critical_3_max_moves,
            )
            os.makedirs(output_dir, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(text)
            saved_files.append(full_path)
        except Exception as exc:
            ctx.log(f"Failed to save karte: {exc}", OUTPUT_ERROR)
            # Phase 235: surface a sanitised version in the Popup so the
            # error message cannot leak file paths / temp-dir names / etc.
            # The full original is preserved in the log line above.
            from katrain.core.reports.karte.models import sanitize_error_message

            safe_error = sanitize_error_message(str(exc))
            Popup(
                title=i18n._("dialog:title:error"),
                title_font=Theme.DEFAULT_FONT,
                content=Label(
                    text=i18n._("Failed to save karte:\n{error}").format(error=safe_error),
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            return

    # Show confirmation
    files_text = "\n".join(saved_files)
    ctx.controls.set_status(i18n._("mykatrain:export-karte:success-title"), STATUS_INFO, check_level=False)

    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
    msg_label = Label(
        text=i18n._("mykatrain:export-karte:success-msg").format(files=files_text),
        halign="center",
        valign="middle",
        font_name=Theme.DEFAULT_FONT,
    )
    content.add_widget(msg_label)

    btn_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
    copy_btn = Button(text=i18n._("mykatrain:clipboard-copy"), font_name=Theme.DEFAULT_FONT)
    close_btn = Button(text=i18n._("button:ok"), font_name=Theme.DEFAULT_FONT)

    def copy_path(instance: Any) -> None:
        Clipboard.copy(files_text)
        instance.text = i18n._("mykatrain:clipboard-copied")
        # Reset text after 2 seconds
        Clock.schedule_once(lambda dt: setattr(instance, "text", i18n._("mykatrain:clipboard-copy")), 2)

    copy_btn.bind(on_release=copy_path)

    btn_box.add_widget(copy_btn)
    btn_box.add_widget(close_btn)
    content.add_widget(btn_box)

    popup = Popup(
        title=i18n._("mykatrain:export-karte:success-title"),
        title_font=Theme.DEFAULT_FONT,
        content=content,
        size_hint=(0.7, 0.5),
    )
    close_btn.bind(on_release=popup.dismiss)
    popup.open()
