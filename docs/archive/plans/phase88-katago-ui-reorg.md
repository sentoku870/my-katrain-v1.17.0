# Phase 88: KataGo Settings UI Reorganization + human-like Exclusivity

## 概要

**修正レベル**: Lv3-4（複数ファイル、UI + Config + i18n）
**Git ブランチ**: `feature/2026-01-30-phase88-katago-ui-reorg`

### 目的
1. **human-like排他制御**: ドロップダウンから専用トグル（ON/OFF）に変更
2. **設定UI 3モード化**: 自動 / 標準 / 高機能
3. **意味ラベル**: ファイルパスではなく「軽量/標準/強力」で表示

### スコープ（Phase 88）
**含む**:
- 3モードUI切替（自動/標準/高機能）
- human-likeトグル（ON/OFF排他制御）
- モデル意味ラベル表示（現在選択中のモデルをラベル化）
- 詳細アコーディオン（パスを畳む）

**含まない（Phase 89以降）**:
- 自動モードのテスト解析機能
- OpenCL→CPUフォールバック
- 診断ファイル自動出力
- 軽量モデル同梱/DL機能
- ラベルによるモデル切替（ディレクトリスキャン）

---

## 設計方針

### 1. human-like排他制御（UI-onlyアプローチ）

**方針**: engine.pyは変更しない。UIがconfigを正規化することで排他を実現。

**トグルON+パス空の動作（決定事項）**:
> **Option A採用: トグルを強制OFFにする**
> - トグルON操作時、パスが空なら即座にOFFに戻し警告表示
> - 保存時もON+空パスなら強制OFFで保存
> - ON状態は有効パス存在時のみ永続化される

| 操作 | パス状態 | 結果 |
|------|----------|------|
| トグルON | パス空、last_pathあり | last_pathを復元してON維持 |
| トグルON | パス空、last_pathなし | 警告表示、トグルを即座にOFFに戻す |
| 保存 | ON + パス空 | 強制OFF + 警告、`humanlike_model=""`で保存 |
| 保存 | ON + パスあり | そのまま保存 |
| 保存 | OFF | `humanlike_model=""`、パスは`humanlike_model_last`に退避 |

**engine.pyの動作（変更なし）**:
- 場所: `KataGoEngine.__init__`内の「Add human model to command if provided」ブロック
- 判定: `if config.get("humanlike_model", ""):` で真偽判定
- `humanlike_model`が空文字/falsy → `-human-model`フラグなし
- `humanlike_model`が有効パス → `-human-model`フラグあり
- **これがUI-onlyアプローチの前提条件**（engine.py変更不要の根拠）

### 2. 意味ラベル表示（Phase 88スコープ）

**方針**: Phase 88では「現在選択中のモデルをラベル表示」のみ。ラベルによるモデル切替は行わない。

| Phase 88でやること | Phase 89以降でやること |
|-------------------|----------------------|
| 現在のモデルパスを分類してラベル表示 | ディレクトリスキャンで利用可能モデル一覧取得 |
| 「軽量」「標準」「強力」「その他」のラベル | ラジオボタンでカテゴリ選択→モデル自動切替 |
| 不明モデルはファイル名表示 | 軽量モデル同梱/DL |

### 3. ラベルのi18n分離

**model_labels.py**: 強度カテゴリキーのみ返す（文字列なし）

**不明モデルの表示**: プレースホルダー付きi18n文字列を使用
- `model:unknown_with_name` = `"Other: {name}"` / `"その他: {name}"`
- 文字列結合は行わない（ロケール間の句読点・スペース問題を回避）

### 4. 設定永続化の確認

**調査結果**: config保存は`JsonFileConfigStore.put(k, **config[k])`で全セクションをそのまま保存。スキーマ検証やキーのフィルタリングはない。

**結論**: `self._config["engine"]["humanlike_model_last"]`に値を設定し、`save_config("engine")`を呼べば新キーも保存される。追加の保存ロジック変更は不要。

---

## 変更ファイル一覧

