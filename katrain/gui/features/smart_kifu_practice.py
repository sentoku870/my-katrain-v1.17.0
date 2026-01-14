# katrain/gui/features/smart_kifu_practice.py
#
# Smart Kifu Learning - Practice Report UI (Phase 13.4)
#
# vs_katago 練習レポートと置石調整提案を表示するUIモジュール。

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton

from katrain.core.constants import STATUS_INFO
from katrain.core.lang import i18n
from katrain.core.smart_kifu import (
    BucketProfile,
    Context,
    GameEntry,
    PlayerProfile,
    compute_bucket_key,
    list_training_sets,
    load_manifest,
    load_player_profile,
    suggest_handicap_adjustment,
)
from katrain.gui.popups import I18NPopup
from katrain.gui.theme import Theme

if TYPE_CHECKING:
    from katrain.gui.features.context import FeatureContext


# =============================================================================
# Constants
# =============================================================================

BUCKET_LABELS = {
    "19_even": "19路 互先",
    "19_handicap": "19路 置碁",
    "13_even": "13路 互先",
    "13_handicap": "13路 置碁",
    "9_even": "9路 互先",
    "9_handicap": "9路 置碁",
}


# =============================================================================
# Practice Stats Calculation
# =============================================================================


def collect_vs_katago_games(bucket_key: Optional[str] = None) -> List[GameEntry]:
    """vs_katago のゲームを収集

    Args:
        bucket_key: フィルタするBucketキー（None の場合は全て）

    Returns:
        vs_katago のゲームエントリリスト
    """
    all_games: List[GameEntry] = []
    for set_id in list_training_sets():
        manifest = load_manifest(set_id)
        if manifest is None:
            continue
        for game in manifest.games:
            if game.context != Context.VS_KATAGO:
                continue
            if bucket_key is not None:
                if game.board_size is None or game.handicap is None:
                    continue
                game_bucket = compute_bucket_key(game.board_size, game.handicap)
                if game_bucket != bucket_key:
                    continue
            all_games.append(game)
    return all_games


def compute_practice_stats(
    games: List[GameEntry],
    recent_n: int = 10,
) -> Dict[str, Any]:
    """練習統計を計算

    Args:
        games: ゲームエントリリスト
        recent_n: 直近N局（勝率計算用）

    Returns:
        統計情報の辞書
    """
    if not games:
        return {
            "total_games": 0,
            "recent_games": 0,
            "winrate": None,
            "wins": 0,
            "losses": 0,
            "current_handicap": None,
        }

    # added_at でソートして直近N局を取得
    sorted_games = sorted(games, key=lambda g: g.added_at, reverse=True)
    recent_games = sorted_games[:recent_n]

    # 勝敗計算（result から判定）
    wins = 0
    losses = 0
    for game in recent_games:
        if game.result:
            result_upper = game.result.upper()
            # プレイヤーが黒の場合、"B+"で始まれば勝ち
            # vs_katagoでは通常プレイヤーが黒（置碁含む）
            if result_upper.startswith("B+"):
                wins += 1
            elif result_upper.startswith("W+"):
                losses += 1

    total_played = wins + losses
    winrate = wins / total_played if total_played > 0 else None

    # 現在の置石数を推定（直近ゲームから）
    current_handicap = None
    if recent_games:
        handicaps = [g.handicap for g in recent_games if g.handicap is not None]
        if handicaps:
            current_handicap = max(set(handicaps), key=handicaps.count)  # 最頻値

    return {
        "total_games": len(games),
        "recent_games": len(recent_games),
        "winrate": winrate,
        "wins": wins,
        "losses": losses,
        "current_handicap": current_handicap,
    }


# =============================================================================
# Practice Report Card Widget
# =============================================================================


