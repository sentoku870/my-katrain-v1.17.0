# Phase 225: LLM Coach GUI 統合（手動貼付ワークフロー）

> 起票日: 2026-07-17
> 完了: 2026-07-17
> ステータス: ✅ 完了

## 1. 概要

Phase 207-214 で実装した `core/coach/` パッケージの **GUI 統合**。
Kivy ポップアップから LLM プロンプトを生成し、クリップボードへコピー →
ユーザーが Claude / ChatGPT / Gemini 等へ手動貼付 → LLM 回答を再度貼付 →
検証 という **手動ワークフロー**を完結させる。

**API 連携（OpenRouter / OpenAI / ローカル LLM）は将来 Phase 224 として
保留**。本 Phase は LLM 自動送信を **しない**（`AGENTS.md §7` の non-goal）。

## 2. 動機と背景

Phase 203-214 で CLI から LLM プロンプト生成 / 検証は完成済み。
ユーザーは `python -m katrain.core.coach.cli ...` をターミナルで叩く必要があり、
KaTrain を閉じずに LLM を呼び出す導線が無かった。

本 Phase では KaTrain の **MyKatrain メニュー**から直接 Popup を開いて
同じ操作を行えるようにする。レスポンスを API で送信しない理由は:

| 観点 | 理由 |
|------|------|
| セキュリティ | API キー管理・ログ混入リスクを避ける |
| 保守コスト | 各 LLM プロバイダの SDK バージョン追従 |
| 透明性 | ユーザーが自分で「どの LLM に何を投げたか」を把握 |
| KataGo 哲学 | オフライン完結が基本、外部送信は明示操作のみ |

## 3. 実装ファイル

### 新規（4 ファイル）

| ファイル | 行数 | 役割 |
|---------|------|------|
| `katrain/gui/features/llm_coach.py` | 161 | FeatureContext 経由で `core/coach/cli.build_prompt` / `validate_llm_output` を呼ぶ薄いラッパー（Kivy 非依存） |
| `katrain/gui/popups/llm_coach_popup.py` | 195 | `LLMCcoachPopupContent(BoxLayout)` — 5 ボタン + ステータスラベル + 結果ラベル |
| `katrain/gui/kv/llm_coach_popup.kv` | 138 | レイアウト定義 |
| `tests/test_llm_coach.py` | 287 | 16 件のロジック単体テスト |
| `tests/test_llm_coach_popup.py` | 227 | 18 件の GUI 単体テスト（`__new__` バイパス、`MagicMock` 注入） |

### 変更（5 ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `katrain/gui/features/commands/__init__.py` | DISPATCH_TABLE に `llm_coach_popup` 追加（diagnostics と kifunarabe_popup の間） |
| `katrain/gui/features/commands/popup_commands.py` | `do_llm_coach_popup(ctx)` 追加 |
| `katrain/gui/kv/menu.kv` | `<MyKatrainDropDown>` に `LLM Coach` メニュー項目追加 |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` & `.mo` | 28 個の `mykatrain:llm-coach:*` キー追加 |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` & `.mo` | 同上 |

## 4. ワークフロー

### 4.1 ユーザー操作

```
┌──────────────────────────────────────────────────────────┐
│ [1] KaTrain → MyKatrain → Export Karte → karte_xxx.json  │
│ [2] MyKatrain → LLM コーチ（手動貼付）                  │
│     → Popup 開く、最新 Karte パス自動入力                │
│ [3] 「プロンプト生成 & コピー」ボタン                    │
│     → Markdown がクリップボードへ                       │
│ [4] Claude / ChatGPT / Gemini に手動貼付                │
│ [5] LLM の回答を Popup のテキストエリアへ手動貼付        │
│ [6] 「検証実行」ボタン                                  │
│     → 結果ラベルに warnings 表示（あれば）               │
│ [7] 「検証結果をコピー」でレポートをクリップボードへ     │
└──────────────────────────────────────────────────────────┘
```

### 4.2 Popup UI

```
┌─────────────────────────────────────────────────────────┐
│ LLM コーチ — KataGo 出力を LLM に翻訳           ✕       │
├─────────────────────────────────────────────────────────┤
│ Karte JSON: [/path/to/karte_xxx.json ] [参照]           │
│ 棋力 (例: 5k): [5k]                                      │
│                                                         │
│ [プロンプト生成 & コピー]  [応答をクリア]               │
│                                                         │
│ ─── LLM 応答（ここに貼り付け）───                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │                                                     │ │
│ │                                                     │ │
│ └─────────────────────────────────────────────────────┘ │
│ [検証実行]  [検証結果をコピー]                          │
│                                                         │
│ ✅ プロンプトをコピーしました（1234 文字）              │
│                                                         │
│ ─── 検証結果 ───                                        │
│ **Status**: ✅ 検証クリア — 警告なし                   │
│ **HIGH**: 0 · **MEDIUM**: 0 · **LOW**: 0              │
│ **Referenced symptom IDs**: miss_atari, overplay       │
└─────────────────────────────────────────────────────────┘
```

