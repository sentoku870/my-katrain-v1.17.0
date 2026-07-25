"""Phase 211: LLM prompt builder — HTML-comment-style system instruction.

Generates an LLM-ready Markdown file containing:
1. **SystemInstruction block** (HTML comment, hidden in Markdown renderers)
2. **Lexicon injection block** (HTML comment, embedded go terminology)
3. **Karte JSON body** (already produced by Phase 149-149+ json_export.py)

The HTML comment format (Phase 203 §5.3) is modelled on
``docs/archive/specs-implemented/common-improvements.md`` §2.

Why HTML comments:
- Markdown renderers (GitHub / VS Code / KaTrain's own i18n_text viewer)
  strip ``<!-- ... -->`` blocks from display
- LLMs that read the rendered text / a copy-paste see the comment content
- Users see only the Karte JSON, never the LLM instructions

Public API:
- :func:`build_translation_prompt` — assemble a complete LlmPrompt
- :func:`append_llm_prompt_block` — wrap an existing Karte JSON dict
- :func:`render_markdown` — convert an LlmPrompt to a single string

Schema impact:
- The Karte JSON schema (``report_schema_version 3.4``) is NOT modified.
- The new content lives in **separately constructed Markdown output**,
  not in the JSON. This keeps the Lv3 scope small (no existing module
  edits). A future ``Phase 211.5`` may bump ``json_export.py`` to embed
  the prompt block in-line.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from katrain.core.coach.lexicon import inject_lexicon_for_prompt
from katrain.core.coach.master_db import CoachMode, ToneVoice
from katrain.core.coach.symptom_index import (
    SymptomId,
    lookup_symptom,
)
from katrain.core.coach.tones import modes_for_voice, voice_summary

_LOG = logging.getLogger(__name__)


# --- Configuration dataclass ---


@dataclass(frozen=True)
class PromptConfig:
    """Configuration for :func:`build_translation_prompt`.

    Attributes:
        voice: Selected ToneVoice (drives both greeting tone and
            instruction strictness).
        mode: Selected CoachMode (drives language level in §0).
        detected_symptom_ids: Auto-detected SymptomId list (Phase 209).
        llm_required_symptom_ids: SymptomId list that needs LLM analysis
            (Phase 209 / §4.2 contract — included as "candidate" hints).
        max_lexicon_entries: Maximum number of lexicon entries to embed
            (Phase 203 §5.2 recommends 3-7 for token budget).
        include_expanded: When True, embed ``ja_expanded`` long-form.
        schema_version: Karte JSON schema version (informational).
        player_rank_str: User's rank string (e.g. "5k"). Optional.
        average_points_lost: Game-level avg pointsLost. Optional.
        player_color: Phase 225.6. "B" / "W" / None.
            When ``None``, the LLM is told "Unknown" so it doesn't
            assume the user's perspective. ``"B"`` / ``"W"`` are
            forwarded to the SystemInstruction so the LLM only
            references that side's weaknesses.
    """

    voice: ToneVoice
    mode: CoachMode
    detected_symptom_ids: tuple[SymptomId, ...]
    llm_required_symptom_ids: tuple[SymptomId, ...] = ()
    max_lexicon_entries: int = 7
    include_expanded: bool = True
    schema_version: str = "3.5"
    player_rank_str: str | None = None
    average_points_lost: float | None = None
    player_color: str | None = None


# --- LlmPrompt container ---


@dataclass(frozen=True)
class LlmPrompt:
    """LLM prompt bundle produced by build_translation_prompt.

    Attributes:
        system_instruction: HTML-comment-bounded instruction block.
        lex_injection: HTML-comment-bounded Lexicon snippet.
        body_markdown: The Karte JSON body (as Markdown code block).
        full_markdown: Concatenation ready to copy/paste.
        config: Echo of the input config (for downstream validation).
        referenced_symptom_ids: Symptom ids embedded as "use these".
        referenced_lexicon_ids: Lexicon ids embedded in the prompt.
    """

    system_instruction: str
    lex_injection: str
    body_markdown: str
    full_markdown: str
    config: PromptConfig
    referenced_symptom_ids: tuple[SymptomId, ...]
    referenced_lexicon_ids: tuple[str, ...]


# --- Template fragments (Phase 203 §5.3) ---


_SYSTEM_INSTRUCTION_TEMPLATE = """<!--
[SYSTEM INSTRUCTION FOR LLM]
Role: You are a Go coach. Translate the attached Karte JSON into Japanese
      coaching language.
