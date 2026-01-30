# Phase 87 実装計画

> **スコープ確定**: A: タイト（Player軸 + テンプレート追加のみ）
> **修正レベル**: Lv2（2-4ファイル、~200行）
> **Git ブランチ**: `feature/2026-01-30-phase87-signature-player`

## 概要

Phase 87は「調整・拡張・磨き込み用バッファ」フェーズです。
Phase 84-86で構築されたパターンマイニング・Reason Generatorシステムの拡張と調整を行います。

---

## 重要な設計決定

### 1. Player の正規表現（Canonical Representation）

**コードベース調査結果**:
- `MoveEval.player: Optional[str]` は `'B' / 'W' / None` と明記 (models.py:282)
- 実際の使用例: `s.player == "B"`, `s.player == "W"` (ai.py:615-616)
- **enum や "black"/"white" は使用されていない**

**正規形式**: `"B"` / `"W"` / `"?"` (str型)

| 入力 | 正規化結果 | 備考 |
|------|-----------|------|
| `"B"` | `"B"` | そのまま |
| `"W"` | `"W"` | そのまま |
| `"b"` | `"B"` | 小文字対応（防御的） |
| `"w"` | `"W"` | 小文字対応（防御的） |
| `None` | `"?"` | ルートノード等 |
| `""` | `"?"` | 空文字 |
| その他 | `"?"` | 安全なフォールバック |

**実装**: `normalize_player()` ヘルパー関数を追加

```python
def normalize_player(player: Optional[str]) -> str:
    """Normalize player to canonical format.

    Args:
        player: Raw player value from MoveEval

    Returns:
        "B", "W", or "?" (unknown/pass)

    Note:
        MoveEval.player is documented as 'B'/'W'/None.
        Defensive: accepts lowercase, returns "?" for anything else.
    """
    if player is None:
        return "?"
    upper = player.upper()
    if upper == "B":
        return "B"
    if upper == "W":
        return "W"
    return "?"
```

**テストケース** (test_pattern_miner.py に追加):
```python
class TestNormalizePlayer:
    """Tests for normalize_player() helper."""

    @pytest.mark.parametrize("input_val,expected", [
        ("B", "B"),
        ("W", "W"),
        ("b", "B"),  # lowercase accepted
        ("w", "W"),  # lowercase accepted
        (None, "?"),
        ("", "?"),
        ("X", "?"),
        ("black", "?"),  # not supported, falls back to "?"
    ])
    def test_normalize_player(self, input_val, expected):
        from katrain.core.batch.stats.pattern_miner import normalize_player
        assert normalize_player(input_val) == expected
```

**適用箇所**:
- `create_signature()` で正規化して `MistakeSignature.player` に設定
- **`player == "?"` の場合は `create_signature()` で `None` を返してスキップ**
- これにより、有効なパターンは必ず `player == "B"` or `"W"` のみ
- i18n の `pattern:player-unknown` キーは防御的フォールバック用（通常は到達しない）

### 2. 表示形式とi18n

**方針**: ローカライズラベルを使用（Option B）

| player値 | JP表示 | EN表示 | i18nキー | 備考 |
|---------|--------|--------|----------|------|
| `"B"` | 黒 | Black | `pattern:player-black` | 通常パス |
| `"W"` | 白 | White | `pattern:player-white` | 通常パス |
| `"?"` | 不明 | Unknown | `pattern:player-unknown` | **防御的フォールバック** |

**"?" の扱い（決定済み）**:
- `create_signature()` で `player == "?"` の場合は `None` を返してスキップ
- よって `MistakeSignature.player` は常に `"B"` or `"W"` のみ
- `pattern:player-unknown` キーは将来の拡張やエッジケース用の防御的フォールバック

**出力例**:
- JP: `"1. **序盤 / 隅 / ミス (direction_error) [黒]**: 2回, 6.5目"`
- EN: `"1. **Opening / Corner / Mistake (direction_error) [Black]**: 2 times, 6.5 pts"`

### 3. create_signature() の None 契約

**現在の実装** (pattern_miner.py:230-275):
- `create_signature()` は `Optional[MistakeSignature]` を返す
- 以下の場合に `None` を返す:
  - `loss < LOSS_THRESHOLD`
  - `severity not in {mistake, blunder}`
  - `player is None` ← 既存チェック
  - `area is None` (pass/resign)

**mine_patterns() での処理** (pattern_miner.py:305-307):
```python
sig = create_signature(move_eval, total_moves, board_size)
if sig is None:
    continue  # ← 明示的にスキップ済み
```

