# katrain/gui/features/package_export_ui.py
from __future__ import annotations

"""LLM Package Export - UI実装

責務（v5）:
- ゲーム状態の取得
- カルテ生成（正しいAPIを使用）
- 匿名化処理（文字列ベース）
- Core層へ最終文字列を渡す
"""

import logging
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from katrain.core.constants import OUTPUT_ERROR, OUTPUT_INFO
from katrain.core.reports.karte.models import KarteGenerationError, MixedEngineSnapshotError
from katrain.core.lang import i18n
from katrain.core.reports.package_export import (
    PackageContent,
    anonymize_karte_content,
    anonymize_sgf_string,
    create_llm_package,
    generate_package_filename,
    get_player_names_from_tree,
    load_coach_md,
    resolve_output_directory,
)
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


def do_export_package(ctx: "FeatureContext", anonymize: bool = False) -> None:
    """Export Packageをメインスレッドでスケジュール

    Args:
        ctx: FeatureContext providing game, config, controls, log
        anonymize: プレイヤー名を匿名化するかどうか
    """
    Clock.schedule_once(lambda dt: _do_export_package_impl(ctx, anonymize), 0)


def _do_export_package_impl(ctx: "FeatureContext", anonymize: bool) -> None:
    """Export Package 実行（内部実装）

    処理順序（v5 - 責務分離）:
    1. プレイヤー名取得 — 最初に元の名前を取得
    2. カルテ生成 — 元の名前でカルテを生成（skill_preset引数を使用）
    3. SGF文字列取得 — 元のツリーからSGF文字列を生成
    4. 匿名化（必要な場合） — GUI層で文字列レベルで置換
    5. パッケージ生成 — Core層は純粋にZIP生成のみ
    """
    game = ctx.game
    if game is None:
        ctx.log(i18n._("No game loaded"), OUTPUT_ERROR)
        return

    # 設定取得
    mykatrain_settings = ctx.config("mykatrain_settings") or {}
    skill_preset = mykatrain_settings.get("skill_preset", "standard")

    # 出力ディレクトリ決定
    config_dir = mykatrain_settings.get("karte_output_directory", "")
    output_dir = resolve_output_directory(config_dir)

    # ファイル名生成
    filename = generate_package_filename()
    output_path = output_dir / filename

    # 1. プレイヤー名取得（最初に、匿名化前の名前を取得）
    pb, pw = get_player_names_from_tree(game.root)

    # 2. カルテ生成（元の名前でカルテを生成）
    # API: build_karte_report(skill_preset=str) - 検証済み
    try:
        karte_md = game.build_karte_report(skill_preset=skill_preset)
    except (KarteGenerationError, MixedEngineSnapshotError) as e:
        # Karte generation failure: data issues or mixed engine analysis
        logging.info(f"Karte generation failed: {e}")
        ctx.log(f"Failed to generate karte: {e}", OUTPUT_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error during karte generation
        logging.warning(f"Unexpected karte generation error: {e}", exc_info=True)
        ctx.log(f"Failed to generate karte: {e}", OUTPUT_ERROR)
        return

    # 3. SGF文字列取得（元のツリーは変更しない）
    try:
        sgf_content = game.root.sgf()
    except (ValueError, AttributeError) as e:
        # SGF serialization failure: invalid node data or missing attributes
        logging.info(f"SGF generation failed: {e}")
        ctx.log(f"Failed to get SGF: {e}", OUTPUT_ERROR)
        return
    except Exception as e:
        # Boundary fallback: unexpected error generating SGF
        logging.warning(f"Unexpected SGF generation error: {e}", exc_info=True)
        ctx.log(f"Failed to get SGF: {e}", OUTPUT_ERROR)
        return

    # 4. 匿名化（必要な場合、GUI層で文字列レベルで置換）
    if anonymize:
        karte_md = anonymize_karte_content(karte_md, pb, pw)
        sgf_content = anonymize_sgf_string(sgf_content, pb, pw)

    # coach.md 読み込み
    coach_md = load_coach_md()

    # ゲーム情報取得
    game_info = {
        "board_size": game.board_size,
        "handicap": game.root.handicap,
        "komi": game.komi,
        "result": game.root.get_property("RE", ""),
        "date": game.root.get_property("DT", ""),
    }

    # 5. パッケージ生成（Core層は純粋にZIP生成のみ）
    content = PackageContent(
        karte_md=karte_md,
        sgf_content=sgf_content,
        coach_md=coach_md,
        game_info=game_info,
        skill_preset=skill_preset,
        anonymized=anonymize,  # manifestフラグ用
    )

    result = create_llm_package(content, output_path)

    if result.success:
        ctx.log(
            i18n._("Package exported: %s") % str(result.output_path),
            OUTPUT_INFO,
        )
        # 成功ポップアップ表示
        Popup(
            title=i18n._("Package Exported"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=i18n._("Package saved to:\n%s") % str(result.output_path),
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.6, 0.3),
        ).open()
    else:
        ctx.log(
            f"Failed to export package: {result.error_message}",
            OUTPUT_ERROR,
        )
        # エラーポップアップ表示
        Popup(
            title=i18n._("Error"),
            title_font=Theme.DEFAULT_FONT,
            content=Label(
                text=i18n._("Failed to export package:\n%s") % result.error_message,
                halign="center",
                valign="middle",
                font_name=Theme.DEFAULT_FONT,
            ),
            size_hint=(0.6, 0.3),
        ).open()
