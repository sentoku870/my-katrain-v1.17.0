# Implementation Plan: Phase A + B (Revised)

> ⚠️ **Archived**: Phase A+B 計画時点（2026-01-03）の記録。一部未実装。

> **Status**: Draft for User Approval (Revision 2)
> **Created**: 2026-01-03
> **Scope**: Batch Analyze UX Improvements + Policy Entropy Normalization

---

## Executive Summary

This plan covers two phases of improvements:

- **Phase A**: Batch Analyze UX improvements (player filter GUI, per-player summaries, settings persistence, i18n)
- **Phase B**: Technical improvement (policy entropy normalization for board-size awareness)

**Modification Level**: Lv3 (Multiple files)

---

## Investigation Results: File Locations

### Confirmed UI Locations

| Component | File | Notes |
|-----------|------|-------|
| Batch Analyze popup | `katrain/__main__.py` lines 2824-3200+ | Entire dialog built in Python code |
| Menu trigger | `katrain/gui.kv` line 925-928 | Just menu item, calls `batch-analyze-popup` |
| No separate GUI file | N/A | All batch UI is in `__main__.py` |

**Conclusion**: A1/A3 changes are confined to `__main__.py` only. No `.kv` changes needed for the popup UI.

### Thread-Safety Verification

Current implementation already uses `Clock.schedule_once()` for UI updates from background thread:
- `log_cb()`: line 3077-3082
- `progress_cb()`: line 3085-3088
- `show_summary()`: line 3128+

**Conclusion**: Thread-safety pattern is already established. New UI updates must follow same pattern.

### board_size Format Verification

`board_size` is a **tuple** `(x, y)` throughout the codebase:
- `game_node.py:75`: `szx, szy = self.root.board_size`
- `eval_metrics.py:342`: `board_size: Tuple[int, int]`
- `classify_game_phase()` uses single int (extracted from tuple)

**Conclusion**: B1 must handle both tuple and int inputs for compatibility.

---

## Phase A: Batch Analyze UX Improvements

### A1: Add karte_player_filter GUI Controls

**Goal**: Add "Player Filter" radio buttons (Both/Black/White) to Batch Analyze popup.

