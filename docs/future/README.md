# Future（将来の機能）

このフォルダには、将来実装予定の機能仕様書が格納されています。

## 収録ファイル

### Phase 80-94 仕様書（Planned - 2026-01-29 追加）

#### Analysis Intelligence（Phase 80-87）

| ファイル | 概要 | Phase |
|----------|------|-------|
| `phase80-82-ownership-consequence.md` | Ownership変動によるConsequence（結末）判定 | 80-82 |
| `phase82-context-filler.md` | Critical 3コンテキスト自動生成 | 82 |
| `phase83-complexity-filter.md` | 難解度（Complexity）フィルタによるノイズ除去 | 83 |
| `phase84-85-pattern-mining.md` | 再発パターン特定（Recurring Pattern Mining） | 84-85 |
| `phase86-reason-generator.md` | 自然言語理由生成エンジン（Reason Generator） | 86 |

#### Beginner Experience（Phase 88-94）

| ファイル | 概要 | Phase |
|----------|------|-------|
| `phase88-90-katago-setup-rescue.md` | KataGoセットアップ救済（初心者向け） | 88-90 |
| `phase91-92-beginner-hints.md` | 初心者向けヒント（Safety Net） | 91-92 |
| `phase93-94-active-review.md` | Active Review Mode（次の一手予測） | 93-94 |

### Future Ideas（延期）

| ファイル | 概要 | 優先度 |
|----------|------|--------|
| `idea3-ownership-overlay.md` | Ownership Volatility Overlay | 中 |
| `idea5-style-quiz.md` | Style Matching Quiz | 低 |

## ステータス

これらの機能は Phase 52 時点で延期（DEFERRED）とされました。
リリース準備完了後、優先度に応じて実装を検討します。

## 実装時の手順

1. このフォルダから仕様書を `docs/` 直下にコピー
2. 仕様を最新化
3. 実装後、仕様書を `docs/archive/specs-implemented/` に移動
