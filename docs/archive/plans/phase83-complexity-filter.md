# Phase 83: Complexity（Chaos）フィルタ 実装計画

## 概要

**目的**: 高変動局面（scoreStdev > 20）のミスをCritical 3選定で減点し、学習価値の低いノイズを削減する

**修正レベル**: Lv2（中程度、1-2ファイル + テスト）

## 設計方針

### フィルタ戦略: 除外ではなく「割引」
- 完全除外ではデータ損失、割引なら大きなミスは残る
- 式: `critical_score *= complexity_discount` （0.3 = 70%減）
- 既存パターン: `diversity_penalty` と同様のアプローチ

### ソートセマンティクス（確認済み）
```python
# critical_moves.py L198-204 (既存、変更不要)
def _sort_key(move_number: int, score: float) -> Tuple[float, int]:
    return (-score, move_number)  # 昇順ソートで高スコアが先頭
```

### 言語一貫性の保証（End-to-End）

**呼び出しサイト検証済み**（important_moves.py L283-288）:
```python
critical_moves = select_critical_moves(
    ctx.game,
    max_moves=3,
    lang=ctx.lang,  # ← ctx.langが渡される
    level=level,
)
```

**言語フロー**:
1. `ctx.lang` → `select_critical_moves(..., lang=ctx.lang)` → `get_tag_label(..., lang=lang)` → `cm.meaning_tag_label`
2. `ctx.lang` → 複雑度注記の直接分岐（`ctx.lang == "ja"`）

**結果**: 同一Karteレポート内でType（`meaning_tag_label`）とNote（複雑度注記）は常に同じ言語で出力される。i18nキー追加は不要。

---

## 変更内容

### 1. 定数追加（critical_moves.py）

```python
# Phase 83: Complexity filter
THRESHOLD_SCORE_STDEV_CHAOS = 20.0  # Chaos判定閾値（厳密に >）
COMPLEXITY_DISCOUNT_FACTOR = 0.3    # 割引率（30%保持）
```

### 2. 必要なインポート（critical_moves.py）

```python
# 既存インポートに追加が必要な場合のみ記載
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

# Decimal, ROUND_HALF_UP は既にインポート済み (L11-12)
```

### 3. 新規関数: `_compute_complexity_discount()`

```python
def _compute_complexity_discount(score_stdev: Optional[float]) -> float:
    """Compute complexity discount factor.

    Phase 83: Chaotic positions (high scoreStdev) receive reduced importance.

    Boundary behavior:
        score_stdev <= 20.0: no discount (1.0)
        score_stdev >  20.0: discounted (0.3)

    Args:
        score_stdev: KataGo scoreStdev value (None for Leela/unanalyzed)

    Returns:
        1.0: 通常（割引なし、Leela/未解析含む）
        COMPLEXITY_DISCOUNT_FACTOR: 高複雑度（割引あり）
    """
    if score_stdev is None:
        return 1.0
    if score_stdev > THRESHOLD_SCORE_STDEV_CHAOS:
        return COMPLEXITY_DISCOUNT_FACTOR
    return 1.0
```

### 4. 関数修正: `_compute_critical_score()`

```python
def _compute_critical_score(
    importance: float,
    tag_id: Optional[str],
    selected_tag_ids: Tuple[str, ...],
    complexity_discount: float = 1.0,  # NEW: Phase 83
) -> float:
    """Compute critical score with deterministic rounding.

    Formula: importance * meaning_tag_weight * diversity_penalty * complexity_discount
    """
    weight = _get_meaning_tag_weight(tag_id)
    penalty = _compute_diversity_penalty(tag_id, selected_tag_ids)

    raw_score = importance * weight * penalty * complexity_discount

    quantized = Decimal(str(raw_score)).quantize(
        Decimal(10) ** -CRITICAL_SCORE_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    return float(quantized)
```

### 5. CriticalMove拡張

```python
@dataclass(frozen=True)
class CriticalMove:
    # ... existing fields (L73-121) ...

    # Phase 83: Complexity filter metadata
    complexity_discounted: bool = False
```

### 6. 統計用dataclass

```python
@dataclass
class ComplexityFilterStats:
    """Statistics for complexity filter application (Phase 83)."""
    total_candidates: int = 0
    discounted_count: int = 0
    max_stdev_seen: Optional[float] = None

    @property
    def discount_rate(self) -> float:
        if self.total_candidates == 0:
            return 0.0
        return 100.0 * self.discounted_count / self.total_candidates
```

