# myKatrain コード構造

> **最終更新**: 2026-07-17（Phase 225: LLM Coach GUI 統合）
> Phase 171 で Leela エンジン完全削除。Phase 187-192 で Architecture Review Follow-up 完了。
> Phase 225 で MyKatrain メニューに LLM コーチ（手動貼付）を追加。
> 完了 Phase の詳細は [`docs/archive/specs-implemented/phase*.md`](./archive/specs-implemented/) を参照。

---

## 1. ディレクトリ構造（2026-07-16 時点 = Phase 192）

```
katrain/
├── __main__.py              # アプリ起動、KaTrainGui クラス（Phase 172 で 995 → 878 行）
│
├── common/                  # 共有定数（循環依存解消用、Kivy非依存）
│   ├── platform.py          # get_platform()（Kivy非依存OS判定）
│   ├── config_store.py      # JsonFileConfigStore（Mapping実装）
│   ├── locale_utils.py      # normalize_lang_code(), to_iso_lang_code()
│   ├── model_labels.py      # classify_model_strength(), get_model_basename()
│   ├── humanlike_config.py  # normalize_humanlike_config()
│   ├── settings_export.py   # settings エクスポート/インポート
│   ├── sanitize.py          # ファイル名サニタイズ
│   ├── resource_utils.py    # find_package_resource()（Phase 163 で core から移動）
│   ├── theme_constants.py   # INFO_PV_COLOR など
│   ├── typed_config/        # 型付き設定読み書き（reader/writer/models）
│   └── lexicon/             # 囲碁用語辞書パッケージ
│
├── core/                    # コアロジック（Kivy非依存）
│   ├── _engine_types.py     # TYPE_CHECKING 専用の前方参照集約（Phase 191）
│   ├── game_node.py         # GameNode（手/解析結果）
│   ├── engine.py            # KataGoEngine（解析プロセス、Phase 158 で分割）
│   ├── engine_io.py         # stdin/stdout reader threads
│   ├── engine_query.py      # query 送信/終了/pondering
│   ├── engine_cmd/          # AnalysisCommand パターン（executor.py）
│   ├── sgf_parser.py        # SGF読み込み
│   ├── game/                # Game クラス（Phase 141 で 4 分割）
│   │   ├── base.py                # BaseGame, IllegalMoveException, KaTrainSGF
│   │   ├── facade.py              # Game（合成クラス）
│   │   ├── analysis_orchestrator.py # AnalysisOrchestrator
│   │   ├── navigation.py          # GameNavigator
│   │   └── insert_mode.py         # InsertModeController
│   │
│   ├── ai_strategies_base.py     # AI戦略基底クラス・register_strategy
│   ├── ai_strategies/            # AI戦略実装（Phase 158 で分割: basic, pick, policy, score, human）
│   │
│   ├── analysis/             # 解析基盤パッケージ
│   │   ├── models/                # Enum, Dataclass, 定数（models/ パッケージに分割）
│   │   ├── logic.py, logic_*.py   # 損失/重要度/クイズ/difficulty/reliability/skill/
│   │   ├── logic_difficulty.py    # 後方互換シム（Phase 192）
│   │   ├── presentation.py        # 表示/フォーマット関数
│   │   ├── critical_moves.py      # Critical 3 選択
│   │   ├── ownership_cluster.py   # ownership クラスタ抽出
│   │   ├── cluster_classifier.py
│   │   ├── cluster_detectors.py
│   │   ├── cluster_geometry.py
│   │   ├── board_context.py
│   │   ├── reason_generator.py
│   │   ├── meaning_tags/          # 意味タグ分類（classifier/context_builder/integration/models/registry）
│   │   ├── time/                  # 時刻・パシング解析（models/parser/pacing）
│   │   └── difficulty/            # Phase 192 新設サブパッケージ（6 モジュール）
│   │       ├── api.py                  # 公開 4 関数
│   │       ├── _io.py                  # 候補手正規化、root_visits 抽出、信頼性判定
│   │       ├── _policy.py              # policy エントロピー fallback + top-1/top-2 gap
│   │       ├── _transition.py          # 評価急落度
│   │       ├── _state.py               # 盤面複雑度（v1 placeholder）
│   │       ├── _error_pressure.py      # KataGo shorttermScoreError
│   │       └── _lcb_gap.py             # LCB 差分
│   │
│   ├── batch/                # バッチ処理パッケージ（Phase 158-B で 10 モジュール分割）
│   │   ├── orchestration.py    # run_batch()
│   │   ├── analysis.py
│   │   ├── discovery.py        # collect_sgf_files
│   │   ├── engine_polling.py
│   │   ├── filenames.py
│   │   ├── inputs.py
│   │   ├── io_safe.py
│   │   ├── loss.py
│   │   ├── markdown_fmt.py
│   │   ├── models.py
│   │   ├── sgf_io.py
│   │   ├── visits.py
│   │   └── stats/              # stats/ パッケージ
│   │
│   ├── beginner/             # 初級者向けヒント（Phase 179-187 で大幅拡張）
│   │   ├── hints.py           # Hint priority chain（Phase 187 で 16.5% → 97% カバレッジ）
│   │   ├── models.py          # HintCategory enum（23 カテゴリ）
│   │   ├── detector_mistake.py
│   │   ├── detector_freedom.py
│   │   ├── detector_difficulty.py
│   │   ├── detector_katago.py
│   │   ├── detector_ownership.py
│   │   ├── detector_policy.py
│   │   └── detector_curator.py   # Phase 186 追加
│   │
│   ├── curator/              # 棋譜適合度スコアリング
│   │   ├── __init__.py
│   │   └── profile.py         # CuratorProfile / load_curator_profile()（Phase 186）
│   │
│   ├── study/                # 学習モード
│   │   ├── __init__.py
│   │   └── kifunarabe.py      # 棋譜並べ KifunarabeSession モデル
│   │
│   ├── auto_setup.py         # 自動セットアップロジック（Phase 189 で 9.8% → 97% カバレッジ）
│   ├── auto_setup_controller.py
│   ├── analysis_result.py
│   ├── board_analysis.py
│   ├── board_geometry.py
│   ├── compatibility.py      # Python 3.11+ StrEnum re-export
│   ├── constants.py
│   ├── diagnostics.py
│   ├── lang.py
│   ├── state/                # StateNotifier
│   ├── tsumego_frame.py
│   ├── utils.py
│   └── reports/              # レポート生成
│       ├── karte/                # Karte report パッケージ
│       │   ├── builder.py
│       │   ├── json_export.py
│       │   ├── helpers.py
│       │   ├── models.py
│       │   └── sections/         # セクション別ビルダー
│       ├── summary_*.py
│       ├── quiz_report.py
│       ├── sections/
│       └── utils/
│
├── gui/                      # GUI（Kivy）
│   ├── controlspanel.py      # 右パネル
│   ├── badukpan.py           # 盤面表示
│   ├── sgf_manager.py
│   ├── lang_bridge.py        # KivyLangBridge
│   ├── theme.py
│   ├── theme_loader.py
│   ├── sound.py
│   ├── error_handler.py
│   ├── commands/             # コマンドパターン
│   ├── kivyutils/            # Kivy ユーティリティ（app_config, mixins, buttons, _base, _labels, _spinners, _player, _timer, _panels, _clickables）
│   ├── managers/             # Manager パターン
│   │   ├── active_review_controller.py
│   │   ├── auto_setup_controller.py
│   │   ├── config_manager.py
│   │   ├── dialog_factory.py
│   │   ├── game_state_manager.py
│   │   ├── game_state_update_manager.py
│   │   ├── gui_refresh_manager.py
│   │   ├── keyboard_manager.py
│   │   ├── kifunarabe_controller.py     # Phase 188 で 4 mixin + facade 分割
│   │   ├── kifunarabe_state.py          # Phase 188 で型注釈集約
│   │   ├── message_loop_manager.py
│   │   ├── popup_manager.py
│   │   ├── scroll_handler.py
│   │   ├── summary_manager.py
│   │   └── ui_update_manager.py
│   ├── popups/               # ポップアップダイアログ
│   ├── widgets/              # カスタム Kivy ウィジェット
│   │   ├── graph.py
│   │   ├── movetree.py
│   │   ├── selection_slider.py
│   │   ├── progress_loader.py
│   │   ├── filebrowser.py
│   │   └── factory.py, helpers.py
│   ├── controllers/          # batch_analysis_controller 等
│   └── features/             # 機能モジュール
│       ├── settings_popup.py
│       ├── settings_popup_state.py
│       ├── settings_popup_helpers.py
│       ├── settings_popup_tabs/  # KataGo 専用タブ（Phase 171 で leela_tab 削除）
│       ├── karte_export.py
│       ├── llm_coach.py            # Phase 225 LLM コーチ（Kivy 非依存ロジックラッパー）
│       ├── summary_*.py
│       ├── batch_*.py
│       ├── active_review_*.py
│       ├── commands/
│       ├── diagnostics_popup.py
│       ├── recovery_actions.py
│       ├── report_navigator.py
│       └── context.py, types.py
│
├── i18n/                     # 国際化（JP+EN）
│   ├── __init__.py
│   └── locales/{en,jp}/LC_MESSAGES/katrain.{po,mo}
```