**File**: [katrain/__main__.py](katrain/__main__.py#L2966) (lines 2966-3016)

**Design**:

```
┌─────────────────────────────────────────────────────────┐
│  [Label: Player Filter:] [Both] [Black] [White]         │
└─────────────────────────────────────────────────────────┘
```

**Implementation Steps**:

1. Add import at top of file:
   ```python
   from kivy.uix.togglebutton import ToggleButton
   ```

2. Add new row after `options_row3` (~line 3010):
   ```python
   # Player filter row
   player_filter_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(5))
   player_filter_label = Label(
       text=i18n._("mykatrain:batch:player_filter"),
       size_hint_x=0.3, halign="right", valign="middle"
   )
   player_filter_label.bind(size=player_filter_label.setter('text_size'))

   # Load saved state
   saved_filter = batch_options.get("karte_player_filter")  # None, "B", or "W"

   filter_both = ToggleButton(
       text=i18n._("mykatrain:batch:filter_both"),
       group="player_filter",
       state="down" if saved_filter is None else "normal",
       size_hint_x=0.23
   )
   filter_black = ToggleButton(
       text=i18n._("mykatrain:batch:filter_black"),
       group="player_filter",
       state="down" if saved_filter == "B" else "normal",
       size_hint_x=0.23
   )
   filter_white = ToggleButton(
       text=i18n._("mykatrain:batch:filter_white"),
       group="player_filter",
       state="down" if saved_filter == "W" else "normal",
       size_hint_x=0.23
   )

   player_filter_row.add_widget(player_filter_label)
   player_filter_row.add_widget(filter_both)
   player_filter_row.add_widget(filter_black)
   player_filter_row.add_widget(filter_white)
   main_layout.add_widget(player_filter_row)
   ```

3. Helper function inside `_do_batch_analyze_popup()`:
   ```python
   def get_player_filter() -> Optional[str]:
       if filter_black.state == "down":
           return "B"
       elif filter_white.state == "down":
           return "W"
       return None  # Both = no filter
   ```

4. Wire to `run_batch()` call (~line 3121):
   ```python
   karte_player_filter=get_player_filter(),
   ```

**Scope Clarification**:
- A1 Player Filter is for **Karte reports only** (per-game focus)
- A2 Per-Player Summary is a **separate axis** (multi-game aggregation by player name)
- These are independent features that don't conflict

---

### A2: Per-Player Summary Generation

**Goal**: Generate separate summaries per player instead of mixing all games.

**Files**:
- [katrain/tools/batch_analyze_sgf.py](katrain/tools/batch_analyze_sgf.py#L620) (primary)
- [katrain/__main__.py](katrain/__main__.py#L3110) (pass new parameter)

**Design Principle**: Reuse existing `_build_batch_summary()` logic, don't duplicate.

#### Step 1: Add player extraction helper

New function `_extract_players_from_stats()` (~line 720):

```python
def _extract_players_from_stats(
    game_stats_list: List[dict],
    min_games: int = 3
) -> Dict[str, List[Tuple[dict, str]]]:
    """
    Extract player names and group their games.

    Args:
        game_stats_list: List of game stats dicts
        min_games: Minimum games required per player

    Returns:
        Dict mapping normalized_player_name -> [(game_stats, role), ...]
        where role is "B" or "W"

    Design Notes:
        - Names are normalized (strip whitespace, NFKC normalize)
        - Original display name preserved in tuple for output
        - Generic names ("Black", "White", "黒", "白", etc.) are skipped
        - Players with < min_games are excluded
    """
    import unicodedata
    from collections import defaultdict

    SKIP_NAMES = {"Black", "White", "黒", "白", "", "?", "Unknown", "不明"}

    # Track: normalized_name -> [(stats, role, original_name), ...]
    player_games: Dict[str, List[Tuple[dict, str, str]]] = defaultdict(list)

    def normalize_name(name: str) -> str:
        """Normalize player name for grouping."""
        name = name.strip()
        name = unicodedata.normalize("NFKC", name)
        # Collapse multiple spaces
        name = " ".join(name.split())
        return name

    for stats in game_stats_list:
        pb_orig = stats.get("player_black", "").strip()
        pw_orig = stats.get("player_white", "").strip()

        if pb_orig and pb_orig not in SKIP_NAMES:
            pb_norm = normalize_name(pb_orig)
            player_games[pb_norm].append((stats, "B", pb_orig))

        if pw_orig and pw_orig not in SKIP_NAMES:
            pw_norm = normalize_name(pw_orig)
            player_games[pw_norm].append((stats, "W", pw_orig))

    # Filter by min_games and convert to output format
    result = {}
    for norm_name, games in player_games.items():
        if len(games) >= min_games:
            # Use first original name as display name
            display_name = games[0][2]
            # Check for name variants
            variants = set(g[2] for g in games)
            if len(variants) > 1:
                # Log warning about name variants
                pass  # Will be logged in caller
            result[display_name] = [(g[0], g[1]) for g in games]

    return result
```

#### Step 2: Add per-player summary builder

New function `_build_player_summary()`:

```python
def _build_player_summary(
    player_name: str,
    player_games: List[Tuple[dict, str]],  # (stats, role)
) -> str:
    """
    Build summary for a single player across their games.

    Reuses aggregation logic from existing code, filtered to player's moves only.
    """
    from datetime import datetime
    from katrain.core import eval_metrics

    lines = [f"# Player Summary: {player_name}\n"]
    lines.append(f"**Games analyzed**: {len(player_games)}\n")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Aggregate only this player's moves
    total_moves = 0
    total_loss = 0.0
    phase_mistake_counts = {}
    phase_mistake_loss = {}
    all_worst = []
    games_as_black = 0
    games_as_white = 0

    for stats, role in player_games:
        if role == "B":
            games_as_black += 1
        else:
            games_as_white += 1

        # Only count this player's moves/loss
        total_moves += stats["moves_by_player"].get(role, 0)
        total_loss += stats["loss_by_player"].get(role, 0.0)

        # Phase x Mistake aggregation (filtered by player)
        # ... (aggregate logic, filter worst_moves by role) ...

        for move_num, player, gtp, loss, cat in stats.get("worst_moves", []):
            if player == role:
                all_worst.append((stats["game_name"], move_num, gtp, loss, cat))

    # Overview
    lines.append(f"\n## Overview\n")
    lines.append(f"- Games as Black: {games_as_black}")
    lines.append(f"- Games as White: {games_as_white}")
    lines.append(f"- Total moves: {total_moves}")
    lines.append(f"- Total points lost: {total_loss:.1f}")
    if total_moves > 0:
        lines.append(f"- Average loss per move: {total_loss / total_moves:.2f}")

    # ... (rest of summary sections, similar to existing) ...

    return "\n".join(lines)
```

#### Step 3: Modify `run_batch()` for multi-summary output

Add new parameter and logic (~line 410, 620):

```python
def run_batch(
    # ... existing params ...
    min_games_per_player: int = 3,  # NEW
) -> BatchResult:
```

Summary generation section (~line 620):

```python
if generate_summary and game_stats_list and not result.cancelled:
    try:
        log("Generating per-player summaries...")

        # Extract and group by player
        player_groups = _extract_players_from_stats(
            game_stats_list,
            min_games=min_games_per_player
        )

        if player_groups:
            summary_count = 0
            for player_name, player_games in player_groups.items():
                # Sanitize filename
                safe_name = _sanitize_filename(player_name)
                summary_filename = f"summary_{safe_name}_{batch_timestamp}.md"
                summary_path = os.path.join(output_dir, "reports", "summary", summary_filename)

                summary_text = _build_player_summary(player_name, player_games)

                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)

                log(f"  [{player_name}] {len(player_games)} games -> {summary_filename}")
                summary_count += 1

            result.summary_written = True
            result.summary_count = summary_count  # NEW field in BatchResult
        else:
            log(f"No players with >= {min_games_per_player} games found")
            result.summary_error = f"No players with >= {min_games_per_player} games"

    except Exception as e:
        # ... error handling ...
```

#### Step 4: Filename sanitization with full safety

```python
import re

# Windows reserved names
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

def _sanitize_filename(name: str, max_length: int = 50) -> str:
    """
    Sanitize player name for use in filename.

    Handles:
        - Invalid characters (<>:"/\\|?*)
        - Whitespace normalization
        - Windows reserved names (CON, PRN, NUL, etc.)
        - Empty result fallback
        - Length truncation

    Args:
        name: Original player name
        max_length: Maximum filename length (default 50)

    Returns:
        Safe filename string
    """
    if not name:
        return "unknown"

    # Remove/replace invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Normalize whitespace
    safe = re.sub(r'\s+', '_', safe)
    # Remove leading/trailing dots and underscores
    safe = safe.strip('._')

    # Check for Windows reserved names (case-insensitive)
    if safe.upper() in WINDOWS_RESERVED:
        safe = f"_{safe}_"

    # Truncate to max length
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('_')

    # Final fallback if empty
    if not safe:
        return "unknown"

    return safe
```

#### Step 5: Collision avoidance for duplicate sanitized names

```python
def _get_unique_filename(base_path: str, extension: str = ".md") -> str:
    """
    Generate unique filename by adding suffix if collision exists.

    Args:
        base_path: Full path without extension
        extension: File extension including dot

    Returns:
        Unique file path
    """
    path = base_path + extension
    if not os.path.exists(path):
        return path

    counter = 1
    while True:
        path = f"{base_path}_{counter}{extension}"
        if not os.path.exists(path):
            return path
        counter += 1
        if counter > 100:  # Safety limit
            import hashlib
            hash_suffix = hashlib.md5(base_path.encode()).hexdigest()[:6]
            return f"{base_path}_{hash_suffix}{extension}"
```

---

### A3: Complete Batch Options Persistence

**Goal**: Persist all batch options across sessions.

**File**: [katrain/__main__.py](katrain/__main__.py#L3104)

**Current State** (line 3104-3108):
Only 3 options persisted: `save_analyzed_sgf`, `generate_karte`, `generate_summary`

**Proposed Changes**:

1. Expand save call:
   ```python
   self._save_batch_options({
       # Existing
       "save_analyzed_sgf": save_analyzed_sgf,
       "generate_karte": generate_karte,
       "generate_summary": generate_summary,
       # New
       "karte_player_filter": get_player_filter(),
       "visits": visits if visits else None,
       "timeout": timeout if timeout != 600.0 else None,
       "output_directory": output_dir if output_dir != input_dir else None,
       "min_games_per_player": min_games_per_player,
   })
   ```

2. Load defaults when creating inputs (~lines 2900-2940):
   ```python
   saved_visits = batch_options.get("visits")
   visits_input = TextInput(
       text=str(saved_visits) if saved_visits else "",
       # ...
   )

   saved_timeout = batch_options.get("timeout", 600)
   timeout_input = TextInput(
       text=str(saved_timeout),
       # ...
   )

   saved_min_games = batch_options.get("min_games_per_player", 3)
   min_games_input = TextInput(
       text=str(saved_min_games),
       input_filter="int",
       # ...
   )
   ```

3. Add min_games input field to UI (new row or in options_row2).

**Backward Compatibility**:
- Missing keys in saved settings use sensible defaults
- Old settings without new keys work correctly
- No migration needed

---

### A4: i18n Updates

**New Keys Required**:

| Key | English (msgstr) | Japanese (msgstr) |
|-----|------------------|-------------------|
| `mykatrain:batch:player_filter` | `Player Filter:` | `プレイヤー絞り込み:` |
| `mykatrain:batch:filter_both` | `Both` | `両方` |
| `mykatrain:batch:filter_black` | `Black` | `黒番` |
| `mykatrain:batch:filter_white` | `White` | `白番` |
| `mykatrain:batch:min_games` | `Min games/player:` | `最低対局数:` |
| `mykatrain:batch:summary_player` | `Summary: {player} ({count} games)` | `サマリー: {player} ({count}局)` |

**Files to Update**:
1. `katrain/i18n/locales/en/LC_MESSAGES/katrain.po`
2. `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po`
3. Compile `.mo` files: `python i18n.py`

**Workflow** (per `docs/i18n-workflow.md`):
1. Add msgid/msgstr pairs to both `.po` files
2. Run `python i18n.py` to auto-add to other locales and compile all `.mo`
3. Commit both `.po` and `.mo` files

---

## Phase B: Policy Entropy Normalization

### B1: Board-Size Aware Entropy Thresholds

**Goal**: Normalize policy entropy for different board sizes (9x9, 13x13, 19x19).

**File**: [katrain/core/eval_metrics.py](katrain/core/eval_metrics.py#L832)

**Current State** (lines 832-885):
- Hardcoded thresholds calibrated for 19x19
- `board_size` not passed to function
- Max entropy for 19x19 ≈ log(361) ≈ 5.89

**Mathematical Basis**:
```
Maximum Shannon entropy = log(N) where N = board_size_x * board_size_y
Normalized entropy = raw_entropy / log(board_size_x * board_size_y)
```

**Scaling Table**:

| Board Size | N (points) | Max Entropy | Scale Factor |
|------------|------------|-------------|--------------|
| 9×9        | 81         | 4.39        | 0.75         |
| 13×13      | 169        | 5.13        | 0.87         |
| 19×19      | 361        | 5.89        | 1.00         |

**Proposed Changes**:

1. Update function signature to accept board_size:
   ```python
   def _assess_difficulty_from_policy(
       policy: List[float],
       *,
       board_size: Union[int, Tuple[int, int]] = 19,  # NEW: int or (x, y) tuple
       entropy_easy_threshold: float = 2.5,
       entropy_hard_threshold: float = 1.0,
       top5_easy_threshold: float = 0.5,
       top5_hard_threshold: float = 0.9,
   ) -> Tuple[PositionDifficulty, float]:
   ```

2. Calculate normalized thresholds:
   ```python
   import math

   # Handle both int and tuple board_size
   if isinstance(board_size, tuple):
       board_points = board_size[0] * board_size[1]
   else:
       board_points = board_size * board_size

   # Safety check
   if board_points <= 0:
       board_points = 361  # Default to 19x19

   # Reference: 19x19 board
   REF_BOARD_POINTS = 361
   ref_max_entropy = math.log(REF_BOARD_POINTS)  # ~5.89

   # Current board max entropy
   current_max_entropy = math.log(board_points)

   # Scale factor
   scale_factor = current_max_entropy / ref_max_entropy

   # Adjusted thresholds
   adjusted_easy = entropy_easy_threshold * scale_factor
   adjusted_hard = entropy_hard_threshold * scale_factor
   ```

3. Update caller `assess_position_difficulty_from_parent()` (~line 888):
   ```python
   # Get board_size from game node
   board_size = node.root.board_size  # Returns tuple (x, y)

   return _assess_difficulty_from_policy(
       parent_policy,
       board_size=board_size,
       # ... other params
   )
   ```

4. Guard against edge cases:
   ```python
   # In _assess_difficulty_from_policy:
   if board_points < 9:  # Smaller than 3x3 is invalid
       board_points = 361  # Fallback to 19x19
   ```

---

## Test Plan

### Unit Tests

**File**: [tests/test_batch_analyzer.py](tests/test_batch_analyzer.py)

```python
class TestPlayerExtraction:
    """Tests for player name extraction and grouping."""

    def test_extract_players_basic(self):
        """Basic player extraction."""
        stats = [
            {"player_black": "Alice", "player_white": "Bob", ...},
            {"player_black": "Alice", "player_white": "Charlie", ...},
            {"player_black": "Bob", "player_white": "Alice", ...},
        ]
        groups = _extract_players_from_stats(stats, min_games=2)
        assert "Alice" in groups
        assert len(groups["Alice"]) == 3
        assert "Bob" in groups
        assert len(groups["Bob"]) == 2
        assert "Charlie" not in groups  # Only 1 game

    def test_skip_generic_names(self):
        """Generic names should be skipped."""
        stats = [
            {"player_black": "Black", "player_white": "White", ...},
            {"player_black": "黒", "player_white": "白", ...},
        ]
        groups = _extract_players_from_stats(stats, min_games=1)
        assert len(groups) == 0

    def test_name_normalization(self):
        """Names with different whitespace should group together."""
        stats = [
            {"player_black": "Alice  ", "player_white": "Bob", ...},
            {"player_black": " Alice", "player_white": "Bob", ...},
            {"player_black": "Alice", "player_white": "Bob", ...},
        ]
        groups = _extract_players_from_stats(stats, min_games=1)
        assert "Alice" in groups
        assert len(groups["Alice"]) == 3


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_basic_names(self):
        assert _sanitize_filename("Alice") == "Alice"
        assert _sanitize_filename("Bob Smith") == "Bob_Smith"

    def test_cjk_names(self):
        assert _sanitize_filename("田中太郎") == "田中太郎"
        assert _sanitize_filename("山田/ヨセ") == "山田_ヨセ"

    def test_invalid_chars(self):
        assert _sanitize_filename("Alice<>Bob") == "Alice__Bob"
        assert _sanitize_filename("User:Name") == "User_Name"

    def test_windows_reserved(self):
        assert _sanitize_filename("CON") == "_CON_"
        assert _sanitize_filename("NUL") == "_NUL_"
        assert _sanitize_filename("com1") == "_com1_"

    def test_whitespace(self):
        assert _sanitize_filename("　全角スペース　") == "全角スペース"
        assert _sanitize_filename("  multiple   spaces  ") == "multiple_spaces"

    def test_empty_fallback(self):
        assert _sanitize_filename("") == "unknown"
        assert _sanitize_filename("   ") == "unknown"
        assert _sanitize_filename("...") == "unknown"

    def test_length_truncation(self):
        long_name = "a" * 100
        result = _sanitize_filename(long_name)
        assert len(result) <= 50


class TestEntropyNormalization:
    """Tests for board-size aware entropy normalization."""

    def test_uniform_distribution_all_sizes(self):
        """Uniform distribution should be EASY on all board sizes."""
        for size in [9, 13, 19]:
            n = size * size
            uniform = [1.0 / n] * n
            diff, _ = _assess_difficulty_from_policy(uniform, board_size=size)
            assert diff == PositionDifficulty.EASY

    def test_concentrated_distribution_all_sizes(self):
        """Single dominant move should be ONLY_MOVE on all board sizes."""
        for size in [9, 13, 19]:
            n = size * size
            concentrated = [0.0] * n
            concentrated[0] = 0.95
            concentrated[1] = 0.05
            diff, _ = _assess_difficulty_from_policy(concentrated, board_size=size)
            assert diff in (PositionDifficulty.ONLY_MOVE, PositionDifficulty.HARD)

    def test_board_size_as_tuple(self):
        """Should handle board_size as tuple (x, y)."""
        uniform = [1.0 / 361] * 361
        diff, _ = _assess_difficulty_from_policy(uniform, board_size=(19, 19))
        assert diff == PositionDifficulty.EASY

    def test_invalid_board_size_fallback(self):
        """Invalid board size should fallback to 19x19."""
        uniform = [1.0 / 361] * 361
        diff1, _ = _assess_difficulty_from_policy(uniform, board_size=0)
        diff2, _ = _assess_difficulty_from_policy(uniform, board_size=-5)
        # Should not crash, uses 19x19 fallback
        assert diff1 is not None
        assert diff2 is not None
```

**File**: [tests/test_i18n.py](tests/test_i18n.py)

```python
def test_batch_player_filter_translations(self, locale_dir):
    """New batch analyze keys should be translated."""
    new_keys = [
        "mykatrain:batch:player_filter",
        "mykatrain:batch:filter_both",
        "mykatrain:batch:filter_black",
        "mykatrain:batch:filter_white",
        "mykatrain:batch:min_games",
    ]
    for lang in ["en", "jp"]:
        locales = gettext.translation("katrain", str(locale_dir), languages=[lang])
        for key in new_keys:
            translated = locales.gettext(key)
            assert translated != key, f"Key '{key}' not translated in '{lang}'"
```

### Manual Tests

| Test | Steps | Expected |
|------|-------|----------|
| **Player Filter UI** | Open Batch Analyze → Verify radio buttons | Both/Black/White visible, "Both" selected by default |
| **Filter Persistence** | Select "Black" → Close → Reopen | "Black" still selected |
| **Settings Persistence** | Set visits=100, timeout=300 → Reopen | Values restored |
| **Per-Player Summary** | Analyze 5+ games with 2 players | Separate summary files per player |
| **Min Games Filter** | Set min_games=4 with player having 3 games | Player excluded from summary |
| **CJK Filenames** | Player named "田中太郎" | Valid filename generated |
| **Reserved Names** | Player named "CON" | Filename is `_CON_` not `CON` |
| **9x9 Difficulty** | Analyze 9x9 game | Position difficulty reasonable |

---

## Risk Checklist

| Risk | Mitigation | Status |
|------|------------|--------|
| **Filename encoding (Windows)** | Use `_sanitize_filename()` with CJK support | Planned |
| **Windows reserved names** | Explicit check for CON/PRN/NUL/COM1-9/LPT1-9 | Planned |
| **Filename collision** | Add counter suffix if file exists | Planned |
| **Path length (Windows MAX_PATH)** | Truncate to 50 chars | Planned |
| **Player name variants** | Normalize with NFKC, log variants | Planned |
| **Empty sanitized name** | Fallback to "unknown" | Planned |
| **Division by zero (entropy)** | Guard `board_points < 9` | Planned |
| **board_size tuple vs int** | Handle both in function | Planned |
| **Thread-safety (UI updates)** | Use `Clock.schedule_once()` | Already implemented |
| **Backward compatibility (settings)** | Missing keys use defaults | Planned |
| **i18n .mo not regenerated** | Include in workflow steps | Planned |

---

## Design Decisions (Confirmed)

| Decision | Value | Notes |
|----------|-------|-------|
| `min_games_per_player` default | 3 | 0 or 1 disables filter |
| A1 filter vs A2 summary | Independent axes | Filter = per-game focus; Summary = multi-game aggregation |
| Filename test cases | `田中太郎`, `山田/ヨセ`, `Alice<>Bob`, `　全角スペース　`, `CON` | Cover CJK, invalid chars, reserved names |
| Name normalization | NFKC + strip + collapse spaces | Preserve case |

---

## Acceptance Criteria

### A1: Player Filter GUI
- [ ] Radio buttons (Both/Black/White) visible in popup
- [ ] Selection persisted across sessions
- [ ] `karte_player_filter` passed to `run_batch()`

### A2: Per-Player Summary
- [ ] Separate summary file per player
- [ ] Filename includes sanitized player name
- [ ] Players with < min_games excluded
- [ ] Only player's own moves counted in stats

### A3: Settings Persistence
- [ ] All options saved: visits, timeout, output_dir, filter, min_games
- [ ] Old settings (without new keys) load correctly
- [ ] Defaults used for missing keys

### A4: i18n
- [ ] All 6 new keys in en/jp `.po` files
- [ ] `.mo` files regenerated
- [ ] UI displays translated strings

### B1: Entropy Normalization
- [ ] `board_size` parameter added to `_assess_difficulty_from_policy()`
- [ ] Handles both int and tuple input
- [ ] 9x9/13x13/19x19 give comparable difficulty ratings
- [ ] No division by zero or crashes on invalid input

---

## Implementation Order

1. **A4 (i18n)**: Add new keys, compile .mo
2. **A1 (GUI)**: Add player filter controls
3. **A3 (Persistence)**: Wire up all options
4. **A2 (Per-Player Summary)**: Refactor summary generation
5. **B1 (Entropy)**: Add board-size normalization
6. **Tests**: Add unit tests
7. **Manual Test**: Full workflow verification

---

## Files Changed Summary

| File | Changes |
|------|---------|
| `katrain/__main__.py` | ToggleButton import, player filter UI, persistence |
| `katrain/tools/batch_analyze_sgf.py` | Player extraction, per-player summary, sanitization |
| `katrain/core/eval_metrics.py` | board_size parameter, entropy scaling |
| `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` | 6 new keys |
| `katrain/i18n/locales/jp/LC_MESSAGES/katrain.po` | 6 new keys (+ .mo) |
| `tests/test_batch_analyzer.py` | Player extraction, sanitization tests |
| `tests/test_i18n.py` | New key translation tests |

---

## Approval Requested

Please review this revised plan. Key changes from v1:
- Confirmed UI is only in `__main__.py` (no .kv changes needed)
- Added comprehensive filename sanitization (reserved names, collision, truncation)
- Added name normalization with NFKC
- Clarified A1 filter vs A2 summary are independent
- Added board_size tuple handling for B1
- Added acceptance criteria and risk checklist

Ready to proceed with implementation upon approval.
