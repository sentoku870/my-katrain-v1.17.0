# katrain/gui/features/smart_kifu_profile.py
#
# Smart Kifu Learning - Player Profile UI (Phase 13.3)
#
# Player Profile の表示・更新を行うUIモジュール。

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from katrain.core.constants import STATUS_ERROR, STATUS_INFO
from katrain.core.lang import i18n
from katrain.core.smart_kifu import (
    BucketProfile,
    Confidence,
    Context,
    ContextProfile,
    GameEntry,
    PlayerProfile,
    TrainingSetManifest,
    ViewerPreset,
    compute_bucket_key,
    compute_confidence,
    estimate_viewer_level,
    list_training_sets,
    load_manifest,
    load_player_profile,
    map_viewer_level_to_preset,
    save_player_profile,
)
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# Constants
# =============================================================================

CONTEXT_LABELS = {
    Context.HUMAN: "対人戦",
    Context.VS_KATAGO: "vs KataGo",
    Context.GENERATED: "AI生成",
}

CONFIDENCE_LABELS = {
    Confidence.LOW: "低",
    Confidence.MEDIUM: "中",
    Confidence.HIGH: "高",
}

PRESET_LABELS = {
    ViewerPreset.LITE: "Lite",
    ViewerPreset.STANDARD: "Standard",
    ViewerPreset.DEEP: "Deep",
}


# =============================================================================
# Bucket Card Widget
# =============================================================================


def build_bucket_card(
    bucket_key: str,
    profile: BucketProfile | None,
) -> BoxLayout:
    """Bucket カードウィジェットを構築

    Args:
        bucket_key: Bucketキー（例: "19_even"）
        profile: BucketProfile（None の場合はデータなし表示）

    Returns:
        カードを含む BoxLayout
    """
    card = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        height=dp(120),
        padding=dp(8),
        spacing=dp(4),
    )
    # 背景色を設定するためのキャンバス命令
    from kivy.graphics import Color, Rectangle
    with card.canvas.before:
        Color(0.2, 0.2, 0.25, 1)  # 暗い背景
        rect = Rectangle(pos=card.pos, size=card.size)
    card.bind(pos=lambda inst, val: setattr(rect, 'pos', val))
    card.bind(size=lambda inst, val: setattr(rect, 'size', val))

    # タイトル行
    title_label = Label(
        text=bucket_key.replace("_", " ").upper(),
        size_hint_y=None,
        height=dp(25),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(14),
        bold=True,
        halign="left",
    )
    title_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    card.add_widget(title_label)

    if profile is None:
        # データなし
        no_data_label = Label(
            text="データなし",
            size_hint_y=1,
            color=(0.6, 0.6, 0.6, 1),
            font_name=Theme.DEFAULT_FONT,
        )
        card.add_widget(no_data_label)
        return card

    # Viewer Level / Preset 行
    level_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(25),
    )
    level_label = Label(
        text=f"Viewer: Lv{profile.viewer_level} ({PRESET_LABELS.get(profile.viewer_preset, 'N/A')})",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
    )
    level_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    level_row.add_widget(level_label)
    card.add_widget(level_row)

    # Confidence / Samples 行
    conf_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(25),
    )
    conf_text = CONFIDENCE_LABELS.get(profile.confidence, "N/A")
    samples_text = f"{profile.samples}局"
    conf_label = Label(
        text=f"信頼度: {conf_text} / {samples_text}",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
    )
    conf_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    conf_row.add_widget(conf_label)
    card.add_widget(conf_row)

    # Analyzed Ratio 行
    ratio_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(25),
    )
    if profile.analyzed_ratio is not None:
        ratio_text = f"{profile.analyzed_ratio:.0%}"
    else:
        ratio_text = "N/A"
    ratio_label = Label(
        text=f"解析率: {ratio_text}",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
    )
    ratio_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    ratio_row.add_widget(ratio_label)
    card.add_widget(ratio_row)

    return card


# =============================================================================
# Update Preview Dialog
# =============================================================================


