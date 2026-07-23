# Kivy ヘッドレステスト

最終更新: 2026-07-23（Phase D: 環境変数の正本化とskの縮小）

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

`tests/conftest.py` で **KivyMD stub ローダ呼び出しより前** に設定される、各変数の Kivy 2.3.1 における有効性:

| 環境変数 | 効果 | Kivy 2.3.1 で有効か |
|---------|------|--------------------|
| `KIVY_NO_CONFIG=1` | `~/.kivy` 自動生成・設定読込を抑止 | ◯（`kivy/__init__.py` で参照） |
| `KIVY_NO_ARGS=1` | CLI 引数パーサを抑止 | ◯（`kivy/__init__.py` で参照） |
| `KIVY_NO_FILELOG=1` | kivy.log ファイル出力を抑止 | ◯（`kivy/logger.py`） |
| `KIVY_NO_CONSOLELOG=1` | kivy.log コンソール出力を抑止 | ◯（`kivy/logger.py`） |
| `KIVY_NO_ENV_CONFIG=1` | `KCFG_*` 環境変数の上書きを抑止 | ◯（`kivy/config.py`） |
| `KIVY_GL_BACKEND=mock` | GL バックエンドをモックに切替 | ◯（`kivy.__init__` の `KIVY_<OPTION>` 規約 + `cgl_get_backend_name`） |
| `SDL_VIDEODRIVER=dummy` | SDL2 dummy video（display なし） | ◯（SDL2 が読む。Kivy ではなく SDL の責務） |
| `KIVY_HEADLESS=1` | （**Kivy は認識しない** ので設定不要） | × |
| `KIVY_NO_WINDOW=1` | （同上） | × |
| `PYTHONIOENCODING=utf-8` | .po / .mo / .kv の非ASCII文字を安全に取り扱う | ◯（標準 Python） |
| `PYTHONUTF8=1` | Windows / 一部イメージで UTF-8 を強制 | ◯（標準 Python） |

主なポイント:

- **`SDL_VIDEODRIVER=dummy` は `DISPLAY` が未設定のときだけ設定する**。CI は `xvfb-run` 配下なので `DISPLAY` が立ち、`xvfb-run` の X サーバを浪費しないよう dummy にフォールバックしない（`conftest.py` で実装）。
- `KIVY_HEADLESS` / `KIVY_NO_WINDOW` は読みやすさのために残してある記述があるが、Kivy 2.3.1 はこれらを **読まない**。`kivy_test_base.py` のコメントの互換目的のためのみ。
- `KIVY_NO_CONFIG=1` が一番重要。これにより `os.mkdir('~/.kivy')` の副作用が出なくなる。

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

### CI での運用（Phase D）

- CI は `xvfb-run -a` で実 DISPLAY を提供するため、SDL 経由でも Kivy は実 GL モジュールの小さいサイズで初期化できる。
- `tests/conftest.py` で `DISPLAY` 設定時は SDL dummy を **抑止** する分岐が入っている。
- 古くは「CI では KaTrainGui の import で OOM する」という想定で `_CI_SKIP` が導入されていたが、Phase D で **「Kivy が import 不可かどうか」だけ** を見るガード `importlib.util.find_spec("kivy")` に縮小済み。

## 5. 動作確認コマンド

```bash
# スモークテスト
uv run pytest tests/test_kivy_headless_smoke.py -v

# kivy_headless マーカーで実行
uv run pytest tests -v -m kivy_headless

# 境界テスト
uv run pytest tests/test_architecture.py::TestKivyHeadlessIsolation -v

# ヘッドレスの Kivy 動作を最終確認 (xvfb-run 利用時は省略可)
xvfb-run -a uv run pytest tests/test_game_report_popup.py
```

