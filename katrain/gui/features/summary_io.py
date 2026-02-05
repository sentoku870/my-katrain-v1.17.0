# katrain/gui/features/summary_io.py
#
# サマリファイル保存機能モジュール
#
# __main__.py から抽出したサマリ保存関連の関数を配置します。
# - save_summaries_per_player: 複数プレイヤー用の保存処理
# - save_categorized_summaries_from_stats: カテゴリ別の保存処理
# - save_summary_file: 単一ファイル保存処理

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from kivy.core.clipboard import Clipboard
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from katrain.core.constants import OUTPUT_DEBUG, OUTPUT_ERROR, OUTPUT_INFO, STATUS_INFO
from katrain.core.lang import i18n
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def save_summaries_per_player(
    game_stats_list: list[dict[str, Any]],
    selected_players: list[str],
    progress_popup: "Popup",
    ctx: "FeatureContext",
    categorize_games_fn: Callable[[list[dict[str, Any]], str], dict[str, Any]],
    build_summary_fn: Callable[[list[dict[str, Any]], str], str],
) -> None:
    """各プレイヤーごとに別ファイルでサマリーを保存

    Args:
        game_stats_list: ゲーム統計辞書のリスト
        selected_players: 選択されたプレイヤー名のリスト
        progress_popup: 進行状況ポップアップ
        ctx: FeatureContext providing config, log, controls
        categorize_games_fn: ゲーム分類関数
        build_summary_fn: サマリ構築関数
    """
    progress_popup.dismiss()

    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")

    # mykatrain_settings の karte_output_directory を優先、なければ従来のパス
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    output_dir = mykatrain_settings.get("karte_output_directory", "")
    if not output_dir or not os.path.isdir(output_dir):
        output_dir = os.path.join(os.path.expanduser(ctx.config("general/sgf_save") or "."), "reports")
    os.makedirs(output_dir, exist_ok=True)

    for player_name in selected_players:
        try:
            # このプレイヤーが参加しているゲームのみフィルタ
            player_games = [
                stats for stats in game_stats_list
                if stats["player_black"] == player_name or stats["player_white"] == player_name
            ]

            if len(player_games) < 2:
                ctx.log(f"Skipping {player_name}: Not enough games ({len(player_games)})", OUTPUT_INFO)
                continue

            # ゲームを分類（互先/置碁）
            categorized_games = categorize_games_fn(player_games, player_name)

            # 各カテゴリごとにファイル出力
            category_labels = {
                "even": "互先",
                "handi_weak": "置碁下手",
                "handi_strong": "置碁上手",
            }

            for category, games in categorized_games.items():
                if len(games) < 2:
                    continue

                summary_text = build_summary_fn(games, player_name)

                # ファイル名にプレイヤー名を含める
                label = category_labels[category]
                # プレイヤー名のサニタイズ
                safe_player_name = re.sub(r'[<>:"/\\|?*]', '_', player_name)[:30]
                filename = f"summary_{safe_player_name}_{label}_{timestamp}.md"
                full_path = os.path.join(output_dir, filename)

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)

                saved_files.append(full_path)
                ctx.log(f"Summary saved: {full_path}", OUTPUT_INFO)

        except OSError as exc:
            # Expected: File I/O error
            ctx.log(f"Failed to save summary for {player_name}: {exc}", OUTPUT_ERROR)
        except Exception as exc:
            # Unexpected: Internal bug - traceback required
            import traceback
            ctx.log(f"Unexpected error saving summary for {player_name}: {exc}\n{traceback.format_exc()}", OUTPUT_ERROR)

    # 結果ポップアップ
    if saved_files:
        files_text = "\n".join([os.path.basename(f) for f in saved_files])
        Popup(
            title=i18n._("Summaries exported"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=f"Saved {len(saved_files)} summary file(s):\n\n{files_text}",
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.6, 0.5),
        ).open()
        ctx.controls.set_status(f"{len(saved_files)} summaries exported", STATUS_INFO, check_level=False)
    else:
        Popup(
            title=i18n._("No summaries generated"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text="No players had enough games (need 2+ per category).",
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.5, 0.3),
        ).open()