def compute_profile_update_preview(
    games: list[GameEntry],
    engine_profile_id: str | None,
) -> dict[str, Any]:
    """プロファイル更新のプレビューを計算

    Args:
        games: 集計対象のゲームエントリリスト
        engine_profile_id: 集計に使用するエンジンプロファイルID（Noneの場合は最多を使用）

    Returns:
        プレビュー結果の辞書
    """
    if not games:
        return {
            "samples": 0,
            "analyzed_ratio": None,
            "confidence": Confidence.LOW,
            "viewer_level": 5,
            "viewer_preset": ViewerPreset.STANDARD,
            "engine_profile_id": None,
        }

    # engine_profile_id が指定されていない場合は最多のものを選択
    if engine_profile_id is None:
        ep_counts: dict[str | None, int] = {}
        for g in games:
            ep_id = g.engine_profile_id
            ep_counts[ep_id] = ep_counts.get(ep_id, 0) + 1
        engine_profile_id = max(ep_counts.keys(), key=lambda k: ep_counts.get(k, 0))

    # 同一 engine_profile_id のゲームのみ集計
    filtered_games = [g for g in games if g.engine_profile_id == engine_profile_id]

    if not filtered_games:
        return {
            "samples": 0,
            "analyzed_ratio": None,
            "confidence": Confidence.LOW,
            "viewer_level": 5,
            "viewer_preset": ViewerPreset.STANDARD,
            "engine_profile_id": engine_profile_id,
        }

    samples = len(filtered_games)

    # analyzed_ratio の平均を計算
    analyzed_ratios = [g.analyzed_ratio for g in filtered_games if g.analyzed_ratio is not None]
    if analyzed_ratios:
        avg_analyzed_ratio = sum(analyzed_ratios) / len(analyzed_ratios)
    else:
        avg_analyzed_ratio = None

    confidence = compute_confidence(samples, avg_analyzed_ratio)

    # viewer_level の推定（v0.2では簡易実装：サンプル数と解析率から推定）
    # 本来は avg_loss と blunder_rate が必要だが、v0.2では仮の値を使用
    # TODO: Phase 2以降で実際の avg_loss, blunder_rate を計算
    viewer_level = 5  # デフォルト
    if avg_analyzed_ratio is not None:
        # 解析率が高いほど詳細な解説が可能と仮定
        if avg_analyzed_ratio >= 0.8:
            viewer_level = 7
        elif avg_analyzed_ratio >= 0.5:
            viewer_level = 5
        else:
            viewer_level = 3

    viewer_preset = map_viewer_level_to_preset(viewer_level)

    return {
        "samples": samples,
        "analyzed_ratio": avg_analyzed_ratio,
        "confidence": confidence,
        "viewer_level": viewer_level,
        "viewer_preset": viewer_preset,
        "engine_profile_id": engine_profile_id,
        "total_games": len(games),
        "filtered_games": len(filtered_games),
    }


