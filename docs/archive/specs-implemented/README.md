# 設計仕様書 (Design Specifications)

このフォルダにはmyKaTrainの機能設計仕様書を格納しています。

> **最終更新**: 2026-07-15（Phase 226 + Phase 227 + Phase 228 + Phase 229 完了）
> Phase 171 で Leela エンジン / 関連スペックを完全削除。KataGo 専用の構成に整理。

---

## Phase 45–52 関連仕様書

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [idea1-meaning-tags.md](idea1-meaning-tags.md) | Phase 46-47 | MeaningTags: ミスの「意味」自動タグ付け |
| [idea2-radar-tier.md](idea2-radar-tier.md) | Phase 48-49, 51 | 5軸レーダーチャートとTier判定 |
| [idea4-critical3-focused-review.md](idea4-critical3-focused-review.md) | Phase 50 | Critical 3: 一点集中レビューモード |
| [lexicon-integration.md](lexicon-integration.md) | Phase 45 | go_lexicon_master_last.yaml活用設計 |
| [summary-improvements.md](summary-improvements.md) | Phase 47, 49 | Summary改善案（5軸レーダー、意味的診断） |
| [karte-improvements.md](karte-improvements.md) | Phase 47, 50 | Karte改善案（信頼度ゲート、敗着特定） |
| [common-improvements.md](common-improvements.md) | Phase 47-50 | カルテ・サマリー共通改善（動的閾値、LLMプロンプト埋め込み） |

## 延期された仕様（Post-52）

| ファイル | 内容 |
|----------|------|
| [idea3-ownership-overlay-DEFERRED.md](idea3-ownership-overlay-DEFERRED.md) | Ownership Volatility Overlay（危険度可視化） |
| [idea5-style-quiz-DEFERRED.md](idea5-style-quiz-DEFERRED.md) | Style Matching Quiz（スタイル一致クイズ） |

## その他の初期仕様書

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [muzero-difficulty.md](muzero-difficulty.md) | Phase 12 | MuZero 3分解難易度 |
| [smart-kifu-learning.md](smart-kifu-learning.md) | Phase 13, 28 | Smart Kifu Learning |
| [human-move-filter.md](human-move-filter.md) | Phase 11 | Human Move Filter |

## Phase 80-94 完了済みスペック

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [phase80-82-ownership-consequence.md](phase80-82-ownership-consequence.md) | Phase 80-82 | Ownership Consequence: Ownership 変動による死に石 / 地損 / 仕留め損ないの自動分類 |
| [phase83-complexity-filter.md](phase83-complexity-filter.md) | Phase 83 | Complexity Filter（局面複雑度フィルタ） |
| [phase84-85-pattern-mining.md](phase84-85-pattern-mining.md) | Phase 84-85 | Recurring Pattern Mining（反復パターン抽出） |
| [phase86-reason-generator.md](phase86-reason-generator.md) | Phase 86 | Reason Generator（理由生成器） |
| [phase88-90-katago-setup-rescue.md](phase88-90-katago-setup-rescue.md) | Phase 88-90 | KataGo Setup Rescue（自動セットアップ救済） |
| [phase91-92-beginner-hints.md](phase91-92-beginner-hints.md) | Phase 91-92 | Beginner Hints MVP（初心者向けヒント） |
| [phase93-94-active-review.md](phase93-94-active-review.md) | Phase 93-94 | Active Review MVP（能動的レビュー） |

### Phase 80-94 で部分実装のみ（Future 参照）

- **Phase 82**: `docs/future/phase82-context-filler.md` — Critical 3 コンテキスト自動生成（`situation_type` 分類器の GUI 統合が残作業）

