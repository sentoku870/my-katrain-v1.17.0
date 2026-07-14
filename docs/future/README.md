# Future（将来の機能）

このフォルダには、将来実装予定の機能仕様書（**まだ実装されていないもの**）が格納されています。

> **最終更新**: 2026-07-14（Phase 201: ドキュメント整合）

## ステータス定義

| ステータス | 意味 |
|-----------|------|
| `partial` | 一部のみ実装済み（GUI 部分のみ未実装等） |
| `deferred` | 構想段階、後回し |
| `idea` | 概要レベル、正式仕様未着手 |

## 収録ファイル

### Partial（一部未実装）

| ファイル | 概要 | 残作業 |
|----------|------|--------|
| [`phase82-context-filler.md`](phase82-context-filler.md) | Critical 3 コンテキスト自動生成 | `situation_type` 分類器と owner-context 拡張の GUI 統合 |

### Deferred（延期）

| ファイル | 概要 | 優先度 |
|----------|------|--------|
| [`idea3-ownership-overlay.md`](idea3-ownership-overlay-DEFERRED.md) | Ownership Volatility Overlay（係争地 / 死に石 / 過剰防衛の盤上可視化） | 中 |
| [`idea5-style-quiz.md`](idea5-style-quiz-DEFERRED.md) | Style Matching Quiz（Human-SL + 標準 KataGo loss 比較クイズ） | 低 |

## 実装済みへの移動先（参考）

実装完了した仕様書は [`docs/archive/specs-implemented/`](../archive/specs-implemented/) に移管済みです。Phase 80-94 系の機能（Ownership クラスタ、Pattern Mining、Reason Generator、KataGo Setup Rescue、Beginner Hints MVP、Active Review MVP）もすべて実装完了しました。