Mode: {voice_summary}
Level: {mode_label} ({mode_description})
DetectedSymptoms: {detected_ids}
CandidateSymptoms: {candidate_ids}
PlayerColor: {player_color_label}   <!-- Phase 225.6: 'black' / 'white' / 'unknown' -->

[STRICT RULES — DO NOT VIOLATE]
1. DO NOT analyze the board independently. Use ONLY the data in the JSON.
2. DO NOT invent move numbers, coordinates, or scores. Every number must
   match the JSON.
3. Every symptom_id you mention MUST exist in the Karte JSON's
   ``weaknesses[<player_color>]``, ``important_moves[*].primary_tag``,
   or ``critical_3[<player_color>][*].meaning_tag_id`` field. When
   ``PlayerColor`` is set, focus your review on that side's
   weaknesses only.
4. Use the Lexicon definitions injected below verbatim for terminology.
5. End your response with the line
   ``参照した症状ID: [<id1>, <id2>, ...]``
   for downstream validation.

Format requirements:
- 主テーマ1つ / 副テーマ最大2つ
- 行動ルール最大3つ（それぞれトリガー / アクション / 終了条件 を含む）
- 加点診断（できていること）が1つ以上
- 内部タグ（facet等）を出力に含めない

LLM-delegated candidate symptoms (KataGo numerical data was insufficient;
consider discussing with the user):
{candidate_hints}
-->

"""

_LEXICON_INJECTION_HEADER = """<!--
[LEXICON INJECTION]
The following go terminology entries are ground truth. Use them verbatim
when discussing the symptoms below. Do not paraphrase the key terms.
Entries are listed in priority order (most relevant first).
-->
"""

_BODY_HEADER_TEMPLATE = """# myKatrain Karte (LLM-ready)

> Generated by :func:`katrain.core.coach.prompt_builder.build_translation_prompt`.
> Schema: {schema_version}
> Voice: {voice_summary}
> Level: {mode_label}

---

## Karte JSON

```json
{karte_json}
```

