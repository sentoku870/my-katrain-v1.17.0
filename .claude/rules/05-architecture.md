# アーキテクチャルール（Architecture Rules）

> このファイルは myKatrain のアーキテクチャ制約を定義します。
> Phase 20 で確立された依存方向ルールを強制するためのガイドラインです。

---

## 1. レイヤー構造

myKatrain は以下のレイヤー構造を持ちます:

```
┌─────────────────────────────────────┐
│           GUI 層 (gui/)              │  ← Kivy依存
├─────────────────────────────────────┤
│          Core 層 (core/)             │  ← Kivy非依存
├─────────────────────────────────────┤
│         Common 層 (common/)          │  ← 共有定数・ユーティリティ
└─────────────────────────────────────┘
```

---

## 2. 依存方向ルール

### 2.1 許可される依存

| From | To | 許可 |
|------|-----|:----:|
| gui/ | core/ | ✅ |
| gui/ | common/ | ✅ |
| core/ | common/ | ✅ |
| common/ | (標準ライブラリのみ) | ✅ |

### 2.2 禁止される依存

| From | To | 禁止理由 |
|------|-----|----------|
| core/ | gui/ | GUI依存をcore層から分離 |
| core/ | kivy* | Kivy依存をcore層から分離 |
| common/ | gui/ | 循環依存防止 |
| common/ | core/ | 循環依存防止 |

---

## 3. 禁止インポート（core層）

core層では以下のモジュールをインポートしてはいけません:

- `kivy`
- `kivymd`
- `kivy_garden`
- `katrain.gui`

### 3.1 例外（許可リスト）

一部のインポートは許可リストで管理されています:

**ファイル**: `tests/fixtures/kivy_import_allowlist.json`

```json
{
  "entries": {
    "core/base_katrain.py|kivy": {
      "reason": "Config for Kivy logging",
      "removal_pr": "PR #139"
    }
  }
}
```

### 3.2 許可リストのポリシー

**DELETE-ONLY（削除専用）**:
- 新規エントリの追加は禁止
- 既存エントリの削除のみ許可
- テスト（`test_allowlist_is_delete_only`）で強制

---

## 4. テストによる強制

`tests/test_architecture.py` で以下を検証:

### 4.1 TestKivyIsolation

| テスト | 検証内容 |
|--------|----------|
| `test_no_forbidden_imports_in_core` | core層がKivy/GUIをインポートしていないこと |
| `test_allowlist_is_delete_only` | 許可リストに新規エントリが追加されていないこと |
| `test_allowlist_entries_still_exist` | 許可リストのエントリがまだ必要であること（stale検出） |

### 4.2 AllImportCollector

AST解析で全インポートを収集:
- 関数内の遅延インポートも検出
- TYPE_CHECKINGブロックはスキップ
- 相対インポートを絶対パスに解決

---

## 5. 代替パターン

Kivy依存を避けるための代替パターン:

### 5.1 プラットフォーム判定

**Before (NG)**:
```python
from kivy.utils import platform
if platform == "win":
    ...
```

**After (OK)**:
```python
from katrain.common.platform import get_platform
if get_platform() == "win":
    ...
```

### 5.2 設定ストレージ

**Before (NG)**:
```python
from kivy.storage.jsonstore import JsonStore
store = JsonStore("config.json")
```

**After (OK)**:
```python
from katrain.common.config_store import JsonFileConfigStore
store = JsonFileConfigStore("config.json")
```

### 5.3 言語管理（i18n）

**Before (NG)**:
```python
# core/lang.py
from kivy._event import Observable
class Lang(Observable):
    ...
```

**After (OK)**:
```python
# core/lang.py（Kivy非依存）
class Lang:
    def add_change_callback(self, callback): ...
    def _notify_change(self): ...

# gui/lang_bridge.py（Kivyブリッジ）
from kivy.event import EventDispatcher
class KivyLangBridge(EventDispatcher):
    ...
```

---

## 6. 新規コードの追加時

### 6.1 core層にコードを追加する場合

1. Kivy関連のインポートを使用しない
2. `katrain.gui` をインポートしない
3. TYPE_CHECKING内でのみ型ヒント用インポートを許可

### 6.2 テストの実行

```powershell
# アーキテクチャテストを実行
uv run pytest tests/test_architecture.py -v
```

---

## 7. 変更履歴

- 2026-01-16: v1.0 作成（Phase 20完了）
