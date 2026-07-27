"""Phase 227-B: LLM output validator for multi-game Summary JSON.

Companion to :mod:`katrain.core.coach.llm_validator`, specialised for
the **multi-game summary** use-case. The Karte validator (Phase 212)
checks per-move data; this validator instead checks **pattern-level**
claims, since summary JSONs do not have ``important_moves`` /
``pointsLost`` / per-game move numbers.

Why a separate module:
- Summary JSONs have NO per-move data. The Karte validator's move-number
  range check would flag every legitimate mention of "N局" (game count)
  or aggregate stats as a false positive.
- The LLM contract differs:
  - Must end with ``抽出した弱点パターン: [...]`` (pattern list)
  - Should NOT invent specific move numbers or game IDs
  - Patterns must come from ``weaknesses[*][*].category``
  - Phases must be in ``{opening, middle, endgame}``
  - Maximum 3 patterns (per the Phase 227-A system instruction)

Severity choices (Phase 227-B §3):
- HIGH: pattern category not in summary, specific move number mentioned
- MEDIUM: phase label outside the standard set, pattern count > 3
- LOW: specific game ID mentioned (e.g. ``g1``), tone inconsistencies

Public API:
- :class:`SummaryValidationReport`
- :func:`validate_summary_llm_output`

Kivy-free. Safe to invoke from CLI / CI / GUI (lazy import).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from katrain.core.coach.llm_validator import (
    _LEXICON_MENTION_RE,  # noqa: F401  (re-exported for test introspection)
    ValidationIssue,
    ValidationSeverity,
)
from katrain.core.coach.summary_prompt_builder import SummaryPrompt

# Phase 269: ToneVoice / has_kansai_markers import removed (AYAKA voice
# gone; tone consistency check deleted).

# --- Constants ---


# Phase 227-B: maximum number of weakness patterns the LLM is allowed
# to extract. The system instruction explicitly says "Maximum 3
# patterns". When the LLM lists more, that's a MEDIUM severity finding
# (the validator is advisory — extra patterns are not wrong, just
# outside the contract).
MAX_PATTERNS = 3

# Phase 227-B: standard phase labels.
_VALID_PHASES: frozenset[str] = frozenset({"opening", "middle", "endgame"})


# --- Regex patterns ---


# Phase 227-B: trailing pattern-list contract line.
# Allow Chinese / English / Japanese variants for flexibility:
#   抽出した弱点パターン: [a, b, c]
#   ExtractedPatterns: [a, b, c]
#   弱点パターン: [a, b, c]
#
# PR-02 (S1): exclude angle-bracket placeholders (`<category1>` etc.)
# so the prompt's template row never matches. The Phase 203 spec only
# ships snake_case / kebab-case ids (atari_blindness, endgame_slip,
# opening / middle / endgame phases), so restricting to
# non-bracket / non-comma characters is safe for legitimate answers.
_PATTERN_LIST_LINE_RE = re.compile(
    r"""
    (?:抽出した弱点パターン|弱点パターン|抽出パターン|ExtractedPatterns?|WeaknessPatterns?)
    \s*[:：=]\s*
    \[
    ([^\[\]<>]+?)           # captured: id list (no placeholders)
    \]
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# Phase 227-B: optional phase-list contract line.
# PR-02 (S1): same placeholder exclusion as the pattern regex above.
_PHASE_LIST_LINE_RE = re.compile(
    r"""
    (?:参照したphase|参照phase|PhasesReferenced|Phases)
    \s*[:：=]\s*
    \[
    ([^\[\]<>]+?)
    \]
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# Phase 229: per-game move number patterns for SUMMARY mode.
# Tighter than the Karte validator's regex (which intentionally allows
# bare "X手"). The Karte validator wants to catch any per-move reference
# even when written as bare "30手", but in summary mode the same pattern
# is ambiguous: "全388手中51手（13.1%）" is a *count* of moves, not a
# reference to move #51. Catching every "X手" produces false positives
# on every statistical phrase the LLM writes.
#
# The summary validator therefore restricts the regex to patterns that
# are unambiguous move references in Japanese:
#   - "#50" / "move 50"   (English-style)
#   - "50手目"            (move #50 with explicit 目 suffix)
#   - "着手 50"           (move #50)
#   - "50番"              (move #50, less common)
#   - "第50手"            (move #50 with 第 prefix)
#
# Bare "X手" is intentionally excluded. In summary mode the LLM is
# instructed to write phase+category only, so any genuine per-move
# reference should use one of the explicit markers above. The Karte
# validator keeps the bare "X手" alternative because Karte output
# naturally references specific moves.
_SUMMARY_MOVE_NUMBER_RE = re.compile(
    r"(?:"
    r"(?:#|move\s+)(\d{1,3})"  # "#50", "move 50"
    r"|(\d{1,3})\s*手目"  # "50手目"
    r"|着手\s*(\d{1,3})"  # "着手 50"
    r"|(\d{1,3})\s*番"  # "50番"
    r"|第\s*(\d{1,3})\s*手"  # "第50手"
    r")",
    re.IGNORECASE,
)

# Backwards-compatibility alias — keeps the original name in case any
# downstream introspection still references it. New code should use
# ``_SUMMARY_MOVE_NUMBER_RE`` directly.
_MOVE_NUMBER_RE = _SUMMARY_MOVE_NUMBER_RE

# Phase 227-B: detect specific game ID references. Game IDs in
# summary JSON take the form ``g1``, ``g2`` (or ``game_1``). When
# the LLM cites a specific game like "g3で起きた" it is fabricating
# data — LOW severity because it's not a contract violation but a
# quality concern.
_GAME_ID_RE = re.compile(
    r"\b(game[_-]?\d+|g\d+)\b",
    re.IGNORECASE,
)


# --- Summary JSON ground truth extraction ---


# Phase 228-C: standard mistake categories that appear in
# ``players.<name>.mistakes``. The validator accepts these as valid
# weakness pattern categories when the summary uses Shape B
# (``summary_json_export.py``-style per-player mistakes block).
_STANDARD_MISTAKE_CATEGORIES: frozenset[str] = frozenset(
    {
        "good",
        "inaccuracy",
        "mistake",
        "blunder",
    }
)


def _summary_available_categories(summary_json: dict[str, Any]) -> set[str]:
    """Return the set of valid ``category`` values for the summary.

    Phase 227-B: looked only at ``weaknesses[*].category`` (Shape A).

    Phase 228-C: also recognises the Shape B export where each player
    has a ``players.<name>.mistakes`` block with the standard 4
    categories (``good`` / ``inaccuracy`` / ``mistake`` / ``blunder``).
    When the summary uses Shape B we add those 4 categories to the
    valid set so the LLM can reference them without triggering
    ``unknown_pattern_category`` warnings.

    Note:
        The 4 standard categories are added unconditionally for
        Shape B because every Shape B summary has them by
        construction. Adding categories that don't actually
        appear in the JSON would still be wrong, so we only do this
        when at least one ``players.<name>.mistakes`` block exists.
    """
    out: set[str] = set()

    # Shape A: top-level weaknesses[*].category
    weaknesses = summary_json.get("weaknesses", {}) or {}
    if isinstance(weaknesses, dict):
        for color_list in weaknesses.values():
            if not isinstance(color_list, list):
                continue
            for w in color_list:
                if isinstance(w, dict):
                    cat = w.get("category")
                    if cat:
                        out.add(str(cat))

    # Shape B: players.<name>.mistakes.{good,inaccuracy,mistake,blunder}
    players = summary_json.get("players", {}) or {}
    shape_b_has_mistakes = False
    if isinstance(players, dict):
        for player_block in players.values():
            if not isinstance(player_block, dict):
                continue
            mistakes = player_block.get("mistakes")
            if isinstance(mistakes, dict) and mistakes:
                shape_b_has_mistakes = True
                # Include any explicit categories that were actually
                # present (defensive — the 4 standard ones are added
                # below, but custom categorisations should also count).
                for cat in mistakes:
                    if isinstance(cat, str) and cat:
                        out.add(cat)

    # When Shape B is in use, the 4 standard mistake categories are
    # always valid (the summary's mistake distribution always uses
    # these keys, even if a specific player's count for that
    # category is 0).
    if shape_b_has_mistakes:
        out |= _STANDARD_MISTAKE_CATEGORIES

    return out


# Phase 228-C: standard phase labels that appear in
# ``players.<name>.phases``. The validator accepts these as valid
# when the summary uses Shape B.
_STANDARD_PHASE_LABELS: frozenset[str] = frozenset(
    {
        "opening",
        "middle",
        "endgame",
    }
)


def _summary_available_phases(summary_json: dict[str, Any]) -> set[str]:
    """Return the set of valid ``phase`` values for the summary.

    Phase 227-B: looked only at ``weaknesses[*].phase`` (Shape A).

    Phase 228-C: also recognises the Shape B export where each player
    has a ``players.<name>.phases`` block with the standard 3 phase
    labels (``opening`` / ``middle`` / ``endgame``). When Shape B is
    in use those 3 phase labels are always added to the valid set
    (the phases block is part of the Shape B schema by construction,
    so the LLM can reference any of the 3 standard labels without
    triggering ``phase_label_out_of_set`` warnings).
    """
    out: set[str] = set()

    # Shape A: top-level weaknesses[*].phase
    weaknesses = summary_json.get("weaknesses", {}) or {}
    if isinstance(weaknesses, dict):
        for color_list in weaknesses.values():
            if not isinstance(color_list, list):
                continue
            for w in color_list:
                if isinstance(w, dict):
                    ph = w.get("phase")
                    if ph:
                        out.add(str(ph).lower())

    # Shape B: players.<name>.phases.{opening,middle,endgame}
    # The 3 standard phase labels are added when any player has
    # a non-empty phases block. The Phase 228-B prompt renders
    # the Player Phase Loss Distribution section for any
    # player that has the block, so the LLM is justified in
    # citing any of the 3 standard labels.
    players = summary_json.get("players", {}) or {}
    shape_b_has_phases = False
    if isinstance(players, dict):
        for player_block in players.values():
            if not isinstance(player_block, dict):
                continue
            phases = player_block.get("phases")
            if isinstance(phases, dict) and phases:
                shape_b_has_phases = True

    if shape_b_has_phases:
        out |= _STANDARD_PHASE_LABELS

    return out


# --- LLM text parsing ---


def _split_id_list(raw: str) -> tuple[str, ...]:
    """Split an id list on commas / whitespace / Japanese separators."""
    parts = re.split(r"[\s,、，]+", raw)
    return tuple(p.strip().strip("[]「」") for p in parts if p.strip())


def _extract_pattern_categories(text: str) -> tuple[str, ...]:
    """Extract the trailing ``抽出した弱点パターン: [...]`` line.

    PR-02 (S1): when the user pastes the prompt + LLM answer together
    the first match of the pattern line is the prompt's template row
    (``<category1>``, ``<category2>``), which then validates the
    placeholder values instead of the actual answer. Take the LAST
    match instead — same strategy the karte validator adopted in
    Phase 272 (see ``llm_validator.py`` ``_extract_referenced_ids``).
    """
    matches = list(_PATTERN_LIST_LINE_RE.finditer(text))
    if not matches:
        return ()
    return _split_id_list(matches[-1].group(1))


def _extract_referenced_phases(text: str) -> tuple[str, ...]:
    """Extract the optional ``参照したphase: [...]`` line.

    PR-02 (S1): same last-match rationale as
    :func:`_extract_pattern_categories`.
    """
    matches = list(_PHASE_LIST_LINE_RE.finditer(text))
    if not matches:
        return ()
    return _split_id_list(matches[-1].group(1))


def _extract_move_numbers(text: str) -> tuple[int, ...]:
    """Phase 227-B: detect per-move references in the LLM text.

    For summary mode, ANY match is a HIGH severity finding because
    the summary has no per-move data — the LLM is fabricating.

    Phase 229: switched from the Karte regex (``_MOVE_NUMBER_RE``) to
    the summary-only ``_SUMMARY_MOVE_NUMBER_RE``. The Karte regex
    intentionally matches bare ``"50手"`` as a move reference, but in
    summary mode the same string is ambiguous with the *count* pattern
    ``"全388手中51手（13.1%）"``. The summary regex drops the bare "X手"
    alternative and accepts only explicit move markers (第/手目/#/move/
    着手/番). The loop still iterates groups 1–6 for safety (5 of 6
    are populated after the change; remaining slots are simply ``None``).
    """
    out: list[int] = []
    for m in _SUMMARY_MOVE_NUMBER_RE.finditer(text):
        for grp in range(1, 7):
            raw = m.group(grp)
            if raw is None:
                continue
            try:
                v = int(raw)
                if 0 < v <= 999:
                    out.append(v)
                break
            except (ValueError, TypeError):
                continue
    return tuple(out)


def _extract_game_id_references(text: str) -> tuple[str, ...]:
    """Phase 227-B: detect specific game ID references (e.g. ``g1``)."""
    if not text:
        return ()
    seen: set[str] = set()
    out: list[str] = []
    for m in _GAME_ID_RE.finditer(text):
        gid = m.group(1)
        if gid and gid.lower() not in seen:
            out.append(gid)
            seen.add(gid.lower())
    return tuple(out)


def _extract_phases_from_prose(text: str) -> tuple[str, ...]:
    """Phase 227-B: detect phase labels (opening / middle / endgame)
    mentioned in prose form anywhere in the LLM text.

    Returns the deduplicated set of phase labels found, ordered by
    their **first occurrence** in the text (more intuitive for the
    validator report than iterating the standard phase set). Used for
    the 'phase_labels_out_of_set' check (a separate validation from
    the trailing ``参照したphase`` contract line).

    Note:
        The regex is intentionally lenient on the right side
        (``(?<![A-Za-z])`` only) so plural forms like ``openings``
        also match. This mirrors the karte validator's leniency for
        similar terms.
    """
    if not text:
        return ()

    # Collect (position, label) pairs in text order.
    matches: list[tuple[int, str]] = []
    for label in _VALID_PHASES:
        for m in re.finditer(rf"(?<![A-Za-z]){label}", text, re.IGNORECASE):
            matches.append((m.start(), label))
    matches.sort(key=lambda x: x[0])

    # Dedupe while preserving text order.
    seen: set[str] = set()
    out: list[str] = []
    for _, label in matches:
        if label not in seen:
            out.append(label)
            seen.add(label)
    return tuple(out)


# --- Validation report ---


@dataclass(frozen=True)
class SummaryValidationReport:
    """Aggregate validation result for a multi-game Summary LLM response.

    Attributes:
        llm_text: Original LLM text (echo for downstream UI).
        issues: Tuple of ValidationIssue. Empty = no issues found.
        referenced_categories: Categories the LLM claimed to extract
            (from the trailing contract line).
        referenced_phases: Phases the LLM mentioned (contract line
            + prose extraction, deduped).
        referenced_move_numbers: Per-move numbers the LLM cited.
            When non-empty, the validator flagged them as HIGH.
        referenced_game_ids: Game IDs the LLM cited.
            When non-empty, the validator flagged them as LOW.
        referenced_lexicon_ids: Lexicon ids the LLM used inside
            「」 brackets, restricted to the injected subset.
    """

    llm_text: str
    issues: tuple[ValidationIssue, ...] = ()
    referenced_categories: tuple[str, ...] = ()
    referenced_phases: tuple[str, ...] = ()
    referenced_move_numbers: tuple[int, ...] = ()
    referenced_game_ids: tuple[str, ...] = ()
    referenced_lexicon_ids: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.LOW)

    def summary_line(self) -> str:
        """One-line Japanese summary for UI display."""
        if self.is_clean:
            return "✅ 検証クリア — LLM 出力に問題なし"
        parts: list[str] = []
        if self.high_count:
            parts.append(f"高: {self.high_count}")
        if self.medium_count:
            parts.append(f"中: {self.medium_count}")
        if self.low_count:
            parts.append(f"低: {self.low_count}")
        return "⚠️ 検証警告 (" + ", ".join(parts) + ")"


# --- Public API ---


def validate_summary_llm_output(
    llm_text: str,
    summary_json: dict[str, Any],
    prompt: SummaryPrompt,
) -> SummaryValidationReport:
    """Validate ``llm_text`` against a multi-game Summary JSON + prompt.

    Checks (Phase 227-B §3, priority order):
    1. Pattern category existence (HIGH if not in summary)
    2. Per-move number references (HIGH — summary has no per-move data)
    3. Pattern count > MAX_PATTERNS (MEDIUM)
    4. Phase labels outside the standard set (MEDIUM)
    5. Specific game ID references (LOW)
    6. Tone consistency (LOW)

    Args:
        llm_text: LLM-generated response text.
        summary_json: Summary JSON that was sent to the LLM (ground truth).
        prompt: The :class:`SummaryPrompt` that was generated (for
            config echo and future lexicon cross-ref).

    Returns:
        :class:`SummaryValidationReport` with all issues found. Caller
        is responsible for rendering — this function never raises.
    """
    issues: list[ValidationIssue] = []
    available_categories = _summary_available_categories(summary_json)
    available_phases = _summary_available_phases(summary_json)

    # PR-02 (S6): surface a LOW warning when neither the
    # ``抽出した弱点パターン`` contract line nor the ``参照したphase`` line
    # is present. Without these, rules 1 and 3 below operate on an empty
    # set and the answer would silently pass even if the LLM completely
    # ignored the contract.
    referenced_cats = _extract_pattern_categories(llm_text)
    referenced_phases = _extract_referenced_phases(llm_text)
    if not referenced_cats and not referenced_phases:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.LOW,
                kind="missing_contract_line",
                message=(
                    "出力契約「抽出した弱点パターン: [...]」「参照したphase: [...]」"
                    "のどちらも検出されません。検証は実質スキップされています"
                ),
                context={},
            )
        )

    # ---- 1. Pattern category existence ----
    for cat in referenced_cats:
        if available_categories and cat not in available_categories:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    kind="unknown_pattern_category",
                    message=(f"弱点パターン '{cat}' は Summary JSON の weaknesses[*].category に存在しません"),
                    context={"category": cat},
                )
            )

    # ---- 2. Per-move number references (forbidden in summary mode) ----
    referenced_moves = _extract_move_numbers(llm_text)
    for n in referenced_moves:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.HIGH,
                kind="forbidden_move_number",
                message=(
                    f"着手番号 {n} が検出されました。"
                    f"サマリモードでは着手番号は存在しないため、"
                    f"phase+category パターンとして記述してください"
                ),
                context={"move_number": n},
            )
        )

    # ---- 3. Pattern count check ----
    if len(referenced_cats) > MAX_PATTERNS:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.MEDIUM,
                kind="too_many_patterns",
                message=(f"弱点パターンが {len(referenced_cats)} 件抽出されました。最大 {MAX_PATTERNS} 件が想定です"),
                context={"count": len(referenced_cats), "max": MAX_PATTERNS},
            )
        )

    # ---- 4. Phase label cross-check ----
    # Trailing contract line first (most authoritative). The function
    # was already called above for the PR-02 (S6) missing-contract
    # warning; reuse the cached result to avoid duplicate regex work.
    prose_phases = _extract_phases_from_prose(llm_text)
    referenced_phases_final: list[str] = []
    seen_phases: set[str] = set()
    for p in list(referenced_phases) + list(prose_phases):
        p_lower = p.lower()
        if p_lower not in seen_phases:
            referenced_phases_final.append(p_lower)
            seen_phases.add(p_lower)

    if available_phases:
        for phase in referenced_phases_final:
            if phase not in available_phases:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        kind="phase_label_out_of_set",
                        message=(f"phase '{phase}' は Summary の weaknesses[*].phase に存在しません"),
                        context={"phase": phase},
                    )
                )

    # ---- 5. Specific game ID references ----
    referenced_game_ids = _extract_game_id_references(llm_text)
    for gid in referenced_game_ids:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.LOW,
                kind="specific_game_id_referenced",
                message=(
                    f"特定ゲーム ID '{gid}' が参照されています。"
                    f"サマリモードでは局を特定せず、傾向として記述してください"
                ),
                context={"game_id": gid},
            )
        )

    # ---- 6. Tone consistency ----
    # Phase 269: tone-consistency check removed (AYAKA voice gone,
    # TOMOKO / TOMOKO_STRICT no longer warn on Kansai particles).

    return SummaryValidationReport(
        llm_text=llm_text,
        issues=tuple(issues),
        referenced_categories=referenced_cats,
        referenced_phases=tuple(referenced_phases_final),
        referenced_move_numbers=referenced_moves,
        referenced_game_ids=referenced_game_ids,
        referenced_lexicon_ids=(),
    )


__all__ = [
    "SummaryValidationReport",
    "validate_summary_llm_output",
    "MAX_PATTERNS",
]
