# myKatrain（PC版）ロードマップ

> 最終更新: 2026-02-09（Phase 133完了）
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

### 直近の更新詳細

**Phase 131**: ✅ JSONレポートの機能改善（2026-02-08 完了）。
- 難易度ラベルの標準化（"easy"→"simple"）。
- 重要手の局面フェーズ（opening/middle/endgame）の動的計算実装。
- Summaryレポートのメタデータへの `skill_preset` 追加。

**Phase 132**: ✅ Leela Zero UI改善（2026-02-08 完了）。
- 候補手表示の修正：`GameNode.candidate_moves`で勝率降順ソート実装。
- 設定オプション拡張：`leela_max_candidates`に「auto」追加、`loss_scale_k`の調整。
- Force解析のUX改善：既存候補手を保持したまま上書き。

**Phase 133**: ✅ プロジェクトのスリム化（2026-02-09 完了）。
- 緊急バグ修正：SGFポップアップの `KeyError`、`ImportError`、イベントハンドラ不足を解消。
- バッチ解析UIのクリーンアップ：KataGo専任化、Leela選択UI削除。
- プロジェクト最適化調査：依存関係とリソースファイルの整理提案を作成。

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
