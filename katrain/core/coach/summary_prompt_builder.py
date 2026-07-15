"""Phase 227-A: LLM prompt builder for multi-game Summary JSON.

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
    extract_summary_total_loss,
    extract_summary_weakness_patterns,
)
from katrain.core.coach.master_db import CoachMode
from katrain.core.coach.tones import ToneVoice, voice_summary

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
        max_patterns: Cap on the number of pre-computed weakness
            patterns injected into the prompt body. Defaults to 10.
    """

    voice: ToneVoice
    mode: CoachMode
    games_analyzed: int
    player_name: str | None = None
    player_rank: str | None = None
    schema_version: str = "3.4"
    max_patterns: int = 10


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
Focus: {focus_label}   <!-- '{player_name}' or '全体俯瞰 (bird's-eye)' -->
Rank: {rank_label}

[STRICT RULES — DO NOT VIOLATE]
1. DO NOT analyze the board independently. Use ONLY the aggregated data
   in the Summary JSON. There is no per-move information available.
2. DO NOT invent specific move numbers, coordinates, or game IDs.
   Reference patterns by phase (opening/middle/endgame) + category.
3. Every weakness pattern you cite MUST come from the injected
   ``weakness_patterns`` list or the ``weaknesses[<color>]`` block in
   the JSON. Do not invent new categories.
4. For each pattern, state:
   - 弱点名 (category)
   - 該当phase (opening/middle/endgame)
   - 頻度 (X / N局, X%) — use the injected ``frequency_ratio`` field
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

### Weakness Patterns (pre-computed, top {patterns_count})

{patterns_block}

### Phase × Mistake Buckets

{buckets_block}

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
    """Render the weakness patterns as a numbered Markdown list."""
    if not patterns:
        return "(weakness データが見つかりませんでした。Summary JSON の ``weaknesses`` ブロックを確認してください。)"
    lines: list[str] = []
    for i, p in enumerate(patterns, start=1):
        freq_pct = p.get("frequency_ratio", 0.0) * 100.0
        lines.append(
            f"{i}. **{p['category']}** / phase=`{p['phase']}` / "
            f"color=`{p['color']}` / count={p['count']} / "
            f"頻度={freq_pct:.1f}% / 総損失={p['total_loss']:.1f}"
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
        schema_version=config.schema_version,
        games_analyzed=games,
        voice_summary=vsummary,
        mode_label=config.mode.name,
        focus_label=focus,
        rank_label=rank_lbl,
        summary_json=json.dumps(summary_json, ensure_ascii=False, indent=2),
        patterns_count=len(patterns_capped),
        patterns_block=_format_patterns_block(patterns_capped),
        buckets_block=_format_buckets_block(buckets),
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
]