## 5. 設計判断

### 5.1 Popup Content Widget パターン

```python
class LLMCcoachPopupContent(BoxLayout):
    """Kivy FileBrowserのサブセット + I18NPopup."""
    karte_path_input = ObjectProperty(None)
    rank_input = ObjectProperty(None)
    response_input = ObjectProperty(None)
    status_label = ObjectProperty(None)
    result_label = ObjectProperty(None)

    def on_generate_and_copy(self) -> None:
        from katrain.gui.features.llm_coach import build_llm_prompt
        ok, md = build_llm_prompt(self.katrain, self.karte_path_input.text, rank=...)
        if ok:
            Clipboard.copy(md)
            self._set_status(i18n._("mykatrain:llm-coach:copy-success").format(chars=len(md)))
        else:
            self._set_status(md, error=True)
```

`core/coach/cli.py:build_prompt` と `core/coach/llm_validator:validate_llm_output`
を **そのまま再利用**。Popup はラッパーのみ。

### 5.2 テスト戦略

KivyMD の `MDTextField` がヘッドレス環境（CI）でハングするため、
`test_game_report_popup.py:51` と同じ `__new__` バイパスパターンを採用:

```python
def _make_content() -> Any:
    from katrain.gui.popups.llm_coach_popup import LLMCcoachPopupContent
    content = LLMCcoachPopupContent.__new__(LLMCcoachPopupContent)
    # Kivy Property bindings を回避し、純粋ロジックのみテスト
    content.karte_path_input = MagicMock()
    ...
```

これにより、Kivy ウィジェット初期化を完全にバイパスし、メソッド本体のみを検証。

### 5.3 i18n キー一覧（28 個）

```
mykatrain:llm-coach                       (menu)
mykatrain:llm-coach:title                 (popup title)
mykatrain:llm-coach:karte-hint            (text input hint)
mykatrain:llm-coach:rank-label            (label)
mykatrain:llm-coach:response-label        (label)
mykatrain:llm-coach:result-label          (label)
mykatrain:llm-coach:browse                (button)
mykatrain:llm-coach:browse-title          (file browser)
mykatrain:llm-coach:build-prompt          (button)
mykatrain:llm-coach:clear-response        (button)
mykatrain:llm-coach:validate              (button)
mykatrain:llm-coach:copy-result           (button)
mykatrain:llm-coach:file-not-found        (error)
mykatrain:llm-coach:invalid-karte         (error)
mykatrain:llm-coach:no-karte              (error)
mykatrain:llm-coach:no-response           (error)
mykatrain:llm-coach:no-result             (error)
mykatrain:llm-coach:copy-success          (status)
mykatrain:llm-coach:copy-failed           (status)
mykatrain:llm-coach:result-copied         (status)
mykatrain:llm-coach:response-cleared      (status)
mykatrain:llm-coach:validation-clean      (status)
mykatrain:llm-coach:validation-issues     (status)
mykatrain:llm-coach:status                (report)
mykatrain:llm-coach:referenced-symptoms   (report)
mykatrain:llm-coach:referenced-moves      (report)
mykatrain:llm-coach:referenced-points-lost (report)
mykatrain:llm-coach:referenced-lexicon    (report)
mykatrain:llm-coach:issues                (report)
mykatrain:llm-coach:truncated             (overflow)
```

## 6. テスト結果

| 指標 | 値 |
|------|-----|
| ロジック単体テスト | **16 件** PASS（`test_llm_coach.py`） |
| Popup 単体テスト | **18 件** PASS（`test_llm_coach_popup.py`） |
| 累計テスト | **4882 件** PASS（4848 baseline + 34 新規） |
| アーキテクチャテスト | **44 件** PASS |

## 7. 申し送り

| Phase | 内容 | 優先度 |
|-------|------|--------|
| **Phase 224** | OpenAI 互換エンドポイント連携（OpenRouter / OpenAI / ローカル LLM） | 中（手動運用で十分なため急がない） |
| Phase 226+ | 履歴タブ（直近 10 件の LLM 回答を Karte に紐付け） | 低 |
| Phase 227+ | ストリーミング応答表示 | 低 |

## 8. 関連ドキュメント

- `docs/01-roadmap.md` 行 1069: Phase 225 章
- `AGENTS.md §1.3`: Phase 225 追記
- `docs/archive/specs-planned/phase203-llm-translator.md`: 翻訳特化設計
- `katrain/core/coach/cli.py`: CLI 実装（Popup から再利用）
- `katrain/core/coach/llm_validator.py`: バリデータ実装（Popup から再利用）
