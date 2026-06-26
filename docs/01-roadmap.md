# myKatrain（PC版）ロードマップ

> 最終更新: 2026-06-26(Phase 145-D完了)
> 固定ルールは `00-purpose-and-scope.md` を参照。
> 過去の履歴（Phase 1-130）は [ROADMAP_HISTORY.md](./archive/ROADMAP_HISTORY.md) を参照。
> Phase 138-145 の詳細は [architecture-review-2026-06-26.md](./archive/architecture-review-2026-06-26.md) を参照。

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

---

## 3. 将来の拡張候補

- [ ] Ownership Volatility (Idea #3): 盤面リスクオーバーレイ
- [ ] Style Matching Quiz (Idea #5): スタイル判定クイズ
- [ ] Lexicon UI Browser: 用語ポップアップ
- [ ] `core/ai.py` (1723 行, 18 戦略クラス) 戦略ファミリ別分割
- [ ] `core/engine.py` (1035 行, 32 メソッド) I/O とロジック分離
- [ ] `gui/features/settings_popup.py` (1519 行) タブコンテンツ抽出
- [ ] GUI テストカバレッジ 21% → 40-50% (Kivy mock 基盤)
