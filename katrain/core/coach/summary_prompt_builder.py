"""Phase 227-A + 228-B + 270: LLM prompt builder for multi-game Summary JSON.

Companion to :mod:`katrain.core.coach.prompt_builder`, specialised for
the **multi-game summary** use-case. Whereas the Karte prompt builder
asks the LLM to translate per-move weaknesses, this builder asks the LLM
to extract **patterns that recur across N games** — the user's stated
use-case is "N局の弱点パターン抽出" (N-game weakness pattern extraction).

Why a separate module (vs. reusing ``prompt_builder``):
- The summary JSON shape differs structurally from a Karte JSON
  (``players`` keyed by name, ``phase_x_mistake`` instead of
  ``important_moves``).
- The LLM task differs: pattern mining vs. single-game review.
- A separate template keeps the existing Karte prompt stable and lets
  the summary prompt evolve independently.

Phase 228-B additions:
- Renders **Player Mistake Distribution** (count / pct / avg_loss per
  blunder / mistake / inaccuracy / good) for the focused player when
  ``players.<name>.mistakes`` is available.
- Renders **Player Phase Loss Distribution** (moves / total_loss /
  avg_loss per opening / middle / endgame) for the focused player.
- System instruction updated to acknowledge the new sections as
  valid reference sources.

Phase 270 additions:
- When ``SummaryPromptConfig.kartes`` is provided, runs the new
  :mod:`katrain.core.coach.karte_aggregator` pipeline to surface
   six per-game fields that the summary path currently drops
   (``reason_tags_distribution`` / ``area`` / ``position_difficulty``
   / ``data_quality`` / ``meaning_tag_label`` / loss-progression
   spikes). The aggregated view is rendered as one extra Markdown
   block, the body header ``Schema:`` line is bumped to ``"3.6"``,
   and the system instruction is updated so the LLM treats the new
   block as a valid reference. Existing 3.5 callers (no ``kartes``
   argument) see the exact same prompt body as before.

Public API:
- :class:`SummaryPromptConfig` — frozen config dataclass
- :class:`SummaryPrompt` — bundle of system_instruction + body + full markdown
- :func:`build_summary_weakness_prompt` — assemble a SummaryPrompt

Kivy-free. Safe to invoke from CLI / CI / GUI (lazy import).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from katrain.core.coach.json_type import (
    extract_summary_game_count,
    extract_summary_mistake_buckets,
    extract_summary_player_mistakes,
    extract_summary_player_phase_losses,
    extract_summary_total_loss,
    extract_summary_weakness_patterns,
)
from katrain.core.coach.karte_aggregator import (
    AggregatedKarteView,
    aggregate_kartes,
)
from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.tones import ToneVoice, voice_summary

# Phase 270: schema version that the prompt body shows when
# ``SummaryPromptConfig.kartes`` is populated. Kept as a module
# constant so tests and downstream code can refer to it without
# re-deriving from the docs. The 3.5 default in
# :class:`SummaryPromptConfig` is intentionally retained for back-
# compatibility — callers that do not pass kartes still see 3.5.
# (2026-07: bumped 3.5 -> 3.6 because the base report schema moved to
# 3.5; the with-kartes view stays one step ahead.)
SCHEMA_VERSION_WITH_KARTES: str = "3.6"

# --- Configuration dataclass ---


@dataclass(frozen=True)
class SummaryPromptConfig:
    """Configuration for :func:`build_summary_weakness_prompt`.

    Attributes:
        voice: Selected ToneVoice (informational; used in the body
            header so the user can see which coach persona was selected).
        mode: Selected CoachMode (informational; surfaced to the LLM
            as the target language level).
        games_analyzed: Total games in the summary. Used in the prompt
            header and for frequency calculations.
        player_name: The player whose perspective the LLM should adopt.
            When ``None``, the LLM is told to take a bird's-eye view
            ("全体俯瞰") instead of focusing on one player.
        player_rank: Optional rank string (e.g. ``"5k"``). Surfaced in
            the body header for the LLM to calibrate vocabulary.
        schema_version: Summary JSON schema version (informational).
            When ``kartes`` is provided the prompt body actually
            displays :data:`SCHEMA_VERSION_WITH_KARTES` (``"3.6"``)
            regardless of this value — the field is kept for
            downstream consumers that want to record the version
            they asked for.
        max_patterns: Cap on the number of pre-computed weakness
            patterns injected into the prompt body. Defaults to 10.
        kartes: Optional tuple of single-game Karte JSON dicts to
            aggregate. When provided, :func:`build_summary_weakness_prompt`
            runs the Phase 270 aggregator and renders a new
            ``Aggregated Karte View (schema 3.6)`` section in the
            body. Defaults to ``None`` (3.5 back-compat — no
            aggregated view, no schema bump).
    """

    voice: ToneVoice
    mode: CoachMode
    games_analyzed: int
    player_name: str | None = None
    player_rank: str | None = None
    schema_version: str = "3.5"
    max_patterns: int = 10
    kartes: tuple[dict[str, Any], ...] | None = None


# --- SummaryPrompt container ---


@dataclass(frozen=True)
class SummaryPrompt:
    """LLM prompt bundle produced by :func:`build_summary_weakness_prompt`.

    Attributes:
        system_instruction: HTML-comment-bounded instruction block.
        body_markdown: The visible Markdown body (header + JSON + patterns).
        full_markdown: Concatenation ready for clipboard copy.
        config: Echo of the input config (for downstream validation).
        referenced_patterns: Tuple of pattern dicts injected into the
            prompt body (post-cap). Useful for validation.
    """

    system_instruction: str
    body_markdown: str
    full_markdown: str
    config: SummaryPromptConfig
    referenced_patterns: tuple[dict[str, Any], ...] = field(default_factory=tuple)


# --- Templates (Phase 227-A §3) ---


_SYSTEM_INSTRUCTION_TEMPLATE = """<!--
[SYSTEM INSTRUCTION FOR LLM — MULTI-GAME SUMMARY MODE]
Role: You are a Go coach. The user has provided a multi-game Summary JSON
      (N games aggregated). Your task is to extract recurring weakness
      patterns, NOT to review a single game.