### 7. ログ関数

```python
_log = logging.getLogger(__name__)

def _log_complexity_filter_stats(stats: ComplexityFilterStats) -> None:
    """Log complexity filter statistics.

    INFO: when discounted_count > 0
    DEBUG: when no discounts applied
    """
    if stats.max_stdev_seen is not None:
        stdev_str = f"{stats.max_stdev_seen:.1f}"
    else:
        stdev_str = "n/a"

    if stats.discounted_count > 0:
        _log.info(
            "Complexity filter: %d/%d candidates discounted (%.1f%%), max_stdev=%s",
            stats.discounted_count,
            stats.total_candidates,
            stats.discount_rate,
            stdev_str,
        )
    else:
        _log.debug(
            "Complexity filter: no discounts applied (max_stdev=%s)",
            stdev_str,
        )
```

### 8. select_critical_moves() 修正

```python
def select_critical_moves(
    game: "Game",
    *,
    max_moves: int = 3,
    lang: str = "ja",
    level: str = "normal",
) -> List[CriticalMove]:
    # ... existing setup (L321-372 unchanged) ...

    candidates = list(important_moves)
    selected: List[CriticalMove] = []
    selected_tag_ids: Tuple[str, ...] = ()

    # Phase 83: Track statistics and cache stdev
    filter_stats = ComplexityFilterStats(total_candidates=len(candidates))
    max_stdev_seen: Optional[float] = None  # Track max directly (simpler than list)
    discounted_move_numbers: Set[int] = set()
    stdev_cache: Dict[int, Optional[float]] = {}

    for _ in range(max_moves):
        if not candidates:
            break

        scores: Dict[int, float] = {}
        for move in candidates:
            # Phase 83: Normalize early for consistent weight/penalty calculation
            tag_id = meaning_tag_map.get(move.move_number) or "uncertain"
            importance = move.importance_score or 0.0

            # Phase 83: Get stdev with caching
            if move.move_number not in stdev_cache:
                stdev_cache[move.move_number] = _get_score_stdev_for_move(
                    node_map, move.move_number
                )
            score_stdev = stdev_cache[move.move_number]
            complexity_discount = _compute_complexity_discount(score_stdev)

            if complexity_discount < 1.0:
                discounted_move_numbers.add(move.move_number)

            if score_stdev is not None:
                if max_stdev_seen is None or score_stdev > max_stdev_seen:
                    max_stdev_seen = score_stdev

            scores[move.move_number] = _compute_critical_score(
                importance, tag_id, selected_tag_ids,
                complexity_discount=complexity_discount,
            )

        candidates.sort(key=lambda m: _sort_key(m.move_number, scores[m.move_number]))

        best = candidates.pop(0)
        # tag_id already normalized in scoring loop, but ensure consistency here
        best_tag_id = meaning_tag_map.get(best.move_number) or "uncertain"

        try:
            tag_enum = MeaningTagId(best_tag_id)
            tag_label = get_tag_label(tag_enum, lang=lang)
        except ValueError:
            tag_label = best_tag_id

        best_stdev = stdev_cache.get(best.move_number)

        critical_move = CriticalMove(
            move_number=best.move_number,
            player=best.player or "?",
            gtp_coord=best.gtp or "?",
            score_loss=get_canonical_loss_from_move(best),
            delta_winrate=best.delta_winrate or 0.0,
            meaning_tag_id=best_tag_id,
            meaning_tag_label=tag_label,
            position_difficulty=(
                best.position_difficulty.value
                if best.position_difficulty is not None
                else "unknown"
            ),
            reason_tags=tuple(best.reason_tags) if best.reason_tags else (),
            score_stdev=best_stdev,
            game_phase=classify_game_phase(best.move_number, board_size),
            importance_score=best.importance_score or 0.0,
            critical_score=scores[best.move_number],
            complexity_discounted=(best.move_number in discounted_move_numbers),
        )

        selected.append(critical_move)
        selected_tag_ids = (*selected_tag_ids, best_tag_id)

    # Phase 83: Log statistics
    filter_stats.discounted_count = len(discounted_move_numbers)
    filter_stats.max_stdev_seen = max_stdev_seen
    _log_complexity_filter_stats(filter_stats)

    return selected
```

### 9. Karte出力（important_moves.py）- ctx.lang分岐方式

**i18nキーは追加しない**。既存パターン（L308-312）に従い、`ctx.lang`で直接分岐する。

