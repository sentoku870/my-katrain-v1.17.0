# Phase 230 マスター仕様書: MyKatrain UI/UX 整理

> **ステータス**: 完了（2026-07-16）
> **Lv**: 3
> **影響範囲**: 23 ファイル + 新規 1 ファイル、合計 約 -726 行
> **テスト**: 既存 5,572 件合格継続

---

## 1. 背景・問題提起

myKatrain fork の MyKatrain メニューと settings popup に、以下の UI/UX 課題が蓄積していた:

1. **メニュー項目が多すぎる**: 8 項目のうち 3 項目（最新レポートを開く / 出力フォルダを開く / 複数局まとめ）が低頻度。OS のファイルマネージャやフォルダ一括解析で代替可能
2. **Leela 検証用の孤立 UI**: Phase 171 で Leela エンジンを完全削除したにもかかわらず、解析設定タブに `KataGo エンジンを無効にする (Leela の検証用)` チェックボックスと `engine-compare:*` i18n 35 キーが残存
3. **棋力入力欄の重複**: 解析設定タブに `棋力` (general/player_rank) と、出力設定タブに `ユーザー棋力(任意)` (mykatrain_settings/default_user_rank) の 2 つの同種入力が存在
4. **棋譜並べタブの説明途切れ**: チェックボックス行の固定 `dp(36)` 高さ + 有限 `text_size` により、32 文字の最長ラベルが 2 行目を黙ってクリップ
5. **診断設定が独立メニュー**: myKatrain 設定内のタブに統合すれば十分

---

## 2. 解決策

5 つのサブフェーズに分割して段階的に実施:

| Sub | 概要 | リスク | Lv |
|-----|------|--------|-----|
| **230-B** | Leela 残滓削除 | 低 | 1 |
| **230-C** | 棋譜並べタブ途切れ修正 | 低 | 1 |
| **230-D** | 診断タブ新設 + メニュー統合 | 中 | 3 |
| **230-E** | 棋力入力統合 + 自動マイグレーション | 中 | 2-3 |
| **230-A** | MyKatrain メニュー整理 | 中 | 2 |
| **230-A.1** | `MyKatrainMenuSectionHeader` クラッシュ修正 | 低 | 1 |
| **230-A.2** | 3 機能（最新レポート・出力フォルダ・複数局まとめ）完全削除 | 中 | 2 |

実行順序: 230-B → 230-C → 230-E → 230-D → 230-A → 230-A.1 → 230-A.2

---

## 3. サブフェーズ別詳細

### 3.1 Phase 230-B: Leela 残滓削除（Lv1）

**変更ファイル**:
- `katrain/gui/features/settings_popup_tabs/analysis_tab.py` — `_build_disable_katago_section` 削除、`_build_engine_section` の spacer 削除
- `katrain/gui/features/settings_popup_state.py` — `selected_disable_katago` フィールド削除
- `katrain/gui/features/settings_popup_savers.py` — `_save_mykatrain_settings` から `disabled_katago` 引数と `engine/disabled` 更新削除
- `katrain/gui/features/settings_popup.py` — state 初期化と save_settings から disable_katago 参照削除
- `katrain/i18n/locales/{jp,en}/LC_MESSAGES/katrain.po` — `mykatrain:settings:disable_katago` + `engine-compare:*` (35 キー) 削除、`.mo` 再コンパイル
- `tests/test_settings_savers.py` — `test_updates_engine_disabled_flag` 削除、`test_disabled_false_passes_through` 削除

### 3.2 Phase 230-C: 棋譜並べタブ途切れ修正（Lv1）

**問題**: `_build_display_checkbox` (kifunarabe_tab.py:100-112) の固定 `height=dp(36)` + `text_size=(lbl.width, lbl.height)` で、32 文字の最長ラベル `kifunarabe_auto_toggle_markers` の 2 行目が黙ってクリップ。

**修正**: 行高さを可変化、`text_size` を `(width, None)` に変更、`texture_size[1]` へ row.height バインド（最小 `dp(36)` クランプ）。help セクションも同様に可変化。

### 3.3 Phase 230-D: 診断タブ新設 + メニュー統合（Lv3）

**変更ファイル**:
- `katrain/gui/features/settings_popup_tabs/diagnostics_tab.py` — 新規。`diagnostics_popup.py` の `_collect_diagnostics` / `_build_info_display` を再利用、ボタン handlers は `_on_generate_zip(parent_popup=None)` / `_on_copy_info` を呼ぶ
- `katrain/gui/features/settings_popup_tabs/__init__.py` — 遅延ロード追加
- `katrain/gui/features/settings_popup.py` — 第 4 タブ追加
- `katrain/gui/features/diagnostics_popup.py` — `_on_generate_zip` / `_on_generate_complete` の `parent_popup` 省略可能化
- `katrain/gui/kv/menu.kv` — 診断情報項目削除
- `katrain/gui/features/commands/__init__.py` — `_DISPATCH_KEYS` から `diagnostics_popup` 削除
- `katrain/gui/features/commands/popup_commands.py` — `do_diagnostics_popup` 削除
- `tests/test_dispatch_table.py` — 関連エントリ削除
- i18n: `mykatrain:settings:tab_diagnostics` 新設

### 3.4 Phase 230-E: 棋力入力統合 + 自動マイグレーション（Lv2-3）

