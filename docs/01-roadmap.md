# myKatrain（PC版）ロードマップ

> 最終更新: 2026-02-10(Phase 137完了)
> 固定ルールは `00-purpose-and-scope.md` を参照。
> 過去の履歴（Phase 1-130）は [ROADMAP_HISTORY.md](./archive/ROADMAP_HISTORY.md) を参照。

---

## 0. 用語（短縮表記）

| 用語 | 説明 |
|------|------|
| カルテ（Karte） | 対局の要点・弱点・根拠をまとめた「診断用まとめ」 |
| アンカー | 根拠を追跡できる最小情報（手数/座標/損失/候補手） |
| LLMパッケージ | LLMに渡す一式（karte.md + sgf + coach.md） |

---

## 1. 完了済みフェーズ一覧 (Phase 131〜)

過去の全フェーズ一覧は [ROADMAP_HISTORY.md](./archive/ROADMAP_HISTORY.md#2-フェーズ一覧) を参照してください。

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| 131 | JSONレポートの機能改善 | 難易度ラベル名寄せ、局面フェーズ計算 | ✅ |
| 132 | Leela Zero UI改善 | 候補手表示修正、設定拡張 | ✅ |
| 133 | プロジェクトのスリム化 | 緊急バグ修正、最適化調査 | ✅ |
| 134 | 10段階Skill Radar実装 | SkillTier拡張、軸別閾値設定 | ✅ |
| 135 | Skill Radarバッチ出力 | GUI統合、テキスト形式出力 | ✅ |
| 136 | AI対応レーダー出力改善 | 構造化マークダウン、閾値情報追加 | ✅ |
| 137 | 不要機能削除とバグ修正 | Skill Radar削除、SGF読み込み修正 | ✅ |

### 直近の更新詳細

**Phase 131**: ✅ JSONレポートの機能改善（2026-02-08 完了）。
- 難易度ラベルの標準化（"easy"→"simple"）。
- 重要手の局面フェーズ（opening/middle/endgame）の動的計算実装。
- Summaryレポートのメタデータへの `skill_preset` 追加。

**Phase 132**: ✅ Leela Zero UI改善（2026-02-08 完了）。
- 候補手表示の修正：`GameNode.candidate_moves`で勝率降順ソート実装。
- 設定オプション拡張：`leela_max_candidates`に「auto」追加、`loss_scale_k`の調整。
- Force解析のUX改善：既存候補手を保持したまま上書き。

**Phase 133**: ✅ プロジェクトのスリム化(2026-02-09 完了)。
- 緊急バグ修正: SGFポップアップの `KeyError`、`ImportError`、イベントハンドラ不足を解消。
- バッチ解析UIのクリーンアップ: KataGo専任化、Leela選択UI削除。
- プロジェクト最適化調査: 依存関係とリソースファイルの整理提案を作成。

**Phase 134**: ✅ 10段階Skill Radar実装(2026-02-09 完了)。
- SkillTier enumを5段階→10段階に拡張(TIER_1〜TIER_10)。
- 軸別閾値定数の定義: Opening/Fighting/Endgame/Stability/Awareness。
- 星表示バグ修正: 10段階スコア→5つ星マッピングを修正。
- 実データに基づく反復調整: 8回の閾値調整でバランス改善。

**Phase 135**: ✅ Skill Radarバッチ出力(2026-02-09 完了)。
- バッチ処理UIにスキルレーダー出力チェックボックス追加。
- 既存 `export_radar_csv.py` を拡張: テキスト形式出力対応。
- 分析済みSGFディレクトリを参照する実装: 正確な棋力評価を実現。
- プレイヤーランク情報（BR/WR）の表示追加。

**Phase 136**: ✅ AI対応レーダー出力改善(2026-02-10 完了)。
- AI解析用の構造化マークダウン形式に変更。
- 閾値設定情報の追加: 5軸すべての評価基準をテーブル化。
- 計算方法の明示: 総合棋力計算、欠損値処理、有効手数定義。
- 実装に基づいた正確な定義: 序盤力(50手)、戦闘力(HARD)、終盤力(150手)。

**Phase 137**: ✅ 不要機能削除とバグ修正(2026-02-10 完了)。
- **Skill Radar 機能の完全削除**: GUI、コアロジック、バッチ処理、統計出力ツールをすべて削除。
- **削除に伴う不具合修正**: `stats/models.py` の `TypeError` 修正、残存する未使用インポートや定数の除去。
- **デグレーション修正 (サマリー)**: Skill Radar 削除時に混入した早期 `return` を排除し、`summary_report.py` で Markdown 出力がスキップされていた問題を解消（ユーザー向けの統計表示を復元）。
- **SGF読み込みバグ修正**: 不適切なパス（ディレクトリ等）選択時の `PermissionError` 回避ロジックを `sgf_manager.py` に実装し、UI レベルでの制約も追加。

---

## 2. 進行中・計画中のフェーズ

| Phase | ゴール | 主成果物 | 状態 |
|------:|--------|----------|:----:|
| - | Beginner Hint 拡張 | 翻訳テンプレ、盤上ハイライト | 📋 Planned |
| - | Active Review 拡張 | Retry/Hint、セッションサマリ | 📋 Planned |

---

## 3. 将来の拡張候補

- [ ] Ownership Volatility (Idea #3): 盤面リスクオーバーレイ
- [ ] Style Matching Quiz (Idea #5): スタイル判定クイズ
- [ ] Lexicon UI Browser: 用語ポップアップ