Mode: {voice_summary}
Level: {mode_label}
Games: {games_analyzed}
Focus: {focus_label}      # '{player_name}' or '全体俯瞰 (bird's-eye)'
Rank: {rank_label}

[STRICT RULES — DO NOT VIOLATE]
1. DO NOT analyze the board independently. Use ONLY the aggregated data
   in the Summary JSON. There is no per-move information available.
2. DO NOT invent specific move numbers, coordinates, or game IDs.
   Reference patterns by phase (opening/middle/endgame) + category.
3. Every weakness pattern you cite MUST come from one of these
   sources in the Summary JSON:
   - the ``weakness_patterns`` list (Phase 227-A format)
   - the ``weaknesses[<color>]`` block (Phase 227-A format)
   - the ``Player Mistake Distribution`` block (Phase 228-B format,
     categories: good / inaccuracy / mistake / blunder)
   - the ``Aggregated Karte View`` block (Phase 270 format,
     schema 3.5) when present — refer to tags by their
     ``meaning_tag_label`` from the injected ``meaning_tag_label_map``
     so the user can match the report against their kifu
   Do not invent new categories.
4. For each pattern, state:
   - 弱点名 (category)
   - 該当phase (opening/middle/endgame)
   - 頻度 (X / N局, X%) — use the injected ``pct`` field when the
     pre-computed pattern shows ``phase=`(全phase)``` (Shape B
     per-move mistake distribution), otherwise use
     ``frequency_ratio`` for Shape A per-game patterns
   - 改善の方向性 (1-2 sentences)
5. Maximum 3 patterns. Order by severity (highest total_loss first).
6. End your response with the line
   ``抽出した弱点パターン: [<category1>, <category2>, ...]``
   for downstream validation.

Format requirements:
- 冒頭に1文の全体評言（N局を通じた傾向）
- 各パターンを箇条書きで提示
- 最後に「次の1局へのアドバイス」を1文で
-->

"""


_BODY_HEADER_TEMPLATE = """# myKatrain 複数局サマリ (LLM-ready)

> Generated by :func:`katrain.core.coach.summary_prompt_builder.build_summary_weakness_prompt`.
> Schema: {schema_version}
> Games: {games_analyzed}
> Voice: {voice_summary}
> Level: {mode_label}
> Focus: {focus_label}
> Rank: {rank_label}

---

## 指示

あなたは囲碁コーチです。以下の **{games_analyzed} 局** の集計サマリを分析し、
**プレイヤーが一貫して犯している弱点パターン** を最大3つ挙げてください。

