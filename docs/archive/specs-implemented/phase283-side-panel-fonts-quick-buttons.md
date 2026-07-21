# Phase 283: サイドパネル文字サイズ縮小 fix + 新規対局 popup の 9 クイック選択ボタン空白 fix

> **ステータス**: 完了（2026-07-21）
> **レベル**: Lv2
> **PR**: #450（初回提出）→ 7b8bdb17（二次バグ追補コミット）

---

## 1. 背景

Phase 277（KivyMD 1.2.0 移行）の完了後、ユーザーから 2 つの UI 問題が報告されました：

1. **問題 1**: サイドパネルの文字（人間/通常対局/勝率/推定目差/獲得目数）が Phase 277.1 の `min(sp(N), …)` キャップで upstream v1.18.1 より小さくスクリーンショット報告
2. **問題 2**: 新規対局 popup の 9 クイック選択ボタン（komi 0.5/6.5/7.5、盤サイズ 9/13/19、置碁 0/2/9）が Phase 277 KivyMD 1.2.0 移行で invisible（背景の BackgroundMixin 枠だけ表示、内部テキストは空白）

---

## 2. 真因（2 段バグ解析）

### 2.1 第 1 バグ: SizedButton の padding 継承

Phase 277 で `SizedButton` の基底が `BaseButton`（AnchorLayout 継承）に変更された。`BaseButton` のデフォルト padding `[dp(16), dp(8), dp(16), dp(8)]` が `<QuickInputButton>` の 36×36 sp Label を **4×20 px** に潰していた。

→ 修正: `katrain/gui/kv/widgets.kv` の `<SizedButton>:` ルールに `padding: 0, 0, 0, 0` を追加

### 2.2 第 2 バグ: MDBoxLayout(adaptive_size=True) の size_hint 計算

初回 PR #450 後にユーザーから「ボタンが見えない」と再報告。ヘッドレス Kivy で実 popup を再現したところ：

- `<QuickInputButton>` の `size: 36, 36` 自体は正しく保持される
- 一方、parent の `MDBoxLayout(adaptive_size=True)` の `minimum_size` が `padding + spacing` のみで計算され `(12, 0)` に
- 各ボタンが **`0×0` に潰れて不可視**

これは `BoxLayout.do_layout` の Kivy 仕様：
> `size_hint_*=None` の子のみ minimum_size に算入

→ 修正: `katrain/gui/kv/popup_widgets.kv` の `<QuickInputButton>` に `size_hint: None, None` を追加（二次バグ追補、commit `7b8bdb17`）

---

## 3. 修正内容

### 3.1 サイドパネル文字サイズ縮小 fix（問題 1）

`katrain/gui/kv/panels.kv` の Phase 277.1 で追加された **3 つの `min(sp(N), …)` キャップ**を解除して upstream v1.18.1 と完全一致させた。

| 対象 | 旧式 | 新式 |
|------|------|------|
| `player_type` | `font_size: min(sp(15), 0.8 * self.height)` | `font_size: 0.8 * self.height` |
| `subtype_label` | `font_size: min(sp(13), self.height * 0.7)` | `font_size: self.height * 0.7` |
| `StatsLabel desc` | `font_size: min(sp(12), self.height * 0.5)` | `font_size: self.height * 0.5` |

### 3.2 新規対局 popup ボタン空白 fix（問題 2）

3.2.1 **`widgets.kv` `<SizedButton>:` ルールに `padding: 0, 0, 0, 0` を追加**
- KivyMD BaseButton → AnchorLayout のデフォルト padding をリセット
- 第 1 バグ修正

3.2.2 **`popup_widgets.kv` `<QuickInputButton>` に `size_hint: None, None` を追加**
- 第 2 バグ修正（commit `7b8bdb17`）

---

## 4. 初回提出の見落とし経緯

- PR #450 初回では (1)+(2) のみ（padding リセット）
- 14 件テスト全 pass していたが、ヘッドレス Kivy での実 popup 再現が漏れていた
- ユーザー再報告 → ヘッドレス Kivy で popup を完全再現
- MDBoxLayout の size_hint 計算ルール（`size_hint_*=None` の子のみ minimum_size 算入）を見落としていた
- 二次バグ修正 commit `7b8bdb17` で対応完了

---

## 5. 再発防止テスト（15 件）

### 5.1 `tests/test_panels_kv_fonts.py` (6 tests)

- フォント式が `0.8 * self.height` / `self.height * 0.7` であることを静的ガード
- AI ブランチの短縮式保持
- `min(sp(…))` 再混入をファイル全体 grep で防止

### 5.2 `tests/test_sized_button_padding.py` (8 tests)

- `<SizedButton>:` の `padding: 0` 存在
- 16dp 再注入禁止
- Phase 283 コメント存在
- 9 QuickInputButton のテキストと出現回数
- QuickInputButton サイズ不変
- `target.text = self.text` 不変
- SizedButton padding が Python あるいは KV いずれかでリセット

### 5.3 既存テスト経由

- 1 件の既存テスト経由（合計 15 件、Phase 283 baseline 6118 → 6183 PASS + 3 SKIP）

---

## 6. 副作用検証

- Phase 277.1 が同時修正した「KivyMD 1.2.0 Dark テーマ視覚回帰」は Phase 281 で `__main__.py` 側に `theme_cls.theme_style = 'Dark'` で恒久対応済み
- 本 Phase でキャップ解除しても新規の視覚問題は発生しない
- 既存 i18n / dispatch / menu / popup は全て不変

---

## 7. 保持された概念

- Phase 277 / 281 で追加した KivyMD 1.2.0 互換コード
- `TabbedPanel` 等の他 SizedButton 派生（NewGameModeButton 等、十分な幅があるため padding 影響なし）
- Phase 277 の `BaseButton` 単一基底構造

---

## 8. 検証結果

```
mypy katrain: 0 issues (310 source files)
ruff check: clean
ruff format: clean
pytest tests: 6183 PASS + 3 SKIP (Phase 282 baseline 6118 → +65 件、うち +15 新規 + 既存 50 件経由)
```

---

## 9. 関連 Phase

- **Phase 277**: KivyMD 0.104.1 → 1.2.0 移行（本 Phase の真因、BaseButton 統合 / padding 追加）
- **Phase 281**: 日本語フォント tofu fix（本 Phase で `popup_widgets.kv` 変更時の回帰テスト役）
- **Phase 280**: AI 戦略スリム化（本 Phase で変更していない別系統）

---

## 10. 関連ドキュメント

- `AGENTS.md` §1.3（直近マイルストーン）
- `docs/01-roadmap.md` §4（Phase 283 詳細）
- `docs/02-code-structure.md` §4.10（UI 整理の Phase 283 言及）
- `docs/usage-guide.md`（UI 操作ガイド）