```python
def critical_3_section_for(ctx: "KarteContext", ...) -> List[str]:
    # ... existing code through L327 ...

    for i, cm in enumerate(player_critical, 1):
        lines.append(f"### {i}. Move #{cm.move_number} ({cm.player}) {cm.gtp_coord}")
        lines.append(f"- **Loss**: {cm.score_loss:.1f}{unit}")
        lines.append(f"- **Type**: {cm.meaning_tag_label}")
        lines.append(f"- **Phase**: {cm.game_phase}")
        lines.append(f"- **Difficulty**: {cm.position_difficulty.upper()}")

        # Phase 83: Show complexity note (using ctx.lang for consistency)
        if cm.complexity_discounted:
            chaos_note = (
                "乱戦局面（評価の変動大）"
                if ctx.lang == "ja"
                else "Complex position (high volatility)"
            )
            lines.append(f"- **Note**: {chaos_note}")

        # ... existing context handling (L328-339) ...
```

---

## 変更ファイル一覧

| ファイル | 変更種別 |
|---------|---------|
| `katrain/core/analysis/critical_moves.py` | 主要修正 |
| `katrain/core/reports/karte/sections/important_moves.py` | 軽微修正 |
| `tests/test_complexity_filter.py` | **新規** |
| `tests/test_critical_moves.py` | テスト追加 |

**注**: i18nの`.po`/`.mo`ファイルの更新は不要（`ctx.lang`分岐方式を採用）

---

## テスト計画（CI対応、実行可能）

### 使用するヘルパー（既存、検証済み）

以下のヘルパーは `tests/helpers_critical_moves.py` に存在し、`tests/test_critical_moves.py` L44-55でインポート済み：

```python
from tests.helpers_critical_moves import (
    StubGameNodeWithAnalysis,
    build_stub_game_with_analysis,
    create_test_snapshot,
    create_test_snapshot_with_tags,
    create_standard_test_game,
    create_standard_test_snapshot,
    StubGame,
    StubGameNode,
    StubMove,
    make_move_eval,
)
```

### 1. ユニットテスト: test_complexity_filter.py（新規）

```python
"""Unit tests for Phase 83 Complexity filter.

All tests are CI-friendly (no real engine, no file I/O).
"""
import pytest

from katrain.core.analysis.critical_moves import (
    THRESHOLD_SCORE_STDEV_CHAOS,
    COMPLEXITY_DISCOUNT_FACTOR,
    _compute_complexity_discount,
    ComplexityFilterStats,
)


class TestComputeComplexityDiscount:
    """Tests for _compute_complexity_discount() boundary behavior."""

    def test_none_stdev_returns_no_discount(self):
        """None scoreStdev (Leela/unanalyzed) returns 1.0."""
        assert _compute_complexity_discount(None) == 1.0

    def test_zero_stdev_returns_no_discount(self):
        """Zero stdev (rare but valid) returns 1.0."""
        assert _compute_complexity_discount(0.0) == 1.0

    def test_low_stdev_returns_no_discount(self):
        """Low stdev (< threshold) returns 1.0."""
        assert _compute_complexity_discount(5.0) == 1.0
        assert _compute_complexity_discount(19.99) == 1.0

    def test_exactly_at_threshold_returns_no_discount(self):
        """Exactly at threshold (==20.0) returns 1.0 (boundary: > not >=)."""
        assert _compute_complexity_discount(20.0) == 1.0
        assert _compute_complexity_discount(THRESHOLD_SCORE_STDEV_CHAOS) == 1.0

    def test_above_threshold_returns_discount(self):
        """Above threshold (>20.0) returns discount factor."""
        assert _compute_complexity_discount(20.01) == COMPLEXITY_DISCOUNT_FACTOR
        assert _compute_complexity_discount(20.1) == COMPLEXITY_DISCOUNT_FACTOR
        assert _compute_complexity_discount(50.0) == COMPLEXITY_DISCOUNT_FACTOR

    def test_discount_factor_in_valid_range(self):
        """Verify discount factor is in valid range (0, 1)."""
        assert 0.0 < COMPLEXITY_DISCOUNT_FACTOR < 1.0

    def test_threshold_value(self):
        """Verify threshold is 20.0 as specified."""
        assert THRESHOLD_SCORE_STDEV_CHAOS == 20.0


class TestComplexityFilterStats:
    """Tests for ComplexityFilterStats dataclass."""

    def test_discount_rate_zero_candidates_no_division_error(self):
        """Zero candidates returns 0.0 rate (no ZeroDivisionError)."""
        stats = ComplexityFilterStats(total_candidates=0, discounted_count=0)
        assert stats.discount_rate == 0.0

    def test_discount_rate_calculation(self):
        """Discount rate calculated correctly."""
        stats = ComplexityFilterStats(total_candidates=10, discounted_count=3)
        assert stats.discount_rate == 30.0

    def test_discount_rate_100_percent(self):
        """100% discount rate."""
        stats = ComplexityFilterStats(total_candidates=5, discounted_count=5)
        assert stats.discount_rate == 100.0

    def test_max_stdev_default_is_none(self):
        """max_stdev defaults to None (not 0.0)."""
        stats = ComplexityFilterStats()
        assert stats.max_stdev_seen is None
```

