# 設計仕様書 (Design Specifications)

このフォルダにはmyKaTrainの機能設計仕様書を格納しています。

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

## その他の仕様書

| ファイル | 対応Phase | 内容 |
|----------|-----------|------|
| [muzero-difficulty.md](muzero-difficulty.md) | Phase 12 | MuZero 3分解難易度 |
| [smart-kifu-learning.md](smart-kifu-learning.md) | Phase 13, 28 | Smart Kifu Learning |
| [leela-estimated-loss.md](leela-estimated-loss.md) | Phase 14, 31 | Leela推定損失 |
| [leela-output-format.md](leela-output-format.md) | Phase 14 | Leela出力フォーマット |
| [human-move-filter.md](human-move-filter.md) | Phase 11 | Human Move Filter |

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

詳細は [docs/01-roadmap.md](../01-roadmap.md) の「Phase 45–52 詳細」セクションを参照。
