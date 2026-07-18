# Phase 249 — Kifunarabe 監査 & 改善計画

> 起票日: 2026-07-18
> ステータス: 🚧 進行中 (α マージ済み、β/γ/δ 着手中)
> 起票者: ユーザー指示 (「全て着手して修正してください」)

## 1. 動機

Phase 177 で実装された棋譜並べ機能 (kifunarabe) の監査を行い、
40 件の課題 (バグ・デッドコード・テスト不足・UX 改善・未実装 Planned 項目) を
発見した。AGENTS.md の方針 (Lv3 分割・1 Phase = 1 PR) に従い、
4 サブフェーズに分割して着手する。

## 2. 監査で見つかった課題

### P0 (クラッシュ・確実な誤動作)

| # | 内容 | 場所 |
|---|------|------|
| 1 | pass 手 (パス) が絶対に正解できない | `core/study/kifunarabe.py:_coords_equal_gtp` |
| 2 | `panels.kv:497` の `size_hint_x: self.width` が Kivy 違反 | `gui/kv/panels.kv:497` |
| 3 | メニューアイコン重複 (`Insert-Move.png` が 2 箇所) | `gui/kv/menu.kv:185` と `menu.kv:340` |

### P1 (挙動の不具合・設計の歪み)

| # | 内容 | 場所 |
|---|------|------|
| 4 | `KifunarabeController.is_fog_active` dead code | `gui/managers/kifunarabe_controller.py:175` |
| 5 | `_source_sgf_path` 属性が dead state | 同上 `__init__` |
| 6 | `_expected_move_gtp` と `_expected_gtp_from_node` の重複実装 | `core/study/kifunarabe.py` と `gui/managers/kifunarabe_guess_mixin.py` |
| 7 | Critical 3 統合テストの `test_select_critical_raises_returns_empty` が noop | `tests/test_kifunarabe_critical3_integration.py` |
| 8 | `_dismiss_summary_popup_if_open` の `contextlib.suppress(Exception)` | `gui/managers/kifunarabe_summary_mixin.py` |
| 9 | policy トグルと kifunarabe の競合 | `gui/managers/kifunarabe_toggle_mixin.py` |

### P2 (UX・堅牢性)

| # | 内容 | 場所 |
|---|------|------|
| 10 | `_kick_root_analysis` 5 回リトライ失敗時のフィードバック皆無 | `gui/popups/kifunarabe_setup_popup.py` |
| 11 | `record_guess` の move_number バリデーションなし | `core/study/kifunarabe.py` |
| 12 | policy トグル変更の動的反映なし | `gui/managers/kifunarabe_toggle_mixin.py` |
| 13 | `_last_critical_3_highlight` のリセット漏れ | 同上 |
| 14 | `_summary_popup` の `on_dismiss` 処理が未実装 | `gui/managers/kifunarabe_summary_mixin.py` |
| 15 | `contextlib.suppress(Exception)` の濫用 | 複数 mixin / popup |

### 仕様書 Planned 未着手項目 (Phase 177 §7)

| # | 内容 |
|---|------|
| 4 | 棋譜並べ成績の履歴保存 (JSON シリアライズ) — **β で着手** |
| 5 | カルテ/Batch 解析との統合 — γ で着手 |
| 6 | Active Review との基底クラス共有 — Active Review 削除済みのため obsolete |
| 7 | 重要局面ジャンプ (jump_to_next_important_move) との統合 — γ で着手 |
| 8 | 誤解析の手動報告 UI |

### UI/UX 改善余地

- summary popup の「全体率」「正解率」の 2 値表示
- Critical 3 バッジ 1.5s 自動 dismiss が短い
- `max_moves` を任意数指定可能に
- `setup_popup` の `dp(360) x dp(320)` 固定値
- i18n 「Pro-game SGF folder」/「棋譜並べ用 SGF フォルダ」整合

### テスト不足箇所

- `_kick_root_analysis` の単体テスト
- `_dismiss_summary_popup_if_open` のテスト
- `_auto_advance_until_user_turn` ループのテスト
- `handle_guess` の `evaluate_guess=None` 経路テスト
- `_do_apply_hint_toggle` の Kivy 単体テスト

### ドキュメント不足

- `docs/usage-guide.md` 独立章 (7.5.5 だけ)
- 監査ドキュメント自体
- Phase 188 仕様書で言及された `kifunarabe_state.py` が現存しない

## 3. サブフェーズ分割

### 249-α: バグ修正 + テスト追加 (Lv2) — PR #416 ✅
- 6, 4, 5, 7, 9, 11 を一掃
- 新規 / 修正テスト計 18 件 + `_kick_root_analysis` 5 件 (Kivy 依存、CI で動作)
- 既存テストの追従 5 件

### 249-β: 履歴保存 + summary popup 拡張 (Lv2-3) — 進行中
- 仕様書 Planned #4 (JSON 履歴保存) を実装
- summary popup に「履歴」ボタン追加
- summary popup に「全体率」表示追加
- 設定タブに「履歴ディレクトリ」フィールド追加
- i18n 5 キー追加 (jp / en)
- 新規テスト 12 件 (`tests/test_kifunarabe_history.py`)
- 仕様書 `docs/archive/specs-implemented/phase249-beta.md` 作成

### 249-γ: Karte 統合 + 重要局面ジャンプ統合 (Lv3) — TODO
- 仕様書 Planned #5 / #7
- 棋譜並べで WRONG_GUESS / Critical 3 を Karte に反映
- Phase 248-γ D1/D2 の `find_prev/next_important_move` を kifunarabe から呼べるように

### 249-δ: メニューアイコン + panels.kv 軽微修正 (Lv2) — TODO
- 1, 3 を解消
- `panels.kv:497` の `self.width` を Kivy 準拠に
- メニューアイコン `Insert-Move.png` 重複解消

## 4. 各 Phase のテスト方針

- **コア層** (kifunarabe.py / kifunarabe_history.py): Kivy 不要 → ローカル pass / CI pass
- **GUI 層** (mixin / popup / KV): Kivy 必要 → CI pass、ローカルは headless 制約
- **CI 整合性**: Phase 241-H の conftest.py で `KIVY_NO_ARGS=1` 等の環境変数を設定済

## 5. 影響範囲

| Phase | ファイル数 | +行 | -行 |
|-------|----------:|----:|----:|
| 249-α | 9 | +623 | -83 |
| 249-β | 8 | +650 | -20 |
| 249-γ | (予定) | +800 | -50 |
| 249-δ | (予定) | +30 | -10 |
| **合計** | | **+2100** | **-160** |

## 6. 関連ドキュメント

- Phase 177 仕様書 (§7 Planned 4 項目)
- Phase 178 仕様書 (`disable_kifunarabe_if_active`)
- Phase 179-B1/B2 仕様書 (Critical 3 統合)
- Phase 188 仕様書 (Mixin 4 分割)
- Phase 241-H 仕様書 (Kivy headless 環境変数)

## 7. マイルストーン

- 2026-07-18: 監査起票、α マージ (PR #416)
- (予定) 2026-07-18: β マージ
- (予定) 2026-07-18: γ マージ
- (予定) 2026-07-18: δ マージ