### 2. 統合テスト: test_critical_moves.py に追加

```python
"""Integration tests for complexity filter in select_critical_moves().

Uses existing test helpers from tests/helpers_critical_moves.py.
All tests are CI-friendly (mock-based, no real engine).

Patch targets for local imports (patch the source module):
- "katrain.core.analysis.snapshot_from_game"
  → Local import in select_critical_moves() from katrain.core.analysis
- "katrain.core.analysis.pick_important_moves"
  → Local import in select_critical_moves() from katrain.core.analysis
- "katrain.core.analysis.meaning_tags.classify_meaning_tag"
  → Local import in _classify_meaning_tags() from katrain.core.analysis.meaning_tags

Note: For local imports inside functions, patch the SOURCE module
(where the function is defined), not the importing module. When Python
executes `from X import Y`, it looks up Y in module X at that moment.
"""
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.analysis.critical_moves import (
    select_critical_moves,
    _compute_critical_score,
    _sort_key,
    COMPLEXITY_DISCOUNT_FACTOR,
)
from katrain.core.analysis.models import EvalSnapshot
from tests.helpers_critical_moves import (
    build_stub_game_with_analysis,
    create_test_snapshot,
)


class TestSelectCriticalMovesComplexity:
    """Integration tests for complexity filter in selection."""

    def test_chaotic_move_gets_lower_critical_score(self):
        """Move with high stdev gets lower critical score than equal-importance normal move.

        Setup:
            Move 1: stdev=5.0 (normal)
            Move 2: stdev=25.0 (chaotic)
            Both have equal importance_score=10.0

        Expected:
            Move 1 selected first (higher effective score)
            Move 2 selected second (discounted)
        """
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 5.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 25.0}}),
        ])

        snapshot = create_test_snapshot([
            {
                "move_number": 1,
                "player": "B",
                "gtp": "D4",
                "score_loss": 5.0,
                "importance_score": 10.0,
            },
            {
                "move_number": 2,
                "player": "W",
                "gtp": "Q16",
                "score_loss": 5.0,
                "importance_score": 10.0,
            },
        ])

        with patch("katrain.core.analysis.snapshot_from_game") as mock_snapshot:
            mock_snapshot.return_value = snapshot

            with patch("katrain.core.analysis.pick_important_moves") as mock_pick:
                mock_pick.return_value = snapshot.moves

                with patch(
                    "katrain.core.analysis.meaning_tags.classify_meaning_tag"
                ) as mock_classify:
                    mock_tag = MagicMock()
                    mock_tag.id.value = "overplay"
                    mock_classify.return_value = mock_tag

                    result = select_critical_moves(game, max_moves=2)

        # Assertions using ordering (robust to rounding)
        assert len(result) == 2
        assert result[0].move_number == 1, "Normal move should be selected first"
        assert result[0].complexity_discounted is False
        assert result[1].move_number == 2, "Chaotic move should be selected second"
        assert result[1].complexity_discounted is True
        # Score ordering (discounted < normal)
        assert result[1].critical_score < result[0].critical_score

    def test_leela_moves_not_penalized(self):
        """Leela moves (no scoreStdev in analysis) are not discounted."""
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"winrate": 0.55}}),
        ])

        snapshot = create_test_snapshot([
            {
                "move_number": 1,
                "player": "B",
                "gtp": "D4",
                "score_loss": 5.0,
                "importance_score": 10.0,
            },
        ])

        with patch("katrain.core.analysis.snapshot_from_game") as mock_snapshot:
            mock_snapshot.return_value = snapshot

            with patch("katrain.core.analysis.pick_important_moves") as mock_pick:
                mock_pick.return_value = snapshot.moves

                with patch(
                    "katrain.core.analysis.meaning_tags.classify_meaning_tag"
                ) as mock_classify:
                    mock_tag = MagicMock()
                    mock_tag.id.value = "overplay"
                    mock_classify.return_value = mock_tag

                    result = select_critical_moves(game, max_moves=1)

        assert len(result) == 1
        assert result[0].complexity_discounted is False
        assert result[0].score_stdev is None

    def test_high_importance_chaotic_move_can_still_win(self):
        """Chaotic move with much higher importance can still be selected first.

        Setup:
            Move 1: importance=5.0, stdev=5.0 -> effective ~5.0
            Move 2: importance=50.0, stdev=25.0 -> effective ~15.0 (50*0.3)

        Expected: Move 2 selected first (15.0 > 5.0)
        """
        game = build_stub_game_with_analysis([
            ("B", (3, 3), 0.5, {"root": {"scoreStdev": 5.0}}),
            ("W", (15, 15), -1.0, {"root": {"scoreStdev": 25.0}}),
        ])

        snapshot = create_test_snapshot([
            {
                "move_number": 1,
                "player": "B",
                "gtp": "D4",
                "score_loss": 1.0,
                "importance_score": 5.0,
            },
            {
                "move_number": 2,
                "player": "W",
                "gtp": "Q16",
                "score_loss": 10.0,
                "importance_score": 50.0,
            },
        ])

        with patch("katrain.core.analysis.snapshot_from_game") as mock_snapshot:
            mock_snapshot.return_value = snapshot

            with patch("katrain.core.analysis.pick_important_moves") as mock_pick:
                mock_pick.return_value = snapshot.moves

                with patch(
                    "katrain.core.analysis.meaning_tags.classify_meaning_tag"
                ) as mock_classify:
                    mock_tag = MagicMock()
                    mock_tag.id.value = "overplay"
                    mock_classify.return_value = mock_tag

                    result = select_critical_moves(game, max_moves=2)

        assert result[0].move_number == 2, "High importance chaotic move wins"
        assert result[0].complexity_discounted is True
        assert result[0].critical_score > result[1].critical_score


class TestCriticalScoreWithComplexityDiscount:
    """Unit tests for _compute_critical_score() with complexity_discount parameter."""

    def test_default_discount_is_one(self):
        """Default complexity_discount=1.0 (backward compatible)."""
        score_without = _compute_critical_score(10.0, "overplay", ())
        score_with = _compute_critical_score(10.0, "overplay", (), complexity_discount=1.0)
        assert score_without == score_with

    def test_discount_reduces_score(self):
        """complexity_discount < 1.0 reduces the score (ordering test)."""
        score_normal = _compute_critical_score(10.0, "overplay", ())
        score_discounted = _compute_critical_score(
            10.0, "overplay", (), complexity_discount=0.3
        )
        assert score_discounted < score_normal
        assert score_discounted > 0

    def test_discount_combines_with_diversity_penalty(self):
        """Discount and diversity penalty both reduce score."""
        base_score = _compute_critical_score(10.0, "overplay", ())
        score_with_diversity = _compute_critical_score(10.0, "overplay", ("overplay",))
        score_with_both = _compute_critical_score(
            10.0, "overplay", ("overplay",), complexity_discount=0.3
        )

        assert score_with_diversity < base_score
        assert score_with_both < score_with_diversity
        assert score_with_both > 0


class TestSortingOrderInvariant:
    """Test that sorting order is correct (highest score at index 0)."""

    def test_sort_key_puts_highest_score_first(self):
        """Verify _sort_key produces correct ordering for pop(0)."""
        candidates = [
            (1, 5.0),
            (2, 15.0),
            (3, 10.0),
        ]

        sorted_candidates = sorted(
            candidates, key=lambda x: _sort_key(x[0], x[1])
        )

        assert sorted_candidates[0] == (2, 15.0), "Highest score should be first"
        assert sorted_candidates[1] == (3, 10.0)
        assert sorted_candidates[2] == (1, 5.0), "Lowest score should be last"

    def test_sort_key_tiebreaker_is_move_number(self):
        """Equal scores -> earlier move_number wins."""
        candidates = [
            (5, 10.0),
            (2, 10.0),
            (8, 10.0),
        ]

        sorted_candidates = sorted(
            candidates, key=lambda x: _sort_key(x[0], x[1])
        )

        assert sorted_candidates[0] == (2, 10.0)
        assert sorted_candidates[1] == (5, 10.0)
        assert sorted_candidates[2] == (8, 10.0)

    def test_sort_order_would_fail_if_inverted(self):
        """Sanity check: inverted key would produce wrong order."""
        candidates = [(1, 5.0), (2, 15.0)]

        correct_order = sorted(candidates, key=lambda x: _sort_key(x[0], x[1]))
        assert correct_order[0][1] == 15.0

        wrong_order = sorted(candidates, key=lambda x: (x[1], x[0]))
        assert wrong_order[0][1] == 5.0

        assert correct_order[0] != wrong_order[0]
```

