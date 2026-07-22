# Archive（アーカイブ）

このフォルダには、完了済みまたは参照専用のドキュメントを格納しています。

## 構造

```
archive/
├── CHANGELOG.md                 ← 長期変更履歴
├── ROADMAP_HISTORY.md           ← 過去ロードマップ
├── architecture-review-*.md     ← アーキテクチャレビュー記録
├── design/                      ← 歴史的設計メモ（Phase 6-7）
├── error-handling-audit.md      ← エラー処理監査
├── fork-comparison-*.md         ← fork 比較資料
├── katrain_qt/                  ← Qt 移植検討メモ
├── phase-guides/                ← Phase 固有の作業ガイド
├── plans/                       ← Phase 計画書（完了済み多数）
├── scripts/                     ← 補助スクリプト
├── specs-implemented/           ← 実装済み仕様書索引
└── specs-planned/               ← 計画中/延期仕様書
```

各フォルダの詳細は以下:

- [`docs/archive/specs-implemented/`](specs-implemented/) — 実装済み Phase スペック（Phase 45-284 まで索引）
- [`docs/archive/specs-planned/`](specs-planned/) — 計画中 / 履歴資料としての Phase 仕様
- [`docs/archive/design/`](design/) — Phase 6-7 の歴史的設計メモ
- [`docs/archive/plans/`](plans/) — Phase 12 / 19 / 20 / 22 / 79 / 82-89 / 146 等の完了計画書
- [`docs/archive/phase-guides/`](phase-guides/) — Phase 7 / 9 などの作業ガイド

## 用途

- **参照**: 過去の設計意図や決定事項を確認する際に使用
- **履歴**: 変更履歴の詳細を確認する際に使用
- **復元**: git 履歴と併用して過去の状態を復元する際に参考

## 仕様書の配置ルール

| ステータス | 配置先 | 命名規則 |
|-----------|--------|----------|
| 計画中（未着手） | `docs/archive/specs-planned/` | `phase<N>-<slug>.md` |
| 実装中（部分実装） | `docs/archive/specs-planned/` または `specs-implemented/` 暫定 | 同上 |
| 完了済み | `docs/archive/specs-implemented/` | 同上 |
| 撤回・延期 | `docs/future/` | `idea<N>-<slug>.md` |

> `docs/` 直下に新規 Phase 仕様を置く運用は Phase 201 で廃止されました。

## 注意

- これらのファイルは通常編集しません
- 新しい Phase の計画書は `docs/archive/specs-planned/` に作成し、完了後に `docs/archive/specs-implemented/` へ移動します
