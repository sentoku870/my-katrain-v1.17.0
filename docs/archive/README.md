# Archive（アーカイブ）

このフォルダには、完了済みまたは参照専用のドキュメントが格納されています。

## 構造

```
archive/
├── CHANGELOG.md          ← 変更履歴（Phase 1-52）
├── plans/                ← 完了した計画書
│   ├── plan-phase-ab.md
│   ├── plan-phase-12.md
│   ├── plan-phase-19.md
│   ├── plan-phase-20.md
│   └── plan-phase-22-stability.md
├── phase-guides/         ← Phase固有のガイド
│   ├── phase7-test-guide.md
│   └── phase9-completion-summary.md
├── design/               ← 初期設計メモ（Phase 6-7）
│   ├── phase6-karte-spec.md
│   ├── phase7-structure-hints.md
│   └── phase7-tier-system.md
└── specs-implemented/    ← 実装済み仕様書
    ├── README.md
    └── (12ファイル)
```

## 用途

- **参照**: 過去の設計意図や決定事項を確認する際に使用
- **履歴**: 変更履歴の詳細を確認する際に使用
- **復元**: git履歴と併用して過去の状態を復元する際に参考

## 注意

- これらのファイルは通常編集しません
- 新しいPhaseの計画書は `docs/` 直下に作成し、完了後にここに移動します