| 順序 | ファイル | 変更内容 | 行数目安 |
|:----:|----------|----------|:--------:|
| 1 | `katrain/common/model_labels.py` | **新規**: 強度カテゴリ判定（i18nキー返却のみ） | ~40 |
| 2 | `katrain/common/humanlike_config.py` | **新規**: 正規化ロジック（純粋関数、Kivy非依存） | ~40 |
| 3 | `katrain/config.json` | `humanlike_model_last` 追加 | ~2 |
| 4 | `katrain/gui/popups.py` | モード切替・トグル・正規化呼び出し | ~100 |
| 5 | `katrain/popups.kv` | UI再構成（3モード + トグル） | ~150 |
| 6 | `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | 英語翻訳追加 | ~35 |
| 7 | `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | 日本語翻訳追加 | ~35 |
| 8 | `tests/test_model_labels.py` | **新規**: カテゴリ判定テスト | ~40 |
| 9 | `tests/test_humanlike_config.py` | **新規**: 正規化ロジックテスト（CI、GUI不要） | ~50 |

---

## 実装詳細

### Step 1: model_labels.py（共通層、Kivy非依存）

```python
# katrain/common/model_labels.py
"""Model strength classification for KataGo models.

Returns i18n keys only - no user-facing strings in this module.
"""
import ntpath
import os
import posixpath
import re
from typing import Literal

StrengthCategory = Literal["light", "standard", "strong", "unknown"]

_STRENGTH_PATTERNS = [
    (r"b10c128", "light"),
    (r"b18c384", "standard"),
    (r"b28|b40", "strong"),
]


def _cross_platform_basename(path: str) -> str:
    """Extract basename from path, handling both Windows and Unix separators.

    os.path.basename("C:\\models\\file.bin") returns the full string on Linux
    because Linux doesn't recognize backslash as separator.

    This function handles:
    - Windows paths on any OS (backslash)
    - Unix paths on any OS (forward slash)
    - Mixed paths (uses rightmost separator)
    """
    if not path:
        return ""
    # If path contains backslash, use ntpath (Windows rules)
    if "\\" in path:
        return ntpath.basename(path)
    # Otherwise use posixpath (works for forward slash on all platforms)
    return posixpath.basename(path)


def classify_model_strength(model_path: str) -> StrengthCategory:
    """Classify model by strength based on filename pattern."""
    if not model_path:
        return "unknown"
    basename = _cross_platform_basename(model_path)
    for pattern, category in _STRENGTH_PATTERNS:
        if re.search(pattern, basename, re.IGNORECASE):
            return category
    return "unknown"


def get_model_i18n_key(model_path: str) -> str:
    """Get i18n key for model label."""
    category = classify_model_strength(model_path)
    return f"model:{category}"


def get_model_basename(model_path: str) -> str:
    """Get basename for display when model is unknown.

    Returns empty string if path is empty (caller should handle).
    """
    return _cross_platform_basename(model_path)
```

### Step 2: humanlike_config.py（共通層、Kivy非依存）

```python
# katrain/common/humanlike_config.py
"""Human-like config normalization logic.

Pure functions with no Kivy dependencies for CI-safe testing.
"""


def normalize_humanlike_config(
    toggle_on: bool,
    current_path: str,
    last_path: str,
) -> tuple[str, str, bool]:
    """Normalize humanlike config for saving.

    Args:
        toggle_on: Whether human-like toggle is ON
        current_path: Current humanlike_model value
        last_path: Previous humanlike_model_last value

    Returns:
        (humanlike_model, humanlike_model_last, effective_toggle_on) tuple

    Rules (Option A: Force OFF when path empty):
        - toggle ON + path valid: (path, path, True)
        - toggle ON + path empty: ("", last_path, False) ← 強制OFF
        - toggle OFF + path valid: ("", path, False) ← パス退避
        - toggle OFF + path empty: ("", last_path, False)
    """
    if toggle_on:
        if current_path:
            return (current_path, current_path, True)
        else:
            # ON but empty path -> force OFF
            return ("", last_path, False)
    else:
        # OFF: clear model, preserve last
        new_last = current_path if current_path else last_path
        return ("", new_last, False)
```

