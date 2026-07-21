# 計画中スペック (Planned Specifications)

このフォルダには **実装に未着手** の設計仕様書を格納しています。実装フェーズに移行した段階で `specs-implemented/` へ移動します。

> **最終更新**: 2026-07-21（Phase 242-245 / 248 を本フォルダに追加）
> Phase 194-202 / 225-284 は `specs-implemented/` または `docs/01-roadmap.md` §4 に実装済み記録。

---

## 配置ルール

| ステータス | 配置先 | 命名規則 |
|-----------|--------|----------|
| 計画中（未着手） | 本フォルダ `specs-planned/` | `phaseXXX-<slug>.md` |
| 実装中（部分実装） | 本フォルダ `specs-planned/` または `specs-implemented/` 暫定 | 同上 |
| 完了済み | `specs-implemented/` | 同上 |
| 撤回・延期 | ファイル先頭に `DEFERRED-` プレフィックス | `DEFERRED-phaseXXX-<slug>.md` |

## Phase 203+（調査・計画中）

| Phase | ファイル | 状態 | 概要 |
|-------|----------|------|------|
| 203 | [phase203-llm-translator.md](phase203-llm-translator.md) | 計画中（調査完了） | LLM「翻訳特化」導入 — KataGo 出力を Ground Truth とし、LLM には判断ではなく翻訳のみを担わせる |
| 242 | [phase242-llm-coach-quality.md](phase242-llm-coach-quality.md) | 計画中（監査完了、A-E 着手） | LLM Coach 機能 40 件以上の監査結果、A-E の 5 サブフェーズ |
| 243 | [phase243-popup-wrapper-migration.md](phase243-popup-wrapper-migration.md) | 計画中 | popup wrapper migration（Phase 242-E で関連部分実装済み） |
| 244 | [phase244-lexicon-yaml-extension.md](phase244-lexicon-yaml-extension.md) | 計画中 | Lexicon YAML 拡張（Phase 242-C で 5 エントリ追加済み、残作業） |
| 245 | [phase245-positional-difficulty.md](phase245-positional-difficulty.md) | 計画中 | Positional Difficulty（Phase 192 の difficulty/ サブパッケージで関連実装済み） |
| 248 | [phase248-important-moves-popup.md](phase248-important-moves-popup.md) | 計画中（D1 実装済み） | 重要局面リスト popup widget（Phase 248-γ D1 でスケルトン + D2 で prev/next ヘルパー実装済み、GUI 統合は残作業） |

---

## Phase 194-202 / 225-284（直近の完了済み、本フォルダ未経由）

多くの Phase は実装フェーズから直接 `specs-implemented/` または `docs/01-roadmap.md` §4 に登録されたため、本フォルダは通過していません。

- Phase 194: MagicMock 汚染除去 → `specs-implemented/` 参照
- Phase 195-A/B/C: 互換シム棚卸し → `specs-implemented/` 参照
- Phase 196: `beginner/hints.py` サブパッケージ化 → `specs-implemented/` 参照
- Phase 197: `batch/orchestration.py` サブパッケージ化 → `docs/01-roadmap.md` §4 参照
- Phase 198 (Stage 1): KaTrainGui AppContext 集約基盤 → `docs/01-roadmap.md` §4 参照
- Phase 200: `except Exception` 整理 → `docs/01-roadmap.md` §4 参照
- Phase 202: 到達不能コード削除 → `docs/01-roadmap.md` §4 参照
- Phase 225-228: LLM Coach GUI 統合 + 複数局対応 → `specs-implemented/` 参照
- Phase 230: MyKatrain UI/UX 整理 → `specs-implemented/` 参照
- Phase 241-242: サマリー / LLM Coach 品質改善 → `specs-implemented/` 参照
- Phase 246-248: 候補手フィルター / 重要局面 包括改善 → `specs-implemented/` 参照
- Phase 250: 重要局面 UI リファクタリング → `specs-implemented/` 参照
- Phase 269-284: AYAKA 削除 / カルテ集約 / UI 整理 / KivyMD 1.2.0 / AI スリム化 / フォント tofu fix / アーキテクチャ follow-up / PyInstaller fix → `specs-implemented/` 参照

---

## 関連ドキュメント

- [docs/01-roadmap.md](../../01-roadmap.md) — 全体ロードマップ
- [docs/03-llm-validation.md](../../03-llm-validation.md) — LLM 検証テンプレート（Phase 128 で作成、運用中）
- [docs/archive/specs-implemented/lexicon-integration.md](../specs-implemented/lexicon-integration.md) — Lexicon Integration Phase 45
- [docs/archive/specs-implemented/common-improvements.md](../specs-implemented/common-improvements.md) — LLM プロンプト注入設計ドラフト
- [docs/archive/specs-implemented/phase80-82-ownership-consequence.md](../specs-implemented/phase80-82-ownership-consequence.md) — Ownership Consequence

詳細は [docs/01-roadmap.md](../../01-roadmap.md) を参照。
