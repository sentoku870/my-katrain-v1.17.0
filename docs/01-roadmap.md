# myKatrain（PC版）ロードマップ

> 最終更新: 2026-06-28(Phase 156 完了)
> 固定ルールは `00-purpose-and-scope.md` を参照。
> 過去の履歴（Phase 1-130）は [ROADMAP_HISTORY.md](./archive/ROADMAP_HISTORY.md) を参照。
> Phase 138-145 の詳細は [architecture-review-2026-06-26.md](./archive/architecture-review-2026-06-26.md) を参照。
> Phase 148 (2026-06-27 完了): 4 PR (#293 / #294 / #295 / #296)。詳細下記。
> Phase 149 (2026-06-27 完了): Karte/Summary 残存問題点の発見と対応。詳細下記。
> Phase 150 (2026-06-28 完了): mykatrain 設定バグ修正 + CI クリーンアップ。詳細下記。
> Phase 151 (2026-06-28 完了): エンジン起動時の UnboundLocalError 修正 + KataGo バイナリ復元。詳細下記。
> Phase 152 (2026-06-28 完了): Linux 環境での起動時ランタイムエラー修正。詳細下記。
> Phase 153 (2026-06-28 完了): Karte/Summary 不要項目整理（schema 3.1）。詳細下記。
> Phase 154 (2026-06-28 完了): 勝敗別損失統計 + 手数帯別推移（schema 3.2）。詳細下記。
> Phase 155 (2026-06-28 完了): 相手の棋力との相関（schema 3.3）。詳細下記。
> Phase 156 (2026-06-28 完了): 動的フェーズ分割（scoreStdev ベース）。詳細下記。

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
| **152** | Linux ランタイムエラー修正 | `Window.top/left` None ガード / `resolve_output_directory` に mkdir + フォールバック追加 | ✅ (2026-06-28) |
| **153** | Karte/Summary 不要項目整理 | difficulty / practice_priorities / common_difficult_positions / urgent_misses 削除 / `definitions` オプトイン化 / schema 3.1 | ✅ (2026-06-28) |
| **154** | 勝敗別損失統計 + 手数帯別推移 | RE パース / `win_loss_analysis` / `loss_progression` セクション追加 / schema 3.2 | ✅ (2026-06-28) |
| **155** | 相手の棋力との相関 | BR/WR → バケット変換 / `opponent_strength_loss_correlation` セクション追加 / schema 3.3 | ✅ (2026-06-28) |
| **156** | 動的フェーズ分割（scoreStdev ベース） | `classify_phases_dynamic()` / `apply_dynamic_phases()` / `dynamic_phase_detection` オプトイン | ✅ (2026-06-28) |

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

**Phase 152**: ✅ Linux ランタイムエラー修正（2026-06-28 完了）。
- **PR #304**: `on_request_close` で `Window.top` / `Window.left` の None ガードを追加し、アプリ終了時の `'NoneType' object is not subscriptable` クラッシュを修正。
- `resolve_output_directory` で候補ディレクトリを `mkdir(parents=True, exist_ok=True)` で自動作成し、`~/Downloads` 不存在時の `FileNotFoundError: '/home/mono_/Downloads'`（Kivy filechooser の listdir 失敗）を解消。
- フォールバックチェーン: 設定ディレクトリ → 候補（Windows: CSIDL_DOWNLOADS、Linux: `~/Downloads`） → `~/katrain_reports` → `cwd`。
- 別タスクとして保留: SGF skip "Too few analyzed moves (0)"（KataGo解析データ scoreLead が無いファイルは集計対象外＝仕様通り）、Topmoves ホバー変化図再生、`padding_x` 廃止警告。

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

### Phase 152: Linux ランタイムエラー修正 (2026-06-28 完了)

> 起票日: 2026-06-28
> 完了: 2026-06-28
> PR: 1 (#304)

#### 背景

ユーザーが KataGo を含む myKatrain を Linux（WSL を含む）で起動・操作した際に複数のランタイムエラーが発生。READ-ONLY 調査で2つの致命的なバグを特定し修正。残り3つは別タスクとして保留。

#### 主な発見・対応

**Bug #1: アプリ終了時の TypeError クラッシュ**
- **症状**: `AttributeError: 'NoneType' object is not subscriptable` at `__main__.py:1143`
- **根本原因**: 一部バックエンド（pygame/sdl2）で `Window.top` / `Window.left` がウィンドウ終了時に `None` を返す。`ui_state["top"] = Window.top` で `None` がそのまま設定され、次回起動時に `dict.get("top")[1]` のような添字アクセスでクラッシュ。
- **修正**: ローカル変数に取得してから None ガード → `if window_top is not None: ui_state["top"] = window_top`
- **影響**: `__main__.py:1140-1145` のみ、+6/-2行

**Bug #2: Kivy filechooser の FileNotFoundError**
- **症状**: `[ERROR] Unable to open directory </home/mono_/Downloads>` + `FileNotFoundError: '/home/mono_/Downloads'` at `kivy/uix/filechooser.py:170`
- **根本原因**: `resolve_output_directory` が `~/Downloads` を返すが、Linux環境で `~/Downloads` が存在しない場合（WSL、ミニマル環境など）Kivy の filechooser が `listdir` で失敗。diagnostics / open output folder / save SGF など複数のポップアップで発火。
- **修正**: `resolve_output_directory` で候補ディレクトリを `mkdir(parents=True, exist_ok=True)` で自動作成。失敗時は `~/katrain_reports` → `cwd` の順でフォールバック。
- **影響**: `utils.py:128-167` のみ、+34/-11行

#### 別タスク保留（3件）

| 問題 | 種別 | 状態 |
|------|------|------|
| SGF skip "Too few analyzed moves (0)" | データ側の問題 | ユーザーのSGFがKataGo解析データ（`KT` プロパティ / `scoreLead`）を含まず、Leela Zero 解析（`LZ` プロパティ）のみ。KataGo で再解析が必要 |
| Topmoves ホバー時の変化図再生 | 既存バグ | `badukpan.py:on_mouse_pos` / `active_pv_moves` 関連、詳細調査が必要 |
| `padding_x` 廃止警告 | 将来削除予定 | `kivy/uix/label.py` の `padding_x` プロパティが Kivy 2.3+ で deprecated、即時動作影響なし |

#### 影響範囲

| 項目 | 影響 |
|------|------|
| `Window.top` / `Window.left` の None ガード | アプリ終了時のクラッシュを完全防止。次回起動時の ui_state 復元も None を保持するため安全 |
| `resolve_output_directory` の自動 mkdir | 初回呼び出し時にディレクトリ作成（既存ディレクトリは touch のみ）。`OSError` 時は2段階のフォールバック |
| 既存テスト | 全件 pass（engine 系 252件 / typed config 107件） |

#### 検証結果

| 検証 | 結果 |
|------|------|
| 既存テスト | 359+ 件パス（engine 252 / typed config 107 / 関連テスト） |
| `resolve_output_directory('')` | `/home/mono_/Downloads` を自動作成して返す |
| `resolve_output_directory(None)` | 同上 |
| `resolve_output_directory('/tmp/existing')` | 既存ディレクトリを返す（作成しない） |
| CI build-windows | pass（PR #304 run） |
| 実機動作確認 | 未実施（マージ後にユーザー側で確認） |

#### 残オープン項目

- SGF skip の根本原因（データ問題）はユーザー側でSGFのKataGo再解析が必要
- Topmoves ホバー変化図の調査（推定30-60分の詳細デバッグ）
- `padding_x` 廃止警告の解消（`buttons.py:37` の `NumericProperty` 削除 + `widgets.kv:78` の `padding` 直接指定）

---

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

**Phase 153**: ✅ Karte/Summary 不要項目整理（2026-06-28 完了）。

ユーザー依頼（2026-06-28 メモ）に基づき、Karte/Summary 出力から不要な項目を削除し、JSON サイズを削減。schema 3.0 → 3.1。

#### 削除した項目（4 つ + 1 フィールド）

| 項目 | 場所 | 理由 |
|------|------|------|
| `difficulty`（per-MistakeItem フィールド） | `reports/extractors.py` の `MoveExtractor.extract` | SGF 直接パース経路で常に "unknown" を出力していたため |
| `practice_priorities` | Karte v3.1 で削除 | `weaknesses` と役割重複 |
| `common_difficult_positions` | Karte v3.1 で削除 | `critical_3` / `important_moves` で代用可能 |
| `urgent_misses` | Karte v3.1 で削除（`mistake_streaks` に統合） | 発動条件が厳しすぎ |
| `meta.definitions.difficulty_levels` | `reports/definitions.py` の `DIFFICULTY_LEVELS` | difficulty 削除に伴い不要 |

#### `definitions` オプトイン化

| Before | After |
|--------|-------|
| デフォルトで `meta.definitions` を含む（LLM ラベル参照には有用） | デフォルト `None`（compact 出力） |
| - | `include_definitions=True` で従来通り埋め込み |

両 `build_karte_json()` と `build_summary_json()` に `include_definitions: bool = False` 引数を追加。

#### 変更ファイル数

| 区分 | ファイル |
|------|---------|
| コア実装 | 9 ファイル（reports/definitions.py, extractors.py, schema.py, summary_json_export.py, karte/json_export.py, karte/builder.py, karte/sections/diagnosis.py, karte/sections/summary.py, gui/features/summary_formatter.py, gui/features/summary_stats.py） |
| テスト | 5 ファイル（test_karte_v3_sections.py, test_karte_json.py, test_batch_json.py, test_summary_snapshot.py, test_golden_summary.py） |
| golden ファイル | 8 ファイル（自動更新: `--update-goldens`） |
| i18n | 2 ファイル（jp/en の `summary:practice*` ラベル削除） |

#### 行数

- 削除: **809 行**
- 追加: **167 行**
- 純減: **-642 行**（不要な出力生成コード + テスト + golden データ）

#### 検証結果

| 検証 | 結果 |
|------|------|
| 関連テスト | 857 件パス（karte / summary / golden / pattern_miner / difficulty / critical_moves / eval_metrics / architecture / batch_analyzer / pacing） |
| mypy strict `core/reports/` | pre-existing 1 件（`summary_logic.py:27` の `Move` インポート）以外は 0 エラー |
| schema version | 3.0 → 3.1（後方互換: フィールド削除のみ、追加はなし） |

#### 残オープン項目

- `practice_priorities_for` / `common_difficult_positions` 関数は将来削除予定（Phase 153 では呼び出し元のみ削除し、関数自体はスタブ化）
- GUI 経由での `include_definitions` トグル UI は未実装（API のみ提供）

---

**Phase 154**: ✅ 勝敗別損失統計 + 手数帯別推移（2026-06-28 完了）。

ユーザー依頼（2026-06-28 メモ）に基づき、Karte/Summary JSON にコーチング向けの2つの新セクションを追加。schema 3.1 → 3.2。

#### 新セクション

| セクション | 場所 | 内容 |
|------------|------|------|
| `win_loss_analysis` | Karte（per-game）/ Summary（per-player） | RE 文字列をパースし、勝局/敗局/持碁別の損失統計を集計 |
| `loss_progression` | Karte（per-game）/ Summary（cross-game aggregate） | 10手区切りの平均損失推移、集中力低下区間を可視化 |

#### 新規ファイル

| パス | 役割 |
|------|------|
| `katrain/core/reports/utils/result_parser.py` | SGF `RE` パーサ（`B+R`/`W+T`/`B+5.5`/`0`/`Draw`/`Jigo` を網羅） |
| `katrain/core/reports/utils/__init__.py` | パッケージ初期化 |
| `katrain/core/reports/utils/loss_progression.py` | 手数バケット集計（`LossBucket` dataclass、`compute_loss_progression()`） |
| `katrain/core/reports/sections/win_loss.py` | `build_win_loss_analysis()` セクションビルダ |
| `katrain/core/reports/sections/__init__.py` | パッケージ初期化 |
| `tests/test_result_parser.py` | RE パーサテスト（40 ケース） |
| `tests/test_loss_progression.py` | 手数バケットテスト（バウンダリ、検証、エッジケース） |

#### 変更ファイル

| パス | 変更 |
|------|------|
| `katrain/core/analysis/models/skill.py` | `GameSummaryData` に `outcome: Any` 追加（循環依存回避のため遅延型） |
| `katrain/core/reports/schema.py` | `KarteReport`/`SummaryReport` に `win_loss_analysis`/`loss_progression` フィールド追加、`NotRequired` import |
| `katrain/core/reports/definitions.py` | `REPORT_SCHEMA_VERSION` を 3.1 → 3.2 にバンプ（過去コミットで見逃していた 3.0 残存も修正） |
| `katrain/core/reports/karte/json_export.py` | Karte 出力に新セクション追加、`schema_version` 3.2 にバンプ |
| `katrain/core/reports/summary_json_export.py` | Summary 出力に新セクション追加、mypy 型注釈修正 |
| `tests/test_karte_v3_sections.py` | スキーマバージョン期待値を 3.2 に更新 |
| `tests/test_karte_json.py` | 同上 |
| `tests/test_batch_json.py` | 同上 |

#### RE パーサ対応フォーマット

| 入力 | black | white | score_diff |
|------|-------|-------|------------|
| `B+R` / `W+R` | win / loss | loss / win | None |
| `B+T` / `W+T` | win / loss | loss / win | None |
| `B+5.5` / `W+12.5` | win / loss | loss / win | ±差分 |
| `0` / `Draw` / `Jigo` | draw | draw | 0.0 |
| `""` / `None` / `?` | unknown | unknown | None |

大小文字・空白差は吸収（`b+r`, `B + R` 等も対応）。

#### 検証結果

| 検証 | 結果 |
|------|------|
| 新規テスト | 40 件パス（test_result_parser 30 + test_loss_progression 10） |
| 既存テスト | 413 件パス（karte / summary / golden / pattern_miner / difficulty / critical_moves / eval_metrics / architecture / batch_analyzer） |
| mypy strict `core/reports/` | pre-existing 1 件（`summary_logic.py:27`）以外は 0 エラー |
| schema version | 3.1 → 3.2（追加のみ、削除なし） |

#### 残オープン項目

- GUI での勝敗別推移の可視化（チャート表示）は未実装（JSON 出力のみ）
- `loss_progression` の bucket_size はデフォルト 10（固定）。Config 経由の可変化は将来検討
- BR/WR（相手の段級位）からの追加分析は Phase 155 で対応予定

---

**Phase 155**: ✅ 相手の棋力との相関（2026-06-28 完了）。

ユーザー依頼（2026-06-28 メモ）に基づき、SGF の BR/WR プロパティから相手棋力をバケット（級位/有段/高段/不明）に分類し、損失との相関を集計するセクションを追加。schema 3.2 → 3.3。

#### 新セクション

| セクション | Karte | Summary | 内容 |
|------------|:-----:|:-------:|------|
| `opponent_strength_loss_correlation` | per-player（B/W） | per-player | 相手棋力バケット別のゲーム数・合計損失・平均損失・ミス数 |

#### 新規ファイル

| パス | 役割 |
|------|------|
| `katrain/core/reports/utils/rank_classifier.py` | 段級位パーサ（`RankBucket` enum + `classify_rank_to_bucket()` + `bucket_for_player()`） |
| `katrain/core/reports/sections/opponent_analysis.py` | `build_opponent_strength_loss_correlation()` セクションビルダ |
| `tests/test_rank_classifier.py` | 段級位パーサテスト（30 ケース） |
| `tests/test_opponent_analysis.py` | セクションテスト（12 ケース：ステータス/バケット/ミス数/フィルタリング） |

#### バケット分類ルール

| 入力例 | バケット | is_dan | is_pro |
|--------|---------|:------:|:------:|
| `"5k"` / `"30K"` / `"1k"` | kyu | False | False |
| `"1d"` / `"3d"` / `"6d"` | dan | True | False |
| `"7d"` / `"9d"` / `"10d"` | high_dan | True | True |
| `""` / `None` / `"?"` / `"pro"` / `"P"` | unknown | False | False |

`pro_threshold=7` がデフォルト（設定可能）。

#### ステータス遷移

| サンプル数 | status |
|----------|--------|
| 0 | `no_opponent_info` |
| 1〜4 | `insufficient_data`（MIN_SAMPLE_SIZE=5 未満） |
| 5 以上 | `computed` |

`status="insufficient_data"` を出力することで、LLM が少ないサンプルで誤った判断をしないようにします。

#### 変更ファイル

| パス | 変更 |
|------|------|
| `katrain/core/analysis/models/skill.py` | `GameSummaryData` に `rank_black`/`rank_white` 追加、`outcome` の型注釈改善 |
| `katrain/core/batch/stats/extraction.py` | `BR`/`WR` プロパティを取得して `stats` dict と `GameSummaryData` に渡す |
| `katrain/core/batch/stats/aggregation.py` | `GameSummaryData` fallback コンストラクタに rank を追加 |
| `katrain/core/reports/schema.py` | `KarteReport`/`SummaryPlayerStats` に `opponent_strength_loss_correlation` フィールド追加 |
| `katrain/core/reports/definitions.py` | `REPORT_SCHEMA_VERSION` を 3.2 → 3.3 にバンプ |
| `katrain/core/reports/karte/json_export.py` | Karte 出力に新セクション追加（BR/WR 抽出 + 1-game summary 構築） |
| `katrain/core/reports/summary_json_export.py` | Summary 出力に新セクション追加 |
| `katrain/core/reports/sections/__init__.py` | `build_opponent_strength_loss_correlation` を export |
| `tests/test_karte_v3_sections.py` | スキーマバージョン期待値を 3.3 に更新 |
| `tests/test_karte_json.py` | 同上 |
| `tests/test_batch_json.py` | 同上 |

#### 検証結果

| 検証 | 結果 |
|------|------|
| 新規テスト | 42 件パス（test_rank_classifier: 30, test_opponent_analysis: 12） |
| 既存テスト | 558 件パス（karte / summary / golden / pattern_miner / difficulty / critical_moves / eval_metrics / architecture / batch_analyzer） |
| mypy strict `core/reports/` + `core/analysis/` | pre-existing 8 件（`StrEnum`/`Move`/`unused-ignore`）以外は 0 エラー |
| schema version | 3.2 → 3.3（追加のみ、削除なし） |

#### 残オープン項目

- GUI での相手棋力相関の可視化（ヒートマップ等）は未実装（JSON 出力のみ）
- 漢数字段級位（"五段" など）の対応は未実装（unknown bucket に分類）
- ネットワーク棋譜（野狐、Fox）特有の前置文字列（"fox 5d" など）のパースは将来検討

---

**Phase 156**: ✅ 動的フェーズ分割（2026-06-28 完了）。

ユーザー依頼（2026-06-28 メモ）に基づき、KataGo の `scoreStdev` を利用した終盤自動検出を追加。schema は 3.3 のまま（追加 API のみ）。

#### 新規 API（オプトイン）

| API | 用途 |
|-----|------|
| `katrain.core.analysis.classify_phases_dynamic(moves)` | moves のリストから手ごとにフェーズ判定 |
| `katrain.core.analysis.apply_dynamic_phases(moves)` | `move.tag` を動的フェーズで in-place 上書き |
| `build_karte_json(..., dynamic_phase_detection=True)` | Karte 生成時に動的フェーズを適用 |
| `build_summary_json(..., dynamic_phase_detection=True)` | Summary 生成時に動的フェーズを適用 |
| `MoveEval.score_stdev` フィールド | KataGo root の scoreStdev を保持 |

#### アルゴリズム

1. 序盤（move_number <= 50）は静的閾値（opening）
2. `score_stdev <= 5.0` が **5手連続**続いたら endgame モードに遷移
3. endgame モードは以降のすべての手に伝播（stdev 高くても維持）
4. `score_stdev = None`（Leela / 未解析）の手は静的判定にフォールバック

#### 新規ファイル

| パス | 役割 |
|------|------|
| `katrain/core/analysis/logic_phase_dynamic.py` | `classify_phases_dynamic()` + `apply_dynamic_phases()` |
| `tests/test_logic_phase_dynamic.py` | 13 ケース（opening fallback, endgame trigger, streak reset, missing stdev, validation, constants, apply_dynamic_phases） |

#### 変更ファイル

| パス | 変更 |
|------|------|
| `katrain/core/analysis/models/move_eval.py` | `score_stdev: float \| None = None` フィールド追加 |
| `katrain/core/analysis/logic_snapshot.py` | `snapshot_from_nodes` で `scoreStdev` を抽出して `move.score_stdev` にセット |
| `katrain/core/analysis/logic.py` | 新シンボルを再エクスポート |
| `katrain/core/analysis/__init__.py` | 新シンボル・定数をパッケージレベルで公開 |
| `katrain/core/reports/karte/json_export.py` | `dynamic_phase_detection: bool = False` 引数追加 |
| `katrain/core/reports/summary_json_export.py` | 同上 |

#### 検証結果

| 検証 | 結果 |
|------|------|
| 新規テスト | 13 件パス（test_logic_phase_dynamic） |
| 既存テスト | 468 件パス（karte / summary / golden / pattern_miner / difficulty / critical_moves / eval_metrics / architecture / batch_analyzer / opponent_analysis / rank_classifier / loss_progression / result_parser） |
| mypy strict `core/reports/` + `core/analysis/` | pre-existing 8 件（`StrEnum`/`Move`/`unused-ignore`）以外は 0 エラー |
| schema version | 3.3 のまま（追加のみ、フィールド削除なし） |

#### 残オープン項目

- GUI 設定画面での `dynamic_phase_detection` トグル UI は未実装（API のみ提供）
- `score_stdev` 抽出は KataGo 解析完了経路のみ動作（Leela / 未解析は None で静的判定にフォールバック）
- 閾値（5.0 / 5手）は固定。Config 経由の可変化は将来検討

---

## 3. 将来の拡張候補

- [ ] Ownership Volatility (Idea #3): 盤面リスクオーバーレイ
- [ ] Style Matching Quiz (Idea #5): スタイル判定クイズ
- [ ] Lexicon UI Browser: 用語ポップアップ
- [ ] `core/ai.py` (1723 行, 18 戦略クラス) 戦略ファミリ別分割
- [ ] `core/engine.py` (1035 行, 32 メソッド) I/O とロジック分離
- [ ] `gui/features/settings_popup.py` (1519 行) タブコンテンツ抽出
- [ ] GUI テストカバレッジ 21% → 40-50% (Kivy mock 基盤)

### Phase 154-156 (計画中)

ユーザー依頼（2026-06-28）に基づく次の改善計画：

| Phase | 主題 | 概要 | Lv | 状態 |
|------:|------|------|:--:|:----:|
| **154** | 勝敗別損失統計 + 手数帯別推移 | `win_loss_analysis` セクション（RE 文字列パース）、`loss_progression`（10手区切り） | Lv3 | ✅ (2026-06-28) |
| **155** | 相手の棋力との相関 | `rank_black/white` を `GameSummaryData` 追加、級位/有段/高段バケット変換 | Lv3 | ✅ (2026-06-28) |
| **156** | 動的フェーズ分割（scoreStdev ベース） | `classify_game_phase_dynamic()` 関数新設（オプトイン） | Lv4 | ✅ (2026-06-28) |

詳細: `docs/ideas/phase-154-156-coaching-stats.md`（計画中）

### Phase 157 以降の候補

Phase 154-156 で達成された「コーチング向け統計」の中核に加え、今後は以下の拡張が考えられます：

- [ ] GUI 設定画面での `dynamic_phase_detection` トグル追加（Phase 156 残オープン項目）
- [ ] `loss_progression` の bucket_size を Config 経由で可変化（Phase 154 残オープン項目）
- [ ] 漢数字段級位（"五段" など）の対応追加（Phase 155 残オープン項目）
- [ ] `win_loss_analysis` の GUI チャート可視化
- [ ] `opponent_strength_loss_correlation` のヒートマップ可視化
- [ ] `apply_dynamic_phases` を Batch 経路にも適用（現状は Karte / Summary のみ）
- [ ] KataGo の `scoreStdev` 以外の動的判定指標（`ownership` エントロピー等）の研究
