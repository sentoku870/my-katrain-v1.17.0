## 概要

ユーザー報告のサマリー機能調査で特定した 11 件のバグ・改善余地を 9 サブ修正に分けて一括で対応。

## サブフェーズ

| Phase | 種別 | 内容 | 影響度 |
|-------|------|------|--------|
| 241-A | バグ | weakness pattern から good カテゴリ除外 | 高 |
| 241-B | バグ | popup の unknown パス早期 return | 高 |
| 241-C | 改善 | loss_progression フォールバック | 中 |
| 241-D | リファクタ | _summary_index_to_internal sentinel 化 | 中 |
| 241-E | バグ | summary_perspective_index race condition 対策 | 中 |
| 241-F | リファクタ | detect_player_color_for_user の _SgfInfoLike + cast() 廃止 | 中 |
| 241-G | 削除 | find_latest_karte 関数完全削除 | 低 |
| 241-H | 環境 | tests/conftest.py に Kivy headless 設定追加 | 中 |
| 241-I | ドキュメント | AGENTS.md / 01-roadmap.md 更新 | 低 |

## 主な修正

### 241-A: weakness pattern から good 除外

`extract_summary_weakness_patterns` の Shape B 経路で "good" を除外。LLM プロンプトに "good" が弱点として並ぶ問題を解消（実害）。`_NON_WEAKNESS_CATEGORIES = frozenset({"good"})` 定数新設。

### 241-B: popup の unknown パス早期 return

popup で karte/summary どちらにも判別できない JSON を開いた場合、silent に karte 経路に流れる問題を修正。`llm-coach:unknown-path` i18n キー追加（jp/en）。`_populate_rank_and_perspective` / `on_generate_and_copy` / `on_validate` 全 3 経路に guard 追加。

### 241-C: loss_progression フォールバック

`_format_loss_progression_block` ヘルパー新設。dict / legacy flat list / 空 bucket list 3 形式対応。テンプレートに「Loss Progression (per game-type)」セクション追加。

### 241-G: find_latest_karte 関数完全削除

popup は既に `find_latest_llm_input_for_ctx` を使用。Phase 239 表記を Phase 241-G に統一。

## テスト

- 17 ファイル変更、+607 / -142 行
- 39 unit tests 追加
- 既存 3 件テスト更新（good 除外に伴う assertion 修正）
- 既存 4 件テスト削除（find_latest_karte 関連）
- 合計 864 件テスト合格（summary/coach 関連、popup テストは Kivy headless 環境依存）

## 注

- main に既存の Phase 238/239/240 が存在するため、本バッチは Phase 241 として採番
- popup テストの Windows headless 環境失敗は KivyMD 互換性問題（既存）
