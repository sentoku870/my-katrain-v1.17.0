# Ideas（アイデア・構想）

このフォルダには、将来の機能拡張に関するアイデア・構想メモ・監査資料を格納しています。

> **最終更新**: 2026-07-21（Phase 280 / 282 後の整合）

## ステータス定義

| ステータス | 意味 |
|-----------|------|
| `concept` | 構想段階、正式仕様未着手 |
| `partial` | 一部のみ実装済み（バックエンドのみ等） |
| `implemented` | 完全実装済み（[`docs/archive/specs-implemented/`](../archive/specs-implemented/) へ移管候補） |
| `audit` | 監査資料（改善余地として記録、移管後は `specs-planned/` または `specs-implemented/` へ） |

## 収録ファイル

| ファイル | 概要 | ステータス |
|----------|------|-----------|
| [`案１ ペース配分＆ティルト検知「Pacing & Tilt Doctor」.md`](案１%20ペース配分＆ティルト検知「Pacing%20%26%20Tilt%20Doctor」.md) | 対局中のペース配分とメンタル状態の検知機能 | **implemented**（Phase 58-60、Pacing/Tilt Doctor） |
| [`案２ ポジティブ・フィードバック生成機能「My Style Identity」.md`](案２%20ポジティブ・フィードバック生成機能「My%20Style%20Identity」.md) | プレイヤーの棋風を分析しポジティブなフィードバックを生成 | **concept** |
| [`案３ 形勢判断・リスク管理チェッカー「Risk Reward Alignments」.md`](案３%20形勢判断・リスク管理チェッカー「Risk%20Reward%20Alignments」.md) | 形勢判断とリスク・リターンのバランス分析 | **concept** |
| [`案４ 弱点克服・反復ドリル「Weakness Repeater」.md`](案４%20弱点克服・反復ドリル「Weakness%20Repeater」.md) | 弱点パターンを繰り返し練習するドリル機能 | **concept** |
| [`案５ 名局選定と学習ガイド生成「Smart Kifu Curator」.md`](案５%20名局選定と学習ガイド生成「Smart%20Kifu%20Curator」.md) | 学習に適した棋譜を選定しガイドを生成 | **partial**（Phase 186 Curator バックエンド実装済、サイドバイサイド GUI と自動 LLM 接続は未着手） |
| [`time_pressure_analysis.md`](time_pressure_analysis.md) | 秒読み前後の損失相関 / thinking-time profile | **concept** |
| [`phase242-llm-coach-audit.md`](phase242-llm-coach-audit.md) | LLM Coach 監査（A-E 着手後の追補含む） | **audit** |
| [`phase249-kifunarabe-audit.md`](phase249-kifunarabe-audit.md) | 棋譜並べ監査（Phase 249-α/β/γ/δ 起案元） | **audit** |
| [`phase250-hint-feature-audit.md`](phase250-hint-feature-audit.md) | 重要局面・Beginner Hints 包括監査 | **audit** |

## ステータス早見表

これらは構想段階・実装中・完全実装済みが**混在**します。実装優先度はファイルごとに個別判断してください。

## 関連フォルダ

- [`docs/future/`](../future/) — 実装未着手・延期の Phase 仕様
- [`docs/archive/specs-planned/`](../archive/specs-planned/) — 着手前スペック（audit 後に Phase 化される前段階）
- [`docs/archive/specs-implemented/`](../archive/specs-implemented/) — 実装済み Phase スペック索引

## 実装検討時の手順

1. アイデアを監査・詳細化した後 `docs/archive/specs-planned/<phase>*.md` にスペックを起こす
2. Phase として実装計画を立てる
3. 実装完了したら `docs/archive/specs-implemented/<phase>*.md` へ移管する

> **旧ルール**: かつて `docs/` 直下に新規 Phase 仕様を置く運用がありましたが、Phase 201 以降は本フォルダ規則（`archive/specs-planned/` → `archive/specs-implemented/`）に統一されています。