def save_categorized_summaries_from_stats(
    categorized_games: dict[str, list[dict[str, Any]]],
    player_name: str | None,
    progress_popup: "Popup",
    ctx: "FeatureContext",
    build_summary_fn: Callable[[list[dict[str, Any]], str | None], str],
) -> None:
    """カテゴリごとにsummary.mdを保存

    Args:
        categorized_games: カテゴリ別に分類されたゲームリスト
        player_name: フォーカスプレイヤー名（オプション）
        progress_popup: 進行状況ポップアップ
        ctx: FeatureContext providing config, log, controls
        build_summary_fn: サマリ構築関数
    """
    progress_popup.dismiss()

    category_labels = {
        "even": "互先",
        "handi_weak": "置碁下手",
        "handi_strong": "置碁上手",
    }

    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")

    # mykatrain_settings の karte_output_directory を優先、なければ従来のパス
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    output_dir = mykatrain_settings.get("karte_output_directory", "")
    if not output_dir or not os.path.isdir(output_dir):
        # フォールバック: general/sgf_save/reports/
        output_dir = os.path.join(os.path.expanduser(ctx.config("general/sgf_save") or "."), "reports")
    os.makedirs(output_dir, exist_ok=True)

    for category, games in categorized_games.items():
        if len(games) < 2:
            # 2局未満はスキップ
            continue

        try:
            # 統計dictから直接まとめレポート生成
            summary_text = build_summary_fn(games, player_name)

            # ファイル名
            label = category_labels[category]
            filename = f"summary_{label}_{timestamp}.md"
            full_path = os.path.join(output_dir, filename)

            # 保存
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(summary_text)

            saved_files.append(full_path)
            ctx.log(f"Summary saved: {full_path}", OUTPUT_INFO)

        except OSError as exc:
            # Expected: File I/O error
            ctx.log(f"Failed to save summary for {category}: {exc}", OUTPUT_ERROR)
        except Exception as exc:
            # Unexpected: Internal bug - traceback required
            import traceback
            ctx.log(f"Unexpected error saving summary for {category}: {exc}\n{traceback.format_exc()}", OUTPUT_ERROR)

    # 結果ポップアップ
    if saved_files:
        files_text = "\n".join([os.path.basename(f) for f in saved_files])
        Popup(
            title=i18n._("Summaries exported"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=f"Saved {len(saved_files)} summary file(s):\n\n{files_text}",
                halign="center",
                valign="middle"
            ),
            size_hint=(0.6, 0.5),
        ).open()
        ctx.controls.set_status(f"{len(saved_files)} summaries exported", STATUS_INFO, check_level=False)
    else:
        Popup(
            title=i18n._("No summaries generated"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text="No categories had enough games (need 2+).\nCheck that focus_player matches SGF player names.",
                halign="center",
                valign="middle"
            ),
            size_hint=(0.5, 0.3),
        ).open()


def save_summary_file(
    summary_text: str,
    player_name: str | None,
    progress_popup: "Popup",
    ctx: "FeatureContext",
) -> None:
    """まとめファイルを保存

    Args:
        summary_text: 保存するサマリテキスト
        player_name: プレイヤー名（ファイル名に使用）
        progress_popup: 進行状況ポップアップ
        ctx: FeatureContext providing config, log, controls
    """
    progress_popup.dismiss()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"summary_{player_name or 'all'}_{timestamp}.md"

    # reports/ ディレクトリに保存
    default_path = os.path.join(os.path.expanduser(ctx.config("general/sgf_save") or "."), "reports")
    os.makedirs(default_path, exist_ok=True)
    full_path = os.path.join(default_path, filename)

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        # クリップボードにコピー
        try:
            Clipboard.copy(summary_text)
        except RuntimeError as exc:
            # Expected: Kivy clipboard backend issue
            ctx.log(f"Clipboard copy failed: {exc}", OUTPUT_DEBUG)
        except Exception as exc:
            # Unexpected: Internal bug - traceback required
            import traceback
            ctx.log(f"Unexpected clipboard error: {exc}\n{traceback.format_exc()}", OUTPUT_DEBUG)

        ctx.controls.set_status(f"Summary exported to {full_path}", STATUS_INFO, check_level=False)
        Popup(
            title=i18n._("Summary exported"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(text=f"Saved to:\n{full_path}", halign="center", valign="middle"),
            size_hint=(0.5, 0.3),
        ).open()
    except OSError as exc:
        # Expected: File I/O error
        ctx.log(f"Failed to export Summary to {full_path}: {exc}", OUTPUT_ERROR)
        Popup(
            title=i18n._("Error"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(text=f"Failed to save:\n{exc}", halign="center", valign="middle"),
            size_hint=(0.5, 0.3),
        ).open()
    except Exception as exc:
        # Unexpected: Internal bug - traceback required
        import traceback
        ctx.log(f"Unexpected error exporting Summary to {full_path}: {exc}\n{traceback.format_exc()}", OUTPUT_ERROR)
        Popup(
            title=i18n._("Error"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(text=f"Unexpected error:\n{exc}", halign="center", valign="middle"),
            size_hint=(0.5, 0.3),
        ).open()