def build_practice_report_card(
    bucket_key: str,
    stats: Dict[str, Any],
) -> BoxLayout:
    """練習レポートカードを構築

    Args:
        bucket_key: Bucketキー
        stats: 練習統計

    Returns:
        カードを含む BoxLayout
    """
    card = BoxLayout(
        orientation="vertical",
        size_hint_y=None,
        height=dp(180),
        padding=dp(10),
        spacing=dp(6),
    )
    # 背景色
    from kivy.graphics import Color, Rectangle
    with card.canvas.before:
        Color(0.2, 0.2, 0.25, 1)
        rect = Rectangle(pos=card.pos, size=card.size)
    card.bind(pos=lambda inst, val: setattr(rect, 'pos', val))
    card.bind(size=lambda inst, val: setattr(rect, 'size', val))

    # タイトル
    title = BUCKET_LABELS.get(bucket_key, bucket_key)
    title_label = Label(
        text=title,
        size_hint_y=None,
        height=dp(28),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(15),
        bold=True,
        halign="left",
    )
    title_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    card.add_widget(title_label)

    if stats["total_games"] == 0:
        no_data_label = Label(
            text="データなし",
            size_hint_y=1,
            color=(0.6, 0.6, 0.6, 1),
            font_name=Theme.DEFAULT_FONT,
        )
        card.add_widget(no_data_label)
        return card

    # 対局数
    games_label = Label(
        text=f"対局数: {stats['total_games']}局（直近{stats['recent_games']}局）",
        size_hint_y=None,
        height=dp(22),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
    )
    games_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    card.add_widget(games_label)

    # 勝率
    if stats["winrate"] is not None:
        winrate_text = f"勝率: {stats['winrate']:.0%}（{stats['wins']}勝 {stats['losses']}敗）"
        winrate_color = Theme.TEXT_COLOR
        if stats["winrate"] >= 0.7:
            winrate_color = (0.3, 0.8, 0.3, 1)  # 緑
        elif stats["winrate"] <= 0.3:
            winrate_color = (0.8, 0.3, 0.3, 1)  # 赤
    else:
        winrate_text = "勝率: 計算不可"
        winrate_color = (0.6, 0.6, 0.6, 1)

    winrate_label = Label(
        text=winrate_text,
        size_hint_y=None,
        height=dp(22),
        color=winrate_color,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
        halign="left",
    )
    winrate_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    card.add_widget(winrate_label)

    # 置石調整提案
    if stats["winrate"] is not None and stats["current_handicap"] is not None:
        suggested, reason = suggest_handicap_adjustment(
            stats["winrate"],
            stats["current_handicap"]
        )
        suggestion_label = Label(
            text=f"提案: {reason}",
            size_hint_y=None,
            height=dp(44),
            color=(0.9, 0.8, 0.3, 1),  # 黄色
            font_name=Theme.DEFAULT_FONT,
            font_size=dp(11),
            halign="left",
            valign="top",
        )
        suggestion_label.bind(size=lambda lbl, _: setattr(lbl, "text_size", (lbl.width, None)))
        card.add_widget(suggestion_label)
    else:
        # スペーサー
        card.add_widget(BoxLayout(size_hint_y=None, height=dp(44)))

    return card


# =============================================================================
# Main Practice Report Popup
# =============================================================================


def show_practice_report_popup(
    ctx: "FeatureContext",
    katrain_gui: Any,
) -> None:
    """練習レポートポップアップを表示

    Args:
        ctx: FeatureContext
        katrain_gui: KaTrainGui インスタンス
    """
    # メインレイアウト
    main_layout = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        padding=dp(15),
    )

    # ヘッダー
    header_label = Label(
        text="vs KataGo 練習レポート",
        size_hint_y=None,
        height=dp(30),
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(18),
    )
    main_layout.add_widget(header_label)

    # サブヘッダー
    sub_label = Label(
        text="直近10局の勝率と置石調整提案",
        size_hint_y=None,
        height=dp(20),
        color=(0.7, 0.7, 0.7, 1),
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(12),
    )
    main_layout.add_widget(sub_label)

    # レポートカードスクロールビュー
    cards_scroll = ScrollView(size_hint_y=1)

    cards_container = BoxLayout(
        orientation="vertical",
        spacing=dp(10),
        size_hint_y=None,
    )
    cards_container.bind(minimum_height=cards_container.setter("height"))

    # 各Bucketのレポートカードを生成
    bucket_keys = ["19_even", "19_handicap", "13_even", "13_handicap", "9_even", "9_handicap"]

    total_vs_katago_games = 0
    for bucket_key in bucket_keys:
        games = collect_vs_katago_games(bucket_key)
        total_vs_katago_games += len(games)
        stats = compute_practice_stats(games, recent_n=10)
        card = build_practice_report_card(bucket_key, stats)
        cards_container.add_widget(card)

    cards_scroll.add_widget(cards_container)
    main_layout.add_widget(cards_scroll)

    # 総計表示
    total_label = Label(
        text=f"合計: {total_vs_katago_games}局（全Bucket）",
        size_hint_y=None,
        height=dp(25),
        color=(0.7, 0.7, 0.7, 1),
        font_name=Theme.DEFAULT_FONT,
        font_size=dp(11),
    )
    main_layout.add_widget(total_label)

    # 閉じるボタン
    close_btn = Button(
        text="閉じる",
        size_hint_y=None,
        height=dp(48),
        background_color=Theme.LIGHTER_BACKGROUND_COLOR,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )

    popup = I18NPopup(
        title_key="",
        size=[dp(500), dp(600)],
        content=main_layout,
        auto_dismiss=True,
    )
    popup.title = "Smart Kifu - 練習レポート"

    close_btn.bind(on_release=lambda *_: popup.dismiss())
    main_layout.add_widget(close_btn)

    popup.open()


# =============================================================================
# __all__
# =============================================================================

__all__ = [
    "show_practice_report_popup",
    "collect_vs_katago_games",
    "compute_practice_stats",
    "build_practice_report_card",
]
