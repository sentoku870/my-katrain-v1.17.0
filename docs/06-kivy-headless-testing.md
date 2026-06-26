# Kivy ヘッドレステスト基盤（Phase 146）

> 最終更新: 2026-06-26
> 関連: `docs/01-roadmap.md` Phase 146、`docs/archive/plans/plan-phase-146.md`

このドキュメントは `KivyUnitTest` ベースクラスと 4 つの Kivy クラススタブ
（`KaTrainGuiStub` / `ControlsPanelStub` / `BadukPanWidgetStub` / `PopupStub`）
の使い方を説明します。

---

## 1. 目的

GUI 層 (`katrain/gui/`) のテストを、ウィンドウや GL コンテキストなしで
実行可能にします。CI 環境でも Kivy を import でき、テストが安定して
通るようにします。

---

## 2. クイックスタート

### 2.1 KivyUnitTest ベースクラス

```python
from tests.kivy_test_base import KivyUnitTest

class TestMyGuiFeature(KivyUnitTest):
    def test_something(self):
        from katrain.gui.badukpan import BadukPanWidget  # OK（ヘッドレス）
        widget = BadukPanWidget()
        widget.update_state()
        # ...
```

継承するだけで、各テストメソッドの前後で Kivy 用環境変数が
自動的にセット / リストアされます。

### 2.2 Kivy クラススタブ

```python
from tests.kivy_stubs import (
    make_ka_train_gui_stub,
    make_controls_panel_stub,
    make_baduk_pan_widget_stub,
    make_popup_stub,
)

def test_with_stub():
    gui = make_ka_train_gui_stub()
    gui.update_state("node")
    gui.update_state.assert_called_once_with("node")
```

`MagicMock` ベースで、テストに必要な API surface（属性名）が
スタブに自動的に設定されます。

### 2.3 既存パターンとの併用

`KivyUnitTest` は既存テスト（`MockKaTrainStub`, `MockEngine` 等）と
併用できます:

```python
from tests.conftest import MockKaTrainStub
from tests.kivy_test_base import KivyUnitTest

class TestGameLogic(KivyUnitTest):
    def test_with_katrain_stub(self):
        katrain = MockKaTrainStub()  # 既存
        # Kivy 環境変数は setup_method/teardown_method で自動管理
        # ...
```

---

## 3. 環境変数リファレンス

`KivyUnitTest` が自動設定する環境変数:

| 環境変数 | 効果 |
|---------|------|
| `KIVY_NO_ARGS=1` | Kivy 引数パーサを抑止 |
| `KIVY_NO_FILELOG=1` | ファイルログを抑止 |
| `KIVY_NO_CONSOLELOG=1` | コンソールログを抑止 |
| `KIVY_NO_ENV_CONFIG=1` | 環境設定ファイルの読込を抑止 |
| `KIVY_HEADLESS=1` | ヘッドレスモード |
| `KIVY_NO_WINDOW=1` | ウィンドウ作成を抑止 |
| `KIVY_GL_BACKEND=mock` | GL バックエンドをモック化 |
| `SDL_VIDEODRIVER=dummy` | SDL2 ダミードライバ |

これらは `setup_method` でセットされ、`teardown_method` で
**元に戻されます**。既存テストへの副作用はありません。

---

## 4. 4 つのスタブが提供する属性

### 4.1 `KaTrainGuiStub`

実体: `katrain/__main__.py:140 class KaTrainGui`

```python
("engine", "controls", "ivar", "game", "current_node", "comment_node",
 "players_info", "pondering", "_config",
 "update_state", "config", "log")
```

### 4.2 `ControlsPanelStub`

実体: `katrain/gui/controlspanel.py`

```python
("update_state", "set_active", "switch_control_panel", "new_game", "set_status")
```

### 4.3 `BadukPanWidgetStub`

実体: `katrain/gui/badukpan.py`

```python
("update_state", "draw_board", "set_handicap", "animate_stone_placement", "redraw")
```

### 4.4 `PopupStub`

実体: `kivy.uix.popup.Popup`

```python
("open", "dismiss", "content", "title", "size_hint", "auto_dismiss")
```

---

## 5. 設計上の注意点

### 5.1 派生クラスは opt-in

`KivyUnitTest` は **autouse フィクスチャではありません**。
既存テストファイル（125 件）に副作用はありません。
明示的に継承することで、意図的に Kivy ヘッドレスを有効化します。

### 5.2 sys.modules パッチは未使用

既存の `tests/test_engine_send_query_safety.py` パターン
（`with patch.dict("sys.modules", {"kivy.clock": mock_clock_module})`）
は Phase 146 では採用しません。環境変数のみでヘッドレス化できる
Kivy 2.3+ の機能を利用します。

### 5.3 スタブの drift リスク

スタブは MagicMock ベースで、実クラスの **公開メソッドのみ**
を再現します。実クラスの API が変更された場合、スタブの追従が
必要になることがあります。Phase 147 以降で新スタブを追加する
際に、適宜 `KA_TRAIN_GUI_ATTRS` などのタプルを更新してください。

### 5.4 core/gui 境界ルール

`KivyUnitTest` 基盤は `tests/` 配下にのみ存在します。
`katrain/` 配下から `tests/` への逆方向 import は禁止です
（`TestKivyHeadlessIsolation` で自動検証）。

---

## 6. 動作確認コマンド

```bash
# UTF-8 強制（Windows PowerShell）
$env:PYTHONUTF8 = "1"

# スモークテスト
uv run pytest tests/test_kivy_headless_smoke.py -v

# kivy_headless マーカーで実行
uv run pytest tests -v -m kivy_headless

# アーキテクチャテスト
uv run pytest tests/test_architecture.py::TestKivyHeadlessIsolation -v
```

---

## 7. Phase 147 への引き継ぎ事項

Phase 147 では以下を予定:

- orchestration.py / curator/ の Manager 経由テスト
- 4 スタブを使った統合テスト
- badukpan.py の draw 系メソッド
- 必要に応じて新スタブの追加（スタブ追加時は本ドキュメント §4 を更新）

新スタブの追加パターン:

```python
# tests/kivy_stubs.py
NEW_CLASS_ATTRS: tuple[str, ...] = (
    "method_a",
    "method_b",
)

def make_new_class_stub() -> MagicMock:
    return _make_stub(NEW_CLASS_ATTRS, name="NewClassStub")

STUB_FACTORIES["new_class"] = make_new_class_stub
```

---

## 8. 変更履歴

- 2026-06-26: 初版作成（Phase 146 完了）