---

## 実装ステップ（順序）

| Step | 内容 | ファイル |
|------|------|---------|
| 1 | 定数・dataclass追加 | critical_moves.py |
| 2 | `_compute_complexity_discount()` 実装 | critical_moves.py |
| 3 | ユニットテスト作成・実行 | test_complexity_filter.py |
| 4 | `_compute_critical_score()` パラメータ追加 | critical_moves.py |
| 5 | `CriticalMove.complexity_discounted` 追加 | critical_moves.py |
| 6 | `select_critical_moves()` 修正 | critical_moves.py |
| 7 | ログ関数追加・呼び出し | critical_moves.py |
| 8 | 統合テスト作成・実行 | test_critical_moves.py |
| 9 | Karte出力修正（`ctx.lang`分岐） | important_moves.py |
| 10 | 全テスト実行・起動確認 | - |

**注**: i18n `.po`/`.mo` ファイルの更新は不要（`ctx.lang`分岐方式を採用したため）

---

## 検証方法

```powershell
# 1. ユニットテスト実行
uv run pytest tests/test_complexity_filter.py -v
# または (uvがない場合)
python -m pytest tests/test_complexity_filter.py -v

# 2. 統合テスト実行
uv run pytest tests/test_critical_moves.py -v -k "Complexity or Sorting"
# または
python -m pytest tests/test_critical_moves.py -v -k "Complexity or Sorting"

# 3. 全テスト実行
uv run pytest tests -v
# または
python -m pytest tests -v

# 4. 起動確認
python -m katrain

# 5. 手動確認
# a. 乱戦の多いSGF（コウ争い、戦い多い棋譜）を読み込み
# b. Karte Exportを実行
# c. Critical 3に「乱戦局面（評価の変動大）」注記が表示されることを確認
# d. コンソールログに出力されることを確認:
#    INFO: "Complexity filter: 3/15 candidates discounted (20.0%), max_stdev=32.5"
#    DEBUG: "Complexity filter: no discounts applied (max_stdev=n/a)"
```