> 注: 上記のツリーは要約です。完全なリストは `find katrain -name "*.py" | sort` を参照。
> 大きな構造変更は [`docs/01-roadmap.md`](./01-roadmap.md) のフェーズ記録を確認してください。

---

## 2. 主要クラスの関係（Phase 172 時点）

```
KaTrainGui (Screen, KaTrainBase) — Phase 172 で 995 → 878 行
├── self.game      → Game（対局状態、Phase 141 で 4 分割）
├── self.engines   → dict[str, KataGoEngine]（KataGo 専用、Phase 171 で Leela 削除）
├── self.controls  → ControlsPanel（右パネル）
├── self.board_gui → BadukPanWidget（盤面、Phase 158+ で 4 分割）
├── self.managers  → 15 個の Manager
│   ├── active_review / auto_setup / config / dialog / game_state
│   ├── game_state_update / gui_refresh / keyboard
│   ├── kifunarabe（Phase 188 で mixin 分割、800 → 180 行 facade）
│   ├── message_loop / popup / scroll_handler / summary / ui_update
└── self.popup_manager / self.summary_manager / ...

# コマンドディスパッチ（Phase 172 で全面刷新）
KaTrainGui → commands/DISPATCH_TABLE (35エントリ) → 各コマンドハンドラ
            （旧 `_do_*` ラッパーメソッド 34個は削除済み）
```

