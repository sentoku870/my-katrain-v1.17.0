# 計画中スペック (Planned Specifications)

このフォルダには **実装に未着手** の設計仕様書を格納しています。実装フェーズに移行した段階で `specs-implemented/` へ移動します。

> **最終更新**: 2026-07-17（Phase 203 新規作成）
> Phase 194-202 は `specs-implemented/` に実装済み（一部）。本フォルダは将来の検討段階スペック用。

---

## 配置ルール

| ステータス | 配置先 | 命名規則 |
|-----------|--------|----------|
| 計画中（未着手） | 本フォルダ `specs-planned/` | `phaseXXX-<slug>.md` |
| 実装中（部分実装） | 本フォルダ `specs-planned/` または `specs-implemented/` 暫定 | 同上 |
| 完了済み | `specs-implemented/` | 同上 |
| 撤回・延期 | ファイル先頭に `DEFERRED-` プレフィックス | `DEFERRED-phaseXXX-<slug>.md` |

## Phase 203+

| Phase | ファイル | 状態 | 概要 |
|-------|----------|------|------|
| 203 | [phase203-llm-translator.md](phase203-llm-translator.md) | 計画中（調査完了） | LLM「翻訳特化」導入 — KataGo 出力を Ground Truth とし、LLM には判断ではなく翻訳のみを担わせる |

---

## Phase 194-202（直近の完了済み、本フォルダ未経由）

Phase 194-202 は実装フェーズから直接 `specs-implemented/` または `docs/01-roadmap.md` §4 に登録されたため、本フォルダは通過していません。本フォルダの運用開始は Phase 203 から。

- Phase 194: MagicMock 汚染除去 → `specs-implemented/` 参照
- Phase 195-A/B/C: 互換シム棚卸し → `specs-implemented/` 参照
- Phase 196: `beginner/hints.py` サブパッケージ化 → `specs-implemented/` 参照
- Phase 197: `batch/orchestration.py` サブパッケージ化 → `docs/01-roadmap.md` §4 参照
- Phase 198 (Stage 1): KaTrainGui AppContext 集約基盤 → `docs/01-roadmap.md` §4 参照
- Phase 200: `except Exception` 整理 → `docs/01-roadmap.md` §4 参照
- Phase 202: 到達不能コード削除 → `docs/01-roadmap.md` §4 参照

---

## 関連ドキュメント

- [docs/01-roadmap.md](../../01-roadmap.md) — 全体ロードマップ
- [docs/03-llm-validation.md](../../03-llm-validation.md) — LLM 検証テンプレート（Phase 128 で作成、運用中）
- [docs/archive/specs-implemented/lexicon-integration.md](../specs-implemented/lexicon-integration.md) — Lexicon Integration Phase 45
- [docs/archive/specs-implemented/common-improvements.md](../specs-implemented/common-improvements.md) — LLM プロンプト注入設計ドラフト
- [docs/archive/specs-implemented/phase80-82-ownership-consequence.md](../specs-implemented/phase80-82-ownership-consequence.md) — Ownership Consequence

詳細は [docs/01-roadmap.md](../../01-roadmap.md) を参照。
