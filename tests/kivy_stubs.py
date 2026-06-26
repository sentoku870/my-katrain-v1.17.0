"""Kivy クラススタブ（Phase 146）

gui/ 層のテストで実 Kivy インスタンスを生成する代わりに使う
スタブ群。``MagicMock`` ベースで、テストに必要な API surface
（属性名タプル）を明示する。

使用方法::

    from tests.kivy_stubs import make_ka_train_gui_stub

    def test_something():
        gui = make_ka_train_gui_stub()
        gui.update_state(node)
        gui.update_state.assert_called_once_with(node)

スタブ追加時の注意:
    - 実クラスの公開メソッドのみをスタブ化
    - 内部実装に踏み込まない（drift リスク軽減）
    - 新しいスタブが必要になったら Phase 147 以降で追加
"""

from __future__ import annotations

from typing import Callable
from unittest.mock import MagicMock


KA_TRAIN_GUI_ATTRS: tuple[str, ...] = (
    "engine",
    "controls",
    "ivar",
    "game",
    "current_node",
    "comment_node",
    "players_info",
    "pondering",
    "_config",
    "update_state",
    "config",
    "log",
)

CONTROLS_PANEL_ATTRS: tuple[str, ...] = (
    "update_state",
    "set_active",
    "switch_control_panel",
    "new_game",
    "set_status",
)

BADUK_PAN_WIDGET_ATTRS: tuple[str, ...] = (
    "update_state",
    "draw_board",
    "set_handicap",
    "animate_stone_placement",
    "redraw",
)

POPUP_ATTRS: tuple[str, ...] = (
    "open",
    "dismiss",
    "content",
    "title",
    "size_hint",
    "auto_dismiss",
)


def _make_stub(attrs: tuple[str, ...], *, name: str = "Stub") -> MagicMock:
    """属性付きの MagicMock スタブを生成する。"""
    stub = MagicMock(name=name)
    for attr in attrs:
        setattr(stub, attr, MagicMock(name=attr))
    return stub


def make_ka_train_gui_stub() -> MagicMock:
    """KaTrainGui (katrain/__main__.py:140) のスタブを生成する。"""
    return _make_stub(KA_TRAIN_GUI_ATTRS, name="KaTrainGuiStub")


def make_controls_panel_stub() -> MagicMock:
    """ControlsPanel (katrain/gui/controlspanel.py) のスタブを生成する。"""
    return _make_stub(CONTROLS_PANEL_ATTRS, name="ControlsPanelStub")


def make_baduk_pan_widget_stub() -> MagicMock:
    """BadukPanWidget (katrain/gui/badukpan.py) のスタブを生成する。"""
    return _make_stub(BADUK_PAN_WIDGET_ATTRS, name="BadukPanWidgetStub")


def make_popup_stub() -> MagicMock:
    """kivy.uix.popup.Popup の最小スタブを生成する。"""
    return _make_stub(POPUP_ATTRS, name="PopupStub")


STUB_FACTORIES: dict[str, Callable[[], MagicMock]] = {
    "ka_train_gui": make_ka_train_gui_stub,
    "controls_panel": make_controls_panel_stub,
    "baduk_pan_widget": make_baduk_pan_widget_stub,
    "popup": make_popup_stub,
}
