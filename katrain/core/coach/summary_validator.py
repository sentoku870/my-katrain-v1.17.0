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
from katrain.core.coach.tones import ToneVoice, has_kansai_markers

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
_PATTERN_LIST_LINE_RE = re.compile(
    r"""
    (?:抽出した弱点パターン|弱点パターン|抽出パターン|ExtractedPatterns?|WeaknessPatterns?)
    \s*[:：=]\s*
    \[
    (.*?)                  # captured: id list
    \]
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# Phase 227-B: optional phase-list contract line.
_PHASE_LIST_LINE_RE = re.compile(
    r"""
    (?:参照したphase|参照phase|PhasesReferenced|Phases)
    \s*[:：=]\s*
    \[
    (.*?)
    \]
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# Phase 227-B: per-game move number patterns. The same regex as the
# Karte validator; here any match is a HIGH severity finding because
# the summary has no per-move data.
_MOVE_NUMBER_RE = re.compile(
    r"(?:"
    r"(?:#|move\s+)(\d{1,3})"               # "#50", "move 50"
    r"|(\d{1,3})\s*手目"                     # "50手目"
    r"|(\d{1,3})(?=\s*手(?![\u4e00-\u9fff]))"  # "50手" (not followed by a CJK char)
    r"|着手\s*(\d{1,3})"                     # "着手 50"
    r"|(\d{1,3})\s*番"                       # "50番"
    r"|第\s*(\d{1,3})\s*手"                  # "第50手"
    r")",
    re.IGNORECASE,
)

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


def _summary_available_categories(summary_json: dict[str, Any]) -> set[str]:
    """Return the set of ``category`` values that exist in any weakness."""
    out: set[str] = set()
    weaknesses = summary_json.get("weaknesses", {}) or {}
    if not isinstance(weaknesses, dict):
        return out
    for color_list in weaknesses.values():
        if not isinstance(color_list, list):
            continue
        for w in color_list:
            if isinstance(w, dict):
                cat = w.get("category")
                if cat:
                    out.add(str(cat))
    return out


def _summary_available_phases(summary_json: dict[str, Any]) -> set[str]:
    """Return the set of ``phase`` values that exist in any weakness."""
    out: set[str] = set()
    weaknesses = summary_json.get("weaknesses", {}) or {}
    if not isinstance(weaknesses, dict):
        return out
    for color_list in weaknesses.values():
        if not isinstance(color_list, list):
            continue
        for w in color_list:
            if isinstance(w, dict):
                ph = w.get("phase")
                if ph:
                    out.add(str(ph).lower())
    return out


# --- LLM text parsing ---


def _split_id_list(raw: str) -> tuple[str, ...]:
    """Split an id list on commas / whitespace / Japanese separators."""
    parts = re.split(r"[\s,、，]+", raw)
    return tuple(p.strip().strip("[]「」") for p in parts if p.strip())


def _extract_pattern_categories(text: str) -> tuple[str, ...]:
    """Extract the trailing ``抽出した弱点パターン: [...]`` line."""
    m = _PATTERN_LIST_LINE_RE.search(text)
    if m is None:
        return ()
    return _split_id_list(m.group(1))


def _extract_referenced_phases(text: str) -> tuple[str, ...]:
    """Extract the optional ``参照したphase: [...]`` line."""
    m = _PHASE_LIST_LINE_RE.search(text)
    if m is None:
        return ()
    return _split_id_list(m.group(1))


def _extract_move_numbers(text: str) -> tuple[int, ...]:
    """Phase 227-B: detect per-move references in the LLM text.

    For summary mode, ANY match is a HIGH severity finding because
    the summary has no per-move data — the LLM is fabricating.
    """
    out: list[int] = []
    for m in _MOVE_NUMBER_RE.finditer(text):
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

    # ---- 1. Pattern category existence ----
    referenced_cats = _extract_pattern_categories(llm_text)
    for cat in referenced_cats:
        if available_categories and cat not in available_categories:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    kind="unknown_pattern_category",
                    message=(
                        f"弱点パターン '{cat}' は Summary JSON の "
                        f"weaknesses[*].category に存在しません"
                    ),
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
                message=(
                    f"弱点パターンが {len(referenced_cats)} 件抽出されました。"
                    f"最大 {MAX_PATTERNS} 件が想定です"
                ),
                context={"count": len(referenced_cats), "max": MAX_PATTERNS},
            )
        )

    # ---- 4. Phase label cross-check ----
    # Trailing contract line first (most authoritative).
    contract_phases = _extract_referenced_phases(llm_text)
    prose_phases = _extract_phases_from_prose(llm_text)
    referenced_phases: list[str] = []
    seen_phases: set[str] = set()
    for p in list(contract_phases) + list(prose_phases):
        p_lower = p.lower()
        if p_lower not in seen_phases:
            referenced_phases.append(p_lower)
            seen_phases.add(p_lower)

    if available_phases:
        for phase in referenced_phases:
            if phase not in available_phases:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        kind="phase_label_out_of_set",
                        message=(
                            f"phase '{phase}' は Summary の "
                            f"weaknesses[*].phase に存在しません"
                        ),
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
    # Note: lexicon cross-ref is intentionally a no-op in summary mode
    # because SummaryPromptConfig does not inject lexicon (Phase 227-A).
    # The structure is preserved for the future extension.
    cfg = prompt.config
    if cfg is not None:
        if cfg.voice == ToneVoice.AYAKA and not has_kansai_markers(llm_text):
            if len(llm_text) > 200:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.LOW,
                        kind="tone_inconsistency_ayaka",
                        message=(
                            "AYAKA 文体が指定されましたが、関西弁マーカーが見当たりません"
                        ),
                        context={"voice": cfg.voice.value},
                    )
                )
        elif (
            cfg.voice in (ToneVoice.TOMOKO, ToneVoice.TOMOKO_STRICT)
            and has_kansai_markers(llm_text)
        ):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.LOW,
                    kind="tone_inconsistency_tomoko",
                    message=(
                        f"{cfg.voice.value} 文体に AYAKA 関西弁マーカーが見られます"
                    ),
                    context={"voice": cfg.voice.value},
                )
            )

    return SummaryValidationReport(
        llm_text=llm_text,
        issues=tuple(issues),
        referenced_categories=referenced_cats,
        referenced_phases=tuple(referenced_phases),
        referenced_move_numbers=referenced_moves,
        referenced_game_ids=referenced_game_ids,
        referenced_lexicon_ids=(),
    )


__all__ = [
    "SummaryValidationReport",
    "validate_summary_llm_output",
    "MAX_PATTERNS",
]