## Phase 177-195-A 完了済みスペック（2026-07）

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [phase177-kifunarabe.md](phase177-kifunarabe.md) | Phase 177-178 | 棋譜並べ（kifunarabe）機能 |
| [phase179-hints-summary-extension.md](phase179-hints-summary-extension.md) | Phase 179 + 179.1 + 179.2 | Beginner Hints Summary Extension（ミス・自由度・難易度） |
| [phase187-hint-main-coverage.md](phase187-hint-main-coverage.md) | Phase 187 | Beginner Hints Main Pipeline カバレッジ 16.5% → 97% |
| [phase188-kifunarabe-controller-split.md](phase188-kifunarabe-controller-split.md) | Phase 188 | Kifunarabe Controller God Class 分割（4 mixin + facade） |
| [phase189-auto-setup-coverage.md](phase189-auto-setup-coverage.md) | Phase 189 | Auto Setup Module カバレッジ 9.8% → 97% |
| [phase190-engine-coverage.md](phase190-engine-coverage.md) | Phase 190 | `core/engine.py` カバレッジ 48.3% → 83% |
| [phase191-engine-type-cycle-cleanup.md](phase191-engine-type-cycle-cleanup.md) | Phase 191 | Engine Subsystem TYPE_CHECKING 循環解消 |
| [phase192-logic-difficulty-subpackage.md](phase192-logic-difficulty-subpackage.md) | Phase 192 | Position Difficulty サブパッケージ化 |

### Phase 194 / 195-A（直近）

- **Phase 194**（MagicMock 汚染除去）: `katrain/core/reports/extractors.py` から `unittest.mock.MagicMock` の production import を排除、`tests/test_extractors.py` を新規 26 件追加。コミット前に仕様書ファイルは未作成（本表も Phase 201 で更新）。
- **Phase 195-A**（互換シム棚卸し）: `logic_difficulty.py` / `karte_report.py` の deprecated シム参照を production code から脱却。Architecture テスト `TestDeprecatedShimIsolation` を 3 件追加。eval_metrics / batch_analyze_sgf シムは Phase 195-C まで保持。

## Phase 225-227 完了済みスペック（2026-07）

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [phase225-llm-coach-gui.md](phase225-llm-coach-gui.md) | Phase 225 | LLM Coach GUI 統合（手動貼付ワークフロー） |
| [phase225-master.md](phase225-master.md) | Phase 225 + 225.1-225.8 | LLM Coach 統合マスター索引 |
| [phase227-llm-coach-multi-game.md](phase227-llm-coach-multi-game.md) | Phase 227-A〜E | LLM コーチ複数局対応（B案フル実装: summary_prompt_builder / summary_validator / popup タブ化 + 視点セレクタ + 集約サマリボタン / calibration fixtures） |
| [phase228-summary-schema-adapt.md](phase228-summary-schema-adapt.md) | Phase 228-A〜D | LLM コーチ複数局対応 - 実シェーマ適応（extractors / prompt builder / validator / real_shape fixtures） |

## Phase 171 で削除されたスペック

以下のスペックは Phase 171（Leela エンジン完全削除）で実装と共に削除されました。git log で参照可能：

- `leela-estimated-loss.md`（Phase 14.0-14.7）— Leela推定損失
- `leela-output-format.md`（Phase 14.0）— Leela Zero lz-analyze 出力フォーマット

---

## 固定決定事項（Decisions Fixed for Phase 45–52）

| 決定事項 | 解決 |
|----------|------|
| **Lexiconデータソース** | `go_lexicon_master_last.yaml` が正本 |
| **Lexicon言語** | EN/JP のみ（既存YAMLフィールド） |
| **Radar軸** | `opening`, `fighting`, `endgame`, `stability`, `awareness` |
| **Radarスコア** | 内部: 0.0–1.0、表示: 1.0–5.0 |
| **Tier名** | Tier 1-5（入門/初級/中級/上級/高段） |
| **MeaningTag↔Lexicon** | `lexicon_anchor_id: Optional[str]` でYAML参照 |
| **Critical 3コンテキスト** | 構造化フィールドのみ（盤面シリアライズなし） |
| **Karte 出力形式** | `.json`（Phase 148 で `.md` → `.json` に完全移行） |

詳細は [docs/01-roadmap.md](../../01-roadmap.md) を参照。