各弱点について、以下の4点を簡潔に述べてください:

1. **弱点名** — category 名（例: blunder / mistake / endgame_slip）
2. **該当phase** — opening / middle / endgame のいずれか
3. **頻度** — 「X / {games_analyzed} 局 (Y%)」の形式。注入された
   ``frequency_ratio`` フィールドを利用すること
4. **改善の方向性** — 1-2文で。具体的な訓練課題やLexicon用語を交えてよい

---

## 入力データ

### Summary JSON

```json
{summary_json}
```

### Player Mistake Distribution{player_mistakes_focus}

{player_mistakes_block}

### Player Phase Loss Distribution{player_phases_focus}

{player_phases_block}

### Weakness Patterns (pre-computed, top {patterns_count})

{patterns_block}

### Phase × Mistake Buckets

{buckets_block}

### Loss Progression (per game-type)

{loss_progression_block}
{aggregated_view_block}
---

## 最終出力形式

以下の行で**必ず**終了すること:

```
抽出した弱点パターン: [<category1>, <category2>, ...]
参照したphase: [opening, middle, ...]
```
"""


# --- Helpers ---


def _focus_label(player_name: str | None) -> str:
    """Render the Focus label for the system instruction / body header."""
    if player_name:
        return f"プレイヤー '{player_name}'"
    return "全体俯瞰 (bird's-eye)"


def _rank_label(rank: str | None) -> str:
    return rank or "(不明)"


def _format_patterns_block(patterns: list[dict[str, Any]]) -> str:
    """Render the weakness patterns as a numbered Markdown list.

    Phase 228-B: distinguishes between Shape A (Phase 227-A fixture
    style — top-level ``weaknesses`` with per-color phase/category
    tuples) and Shape B (Phase 228-A real export style — per-player
    mistakes). For Shape B patterns the ``frequency_ratio`` field is
    not meaningful (count is per-move, not per-game) so we surface the
    per-move ``pct`` field instead when available.

    Phase 269: Shape B patterns carry ``phase="all"`` (the per-move
    mistake distribution has no per-phase breakdown). The validator
    only accepts ``{opening, middle, endgame}`` as valid phase values,
    so the LLM must not echo ``all`` in the trailing contract line.
    Render the meta-tag as ``"(全phase)"`` so the LLM treats it as a
    description rather than a phase value to cite.
    """
    if not patterns:
        return "(weakness データが見つかりませんでした。Summary JSON の ``weaknesses`` ブロックを確認してください。)"
    lines: list[str] = []
    for i, p in enumerate(patterns, start=1):
        freq_pct = p.get("frequency_ratio", 0.0) * 100.0
        # Phase 228-B: Shape B patterns carry a ``pct`` field
        # (per-move percentage) that is more informative than the
        # (intentionally 0) ``frequency_ratio``. When pct is present,
        # use it for the frequency label so the LLM gets a usable
        # number instead of misleading "0.0%".
        if "pct" in p and p["frequency_ratio"] == 0.0:
            freq_str = f"全体に占める割合={p['pct']:.1f}%"
        else:
            freq_str = f"頻度={freq_pct:.1f}%"
        # The player key (if present, Shape B) takes precedence over
        # the generic ``color`` label so the LLM knows which player
        # this pattern came from.
        source_label = f"player=`{p['player']}`" if "player" in p else f"color=`{p['color']}`"
        # Phase 269: Shape B patterns have ``phase="all"`` as a meta-tag
        # (the per-move mistake distribution has no per-phase breakdown).
        # The validator rejects ``all`` as an invalid phase value, so we
        # render it as ``"(全phase)"`` here to signal it is a description
        # (not a phase label) and the LLM should pick a real phase from
        # ``{opening, middle, endgame}`` in the contract line.
        phase_display = "(全phase)" if p["phase"] == "all" else p["phase"]
        lines.append(
            f"{i}. **{p['category']}** / phase=`{phase_display}` / "
            f"{source_label} / count={p['count']} / "
            f"{freq_str} / 総損失={p['total_loss']:.1f}"
        )
    return "\n".join(lines)


def _format_buckets_block(buckets: dict[str, int]) -> str:
    """Render the phase_x_mistake buckets as a compact Markdown list."""
    if not buckets:
        return "(phase_x_mistake データがありません)"
    lines: list[str] = []
    for key in sorted(buckets.keys()):
        lines.append(f"- `{key}`: {buckets[key]}")
    return "\n".join(lines)


def _format_loss_progression_block(loss_progression: dict[str, list[Any]] | list[Any] | None) -> str:
    """Phase 241-C: render the ``loss_progression`` block for the LLM.

    The summary JSON may store ``loss_progression`` in one of three shapes:

    - ``{"all": [...], "even": [...], "handicapped": [...]}"`` (Phase 157-C+,
      the common case for multi-game summaries that mix game types)
    - ``{"all": [...]}"`` (only one game type, e.g. all-even)
    - ``[...]`` (legacy flat list — pre-Phase 157-C, still produced by
      some downstream consumers)

    Returns a Markdown bullet list of the per-bucket loss / mistake
    counts. When the input is missing or empty, returns a
    placeholder so the LLM doesn't see "no data" silently.

    Args:
        loss_progression: Whatever the summary JSON carries under
            ``loss_progression``. ``None`` is treated as missing.

    Returns:
        Markdown block content (without the section header).
    """
    if not loss_progression:
        return "(loss_progression データがありません)"

    # Normalise legacy flat-list shape.
    if isinstance(loss_progression, list):
        loss_progression = {"all": loss_progression}

    if not isinstance(loss_progression, dict) or not loss_progression:
        return "(loss_progression データがありません)"

    lines: list[str] = []
    for game_type in ("all", "even", "handicapped"):
        if game_type not in loss_progression:
            continue
        buckets = loss_progression[game_type]
        if not isinstance(buckets, list) or not buckets:
            # Phase 241-C: the game-type key exists but the bucket
            # list is empty. Surface this distinctly from "key
            # missing entirely" so the LLM knows the data shape was
            # present (rather than the section being absent).
            lines.append(f"- **{game_type}**: (空)")
            continue
        # Aggregate the per-bucket totals into a single row so the LLM
        # gets a high-level view without drowning in 30+ rows. The
        # full data is already in the injected JSON.
        total_moves = sum(int(b.get("move_count", 0) or 0) for b in buckets if isinstance(b, dict))
        total_loss = sum(float(b.get("total_loss", 0.0) or 0.0) for b in buckets if isinstance(b, dict))
        total_mistakes = sum(int(b.get("mistake_count", 0) or 0) for b in buckets if isinstance(b, dict))
        bucket_count = len(buckets)
        avg_loss = total_loss / total_moves if total_moves > 0 else 0.0
        lines.append(
            f"- **{game_type}** ({bucket_count} buckets, "
            f"{total_moves}手): 総損失={total_loss:.2f}, "
            f"avg={avg_loss:.3f}, ミス数={total_mistakes}"
        )
    return "\n".join(lines) if lines else "(loss_progression データがありません)"


def _resolve_focused_player(
    summary_json: dict[str, Any],
    configured_player: str | None,
) -> str | None:
    """Phase 228-B: pick which player to show per-player stats for.

    Selection priority:
    1. ``configured_player`` if it matches a key in ``players``
    2. ``None`` when no player was configured (bird's-eye mode — the
       section header should display "全体俯瞰" rather than auto-
       picking a player, which would be misleading to the LLM).
    3. ``None`` when no players block exists.

    Returns the resolved player name or ``None``. The returned
    ``None`` is intentional: callers render an aggregate "全体俯瞰"
    view in that case.
    """
    players = summary_json.get("players", {}) or {}
    if not isinstance(players, dict) or not players:
        return None
    if configured_player and configured_player in players:
        return configured_player
    # Birdseye: leave as None so the section header can render
    # "全体俯瞰" and the body shows a per-player overview.
    return None


def _format_player_mistakes_block(
    player_mistakes: dict[str, list[dict[str, Any]]],
    focused_player: str | None,
) -> str:
    """Phase 228-B: render the Player Mistake Distribution block.

    Renders the focused player's mistake breakdown. When
    ``focused_player`` is ``None`` (bird's-eye) or no data is available,
    a placeholder is shown so the LLM doesn't see "no data" silently.

    Args:
        player_mistakes: Output of
            :func:`extract_summary_player_mistakes` —
            ``{player_name: [{category, count, pct, avg_loss, total_loss,
            denominator}, ...], ...}``
        focused_player: The player whose stats to show. Falls back to
            "bird's-eye" label if ``None``.

    Returns:
        Markdown block content (without the section header).
    """
    if not player_mistakes:
        return (
            "(players.<name>.mistakes データがありません。"
            "Summary JSON に ``mistakes`` ブロックが無い場合はこのセクションは空です。)"
        )
    if focused_player is None or focused_player not in player_mistakes:
        # Bird's-eye or unknown player: show all players
        # (top entry per player — the most severe category).
        lines: list[str] = []
        for player_name in sorted(player_mistakes.keys()):
            entries = player_mistakes[player_name]
            if not entries:
                continue
            # Top entry is blunder (severity order from extractor)
            top = entries[0]
            pct = top.get("pct", 0.0)
            avg = top.get("avg_loss", 0.0)
            cnt = top.get("count", 0)
            denom = top.get("denominator", 0)
            lines.append(f"- **{player_name}**: top={top['category']} ({cnt}/{denom}, {pct:.1f}%, avg_loss {avg:.2f})")
        return "\n".join(lines) if lines else "(データがありません)"

    entries = player_mistakes[focused_player]
    if not entries:
        return f"({focused_player} の mistakes データが空です)"

    lines = []
    for m in entries:
        denom = m["denominator"]
        cnt = m["count"]
        pct = m["pct"]
        avg = m["avg_loss"]
        lines.append(f"- **{m['category']}**: {cnt}/{denom} ({pct:.1f}%) - avg_loss {avg:.2f}")
    return "\n".join(lines)


def _format_player_phases_block(
    player_phases: dict[str, dict[str, dict[str, Any]]],
    focused_player: str | None,
) -> str:
    """Phase 228-B: render the Player Phase Loss Distribution block.

    Renders the focused player's per-phase loss breakdown. Sort phases
    by ``total_loss`` descending so the LLM sees the worst phase first
    (the bottleneck). When ``focused_player`` is ``None`` (bird's-eye),
    shows the worst phase per player.

    Args:
        player_phases: Output of
            :func:`extract_summary_player_phase_losses` —
            ``{player_name: {phase: {moves, total_loss, avg_loss}, ...}, ...}``
        focused_player: The player whose stats to show.

    Returns:
        Markdown block content (without the section header).
    """
    if not player_phases:
        return (
            "(players.<name>.phases データがありません。"
            "Summary JSON に ``phases`` ブロックが無い場合はこのセクションは空です。)"
        )

    def _format_phase_line(label: str, data: dict[str, Any]) -> str:
        return f"- **{label}**: {data['moves']}手 / {data['total_loss']:.2f}損失 (avg {data['avg_loss']:.3f})"

    if focused_player is None or focused_player not in player_phases:
        # Bird's-eye: show the worst phase per player
        lines = []
        for player_name in sorted(player_phases.keys()):
            phases = player_phases[player_name]
            if not phases:
                continue
            worst_phase = max(phases.items(), key=lambda kv: kv[1]["total_loss"])
            data = worst_phase[1]
            lines.append(
                f"- **{player_name}** (worst phase): "
                f"phase=`{worst_phase[0]}` / "
                f"{data['moves']}手 / {data['total_loss']:.2f}損失"
            )
        return "\n".join(lines) if lines else "(データがありません)"

    phases = player_phases[focused_player]
    if not phases:
        return f"({focused_player} の phases データが空です)"

    # Sort by total_loss desc so the bottleneck is first
    sorted_phases = sorted(phases.items(), key=lambda kv: -kv[1]["total_loss"])
    return "\n".join(_format_phase_line(name, data) for name, data in sorted_phases)


# --- Phase 270: Aggregated Karte View (schema 3.5) ---


def _format_aggregated_view_block(view: AggregatedKarteView) -> str:
    """Render the Phase 270 Aggregated Karte View as a Markdown block.

    Six sub-sections, one per aggregator output. Each sub-section
    is omitted (replaced with a short "no data" marker) when its
    data is empty so the LLM does not see noisy placeholders.

    Args:
        view: An :class:`AggregatedKarteView` produced by
            :func:`aggregate_kartes`.

    Returns:
        Markdown block content (without the section header). Empty
        string when the view has no data at all.
    """
    sections: list[str] = []

    # 1. reason_tags_by_color
    rt_lines: list[str] = []
    for color in sorted(view.reason_tags_by_color.keys()):
        tags = view.reason_tags_by_color[color]
        if not tags:
            continue
        # Sort by count desc so the most frequent tag is first.
        items = sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))
        rendered = ", ".join(f"{tag}={n}" for tag, n in items)
        rt_lines.append(f"- **{color}**: {rendered}")
    sections.append(
        "#### reason_tags_by_color\n" + ("\n".join(rt_lines) if rt_lines else "(reason_tags_distribution データなし)")
    )

    # 2. area_difficulty_matrix
    matrix = view.area_difficulty_matrix
    if matrix:
        diff_keys = ("only", "hard", "normal", "easy", "unknown")
        header = "| area | " + " | ".join(diff_keys) + " |"
        sep = "|------|" + "|".join(["------"] * len(diff_keys)) + "|"
        rows: list[str] = []
        for area in ("corner", "edge", "center"):
            if area not in matrix:
                continue
            cells = [str(matrix[area].get(d, 0)) for d in diff_keys]
            rows.append(f"| {area} | " + " | ".join(cells) + " |")
        sections.append(
            "#### area_difficulty_matrix\n" + header + "\n" + sep + "\n" + ("\n".join(rows) if rows else "(データなし)")
        )
    else:
        sections.append("#### area_difficulty_matrix\n(area / position_difficulty データなし)")

    # 3. loss_spike_windows
    spikes = view.loss_spike_windows
    if spikes:
        lines = []
        for s in spikes:
            lines.append(
                f"- **{s['game_id']}**: moves {s['start_move']}-{s['end_move']} "
                f"({s['bucket_count']} buckets, total_loss={s['total_loss']:.2f}, "
                f"avg={s['avg_loss']:.3f})"
            )
        sections.append("#### loss_spike_windows\n" + "\n".join(lines))
    else:
        sections.append("#### loss_spike_windows\n(loss_progression スパイクなし)")

    # 4. representative_moves_by_tag
    rep = view.representative_moves_by_tag
    if rep:
        lines = []
        for tag, entries in rep.items():
            label = view.meaning_tag_label_map.get(tag, tag)
            parts = []
            for e in entries:
                parts.append(f"{e['coords']} #{e['move_number']} (loss={e['loss']:.2f}, {e['game_id']})")
            lines.append(f"- **{tag}** ({label}): " + "; ".join(parts))
        sections.append("#### representative_moves_by_tag\n" + "\n".join(lines))
    else:
        sections.append("#### representative_moves_by_tag\n(primary_tag 付き代表手なし)")

    # 5. data_quality_aggregate
    dq = view.data_quality_aggregate
    if dq.get("games_count", 0) > 0:
        dq_lines = [
            f"- games_count: {dq['games_count']}",
            f"- avg_visits: {dq['avg_visits']:.1f}",
            f"- reliability_pct: {dq['reliability_pct']:.1f}",
            f"- coverage_pct: {dq['coverage_pct']:.1f}",
            f"- total_moves: {dq['total_moves']}",
            f"- confidence_level: {dq['confidence_level']}",
        ]
        sections.append("#### data_quality_aggregate\n" + "\n".join(dq_lines))
    else:
        sections.append("#### data_quality_aggregate\n(data_quality データなし)")

    # 6. meaning_tag_label_map
    lbl: dict[str, str] = view.meaning_tag_label_map
    if lbl:
        lbl_items: list[tuple[str, str]] = sorted(lbl.items(), key=lambda kv: kv[0])
        rendered = ", ".join(f"{k} → {v}" for k, v in lbl_items)
        sections.append("#### meaning_tag_label_map\n" + rendered)
    else:
        sections.append("#### meaning_tag_label_map\n(マッピングデータなし)")

    return "### Aggregated Karte View (Phase 270, schema 3.5)\n\n" + "\n\n".join(sections) + "\n\n"


# --- Public API ---


def build_summary_weakness_prompt(
    summary_json: dict[str, Any],
    config: SummaryPromptConfig,
) -> SummaryPrompt:
    """Assemble a SummaryPrompt specialised for multi-game pattern extraction.

    The summary JSON is rendered verbatim (Markdown code block) and
    augmented with a pre-computed weakness patterns list and the
    ``phase_x_mistake`` buckets. The LLM is explicitly told NOT to
    invent per-move data.

    Phase 270: when ``config.kartes`` is non-empty the function
    runs the multi-karte aggregator and renders a new ``Aggregated
    Karte View (schema 3.6)`` section. The body header's ``Schema:``
    line is also bumped to ``"3.6"`` so downstream consumers can
    tell the two versions apart at a glance. Existing 3.5 callers
    (no ``kartes``) get the exact same prompt body as before.

    Args:
        summary_json: Parsed multi-game Summary JSON dict. The function
            does not verify the JSON type — callers should ensure they
            have a summary (use :func:`katrain.core.coach.is_summary`
            when in doubt).
        config: :class:`SummaryPromptConfig` with voice / mode / focus.

    Returns:
        :class:`SummaryPrompt` with ``full_markdown`` ready for the
        clipboard.
    """
    games = config.games_analyzed or extract_summary_game_count(summary_json) or 0
    patterns_all = extract_summary_weakness_patterns(summary_json)
    patterns_capped = patterns_all[: config.max_patterns] if config.max_patterns > 0 else patterns_all
    buckets = extract_summary_mistake_buckets(summary_json)
    total_loss = extract_summary_total_loss(summary_json)

    # Phase 228-B: per-player stats (Player Mistake Distribution +
    # Player Phase Loss Distribution). Resolve focus player first so
    # the helper blocks know which row to highlight.
    player_mistakes_all = extract_summary_player_mistakes(summary_json)
    player_phases_all = extract_summary_player_phase_losses(summary_json)
    focused_player = _resolve_focused_player(summary_json, config.player_name)

    # Phase 270: aggregated view from per-game kartes. When the
    # config provides any karte JSONs, run the aggregator once and
    # inject the result as a new body section. The body header's
    # ``Schema:`` line is bumped to 3.6 in that case so consumers
    # can tell the two versions apart.
    kartes_provided = bool(config.kartes)
    aggregated_view: AggregatedKarteView | None = None
    aggregated_block: str = ""
    effective_schema_version = config.schema_version
    if kartes_provided:
        aggregated_view = aggregate_kartes(config.kartes)  # type: ignore[arg-type]
        effective_schema_version = SCHEMA_VERSION_WITH_KARTES
        aggregated_block = _format_aggregated_view_block(aggregated_view)

    focus = _focus_label(config.player_name)
    rank_lbl = _rank_label(config.player_rank)
    vsummary = voice_summary(config.voice)

    # 1. System instruction
    system_instruction = _SYSTEM_INSTRUCTION_TEMPLATE.format(
        voice_summary=vsummary,
        mode_label=config.mode.name,
        games_analyzed=games,
        focus_label=focus,
        player_name=config.player_name or "",
        rank_label=rank_lbl,
    )

    # 2. Body
    body_markdown = _BODY_HEADER_TEMPLATE.format(
        schema_version=effective_schema_version,
        games_analyzed=games,
        voice_summary=vsummary,
        mode_label=config.mode.name,
        focus_label=focus,
        rank_label=rank_lbl,
        summary_json=json.dumps(summary_json, ensure_ascii=False, indent=2),
        patterns_count=len(patterns_capped),
        patterns_block=_format_patterns_block(patterns_capped),
        buckets_block=_format_buckets_block(buckets),
        loss_progression_block=_format_loss_progression_block(summary_json.get("loss_progression")),
        player_mistakes_block=_format_player_mistakes_block(player_mistakes_all, focused_player),
        player_phases_block=_format_player_phases_block(player_phases_all, focused_player),
        player_mistakes_focus=(f" ({focused_player})" if focused_player else " (全体俯瞰)"),
        player_phases_focus=(f" ({focused_player})" if focused_player else " (全体俯瞰)"),
        aggregated_view_block=aggregated_block,
    )

    # Optional total_loss annotation appended to body when available
    if total_loss is not None:
        body_markdown += f"\n> **集計総損失**: {total_loss:.1f}\n"

    full_markdown = system_instruction + body_markdown

    return SummaryPrompt(
        system_instruction=system_instruction,
        body_markdown=body_markdown,
        full_markdown=full_markdown,
        config=config,
        referenced_patterns=tuple(patterns_capped),
    )


__all__ = [
    "SummaryPromptConfig",
    "SummaryPrompt",
    "build_summary_weakness_prompt",
    "SCHEMA_VERSION_WITH_KARTES",
]
