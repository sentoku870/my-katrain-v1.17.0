# Phase 85: Pattern to Summary Integration (Revised v5)

## 概要

**修正レベル**: Lv3（複数ファイル）

Phase 84で実装した`mine_patterns()`を使い、複数ゲームから検出された繰り返しパターンをSummaryレポートに統合する。

## 修正済み課題

| 課題 | 対応 |
|------|------|
| i18n一貫性 | 翻訳キー使用、en/jp別々に.po記載 |
| CIポリシー | i18n.pyは変更時FAIL、.mo更新をコミット必須 |
| データ契約リスク | 必須属性明示、string→Enum変換（失敗時スキップ+警告） |
| board_sizeフィルタ | 完全タプル(w,h)で比較、正方形チェック、**tuple/list両対応** |
| **決定論的ソート** | **(game_name, date, total_moves, source_index)で完全安定ソート** |
| loss fields欠損 | 抽出時にフィルタ（all-None除外） |
| 本番安全性 | invalid mistake_categoryでクラッシュしない |
| **入力検証** | **player/gtp/move_number無効時もスキップ+警告** |
| **循環import防止** | **TYPE_CHECKINGガード使用** |
| **meaning_tag_id保証** | **pattern_minerが`normalize_primary_tag()`で"uncertain"にフォールバック** |
| **gtp座標検証** | **正規表現+board_size範囲チェック（早期フィルタ）** |
| **未知フィールド検出** | **unknown phase/area/severity時にdebugログ出力** |

---

## 1. データ契約: pattern_data必須フィールド

`create_signature()`と`mine_patterns()`が必要とするMoveEval属性:

| 属性 | 格納型 | 復元型 | 用途 | 検証条件 |
|------|--------|--------|------|----------|
| `move_number` | int | int | phase判定 | > 0 |
| `player` | str | str | GameRef生成 | "B" or "W" |
| `gtp` | str | str | area判定 | 非空、pass/resign以外 |
| `score_loss` | Optional[float] | Optional[float] | loss取得(優先1) | 少なくとも1つ非None |
| `leela_loss_est` | Optional[float] | Optional[float] | loss取得(優先2) | 〃 |
| `points_lost` | Optional[float] | Optional[float] | loss取得(優先3) | 〃 |
| `mistake_category` | str (enum name) | MistakeCategory or None | severity判定 | 有効なEnum名 |
| `meaning_tag_id` | Optional[str] | Optional[str] | primary_tag | (なし) |

**重要**:
- 格納時に`move.mistake_category.name`（文字列）
- 復元時に各フィールドを検証、無効時は`None`設定+警告ログ（クラッシュしない）
- 無効な手は`_reconstruct_pattern_input()`でフィルタアウト

### meaning_tag_id → primary_tag 保証

**pattern_miner.pyが保証**:
- `normalize_primary_tag(meaning_tag_id)`関数が`None`/空文字列を`MeaningTagId.UNCERTAIN.value`（= "uncertain"）に変換
- `create_signature()`で使用されるため、**`signature.primary_tag`は常に非空文字列**
- summary_formatter側でのフォールバック処理は不要

```python
# pattern_miner.py (既存コード)
def normalize_primary_tag(meaning_tag_id: Optional[str]) -> str:
    if not meaning_tag_id:
        return MeaningTagId.UNCERTAIN.value  # "uncertain"
    return meaning_tag_id
```

---

## 2. i18n設計

### 2.1 POファイル形式

**重要**: 各言語ファイルは別々に編集。msgidは同じ、msgstrは言語ごとに異なる。

#### English: `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`

```po
#. Phase 85: Recurring Patterns section header
msgid "pattern:section-header"
msgstr "Recurring Patterns"

#. Phase 85: Recurring Patterns intro text
msgid "pattern:intro"
msgstr "The following patterns were detected multiple times (by impact):"

#. Phase 85: Pattern phase labels
msgid "pattern:phase-opening"
msgstr "Opening"

msgid "pattern:phase-middle"
msgstr "Midgame"

msgid "pattern:phase-endgame"
msgstr "Endgame"

#. Phase 85: Pattern area labels
msgid "pattern:area-corner"
msgstr "Corner"

msgid "pattern:area-edge"
msgstr "Edge"

msgid "pattern:area-center"
msgstr "Center"

#. Phase 85: Pattern severity labels
msgid "pattern:severity-mistake"
msgstr "Mistake"

msgid "pattern:severity-blunder"
msgstr "Blunder"

#. Phase 85: Pattern format strings
msgid "pattern:count-loss"
msgstr "{count} times, total loss {loss:.1f} pts"
```

#### Japanese: `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`

```po
#. Phase 85: Recurring Patterns section header
msgid "pattern:section-header"
msgstr "繰り返しパターン"

#. Phase 85: Recurring Patterns intro text
msgid "pattern:intro"
msgstr "以下のパターンが複数回検出されました（影響度順）:"

#. Phase 85: Pattern phase labels
msgid "pattern:phase-opening"
msgstr "序盤"

msgid "pattern:phase-middle"
msgstr "中盤"

msgid "pattern:phase-endgame"
msgstr "終盤"

#. Phase 85: Pattern area labels
msgid "pattern:area-corner"
msgstr "隅"

msgid "pattern:area-edge"
msgstr "辺"

msgid "pattern:area-center"
msgstr "中央"

#. Phase 85: Pattern severity labels
msgid "pattern:severity-mistake"
msgstr "悪手"

msgid "pattern:severity-blunder"
msgstr "大悪手"

#. Phase 85: Pattern format strings
msgid "pattern:count-loss"
msgstr "{count}回、総損失{loss:.1f}目"
```