def show_update_preview_dialog(
    ctx: "FeatureContext",
    context: Context,
    bucket_key: str,
    preview: dict[str, Any],
    on_apply: Callable[[], None],
) -> None:
    """更新プレビューダイアログを表示

    Args:
        ctx: FeatureContext
        context: 対戦コンテキスト
        bucket_key: Bucketキー
        preview: プレビュー結果
        on_apply: 適用時のコールバック
    """
    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # ヘッダー
    header_label = Label(
        text=f"{CONTEXT_LABELS.get(context, 'N/A')} / {bucket_key}",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(16),
        bold=True,
    )
    content.add_widget(header_label)

    # プレビュー情報
    info_lines = [
        f"集計局数: {preview['samples']}局（全{preview.get('total_games', 0)}局中）",
        f"解析率: {preview['analyzed_ratio']:.0%}" if preview['analyzed_ratio'] is not None else "解析率: N/A",
        f"信頼度: {CONFIDENCE_LABELS.get(preview['confidence'], 'N/A')}",
        f"Viewer Level: Lv{preview['viewer_level']} ({PRESET_LABELS.get(preview['viewer_preset'], 'N/A')})",
    ]

    if preview.get('engine_profile_id'):
        info_lines.append(f"Engine Profile: {preview['engine_profile_id'][:20]}...")

    for line in info_lines:
        line_label = Label(
            text=line,
            size_hint_y=None,
            height=dp(25),
            color=Theme.TEXT_COLOR,
            font_name=Theme.DEFAULT_FONT,
            font_size=dp(13),
            halign="left",
        )
        line_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
        content.add_widget(line_label)

    # スペーサー
    content.add_widget(BoxLayout(size_hint_y=1))

    # ボタン行
    button_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(400), dp(350)],
        content=content,
        auto_dismiss=True,
    )
    popup.title = "プロファイル更新プレビュー"

    def on_apply_click(*_args: Any) -> None:
        popup.dismiss()
        on_apply()

    def on_cancel(*_args: Any) -> None:
        popup.dismiss()

    apply_btn = Button(
        text="適用",
        size_hint_x=0.5,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    apply_btn.bind(on_release=on_apply_click)

    cancel_btn = Button(
        text="キャンセル",
        size_hint_x=0.5,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    cancel_btn.bind(on_release=on_cancel)

    button_row.add_widget(apply_btn)
    button_row.add_widget(cancel_btn)
    content.add_widget(button_row)

    popup.open()


# =============================================================================
# Update Bucket Dialog
# =============================================================================


def show_update_bucket_dialog(
    ctx: "FeatureContext",
    context: Context,
    bucket_key: str,
    on_updated: Callable[[], None],
) -> None:
    """Bucket 更新ダイアログを表示

    Args:
        ctx: FeatureContext
        context: 対戦コンテキスト
        bucket_key: Bucketキー
        on_updated: 更新完了時のコールバック
    """
    content = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # ヘッダー
    header_label = Label(
        text=f"{CONTEXT_LABELS.get(context, 'N/A')} / {bucket_key} の更新",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(16),
    )
    content.add_widget(header_label)

    # N局入力行
    n_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(10),
    )
    n_label = Label(
        text="集計局数:",
        size_hint_x=0.3,
        halign="right",
        valign="middle",
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    n_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    n_input = TextInput(
        text="30",
        hint_text="直近N局",
        multiline=False,
        input_filter="int",
        size_hint_x=0.7,
        font_name=Theme.DEFAULT_FONT,
    )
    n_row.add_widget(n_label)
    n_row.add_widget(n_input)
    content.add_widget(n_row)

    # 情報表示用ラベル
    info_label = Label(
        text="",
        size_hint_y=None,
        height=dp(60),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
        valign="top",
    )
    info_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
    content.add_widget(info_label)

    # スペーサー
    content.add_widget(BoxLayout(size_hint_y=1))

    # ボタン行
    button_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(400), dp(300)],
        content=content,
        auto_dismiss=True,
    )
    popup.title = "Bucket 更新"

    def collect_games_for_bucket() -> list[GameEntry]:
        """指定されたContext/Bucketに該当するゲームを全Training Setから収集"""
        all_games: list[GameEntry] = []
        for set_id in list_training_sets():
            manifest = load_manifest(set_id)
            if manifest is None:
                continue
            for game in manifest.games:
                if game.context != context:
                    continue
                if game.board_size is None or game.handicap is None:
                    continue
                game_bucket = compute_bucket_key(game.board_size, game.handicap)
                if game_bucket == bucket_key:
                    all_games.append(game)
        return all_games

    def on_preview(*_args: Any) -> None:
        try:
            n = int(n_input.text.strip())
            if n <= 0:
                ctx.controls.set_status("1以上の数値を入力してください", STATUS_ERROR)
                return
        except ValueError:
            ctx.controls.set_status("有効な数値を入力してください", STATUS_ERROR)
            return

        # ゲーム収集
        all_games = collect_games_for_bucket()
        if not all_games:
            info_label.text = "該当するゲームがありません"
            return

        # added_at でソートして直近N局を取得
        sorted_games = sorted(all_games, key=lambda g: g.added_at, reverse=True)
        recent_games = sorted_games[:n]

        info_label.text = f"対象: {len(recent_games)}局（全{len(all_games)}局中）"

        # プレビュー計算
        preview = compute_profile_update_preview(recent_games, None)

        def apply_update() -> None:
            profile = load_player_profile()

            # ContextProfile を取得または作成
            ctx_key = context.value
            if ctx_key not in profile.per_context:
                profile.per_context[ctx_key] = ContextProfile(context=context)
            ctx_profile = profile.per_context[ctx_key]

            # BucketProfile を作成または更新
            bucket_profile = BucketProfile(
                viewer_level=preview["viewer_level"],
                viewer_preset=preview["viewer_preset"],
                confidence=preview["confidence"],
                samples=preview["samples"],
                analyzed_ratio=preview["analyzed_ratio"],
                engine_profile_id=preview["engine_profile_id"],
                use_for_reports=True,
                updated_at=datetime.now().isoformat(),
            )
            ctx_profile.buckets[bucket_key] = bucket_profile

            # 保存
            profile.updated_at = datetime.now().isoformat()
            save_player_profile(profile)

            ctx.controls.set_status(f"{bucket_key} プロファイルを更新しました", STATUS_INFO)
            popup.dismiss()
            on_updated()

        show_update_preview_dialog(ctx, context, bucket_key, preview, apply_update)

    def on_cancel(*_args: Any) -> None:
        popup.dismiss()

    preview_btn = Button(
        text="プレビュー",
        size_hint_x=0.5,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    preview_btn.bind(on_release=on_preview)

    cancel_btn = Button(
        text="キャンセル",
        size_hint_x=0.5,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    cancel_btn.bind(on_release=on_cancel)

    button_row.add_widget(preview_btn)
    button_row.add_widget(cancel_btn)
    content.add_widget(button_row)

    popup.open()


# =============================================================================
# Main Player Profile Popup
# =============================================================================


def show_player_profile_popup(
    ctx: "FeatureContext",
    katrain_gui: Any,
) -> None:
    """Player Profile ポップアップを表示

    Args:
        ctx: FeatureContext
        katrain_gui: KaTrainGui インスタンス
    """
    # 状態管理
    selected_context: list[Context] = [Context.HUMAN]
    cards_container: list[BoxLayout | None] = [None]

    # メインレイアウト
    main_layout = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # ヘッダー
    header_label = Label(
        text="Player Profile",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(18),
    )
    main_layout.add_widget(header_label)

    # Context 切替ボタン行
    context_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(40),
        spacing=dp(5),
    )

    def refresh_cards() -> None:
        """Bucket カードを更新"""
        if cards_container[0] is not None:
            cards_scroll.remove_widget(cards_container[0])

        profile = load_player_profile()
        ctx_key = selected_context[0].value
        ctx_profile = profile.per_context.get(ctx_key)

        container = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            size_hint_y=None,
        )
        container.bind(minimum_height=container.setter("height"))

        # 標準的なBucket一覧
        bucket_keys = ["19_even", "19_handicap", "13_even", "13_handicap", "9_even", "9_handicap"]

        for bucket_key in bucket_keys:
            bucket_profile = None
            if ctx_profile is not None:
                bucket_profile = ctx_profile.buckets.get(bucket_key)

            card = build_bucket_card(bucket_key, bucket_profile)
            container.add_widget(card)

        cards_container[0] = container
        cards_scroll.add_widget(container)

    def make_context_select(c: Context) -> Callable[[Any, str], None]:
        def select_fn(instance: Any, state: str) -> None:
            if state == "down":
                selected_context[0] = c
                refresh_cards()
        return select_fn

    for ctx_enum in [Context.HUMAN, Context.VS_KATAGO, Context.GENERATED]:
        btn = ToggleButton(
            text=CONTEXT_LABELS[ctx_enum],
            group="profile_context",
            state="down" if ctx_enum == Context.HUMAN else "normal",
            font_name=Theme.DEFAULT_FONT,
            background_color=Theme.BOX_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        btn.bind(state=make_context_select(ctx_enum))
        context_row.add_widget(btn)

    main_layout.add_widget(context_row)

    # カードスクロールビュー
    cards_scroll = ScrollView(size_hint_y=1)
    main_layout.add_widget(cards_scroll)

    refresh_cards()

    # アクションボタン行
    action_row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(48),
        spacing=dp(10),
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(550), dp(550)],
        content=main_layout,
        auto_dismiss=True,
    )
    popup.title = "Smart Kifu - Player Profile"

    def on_update(*_args: Any) -> None:
        # Bucket選択ダイアログを表示（簡易版：最初のBucketを選択）
        show_update_bucket_dialog(
            ctx,
            selected_context[0],
            "19_even",
            on_updated=refresh_cards,
        )

    def on_close(*_args: Any) -> None:
        popup.dismiss()

    update_btn = Button(
        text="Bucket 更新...",
        size_hint_x=0.5,
        background_color=Theme.BOX_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    update_btn.bind(on_release=on_update)

    close_btn = Button(
        text="閉じる",
        size_hint_x=0.5,
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    close_btn.bind(on_release=on_close)

    action_row.add_widget(update_btn)
    action_row.add_widget(close_btn)
    main_layout.add_widget(action_row)

    popup.open()


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    "show_player_profile_popup",
    "show_update_bucket_dialog",
    "build_bucket_card",
]
