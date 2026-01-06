"""
UI構築ヘルパー関数

重複するUIパターンを共通化し、コードの保守性を向上させる。
"""
from __future__ import annotations

from typing import Optional, Tuple

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from katrain.gui.theme import Theme


def bind_label_text_size(label: Label) -> Label:
    """Labelのtext_sizeをサイズに自動バインドする。

    Args:
        label: バインド対象のLabel

    Returns:
        同じLabelインスタンス（チェーン可能）
    """
    label.bind(size=lambda lbl, _sz: setattr(lbl, "text_size", (lbl.width, lbl.height)))
    return label


def create_styled_label(
    text: str,
    size_hint_x: float = 1.0,
    halign: str = "left",
    valign: str = "middle",
) -> Label:
    """スタイル付きLabelを作成する。

    Args:
        text: 表示テキスト
        size_hint_x: 幅のヒント
        halign: 水平方向の配置
        valign: 垂直方向の配置

    Returns:
        スタイル適用済みLabel（text_sizeバインド済み）
    """
    label = Label(
        text=text,
        size_hint_x=size_hint_x,
        halign=halign,
        valign=valign,
        color=Theme.TEXT_COLOR,
        font_name=Theme.DEFAULT_FONT,
    )
    return bind_label_text_size(label)


def create_text_input_row(
    label_text: str,
    initial_value: str = "",
    label_size_hint_x: float = 0.35,
    input_size_hint_x: float = 0.65,
    row_height: int = 40,
    spacing: int = 10,
    with_browse: bool = False,
    browse_text: str = "Browse...",
    browse_size_hint_x: float = 0.15,
) -> Tuple[BoxLayout, TextInput, Optional[Button]]:
    """Label + TextInput の行を作成する。

    Args:
        label_text: ラベルテキスト
        initial_value: テキスト入力の初期値
        label_size_hint_x: ラベル幅のヒント
        input_size_hint_x: 入力幅のヒント
        row_height: 行の高さ（dp）
        spacing: ウィジェット間のスペース（dp）
        with_browse: Browseボタンを追加するか
        browse_text: Browseボタンのテキスト
        browse_size_hint_x: Browseボタン幅のヒント

    Returns:
        (row, text_input, browse_button or None) のタプル
    """
    row = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(row_height),
        spacing=dp(spacing),
    )

    label = create_styled_label(label_text, size_hint_x=label_size_hint_x)

    # Browseボタン分を調整（負にならないよう保護）
    actual_input_size_hint_x = input_size_hint_x
    if with_browse:
        actual_input_size_hint_x = max(0.1, input_size_hint_x - browse_size_hint_x)

    text_input = TextInput(
        text=initial_value,
        multiline=False,
        size_hint_x=actual_input_size_hint_x,
        font_name=Theme.DEFAULT_FONT,
    )

    row.add_widget(label)
    row.add_widget(text_input)

    browse_button = None
    if with_browse:
        browse_button = Button(
            text=browse_text,
            size_hint_x=browse_size_hint_x,
            background_color=Theme.LIGHTER_BACKGROUND_COLOR,
            color=Theme.TEXT_COLOR,
        )
        row.add_widget(browse_button)

    return row, text_input, browse_button
