"""Kivy ヘッドレステスト基盤（Phase 146）

gui/ 層のテストをヘッドレス環境（CI、メモリ内のモック）で行うための
基底クラス。

設計判断:
    - autouse フィクスチャにはしない（既存テストへの副作用を避ける）
    - 環境変数パッチはメソッド単位で自動復元
    - 派生クラスは明示的に KivyUnitTest を継承して opt-in
    - sys.modules 経由の Kivy スタブ注入は ``kivy_stubs.py`` で提供

使い方::

    class TestBadukPan(KivyUnitTest):
        def test_draw_board(self):
            from katrain.gui.badukpan import BadukPanWidget
            widget = BadukPanWidget()  # ヘッドレスで import 可能
            widget.update_state()
            ...

環境変数の根拠:
    - ``KIVY_NO_ARGS``: Kivy 引数パーサ抑止
    - ``KIVY_NO_FILELOG`` / ``KIVY_NO_CONSOLELOG``: ログ抑止
    - ``KIVY_NO_ENV_CONFIG``: 環境設定読込抑止
    - ``KIVY_HEADLESS``: ヘッドレスモード
    - ``KIVY_NO_WINDOW``: ウィンドウ作成抑止
    - ``KIVY_GL_BACKEND=mock``: GL バックエンドモック化
    - ``SDL_VIDEODRIVER=dummy``: SDL2 ダミードライバ
"""

from __future__ import annotations

import os
from typing import ClassVar


class KivyUnitTest:
    """Kivy ヘッドレステスト基底クラス。

    派生クラスの各テストメソッド実行前後で Kivy 関連の環境変数を
    セット / リストアする。これにより、``KIVY_GL_BACKEND=mock`` と
    ``SDL_VIDEODRIVER=dummy`` により、ウィンドウや GL コンテキストを
    作成せずに Kivy を import できる。

    既存の ``MockKaTrainStub`` (conftest.py) パターンと併用可能。
    """

    KIVY_ENV_VARS: ClassVar[dict[str, str]] = {
        "KIVY_NO_ARGS": "1",
        "KIVY_NO_FILELOG": "1",
        "KIVY_NO_CONSOLELOG": "1",
        "KIVY_NO_ENV_CONFIG": "1",
        "KIVY_HEADLESS": "1",
        "KIVY_NO_WINDOW": "1",
        "KIVY_GL_BACKEND": "mock",
        "SDL_VIDEODRIVER": "dummy",
    }

    def setup_method(self, method):  # noqa: ARG002
        """pytest から自動呼出し。環境変数を保存して Kivy 用に上書き。"""
        self._original_env = {k: os.environ.get(k) for k in self.KIVY_ENV_VARS}
        os.environ.update(self.KIVY_ENV_VARS)

    def teardown_method(self, method):  # noqa: ARG002
        """pytest から自動呼出し。環境変数を元に戻す。"""
        for key, prev in self._original_env.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