### Step 3: config.json

追加するキー（JSONにはコメント不可のため、ここで説明）:
- `engine.humanlike_model_last`: トグルOFF時のパス退避先（デフォルト: `""`）

```json
{
    "engine": {
        "humanlike_model": "",
        "humanlike_model_last": ""
    }
}
```

### Step 4: popups.py（GUI層）

**必須インポート**:
```python
import os  # os.path.exists() に必要

from katrain.common.humanlike_config import normalize_humanlike_config
from katrain.common.model_labels import classify_model_strength, get_model_basename
```

**実装時の注意**: プロパティ/メソッド名は既存ConfigPopupコードに合わせる。
以下は擬似コード。実際の名前（`humanlike_model_path`, `show_warning`等）は実装時に確認・調整。

**Kivyプロパティとハンドラのバインディング**:
```python
# 追加プロパティ
current_mode = StringProperty("standard")  # "automatic", "standard", "advanced"
humanlike_enabled = BooleanProperty(False)

# Option A: Kivy自動コールバック名を使用（推奨）
# Kivyは on_<property_name> を自動的に呼び出す
def on_humanlike_enabled(self, instance, value: bool):
    """Kivy auto-callback when humanlike_enabled changes."""
    self._handle_humanlike_toggle(value)

# Option B: KVで明示的にバインド
# popups.kv で: on_active: root._handle_humanlike_toggle(self.active)
```

**トグルハンドラ（コア実装）**:
```python
def _handle_humanlike_toggle(self, enabled: bool):
    """Handle human-like toggle change.

    When forcing OFF, always clear humanlike_model_path to avoid stale state.
    """
    if enabled:
        last = self.katrain.config("engine/humanlike_model_last", "")
        if last and os.path.exists(last):
            self.humanlike_model_path = last
            self.humanlike_enabled = True
        elif last:
            # File missing - force OFF and clear path
            self.show_warning(i18n._("humanlike:path_not_found"))
            self.humanlike_enabled = False
            self.humanlike_model_path = ""  # Clear stale path
        else:
            # No previous path - force OFF
            self.show_warning(i18n._("humanlike:no_path_warning"))
            self.humanlike_enabled = False
            self.humanlike_model_path = ""  # Ensure clean state
    else:
        self.humanlike_enabled = False
        # Note: Don't clear path here - save_settings will preserve it in last_path

def save_settings(self):
    """Save settings with normalization.

    CRITICAL: After normalization, sync UI state to match persisted config.
    This prevents UI showing ON while config was saved OFF.
    """
    model, last, effective_on = normalize_humanlike_config(
        self.humanlike_enabled,
        self.humanlike_model_path,
        self.katrain.config("engine/humanlike_model_last", "")
    )

    # Persist to config
    self.katrain._config["engine"]["humanlike_model"] = model
    self.katrain._config["engine"]["humanlike_model_last"] = last
    self.katrain.save_config("engine")

    # MUST sync UI state to match persisted config
    if self.humanlike_enabled and not effective_on:
        self.show_warning(i18n._("humanlike:forced_off"))
    self.humanlike_enabled = effective_on  # UI == config
    self.humanlike_model_path = model       # UI == config

def get_model_display_text(self, model_path: str) -> str:
    """Get localized display text for model.

    Handles empty path gracefully with model:none fallback.
    """
    if not model_path:
        return i18n._("model:none")

    category = classify_model_strength(model_path)
    if category == "unknown":
        basename = get_model_basename(model_path)
        if not basename:
            return i18n._("model:none")
        # Use placeholder form: "Other: {name}"
        return i18n._("model:unknown_with_name").format(name=basename)
    return i18n._(f"model:{category}")
```

### Step 5: popups.kv（UI層）

**言語切替追従（既存パターン使用）**:
```kivy
<ConfigPopup>:
    lang_change_tracking: i18n._('')
    # ... UI定義 ...
```