**決定**: 現状維持（None 返却 + 呼び出し側でスキップ）
- Phase 87 では `normalize_player(...)=="?"` の場合も `None` を返す
- `mine_patterns()` は既に `None` をスキップするので追加変更不要

### 4. 破壊的変更の影響範囲

**MistakeSignature 使用箇所一覧**:

| ファイル | 行 | 用途 | 更新内容 |
|---------|-----|------|---------|
| `pattern_miner.py` | 60-77 | クラス定義 | player フィールド追加 |
| `pattern_miner.py` | 270-275 | 生成 | player 引数追加 |
| `pattern_miner.py` | 299, 322 | Dict キー | ハッシュ変更で自動対応 |
| `pattern_miner.py` | 342 | ソート | sort_key() 更新 |
| `__init__.py` | 40, 141 | エクスポート | 変更不要 |
| `test_pattern_miner.py` | 81, 92, 102, 103, 108, 134, 146 | テスト | player 引数追加 |

**ハッシュ/等価性の影響**:
- 同じ (phase, area, tag, severity) でも player が異なれば別パターンとして集計
- これは意図した動作（黒/白の分離分析が目的）

### 5. ワイルドカード優先順位（既存仕様を文書化）

`_find_combo_match()` のマッチング優先度（reason_generator.py:206-246）:

1. **完全一致** `(phase, area, tag)` → 最優先
2. **エリアワイルドカード** `(phase, "*", tag)` → 2番目
3. **フェーズワイルドカード** `("*", area, tag)` → 3番目
4. **単一タグフォールバック** → 最後

**優先順位テスト設計** (test_reason_generator.py):

既存テンプレートでは真の優先順位競合が起きないため、テスト用にモックを使用:

```python
from unittest.mock import patch
from katrain.core.analysis.reason_generator import (
    COMBINATION_REASONS,
    ReasonTemplate,
    generate_reason,
)

class TestWildcardPrecedence:
    """Tests to lock wildcard matching priority."""

    def test_exact_beats_area_wildcard(self):
        """Exact (phase, area, tag) beats (phase, '*', tag)."""
        # Inject exact template that competes with existing ("middle", "*", "overplay")
        test_combo = {
            ("middle", "center", "overplay"): ReasonTemplate(jp="EXACT_JP", en="EXACT_EN"),
        }
        # Patch the module-level dict used by generate_reason()
        with patch.dict(
            "katrain.core.analysis.reason_generator.COMBINATION_REASONS",
            test_combo
        ):
            result = generate_reason("overplay", phase="middle", area="center", lang="jp")
            # Assert injected template is selected (not wildcard)
            assert result == "EXACT_JP"

    def test_area_wildcard_when_no_exact(self):
        """Area wildcard matches when no exact template exists."""
        # ("middle", "*", "overplay") exists, no exact for ("middle", "edge", "overplay")
        result = generate_reason("overplay", phase="middle", area="edge", lang="jp")
        # Should get wildcard template, not None
        assert result is not None

    def test_fallback_to_single_tag(self):
        """No combo match falls back to single tag template."""
        # No combo for (opening, center, slow_move)
        result = generate_reason("slow_move", phase="opening", area="center", lang="jp")
        assert result is not None
```

**設計ポイント**:
- `patch.dict()` にモジュール完全修飾パス `"katrain.core.analysis.reason_generator.COMBINATION_REASONS"` を使用
- 脆弱な自然言語文字列アサーションを避け、注入されたテンプレート `"EXACT_JP"` が選択されることを検証

### 6. 決定論的ソートとGoldenテスト

**ソートキー** (更新後):
```python
def sort_key(self) -> Tuple[str, str, str, str, str]:
    return (self.phase, self.area, self.primary_tag, self.severity, self.player)
```

**ソート順**: phase → area → primary_tag → severity → player（アルファベット順）
- "B" < "W" < "?" となり決定論的

**Goldenテストへの影響**:

| Task | 影響する可能性 | 理由 |
|------|--------------|------|
| Task 1 | **あり** | パターン行に `[黒]/[白]` が追加される |
| Task 2 | **あり得る** | 新テンプレートがgoldenデータにマッチすればreason行が追加 |

**現在のgolden出力** (summary_output.txt:80-81):
```
1. **Opening / Corner / Blunder (overplay)**: 3 times, total loss 15.0 pts
   - game_1.sgf #25(B), game_2.sgf #25(B), game_3.sgf #25(B)
```
↑ Task 2 で `("opening", "corner", "overplay")` を追加するとreason行が追加される

