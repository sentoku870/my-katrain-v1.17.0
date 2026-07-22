# Kivy ヘッドレステスト

最終更新: 2026-07-21

GUI 層 (`katrain/gui/`) のテストを、ウィンドウや GL コンテキストなしで実行可能にする基盤。CI でも Kivy 安定して動作する。

## 1. クイックスタート

### KivyUnitTest を使う

```python
from tests.kivy_test_base import KivyUnitTest

class TestMyGuiFeature(KivyUnitTest):
    def test_something(self):
        from katrain.gui.badukpan import BadukPanWidget
        widget = BadukPanWidget()  # ヘッドレスで OK
        widget.update_state()
```

継承するだけで、各メソッドの前後で Kivy 用環境変数が自動セット / リストアされる。

### クラススタブを使う

```python
from tests.kivy_stubs import (
    make_ka_train_gui_stub,
    make_controls_panel_stub,
    make_baduk_pan_widget_stub,
    make_popup_stub,
)

def test_with_stub(gui):
    gui.update_state("node")
    gui.update_state.assert_called_once_with("node")
```

`MagicMock` ベース。テストに必要な公開属性が自動的に設定される。

## 2. 自動設定される環境変数

| 環境変数 | 効果 |
|---------|------|
| `KIVY_NO_ARGS=1` | 引数パーサ抑止 |
| `KIVY_NO_FILELOG=1` | ファイルログ抑止 |
| `KIVY_NO_CONSOLELOG=1` | コンソールログ抑止 |
| `KIVY_NO_ENV_CONFIG=1` | 環境設定ファイル読込抑止 |
| `KIVY_HEADLESS=1` | ヘッドレスモード |
| `KIVY_NO_WINDOW=1` | ウィンドウ作成抑止 |
| `KIVY_GL_BACKEND=mock` | GL バックエンドをモック化 |
| `SDL_VIDEODRIVER=dummy` | SDL2 ダミードライバ |

`setup_method` でセット → `teardown_method` で **元に戻る**。他テストへの副作用なし。

## 3. 提供スタブ

| スタブ | 実体 | 公開属性 |
|--------|------|---------|
| `KaTrainGuiStub` | `katrain/__main__.py:140 class KaTrainGui` | `engine`, `controls`, `ivar`, `game`, `current_node`, `comment_node`, `players_info`, `pondering`, `_config`, `update_state`, `config`, `log` |
| `ControlsPanelStub` | `katrain/gui/controlspanel.py` | `update_state`, `set_active`, `switch_control_panel`, `new_game`, `set_status` |
| `BadukPanWidgetStub` | `katrain/gui/badukpan.py` | `update_state`, `draw_board`, `set_handicap`, `animate_stone_placement`, `redraw` |
| `PopupStub` | `kivy.uix.popup.Popup` | `open`, `dismiss`, `content`, `title`, `size_hint`, `auto_dismiss` |

## 4. 設計上の注意点

### opt-in ベース

`KivyUnitTest` は **autouse フィクスチャではない**。明示的に継承することで Kivy ヘッドレスを有効化する。既存テストファイルへの副作用なし。

### core / gui 境界ルール

`tests/` 配下にのみ存在。`katrain/` から `tests/` への逆方向 import は禁止（`TestKivyHeadlessIsolation` で自動検証）。

### スタブの drift リスク

実クラスの **公開メソッドのみ** 再現する MagicMock ベース。実クラスの API が変わった場合、スタブ追従が必要。新規スタブ追加時は `kivy_stubs.py` の `*_ATTRS` タプルを更新する。

## 5. 動作確認コマンド

```powershell
$env:PYTHONUTF8 = "1"
```

```bash
# スモークテスト
uv run pytest tests/test_kivy_headless_smoke.py -v

# kivy_headless マーカーで実行
uv run pytest tests -v -m kivy_headless

# 境界テスト
uv run pytest tests/test_architecture.py::TestKivyHeadlessIsolation -v
```
