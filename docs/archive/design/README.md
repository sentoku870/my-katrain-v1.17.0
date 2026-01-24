# Design Documents

Phase別の設計メモ格納場所。

## ファイル一覧

### Phase 6: カルテ（診断書）機能
- **phase6-karte-spec.md**: カルテの設計仕様
  - 単局カルテ・複数局サマリーの出力形式
  - ユースケース4ルート（プロンプト/SGF/解析SGF/カルテ）
  - LLM連携時の運用ルール

### Phase 7: 構造解析＋初心者向けヒント（未実装）
- **phase7-structure-hints.md**: 構造の言語化パーツ
  - グループ抽出・呼吸点・連絡点・切断点
  - 初心者向けテンプレ10個（症状→処方箋）
  - 理由タグ（atari/low_liberties/cut_risk等）

- **phase7-tier-system.md**: 棋力判定システム（未実装）
  - 5段階評価（Tier1 初心者 〜 Tier5 アマ強豪）
  - Adjusted APL / Blunder Rate / Move Agreement
  - レーダー5軸（Opening/Fighting/Endgame/Stability/Awareness）

## 管理方針
- 設計メモは Git 管理下に置く（バージョン追跡）
- 実装時は該当 Phase の仕様を参照する
- 仕様変更時はこのフォルダ内を更新する
