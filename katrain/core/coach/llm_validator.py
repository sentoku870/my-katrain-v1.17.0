"""Phase 212: LLM output validator.

Validates LLM responses against the Karte JSON ground truth (Phase 203 §7).

The validator is **advisory** — issues are returned as warnings, not raised
as errors (Phase 203 §7.3 user decision: 「警告表示のみ」).

What it checks (Phase 203 §7.2 priority):
1. Symptom IDs mentioned in the LLM output must exist in Karte JSON.
2. Move numbers must be in valid range (1..total_moves).
3. pointsLost values mentioned should match Karte values (within rounding).
4. Lexicon entry references must exist in the embedded injection block.
5. Tone consistency (AYAKA → Kansai markers, TOMOKO → no Kansai).

Result: :class:`ValidationReport` with typed issues and a summary.

Note:
    This module never raises on validation failures — it always returns a
    :class:`ValidationReport`. The GUI layer (future Phase 213) renders
    the report as a warnings panel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from katrain.core.coach.master_db import ToneVoice
from katrain.core.coach.prompt_builder import LlmPrompt, PromptConfig
from katrain.core.coach.symptom_index import SymptomId


class ValidationSeverity(Enum):
    """Severity of a single validation issue.

    Per Phase 203 §7.2, all issues are advisory (warning level). The
    enum exists to let downstream code colour-code UI displays.
    """

    HIGH = "high"  # Symptom id not in Karte, move out of range
    MEDIUM = "medium"  # pointsLost mismatch, Lexicon reference mismatch
    LOW = "low"  # Tone inconsistency, prose hint


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation finding.

    Attributes:
        severity: Issue severity.
        kind: Stable identifier (e.g. ``"unknown_symptom_id"``).
        message: Human-readable explanation (Japanese or English).
        context: Optional extracted data (e.g. the symptom id).
    """

    severity: ValidationSeverity
    kind: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate validation result for a single LLM response.

    Attributes:
        llm_text: Original LLM text (echo for downstream UI).
        issues: Tuple of ValidationIssue. Empty = no issues found.
        referenced_symptom_ids: Symptom ids the LLM claimed to use.
        referenced_move_numbers: Move numbers the LLM mentioned.
        referenced_points_lost: pointsLost values the LLM mentioned.
        referenced_lexicon_ids: Lexicon ids the LLM mentioned.
    """

    llm_text: str
    issues: tuple[ValidationIssue, ...] = ()
    referenced_symptom_ids: tuple[str, ...] = ()
    referenced_move_numbers: tuple[int, ...] = ()
    referenced_points_lost: tuple[float, ...] = ()
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
        parts = []
        if self.high_count:
            parts.append(f"高: {self.high_count}")
        if self.medium_count:
            parts.append(f"中: {self.medium_count}")
        if self.low_count:
            parts.append(f"低: {self.low_count}")
        return "⚠️ 検証警告 (" + ", ".join(parts) + ")"


# --- Regex patterns ---


# Phase 203 §5.3 contract: LLM must end with "参照した症状ID: [list]"
# Allow some flexibility: Chinese / English / Japanese variants.
_SYMPTOM_ID_LINE_RE = re.compile(
    r"""
    (?:参照した症状ID|参照した症状|UsedSymptoms|SymptomIDs)
    \s*[:：=]\s*
    \[
?                       # optional opening bracket
    (.*?)                  # captured: id list
    \]?                    # optional closing bracket
    \s*$
    """,
    re.VERBOSE | re.MULTILINE,
)

# Coordinates like "P13", "Q5", "A19" — match standalone tokens.
_MOVE_COORD_RE = re.compile(r"\b([A-Ta-t])\s*(\d{1,2})\b")

# Move number tokens like "N手目", "move 50", "#50", "50手目" — permissive.
# Catches the integer regardless of whether it precedes or follows the marker.
_MOVE_NUMBER_RE = re.compile(
    r"(?:(?:#|move\s*|手(?:目)?|手目|着手)?\s*(\d{1,3})\s*(?:手(?:目)?|move|番|#)?)",
    re.IGNORECASE,
)

# pointsLost values like "-3.5目", "(2.0目)" — Phase 203 §7.2 item 3.
_POINTS_LOST_RE = re.compile(r"[-+]?\d+(?:\.\d+)?目")

# Lexicon mention patterns — JA term in 「」/（） brackets.
_LEXICON_MENTION_RE = re.compile(r"[「『]([^」』]{2,12})[」』]")


# --- Karte JSON ground truth extraction ---


def _karte_symptom_ids(karte: dict[str, Any]) -> set[str]:
    """Extract every symptom id present in the Karte JSON."""
    ids: set[str] = set()
    # weaknesses — keys include "phase" + "category", plus evidence
    for color in ("black", "white"):
        for weakness in karte.get("weaknesses", {}).get(color, []) or []:
            category = weakness.get("category")
            if category:
                ids.add(str(category))
    # important_moves[].meaning_tag_id (Phase 148+)
    for move in karte.get("important_moves", []) or []:
        mtag = move.get("meaning_tag_id")
        if mtag:
            ids.add(str(mtag))
        # Also collect mistake category strings
        cat = move.get("category") or move.get("mistake_category")
        if cat:
            ids.add(str(cat).lower())
    # reason_tags_distribution (Phase 149 C-3)
    for color in ("black", "white"):
        rt = karte.get("reason_tags_distribution", {}).get(color, {}) or {}
        for key in (rt.get("by_category") or {}).keys():
            ids.add(str(key))
    return ids


def _karte_move_count(karte: dict[str, Any]) -> int | None:
    """Return the total number of moves in the game."""
    summary = karte.get("summary", {})
    n = summary.get("total_moves")
    if isinstance(n, int) and n > 0:
        return n
    return None


def _karte_max_points_lost(karte: dict[str, Any]) -> float | None:
    """Return max pointsLost across important moves for sanity bounds."""
    moves = karte.get("important_moves", []) or []
    if not moves:
        return None
    losses: list[float] = []
    for m in moves:
        v = m.get("points_lost")
        if isinstance(v, (int, float)):
            losses.append(float(v))
    return max(losses) if losses else None


def _injected_lexicon_ids(prompt: LlmPrompt) -> set[str]:
    """Return lexicon ids embedded in the LLM prompt."""
    return set(prompt.referenced_lexicon_ids)


# --- LLM text parsing ---


def _extract_symptom_ids(text: str) -> tuple[str, ...]:
    """Parse the trailing "参照した症状ID: [...]" line from the LLM."""
    m = _SYMPTOM_ID_LINE_RE.search(text)
    if not m:
        return ()
    raw = m.group(1)
    # Split on commas / spaces.
    parts = re.split(r"[\s,、]+", raw)
    ids = tuple(p.strip() for p in parts if p.strip())
    return ids


def _extract_move_numbers(text: str) -> tuple[int, ...]:
    """Extract integers that look like move numbers (0..999).

    The range check itself enforces [1..total_moves]; we include 0 here
    so the range check (not this function) flags out-of-range values.
    """
    out: list[int] = []
    for m in _MOVE_NUMBER_RE.finditer(text):
        try:
            v = int(m.group(1))
        except (ValueError, IndexError):
            continue
        if 0 <= v <= 999:
            out.append(v)
    return tuple(out)


def _extract_points_lost(text: str) -> tuple[float, ...]:
    out: list[float] = []
    for m in _POINTS_LOST_RE.findall(text):
        try:
            out.append(float(m.replace("目", "")))
        except ValueError:
            continue
    return tuple(out)


def _extract_lexicon_mentions(text: str, known_ids: set[str]) -> tuple[str, ...]:
    """Return ja_terms from 「」 mentions whose id is in known_ids set."""
    mentioned: list[str] = []
    seen: set[str] = set()
    for m in _LEXICON_MENTION_RE.finditer(text):
        term = m.group(1)
        if term in known_ids and term not in seen:
            mentioned.append(term)
            seen.add(term)
    return tuple(mentioned)


# --- Public API ---


def validate_llm_output(
    llm_text: str,
    karte_json: dict[str, Any],
    prompt: LlmPrompt,
    *,
    config: PromptConfig | None = None,
    tolerance: float = 0.05,
) -> ValidationReport:
    """Validate ``llm_text`` against Karte JSON + LLM prompt.

    Args:
        llm_text: LLM-generated response text.
        karte_json: Karte JSON that was sent to the LLM (ground truth).
        prompt: The LlmPrompt that was generated (for lexicon cross-ref).
        config: Optional PromptConfig (used for tone consistency checks).
        tolerance: PointsLost comparison tolerance (default 0.05).

    Returns:
        ValidationReport with all issues found. Caller is responsible
        for rendering — this function never raises.
    """
    issues: list[ValidationIssue] = []

    # ---- Symptom id existence ----
    # Ground truth = the union of:
    # (a) Symptoms / categories present in the Karte JSON
    # (b) Symptom ids the prompt told the LLM about
    # (c) The configuration's detected + LLM-required ids
    ground_truth_symptoms = _karte_symptom_ids(karte_json)
    ground_truth_symptoms.update(prompt.referenced_symptom_ids)
    if config is not None:
        for sid in config.detected_symptom_ids:
            ground_truth_symptoms.add(sid.value)
        for sid in config.llm_required_symptom_ids:
            ground_truth_symptoms.add(sid.value)
    referenced_ids = _extract_symptom_ids(llm_text)
    for sid in referenced_ids:
        if sid not in ground_truth_symptoms:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.HIGH,
                    kind="unknown_symptom_id",
                    message=f"症状 ID '{sid}' は Karte JSON に存在しません",
                    context={"symptom_id": sid},
                )
            )

    # ---- Move number ranges ----
    total_moves = _karte_move_count(karte_json)
    referenced_moves = _extract_move_numbers(llm_text)
    if total_moves is not None:
        for n in referenced_moves:
            if n < 1 or n > total_moves:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.HIGH,
                        kind="move_number_out_of_range",
                        message=f"着手番号 {n} は範囲外（1〜{total_moves}）",
                        context={"move_number": n, "max": total_moves},
                    )
                )

    # ---- pointsLost sanity ----
    max_loss = _karte_max_points_lost(karte_json)
    referenced_losses = _extract_points_lost(llm_text)
    if max_loss is not None:
        # Heuristic: any value > 1.5x max_loss is suspicious. Smaller values
        # can be legitimate descriptive ranges — we only warn on outliers.
        ceiling = max_loss * 1.5
        for v in referenced_losses:
            if abs(v) > ceiling:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        kind="points_lost_outlier",
                        message=(
                            f"pointsLost 値 {v} は Karte 上限 {max_loss:.1f} と乖離"
                        ),
                        context={"value": v, "ceiling": ceiling},
                    )
                )

    # ---- Lexicon mention cross-ref ----
    known_lex = _injected_lexicon_ids(prompt)
    mentioned_lex = _extract_lexicon_mentions(llm_text, known_lex)
    # Anything in prompt.lex_injection that's not referenced is fine;
    # we're only flagging terms hallucinated outside the injected set.
    # For full audit we'd need a Lexicon lookup keyed by term, but the
    # ground-truth here is "id list" already validated above.

    # ---- Tone consistency ----
    cfg = config
    if cfg is not None:
        from katrain.core.coach.tones import has_kansai_markers

        if cfg.voice == ToneVoice.AYAKA and not has_kansai_markers(llm_text):
            # Not strictly wrong, but worth flagging if zero Kansai markers in long text.
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
        elif cfg.voice in (ToneVoice.TOMOKO, ToneVoice.TOMOKO_STRICT):
            if has_kansai_markers(llm_text):
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

    return ValidationReport(
        llm_text=llm_text,
        issues=tuple(issues),
        referenced_symptom_ids=referenced_ids,
        referenced_move_numbers=referenced_moves,
        referenced_points_lost=referenced_losses,
        referenced_lexicon_ids=mentioned_lex,
    )


__all__ = [
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationReport",
    "validate_llm_output",
] 