**UI構造**:
```
+-----------------------------------------------------------+
| KataGo Settings                                            |
+-----------------------------------------------------------+
| Mode: [ 自動 ] [ 標準 ] [ 高機能 ]                          |
+-----------------------------------------------------------+
| [自動モード時] ※Phase 88では暫定表示                        |
| 「推奨設定を使用中」                                        |
| (テスト解析ボタンはPhase 89で追加)                         |
+-----------------------------------------------------------+
| [標準モード時]                                             |
| 現在のモデル: 標準（推奨）                                  |
|              ※表示のみ、切替は高機能モードで               |
|                                                            |
| [ ] human-like モード（実験）                               |
|     OFF時: 通常の解析（推奨）                               |
|     ON時:  人間らしい傾向を優先 + パス入力欄                |
+-----------------------------------------------------------+
| [高機能モード時]                                           |
| 既存のフルUI（パス入力等）+ human-likeトグル               |
+-----------------------------------------------------------+
| ▶ 詳細（クリックで展開）                                   |
|   エンジンパス: /path/to/katago  [開く] [コピー]           |
|   モデルパス: /path/to/model.bin.gz  [開く] [コピー]       |
+-----------------------------------------------------------+
```

### Step 6-7: i18n翻訳

**英語 (`katrain/i18n/locales/en/LC_MESSAGES/katrain.po`)**:
```po
# Phase 88: Settings Mode
msgid "mode:automatic"
msgstr "Automatic"

msgid "mode:standard"
msgstr "Standard"

msgid "mode:advanced"
msgstr "Advanced"

msgid "mode:automatic:desc"
msgstr "Using recommended settings"

# Phase 88: Model Labels (display only)
msgid "model:current"
msgstr "Current model"

msgid "model:light"
msgstr "Light (fast)"

msgid "model:standard"
msgstr "Standard (recommended)"

msgid "model:strong"
msgstr "Strong (slow)"

msgid "model:unknown"
msgstr "Other"

msgid "model:unknown_with_name"
msgstr "Other: {name}"

msgid "model:none"
msgstr "(No model selected)"

# Phase 88: human-like Toggle
msgid "humanlike:toggle_label"
msgstr "Enable human-like mode (experimental)"

msgid "humanlike:status_off"
msgstr "Normal analysis (recommended)"

msgid "humanlike:status_on"
msgstr "Human-like tendencies active (accuracy may vary)"

msgid "humanlike:no_path_warning"
msgstr "Please select a human-like model file first"

msgid "humanlike:path_not_found"
msgstr "Previous human-like model file not found"

msgid "humanlike:forced_off"
msgstr "Human-like mode disabled (no valid model path)"

# Phase 88: Details
msgid "details:title"
msgstr "Details"
```

**日本語 (`katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`)**:
```po
# Phase 88: Settings Mode
msgid "mode:automatic"
msgstr "自動"

msgid "mode:standard"
msgstr "標準"

msgid "mode:advanced"
msgstr "高機能"

msgid "mode:automatic:desc"
msgstr "推奨設定を使用中"

# Phase 88: Model Labels
msgid "model:current"
msgstr "現在のモデル"

msgid "model:light"
msgstr "軽量（高速）"

msgid "model:standard"
msgstr "標準（推奨）"

msgid "model:strong"
msgstr "強力（重い）"

msgid "model:unknown"
msgstr "その他"

msgid "model:unknown_with_name"
msgstr "その他: {name}"

msgid "model:none"
msgstr "（モデル未選択）"

# Phase 88: human-like Toggle
msgid "humanlike:toggle_label"
msgstr "人間らしいモード（実験）を有効にする"

msgid "humanlike:status_off"
msgstr "通常の解析（推奨）"

msgid "humanlike:status_on"
msgstr "人間らしい傾向を優先（精度が変わる可能性）"

msgid "humanlike:no_path_warning"
msgstr "human-likeモデルファイルを先に選択してください"

msgid "humanlike:path_not_found"
msgstr "以前のhuman-likeモデルファイルが見つかりません"

msgid "humanlike:forced_off"
msgstr "human-likeモードを無効化しました（有効なパスなし）"

# Phase 88: Details
msgid "details:title"
msgstr "詳細"
```