### 依存方向
```
KaTrainGui → Game → GameNode
          → KataGoEngine (engine_io + engine_query + engine_cmd)
                          + core/_engine_types (TYPE_CHECKING 集約、Phase 191)
          → ControlsPanel → ScoreGraph
                         → various widgets
          → Managers → 各機能（state, popup, dialog, ...）
```

---

## 3. データフロー

### 3.1 解析データの流れ
```
1. GameNode.analyze()
     ↓ KataGoEngine に解析リクエスト
2. KataGoEngine.send_query() → write_queue
     ↓
3. write_stdin_thread → KataGo (subprocess)
     ↓ JSON結果
4. analysis_read_thread → set_analysis(result)
     ↓ analysis dict に格納
5. StateNotifier (Phase 104) → Manager 通知
     ↓
6. UI Update (gui_refresh_manager / ui_update_manager)
     ↓
7. ControlsPanel.update_evaluation() → UI更新
```

### 3.2 UIイベントの流れ（Phase 172 反映）
```
1. ユーザー操作（ボタン/盤面タップ）
     ↓
2. Kivy → root.katrain("action", args)
     ↓
3. KaTrainGui.__call__() → commands/DISPATCH_TABLE[action]
     ↓                                  ↑ Phase 172 で旧 `_do_*` ラッパーは削除
4. 各コマンドハンドラ (commands/*.py) が必要に応じて Manager / GameNode を操作
```

---

## 4. myKatrain で追加した主な機能

詳細は [`docs/01-roadmap.md`](./01-roadmap.md) のフェーズ記録を参照してください。