---

## 受け入れ基準（Acceptance Criteria）

### 必須（Must Have）
- [ ] `_compute_complexity_discount()` が境界条件を正しく処理（`> 20.0` でのみ割引）
- [ ] `_compute_critical_score()` が後方互換性を維持（`complexity_discount=1.0`がデフォルト）
- [ ] `CriticalMove.complexity_discounted` がCriticalMove構築時に正しく設定される
- [ ] `tag_id` がスコアリングループ冒頭で正規化される（`or "uncertain"`）
- [ ] `selected_tag_ids` に `None` が入らない（一貫した正規化により保証）
- [ ] `select_critical_moves()` 終了時にログ出力される
- [ ] ログで `max_stdev=n/a`（Noneの場合）と実数値を区別
- [ ] `discounted_count > 0` の場合のみINFOログ
- [ ] テストがCI対応（実エンジン不要、mock使用）
- [ ] テストは順序/不等式で比較（丸め誤差に依存しない）
- [ ] ソート順テストが存在し、反転でテストが失敗することを確認
- [ ] 既存テストが全てパス
- [ ] **混合言語なし**: 同一Karteレポート内でType（meaning_tag_label）とNote（complexity注記）が同じ言語で出力される（両方`ctx.lang`に基づく）

### 推奨（Should Have）
- [ ] Karte出力に複雑度注記が表示される（`ctx.lang`分岐方式）
- [ ] 高stdevでも重要度が十分高い手は選択される
- [ ] `stdev_cache`で`_get_score_stdev_for_move`の二重呼び出しを回避

### 将来拡張（Won't Have in Phase 83）
- 設定ファイルで閾値を変更可能に
- 連続的な割引関数（現在は二値）
- Summary/バッチ統計への反映