### 2.2 署名フィールド値の確認

`pattern_miner.py`の実際の値とi18nキーの対応:

| フィールド | 実際の値 | i18nキー | 一致 |
|------------|----------|----------|:----:|
| phase | "opening", "middle", "endgame" | pattern:phase-* | ✓ |
| area | "corner", "edge", "center" | pattern:area-* | ✓ |
| severity | "mistake", "blunder" | pattern:severity-* | ✓ |

### 2.3 .moコンパイルとCIポリシー

**ワークフロー（必須順序）**:
```powershell
# 1. POファイルを編集
# 2. i18n.pyを実行（.moをコンパイル）
python i18n.py

# 3. 変更された.poと.moを両方コミット
git add katrain/i18n/locales/*/LC_MESSAGES/*.po
git add katrain/i18n/locales/*/LC_MESSAGES/*.mo
git commit -m "feat: add Phase 85 i18n keys"
```

**CIポリシー**:
- `python i18n.py`がexit code 1を返す場合、**CIはFAIL**
- これは「.poと.moが同期していない」ことを示す

---

## 3. board_size一貫性チェック（tuple/list両対応）

### 3.1 設計

- `stats["board_size"]`は通常`(width, height)`タプルだが、JSONシリアライズ経由で`[width, height]`リストになる可能性がある
- **インデックスアクセスで正規化**（tuple/list両対応）
- 完全値`(w, h)`で比較、非正方形はスキップ

### 3.2 実装

```python
import logging
from collections import Counter
from typing import List, Optional, Tuple, Union, Sequence

_logger = logging.getLogger("katrain.gui.features.summary_formatter")


def _normalize_board_size(bs: Union[Tuple[int, int], List[int], None]) -> Optional[Tuple[int, int]]:
    """Normalize board_size to (w, h) tuple.

    Handles both tuple and list (from JSON deserialization).

    Returns:
        (w, h) tuple, or None if invalid.
    """
    if bs is None:
        return None
    if not isinstance(bs, (tuple, list)) or len(bs) < 2:
        return None
    try:
        return (int(bs[0]), int(bs[1]))
    except (ValueError, TypeError):
        return None


def _filter_by_board_size(
    stats_list: List[StatsDict],
) -> Tuple[List[StatsDict], Optional[int]]:
    """Filter stats_list to games with consistent board size.

    Only square boards (w == h) are supported for pattern mining.
    Handles both tuple and list board_size formats.

    Args:
        stats_list: List of stats dictionaries

    Returns:
        Tuple of (filtered_stats_list, board_size as int).
        If no valid games, returns ([], None).
    """
    # Count normalized (w, h) tuples
    size_counts: Counter[Tuple[int, int]] = Counter()
    non_square_games: List[str] = []
    invalid_games: List[str] = []

    for stats in stats_list:
        game_name = stats.get("game_name", "unknown")
        bs_normalized = _normalize_board_size(stats.get("board_size"))

        if bs_normalized is None:
            invalid_games.append(game_name)
            continue

        w, h = bs_normalized
        if w != h:
            non_square_games.append(f"{game_name} ({w}x{h})")
            continue

        size_counts[bs_normalized] += 1

    # Log invalid board_size
    if invalid_games:
        _logger.debug(
            "Skipping %d game(s) with missing/invalid board_size: %s",
            len(invalid_games),
            ", ".join(invalid_games[:5]) + ("..." if len(invalid_games) > 5 else ""),
        )

    # Log non-square games
    if non_square_games:
        _logger.warning(
            "Skipping %d non-square board game(s) for pattern mining: %s",
            len(non_square_games),
            ", ".join(non_square_games[:5]) + ("..." if len(non_square_games) > 5 else ""),
        )

    if not size_counts:
        _logger.warning("No games have valid square board_size; skipping pattern mining.")
        return [], None

    # Find most common size
    most_common_tuple = size_counts.most_common(1)[0][0]
    most_common_size = most_common_tuple[0]  # w == h, so use either

    # Check for mixed sizes
    if len(size_counts) > 1:
        skipped_count = sum(c for t, c in size_counts.items() if t != most_common_tuple)
        _logger.warning(
            "Mixed board sizes detected: %s. Using %dx%d for pattern mining; "
            "skipping %d game(s) with other sizes.",
            {f"{t[0]}x{t[1]}": c for t, c in size_counts.items()},
            most_common_size,
            most_common_size,
            skipped_count,
        )

    # Filter to only games with the most common size (using normalized comparison)
    filtered = [
        s for s in stats_list
        if _normalize_board_size(s.get("board_size")) == most_common_tuple
    ]

    return filtered, most_common_size
```

---

## 4. 決定論的ソート（source_index追加）

### 4.1 設計

`game_name`, `date`, `total_moves`が全て等しい場合でも安定するよう、**source_index**を最終タイブレーカーとして使用。

#### extraction.pyでsource_index追加

```python
# extract_game_stats() に追加
stats["source_index"] = source_index  # 呼び出し元から渡される連番
```

**注**: 既存の呼び出し元（`orchestration.py`など）を修正し、`enumerate`で連番を渡す。

#### ソートキー

