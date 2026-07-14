# Ideas（アイデア・構想）

このフォルダには、将来の機能拡張に関するアイデアや構想メモが格納されています。

> **最終更新**: 2026-07-14（Phase 201: ドキュメント整合）

## ステータス定義

| ステータス | 意味 |
|-----------|------|
| `concept` | 構想段階、正式仕様未着手 |
| `partial` | 一部のみ実装済み（バックエンドのみ等） |
| `implemented` | 完全実装済み（[`docs/archive/specs-implemented/`](../archive/specs-implemented/) へ移管候補） |

## 収録ファイル

| ファイル | 概要 | ステータス |
|----------|------|-----------|
| [`案１ ペース配分＆ティルト検知「Pacing & Tilt Doctor」.md`](案１%20ペース配分＆ティルト検知「Pacing%20%26%20Tilt%20Doctor」.md) | 対局中のペース配分とメンタル状態の検知機能 | **implemented**（Phase 58-60、Pacing/Tilt Doctor） |
| [`案２ ポジティブ・フィードバック生成機能「My Style Identity」.md`](案２%20ポジティブ・フィードバック生成機能「My%20Style%20Identity」.md) | プレイヤーの棋風を分析しポジティブなフィードバックを生成 | **concept**（一旦バックエンド未着手） |
| [`案３ 形勢判断・リスク管理チェッカー「Risk Reward Alignments」.md`](案３%20形勢判断・リスク管理チェッカー「Risk%20Reward%20Alignments」.md) | 形勢判断とリスク・リターンのバランス分析 | **concept** |
| [`案４ 弱点克服・反復ドリル「Weakness Repeater」.md`](案４%20弱点克服・反復ドリル「Weakness%20Repeater」.md) | 弱点パターンを繰り返し練習するドリル機能 | **concept** |
| [`案５ 名局選定と学習ガイド生成「Smart Kifu Curator」.md`](案５%20名局選定と学習ガイド生成「Smart%20Kifu%20Curator」.md) | 学習に適した棋譜を選定しガイドを生成 | **partial**（Phase 186 で Curator バックエンド実装、サイドバイサイド GUI と自動 LLM 接続は未着手） |
| [`time_pressure_analysis.md`](time_pressure_analysis.md) | 秒読み前後の損失相関 / thinking-time profile | **concept** |

## ステータス

これらは構想段階のアイデアです。実装の優先度は未定です。

## 関連フォルダ

- [`docs/future/`](../future/) - Phase 52 時点で延期された Phase 仕様のうち、未実装部分
- [`docs/archive/specs-implemented/`](../archive/specs-implemented/) - 実装済みの仕様書（Phase 45-52 / 80-94 / 177-195-A）

## 実装検討時の手順

1. アイデアを詳細な仕様書に落とし込む
2. 仕様書を [`docs/`](../) 直下に配置
3. Phase として実装計画を立てる
4. 実装後、仕様書を [`docs/archive/specs-implemented/`](../archive/specs-implemented/) に移動
