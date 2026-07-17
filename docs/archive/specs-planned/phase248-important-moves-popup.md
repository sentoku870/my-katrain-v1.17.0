# Phase 248-γ: 重要局面リスト popup + ジャンプ + Curator 統合

> Status: **設計ドキュメント / スケルトン** (Phase 248-γ-D1/D2/E1)
> 実装本体は次フェーズで着手予定 (推定 +1,500 行 / 30+ テスト)

## 動機

Phase 248 調査 §D1:
> 重要局面リストを一覧する GUI がない。Phase 230-A.2 で「複数局まとめ」UI が
> 削除されたが、「単局の重要局面リスト」も独立 UI として存在しない。
> ユーザーは controlspanel の info.text で現在のノードの hint しか見られない。

Phase 248 調査 §D2:
> 重要局面に「移動 / ジャンプ」する UI がない。盤面クリックで特定の
> 手にジャンプはできるが、重要局面リストから該当局面に直接ジャンプする
> 手段がない。

Phase 248 調査 §E1:
> curator_hint (CURATOR_WEAK_AXIS) が critical_3 に反映されない。
> ユーザーが苦手な overplay を 3 回やった試合でも、critical_3 には
> 別タグの局面が出る。優先度チェーンに「ユーザー弱点タグ」を加える価値あり。

## γ-D1: 重要局面リスト popup

### UI 概要

新規 popup: **「重要局面リスト」**

```
┌─ 重要局面リスト ────────────────────────────┐
│  棋譜: 2026-07-17 vs fox (B+R)               │
│  重要度レベル: 標準 (1.0/0.5/0.3)             │
│  重要局面: 3/3 black + 2/3 white             │
│  ─────────────────────────────────────────  │
│  #1 (B) move 17 R8    6.0目  territorial_loss│
│  #2 (B) move 5  F17   2.5目  territorial_loss│
│  #3 (B) move 23 E4   ...                     │
│  #1 (W) move 34 B6   12.0目 territorial_loss│
│  #2 (W) move 12 D3   ...                     │
│  ─────────────────────────────────────────  │
│  [この局面にジャンプ] [コピー] [閉じる]      │
└────────────────────────────────────────────┘
```

### 実装

- **新ファイル**: `katrain/gui/popups/important_moves_popup.py`
- **KV ファイル**: `katrain/gui/kv/important_moves_popup.kv`
- **データソース**: `select_critical_moves(game, max_moves=N)` の戻り値
  (Phase 248-β2 で N が可変化済)
- **state 統合**: popup 表示中に game 状態が変化したら refresh

#### 主要 API

```python
def show_important_moves_popup(katrain, max_moves: int = 3,
                                level: str = "normal") -> None:
    """Open the important-moves-list popup.

    Reads the current game from ``katrain.game`` and shows the
    critical_3 candidates for both players in a single scrollable
    list. Selecting an entry calls ``katrain.game.set_current_node``
    so the board view jumps to the chosen move.
    """
```

#### i18n キー (追加予定)

| キー | 日本語 | English |
|------|--------|---------|
| `mykatrain:popup:important_moves:title` | 重要局面リスト | Important moves |
| `mykatrain:popup:important_moves:subtitle` | 重要度レベル: {level} | Level: {level} |
| `mykatrain:popup:important_moves:count` | {shown}/{max} 件 | {shown}/{max} shown |
| `mykatrain:popup:important_moves:jump` | この局面にジャンプ | Jump to this move |
| `mykatrain:popup:important_moves:copy` | コピー | Copy |
| `mykatrain:popup:important_moves:close` | 閉じる | Close |
| `mykatrain:popup:important_moves:empty` | 重要局面がありません (KataGo 解析が必要) | No important moves (run KataGo analysis) |
| `mykatrain:popup:important_moves:complexity` | 複雑局面で割引 | Discounted (chaotic) |

### メニュー統合

- `MyKatrainMenuSection` に新項目追加:
  - 「重要局面リスト」 → クリックで `show_important_moves_popup` 呼び出し
- DISPATCH_TABLE に `important_moves_popup` エントリ追加

## γ-D2: 重要局面ジャンプボタン

### UI 概要

controlspanel に **新しい 2 ボタン** を追加:

```
┌─ コントロールパネル ────────────────────────┐
│  [<< 前]  [前重要局面]  [次重要局面]  [後 >>] │
│                                              │
│  (情報テキスト)                              │
│  ...                                         │
└──────────────────────────────────────────────┘
```

- **前重要局面** (Previous important move): `current_node` の前にある重要局面へジャンプ
- **次重要局面** (Next important move): `current_node` の次にある重要局面へジャンプ
- 端まで来ると無効化 (グレーアウト)

### 実装

- **変更ファイル**: `katrain/gui/controlspanel.py`
- **新ヘルパー**: `_jump_to_important_move(direction: Literal["prev", "next"]) -> bool`
  - `select_critical_moves(game, max_moves=99)` で全 candidate を取得 (上限緩和)
  - `current_node.depth` 未満/超過のものをフィルタ
  - その中で最深/最浅を選択
  - `game.set_current_node(node)` でジャンプ
- **i18n キー追加**: 2 ボタン分のラベル

### 既存機能との非互換性

- 既存の `MoveTreeWidget` (盤面下の「next/prev move」) とは独立。混同しないよう
  ラベルを「重要局面」に明示。

## γ-E1: Curator profile を pick_important_moves に統合

### 設計

`pick_important_moves(level=..., streak_start_moves=...)` の新パラメータ:
```python
def pick_important_moves(
    snapshot: EvalSnapshot,
    level: str = "normal",
    *,
    user_weak_tags: dict[str, int] | None = None,  # Phase 248-γ-E1 NEW
    weak_tag_boost: float = 0.5,                  # NEW
    ...
) -> list[MoveEval]:
    """Pick important moves from the snapshot.

    Phase 248-γ-E1: ``user_weak_tags`` adds a multiplicative
    boost to the importance score for moves whose
    ``meaning_tag_id`` appears in the user's Curator profile.
    Boost factor: ``1 + weak_tag_boost * log(occurrence_count + 1)``
    so the first weak-tag occurrence gets a modest bump and
    repeats get progressively larger bumps.
    """
```

### 実装

- **変更ファイル**: `katrain/core/analysis/logic_importance.py`
- **新ロジック**: `compute_importance_for_moves` 内で
  `move.meaning_tag_id in user_weak_tags` のときに importance を
  ブースト
- **呼び出し元**: `gui/features/karte_export.py` で
  `ctx.config("mykatrain_settings/curator_profile")` から
  user_weak_tags をロード

### 期待される挙動

- ユーザーが **overplay** を 5 回繰り返したゲームで、
  pick_important_moves は **overplay タグの手を優先的に** critical_3 に
  選ぶ
- ブーストなし → 通常の importance 順
- カウント 0 → ブーストなし

## 進捗

| 項目 | 状態 |
|------|------|
| 設計ドキュメント | **完了** (本ファイル) |
| γ-D1 スケルトン | **完了** (i18n キー + 主要 API シグネチャ) |
| γ-D2 設計 | **完了** (controlspanel への追加設計) |
| γ-E1 設計 | **完了** (pick_important_moves 拡張仕様) |
| γ-D1 実装 | **未着手** (次フェーズ) |
| γ-D2 実装 | **未着手** (次フェーズ) |
| γ-E1 実装 | **未着手** (次フェーズ) |

## 実装時の TODO

- [ ] `katrain/gui/popups/important_moves_popup.py` 新規
- [ ] `katrain/gui/kv/important_moves_popup.kv` 新規
- [ ] `katrain/gui/features/menu.py` (or equivalent) に新項目追加
- [ ] `katrain/gui/controlspanel.py` に Prev/Next ボタン追加
- [ ] `katrain/core/analysis/logic_importance.py` に `user_weak_tags` 追加
- [ ] `katrain/gui/features/karte_export.py` で `curator_profile` ロード
- [ ] i18n jp/en 8-10 キー追加
- [ ] テスト 30+ 件 (popup mock, jump logic, weak tag boost)
- [ ] docs/usage-guide.md 7.7 節追加 (D1/D2/E1 使い方)

## 推定工数

- γ-D1: 4-6 時間 (popup レイアウト + state 統合)
- γ-D2: 1-2 時間 (ボタン + jump ロジック)
- γ-E1: 2-3 時間 (resolver + karte_export 統合)

合計 7-11 時間 = 1 セッションで 1-2 PR が現実的