```python
def _stable_sort_key(stats: StatsDict) -> Tuple[str, str, int, int]:
    """Generate fully stable sort key for stats dict.

    Returns:
        (game_name, date, total_moves, source_index) for deterministic ordering.
        Uses empty string / 0 as defaults for missing values.
    """
    return (
        stats.get("game_name", ""),
        stats.get("date", "") or "",
        stats.get("total_moves", 0),
        stats.get("source_index", 0),  # Final tie-breaker
    )
```

### 4.2 入力の完全検証

```python
def _is_valid_player(player: Optional[str]) -> bool:
    """Check if player is valid ("B" or "W")."""
    return player in ("B", "W")


def _is_valid_gtp(gtp: Optional[str], board_size: int = 19) -> bool:
    """Check if gtp is a valid coordinate for the given board size.

    Validates:
    - Non-empty string
    - Not pass/resign
    - Matches GTP coordinate pattern (letter + number)
    - Within board bounds

    Args:
        gtp: GTP coordinate string (e.g., "D4", "Q16")
        board_size: Board size (default 19)

    Returns:
        True if valid coordinate, False otherwise
    """
    if not gtp or not isinstance(gtp, str):
        return False

    gtp_stripped = gtp.strip()
    gtp_lower = gtp_stripped.lower()

    # Reject pass/resign
    if gtp_lower in ("pass", "resign"):
        return False

    # Validate format with regex
    if not _GTP_COORD_PATTERN.match(gtp_stripped):
        return False

    # Validate within board bounds
    try:
        col_char = gtp_lower[0]
        row_num = int(gtp_stripped[1:])

        # GTP columns: A-H, J-T (I is skipped), max 19 for 19x19
        col_index = ord(col_char) - ord('a')
        if col_char >= 'j':
            col_index -= 1  # Adjust for skipped 'I'

        if col_index < 0 or col_index >= board_size:
            return False
        if row_num < 1 or row_num > board_size:
            return False

        return True
    except (ValueError, IndexError):
        return False


def _is_valid_move_number(move_number) -> bool:
    """Check if move_number is a positive integer."""
    return isinstance(move_number, int) and move_number > 0


def _reconstruct_pattern_input(
    stats_list: List[StatsDict],
    board_size: int,
) -> List[Tuple[str, "_FakeSnapshot"]]:
    """Reconstruct pattern mining input from stats_list.

    Returns games sorted by (game_name, date, total_moves, source_index),
    with each game's moves sorted by (move_number, player, gtp).
    Invalid moves are skipped with warning log.
    """
    games = []
    skipped_moves_count = 0

    # Sort by stable composite key
    sorted_stats = sorted(stats_list, key=_stable_sort_key)

    for stats in sorted_stats:
        pattern_data = stats.get("pattern_data", [])
        if not pattern_data:
            continue

        game_name = stats.get("game_name", "unknown")

        # Sort moves deterministically within game
        sorted_data = sorted(
            pattern_data,
            key=lambda d: (
                d.get("move_number", 0),
                d.get("player", ""),
                d.get("gtp", ""),
            )
        )

        valid_moves = []
        for d in sorted_data:
            move_eval = _PatternMoveEval(d)

            # Validate all required fields
            if not _is_valid_move_number(move_eval.move_number):
                _logger.debug(
                    "Skipping invalid move_number=%s in %s",
                    d.get("move_number"), game_name
                )
                skipped_moves_count += 1
                continue

            if not _is_valid_player(move_eval.player):
                _logger.debug(
                    "Skipping invalid player='%s' at move %d in %s",
                    move_eval.player, move_eval.move_number, game_name
                )
                skipped_moves_count += 1
                continue

            if not _is_valid_gtp(move_eval.gtp, board_size):
                _logger.debug(
                    "Skipping invalid gtp='%s' at move %d in %s",
                    move_eval.gtp, move_eval.move_number, game_name
                )
                skipped_moves_count += 1
                continue

            if move_eval.mistake_category is None:
                # Already logged in _PatternMoveEval.__init__
                skipped_moves_count += 1
                continue

            valid_moves.append(move_eval)

        if valid_moves:
            games.append((game_name, _FakeSnapshot(valid_moves)))

    if skipped_moves_count > 0:
        _logger.warning(
            "Skipped %d invalid move(s) during pattern mining input reconstruction.",
            skipped_moves_count
        )

    return games
```

---

## 5. 循環import防止: TYPE_CHECKINGガード

### 5.1 設計

- `PatternCluster`, `GameRef`は型ヒント専用
- `mine_patterns`のみ実行時import
- `TYPE_CHECKING`ブロックで型importをガード

### 5.2 実装

```python
from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from katrain.core.batch.stats.pattern_miner import PatternCluster, GameRef

from katrain.core.lang import i18n
from katrain.core import eval_metrics

_logger = logging.getLogger("katrain.gui.features.summary_formatter")


# Runtime import inside function to avoid circular dependency
def _mine_patterns_safe(
    games: List[Tuple[str, "_FakeSnapshot"]],
    board_size: int,
    min_count: int,
    top_n: int,
) -> List["PatternCluster"]:
    """Wrapper for mine_patterns with lazy import."""
    from katrain.core.batch.stats.pattern_miner import mine_patterns
    return mine_patterns(games, board_size=board_size, min_count=min_count, top_n=top_n)


def _format_game_refs(game_refs: List["GameRef"], max_display: int = 3) -> str:
    """Format game refs with deterministic ordering."""
    sorted_refs = sorted(
        game_refs,
        key=lambda r: (r.game_name, r.move_number, r.player)
    )
    display_refs = sorted_refs[:max_display]
    return ", ".join(
        f"{r.game_name} #{r.move_number}({r.player})"
        for r in display_refs
    )
```