**更新手順**:
1. Task 1 完了後: `uv run pytest tests/test_golden_summary.py` で差分確認
2. 差分レビュー: `[黒]/[白]` 追加を確認
3. 更新: `uv run pytest tests/test_golden_summary.py --update-golden`
4. Task 2 完了後: 再度 `uv run pytest tests/test_golden_summary.py` で差分確認
5. reason行追加があれば差分レビュー後に更新

---

## 現在の実装状態

### Phase 84-86で完成したシステム

| Phase | 成果物 | 主要ファイル |
|-------|--------|-------------|
| 84 | パターンマイニング | `pattern_miner.py` (MistakeSignature, mine_patterns) |
| 85 | サマリ統合 | `summary_formatter.py` (Recurring Patternsセクション) |
| 86 | Reason Generator | `reason_generator.py` (12単発+8組み合わせテンプレート) |

### 現在のパラメータ

| パラメータ | 値 | ファイル |
|-----------|-----|---------|
| LOSS_THRESHOLD | 2.5目 | pattern_miner.py |
| min_count | 2 | pattern_miner.py / summary_formatter.py |
| top_n | 5 | pattern_miner.py / summary_formatter.py |
| 組み合わせテンプレート | 8個 | reason_generator.py |
| MEANING_TAG_WEIGHTS | 12タグ (0.5-1.5) | critical_moves.py |

---

## Phase 87 スコープ

### MVP (必須)

#### Task 1: MistakeSignature に player 軸を追加 (Lv2)

**目的**: パターンを黒/白で分離し、「黒は隅で方向ミスしやすい」等の分析を可能にする

**変更ファイル**:
- `katrain/core/batch/stats/pattern_miner.py` - normalize_player(), MistakeSignature 拡張
- `katrain/gui/features/summary_formatter.py` - PLAYER_KEYS 追加、表示更新
- `katrain/i18n/locales/*/katrain.po` - i18n キー追加
- `tests/test_pattern_miner.py` - テスト更新

**変更内容**:

1. normalize_player() ヘルパー追加 (pattern_miner.py:~120):
```python
def normalize_player(player: Optional[str]) -> str:
    """Normalize player to canonical format: 'B', 'W', or '?'.

    Accepts lowercase 'b'/'w' defensively. Returns '?' for None/unknown.
    """
    if player is None:
        return "?"
    upper = player.upper()
    if upper == "B":
        return "B"
    if upper == "W":
        return "W"
    return "?"
```

2. MistakeSignature に player フィールド追加 (pattern_miner.py:59-77):
```python
@dataclass(frozen=True)
class MistakeSignature:
    phase: str
    area: str
    primary_tag: str
    severity: str
    player: str  # "B", "W", or "?" (canonical)

    def sort_key(self) -> Tuple[str, str, str, str, str]:
        return (self.phase, self.area, self.primary_tag, self.severity, self.player)
```

3. create_signature() で正規化して返す (pattern_miner.py:~270):
```python
    # Normalize player (skip if unknown)
    norm_player = normalize_player(move_eval.player)
    if norm_player == "?":
        return None  # Skip pass/unknown moves

    return MistakeSignature(
        phase=phase,
        area=area,
        primary_tag=primary_tag,
        severity=severity,
        player=norm_player,
    )
```

4. PLAYER_KEYS 追加と表示更新 (summary_formatter.py):
```python
PLAYER_KEYS = {
    "B": "pattern:player-black",
    "W": "pattern:player-white",
    "?": "pattern:player-unknown",
}

# _append_recurring_patterns() 内:
player_label = i18n._(PLAYER_KEYS.get(sig.player, "pattern:player-unknown"))
lines.append(
    f"{idx}. **{phase_label} / {area_label} / {severity_label} "
    f"({sig.primary_tag}) [{player_label}]**: {count_loss_text}"
)
```

5. i18n キー追加 (katrain.po):
```
# jp/katrain.po
msgid "pattern:player-black"
msgstr "黒"

msgid "pattern:player-white"
msgstr "白"

msgid "pattern:player-unknown"
msgstr "不明"

# en/katrain.po
msgid "pattern:player-black"
msgstr "Black"

msgid "pattern:player-white"
msgstr "White"

msgid "pattern:player-unknown"
msgstr "Unknown"
```