**msgid衝突チェック（確認済み）**:
```powershell
# 既存の msgid を検索（Phase 88で使用予定のプレフィックス）
Select-String -Path "katrain/i18n/**/*.po" -Pattern 'msgid "model:|msgid "mode:|msgid "humanlike:|msgid "details:'
# 結果: 該当なし → 新規msgid追加は安全
```

**i18nコンパイル手順**:
```powershell
# .po更新後に実行（リポジトリルートで）
python i18n.py
```

---

## テスト計画

### CI実行（自動） - GUI不要、Kivy非依存

テストディレクトリ: `tests/`

**CIコマンド**（CLAUDE.mdで定義されている標準コマンドに準拠）:
```powershell
# Phase 88 関連テストのみ
uv run pytest tests/test_model_labels.py tests/test_humanlike_config.py -v

# 全テスト（既存テストとの整合確認）
uv run pytest tests -v

# 失敗時に即停止（デバッグ用）
uv run pytest tests/test_model_labels.py tests/test_humanlike_config.py -x -v
```

**注意**: リポジトリのCI環境は`uv run pytest`を使用（CLAUDE.md参照）。

**tests/test_model_labels.py**:
```python
"""Tests for katrain.common.model_labels module.

CI-safe: No Kivy imports.
"""
import pytest
from katrain.common.model_labels import (
    classify_model_strength,
    get_model_i18n_key,
    get_model_basename,
)


class TestClassifyModelStrength:
    def test_light_model(self):
        assert classify_model_strength("kata1-b10c128-xxx.bin.gz") == "light"

    def test_standard_model(self):
        assert classify_model_strength("kata1-b18c384nbt-xxx.bin.gz") == "standard"

    def test_strong_model_b28(self):
        assert classify_model_strength("kata1-b28c512-xxx.bin.gz") == "strong"

    def test_strong_model_b40(self):
        assert classify_model_strength("kata1-b40c256-xxx.bin.gz") == "strong"

    def test_unknown_model(self):
        assert classify_model_strength("custom-model.bin.gz") == "unknown"

    def test_empty_path(self):
        assert classify_model_strength("") == "unknown"

    def test_windows_full_path(self):
        assert classify_model_strength(r"C:\models\kata1-b18c384.bin.gz") == "standard"

    def test_unix_full_path(self):
        assert classify_model_strength("/home/user/kata1-b10c128.bin.gz") == "light"

    def test_case_insensitive(self):
        assert classify_model_strength("KATA1-B18C384.BIN.GZ") == "standard"


class TestGetModelI18nKey:
    def test_light_key(self):
        assert get_model_i18n_key("kata1-b10c128.bin.gz") == "model:light"

    def test_unknown_key(self):
        assert get_model_i18n_key("unknown.bin.gz") == "model:unknown"

    def test_empty_path_key(self):
        assert get_model_i18n_key("") == "model:unknown"


class TestGetModelBasename:
    """Cross-platform basename tests.

    These tests verify Windows paths work correctly on Linux CI.
    os.path.basename("C:\\models\\file.bin") returns the whole string on Linux,
    so we use _cross_platform_basename internally.
    """

    def test_windows_path_on_any_os(self):
        # This must pass on Linux CI (backslash handling)
        assert get_model_basename(r"C:\models\kata1.bin.gz") == "kata1.bin.gz"

    def test_windows_path_deep_nesting(self):
        assert get_model_basename(r"D:\foo\bar\baz\model.bin") == "model.bin"

    def test_unix_path(self):
        assert get_model_basename("/home/user/kata1.bin.gz") == "kata1.bin.gz"

    def test_unix_path_deep_nesting(self):
        assert get_model_basename("/a/b/c/d/model.bin") == "model.bin"

    def test_filename_only(self):
        assert get_model_basename("kata1.bin.gz") == "kata1.bin.gz"

    def test_empty_path(self):
        assert get_model_basename("") == ""

    def test_mixed_separators(self):
        # Forward slash after backslash - uses rightmost separator
        assert get_model_basename(r"C:\models/subdir/file.bin") == "file.bin"


class TestCrossPlatformInClassify:
    """Verify classify_model_strength uses cross-platform basename."""

    def test_windows_path_classification(self):
        # Must work on Linux CI
        assert classify_model_strength(r"C:\models\kata1-b18c384.bin.gz") == "standard"
        assert classify_model_strength(r"D:\foo\bar\kata1-b10c128.bin") == "light"
```

