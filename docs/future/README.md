# Future（将来の機能）

このフォルダには、**未実装または一部実装済み**の機能仕様書を格納しています。  
実装済みのものは [`docs/archive/specs-implemented/`](../archive/specs-implemented/) へ移管されます。

> **最終更新**: 2026-07-21（Phase 280 / 250 後の状態整合）

## ステータス定義

| ステータス | 意味 |
|-----------|------|
| `partial` | 一部のみ実装済み（GUI 部分のみ未実装等） |
| `deferred` | 構想段階、後回し（DEFERRED 命名規則へ移行予定） |
| `idea` | 概要レベル、正式仕様未着手 |

## 収録ファイル

### Partial（一部未実装）

| ファイル | 概要 | 残作業 |
|----------|------|--------|
| [`phase82-context-filler.md`](phase82-context-filler.md) | Critical 3 コンテキスト自動生成 | `situation_type` 分類器と owner-context 拡張の GUI 統合 |

### Deferred（延期）

| ファイル | 概要 | 優先度 |
|----------|------|--------|
| [`idea3-ownership-overlay.md`](idea3-ownership-overlay.md) | Ownership Volatility Overlay（係争地 / 死に石 / 過剰防衛の盤上可視化） | 中 |
| [`idea5-style-quiz.md`](idea5-style-quiz.md) | Style Matching Quiz（Human-SL + 標準 KataGo loss 比較クイズ） | 低 |

> **命名規則**: 延期ファイルはかつて `DEFERRED-` プレフィックス付きで `docs/archive/specs-implemented/` に置かれていましたが、Phase 280 の整理で `docs/future/` へ移管されました。DEFERRED プレフィックスは順次削除中です。

## 関連

- **実装済み**: [`docs/archive/specs-implemented/`](../archive/specs-implemented/) — Phase 計画完了済みのスペック
- **計画中（着手前）**: [`docs/archive/specs-planned/`](../archive/specs-planned/) — Phase 単位の着手前スペック
- **アイデア原案**: [`docs/ideas/`](../ideas/) — 構想段階のメモ

Phase 80-94 系（Ownership クラスタ / Pattern Mining / Reason Generator / KataGo Setup Rescue / Beginner Hints MVP / Active Review MVP）は実装完了し、`docs/archive/specs-implemented/` へ移管済みです。
