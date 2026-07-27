"""Common base classes and input widgets for katrain GUI popups.

Phase 140 P2-1: Extracted from katrain/gui/popups.py to enable focused
maintenance and faster incremental imports.
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from typing import Any

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.textfield import MDTextField

from katrain.common.resource_utils import find_package_resource
from katrain.gui.kivyutils import I18NSpinner
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label, Popup, _sync_font_to_hint_labels


def _get_app_gui() -> Any:
    """アプリのguiインスタンスを安全に取得

    Returns:
        gui instance or None

    Note: KivyMD (MDApp) と Kivy (App) の両方に対応
          将来的な移行を容易にするためヘルパー関数化
    """
    try:
        from kivymd.app import MDApp

        app = MDApp.get_running_app()
    except ImportError:
        from kivy.app import App

        app = App.get_running_app()

    if app is None:
        return None
    return getattr(app, "gui", None)


def clamp_popup_size(requested: list[float], max_ratio: float = 0.9) -> list[int]:
    """Clamp a popup size to ``max_ratio`` of the current app window.

    Phase 287-E: the popup dialogs previously used fixed ``dp(W)`` /
    ``dp(H)`` sizes (e.g. 1200x950 for the general settings) that would
    overflow the screen on small windows, 1366x768 laptops with the
    Windows DPI scale at 125%, and DPI-2x displays. This helper returns
    a size that never exceeds ``max_ratio`` (default 90%) of the current
    ``Window.width`` / ``Window.height``. Falls back to the requested
    size if the window dimensions are not yet known (e.g. in headless
    tests).

    The pure-Python sizing logic lives in
    :mod:`katrain.core.gui_utils.popup_math` so it can be unit-tested
    without importing Kivy. This wrapper merely injects the live
    ``Window`` dimensions.

    Args:
        requested: ``[width, height]`` in dp / px.
        max_ratio: Maximum fraction of the window dimension the popup
            may occupy. Default 0.9 leaves a 5% margin on each side.

    Returns:
        A fresh ``[width, height]`` list with each dimension clamped
        independently and rounded to int (Kivy Popup size takes int).
    """
    from kivy.core.window import Window

    from katrain.core.gui_utils.popup_math import compute_clamped_popup_size

    win_w = getattr(Window, "width", None)
    win_h = getattr(Window, "height", None)
    return compute_clamped_popup_size(
        requested,
        window_width=win_w,
        window_height=win_h,
        max_ratio=max_ratio,
    )


class I18NPopup(Popup):
    title_key = StringProperty("")
    font_name = StringProperty(Theme.DEFAULT_FONT)
    title_font = StringProperty(Theme.DEFAULT_FONT)
    # クラス変数: 前回のupdate_stateイベント（連続dismiss対策）
    _pending_update_event: Any = None

    def __init__(self, size: list[int] | None = None, **kwargs: Any) -> None:
        if size:  # do not exceed window size
            # v3: sizeをミューテートせず新しいリストを作成
            # Kivyは内部でlistに変換するため、listで渡すのがベストプラクティス
            gui = _get_app_gui()
            if gui:
                size = [min(gui.width, size[0]), min(gui.height, size[1])]
            else:
                # appがNoneの場合は元のsizeをlistに変換（tuple対応）
                size = list(size) if not isinstance(size, list) else size
        super().__init__(size=size, **kwargs)
        self.bind(on_dismiss=self._schedule_update_state)

    def _schedule_update_state(self, popup_instance: Any) -> None:
        """on_dismiss時にupdate_stateをスケジュール（重複防止付き）

        Args:
            popup_instance: Kivyのbindコールバックから渡されるPopupインスタンス

        Note:
            - v5改善: 引数を明示的に受け取る（*argsより安全）
            - Phase 22: 遅延を1秒→0.1秒に短縮、前回イベントをキャンセル
        """
        # 前回のイベントをキャンセル（連続dismiss対策）
        if I18NPopup._pending_update_event is not None:
            I18NPopup._pending_update_event.cancel()
        # 0.1秒後に実行（Kivyのレイアウト計算に十分な余裕）
        I18NPopup._pending_update_event = Clock.schedule_once(self._do_update_state, 0.1)

    def _do_update_state(self, dt: float) -> None:
        """実際のupdate_state呼び出し（nullチェック付き）

        Args:
            dt: Clock.schedule_onceから渡される経過時間（秒）

        Note: アプリ終了中やgui未初期化時は何もしない
        """
        gui = _get_app_gui()
        if gui:
            gui.update_state()


class LabelledTextInput(MDTextField):
    input_property = StringProperty("")
    multiline = BooleanProperty(False)

    # Phase 280: あらゆる代入経路 (manual setattr / KV rule / KivyMD 内部
    # メソッド) で色属性が青に戻るのを防ぐ最強の防御。
    # ``__setattr__`` を override して色属性への代入を横取りし、
    # ターゲット値で固定する。``on_<prop>`` ハンドラとの二重防御。
    # フォーカス時にしても青色文字が出ないように ``foreground_color`` /
    # ``text_color`` / ``text_color_focus`` / ``text_color_normal`` /
    # ``disabled_foreground_color`` / ``cursor_color`` も白いまま維持。
    _COLOR_VALUE_GUARDS = {
        "selection_color": [0, 0, 0, 0],
    }
    # Phase 280: 白色維持対象プロパティ一覧。``__setattr__`` で代入時に
    # ターゲット値 (Theme.TEXT_COLOR) に固定する。``hint_text_color`` /
    # ``helper_text_color`` / ``line_color_*`` は枠線やヒントの色なので
    # ここでは保護せず、``line_color_focus`` のみ枠線用に白維持する。
    _WHITE_GUARDED = frozenset(
        {
            "foreground_color",
            "text_color",
            "text_color_focus",
            "text_color_normal",
            "disabled_foreground_color",
            "cursor_color",
            "line_color_focus",
        }
    )

    def __setattr__(self, name: str, value: Any) -> None:
        # Phase 280: 色属性の代入を完全横取り。
        # - ``selection_color`` は ``[0, 0, 0, 0]`` (完全透明) に固定
        # - ``foreground_color`` / ``text_color`` / ``text_color_focus``
        #   / ``text_color_normal`` / ``disabled_foreground_color``
        #   / ``cursor_color`` / ``line_color_focus`` は ``Theme.TEXT_COLOR``
        #   (白) を維持。これで 1 フレームだけ青が出るのも防ぐ。
        if name in self._COLOR_VALUE_GUARDS:
            target = self._COLOR_VALUE_GUARDS[name]
            if value != target:
                value = target
        elif name in self._WHITE_GUARDED:
            _target: list[float] = list(Theme.TEXT_COLOR)
            if value != _target:
                value = _target
        super().__setattr__(name, value)

    def on_kv_post(self, base_widget: Any) -> None:
        # Phase 281 (tofu-fix): KivyMD 1.2.0's internal ``TextfieldLabel``
        # does not reliably inherit ``font_name`` from the parent
        # ``MDTextField`` (the binding propagates asynchronously and
        # can race with the first paint). Force the sync once the KV
        # rules have been applied so the Japanese hint text uses
        # ``NotoSansJP-Regular.otf`` instead of falling back to
        # Roboto (which has no JP glyphs and renders as tofu).
        super().on_kv_post(base_widget)
        _sync_font_to_hint_labels(self)
        # Phase 280: KivyMD 1.2.0 内部の ``set_default_colors`` メソッド
        # (``_set_color`` 経由) がテーマ更新時に ``selection_color`` を
        # ``[0.184, 0.655, 0.831, 0.5]`` (青 50% 透明) に戻してしまう、
        # あるいは ``foreground_color`` を ``theme_cls.primary_color``
        # (青) に戻してしまう副作用を Python レベルで compensate。
        # KV rule だけの override ではタイミング次第で反映漏れが
        # 起きるので、``_set_color`` を override して上書き対象プロパティを
        # 白 Theme.TEXT_COLOR と完全透明に固定する。
        self._hardcoded_color_attrs = {
            "selection_color",
            "foreground_color",
            "cursor_color",
            "text_color_focus",
            "text_color_normal",
        }
        # Phase 280: カーソルの目標色を保持 (``on_focus`` で再適用する)。
        # ユーザー要望に従い白 ``[1, 1, 1, 1]`` で固定。白文字編集位置の
        # 目印として、白い縦線が BOX_BACKGROUND_COLOR (やや明るい紺) の
        # 上で高コントラストで表示される。文字本体 (白) とカーソル (白)
        # の境界は幅 2.5sp の縦線形状で識別可能。
        self._target_cursor_color = [1, 1, 1, 1]
        # Phase 280: KivyMD 1.2.0 の stub KV にはカーソルのキャンバス描画が
        # 含まれていない (KivyMD 0.104.1 から削除された)。 canvas.after に
        # 自前で ``Color`` + ``Rectangle`` 命令を追加し、``cursor_color`` /
        # ``cursor_pos`` / ``cursor_width`` / ``line_height`` の各プロパティに
        # 明示的に bind して、KV rule の ``self.cursor_color`` binding で
        # 起きない問題 (初回評価時に古い [1, 0, 0, 1] が残る) を克服する。
        # グループ ``kivymd_cursor`` を付けて cleanup 可能にする。
        from kivy.graphics import Color as _KColor
        from kivy.graphics import Rectangle as _KRect

        # 初期状態はフォーカスなし → 透明 (非表示)
        with self.canvas.after:
            self._cursor_color_instr = _KColor(0, 0, 0, 0)
            self._cursor_rect_instr = _KRect(
                pos=self.cursor_pos,
                size=(self.cursor_width, -self.line_height),
            )
        self.bind(
            cursor_color=self._update_cursor_canvas,
            cursor_pos=self._update_cursor_canvas,
            cursor_width=self._update_cursor_canvas,
            line_height=self._update_cursor_canvas,
            focus=self._update_cursor_canvas,
        )

        # Phase 280: KivyMD 1.2.0 の private カラープロパティ
        # ``_text_color_focus`` / ``_text_color_normal`` / ``_hint_text_color`` /
        # ``_hint_text_color_focus`` / ``_hint_text_color_normal`` /
        # ``_line_color_focus`` / ``_line_color_normal`` / ``_icon_left_color`` /
        # ``_icon_right_color`` がフォーカス時に ``theme_cls.primary_color``
        # (青) にフォールバックするのを防ぐ。``set_default_colors`` が
        # ``_set_color`` 経由でこれらを更新するため、``on_<prop>`` ハンドラ
        # で次フレーム復元する。``functools.partial`` で各プロパティ名を
        # キャプチャして、正しい属性を白に書き戻す。

        def _make_kivymd_color_handler(_attr_name: str) -> Callable[[Any, Any], None]:
            def _handler(instance: Any, value: Any) -> None:
                if not value or len(value) < 4:
                    return
                r, g, b, a = value[:4]
                # 青系判定: 青 > 赤+緑 かつ 青 > 0.3 (大体の青色域)
                is_bluish = b > (r + g) * 0.6 and b > 0.3
                if is_bluish:
                    from kivy.clock import Clock

                    def _reset_kivymd_color(_dt: float, attr: str = _attr_name) -> None:
                        target = list(Theme.TEXT_COLOR)
                        current = getattr(self, attr, None)
                        if current and len(current) >= 4 and current[2] > (current[0] + current[1]) * 0.6:
                            # 強制 setattr で書き戻し。``__setattr__``
                            # 横取りで白に固定される。
                            try:
                                object.__setattr__(self, attr, target)
                            except Exception:
                                setattr(self, attr, target)
                            self.canvas.ask_update()

                    Clock.schedule_once(_reset_kivymd_color, 0)

            return _handler

        for _kivymd_color_attr in (
            "_text_color_focus",
            "_text_color_normal",
            "_hint_text_color",
            "_hint_text_color_focus",
            "_hint_text_color_normal",
            "_line_color_focus",
            "_line_color_normal",
            "_icon_left_color",
            "_icon_right_color",
            "_max_length_text_color",
        ):
            with contextlib.suppress(Exception):
                self.bind(**{_kivymd_color_attr: _make_kivymd_color_handler(_kivymd_color_attr)})

    def _on_kivymd_text_color(self, instance: Any, value: Any) -> None:
        # Phase 280: KivyMD 1.2.0 の ``_text_color_focus`` 系プロパティが
        # フォーカス時に ``theme_cls.primary_color`` (青) に切り替わる
        # 副作用を compensate。値を見て、青系 (B > R+G) なら白に矯正。
        # ``text_color_focus`` 系を ``Theme.TEXT_COLOR`` に bind しても
        # ``_text_color_focus`` は別プロパティのため、青が残る。
        if not value or len(value) < 4:
            return
        r, g, b, a = value[:4]
        # 青系判定: 青 > 赤+緑 かつ 青 > 0.3 (大体の青色域)
        is_bluish = b > (r + g) * 0.6 and b > 0.3
        if is_bluish:
            from kivy.clock import Clock

            def _reset_kivymd_color(_dt: float) -> None:
                attr = getattr(self, "_last_kivymd_color_attr", "_text_color_focus")
                target = list(Theme.TEXT_COLOR)
                current = getattr(self, attr, None)
                if current and len(current) >= 4 and current[2] > (current[0] + current[1]) * 0.6:
                    # KivyMD の ``on_<prop>`` ハンドラは通常未定義なので、
                    # 強制 setattr で書き戻し。``__setattr__`` 横取りで
                    # 白に固定される。
                    try:
                        object.__setattr__(self, attr, target)
                    except Exception:
                        setattr(self, attr, target)
                    self.canvas.ask_update()

            self._last_kivymd_color_attr = "_text_color_focus"
            Clock.schedule_once(_reset_kivymd_color, 0)

    def _update_cursor_canvas(self, *_args: Any) -> None:
        # Phase 280: ``cursor_color`` / ``cursor_pos`` / ``cursor_width``
        # / ``line_height`` / ``focus`` のいずれかが変化したら Canvas 命令を
        # 最新値に更新する。Kivy canvas 動的 binding では初回評価時に古い値
        # (例: cursor_color の TextInput デフォルト [1, 0, 0, 1]) が残る
        # ため、明示的に ``self.cursor_color`` を ``_cursor_color_instr.rgba``
        # にコピーする。
        # フォーカス時のみ可視 (alpha=1)、非フォーカス時は完全に透明 (alpha=0)
        # にして「選択したところだけカーソル表示」要件を満たす。
        instr = getattr(self, "_cursor_color_instr", None)
        rect = getattr(self, "_cursor_rect_instr", None)
        if instr is not None:
            if self.focus:
                instr.rgba = self.cursor_color
            else:
                instr.rgba = [0, 0, 0, 0]
        if rect is not None:
            rect.pos = self.cursor_pos
            rect.size = (self.cursor_width, -self.line_height)

    def _set_color(self, attr_name: str, color: Any, updated: bool) -> None:
        # Phase 280: ハードコードした色属性は KivyMD 1.2.0 内部の
        # ``set_default_colors`` (``_set_color``) から上書きさせない。
        # それ以外の属性 (line_color_normal/focus, hint_text_color など)
        # は通常通り親クラスの挙動に従う。
        if attr_name in getattr(self, "_hardcoded_color_attrs", set()):
            return
        super()._set_color(attr_name, color, updated)

    def on_focus(self, instance: Any, focus: bool) -> None:
        # Phase 280: フォーカスが移った瞬間に KivyMD 1.2.0 が
        # ``set_default_colors(updated=True)`` をトリガーして色属性を
        # テーマデフォルトに戻すことがあるので、その直後に自前の白系
        # プロパティを強制再適用する。``super().on_focus()`` 後に
        # 上書きする順序で必ず白を維持。
        super().on_focus(instance, focus)
        self.foreground_color = Theme.TEXT_COLOR
        self.cursor_color = getattr(self, "_target_cursor_color", [1, 1, 1, 1])
        self.selection_color = [0, 0, 0, 0]
        self.text_color_focus = Theme.TEXT_COLOR
        self.text_color_normal = Theme.TEXT_COLOR
        # Canvas 命令も即時更新 (``_update_cursor_canvas`` 内で focus 判定)
        self._update_cursor_canvas()
        # canvas.after の 'selection' グループ Color 命令を直接透明化
        self._scrub_selection_canvas()
        # canvas 全体を強制再描画 (Windows DWM の古いフレームキャッシュを無効化)
        self.canvas.ask_update()

    def on_selection_color(self, instance: Any, value: Any) -> None:
        # Phase 280: ユーザー報告「選択すると青色文字になる」問題の
        # 最終防御。KivyMD 1.2.0 内部の ``set_default_colors`` 系が
        # 動的に ``selection_color`` を ``theme_cls.primary_color`` (青)
        # に戻しても、その直後に ``on_selection_color`` が発火して
        # ここで [0, 0, 0, 0] (完全透明) に戻す。遅延フレームで再設定
        # することで、TextInput 内部の選択範囲ハイライト用 Color 命令の
        # ``rgba`` も次の draw frame で透明に上書きされる。
        if value != [0, 0, 0, 0]:
            from kivy.clock import Clock

            def _reset_selection_color(_dt: float) -> None:
                # 再帰防止: 既に [0, 0, 0, 0] なら何もしない
                if list(self.selection_color) != [0, 0, 0, 0]:
                    self.selection_color = [0, 0, 0, 0]
                # TextInput 内部の canvas.after 'selection' グループの
                # Color 命令を直接透明化 (値プロパティが正しくても
                # 描画の命令キャッシュが残るケースに対応)。
                self._scrub_selection_canvas()

            Clock.schedule_once(_reset_selection_color, 0)

    def _scrub_selection_canvas(self) -> None:
        # Phase 280: TextInput._draw_selection() が canvas.after に
        # ``Color(*self.selection_color, group='selection')`` を追加
        # する。この Color 命令の rgba が ``[0.184, 0.655, 0.831, 0.5]``
        # (青 50% 透明) の場合、青いハイライトとして描画される。
        # 値プロパティ ``selection_color`` を ``[0, 0, 0, 0]`` にしても、
        # TextInput 内部に追加済み Color 命令の rgba が古い値で残る
        # ことがあるため、直接 canvas.after を歩いて 'selection'
        # グループの Color 命令を全て透明化する。
        from kivy.graphics import Color as _KColor

        for instr in self.canvas.after.get_group("selection"):
            if isinstance(instr, _KColor):
                instr.rgba = [0, 0, 0, 0]

    def on_foreground_color(self, instance: Any, value: Any) -> None:
        # Phase 280: 同上の防御を ``foreground_color`` にも。
        # KivyMD 1.2.0 内部の何かがフォーカス時に ``theme_cls.primary_color``
        # (青) に ``foreground_color`` を変えても、次フレームで白に戻す。
        # Kivy の ``ColorProperty.__set__`` は Cython で ``__setattr__`` を
        # 経由せず ``self.__dict__`` を直接書き換えるため、``__setattr__``
        # 横取りは機能しない。``on_<prop>`` ハンドラで Kivy の Property
        # バインディング経由で値を書き戻し、``canvas.ask_update()`` で
        # 描画も強制更新する。
        if value != Theme.TEXT_COLOR:
            from kivy.clock import Clock

            def _reset_fg_color(_dt: float) -> None:
                if list(self.foreground_color) != list(Theme.TEXT_COLOR):
                    self.foreground_color = Theme.TEXT_COLOR
                self.canvas.ask_update()

            Clock.schedule_once(_reset_fg_color, 0)

    def on_text_color_focus(self, instance: Any, value: Any) -> None:
        # Phase 280: 同上の防御を ``text_color_focus`` にも。
        if value != Theme.TEXT_COLOR:
            from kivy.clock import Clock

            def _reset_tcf(_dt: float) -> None:
                if list(self.text_color_focus) != list(Theme.TEXT_COLOR):
                    self.text_color_focus = Theme.TEXT_COLOR
                self.canvas.ask_update()

            Clock.schedule_once(_reset_tcf, 0)

    def on_text_color_normal(self, instance: Any, value: Any) -> None:
        # Phase 280: 同上の防御を ``text_color_normal`` にも。
        if value != Theme.TEXT_COLOR:
            from kivy.clock import Clock

            def _reset_tcn(_dt: float) -> None:
                if list(self.text_color_normal) != list(Theme.TEXT_COLOR):
                    self.text_color_normal = Theme.TEXT_COLOR
                self.canvas.ask_update()

            Clock.schedule_once(_reset_tcn, 0)

    def on_font_name(self, instance: Any, value: str) -> None:
        # font_name changes (e.g. theme switch or programmatic
        # override) must propagate to the internal hint label, too.
        # We deliberately do NOT call ``super().on_font_name`` here:
        # KivyMD 1.2.0's ``MDTextField`` does not define an
        # ``on_font_name`` method (it inherits ``TextInput`` which
        # also lacks one), and calling ``super()`` raises
        # ``AttributeError``. Kivy's property dispatch does not
        # require a ``super().on_*`` call — it merely invokes this
        # method when the binding fires.
        _sync_font_to_hint_labels(self)

    @property
    def input_value(self) -> Any:
        return self.text

    @property
    def raw_input_value(self) -> Any:
        return self.text


class LabelledPathInput(LabelledTextInput):
    check_path = BooleanProperty(True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        Clock.schedule_once(self.check_error, 0)

    def check_error(self, _dt: float | None = None) -> None:
        file = find_package_resource(self.input_value, silent_errors=True)
        self.error = self.check_path and not (file and os.path.exists(file))

    def on_text(self, instance: Any, text: str) -> None:
        # Phase 277: KivyMD 1.2.0 ``MDTextField`` no longer exposes
        # ``on_text`` on the parent class (it migrated to the
        # ``TextInput`` ``text`` property dispatcher with a different
        # signature). Calling ``super().on_text`` would raise
        # ``AttributeError``; we just need to run our validation hook.
        self.check_error()

    @property
    def input_value(self) -> Any:
        return self.text.strip().replace("\n", " ").replace("\r", " ")


class LabelledCheckBox(MDCheckbox):
    input_property = StringProperty("")

    def __init__(self, text: str | None = None, **kwargs: Any) -> None:
        if text is not None:
            kwargs["active"] = text.lower() == "true"
        super().__init__(**kwargs)

    @property
    def input_value(self) -> bool:
        return bool(self.active)

    def raw_input_value(self) -> Any:
        return self.active


class LabelledSpinner(I18NSpinner):
    input_property = StringProperty("")

    @property
    def input_value(self) -> Any:
        return self.selected[1]  # ref value

    def raw_input_value(self) -> Any:
        return self.text


class LabelledFloatInput(LabelledTextInput):
    input_filter = ObjectProperty("float")

    @property
    def input_value(self) -> float:
        return float(self.text or "0.0")


class LabelledIntInput(LabelledTextInput):
    input_filter = ObjectProperty("int")

    @property
    def input_value(self) -> int:
        return int(self.text or "0")


class LabelledSelectionSlider(BoxLayout):
    input_property = StringProperty("")
    values = ListProperty([(0, "")])  # (value:numeric,label:string) pairs
    key_option = BooleanProperty(False)

    def set_value(self, v: Any) -> None:
        self.slider.set_value(v)
        self.textbox.text = str(v)

    @property
    def input_value(self) -> float:
        if self.textbox.text:
            return float(self.textbox.text)
        return float(self.slider.values[self.slider.index][0])

    @property
    def raw_input_value(self) -> Any:
        return self.textbox.text


class InputParseError(Exception):
    pass


class DescriptionLabel(Label):
    font_name = StringProperty(Theme.DEFAULT_FONT)


def wrap_anchor(widget: Any) -> AnchorLayout:
    anchor = AnchorLayout()
    anchor.add_widget(widget)
    return anchor
