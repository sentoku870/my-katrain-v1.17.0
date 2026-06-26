"""Kivy ヘッドレステスト基盤のスモークテスト（Phase 146）

このテストは ``KivyUnitTest`` 基盤と 4 つの Kivy クラススタブが
正しく動作することを確認する。
"""

from __future__ import annotations

import os

import pytest

from tests.kivy_stubs import (
    BADUK_PAN_WIDGET_ATTRS,
    CONTROLS_PANEL_ATTRS,
    KA_TRAIN_GUI_ATTRS,
    POPUP_ATTRS,
    STUB_FACTORIES,
    make_baduk_pan_widget_stub,
    make_controls_panel_stub,
    make_ka_train_gui_stub,
    make_popup_stub,
)
from tests.kivy_test_base import KivyUnitTest


class TestKivyUnitTestEnv(KivyUnitTest):
    """KivyUnitTest ベースクラスの環境変数管理確認。"""

    def test_env_vars_set_in_method(self):
        """setup_method 後に Kivy 環境変数が設定される。"""
        for key, expected in self.KIVY_ENV_VARS.items():
            actual = os.environ.get(key)
            assert actual == expected, f"{key}: expected={expected!r} actual={actual!r}"

    def test_env_vars_keys_complete(self):
        """環境変数キーが漏れなく定義されている（回帰検知）。"""
        required_keys = {
            "KIVY_NO_ARGS",
            "KIVY_NO_FILELOG",
            "KIVY_NO_CONSOLELOG",
            "KIVY_NO_ENV_CONFIG",
            "KIVY_HEADLESS",
            "KIVY_NO_WINDOW",
            "KIVY_GL_BACKEND",
            "SDL_VIDEODRIVER",
        }
        assert set(self.KIVY_ENV_VARS.keys()) == required_keys

    def test_setup_and_teardown_idempotent(self):
        """同じ環境変数セットを再適用しても安全。"""
        os.environ.update(self.KIVY_ENV_VARS)
        for key, expected in self.KIVY_ENV_VARS.items():
            assert os.environ.get(key) == expected


class TestKaTrainGuiStub:
    """KaTrainGuiStub の動作確認。"""

    def test_has_all_required_attrs(self):
        stub = make_ka_train_gui_stub()
        for attr in KA_TRAIN_GUI_ATTRS:
            assert hasattr(stub, attr), f"missing attr: {attr}"

    def test_callable_methods(self):
        """メソッドとして呼ばれる属性が呼び出し可能。"""
        stub = make_ka_train_gui_stub()
        stub.update_state("node")
        stub.config("key", "default")
        stub.log("debug message")
        stub.update_state.assert_called_once_with("node")
        stub.config.assert_called_once_with("key", "default")
        stub.log.assert_called_once_with("debug message")


class TestControlsPanelStub:
    """ControlsPanelStub の動作確認。"""

    def test_has_all_required_attrs(self):
        stub = make_controls_panel_stub()
        for attr in CONTROLS_PANEL_ATTRS:
            assert hasattr(stub, attr), f"missing attr: {attr}"

    def test_set_status_callable(self):
        stub = make_controls_panel_stub()
        stub.set_status("test message")
        stub.set_status.assert_called_once_with("test message")


class TestBadukPanWidgetStub:
    """BadukPanWidgetStub の動作確認。"""

    def test_has_all_required_attrs(self):
        stub = make_baduk_pan_widget_stub()
        for attr in BADUK_PAN_WIDGET_ATTRS:
            assert hasattr(stub, attr), f"missing attr: {attr}"


class TestPopupStub:
    """PopupStub の動作確認。"""

    def test_has_all_required_attrs(self):
        stub = make_popup_stub()
        for attr in POPUP_ATTRS:
            assert hasattr(stub, attr), f"missing attr: {attr}"

    def test_open_dismiss_sequence(self):
        """open → dismiss シーケンスが動作する。"""
        stub = make_popup_stub()
        stub.open()
        stub.dismiss()
        stub.open.assert_called_once()
        stub.dismiss.assert_called_once()


@pytest.mark.kivy_headless
class TestKivyStubsRegistry:
    """kivy_headless マーカー付き: スタブレジストリのまとめ確認。"""

    def test_all_stubs_creatable(self):
        """全 4 種のスタブがファクトリ経由で生成可能。"""
        for factory_name, factory in STUB_FACTORIES.items():
            stub = factory()
            assert stub is not None, f"factory {factory_name} returned None"

    def test_stub_factories_keys(self):
        """ファクトリ辞書が 4 種を網羅。"""
        assert set(STUB_FACTORIES.keys()) == {
            "ka_train_gui",
            "controls_panel",
            "baduk_pan_widget",
            "popup",
        }