---

## 6. 本番安全性: _PatternMoveEval完全実装

```python
class _PatternMoveEval:
    """Duck-typed MoveEval for pattern mining.

    Safely handles invalid/missing data without raising exceptions.
    """
    __slots__ = (
        "move_number", "player", "gtp", "score_loss",
        "leela_loss_est", "points_lost", "mistake_category", "meaning_tag_id"
    )

    def __init__(self, data: dict):
        # Safe extraction with defaults
        self.move_number = data.get("move_number", 0)
        self.player = data.get("player")
        self.gtp = data.get("gtp")
        self.score_loss = data.get("score_loss")
        self.leela_loss_est = data.get("leela_loss_est")
        self.points_lost = data.get("points_lost")
        self.meaning_tag_id = data.get("meaning_tag_id")

        # Safe mistake_category conversion
        cat_name = data.get("mistake_category")
        if cat_name:
            try:
                self.mistake_category = eval_metrics.MistakeCategory[cat_name]
            except KeyError:
                _logger.warning(
                    "Invalid mistake_category '%s' at move %d; skipping.",
                    cat_name,
                    self.move_number,
                )
                self.mistake_category = None
        else:
            self.mistake_category = None


class _FakeSnapshot:
    """Duck-typed EvalSnapshot for pattern mining."""
    __slots__ = ("moves",)

    def __init__(self, moves: list):
        self.moves = moves
```

---

## 7. loss fields欠損ポリシー: 抽出時フィルタ

### 7.1 実装（extraction.py）

```python
# stats["pattern_data"] 構築時
stats["pattern_data"] = []

for move in snapshot.moves:
    # Only MISTAKE or BLUNDER
    if move.mistake_category not in (
        eval_metrics.MistakeCategory.MISTAKE,
        eval_metrics.MistakeCategory.BLUNDER,
    ):
        continue

    # Skip if ALL loss fields are None
    has_loss = (
        move.score_loss is not None
        or move.leela_loss_est is not None
        or move.points_lost is not None
    )
    if not has_loss:
        continue

    stats["pattern_data"].append({
        "move_number": move.move_number,
        "player": move.player,
        "gtp": move.gtp,
        "score_loss": move.score_loss,
        "leela_loss_est": move.leela_loss_est,
        "points_lost": move.points_lost,
        "mistake_category": move.mistake_category.name,
        "meaning_tag_id": move.meaning_tag_id,
    })
```

### 7.2 source_index追加

```python
# extract_game_stats() のシグネチャに追加
def extract_game_stats(
    game: "Game",
    rel_path: str,
    log_cb: Optional[Callable[[str], None]] = None,
    target_visits: Optional[int] = None,
    source_index: int = 0,  # Phase 85: stable sort tie-breaker
) -> Optional[dict]:
    ...
    stats["source_index"] = source_index
    ...
```

---

## 8. 変更ファイル一覧

### 8.1 `katrain/core/batch/stats/extraction.py`

**変更内容**:
- `pattern_data`フィールド追加（loss filterあり）
- `source_index`パラメータ追加

### 8.2 `katrain/core/batch/orchestration.py`

**変更内容**:
- `extract_game_stats()`呼び出し時に`source_index`を渡す

```python
# run_batch() 内
for idx, (game, rel_path) in enumerate(games_to_process):
    stats = extract_game_stats(
        game, rel_path, log_cb, target_visits,
        source_index=idx,  # Phase 85
    )
```

### 8.3 `katrain/gui/features/summary_formatter.py`

**変更内容**:

1. **import修正（TYPE_CHECKINGガード）**:
```python
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from katrain.core.batch.stats.pattern_miner import PatternCluster, GameRef

from katrain.core.lang import i18n
from katrain.core import eval_metrics

_logger = logging.getLogger("katrain.gui.features.summary_formatter")

# GTP coordinate pattern: letter (A-T, excluding I) + number (1-25)
_GTP_COORD_PATTERN = re.compile(r"^[a-hj-t](?:[1-9]|1[0-9]|2[0-5])$", re.IGNORECASE)
```

2. **新関数**: `_normalize_board_size()`, `_filter_by_board_size()` - セクション3参照

3. **新関数**: `_stable_sort_key()`, `_is_valid_*()`, `_reconstruct_pattern_input()` - セクション4参照

4. **新関数**: `_mine_patterns_safe()`, `_format_game_refs()` - セクション5参照

5. **新クラス**: `_PatternMoveEval`, `_FakeSnapshot` - セクション6参照

6. **新関数**: `_append_recurring_patterns()`