6. i18n コンパイル (.po → .mo):
```powershell
# UTF-8 設定（Windows PowerShell）
$env:PYTHONUTF8 = "1"

# プロジェクト標準のi18nスクリプトを使用（全ロケール + 自動修正）
python i18n.py
```
**注意**: `python i18n.py` は全ロケールの .mo をコンパイルし、欠落翻訳を自動修正します。
詳細は `docs/i18n-workflow.md` 参照。

**推定行数**: ~90行

---

#### Task 2: Reason Generator 組み合わせテンプレート追加 (Lv1)

**目的**: より多くの (phase, area, tag) 組み合わせに対応した理由文を提供

**変更ファイル**:
- `katrain/core/analysis/reason_generator.py` - 7個の組み合わせテンプレート追加
- `tests/test_reason_generator.py` - テスト追加 + ワイルドカード優先順位テスト

**追加テンプレート** (8個 → 15個):

既存8個:
- `("opening", "corner", "direction_error")`
- `("opening", "edge", "direction_error")`
- `("middle", "corner", "life_death_error")`
- `("middle", "edge", "connection_miss")`
- `("middle", "center", "capture_race_loss")`
- `("endgame", "corner", "endgame_slip")`
- `("endgame", "edge", "territorial_loss")`
- `("middle", "*", "overplay")` (wildcard)

新規7個:
1. `("opening", "corner", "overplay")`:
   - JP: "隅での定石選択が無理でした。相手の反撃に備えましょう。"
   - EN: "An overplay in the corner joseki. Be prepared for counterattacks."

2. `("opening", "edge", "slow_move")`:
   - JP: "序盤の辺で緩い手を打ちました。大場を優先しましょう。"
   - EN: "A slow move on the side in the opening. Prioritize big points."

3. `("middle", "corner", "capture_race_loss")`:
   - JP: "隅の攻め合いで手数を読み間違えました。"
   - EN: "Miscounted liberties in a corner capturing race."

4. `("middle", "edge", "life_death_error")`:
   - JP: "辺の石の死活で判断ミスがありました。"
   - EN: "A life and death misjudgment on the side."

5. `("middle", "center", "direction_error")`:
   - JP: "中央の戦いで攻め方向を誤りました。"
   - EN: "Wrong direction of attack in the center fight."

6. `("endgame", "edge", "slow_move")`:
   - JP: "辺のヨセで大きな先手を逃しました。"
   - EN: "Missed a big sente move in side endgame."

7. `("endgame", "center", "territorial_loss")`:
   - JP: "中央の地の出入りで損をしました。"
   - EN: "Lost points in center territory exchange."

**ワイルドカード優先順位テスト** (test_reason_generator.py に追加):

設計セクション5参照。モジュール完全修飾パスで `patch.dict()` を使用。

```python
def test_new_template_matches(self):
    """New templates return expected content."""
    result = generate_reason("overplay", phase="opening", area="corner", lang="jp")
    # New template added in Task 2
    assert result is not None
    assert "定石" in result
```

**推定行数**: ~80行

---

### Phase 87 PR から除外

#### ~~Task 3: テンプレート文言改善~~ → Phase 88+ へ延期

**理由**: スコープを絞り、Phase 87 PR は Task 1 + Task 2 のみに集中する。
文言改善は別 PR/Phase 88+ で対応。

---

## 実装順序

1. **Task 1: Player 軸追加** - 最もインパクトが大きい
2. **Task 2: テンプレート追加** - 既存インフラを活用

---

## ファイル変更一覧

| ファイル | Task | 変更内容 |
|---------|------|---------|
| `katrain/core/batch/stats/pattern_miner.py` | 1 | normalize_player()追加、MistakeSignature.player追加 |
| `katrain/gui/features/summary_formatter.py` | 1 | PLAYER_KEYS追加、player表示追加 |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | 1 | pattern:player-* キー追加 |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.mo` | 1 | コンパイル済みバイナリ（自動生成） |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | 1 | pattern:player-* キー追加 |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.mo` | 1 | コンパイル済みバイナリ（自動生成） |
| `katrain/core/analysis/reason_generator.py` | 2 | テンプレート7個追加 |
| `tests/test_pattern_miner.py` | 1 | テスト更新（player引数追加） |
| `tests/test_reason_generator.py` | 2 | テスト追加 + 優先順位テスト |
| `tests/fixtures/golden/summary_output.txt` | 1,2 | golden期待値更新 |

---

## テスト戦略