**変更ファイル**:
- `katrain/gui/features/settings_popup_tabs/export_tab.py` — `_build_default_user_rank_row` 削除、`widget_refs["rank_input"]` 削除
- `katrain/gui/features/settings_popup_tabs/analysis_tab.py` — player_rank セクションに `mykatrain:settings:player_rank_usage` ヘルプテキスト追加
- `katrain/gui/features/settings_popup_savers.py` — `migrate_default_user_rank()` 追加（Kivy 非依存）
- `katrain/gui/features/settings_popup.py` — popup 起動時にマイグレーション実行
- i18n: `player_rank_usage` 新設、`default_user_rank` 削除
- テスト: 5 マイグレーションテスト追加

**マイグレーションルール**:
- `player_rank` 空 + `default_user_rank` 設定 → `player_rank` へコピー
- `player_rank` 設定 + `default_user_rank` 設定 → `player_rank` 維持、`default_user_rank` クリア
- `default_user_rank` 常にクリア

### 3.5 Phase 230-A: MyKatrain メニュー整理（Lv2）

**初回実装（Phase 230-A）**:
- メニュー 8 項目 → 4 項目（メイン）+ 3 項目（「その他」セクション）に分割
- アイコン再割り当て（`analysis.png` 5 重複 → 固有アイコン）
- `chat.png`（存在しない）→ `Teaching-Settings.png` に修正
- `MyKatrainMenuSectionHeader` KV ルール + Python クラス追加

**Phase 230-A.1（バグ修正）**:
- `MyKatrainMenuSectionHeader` を `Label` から派生させたが、`badukpan.py:725` が `content_width` 属性を読むためクラッシュ
- `kivyutils/_panels.py` に `MDBoxLayout` ベースのクラスを新設し、`content_width` / `text` / `font_name` プロパティを追加

**Phase 230-A.2（最終形）**:
- 「その他」セクション + 3 機能を完全削除
- メニューは **4 項目のみ**（カルテ出力 / LLM コーチ / フォルダ一括解析 / myKatrain 設定）に整理
- `MyKatrainMenuSectionHeader` クラスも不要になったため削除

### 3.6 Phase 230-A.2 削除された機能と代替手段

| 削除機能 | 代替手段 |
|----------|---------|
| 最新レポートを開く | OS のファイルマネージャで出力フォルダを開く |
| 出力フォルダを開く | 同上（settings の出力ディレクトリ設定で確認可能） |
| 複数局まとめ | フォルダ一括解析（メニュー）でサマリを生成、個別レポートは OS で開く |

---

## 4. 影響範囲サマリ

### 削除されたコード（合計 約 726 行）

| 区分 | 行数 |
|------|------|
| `summary_ui.py` 完全削除 | -495 |
| `summary_manager.py` UI メソッド削除 | -95 |
| `report_navigator.py` 2 関数削除 | -65 |
| `export_commands.py` 4 ハンドラ削除 | -50 |
| `kifunarabe_tab.py` 可変化 | -46 |
| `analysis_tab.py` disable_katago 削除 | -43 |
| `menu.kv` 整理 | -30 |
| `popup_commands.py` do_diagnostics 削除 | -11 |
| `__init__.py` dispatch table 整理 | -8 |
| i18n `.po` 整理 | -150 |
| その他（テスト更新等） | -100 |

### 追加されたコード（合計 約 425 行）

| 区分 | 行数 |
|------|------|
| `diagnostics_tab.py` 新規 | +100 |
| `analysis_tab.py` player_rank_usage ヘルプ | +20 |
| `settings_popup_savers.py` migrate_default_user_rank | +45 |
| テスト 5 件追加（migration） | +100 |
| テスト更新（既存テスト修正） | +50 |
| その他（i18n 追加等） | +110 |

---

## 5. テスト結果

- **既存 5,572 件テスト合格継続**
- 新規テスト 5 件（マイグレーション）
- Kivy 関連テスト（環境依存）は pre-existing failures（修正前後で変化なし）

---

## 6. ユーザー視点の効果

### Before（修正前）
- MyKatrain メニュー: 8 項目（うち 3 項目は低頻度）
- 解析設定タブ: KataGo 無効化チェックボックス（孤立機能）
- 棋譜並べタブ: 最長ラベルの 2 行目が見切れる
- 棋力入力: 2 箇所に分散（混乱の元）
- 診断: 独立メニュー項目

### After（修正後）
- MyKatrain メニュー: 4 項目のみ（スッキリ）
- 解析設定タブ: KataGo 固定表示のみ（Leela 残滓なし）
- 棋譜並べタブ: 全ラベル完全表示
- 棋力入力: 解析設定タブの 1 箇所のみ + 用途ヘルプ表示
- 診断: myKatrain 設定 → 「診断」タブ（統合）

---

## 7. 関連 Phase

- **Phase 171** (2026-07-04): Leela エンジン完全削除（本 Phase 230-B で UI 残滓も削除完了）
- **Phase 177** (2026-07-12): 棋譜並べ機能追加（本 Phase 230-C で UI 改善）
- **Phase 229** (2026-07-15): 棋力プリセット統一（本 Phase 230-E で残っていた default_user_rank を統合完了）

---

## 8. 次のステップ（将来 Phase として提案済み）

| Phase | 内容 |
|-------|------|
| 231 | `controlspanel.py` Details 日本語ハードコード解消（良/軽/悪/大悪、手の自由度、一択/狭い/広い/普通） |
| 232 | `summary_formatter.py` Markdown / ファイル名 日本語ハードコード解消 |
| 233 | Batch/Diagnostics ポップアップのボタンスタイル統一（raw kivy.Button → SizedRoundedRectangleButton） |
| 234 | kifunarabe を MyKatrain ドロップダウンへ移動（ハンバーガーメニュー → MyKatrain 配下） |
| 235 | 孤立 i18n キー（training-set/player-profile/practice-report/skill_radar）の完全削除 |