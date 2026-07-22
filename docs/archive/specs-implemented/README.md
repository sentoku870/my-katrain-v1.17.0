# 設計仕様書 (Design Specifications)

このフォルダには myKatrain の機能設計仕様書（実装済み Phase）を格納しています。

> **最終更新**: 2026-07-21（Phase 284 完了、Phase 271-284 のスペック索引を追加）  
> Phase 171 で Leela エンジン / 関連スペックを完全削除。KataGo 専用の構成に整理。

---

## Phase 45–52 関連仕様書

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [idea1-meaning-tags.md](idea1-meaning-tags.md) | Phase 46-47 | MeaningTags: ミスの「意味」自動タグ付け |
| [idea2-radar-tier.md](idea2-radar-tier.md) | Phase 48-49, 51 | 5軸レーダーチャートと Tier 判定 |
| [idea4-critical3-focused-review.md](idea4-critical3-focused-review.md) | Phase 50 | Critical 3: 一点集中レビューモード |
| [lexicon-integration.md](lexicon-integration.md) | Phase 45 | go_lexicon_master_last.yaml 活用設計 |
| [summary-improvements.md](summary-improvements.md) | Phase 47, 49 | Summary 改善案（5軸レーダー、意味的診断） |
| [karte-improvements.md](karte-improvements.md) | Phase 47, 50 | Karte 改善案（信頼度ゲート、敗着特定） |
| [common-improvements.md](common-improvements.md) | Phase 47-50 | カルテ・サマリー共通改善（動的閾値、LLM プロンプト埋め込み） |

## 延期された仕様

| ファイル | 内容 |
|----------|------|
| [idea3-ownership-overlay.md](../../future/idea3-ownership-overlay.md) | Ownership Volatility Overlay（危険度可視化）— `docs/future/` 参照 |
| [idea5-style-quiz.md](../../future/idea5-style-quiz.md) | Style Matching Quiz（スタイル一致クイズ）— `docs/future/` 参照 |

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

- **Phase 82**: [`docs/future/phase82-context-filler.md`](../../future/phase82-context-filler.md) — Critical 3 コンテキスト自動生成（`situation_type` 分類器の GUI 統合が残作業）

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

- **Phase 194**（MagicMock 汚染除去）: `katrain/core/reports/extractors.py` から `unittest.mock.MagicMock` の production import を排除、`tests/test_extractors.py` を新規 26 件追加。仕様書ファイルは未作成（Phase 201 整理のため省略）。
- **Phase 195-A**（互換シム棚卸し）: `logic_difficulty.py` / `karte_report.py` の deprecated シム参照を production code から脱却。Architecture テスト `TestDeprecatedShimIsolation` を 3 件追加。eval_metrics / batch_analyze_sgf シムは Phase 195-C まで保持。

## Phase 225-270 完了済みスペック（2026-07）

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [phase225-llm-coach-gui.md](phase225-llm-coach-gui.md) | Phase 225 | LLM Coach GUI 統合（手動貼付ワークフロー） |
| [phase225-master.md](phase225-master.md) | Phase 225 + 225.1-225.8 | LLM Coach 統合マスター索引 |
| [phase227-llm-coach-multi-game.md](phase227-llm-coach-multi-game.md) | Phase 227-A〜E | LLM コーチ複数局対応（B 案フル実装: summary_prompt_builder / summary_validator / popup タブ化 + 視点セレクタ + 集約サマリボタン / calibration fixtures） |
| [phase228-summary-schema-adapt.md](phase228-summary-schema-adapt.md) | Phase 228-A〜D | LLM コーチ複数局対応 - 実シェーマ適応（extractors / prompt builder / validator / real_shape fixtures） |
| [phase229-rank-preset-unification.md](phase229-rank-preset-unification.md) | Phase 229 | 棋力プリセット / LLM コーチ 統合（`common/rank.py` 新設 + `resolve_skill_preset()` 統合 + 設定 UI 刷新） |
| [phase230-ui-ux-cleanup.md](phase230-ui-ux-cleanup.md) | Phase 230 | MyKatrain UI/UX 整理（メニュー 8→4 項目 + Leela 残滓削除 + 診断タブ統合 + 棋力入力統合） |
| [phase241-summary-quality-improvements.md](phase241-summary-quality-improvements.md) | Phase 241 | サマリー機能 品質改善（A-I の 9 サブフェーズ） |
| [phase246-candidate-filter-improvements.md](phase246-candidate-filter-improvements.md) | Phase 246 | 候補手フィルター（PV Filter）包括改善（5 サブフェーズ） |
| [phase249-beta-kifunarabe-history.md](phase249-beta-kifunarabe-history.md) | Phase 249-β | 棋譜並べ 永続履歴（KifunarabeHistoryStore）+ 設定タブ + 履歴ポップアップ + テスト 12 件 |
| [phase249-gamma-kifunarabe-integration.md](phase249-gamma-kifunarabe-integration.md) | Phase 249-γ | 棋譜並べ 重要局面リスト統合 + 弱点自動 export |
| [phase249-delta-kifunarabe-minor.md](phase249-delta-kifunarabe-minor.md) | Phase 249-δ | 棋譜並べ メニューアイコン重複解消 + panels.kv Kivy 違反修正 |
| [phase249-hotfix-startup-attrerror.md](phase249-hotfix-startup-attrerror.md) | Phase 249-hotfix | 起動時 AttributeError + 残存 γ リグレッション復旧 |
| [phase250-important-moves-refactor.md](phase250-important-moves-refactor.md) | Phase 250 | 重要局面 UI リファクタリング（A-H の 8 サブフェーズ） |
| [phase269-ayaka-removal-and-summary-phase-fix.md](phase269-ayaka-removal-and-summary-phase-fix.md) | Phase 269 | AYAKA 完全削除 + voice 統一（TOMOKO）+ 弱点抽出整合性修正 |
| [phase270-karte-aggregator.md](phase270-karte-aggregator.md) | Phase 270 | 複数カルテ集約 + サマリプロンプト v3.5 拡張 |