**tests/test_humanlike_config.py**:
```python
"""Tests for katrain.common.humanlike_config module.

CI-safe: No Kivy imports, pure function testing.
"""
import pytest
from katrain.common.humanlike_config import normalize_humanlike_config


class TestNormalizeHumanlikeConfig:
    """Test normalize_humanlike_config with Option A (force OFF when path empty)."""

    def test_toggle_on_with_valid_path(self):
        """ON + valid path -> keep ON, sync both paths."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="/path/to/humanlike.bin.gz",
            last_path=""
        )
        assert model == "/path/to/humanlike.bin.gz"
        assert last == "/path/to/humanlike.bin.gz"
        assert effective_on is True

    def test_toggle_on_empty_path_forces_off(self):
        """ON + empty path -> force OFF (Option A behavior)."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="",
            last_path="/previous/path.bin.gz"
        )
        assert model == ""
        assert last == "/previous/path.bin.gz"
        assert effective_on is False

    def test_toggle_on_empty_both_paths(self):
        """ON + both paths empty -> force OFF."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=True,
            current_path="",
            last_path=""
        )
        assert model == ""
        assert last == ""
        assert effective_on is False

    def test_toggle_off_with_current_path(self):
        """OFF + current path -> clear model, save to last."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="/path/to/humanlike.bin.gz",
            last_path=""
        )
        assert model == ""
        assert last == "/path/to/humanlike.bin.gz"
        assert effective_on is False

    def test_toggle_off_preserves_last(self):
        """OFF + no current path -> preserve existing last."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="",
            last_path="/previous/path.bin.gz"
        )
        assert model == ""
        assert last == "/previous/path.bin.gz"
        assert effective_on is False

    def test_toggle_off_both_empty(self):
        """OFF + both empty -> both stay empty."""
        model, last, effective_on = normalize_humanlike_config(
            toggle_on=False,
            current_path="",
            last_path=""
        )
        assert model == ""
        assert last == ""
        assert effective_on is False


class TestDesignInvariants:
    """Document design invariants for engine.py compatibility.

    These tests verify normalization output satisfies engine.py requirements:
    - humanlike_model="" => engine does NOT add -human-model flag
    - humanlike_model=valid_path => engine adds -human-model flag

    The actual engine.py behavior is NOT tested here (requires heavy imports).
    See manual test checklist for engine verification.
    """

    def test_off_state_produces_empty_model(self):
        """OFF state always produces empty humanlike_model."""
        model, _, _ = normalize_humanlike_config(False, "/any/path.bin", "")
        assert model == ""

    def test_on_without_path_produces_empty_model(self):
        """ON without valid path produces empty humanlike_model (force OFF)."""
        model, _, effective_on = normalize_humanlike_config(True, "", "/last.bin")
        assert model == ""
        assert effective_on is False

    def test_on_with_path_produces_nonempty_model(self):
        """ON with valid path produces non-empty humanlike_model."""
        model, _, effective_on = normalize_humanlike_config(True, "/valid.bin", "")
        assert model == "/valid.bin"
        assert effective_on is True
```

### 手動テスト

| テスト項目 | 確認内容 |
|-----------|---------|
| 起動確認 | `python -m katrain` でクラッシュなし |
| モード切替 | 自動/標準/高機能の表示切替 |
| human-likeトグルON（パスなし） | 警告表示、トグルがOFFに戻る |
| human-likeトグルON（last_pathあり） | パス復元、トグルON維持 |
| 意味ラベル | 現在のモデルが正しくラベル表示 |
| 不明モデル | 「その他: {filename}」と表示（プレースホルダー使用） |
| 言語切替 | EN↔JP切替で新ラベルが更新される |
| 設定保存 | トグル状態とパスが正しく永続化 |
| **engine.py検証** | humanlike_model=""時、KataGoコマンドに`-human-model`なし |
| **engine.py検証** | humanlike_model=有効パス時、KataGoコマンドに`-human-model`あり |
| **UI/config同期** | 保存後、UIのトグル状態が保存されたconfig状態と一致する |

