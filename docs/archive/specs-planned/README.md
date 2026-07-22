# 計画中スペック (Planned Specifications)

このフォルダには、**実装未着手** または **着手したが完了していない** 設計仕様書を格納します。  
実装が完了したものは `specs-implemented/` へ移管されます。

> **最終更新**: 2026-07-21（Phase 241-242 / 248 の完了反映、Phase 248 Popup 廃止を反映）

---

## 配置ルール

| ステータス | 配置先 | 命名規則 |
|-----------|--------|----------|
| 計画中（未着手） | 本フォルダ `specs-planned/` | `phase<N>-<slug>.md` |
| 実装中（部分実装） | 本フォルダ `specs-planned/` または `specs-implemented/` 暫定 | 同上 |
| 完了済み | `specs-implemented/` | 同上 |
| 撤回・延期 | [`docs/future/`](../../future/) | `idea<N>-<slug>.md` |

> **旧ルール**: 一時期 `docs/` 直下に Phase 仕様を置く運用がありましたが、Phase 201 で本配置ルールに統一されました。

---

## 計画中（着手前）

現在、未着手の Phase 仕様はありません。着手予定の Phase 監査・起案は [`docs/ideas/`](../../ideas/) を起点に行います。

---

## 着手したが他フェーズへ統合・廃止された項目

歴史として残置している項目。実装が必要な場合は [`docs/future/`](../../future/) または [`docs/ideas/`](../../ideas/) で再起案してください。

| Phase | ファイル | 状態 | 備考 |
|-------|----------|------|------|
| 203 | [phase203-llm-translator.md](phase203-llm-translator.md) | **履歴** | LLM「翻訳特化」導入の調査設計。中核は Phase 207-213 / 225 で実装済み |
| 242 | [phase242-llm-coach-quality.md](phase242-llm-coach-quality.md) | **履歴** | LLM Coach 監査 A-E は完了。残項目は Phase 244 / 245 / 254 として再起案 |
| 243 | [phase243-popup-wrapper-migration.md](phase243-popup-wrapper-migration.md) | **履歴** | popup wrapper migration の原案。Phase 242-E 関連部分を実装済み、残作業は `docs/ideas/` で再起案 |
| 244 | [phase244-lexicon-yaml-extension.md](phase244-lexicon-yaml-extension.md) | **履歴** | Lexicon YAML 拡張計画。Phase 242-C で 5 エントリ追加、残作業は `docs/ideas/` で再起案 |
| 245 | [phase245-positional-difficulty.md](phase245-positional-difficulty.md) | **履歴** | Positional Difficulty 計画。Phase 192 の `difficulty/` サブパッケージで関連部分実装済み |
| 248 | [phase248-important-moves-popup.md](phase248-important-moves-popup.md) | **履歴** | 重要局面リスト popup 計画。Phase 248-γ D1/D2 で Kivy 骨格・prev/next ヘルパー実装 → **Phase 250-E で完全廃止**。代替は重要局面タブ + 黒白別 4 ボタン |

---

## 直近の完了済み（参考リンク）

完了済み Phase は実装フェーズから直接 `docs/archive/specs-implemented/` または `docs/01-roadmap.md` §4 に登録されたものが多く、本フォルダは通過していません:

- Phase 194 / 195 / 196 / 197 / 200 / 202 / 203-230 / 241-242 / 246-284 — `specs-implemented/` 参照
- Phase 198-202 / 230 / 250 / 269-284 — `docs/01-roadmap.md` §4 参照

---

## 関連ドキュメント

- [`docs/01-roadmap.md`](../../01-roadmap.md) — 全体ロードマップ
- [`docs/03-llm-validation.md`](../../03-llm-validation.md) — LLM 検証テンプレート（Phase 128 で作成、運用中）
- [`docs/archive/specs-implemented/lexicon-integration.md`](../specs-implemented/lexicon-integration.md) — Lexicon Integration Phase 45
- [`docs/archive/specs-implemented/common-improvements.md`](../specs-implemented/common-improvements.md) — LLM プロンプト注入設計ドラフト
- [`docs/archive/specs-implemented/phase80-82-ownership-consequence.md`](../specs-implemented/phase80-82-ownership-consequence.md) — Ownership Consequence

詳細は [`docs/01-roadmap.md`](../../01-roadmap.md) を参照。
