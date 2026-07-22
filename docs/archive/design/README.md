# Design Documents（歴史的設計メモ）

Phase 6-7 の初期設計メモ。歴史的資料であり、**現行実装は別設計で進んでいます**。  
現行の正本は [`docs/00-purpose-and-scope.md`](../../00-purpose-and-scope.md) / [`docs/02-code-structure.md`](../../02-code-structure.md) / [`docs/archive/specs-implemented/`](../specs-implemented/) を参照してください。

> **最終更新**: 2026-07-21（Phase 280 / 282 後の注記整備）

## ファイル一覧

### Phase 6: カルテ（診断書）機能

- **phase6-karte-spec.md**: カルテの設計仕様
  - 単局カルテ・複数局サマリーの出力形式
  - ユースケース 4 ルート（プロンプト / SGF / 解析 SGF / カルテ）
  - LLM 連携時の運用ルール
  
  > **実装状況**: Phase 148 で Markdown → JSON へ完全移行（Karte v3.3 / Summary v3.4）。LLM Coach GUI 統合は Phase 225 / 227 で実装。スキーマ正本は [`docs/archive/specs-implemented/karte-schema.md`](../specs-implemented/karte-schema.md)。

### Phase 7: 構造解析＋初心者向けヒント

- **phase7-structure-hints.md**: 構造の言語化パーツ
  - グループ抽出・呼吸点・連絡点・切断点
  - 初心者向けテンプレ 10 個（症状 → 処方箋）
  - 理由タグ（atari / low_liberties / cut_risk 等）
  
  > **実装状況**: 当初の Tier 設計は採用せず、Phase 91-92 で Beginner Hints MVP、Phase 179 / 182 / 186 で合計 9 カテゴリのヒントに拡張。Reason Tag は `core/analysis/meaning_tags/` 配下で実装。

- **phase7-tier-system.md**: 棋力判定システム
  - 5 段階評価（Tier 1 初心者 〜 Tier 5 アマ強豪）
  - Adjusted APL / Blunder Rate / Move Agreement
  - レーダー 5 軸（Opening / Fighting / Endgame / Stability / Awareness）
  
  > **実装状況**: 当初案は未採用。Tier 名称は LLM Coach の CoachMode に流用されたが、`Master doc §0-1` の 5 モード（BEGINNER / INTERMEDIATE / DAN / ADVANCED / EXPERT）が現行の正本。詳細は [`docs/archive/specs-implemented/phase225-master.md`](../specs-implemented/phase225-master.md)。

## 管理方針

- 設計メモは **Git 管理**下で履歴追跡する
- 実装時は [**`docs/archive/specs-implemented/`**](../specs-implemented/) の現行スペックを優先する
- 仕様変更時は新スペックを作成して `specs-planned/` → `specs-implemented/` へ移管する

> 本フォルダの文書は **歴史的資料**として凍結されています。新規設計は [`docs/archive/specs-planned/`](../specs-planned/) へ起案してください。
