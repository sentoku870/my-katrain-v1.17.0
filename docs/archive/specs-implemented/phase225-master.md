# Phase 225 マスター仕様書 — LLM Coach 統合（Phase 225 + 225.1〜225.8）

> 起票日: 2026-07-17
> 最終更新: 2026-07-15（Phase 226-E）
> ステータス: ✅ 完了（全サブフェーズ）

## 1. 概要

Phase 225 では **手動貼付ワークフロー**で動作する LLM Coach GUI を導入した。
以降 Phase 225.1〜225.8 で段階的にバグ修正・機能拡張を実施した。

このドキュメントは Phase 225 マスターの **索引** として機能する。
各サブフェーズの実装詳細は AGENTS.md §10 および個別ログ（git history）を参照。

## 2. サブフェーズ一覧

| Phase | 概要 | 主な変更 |
|-------|------|---------|
| 225 | LLM Coach GUI 統合（手動貼付ワークフロー） | Popup / KV / DISPATCH_TABLE 登録 |
| 225.1 | `do_export_karte` 引数抜け TypeError 修正 | popup_commands.py |
| 225.2 | `karte_export.copy_path` Clock NameError 修正 | on_success / on_submit 両 bind |
| 225.3 | ボタン整列 + ids 経由テキスト読み出し | KV レイアウト再設計 |
| 225.4 | ボタン幅完全固定 + 使い方ヒント表示 | SizedRoundedRectangleButton 統一 |
| 225.5 | status/result stale ref 修正 + 検証サマリ件数表示 | 全 setter を ids 経由に統一 |
| 225.6 | 視点自動判定 + SGF 棋力自動取得 | sgf_player_info.py + player_color |
| 225.7 | Popup 幅拡大 + 自動判定タイミング修正 + LLM 応答はみ出し修正 | 900x720 + 0.2s 遅延 + リトライ |
| 225.8 | 漢字段級サポート + mykatrain settings に `default_user_rank` 追加 | _RANK_ALIASES + _normalise_rank_str |

## 3. 関連ドキュメント

- 既存詳細仕様: `docs/archive/specs-implemented/phase225-llm-coach-gui.md` (Phase 225.6)
- AGENTS.md §1.3「現在のフェーズ」と §10「変更履歴」に各 Phase のログ
- Phase 226-A〜E は LLM Coach 機能の包括的品質改善（別 Phase）

## 4. テスト状況

- Phase 225 完了時: 全 4882 件テスト合格
- Phase 225.1-225.8 累計: 約 5070 件テスト合格
- Phase 226 完了時（このドキュメント時点）: 5116 件テスト合格（GUI系は環境依存）

## 5. Phase 226 サブフェーズとの対応

Phase 226 では LLM Coach 機能の品質改善を 5 つのサブフェーズで実施:

| Phase | テーマ | 主な改善 |
|-------|--------|---------|
| 226-A | 検証ロジック強化 | Lexicon検証の修正、症状ID 3段階フォールバック、着手番号/pointsLost 正規表現厳格化、player_color 整合性検証、tolerance 活用 |
| 226-B | GUI 堅牢性 | Clock 再試行最大回数+on_dismissキャンセル、ハードコード日本語 i18n化、Spinner安定内部値、detect_player_info キャッシュ化、例外表示統一 |
| 226-C | データ・設定不整合解消 | _RANK_ALIASES デッドコード解消、config.json に default_user_rank、estimate_mode_from_loss docstring 修正、detect_json_type 精緻化 |
| 226-D | テスト強化・CI 整備 | CI skip 解消、validator 境界値テスト、settings_export フィクスチャ更新 |
| 226-E | 軽微な品質改善 | クラス名タイポ修正、avg_points_lost 意図省略明示、関西弁定義同期契約、rank-auto msgstr 更新 |