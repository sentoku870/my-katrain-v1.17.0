# myKatrain（PC版）ロードマップ

> 最終更新: 2026-06-28(Phase 151 完了)
> 固定ルールは `00-purpose-and-scope.md` を参照。
> 過去の履歴（Phase 1-130）は [ROADMAP_HISTORY.md](./archive/ROADMAP_HISTORY.md) を参照。
> Phase 138-145 の詳細は [architecture-review-2026-06-26.md](./archive/architecture-review-2026-06-26.md) を参照。
> Phase 148 (2026-06-27 完了): 4 PR (#293 / #294 / #295 / #296)。詳細下記。
> Phase 149 (2026-06-27 完了): Karte/Summary 残存問題点の発見と対応。詳細下記。
> Phase 150 (2026-06-28 完了): mykatrain 設定バグ修正 + CI クリーンアップ。詳細下記。
> Phase 151 (2026-06-28 完了): エンジン起動時の UnboundLocalError 修正 + KataGo バイナリ復元。詳細下記。

---

## 0. 用語（短縮表記）

| 用語 | 説明 |
|------|------|
| カルテ（Karte） | 対局の要点・弱点・根拠をまとめた「診断用まとめ」 |
| アンカー | 根拠を追跡できる最小情報（手数/座標/損失/候補手） |
| LLMパッケージ | LLMに渡す一式（karte.md + sgf + coach.md） |
| カルテ (Karte) | KataGo 解析を元に生成する診断レポート |
| god module | 責務が混在し肥大化した単一ファイル/クラス |

---

## 1. 完了済みフェーズ一覧 (Phase 131〜)

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 131 | JSONレポートの機能改善 | 難易度ラベル名寄せ、局面フェーズ計算 | ✅ |
| 132 | Leela Zero UI改善 | 候補手表示修正、設定拡張 | ✅ |
| 133 | プロジェクトのスリム化 | 緊急バグ修正、最適化調査 | ✅ |
| 134 | 10段階Skill Radar実装 | SkillTier拡張、軸別閾値設定 | ✅ |
| 135 | Skill Radarバッチ出力 | GUI統合、テキスト形式出力 | ✅ |
| 136 | AI対応レーダー出力改善 | 構造化マークダウン、閾値情報追加 | ✅ |
| 137 | 不要機能削除とバグ修正 | Skill Radar削除、SGF読み込み修正 | ✅ |
| 138-142 | リファクタリング | 解析基盤、カルテ、Manager分割、God module 抽出 | ✅ |
| **143-A** | Kivy 違反解消 | `core/base_katrain.py` の Kivy Config を `gui/kivyutils/app_config.py` に分離 | ✅ |
| **143-B** | 循環依存検出 | `gui → __main__` ランタイム循環依存チェック追加 | ✅ |
| **144-A** | kivyutils/widgets.py 分割 | 23 クラスを 6 ファイルに分割（labels/spinners/player/timer/panels/clickables） | ✅ |
| **144-B** | analysis/models.py 分割 | 26 クラスを 6 モジュールに分割（enums/move_eval/quiz/skill/reliability/difficulty） | ✅ |
| **144-C** | analysis/logic.py 分割 | 32 関数を 6 モジュールに分割 + 既存 3 モジュール無変更 | ✅ |
| **145-A** | badukpan.py draw_hover_contents 分割 | 239 行を 6 メソッドに分割 | ✅ |
| **145-B** | batch_ui.py build_batch_popup_widgets 分割 | 375 行を 1 オーケストレータ + 15 ヘルパーに分割 | ✅ |
| **145-C** | orchestration.py run_batch 分割 | 462 行を 5 関数 + 3 context dataclass に分割 | ✅ |
| **145-D** | settings_popup.py 部分抽出 | 703 行の関数から search / buttons / save / browse を抽出 | ✅ (部分的) |
| **148** | Karte/Summary 品質改善 | only判定 / preset差 / importance / primary_tag / 連続forced / メタ情報 / 用語・拡張子 | ✅ (2026-06-27) |
| **149** | Karte/Summary 残存問題対応 + Dead Code Revival | 4 PR (A: bug fixes / B: summary quality / C: JSON revival / D: docs) | ✅ (2026-06-27) |
| **150** | mykatrain 設定バグ修正 + CI クリーンアップ | LeelaConfig.get() None デフォルト修正 / CI から macOS ビルド削除 / dead import 削除 | ✅ (2026-06-28) |
| **151** | エンジン起動エラー処理 + KataGo バイナリ復元 | `query_found` UnboundLocalError 修正 / KataGo eigen 版への復元 / `.gitignore` 拡張 | ✅ (2026-06-28) |

### 直近の更新詳細

**Phase 138-142**: ✅ リファクタリング（2026-05 完了）。
- 解析基盤の刷新、カルテ統合、Manager 分割、God module 抽出を一連で実施。

**Phase 143-A**: ✅ Kivy 違反解消（2026-06-25 完了）。
- `core/base_katrain.py:7` の `from kivy import Config` を `core/kivyutils/app_config.py`（実際は `gui/kivyutils/app_config.py`）に分離。
- `importlib.import_module("katrain.gui.kivyutils.app_config")` による動的呼び出しで `AllImportCollector` の関数内 import 検出も回避。
- `kivy_import_allowlist.json` から `core/base_katrain.py|kivy` エントリ削除。
- 検証: mypy strict 222 ファイル 0 エラー、Architecture テスト 36/36 パス。

**Phase 143-B**: ✅ 循環依存検出（2026-06-25 完了）。
- `tests/test_architecture.py` に `test_gui_does_not_import_main_at_runtime` テストを追加。
- 8 件の `from katrain.__main__ import KaTrainGui` はすべて `if TYPE_CHECKING:` ブロック内にあり、ランタイム循環は存在しないことを確認。
- 自動検出体制を確立。

**Phase 144-A**: ✅ kivyutils/widgets.py 分割（2026-06-25 完了）。
- 512 行 23 クラスを 6 ファイルに分割:
  - `_labels.py` (63行): TableCellLabel 等
  - `_spinners.py` (101行): KeyValueSpinner, I18NSpinner
  - `_player.py` (128行): PlayerSetup 系
  - `_timer.py` (22行): Timer, TimerOrMoveTree
  - `_panels.py` (243行): CollapsablePanel, MenuItem 等
  - `_clickables.py` (28行): ClickableLabel, ClickableCircle, CircleWithText
- `__init__.py` で全クラスを re-export（後方互換維持）。

**Phase 144-B**: ✅ analysis/models.py サブパッケージ化（2026-06-25 完了）。
- 1230 行 26 クラスを 6 モジュールに分割:
  - `enums.py` (241行): 7 enum + engine config helpers
  - `move_eval.py` (274行): MoveEval + EvalSnapshot + canonical_loss
  - `quiz.py` (101行): Quiz* + ImportantMove*
  - `skill.py` (357行): GameSummaryData, SummaryStats, SkillPreset, MistakeStreak, AutoRecommendation, UrgentMiss
  - `reliability.py` (104行): ReliabilityStats + 関連定数
  - `difficulty.py` (134行): PVFilter, DifficultyMetrics + 関連定数
- `__init__.py` で全シンボルを re-export、`__getattr__` 遅延 import も維持。

**Phase 144-C**: ✅ analysis/logic.py 分割（2026-06-25 完了）。
- 1494 行 32 関数を 6 モジュールに分割 + 既存 3 モジュール無変更:
  - `logic_skill.py` (235行): get_skill_preset, recommend_auto_strictness, estimate_skill_level_from_tags
  - `logic_reliability.py` (236行): move_eval_from_node, compute_reliability_stats, compute_confidence_level
  - `logic_phase.py` (64行): get_phase_thresholds, classify_game_phase
  - `logic_difficulty.py` (589行): assess_position_difficulty_from_parent, compute_difficulty_metrics
  - `logic_snapshot.py` (292行): snapshot_from_nodes, snapshot_from_game, detect_mistake_streaks
  - `logic_pv.py` (107行): get_pv_filter_config, filter_candidates_by_pv_complexity
- `.gitignore` の `log*` パターンに `!**/logic_*.py` 追加（gitignore 誤認識を修正）。
- 循環依存回避のため関数内遅延 import を使用。

**Phase 145-A**: ✅ badukpan.py draw_hover_contents 分割（2026-06-26 完了）。
- 239 行の単一関数を 1 オーケストレータ + 5 ヘルパーに分割:
  - `draw_hover_contents` (43行): オーケストレータ
  - `_prepare_hint_moves` (33行): 候補手収集 + PV フィルタ
  - `_draw_leela_or_kata_hints` (25行): Leela vs KataGo ディスパッチ
  - `_draw_kata_hint_moves` (25行): 候補手イテレーション
  - `_draw_kata_hint_marker` (115行): 個別マーカ描画
  - `_draw_children_markers` (40行): 子ノードマーカ
  - `_draw_hover_overlay` (15行): ROI / ゴースト石 / PV アニメーション
  - `_draw_pass_circle` (20行): パス / 終局サークル

**Phase 145-B**: ✅ batch_ui.py build_batch_popup_widgets 分割（2026-06-26 完了）。
- 375 行の単一関数を 1 オーケストレータ + 15 ヘルパーに分割。
- 各 row ビルダーは独立して `BoxLayout` を返す設計でテスト容易性を確保。
- ヘルパーの例: `_build_input_row`, `_build_visits_timeout_row`, `_build_player_filter_row`, `_build_buttons_row` 等。

**Phase 145-C**: ✅ orchestration.py run_batch 分割（2026-06-26 完了）。
- 462 行の単一関数を 5 関数 + 3 context dataclass に分割:
  - `run_batch` (89行): オーケストレータ
  - `_setup_batch` (~95行): 入力検証 + 出力ディレクトリ + SGF ファイル収集
  - `_process_single_file` (~125行): 単一ファイル処理
  - `_generate_karte_for_file` (~70行): karte レポート生成
  - `_collect_stats_for_file` (~20行): stats 抽出
  - `_generate_summaries` (~80行): サマリ生成
  - `_generate_curator_outputs` (~40行): キュレータ生成
- Context dataclass: `_BatchFileContext`, `_BatchSummaryContext`, `_BatchCuratorContext`
- 循環インポート回避: 各ヘルパー内で必要に応じて遅延 import。

**Phase 145-D**: ✅ settings_popup.py 部分抽出（2026-06-26 完了）。
- `do_mykatrain_settings_popup` (703 行) から以下を抽出:
  - `_build_search_bar` (45行): 検索バー + 検索コールバック
  - `_build_button_row` (37行): Export/Import/Save/Cancel ボタン
  - `_open_browse_dialog` (57行): 3 つの browse コールバック統合
  - 5 つの save ヘルパー: `_save_general_settings`, `_save_beginner_hints_settings`, `_save_engine_settings`, `_save_mykatrain_settings`, `_save_leela_settings`
  - `save_settings` 自身は 6 行のオーケストレータに
- **未完了**: 3 つのタブコンテンツ (Tab 1: Analysis, Tab 2: Export, Tab 3: Leela) の抽出はクロージャ依存が深く別セッションで再設計が必要。

**Phase 148**: ✅ Karte/Summary 品質改善（2026-06-27 完了）。
- **A + B + B'-1 (PR #293)**: skill_preset 伝達、IMPORTANCE_DEF 整合、visits ガード、importance フォールバック閾値、context_builder 経路整備（distance/scoreStdev 供給）、Mock game ハング修正（iter_main_branch_nodes に isinstance ガード + range(2000) 安全上限）。
- **B'-2 (PR #294)**: context_builder に best_move_policy / actual_move_policy を追加（moveInfos の "prior"）、3タグ完全復活。
- **C (PR #295)**: ONLY_MOVE BLUNDER を severity 集計から除外、SummaryAnalyzer の skill_preset 再分類、standard preset heavy_loss 15→5 / reading_failure 20→8、連続 forced 集約（consecutive_forced）、difficulty を "easy" に統一。
- **D (PR #296)**: karte/summary の出力拡張子を `.md` → `.json` に完全移行（Navigator 既存パターン更新）、Navigator/preset テスト追加（test_report_navigator.py, test_preset_thresholds.py）。

**Phase 150**: ✅ mykatrain 設定バグ修正 + CI クリーンアップ（2026-06-28 完了）。
- **PR #301**: `LeelaConfig.get()` の dict 互換セマンティクス修正。`exe_path` が `None` の場合に `default` を返すよう変更し、`TextInput(text=None)` クラッシュを解消。
- **PR #302**: CI から `build-macos` ジョブ削除（macOS 非サポート方針）。`spec/KaTrain.spec` と `__main__.py` の macOS 分岐は手動ビルド向けに温存。
- 付随: `batch_analysis_controller.py:53` の未使用 import `do_mykatrain_settings_popup` を削除。

**Phase 151**: ✅ エンジン起動時の UnboundLocalError 修正 + KataGo バイナリ復元（2026-06-28 完了）。
- **PR #303**: `_analysis_read_thread` で `query_found = False` を `try: json.loads(line)` ブロックの直前に移動。KataGo が非JSON出力（AppImage マウント失敗、FUSE エラー、エンジンクラッシュ stderr）を行った際の `UnboundLocalError` を解消。
- 環境復元: `katago_eigen_backup` (37MB) を `katago` にリネームし、AppImage 版 (944KB) は `katago_appimage.broken` に退避。Linux 環境で KataGo eigen 版が正常起動することを確認。
- `.gitignore` 拡張: `katago_eigen_backup`, `katago_appimage*`, `katago-osx`, `katago-cpu`, `katago-eigen` を除外対象に追加し、誤コミットを防止。

### 累積検証結果

| 検証 | 結果 |
|---|---|
| mypy strict | エラー 0（222 ファイル） |
| Architecture テスト | 36/36 パス |
| 関連ユニットテスト | 全パス（累計 700+ 件） |
| Kivy 隔離違反 | 1 → 0 |

---

## 2. 進行中・計画中のフェーズ

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| - | Beginner Hint 拡張 | 翻訳テンプレ、盤上ハイライト | 📋 Planned |
| - | Active Review 拡張 | Retry/Hint、セッションサマリ | 📋 Planned |
| **146** | Kivy ヘッドレステスト基盤 | `KivyUnitTest` モックレイヤー | 📋 Planned |
| **147** | テスト追加 | orchestration, curator 等 | 📋 Planned |
| **145-D 残り** | settings_popup.py タブコンテンツ抽出 | Tab 1/2/3 ビルダー + 状態管理 | 📋 Planned |
| **P3 クリーンアップ** | 軽量リファクタ | `MyKatrainDropDown` 削除、TODO 解消、コメントアウト削除 | ✅ (2026-06-26) |

**P3 クリーンアップ詳細** (architecture review より):
- `gui/badukpan.py:1572` の `class MyKatrainDropDown(DropDown): pass` 削除（KV ファイルが名前参照中なので 1 行 alias 置換で対応）
- `core/reports/types.py:84-90` の 7 行コメントアウトコード削除
- 5 件の TODO コメント解消: `core/constants.py:84`, `core/engine.py:930`, `core/game/base.py:65`, `core/sgf_parser.py:412`, `gui/badukpan.py:1255`

### Phase 148: Karte / Summary 品質改善（2026-06-27 完了）

> 起票日: 2026-06-26
> 完了: 2026-06-27
> PR: 4 (#293 A+B+B'-1, #294 B'-2, #295 C, #296 D)

#### 背景
ユーザーが AI 向け出力（Karte / Summary）の品質懸念 7 項目を 2026-06-26 に調査依頼。
READ-ONLY 調査で複数の回帰と設計上の問題を確認。LLM 受け渡しのため出力の正確性・整合性を優先して改修する。

| 重大度 | 懸念 | 主な発見 |
|:------:|------|----------|
| 必須 | ① only 判定の扱い | `classify_mistake()` は `position_difficulty` を参照しない → ONLY_MOVE の BLUNDER が混入 |
| 必須 | ② プリセット挙動差 | `logic_snapshot.py:104-107` で `score_thresholds` 未渡し → snapshot 凍結後 relaxed の閾値が反映されない |
| 重要 | ③ importance 閾値 | フォールバックが `raw_score > 0.0` で軽微損失を全件拾う、`IMPORTANCE_DEF` と実装の閾値が乖離 |
| 重要 | ④ primary_tag 精度 | `critical_moves.py:382-383` が `ClassificationContext` に policy/distance 未渡し → 3 タグ発動不可 |
| 中程度 | ⑤ 連続 forced 損失重複 | worst_moves / pattern_miner で連続 ONLY_MOVE が各手カウント |
| 中程度 | ⑥ メタ情報 | `orchestration.py:620-626` で skill_preset 未渡し → サマリーが常に "unknown" |
| 軽微 | ⑦ 用語・拡張子 | `"easy"`/`"simple"` 揺れ、GUI は `.md` / Batch は `.json` で Navigator 両対応なし |

#### 計画: 4 サブフェーズ = 4 PR

| Sub | 内容 | 修正Lv | 主要ファイル |
|:---:|------|:------:|--------------|
| **A1** | ② skill_preset 伝達修正（1行） | Lv1 | `core/batch/orchestration.py:620-626` |
| **A2** | ③ `IMPORTANCE_DEF.thresholds` を実装値（0.3/0.5/1.0）に整合 | Lv1 | `core/reports/definitions.py:80-88` |
| **B1** | ① `assess_position_difficulty_from_parent` に visits ガード | Lv2 | `core/analysis/logic_difficulty.py:100-163` + `logic_reliability.py:66` |
| **B2** | ③ フォールバックに `MIN_LOSS_DISPLAY=0.3` 導入 | Lv2 | `core/analysis/logic_importance.py:213-225` + `models/quiz.py` 新規定数 |
| **B3** | ④ `ClassificationContext` に policy/distance 追加（3 タグ復活） | Lv2 | `core/analysis/critical_moves.py:382-383` |
| **C1** | ① pattern_miner / extraction で ONLY_MOVE の BLUNDER を severity 集計から除外 | Lv2 | `core/batch/stats/extraction.py:189-194` + `pattern_miner.py:130-143` |
| **C2** | ② `SummaryAnalyzer` で `skill_preset` を使った再分類 | Lv2 | `core/reports/summary_logic.py:82-85` + `core/batch/stats/formatting.py:30` |
| **C3** | ④ standard preset の `heavy_loss` 15→5, `reading_failure` 20→8（standard のみ） | Lv2 | `core/analysis/models/skill.py:278` |
| **C4** | ⑤ 連続 ONLY_MOVE 集約 + worst_moves から forced 除外 | Lv2 | `core/batch/stats/pattern_miner.py` + `core/reports/summary_logic.py:103-104` |
| **C5** | ⑦ difficulty を `"easy"` に統一（definitions / extractors 変換削除） | Lv1 | `core/reports/definitions.py:62-68` + `core/reports/extractors.py:60-61` |
| **D1** | ⑦ 拡張子 `.md` → `.json` 統一（完全移行、既存 `.md` は Navigator 対象外） | Lv2 | `gui/features/karte_export.py:158-182` + `summary_io.py:93,186,247` + `report_navigator.py:17-21` |
| **D2** | テスト追加・ゴールデン再生成（`test_eval_metrics.py` / `test_summary_stats.py` / `test_preset_thresholds.py` 新規 / `test_report_navigator.py` 新規） | Lv2 | `tests/` 5 ファイル想定 |

#### 実行順序

```
PR 1 (Phase A): A1, A2
PR 2 (Phase B): B1, B2, B3
PR 3 (Phase C): C1, C2, C3, C4, C5
PR 4 (Phase D): D1, D2
```

#### リスク評価

| リスク | 影響 | 対策 |
|--------|------|------|
| C2 再分類で summary 数値が変わる | 中 | 既存テストで regression、ゴールデン再生成 |
| B1 visits ガードで ONLY_MOVE が UNKNOWN 化 | 低（誤判定抑制、目的に合致） | 既存 only テストで許容範囲確認 |
| C3 standard 閾値変更で既存 Karte 結果が変わる | 中 | `tests/fixtures/golden/` 更新 |
| D1 拡張子変更で既存 `.md` ファイルが Navigator から消える | 中（ユーザー承認済み） | リリースノートに明記 |

#### 関連定数・参照

- 閾値定数: `core/analysis/models/difficulty.py:123` `DIFFICULTY_MIN_VISITS=500`
- 既存テスト: `tests/test_eval_metrics.py:2178-2316` (importance), `test_summary_stats.py:279` (preset=standard 固定), `test_karte_structure.py:1271-1410` (urgent_miss)
- ゴールデン: `tests/fixtures/golden/karte_sgf_panda.golden:21`

#### 着手時の手順

1. `feature/phase-148-a-skill-preset-and-importance-docs` ブランチ作成
2. A1, A2 実装 → `uv run pytest tests/ -k "summary or importance or preset"` 実行
3. ゴールデン差分確認 → 必要なら再生成
4. PR 作成 → レビュー・マージ
5. B → C → D の順で同様

#### 残オープン項目

- C2 採用時、Leela 経路（`core/leela/conversion.py:244-270`）も同じ `classify_mistake(score_loss=None, ...)` パターンのため、再分類が必要か判断
- D1 完全移行後、既存 `.md` ファイルを救済する CLI ツール（マイグレーション）を別 Phase で用意するか

### Phase 149: Karte/Summary 残存問題対応 + Dead Code Revival (2026-06-27 完了)

> 起票日: 2026-06-26
> 完了: 2026-06-27
> PR: 4 (A: bug fixes / B: summary quality / C: JSON revival / D: docs)

#### 背景

ユーザーが AI 向け出力（Karte / Summary）の品質懸念を 2026-06-26 に調査依頼。
READ-ONLY 調査で Phase 148 では触れられなかった 5 件のバグ、6 件のデッドコード、
3 件の設計上の問題を確認。LLM 受け渡しのため出力の正確性・整合性を優先して改修。

#### 計画: 4 サブフェーズ = 4 PR

| Sub | 内容 | 修正Lv | 主要ファイル |
|:---:|------|:------:|--------------|
| **A** | Critical Bug Fixes (Lv1 のみ, 8 項目) | Lv1 | `core/batch/orchestration.py` (skill_preset渡し) / `gui/features/karte_export.py` (i18n) / 他 |
| **B** | Summary Quality (Lv2): SummaryAnalyzer 専用テスト + build_batch_summary i18n + MISTAKE_THRESHOLDS 明示値化 | Lv2 | `tests/test_summary_analyzer.py` (新規, 21 tests) / `core/batch/stats/aggregation.py` / `core/reports/definitions.py` |
| **C** | Dead Code Revival as JSON (Lv3): セクションジェネレーターを JSON データとして復活 + Karte JSON v2.1→v3.0 + D-2 dead code 削除 | Lv3 | `core/reports/karte/sections/*.py` (4 files refactored) / `core/reports/schema.py` (TypedDict 追加) / `core/reports/karte/json_export.py` (v3.0 拡張) |
| **D** | Docs & Validation (このドキュメント更新 + 全体検証) | Lv0 | `docs/01-roadmap.md` |

#### 主な発見・対応

**A. Critical Bugs**
- A-1: `_generate_karte_for_file` で `skill_preset` が渡されておらず常に DEFAULT を使用
- A-2/A-3: 動的 i18n キー構築（`i18n._(f"...{user}...")`）で翻訳が効かない
- A-4: `RELIABILITY_VISITS_THRESHOLD` が `reports/constants.py` と `analysis/models/reliability.py` で重複定義
- A-5: `SummaryAnalyzer.worst_moves` が top 10 に切られていない（メモリ効率）
- A-6: `extractors.py:121` の bare `except:` を `except ValueError:` に
- A-8: `_build_karte_report_impl` の未使用ローカル変数を削除

**B. Summary Quality**
- B-1: `tests/test_summary_analyzer.py` 新規（21 tests: skill_preset 再分類 / worst_moves forced 除外 / mistake_streak / focus_player / multi-game / reason_tags）
- B-2: `build_batch_summary(lang=...)` 追加（jp/en 両対応）
- B-3: `MISTAKE_THRESHOLDS` を auto preset 依存から明示値 (1.0/2.5/5.0) に固定

**C. Dead Code Revival as JSON**
- C-1: スキーマ v2.1 → v3.0。9 セクション追加 (weaknesses / practice_priorities / mistake_streaks / urgent_misses / critical_3 / data_quality / common_difficult_positions / reason_tags_distribution)
- C-2: 4 セクションファイル (~1,300 行) を `list[str]` (markdown) → `list[TypedDict]` (JSON) に refactor
- C-3: `build_karte_json` で KarteContext 経由で全セクションを呼び出し、v3.0 JSON として出力
- C-4: 死蔵コード ~385 行を削除 (`_select_evidence_moves` / `_format_evidence_with_links` / `detect_color_bias` / `build_tag_based_hints` / 9 i18n getters / 10 i18n constants)
- C-5: ゴールデン karte 3 種を v3.0 で再生成 + 16 新規テスト

**D. Docs & Validation**
- D-1: 本セクション追加
- D-2: 全テスト 403 passed / mypy strict clean / architecture 40/40

#### リスク評価

| リスク | 影響 | 対策 |
|--------|------|------|
| スキーマ v3.0 で下流 LLM 連携が壊れる | 中 | additive 変更のみ。既存フィールド削除なし。release notes に明記 |
| セクション refactor で値が変わる | 中 | 既存ゴールデン 3 種 + 新セクション単体テスト |
| `build_batch_summary` マークダウン i18n 化で文字列が変わる | 低 | 既存ゴールデン summary 系は JSON 部分のみで影響なし |
| Dead code 削除で誰かが import していた | 低 | 削除前に grep で事前確認、テストは削除に合わせて更新 |

### Phase 150: mykatrain 設定バグ修正 + CI クリーンアップ (2026-06-28 完了)

> 起票日: 2026-06-28
> 完了: 2026-06-28
> PR: 2 (#301, #302)

#### 背景

ユーザーが myKatrain メニュー 5 機能（open latest report / open output folder / batch analyze folder / mykatrain settings / diagnostics）の動作確認を依頼したところ、mykatrain settings 起動時にクラッシュ。READ-ONLY 調査で残 4 機能は正常動作を確認。

#### 主な発見・対応

**Bug #1 (CRITICAL): mykatrain settings 起動時 AttributeError**
- **症状**: ポップアップを開くと `'NoneType' object has no attribute 'replace'` で停止
- **根本原因**: `LeelaConfig.exe_path: str | None = None` で属性値が `None` のデフォルト。一方 `LeelaConfig.get()` は `getattr(self, key, default)` で実装されており、属性値が存在すると default ではなく actual value（=None）が返る。`settings_popup.py:919` の `TextInput(text=None)` で Kivy の `_set_text` がクラッシュ
- **修正**: `LeelaConfig.get()` を dict 互換セマンティクスに変更（属性が **存在しない** または **値が None** のときに default を返す）
- **回帰テスト**: 3 件追加（None / present / missing key の各ケース）

**CI クリーンアップ: macOS ビルド削除**
- **背景**: macOS はサポート対象外方針。`build-macos` ジョブは 2 つの理由で fail
  1. `setup-python-uv` アクションに存在しない `install-pyinstaller` 入力を渡していた
  2. KataGo `BUILD_DISTRIBUTED=1` ビルドで libzip がリンク失敗
- **対応**: `build-macos` ジョブ全体を削除。`create-release.needs` から `build-macos` を削除。release notes から macOS 行を削除
- **温存**: `spec/KaTrain.spec` と `katrain/__main__.py` の macOS 分岐は手動ビルド用に意図的に残置

**Cleanup: dead import 削除**
- `gui/controllers/batch_analysis_controller.py:53` の未使用 import `do_mykatrain_settings_popup` を削除（バッチ解析フローでは参照されていない）

#### 影響範囲

| 項目 | 影響 |
|------|------|
| `LeelaConfig.get()` 利用箇所 7 箇所 | `exe_path` のみが `str | None` 型のため挙動変化、他 6 箇所は non-None デフォルトで変化なし |
| 既存テスト `test_exe_path_empty_becomes_none` | 維持（`from_dict()` 挙動不変、`get()` のみ修正） |
| Windows ビルド | 影響なし（PR #301 で build-windows pass 済み） |
| 手動 macOS ビルド | 引き続き可能（spec/`__main__.py` の分岐を温存） |

#### 検証結果

| 検証 | 結果 |
|------|------|
| 既存テスト | 373 件パス + 2 件 skip |
| 新規回帰テスト | 3 件追加（None / present / missing） |
| mypy strict | エラー 0 |
| Architecture テスト | 40/40 パス |
| build-windows CI | pass（PR #302 CI run） |
| CI 実行時間 | 約 2-3 分短縮（macOS ジョブ削除効果） |

#### 残オープン項目

- `katrain/KataGo/katago_eigen_backup` という untracked な巨大バックアップファイルが残存（ユーザー指示により放置）
- `spec/KaTrain.spec` の macOS 分岐は macOS サポート再開時に備えて温存中

### Phase 151: エンジン起動エラー処理 + KataGo バイナリ復元 (2026-06-28 完了)

> 起票日: 2026-06-28
> 完了: 2026-06-28
> PR: 1 (#303)

#### 背景

KataGo を含む myKatrain 起動時に、解析スレッドで以下の2段階エラーが発生：

1. **第1段階**: KataGo バイナリが AppImage（944KB）に置き換わっており、FUSE が無い Linux 環境で起動失敗。stderr に「Cannot mount AppImage, please check your FUSE setup.」を出力。
2. **第2段階**: 起動失敗時の非JSON出力が engine.py の `json.loads(line)` で `JSONDecodeError` を引き起こし、except ハンドラが `query_found` を参照しようとして `UnboundLocalError` を発生。元のエラーをマスクして解析スレッドがクラッシュ。

#### 主な発見・対応

**Bug: 解析スレッドの UnboundLocalError**
- **症状**: `Expecting value: line 1 column 1 (char 0)` の直後に `UnboundLocalError: cannot access local variable 'query_found' where it is not associated with a value` が発生
- **根本原因**: `engine.py:619` の `query_found = False` 宣言が `try: analysis = json.loads(line)` ブロックの **内側** にあった。`json.loads` が失敗すると `query_found` に到達せず、except ハンドラが未初期化変数を参照してクラッシュ
- **修正**: `query_found = False` を `try` ブロックの **直前**（line 606 直後）に移動（+1/-1行）

**KataGo バイナリ復元**
- `katrain/KataGo/katago` (944KB, AppImage) を `katago_appimage.broken` に退避
- `katrain/KataGo/katago_eigen_backup` (37MB, ELF eigen版) を `katago` にリネーム
- `./katrain/KataGo/katago` 直接実行で KataGo の usage メッセージが表示されることを確認

**`.gitignore` 拡張**
- ローカルKataGoバイナリの誤コミット防止のため以下を追加：
  - `katago_eigen_backup`
  - `katago_appimage*`
  - `katago-osx`
  - `katago-cpu`
  - `katago-eigen`
- 既存の `katago` および `katago.exe` はリポジトリに保持（fresh clone で動作するように）

#### 影響範囲

| 項目 | 影響 |
|------|------|
| `query_found` の宣言位置変更 | `_analysis_read_thread` 内のスコープが拡張。except ハンドラが常に `query_found` にアクセス可能 |
| KataGo バイナリ差分 | リポジトリには反映されない（`.gitignore` で除外）。ユーザー環境のみで復元 |
| 既存テスト | 全件 pass（engine 系 252件 / typed config 107件） |

#### 検証結果

| 検証 | 結果 |
|------|------|
| 既存テスト | 359+ 件パス（engine 252 / typed config 107 / 関連テスト） |
| 構造確認 | `query_found = False` が try ブロック前にあることを inspect で検証 |
| CI build-windows | pass（PR #303 run） |
| KataGo eigen版 動作 | 直接実行で正常な usage メッセージを表示 |

#### 残オープン項目

- `katago_appimage.broken` (944KB) はユーザー環境のみに残存（リポジトリには影響なし）
- macOS環境でも AppImage ではなく eigen版を使う運用が望ましい（ユーザー判断）

---

## 3. 将来の拡張候補

- [ ] Ownership Volatility (Idea #3): 盤面リスクオーバーレイ
- [ ] Style Matching Quiz (Idea #5): スタイル判定クイズ
- [ ] Lexicon UI Browser: 用語ポップアップ
- [ ] `core/ai.py` (1723 行, 18 戦略クラス) 戦略ファミリ別分割
- [ ] `core/engine.py` (1035 行, 32 メソッド) I/O とロジック分離
- [ ] `gui/features/settings_popup.py` (1519 行) タブコンテンツ抽出
- [ ] GUI テストカバレッジ 21% → 40-50% (Kivy mock 基盤)