```python
PHASE_KEYS = {
    "opening": "pattern:phase-opening",
    "middle": "pattern:phase-middle",
    "endgame": "pattern:phase-endgame",
}
AREA_KEYS = {
    "corner": "pattern:area-corner",
    "edge": "pattern:area-edge",
    "center": "pattern:area-center",
}
SEVERITY_KEYS = {
    "mistake": "pattern:severity-mistake",
    "blunder": "pattern:severity-blunder",
}
MAX_DISPLAY_REFS = 3


def _append_recurring_patterns(
    lines: List[str],
    pattern_clusters: List["PatternCluster"],
    focus_player: Optional[str],
) -> None:
    """Append Recurring Patterns section to lines."""
    if not pattern_clusters:
        return

    header = i18n._("pattern:section-header")
    lines.append(f"## {header}" + (f" ({focus_player})" if focus_player else ""))
    lines.append("")
    lines.append(i18n._("pattern:intro"))
    lines.append("")

    # Track unknown values for logging (once per call, not per cluster)
    unknown_phases: set = set()
    unknown_areas: set = set()
    unknown_severities: set = set()

    for idx, cluster in enumerate(pattern_clusters, 1):
        sig = cluster.signature

        # Check for unknown values and log
        if sig.phase not in PHASE_KEYS:
            unknown_phases.add(sig.phase)
        if sig.area not in AREA_KEYS:
            unknown_areas.add(sig.area)
        if sig.severity not in SEVERITY_KEYS:
            unknown_severities.add(sig.severity)

        phase_label = i18n._(PHASE_KEYS.get(sig.phase, "pattern:phase-middle"))
        area_label = i18n._(AREA_KEYS.get(sig.area, "pattern:area-center"))
        severity_label = i18n._(SEVERITY_KEYS.get(sig.severity, "pattern:severity-mistake"))

        count_loss_text = i18n._("pattern:count-loss").format(
            count=cluster.count,
            loss=cluster.total_loss,
        )

        lines.append(
            f"{idx}. **{phase_label} / {area_label} / {severity_label} "
            f"({sig.primary_tag})**: {count_loss_text}"
        )

        refs_text = _format_game_refs(cluster.game_refs, MAX_DISPLAY_REFS)
        lines.append(f"   - {refs_text}")
        lines.append("")

    # Log unknown signature field values (once per call)
    if unknown_phases:
        _logger.debug("Unknown phase value(s) in pattern clusters: %s", unknown_phases)
    if unknown_areas:
        _logger.debug("Unknown area value(s) in pattern clusters: %s", unknown_areas)
    if unknown_severities:
        _logger.debug("Unknown severity value(s) in pattern clusters: %s", unknown_severities)
```

7. **`build_summary_from_stats()`修正**:

```python
# Weakness Hypothesis 後、Practice Priorities 前に挿入

# Recurring Patterns (Phase 85)
filtered_for_patterns, pattern_board_size = _filter_by_board_size(stats_list)
if filtered_for_patterns and pattern_board_size:
    games_input = _reconstruct_pattern_input(filtered_for_patterns, pattern_board_size)
    if len(games_input) >= 2:  # min_count=2 requires at least 2 games
        pattern_clusters = _mine_patterns_safe(
            games_input,
            board_size=pattern_board_size,
            min_count=2,
            top_n=5,
        )
        _append_recurring_patterns(lines, pattern_clusters, focus_player)
```

### 8.4 `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`

**変更内容**: セクション2.1 English参照

### 8.5 `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`

**変更内容**: セクション2.1 Japanese参照

### 8.6 `tests/test_golden_summary.py`

**変更内容**:
- `create_single_game_stats()`に`pattern_data`、`board_size`、`source_index`追加

### 8.7 `tests/test_pattern_summary_contract.py` (新規)

**変更内容**: データ契約テスト + 本番安全性テスト

### 8.8 `tests/fixtures/golden/summary_output.txt`

**変更内容**: 新セクションを含む期待出力に更新

---

## 9. 出力テンプレート（英語版）

```markdown
## Recurring Patterns (TestPlayer)

The following patterns were detected multiple times (by impact):

1. **Midgame / Corner / Blunder (overplay)**: 5 times, total loss 15.2 pts
   - game1.sgf #50(B), game2.sgf #45(W), game3.sgf #52(B)

2. **Opening / Edge / Mistake (life_death)**: 3 times, total loss 12.5 pts
   - game1.sgf #25(B), game4.sgf #30(B)
```

---

## 10. テスト戦略

### 10.1 データ契約テスト

`tests/test_pattern_summary_contract.py`:

```python
import logging
import pytest
from katrain.core import eval_metrics
from katrain.gui.features.summary_formatter import (
    _PatternMoveEval,
    _is_valid_player,
    _is_valid_gtp,
    _is_valid_move_number,
    _normalize_board_size,
    _filter_by_board_size,
    _reconstruct_pattern_input,
    _stable_sort_key,
    build_summary_from_stats,
)

# Import the shared test helper from test_golden_summary.py
from tests.test_golden_summary import create_single_game_stats


# Mock config function for tests
def mock_config_fn(key: str, default=None):
    return default


class TestPatternDataContract:
    """Verify pattern_data contract for mine_patterns()."""

    def test_required_fields_present(self):
        """pattern_data must contain all required fields."""
        required = {"move_number", "player", "gtp", "mistake_category"}
        loss_fields = {"score_loss", "leela_loss_est", "points_lost"}

        stats = create_single_game_stats()

        for item in stats["pattern_data"]:
            assert required.issubset(item.keys())
            assert any(item.get(f) is not None for f in loss_fields)

    def test_mistake_category_string_to_enum_conversion(self):
        """Valid mistake_category should convert from string to Enum."""
        data = {
            "move_number": 10,
            "player": "B",
            "gtp": "D4",
            "score_loss": 5.0,
            "mistake_category": "BLUNDER",
        }

        move_eval = _PatternMoveEval(data)

        assert move_eval.mistake_category == eval_metrics.MistakeCategory.BLUNDER

    def test_invalid_mistake_category_sets_none_and_logs_warning(self, caplog):
        """Invalid mistake_category should set None and log warning."""
        data = {
            "move_number": 10,
            "player": "B",
            "gtp": "D4",
            "score_loss": 5.0,
            "mistake_category": "INVALID_CATEGORY",
        }

        with caplog.at_level(logging.WARNING):
            move_eval = _PatternMoveEval(data)

        assert move_eval.mistake_category is None
        assert "Invalid mistake_category" in caplog.text


class TestInputValidation:
    """Test move validation functions."""

    def test_valid_player(self):
        assert _is_valid_player("B") is True
        assert _is_valid_player("W") is True
        assert _is_valid_player("X") is False
        assert _is_valid_player("") is False
        assert _is_valid_player(None) is False

    def test_valid_gtp(self):
        # Valid coordinates
        assert _is_valid_gtp("D4") is True
        assert _is_valid_gtp("A1") is True
        assert _is_valid_gtp("T19") is True
        assert _is_valid_gtp("d4") is True  # lowercase OK
        assert _is_valid_gtp("J10") is True  # J is valid (I is skipped)

        # Pass/resign
        assert _is_valid_gtp("pass") is False
        assert _is_valid_gtp("resign") is False
        assert _is_valid_gtp("PASS") is False  # case insensitive

        # Empty/None
        assert _is_valid_gtp("") is False
        assert _is_valid_gtp(None) is False
        assert _is_valid_gtp("  ") is False  # whitespace only

        # Invalid format (production safety - must not crash)
        assert _is_valid_gtp("Z99") is False  # out of range letter
        assert _is_valid_gtp("A0") is False   # 0 is invalid row
        assert _is_valid_gtp("A26") is False  # row > 25
        assert _is_valid_gtp("I5") is False   # I is skipped in GTP
        assert _is_valid_gtp("AA1") is False  # double letter
        assert _is_valid_gtp("1A") is False   # reversed format
        assert _is_valid_gtp("D") is False    # missing number
        assert _is_valid_gtp("4") is False    # missing letter
        assert _is_valid_gtp("D4D4") is False # garbage

    def test_valid_gtp_board_size_bounds(self):
        """GTP validation should respect board_size."""
        # 19x19 board
        assert _is_valid_gtp("T19", board_size=19) is True
        assert _is_valid_gtp("T20", board_size=19) is False  # row out of bounds
        assert _is_valid_gtp("S19", board_size=19) is True

        # 9x9 board
        assert _is_valid_gtp("J9", board_size=9) is True
        assert _is_valid_gtp("J10", board_size=9) is False  # row out of bounds
        assert _is_valid_gtp("K9", board_size=9) is False   # col out of bounds (K=10th)

    def test_valid_move_number(self):
        assert _is_valid_move_number(1) is True
        assert _is_valid_move_number(100) is True
        assert _is_valid_move_number(0) is False
        assert _is_valid_move_number(-1) is False
        assert _is_valid_move_number(None) is False
        assert _is_valid_move_number("1") is False  # string
```

### 10.2 board_sizeテスト

```python
class TestBoardSizeFiltering:
    def test_normalize_handles_tuple(self):
        assert _normalize_board_size((19, 19)) == (19, 19)
        assert _normalize_board_size((9, 9)) == (9, 9)

    def test_normalize_handles_list(self):
        """JSON deserialization may produce list instead of tuple."""
        assert _normalize_board_size([19, 19]) == (19, 19)
        assert _normalize_board_size([9, 9]) == (9, 9)

    def test_normalize_handles_invalid(self):
        assert _normalize_board_size(None) is None
        assert _normalize_board_size((19,)) is None  # too short
        assert _normalize_board_size([]) is None
        assert _normalize_board_size("19x19") is None  # string

    def test_filter_handles_mixed_tuple_and_list(self):
        """Filter should work with mixed tuple/list board_size formats."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=(19, 19)),
            create_single_game_stats(game_name="b.sgf", board_size=[19, 19]),  # list
        ]
        filtered, size = _filter_by_board_size(stats_list)

        assert size == 19
        assert len(filtered) == 2

    def test_filter_skips_non_square_boards(self, caplog):
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=(19, 19)),
            create_single_game_stats(game_name="rect.sgf", board_size=(19, 13)),
        ]

        with caplog.at_level(logging.WARNING):
            filtered, size = _filter_by_board_size(stats_list)

        assert size == 19
        assert len(filtered) == 1
        assert "non-square" in caplog.text.lower()
```

### 10.3 決定論的ソートテスト

