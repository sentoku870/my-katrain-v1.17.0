# myKatrain アーキテクチャ

最終更新: 2026-07-21

開発者向けのコード構造・依存方向・変更時の注意点をまとめた正本。実装の変更や機能追加の前に対象パッケージの責務を確認してください。

## 1. レイヤー依存

```
common/   ←  共有定数 (Kivy 非依存)
core/     ←  コアロジック (Kivy 非依存)
gui/      ←  Kivy GUI (Kivy / KivyMD に依存)
```

- `common → core → gui` の片方向依存のみ許可。逆向きは禁止。
- `core` 内の変更は Kivy を import せずにテスト可能。
- `gui` から `core` を呼ぶのは OK。逆は禁止。

## 2. 主要パッケージ

| パッケージ | 責務 | 公開 API |
|----------|------|---------|
| `katrain.common` | 共有定数・型・変換ユーティリティ | `rank.Rank`, `locale_utils.*` |
| `katrain.core.analysis` | 解析基盤 (logic / models / meaning_tags / difficulty) | `logic.py`, `difficulty.api.*` |
| `katrain.core.beginner` | Beginner Hints 検出 (9 系統) | `compute_hint`, `HintCategory` |
| `katrain.core.coach` | LLM Coach 翻訳特化基盤 | `prompt_builder.build_translation_prompt`, `validator.validate_llm_response` |
| `katrain.core.study` | 学習モード (kifunarabe) | `kifunarabe.KifunarabeSession`, `kifunarabe_history.KifunarabeHistoryStore` |
| `katrain.core.reports` | Karte / Summary レポート生成 | `karte.build_karte_json_string`, `summary_json_export.build_summary_json` |
| `katrain.core.batch` | バッチ解析 (orchestration サブパッケージ) | `orchestration.run_batch` |
| `katrain.core.curator` | 棋譜適合度スコアリング | `models.load_curator_profile`, `scoring.score_games` |
| `katrain.gui.commands` | コマンドディスパッチ (35 エントリ) | `DISPATCH_TABLE` |
| `katrain.gui.popups` | ポップアップダイアログ | `llm_coach_popup.LLMCoachPopup`, `kifunarabe_*` |
| `katrain.gui.managers` | 19 Manager クラス (UI 状態管理) | `KaTrainGui.ctx.{manager_name}` |

`katrain.gui.app_context.AppContext` が Manager 19 個を集約し、`KaTrainGui.ctx.<name>` でアクセスする単一エントリポイント。

## 3. データフロー

### 3.1 解析パイプライン

```text
KataGo (subprocess)
  → engine_io (stdin/stdout reader thread)
  → KataGoEngine (query queue, pondering)
  → GameNode.set_analysis()
  → core.analysis (loss / importance / meaning tag)
  → StateNotifier
  → Managers (gui_refresh, ui_update)
  → ControlsPanel / BadukPanWidget 更新
```

### 3.2 LLM Coach パイプライン

```text
ユーザーが Karte / Summary JSON を指定
  → katrain.core.coach.json_type.detect_json_type()
  → popup_logic (Kivy 非依存ロジック) [Phase 242-E]
  → prompt_builder.build_translation_prompt()
       ├─ Lexicon 注入 (go_lexicon_master_last.yaml)
       ├─ SymptomId ground truth (30 症状)
       └─ System Instruction (HTML コメント式 3 層防御)
  → ユーザーが手動で外部 LLM に貼付
  → 応答を貼り戻して validator.validate_llm_response()
       ├─ 症状 ID 存在チェック
       ├─ 着手番号範囲チェック
       ├─ pointsLost 天井チェック
       ├─ 鳥瞰違反チェック
       └─ Lexicon / tone 整合性チェック
```

## 4. コマンドディスパッチ

UI からのアクションは `gui/commands/DISPATCH_TABLE`（35 エントリ）への明示的ディスパッチに移行済み。

```python
# gui/commands/__init__.py
DISPATCH_TABLE = {
    "new_game": new_game,
    "export_karte_ui": export_karte_ui,
    "llm_coach_popup": open_llm_coach_popup,
    # ...
}
```

新規アクション追加時は:

1. `gui/commands/<action>.py` にハンドラを実装
2. `gui/commands/__init__.py` の `DISPATCH_TABLE` に登録
3. KV / menu から `app.dispatch("action", *args)` で呼び出し

旧 `_do_*` ラッパーメソッドは完全廃止。`KaTrainGui` に個別ハンドラを書かない。

## 5. 変更時の注意

### 5.1 UI (`.kv` / `gui/`)

- `.kv` ファイルと `.py` の両方を確認
- Kivy の id / property バインディングに注意
- Phase 277 以降は KivyMD 1.2.0 で削除された API を使わない（`selected_color`, `unselected_color`, `helper_text_mode: "none"`, `BaseFlatButton`, `BasePressedButton`）
- Phase 277 以降は `<SizedButton>: padding: 0` 必須（Phase 283 で回帰テスト保護）
- Phase 281 以降は `factory._sync_font_to_hint_labels` パターンを維持（日本語フォント豆腐防止）

### 5.2 解析ロジック (`core/analysis/`)

- データモデル → `models/`
- 計算ロジック → `logic.py` / `logic_*.py` / `difficulty/`
- 表示処理 → `presentation.py`
- `difficulty/` を触る場合は `api.py` 経由（後方互換シム維持）
- `internal_params.py` のパラメータは config 経由でユーザーオーバーライド可能

### 5.3 Beginner Hints (`core/beginner/`)

1. `core/beginner/detector_<name>.py` に pure detector を追加（Kivy 非依存）
2. `HintCategory` enum に追加
3. `compute_summary_hint` の priority chain に統合
4. i18n キー追加（jp/en 両方）
5. `tests/test_beginner_hints_*.py` の整合性チェック更新

### 5.4 LLM Coach (`core/coach/`)

- `core/coach/popup_logic.py` に Kivy 非依存ロジックを抽出（Phase 242-E）
- GUI 側は薄いラッパー
- `json_type.detect_json_type()` で karte / summary 自動判別
- `validate_prompt_config()` で voice / mode / difficulty の整合性チェック

### 5.5 PyInstaller ビルド

- `spec/KaTrain.spec` の `hiddenimports` に Clock-scheduled lazy import 経路のモジュールを明示
- 既知: `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` / `katrain.gui.lang_bridge` / KivyMD 36 widget

## 6. 開発コマンド

```bash
# 依存同期
uv sync

# 起動
uv run python -m katrain

# テスト（逐次）
uv run pytest tests

# テスト（並列）
uv run pytest tests -n auto

# テスト（時間上位表示）
uv run pytest tests --durations=20 --durations-min=0.1

# アーキテクチャテスト
uv run pytest tests/test_architecture.py -v

# 静的解析
uv run mypy katrain
uv run ruff check katrain tests
uv run ruff format --check katrain tests

# 整形
uv run ruff format katrain tests
```

## 7. 関連ドキュメント

- [`docs/karte-schema.md`](./karte-schema.md) — Karte / Summary JSON スキーマ正本
- [`docs/usage-guide.md`](./usage-guide.md) — 利用者ガイド
- [`docs/i18n-workflow.md`](./i18n-workflow.md) — 翻訳手順
- [`docs/kivy-testing.md`](./kivy-testing.md) — headless Kivy テスト手順