### 4.1 解析基盤（analysis パッケージ）
- 損失/重要度計算、難易度メトリクス、信頼度
- 意味タグ分類（`meaning_tags/` パッケージ）
- Critical 3 選択、Pattern Mining
- Time/Pacing 分析
- **Phase 192**: `difficulty/` サブパッケージ化（756 行 → 6 モジュール + 後方互換シム）

### 4.2 Beginner Hints（初心者向けヒント）
- Phase 91-92 で MVP 構築
- Phase 179 + 179.1 + 179.2 で Summary Extension（ミス・自由度・難易度、9 カテゴリ）
- Phase 182 で Ownership / Policy 派生ヒント（3 カテゴリ追加）
- Phase 186 で Curator 集約統合（HintCategory 計 23 カテゴリ）
- Phase 187 で `hints.py` カバレッジ 16.5% → 97%（137 件追加）

### 4.3 Karte レポート
- ビルドフロー: `build_karte_json_string()` → `katrain/core/reports/karte/__init__.py` （Phase 231 で `build_karte_report` → `build_karte_json_string` リネーム。実装は Phase 149 から常に JSON 文字列を返していた）
- セクション分割: `katrain/core/reports/karte/sections/`
- 意味タグ分類: `katrain/core/analysis/meaning_tags/`

### 4.4 バッチ解析
- `katrain/core/batch/orchestration.py::run_batch()` がメインエントリ
- 統計抽出: `katrain/core/batch/stats/` パッケージ
- Markdown 出力: `katrain/core/batch/markdown_fmt.py`

### 4.5 Manager パターン
- 15 個の Manager クラスで UI 状態を管理（Phase 188 で Kifunarabe Controller を mixin 分割）
- PEP 562 `__getattr__` で遅延 import

### 4.6 Kifunarabe（棋譜並べ）
- `core/study/kifunarabe.py` に KifunarabeSession モデル
- `gui/managers/kifunarabe_controller.py` に Controller（4 mixin + facade）
- Phase 178 で `_kick_root_analysis` リトライ + 終了経路統一

### 4.7 Curator（棋譜適合度スコアリング）
- `core/curator/profile.py` に CuratorProfile（Phase 186 追加）
- Beginner Hints の最下層 priority chain に統合

---

## 5. 削除済み/旧ファイル（参考）

### 5.1 Phase 171 で削除（Leela エンジン完全削除）
- `katrain/core/leela/` ディレクトリ（1459 行）
- `katrain/gui/leela_manager.py`
- `katrain/gui/features/settings_popup_tabs/leela_tab.py`
- `katrain/gui/features/resign_hint_popup.py`
- `katrain/core/batch/leela_gate.py`
- `katrain/core/analysis/engine_compare.py`
- `EngineType.LEELA`、`LeelaConfig` / `LeelaEngine`、`leela_loss_est` フィールド、`is_single_engine_snapshot` / `MixedEngineSnapshotError` / `KARTE_ERROR_CODE_NON_KATAGO`、`LEELA_*` 定数

### 5.2 過去の削除
- `katrain/core/yose_analyzer.py`（Phase 100 付近で削除）
- `katrain/core/analysis/skill_radar.py`（意味タグに統合）
- `katrain/gui/features/radar_geometry.py`, `radar_chart.py`, `skill_radar_popup.py`（同上）
- `katrain/gui/features/auto_mode_popup.py`（auto_setup_controller.py に統合）
- `katrain/gui/features/quiz_popup.py`, `quiz_session.py`（quiz_manager に統合）
- `katrain/core/reports/karte/sections/summary.py`（Phase 161 で削除）

### 5.3 Phase 172 で削除
- `KaTrainGui._do_*` ラッパーメソッド 34 個（DISPATCH_TABLE への明示的ディスパッチに置換）

---

## 6. 変更時の注意点

### 6.1 UIを触る場合
- `.kv` ファイルと `.py` の両方を確認
- Kivy の id/property バインディングに注意
- Phase 172 以降は `commands/DISPATCH_TABLE` への登録が必須（`__main__.py` 内のラッパー作成は不要）