```powershell
# 1. 変更前に既存テスト確認（ベースライン）
uv run pytest tests/test_pattern_miner.py tests/test_reason_generator.py -v

# 2. Task 1 完了後: pattern_miner テスト更新
uv run pytest tests/test_pattern_miner.py -v

# 3. Task 2 完了後: reason_generator テスト追加
uv run pytest tests/test_reason_generator.py -v

# 4. Golden テスト更新（Task 1完了後に必須）
# 期待される変更: Recurring Patterns に [黒]/[白] が追加
uv run pytest tests/test_golden_summary.py --update-golden

# 5. 全テスト通過確認
uv run pytest tests
```

**Golden テスト更新のタイミング**:

1. **Task 1 完了後**:
   - `uv run pytest tests/test_golden_summary.py` で差分確認
   - 期待される差分: パターン行に `[黒]` / `[白]` 追加
   - 確認後: `uv run pytest tests/test_golden_summary.py --update-golden`

2. **Task 2 完了後**:
   - `uv run pytest tests/test_golden_summary.py` で差分確認
   - goldenデータに `("opening", "corner", "overplay")` があるため**reason行が追加される可能性あり**
   - 差分があれば確認後: `--update-golden` で更新

---

## 動作確認

1. 複数SGFファイルでバッチ解析を実行
2. サマリの Recurring Patterns セクションに player が表示されることを確認
3. 新規テンプレートの理由文が表示されることを確認

---

## リスクと対策

| リスク | 対策 |
|--------|------|
| MistakeSignature の破壊的変更 | 全7箇所を更新、テスト徹底（上記一覧参照） |
| player 値の不整合 | normalize_player() で正規化、"?" はスキップ |
| ハッシュ/Dict キー変更 | 同じパターンでも黒/白が別集計は意図した動作 |
| テンプレートカバレッジ不足 | 単一タグへのフォールバック維持 |
| ワイルドカード優先順位の混乱 | 既存仕様を文書化 + patch.dictテストでロック |
| Golden テスト失敗 | 各Task完了後に差分確認→`--update-golden` |
| i18n キー漏れ | jp/en 両方にキー追加を確認 |
| .mo未生成でUIに生キー表示 | .po編集後に必ずコンパイル、.moもコミット |

---

## Phase 87 で対象外とするもの

以下は Phase 88+ に延期:

- **Task 3 (テンプレート文言改善)** - スコープ維持のため別PRへ
- **BoardContext dataclass** - 設計が大きい
- **SituationClassifier** (fight/invasion/joseki判定) - 要分析
- **StoneStatusClassifier** - 要分析
- **閾値変更** (LOSS_THRESHOLD等) - データ検証なしでは変更しない

---

## 推定工数

| Task | 行数 | リスク |
|------|------|--------|
| Task 1 (Player軸 + i18n) | ~90 | 中 |
| Task 2 (テンプレート+7 + 優先順位テスト) | ~80 | 低 |
| **合計** | **~170** | **中** |

---

## 実装チェックリスト

### Task 1: Player 軸追加
- [ ] `normalize_player()` ヘルパー関数追加
- [ ] `MistakeSignature.player` フィールド追加
- [ ] `sort_key()` に player 追加
- [ ] `create_signature()` で正規化＆スキップロジック追加
- [ ] `PLAYER_KEYS` 定義追加 (summary_formatter.py)
- [ ] `_append_recurring_patterns()` で player 表示
- [ ] i18n キー追加 (jp/en の .po ファイル)
- [ ] i18n コンパイル (.po → .mo)
- [ ] `test_pattern_miner.py` の既存テスト更新
- [ ] `normalize_player()` のテスト追加
- [ ] player="?" のスキップテスト追加

### Task 2: テンプレート追加
- [ ] 7個の組み合わせテンプレート追加
- [ ] ワイルドカード優先順位テスト追加
- [ ] 新テンプレートのテスト追加

### 確認（各Task完了後）
- [ ] `uv run pytest tests/test_pattern_miner.py -v` 通過
- [ ] `uv run pytest tests/test_reason_generator.py -v` 通過
- [ ] `uv run pytest tests/test_golden_summary.py` で差分確認
- [ ] 差分レビュー後: `uv run pytest tests/test_golden_summary.py --update-golden`
- [ ] `uv run pytest tests` 全テスト通過
- [ ] 動作確認（バッチ解析でRecurring Patterns確認）

---

## Git ワークフロー

```
feature/2026-01-30-phase87-signature-player → PR → main
```
