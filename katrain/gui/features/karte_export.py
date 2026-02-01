# katrain/gui/features/karte_export.py
#
# カルテエクスポート機能モジュール
#
# __main__.py から抽出したカルテ関連の関数を配置します。
# - Pure関数: determine_user_color
# - UI関数: do_export_karte_ui (FeatureContext経由)

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from katrain.core import eval_metrics
from katrain.core.constants import OUTPUT_ERROR, STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.core.game import Game
    from katrain.gui.features.context import FeatureContext


def determine_user_color(game: "Game", username: str) -> Optional[str]:
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

    def normalize_name(name: Optional[str]) -> str:
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


def do_export_karte(ctx: "FeatureContext", open_settings_callback: Any) -> None:
    """Schedule karte export on the main Kivy thread.

    Args:
        ctx: FeatureContext providing game, config, controls, log
        open_settings_callback: Callback to open settings dialog if needed
    """
    # export_karte is executed from _message_loop_thread (NOT the main Kivy thread).
    # Any Kivy UI creation must happen on the main thread.
    Clock.schedule_once(lambda dt: do_export_karte_ui(ctx, open_settings_callback), 0)


def do_export_karte_ui(ctx: "FeatureContext", open_settings_callback: Any) -> None:
    """Export karte using myKatrain settings.

    Args:
        ctx: FeatureContext providing game, config, controls, log
        open_settings_callback: Callback to open settings dialog if needed
    """
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
            title=i18n._("Error"),
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
    base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)

    # Check if analysis data exists
    snapshot = ctx.game.build_eval_snapshot()
    if not snapshot.moves:
        Popup(
            title=i18n._("Error"),
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
    exports: List[Tuple[Optional[str], str]] = []

    if karte_format == "both":
        # Both players in one file (player_filter=None)
        exports = [(None, f"karte_{base_name}_{timestamp}.md")]
    elif karte_format == "black_only":
        exports = [("B", f"karte_{base_name}_black_{timestamp}.md")]
    elif karte_format == "white_only":
        exports = [("W", f"karte_{base_name}_white_{timestamp}.md")]
    elif karte_format == "default_user_only":
        # Determine user's color
        player_color = determine_user_color(ctx.game, default_user)
        if player_color:
            color_label = "black" if player_color == "B" else "white"
            exports = [(player_color, f"karte_{base_name}_{color_label}_{timestamp}.md")]
        else:
            # Fallback to both in one file
            Popup(
                title="Warning",
                content=Label(
                    text=i18n._(
                        f"Could not determine color for '{default_user}'.\nExporting both players."
                    ),
                    halign="center",
                    valign="middle",
                    font_name=Theme.DEFAULT_FONT,
                ),
                size_hint=(0.5, 0.3),
            ).open()
            exports = [(None, f"karte_{base_name}_{timestamp}.md")]

    # Generate and save karte(s)
    skill_preset = ctx.config("general/skill_preset") or eval_metrics.DEFAULT_SKILL_PRESET
    saved_files = []
    for player_filter, filename in exports:
        full_path = os.path.join(output_dir, filename)
        try:
            text = ctx.game.build_karte_report(player_filter=player_filter, skill_preset=skill_preset)
            os.makedirs(output_dir, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(text)
            saved_files.append(full_path)
        except Exception as exc:
            ctx.log(f"Failed to save karte: {exc}", OUTPUT_ERROR)
            Popup(
                title="Error",
                content=Label(text=f"Failed to save karte:\n{exc}", halign="center", valign="middle"),
                size_hint=(0.5, 0.3),
            ).open()
            return

    # Show confirmation
    files_text = "\n".join(saved_files)
    ctx.controls.set_status("Karte(s) exported", STATUS_INFO, check_level=False)
    Popup(
        title="Karte exported",
        content=Label(text=f"Saved to:\n{files_text}", halign="center", valign="middle"),
        size_hint=(0.6, 0.4),
    ).open()