### engine.py検証の具体的手順

KataGoコマンドラインを確認するには:

1. **KaTrainのコンソール出力を確認**:
   ```powershell
   $env:PYTHONUTF8 = "1"
   python -m katrain 2>&1 | Tee-Object -FilePath katrain_log.txt
   ```
   ログに `Starting kata analysis` や実行コマンドが出力される

2. **engine.pyにデバッグ出力を一時追加**（開発時のみ）:
   ```python
   # KataGoEngine.__init__ 内、self.command = ... の直後
   print(f"[DEBUG] KataGo command: {self.command}")
   ```

3. **確認項目**:
   - `humanlike_model=""` の場合:
     コマンドに `-human-model` が**含まれない**ことを確認
   - `humanlike_model="/path/to/humanlike.bin"` の場合:
     コマンドに `-human-model "/path/to/humanlike.bin"` が**含まれる**ことを確認

4. **デバッグ出力の削除**:
   テスト完了後、`[DEBUG]` 行を削除（`.claude/rules/03-debug-workflow.md` 参照）

---

## 受け入れ基準

### human-like排他（Option A: 強制OFF）
- [ ] トグルON操作時、パス空＋last_pathなしなら警告表示＆即座にOFF＆パスクリア
- [ ] トグルON操作時、パス空＋last_pathありなら復元してON維持
- [ ] 保存時、ON＋パス空なら強制OFF＆`humanlike_model=""`で保存
- [ ] **保存後、UI状態をconfig状態に同期**: `self.humanlike_enabled = effective_on`
- [ ] **Kivyバインディング**: `on_humanlike_enabled`メソッドまたはKVで明示的にバインド
- [ ] `normalize_humanlike_config()`が3値タプル`(model, last, effective_on)`を返す
- [ ] `normalize_humanlike_config()`は`katrain/common/humanlike_config.py`に配置（Kivy非依存）
- [ ] engine.pyは変更なし（手動でコマンドライン検証）

### 3モード切替
- [ ] 自動/標準/高機能の切替UIが動作する
- [ ] 自動モードは暫定表示（「推奨設定を使用中」）
- [ ] 標準モードで現在モデルの意味ラベルが表示される（切替なし）
- [ ] 高機能モードで既存フルUIが表示される

### 意味ラベル（表示のみ）
- [ ] `model_labels.py`はカテゴリキーのみ返す（文字列なし）
- [ ] 全ユーザー向け文字列はi18n (.po)から取得
- [ ] 不明モデルは`model:unknown_with_name`（プレースホルダー`{name}`）で表示
- [ ] 空パスは`model:none`で表示（"Other: "の防止）
- [ ] `_cross_platform_basename()`でLinux CI上でもWindowsパスを正しく処理

### i18n
- [ ] `jp`ロケールコードを使用（`ja`ではない）
- [ ] `lang_change_tracking: i18n._('')`パターンで言語切替追従
- [ ] `python i18n.py`でコンパイル完了

### テスト
- [ ] `tests/test_model_labels.py` が全パス（CI、Kivy非依存）
- [ ] `tests/test_humanlike_config.py` が全パス（CI、Kivy非依存）
- [ ] 手動テスト項目が全て確認済み（engine.py検証含む）

### 設定永続化
- [ ] `humanlike_model_last`が`config.json`に保存される
- [ ] 再起動後も`humanlike_model_last`が読み込まれる

---

## 後方互換性

- `humanlike_model`キーは既存のまま維持
- `humanlike_model_last`は新規追加（なければ空文字扱い）
- engine.pyの動作は完全に変更なし
- 既存設定ファイルはそのまま動作（マイグレーション不要）
- config保存はスキーマ検証なし（新キーは自動的に保存される）