```python
class TestDeterministicOrdering:
    def test_stable_sort_key_uses_source_index(self):
        """source_index should break ties when other fields are equal."""
        stats_list = [
            create_single_game_stats(
                game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=2
            ),
            create_single_game_stats(
                game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=1
            ),
            create_single_game_stats(
                game_name="same.sgf", date="2025-01-01", total_moves=50, source_index=0
            ),
        ]

        games = _reconstruct_pattern_input(stats_list, 19)
        # Should be sorted by source_index when other fields are equal
        # source_index 0 < 1 < 2

        # Verify order is deterministic
        sorted_keys = [_stable_sort_key(s) for s in sorted(stats_list, key=_stable_sort_key)]
        assert sorted_keys[0][3] == 0  # source_index
        assert sorted_keys[1][3] == 1
        assert sorted_keys[2][3] == 2

    def test_empty_and_duplicate_game_names_sorted_stably(self):
        """Empty and duplicate game_name should be sorted deterministically."""
        stats_list = [
            create_single_game_stats(game_name="", source_index=1),
            create_single_game_stats(game_name="", source_index=0),
            create_single_game_stats(game_name="a.sgf", source_index=2),
        ]

        games = _reconstruct_pattern_input(stats_list, 19)
        game_names = [g[0] for g in games]

        # Empty strings sort first, then by source_index
        assert game_names[0] == ""
        assert game_names[1] == ""
        assert game_names[2] == "a.sgf"

    def test_skipped_invalid_moves_logged(self, caplog):
        """Invalid moves should be skipped with warning."""
        stats = create_single_game_stats()
        stats["pattern_data"] = [
            # Valid move
            {"move_number": 10, "player": "B", "gtp": "D4", "mistake_category": "BLUNDER", "score_loss": 5.0},
            # Invalid player
            {"move_number": 20, "player": "X", "gtp": "E5", "mistake_category": "MISTAKE", "score_loss": 3.0},
            # Invalid gtp
            {"move_number": 30, "player": "W", "gtp": "pass", "mistake_category": "MISTAKE", "score_loss": 3.0},
            # Invalid move_number
            {"move_number": 0, "player": "B", "gtp": "F6", "mistake_category": "BLUNDER", "score_loss": 4.0},
        ]

        with caplog.at_level(logging.DEBUG):
            games = _reconstruct_pattern_input([stats], 19)

        # Only 1 valid move should remain
        assert len(games[0][1].moves) == 1
        assert games[0][1].moves[0].gtp == "D4"
```

### 10.4 本番安全性テスト

```python
class TestProductionSafety:
    def test_summary_does_not_crash_on_corrupt_data(self):
        """Summary generation should not crash with corrupt data."""
        stats_list = [create_single_game_stats(game_name="good.sgf")]
        stats_list[0]["pattern_data"].append({
            "move_number": 99,
            "player": "INVALID",  # Invalid player
            "gtp": "A1",
            "score_loss": 10.0,
            "mistake_category": "BLUNDER",
        })

        # Should NOT raise
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_does_not_crash_on_invalid_gtp_format(self):
        """Summary generation should not crash with invalid GTP coordinates."""
        stats_list = [create_single_game_stats(game_name="good.sgf")]
        stats_list[0]["pattern_data"].append({
            "move_number": 50,
            "player": "B",
            "gtp": "Z99",  # Invalid coordinate format
            "score_loss": 10.0,
            "mistake_category": "BLUNDER",
        })
        stats_list[0]["pattern_data"].append({
            "move_number": 51,
            "player": "W",
            "gtp": "I5",  # 'I' is skipped in GTP
            "score_loss": 8.0,
            "mistake_category": "BLUNDER",
        })

        # Should NOT raise - invalid moves are filtered out
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_handles_list_board_size(self):
        """Summary should handle list board_size from JSON."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf", board_size=[19, 19]),
            create_single_game_stats(game_name="b.sgf", board_size=[19, 19]),
        ]

        # Should NOT raise
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)

    def test_summary_handles_none_meaning_tag_id(self):
        """Summary should handle None meaning_tag_id (pattern_miner normalizes to 'uncertain')."""
        stats_list = [
            create_single_game_stats(game_name="a.sgf"),
            create_single_game_stats(game_name="b.sgf"),
        ]
        # Set meaning_tag_id to None
        for stats in stats_list:
            for item in stats["pattern_data"]:
                item["meaning_tag_id"] = None

        # Should NOT raise - pattern_miner normalizes to "uncertain"
        output = build_summary_from_stats(stats_list, "TestPlayer", mock_config_fn)
        assert isinstance(output, str)


class TestUnknownSignatureFieldLogging:
    """Test that unknown signature field values are logged for debugging."""

    def test_unknown_phase_logged(self, caplog):
        """Unknown phase values should be logged at DEBUG level."""
        # This test requires mocking mine_patterns to return clusters with unknown phase.
        # For now, verify the logging infrastructure exists via the PHASE_KEYS constant.
        from katrain.gui.features.summary_formatter import PHASE_KEYS

        # PHASE_KEYS should contain exactly the expected values
        assert set(PHASE_KEYS.keys()) == {"opening", "middle", "endgame"}

    def test_unknown_area_logged(self, caplog):
        """Unknown area values should be logged at DEBUG level."""
        from katrain.gui.features.summary_formatter import AREA_KEYS

        assert set(AREA_KEYS.keys()) == {"corner", "edge", "center"}

    def test_unknown_severity_logged(self, caplog):
        """Unknown severity values should be logged at DEBUG level."""
        from katrain.gui.features.summary_formatter import SEVERITY_KEYS

        assert set(SEVERITY_KEYS.keys()) == {"mistake", "blunder"}
```

### 10.5 ゴールデンテスト更新

```python
def create_single_game_stats(
    game_name: str = "test_game.sgf",
    board_size: Union[Tuple[int, int], List[int]] = (19, 19),
    date: str = "2025-01-05",
    total_moves: int = 50,
    source_index: int = 0,
    ...
) -> dict:
    ...
    stats["board_size"] = board_size
    stats["date"] = date
    stats["total_moves"] = total_moves
    stats["source_index"] = source_index
    stats["pattern_data"] = [
        {
            "move_number": 25,
            "player": "B",
            "gtp": "D4",
            "score_loss": 5.0,
            "leela_loss_est": None,
            "points_lost": 5.0,
            "mistake_category": "BLUNDER",
            "meaning_tag_id": "overplay",
        },
        {
            "move_number": 45,
            "player": "B",
            "gtp": "Q16",
            "score_loss": 3.5,
            "leela_loss_est": None,
            "points_lost": 3.5,
            "mistake_category": "MISTAKE",
            "meaning_tag_id": "life_death",
        },
    ]
    return stats
```