> **Phase 249-α 仕様書**: 同名のスペックファイルは未作成（Phase 249-β が α の成果を内包）。α 単独サマリーは [`docs/01-roadmap.md`](../../01-roadmap.md) §4 および AGENTS.md §1.3 を参照してください。

## Phase 231-237 カルテ刷新（2026-07）

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [karte-schema.md](karte-schema.md) | Phase 231-237 | 単局カルテ（v3.3）/ 複数局サマリ（v3.4）の **JSON スキーマ正本ドキュメント**。型判別ロジック / Shape A vs Shape B / 全フィールド仕様 / バージョン履歴 |

## Phase 271-284 完了済みスペック（2026-07）

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [phase269-ayaka-removal-and-summary-phase-fix.md](phase269-ayaka-removal-and-summary-phase-fix.md) | Phase 269 | AYAKA 完全削除 + voice 統一（TOMOKO）+ 弱点抽出整合性修正 |
| [phase270-karte-aggregator.md](phase270-karte-aggregator.md) | Phase 270 | 複数カルテ集約 + サマリプロンプト v3.5 拡張 |
| [phase277-kivymd-1.2.0-migration.md](phase277-kivymd-1.2.0-migration.md) | Phase 277 | KivyMD 0.104.1 → 1.2.0 移行（Material Design 3 対応 + 欠落 `.kv` ファイル runtime hook） |
| [phase281-jp-font-tofu-fix.md](phase281-jp-font-tofu-fix.md) | Phase 281 | 日本語フォント 豆腐修正 包括対策（`_sync_font_to_hint_labels` ヘルパー + `_kivymd_kv_loader.py` Roboto フォールバック撤廃） |
| [phase282-architecture-followup.md](phase282-architecture-followup.md) | Phase 282 | アーキテクチャレビュー P1+P2 着手（conftest.py 死蔵コード除去 851→500 行 + 5 大ファイルスモークテスト 312 件） |
| [phase283-side-panel-fonts-quick-buttons.md](phase283-side-panel-fonts-quick-buttons.md) | Phase 283 | サイドパネル文字サイズ縮小 fix + 新規対局 popup 9 クイック選択ボタン空白 fix（2 段バグ修正） |
| [phase284-pyinstaller-legacy-widgets.md](phase284-pyinstaller-legacy-widgets.md) | Phase 284 | PyInstaller frozen binary の `kivy.uix.tabbedpanel` / `kivy.uix.checkbox` 欠落 fix（hiddenimports 明示追加） |

## Phase 171 で削除されたスペック

以下のスペックは Phase 171（Leela エンジン完全削除）で実装と共に削除されました。git log で参照可能:

- `leela-estimated-loss.md`（Phase 14.0-14.7）— Leela 推定損失
- `leela-output-format.md`（Phase 14.0）— Leela Zero lz-analyze 出力フォーマット

---

## 固定決定事項（Decisions Fixed for Phase 45–52）

| 決定事項 | 解決 |
|----------|------|
| **Lexicon データソース** | `go_lexicon_master_last.yaml` が正本 |
| **Lexicon 言語** | EN/JP のみ（既存 YAML フィールド） |
| **Radar 軸** | `opening`, `fighting`, `endgame`, `stability`, `awareness` |
| **Radar スコア** | 内部: 0.0–1.0、表示: 1.0–5.0 |
| **Tier 名** | Tier 1-5（入門/初級/中級/上級/高段） |
| **MeaningTag ↔ Lexicon** | `lexicon_anchor_id: Optional[str]` で YAML 参照 |
| **Critical 3 コンテキスト** | 構造化フィールドのみ（盤面シリアライズなし） |
| **Karte 出力形式** | `.json`（Phase 148 で `.md` → `.json` に完全移行） |
| **AI 戦略** | Phase 280 で `ai:default` / `ai:handicap` の 2 戦略のみに集約 |
| **LLM 連携** | 手動コピー＆貼付（自動 API 送信は non-goal） |

詳細は [`docs/01-roadmap.md`](../../01-roadmap.md) を参照。