### 6.2 解析ロジックを触る場合
- `katrain/core/analysis/` パッケージが主な変更対象
  - データモデル → `models/`
  - 計算ロジック → `logic.py` / `logic_*.py` / `difficulty/` (Phase 192)
  - 表示処理 → `presentation.py`
- `core/analysis/difficulty/` を触る場合は `api.py` の公開関数経由を推奨（後方互換シム維持）

### 6.3 翻訳を追加する場合
- 文字列を `i18n._("...")` で包む
- `uv run python i18n.py -todo` で不足をチェック
- 各言語の `.po` ファイルに追加
- `.mo` ファイルを再生成

### 6.4 Beginner Hints を追加する場合
- `core/beginner/detector_*.py` に pure detector を追加（Kivy 非依存）
- `HintCategory` enum に追加（合計 23 カテゴリ）
- `compute_summary_hint` の priority chain に統合
- 既存テスト（`tests/test_beginner_hints_*.py`）の追加カテゴリの i18n 整合性チェックを更新

---

## 7. テスト実行

```bash
# テスト実行（逐次）
uv run pytest tests

# テスト実行（並列）
uv run pytest tests -n auto

# テスト実行（時間上位表示）
uv run pytest tests --durations=20 --durations-min=0.1

# アーキテクチャテスト
uv run pytest tests/test_architecture.py -v

# 起動確認
python -m katrain

# i18nチェック
$env:PYTHONUTF8 = "1"
uv run python i18n.py -todo
```

---

## 8. 変更履歴

> 直近 3 ヶ月の主要 Phase のみ記載。詳細は `AGENTS.md` セクション 10 を参照。

- 2026-07-16: **Documentation cleanup** — 旧 addendum を本ファイルにマージ、Phase 171-192 の構造反映
- 2026-07-16: Phase 192 — `core/analysis/difficulty/` サブパッケージ新設（6 モジュール + 後方互換シム）
- 2026-07-15: Phase 191 — `core/_engine_types.py` 新設（engine subsystem TYPE_CHECKING 循環解消）
- 2026-07-15: Phase 190 — `core/engine.py` カバレッジ 48.3% → 83%
- 2026-07-15: Phase 189 — `core/auto_setup.py` カバレッジ 9.8% → 97%
- 2026-07-14: Phase 188 — `gui/managers/kifunarabe_controller.py` God Class 分割（4 mixin + facade、800 → 180 行）
- 2026-07-14: Phase 187 — `core/beginner/hints.py` カバレッジ 16.5% → 97%
- 2026-07-14: Phase 186 — `core/curator/profile.py` 新設（CuratorProfile、Beginner Hints 統合）
- 2026-07-14: Phase 182 — `core/beginner/detector_ownership.py` / `detector_policy.py` 新設
- 2026-07-14: Phase 179 + 179.1 + 179.2 — Beginner Hints Summary Extension（9 カテゴリ追加）
- 2026-07-13: Phase 178 — kifunarabe Root 解析堅牢化 + 終了経路統一
- 2026-07-11: Phase 173 — kivy import を関数内に移動（CI exit-102 部分修正）
- 2026-07-11: Phase 172 — `commands/DISPATCH_TABLE` への明示的ディスパッチ移行、`KaTrainGui._do_*` メソッド 34 個削除
- 2026-07-04: Phase 171 — **Leela エンジン完全削除**（`core/leela/` 1459 行削除、KataGo 専用化）
- 2026-07-01: Phase 166 — 設定ポップアップ partial 整理
- 2026-06-25: Phase 143-A/B — Kivy 違反解消 + 循環依存検出
- 2026-06-25: Phase 144-A/B/C — kivyutils / analysis/models / analysis/logic 分割
- 2026-06-26: Phase 145-A/B/C/D — badukpan / batch_ui / orchestration / settings_popup 部分抽出
- 2026-05: Phase 138-142 — リファクタリング（解析基盤刷新、God module 抽出、Manager 分割）

> 注: 2026-06-26 までは `CLAUDE.md` を使用していた。opencode 移行により `AGENTS.md` に変更。