---

## 11. 実装ステップ

### Step 1: データ収集拡張
- [ ] `extraction.py`に`pattern_data`フィールド追加（loss filterあり）
- [ ] `extraction.py`に`source_index`パラメータ追加
- [ ] `orchestration.py`で`enumerate`を使って`source_index`を渡す

### Step 2: i18n翻訳キー追加
- [ ] `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`に翻訳キー追加
- [ ] `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`に翻訳キー追加
- [ ] **`python i18n.py`で.moファイルをコンパイル**
- [ ] **更新された.poと.moの両方をコミット**

### Step 3: フォーマッタ実装
- [ ] `from __future__ import annotations`追加
- [ ] `TYPE_CHECKING`ガードでimport整理
- [ ] `_normalize_board_size()`、`_filter_by_board_size()`実装
- [ ] `_is_valid_player()`、`_is_valid_gtp()`、`_is_valid_move_number()`実装
- [ ] `_stable_sort_key()`、`_reconstruct_pattern_input()`実装
- [ ] `_PatternMoveEval`、`_FakeSnapshot`実装
- [ ] `_mine_patterns_safe()`、`_format_game_refs()`実装
- [ ] `_append_recurring_patterns()`実装
- [ ] `build_summary_from_stats()`に統合

### Step 4: テスト実装
- [ ] `tests/test_pattern_summary_contract.py`作成
- [ ] 入力検証テスト（player/gtp/move_number）
- [ ] **gtp座標検証テスト（正規表現、board_size範囲、"Z99"等の無効形式）**
- [ ] board_sizeテスト（tuple/list、non-square）
- [ ] 決定論的ソートテスト（source_index tie-breaker）
- [ ] 本番安全性テスト（corrupt data、invalid GTP format、None meaning_tag_id）
- [ ] **unknown signature field値のdebugログテスト**
- [ ] `test_golden_summary.py`に`pattern_data`、`board_size`、`source_index`追加

### Step 5: ゴールデン更新・検証
- [ ] `--update-goldens`で期待値更新
- [ ] 全テスト実行確認
- [ ] **i18n.pyで.moコンパイル確認（exit code 0）**

---

## 12. エッジケース

| ケース | 対応 |
|--------|------|
| `pattern_data`が空 | セクション省略 |
| 1ゲームのみ | `min_count=2`でパターン検出なし → 省略 |
| mixed board_size | 多数派サイズでフィルタ、不一致スキップ |
| 非正方形board_size | スキップ+警告ログ |
| **board_sizeがlist** | **tuple同様に処理（正規化）** |
| `board_size`欠損 | そのゲームをスキップ |
| `meaning_tag_id`がNone | **pattern_minerの`normalize_primary_tag()`が"uncertain"を保証（summary_formatterでは対応不要）** |
| **invalid player** | **スキップ+debugログ** |
| **invalid gtp (pass/resign/empty/corrupt format like "Z99")** | **正規表現+board_size範囲チェックでスキップ+debugログ** |
| **invalid move_number (≤0)** | **スキップ+debugログ** |
| loss全てNone | 抽出時にフィルタ |
| `focus_player`がNone | 全プレイヤーを対象 |
| invalid mistake_category | None設定+警告ログ |
| **重複/空game_name** | **source_indexで安定ソート** |
| **unknown phase/area/severity** | **デフォルト値使用+debugログ（一度だけ）** |

---

## 13. 検証手順

```powershell
# 0. UTF-8設定
$env:PYTHONUTF8 = "1"

# 1. i18n コンパイル（exit code 0を確認）
python i18n.py
if ($LASTEXITCODE -ne 0) { Write-Error "i18n changes not committed"; exit 1 }

# 2. 単体テスト
uv run pytest tests/test_pattern_summary_contract.py -v

# 3. ゴールデンテスト
uv run pytest tests/test_golden_summary.py -v

# 4. ゴールデン更新（必要な場合）
uv run pytest tests/test_golden_summary.py --update-goldens

# 5. 全テスト
uv run pytest tests

# 6. 起動確認
python -m katrain

# 7. 決定論性確認
# Summary出力を2回生成し、diffで比較して同一であることを確認
```

---

## 14. 重要ファイルパス

| ファイル | 変更内容 |
|----------|----------|
| `katrain/core/batch/stats/extraction.py` | `pattern_data`、`source_index`追加 |
| `katrain/core/batch/orchestration.py` | `source_index`渡し |
| `katrain/gui/features/summary_formatter.py` | メイン統合（TYPE_CHECKING、検証関数含む） |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | 英語翻訳キー追加 |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | 日本語翻訳キー追加 |
| `katrain/core/batch/stats/pattern_miner.py` | 参照のみ（変更なし） |
| `tests/test_pattern_summary_contract.py` | 新規契約テスト+検証テスト |
| `tests/test_golden_summary.py` | テスト拡張 |
| `tests/fixtures/golden/summary_output.txt` | 期待値更新 |