"""


# --- Helpers ---


def _format_symptom_id_list(ids: Iterable[SymptomId]) -> str:
    """Format symptom IDs as a stable string for the instruction header."""
    ids = sorted(set(ids), key=lambda i: i.value)
    return "[" + ", ".join(i.value for i in ids) + "]" if ids else "[]"


def _candidate_hints(llm_required_ids: tuple[SymptomId, ...]) -> str:
    """Render LLM-required symptom context_hint lines (Phase 203 §4.2)."""
    lines: list[str] = []
    for sid in llm_required_ids:
        symptom = lookup_symptom(sid)
        if symptom is None:
            continue
        lines.append(f"- ``{sid.value}`` ({symptom.ja_label}): {symptom.context_hint or '(no hint)'}")
    return "\n".join(lines) if lines else "(none)"


_PLAYER_COLOR_LABELS: dict[str | None, str] = {
    "B": "black",
    "W": "white",
    None: "unknown",
}


def _player_color_label(color: str | None) -> str:
    """Render the player_color for the SystemInstruction block."""
    return _PLAYER_COLOR_LABELS.get(color, "unknown")


def _select_lexicon_entry_ids(
    detected_ids: tuple[SymptomId, ...],
    *,
    max_count: int,
) -> tuple[str, ...]:
    """Pick lexicon ids referenced by the detected symptoms.

    Each Symptom may carry ``related_lexicon_ids`` (e.g. atari_blindness
    references ``liberty`` and ``atari``). Deduplicated and capped.
    """
    seen: list[str] = []
    seen_set: set[str] = set()
    for sid in detected_ids:
        symptom = lookup_symptom(sid)
        if symptom is None:
            continue
        for lex_id in symptom.related_lexicon_ids:
            if lex_id not in seen_set:
                seen.append(lex_id)
                seen_set.add(lex_id)
            if len(seen) >= max_count:
                break
        if len(seen) >= max_count:
            break
    return tuple(seen)


# --- Validation (Phase 226-J) ---


def validate_prompt_config(config: PromptConfig) -> list[str]:
    """Sanity-check ``PromptConfig`` consistency.

    Phase 226-J: the LLM Coach popup can produce a ``PromptConfig``
    whose ``voice`` / ``mode`` / ``detected_symptom_ids`` are internally
    inconsistent (e.g. ``voice=TOMOKO_STRICT`` against ``mode=BEGINNER``).
    Instead of silently feeding the LLM a broken instruction, we surface
    the inconsistencies as a list of human-readable warnings so the
    caller can log / display them.

    Phase 269: after AYAKA removal the BEGINNER/INTERMEDIATE modes
    are now served by TOMOKO, so the previously-buggy
    ``voice=TOMOKO + mode=BEGINNER`` combo no longer fires. The check
    is still useful for the remaining TOMOKO_STRICT-only mismatch
    (e.g. voice=TOMOKO + mode=EXPERT).

    Returns:
        List of warning strings (Japanese). Empty list = no issues.

    Note:
        This function never raises. The validator is advisory — the
        caller may still proceed with a sub-optimal config (e.g. when
        the user has explicitly chosen ``mode=BEGINNER`` but the karte
        contains an EXPERT symptom).
    """
    warnings: list[str] = []
    # 1) voice / mode consistency: every mode served by the voice must
    #    include ``config.mode``. Otherwise the LLM is being asked to
    #    speak in TOMOKO's strict voice while the prompt was prepared
    #    for BEGINNER kids — the §1-3 Kansai dictionary will be wrong.
    allowed_modes = modes_for_voice(config.voice)
    if allowed_modes and config.mode not in allowed_modes:
        warnings.append(
            f"voice={config.voice.value} は mode={config.mode.name} を担当しません。"
            f"想定モード: {', '.join(m.name for m in allowed_modes)}"
        )

    # 2) symptom / mode consistency: each detected symptom has a
    #    ``difficulty_range`` (min_mode, max_mode). If ``config.mode``
    #    is outside the range, the symptom is technically out of scope
    #    for the configured coach level.
    mode_order = list(CoachMode)
    try:
        mode_idx = mode_order.index(config.mode)
    except ValueError:
        mode_idx = -1

    for sid in config.detected_symptom_ids:
        symptom = lookup_symptom(sid)
        if symptom is None:
            continue
        lo = mode_order.index(symptom.difficulty_range[0])
        hi = mode_order.index(symptom.difficulty_range[1])
        if mode_idx < 0 or mode_idx < lo or mode_idx > hi:
            warnings.append(
                f"症状 '{sid.value}' は mode={config.mode.name} の範囲外です。"
                f"想定範囲: {symptom.difficulty_range[0].name}〜{symptom.difficulty_range[1].name}"
            )
    return warnings


# --- Public API ---


def build_translation_prompt(
    karte_json: dict[str, Any],
    config: PromptConfig,
) -> LlmPrompt:
    """Assemble a complete LlmPrompt from a Karte JSON dict + PromptConfig.

    The Karte JSON is rendered as a Markdown JSON code block (preserving
    its raw structure). The system instruction and lexicon injection are
    placed in HTML comments above and below the body.

    Phase 226-J: runs ``validate_prompt_config`` first and logs any
    warnings at WARNING level. The warnings are intentionally advisory
    — the LLM still receives a (potentially sub-optimal) prompt. Callers
    that want to surface these to the user should call
    ``validate_prompt_config`` directly and display the result.

    Args:
        karte_json: Output of :func:`katrain.core.reports.karte.json_export.build_karte_json`.
        config: PromptConfig with voice / mode / symptoms / preferences.

    Returns:
        LlmPrompt with full_markdown ready for clipboard copy.
    """
    # Phase 226-J: log voice / mode / symptom consistency warnings
    # without aborting. The popup / CLI caller can also call
    # ``validate_prompt_config`` to surface these to the user.
    for warning in validate_prompt_config(config):
        _LOG.warning("PromptConfig inconsistency: %s", warning)
    detected_ids = tuple(config.detected_symptom_ids)
    candidate_ids = tuple(config.llm_required_symptom_ids)

    voice = config.voice
    mode = config.mode

    # 1. System instruction (HTML comment with strict rules + Mode info).
    system_instruction = _SYSTEM_INSTRUCTION_TEMPLATE.format(
        voice_summary=voice_summary(voice),
        mode_label=mode.name,
        mode_description=(lookup_mode_description(mode)),
        detected_ids=_format_symptom_id_list(detected_ids),
        candidate_ids=_format_symptom_id_list(candidate_ids),
        candidate_hints=_candidate_hints(candidate_ids),
        player_color_label=_player_color_label(config.player_color),
    )

    # 2. Lexicon injection (HTML comment with verbatim entries).
    lex_ids = _select_lexicon_entry_ids(
        detected_ids,
        max_count=config.max_lexicon_entries,
    )
    lex_body = inject_lexicon_for_prompt(
        lex_ids,
        include_expanded=config.include_expanded,
    )
    lex_injection = (
        _LEXICON_INJECTION_HEADER + "\n" + lex_body
        if lex_body
        else "<!-- [LEXICON INJECTION] (no entries selected) -->\n"
    )

    # 3. Body markdown.
    body_markdown = _BODY_HEADER_TEMPLATE.format(
        schema_version=config.schema_version,
        voice_summary=voice_summary(voice),
        mode_label=mode.name,
        karte_json=json.dumps(karte_json, ensure_ascii=False, indent=2),
    )

    # 4. Concatenate.
    full_markdown = system_instruction + lex_injection + body_markdown

    return LlmPrompt(
        system_instruction=system_instruction,
        lex_injection=lex_injection,
        body_markdown=body_markdown,
        full_markdown=full_markdown,
        config=config,
        referenced_symptom_ids=detected_ids,
        referenced_lexicon_ids=lex_ids,
    )


def append_llm_prompt_block(
    karte_json: dict[str, Any],
    config: PromptConfig,
) -> dict[str, Any]:
    """Return a copy of ``karte_json`` with an ``__llm_prompt__`` extra key.

    This is a non-invasive integration helper: it does NOT mutate the
    Karte JSON schema. The LLM prompt is stored as a sibling key that
    downstream consumers can ignore without breaking.

    Note:
        This is preferred over editing ``json_export.py`` directly because
        it preserves the canonical schema hash (Phase 158-I) and avoids
        the Lv3 risk of breaking downstream test goldens.
    """
    prompt = build_translation_prompt(karte_json, config)
    out = dict(karte_json)
    out["__llm_prompt__"] = {
        "full_markdown": prompt.full_markdown,
        "referenced_symptom_ids": [s.value for s in prompt.referenced_symptom_ids],
        "referenced_lexicon_ids": list(prompt.referenced_lexicon_ids),
    }
    return out


def render_markdown(prompt: LlmPrompt) -> str:
    """Return the full Markdown text for clipboard use."""
    return prompt.full_markdown


# --- Internal helper that needs the master_db CoachMode.description ---


def lookup_mode_description(mode: CoachMode) -> str:
    """Return short Japanese description for the mode.

    Avoids importing master_db at module load to keep cycles low; we
    inline the lookup here.
    """
    from katrain.core.coach.master_db import get_mode_config

    cfg = get_mode_config(mode)
    return cfg.description_jp


__all__ = [
    "PromptConfig",
    "LlmPrompt",
    "build_translation_prompt",
    "append_llm_prompt_block",
    "render_markdown",
    "lookup_mode_description",
    "validate_prompt_config",  # Phase 226-J
]
