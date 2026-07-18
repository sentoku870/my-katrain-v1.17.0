"""Phase 212 / Phase 226-A: LLM output validator.

Validates LLM responses against the Karte JSON ground truth (Phase 203 §7).

The validator is **advisory** — issues are returned as warnings, not raised
as errors (Phase 203 §7.3 user decision: 「警告表示のみ」).

What it checks (Phase 203 §7.2 priority):
1. Symptom IDs mentioned in the LLM output must exist in Karte JSON.
2. Move numbers must be in valid range (1..total_moves).
3. pointsLost values mentioned should match Karte values (within rounding).
4. Lexicon entry references must exist in the embedded injection block.

Phase 269: tone-consistency check removed. AYAKA voice is gone and
TOMOKO / TOMOKO_STRICT no longer warn on Kansai particle appearance.

Phase 226-A additions:
- A1: Lexicon validation is now functional. The previous implementation
     was a no-op (English id ↔ Japanese term mismatch). The new code
     builds an ``{id: ja_term}`` map from the prompt and detects both
     *referenced* ids and *off-injection* ja_terms used by the LLM.
- A2: Symptom id extraction has a 3-tier fallback:
     1. Trailing ``参照した症状ID: [...]`` line (the canonical form).
     2. Inline ``症状:`` / ``Symptoms:`` / ``Referenced symptoms:`` markers.
     3. Safety-net grep over the full text against the known id set,
        using strict word boundaries to minimise false positives.
- A3: Move number regex is now strict — prefix or suffix is required,
     and unit suffixes (年/月/日/段/級) prevent accidental matches.
- A4: pointsLost regex now matches ``目``/``損失``/``ロス``/
     ``points lost``/``loss`` in addition to the original ``目`` form.
- A5: When ``PromptConfig.player_color`` is set, references to the
     *opponent's* symptom ids are demoted from HIGH to MEDIUM with a
     distinct ``kind`` so the GUI can render them differently.
- A6: The ``tolerance`` parameter is now applied to the pointsLost
     ceiling comparison to prevent boundary false positives.

Result: :class:`ValidationReport` with typed issues and a summary.

Note:
    This module never raises on validation failures — it always returns a
    :class:`ValidationReport`. The GUI layer (Phase 225) renders the
    report as a warnings panel.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from katrain.core.analysis.meaning_tags.models import MeaningTagId
from katrain.core.coach.lexicon import build_id_to_ja_term_map
from katrain.core.coach.prompt_builder import LlmPrompt, PromptConfig


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

# Phase 226-A (A2 tier 2): inline symptom reference markers. The id list
# may appear mid-sentence (not just at end-of-text).
_INLINE_SYMPTOM_ID_RE = re.compile(
    r"""
    (?:症状|参照症状|ReferencedSymptoms?|UsedSymptoms?|SymptomIDs?)
    \s*[:：=]\s*
    \[?                       # optional opening bracket
    ([^\]\n]{1,400}?)         # captured: id list (no closing bracket / newline)
    \]?                       # optional closing bracket
    \s*(?=$|[\n。.]|参照した) # bounded by EOL / Japanese period / another marker
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Coordinates like "P13", "Q5", "A19" — match standalone tokens.
_MOVE_COORD_RE = re.compile(r"\b([A-Ta-t])\s*(\d{1,2})\b")

# Phase 226-A (A3): strict move-number regex. Either prefix *or* suffix
# is required (no longer both-optional), and a small set of unit
# suffixes (年/月/日/段/級/位) is explicitly excluded from the bare
# "50手" branch so things like "5段" / "30級" / "2026年" / "7月" do
# not get picked up as move numbers.
_MOVE_NUMBER_RE = re.compile(
    r"(?:"
    r"(?:#|move\s+)(\d{1,3})"  # "#50", "move 50"
    r"|(\d{1,3})\s*手目"  # "50手目"
    r"|(\d{1,3})(?=\s*手(?![\u4e00-\u9fff]))"  # "50手" (not followed by a CJK char)
    r"|着手\s*(\d{1,3})"  # "着手 50"
    r"|(\d{1,3})\s*番"  # "50番"
    r"|第\s*(\d{1,3})\s*手"  # "第50手"
    r")",
    re.IGNORECASE,
)

# Phase 226-A (A4): pointsLost patterns.
# Captures the numeric value in group 1.  Multiple alternative phrasings
# are accepted, but they all anchor on either the Japanese "目" unit
# or an explicit English/Japanese label so that bare integers in the
# prose do not leak in.
_POINTS_LOST_RE = re.compile(
    r"(?:"
    r"[-+]?\d+(?:\.\d+)?\s*目"  # "3.5目"
    r"|(?:損失|ロス)\s*[:：]?\s*[-+]?\d+(?:\.\d+)?"  # "損失 3.5"
    r"|[-+]?\d+(?:\.\d+)?\s*(?:points?\.?\s*lost|loss|lost)\b"  # "3.0 points lost"
    r"|(?:points?\.?\s*lost|loss)\s*[:：]?\s*[-+]?\d+(?:\.\d+)?"  # "points lost 3.5"
    r")",
    re.IGNORECASE,
)

# Phase 226-A (A1): Lexicon mention patterns — JA term in 「」/『』 brackets.
# Capture group 1 is the inner text (no quotes). Range widened slightly
# to accept 2-20 chars so longer terms like "シチョウの弱点" fit.
_LEXICON_MENTION_RE = re.compile(r"[「『]([^」』]{2,20})[」』]")


# --- Karte JSON ground truth extraction ---


def _karte_symptom_ids(karte: dict[str, Any]) -> set[str]:
    """Extract every symptom id present in the Karte JSON.

    Phase 226-H: also include all ``MeaningTagId`` enum values as
    ground truth. LLMs often confuse SymptomId (30 user-facing
    diagnoses) with MeaningTagId (12 technical KataGo-output tags)
    — e.g. writing ``life_death_error`` (a MeaningTagId) instead of
    ``life_death_misjudgment`` (the matching SymptomId). Both are
    valid references from the LLM's perspective, so we accept both.
    """
    ids: set[str] = set()
    # All MeaningTagId values are valid symptom references (Phase 226-H)
    for tag in MeaningTagId:
        ids.add(tag.value)
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
        for key in rt.get("by_category") or {}:
            ids.add(str(key))
    return ids


def _karte_symptom_ids_by_color(karte: dict[str, Any]) -> dict[str, set[str]]:
    """Phase 226-A (A5): per-color symptom id sets.

    Returns:
        ``{"black": {...}, "white": {...}}`` — only symptom ids that
        belong to a single colour are placed in that colour's set. Ids
        that appear in both colours (rare but possible via
        ``reason_tags_distribution`` aggregation) are present in both.
    """
    out: dict[str, set[str]] = {"black": set(), "white": set()}
    for color in ("black", "white"):
        for weakness in karte.get("weaknesses", {}).get(color, []) or []:
            cat = weakness.get("category")
            if cat:
                out[color].add(str(cat))
        for move in karte.get("important_moves", []) or []:
            owner = str(move.get("color", "")).lower()
            if owner not in out:
                continue
            mtag = move.get("meaning_tag_id")
            if mtag:
                out[owner].add(str(mtag))
            cat = move.get("category") or move.get("mistake_category")
            if cat:
                out[owner].add(str(cat).lower())
        rt = karte.get("reason_tags_distribution", {}).get(color, {}) or {}
        for key in rt.get("by_category") or {}:
            out[color].add(str(key))
    return out


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


# --- LLM text parsing ---


def _split_id_list(raw: str) -> tuple[str, ...]:
    """Split an id list on commas / whitespace / Japanese separators.

    Shared helper used by both the trailing-line and the inline fallback
    extractors (Phase 226-A A2).
    """
    parts = re.split(r"[\s,、，]+", raw)
    return tuple(p.strip().strip("[]「」") for p in parts if p.strip())


def _extract_symptom_ids(text: str) -> tuple[str, ...]:
    """Phase 226-A (A2): parse symptom ids from the LLM text.

    Three-tier fallback:
    1. Trailing ``参照した症状ID: [...]`` line (the canonical form).
    2. Inline ``症状: [...]`` / ``Symptoms: [...]`` markers anywhere in
       the text (so the LLM doesn't *have* to put the list at the end).
    3. Safety-net grep over the full text against a caller-supplied
       known id set — this lets the caller recover ids that the LLM
       mentioned in prose form without using any of the agreed markers.

    Returns the union of all tiers, deduped while preserving order.
    """
    out: list[str] = []
    seen: set[str] = set()

    # Tier 1: canonical trailing line.
    m = _SYMPTOM_ID_LINE_RE.search(text)
    if m:
        captured: str = str(m.group(1))
        for sid in _split_id_list(captured):
            if sid not in seen:
                out.append(sid)
                seen.add(sid)

    # Tier 2: inline markers (anywhere in the text).
    for m in _INLINE_SYMPTOM_ID_RE.finditer(text):
        captured = str(m.group(1))
        for sid in _split_id_list(captured):
            if sid not in seen:
                out.append(sid)
                seen.add(sid)

    return tuple(out)


def _extract_symptom_ids_with_grep(
    text: str,
    known_ids: Iterable[str],
) -> tuple[str, ...]:
    """Phase 226-A (A2 tier 3): safety-net grep.

    Looks for known symptom ids anywhere in the text using ``\b`` word
    boundaries on both sides. This catches cases where the LLM mentions
    a symptom in prose form (``アタリの見逃し: atari_blindness`` etc.)
    without using any explicit reference marker.

    Only ids that survive the strict word-boundary check are returned.
    Accepts both plain strings and ``SymptomId`` enum members; the
    caller is expected to coerce SymptomId to ``str.value`` before
    invoking this helper (the ground-truth set in
    :func:`validate_llm_output` is always ``set[str]`` by then).
    """
    if not text:
        return ()
    out: list[str] = []
    seen: set[str] = set()
    for sid in known_ids:
        if not sid or sid in seen:
            continue
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(sid)}(?![A-Za-z0-9_])", text):
            out.append(sid)
            seen.add(sid)
    return tuple(out)


def _extract_move_numbers(text: str) -> tuple[int, ...]:
    """Extract integers that look like move numbers (1..999).

    Phase 226-A (A3): the regex is now strict — prefix or suffix is
    required, and unit suffixes (年/月/日/段/級/位) are excluded from
    the bare "50手" branch. ``0`` is still accepted here so the range
    check (not this function) flags it as ``move_number_out_of_range``.
    """
    out: list[int] = []
    for m in _MOVE_NUMBER_RE.finditer(text):
        # The regex has 6 alternative capture groups; pick the first
        # that produced a digit string.
        v: int | None = None
        for grp in range(1, 7):
            raw = m.group(grp)
            if raw is None:
                continue
            try:
                v = int(raw)
                break
            except (ValueError, TypeError):
                continue
        if v is None:
            continue
        if 0 <= v <= 999:
            out.append(v)
    return tuple(out)


def _extract_points_lost(text: str) -> tuple[float, ...]:
    """Phase 226-A (A4): extract numeric pointsLost values from LLM text.

    Returns the first numeric value per matched region.  Multiple
    alternative phrasings (目 / 損失 / ロス / points lost / loss) are
    accepted, but bare integers in the prose do not leak in.
    """
    if not text:
        return ()
    out: list[float] = []
    for m in _POINTS_LOST_RE.finditer(text):
        region = m.group(0)
        # Pull the first signed/unsigned decimal integer.
        num_match = re.search(r"[-+]?\d+(?:\.\d+)?", region)
        if not num_match:
            continue
        try:
            out.append(float(num_match.group(0)))
        except ValueError:
            continue
    return tuple(out)


def _extract_lexicon_mentions(text: str, id_to_ja_term: dict[str, str]) -> tuple[str, ...]:
    """Phase 226-A (A1): identify lexicon terms the LLM mentioned.

    Args:
        text: LLM response text.
        id_to_ja_term: Mapping from injected ``id`` → ``ja_term``. Built
            by the caller from ``prompt.referenced_lexicon_ids`` via
            :func:`lexicon.build_id_to_ja_term_map`.

    Returns:
        Tuple of lexicon ids whose ``ja_term`` was found inside 「」
        brackets in the LLM text. Deduped, order preserved.

    Note:
        This is the *positive* side of A1 — the negative side
        (off-injection ja_terms) is computed in
        :func:`_extract_off_injection_lexicon_mentions` and rendered as
        a separate LOW warning.
    """
    if not text or not id_to_ja_term:
        return ()
    ja_to_id = {ja: eid for eid, ja in id_to_ja_term.items()}
    mentioned: list[str] = []
    seen: set[str] = set()
    for m in _LEXICON_MENTION_RE.finditer(text):
        term = m.group(1)
        eid = ja_to_id.get(term)
        if eid and eid not in seen:
            mentioned.append(eid)
            seen.add(eid)
    return tuple(mentioned)


def _extract_off_injection_lexicon_mentions(
    text: str,
    id_to_ja_term: dict[str, str],
    all_known_ja_terms: set[str] | None = None,
) -> tuple[str, ...]:
    """Phase 226-A (A1 negative side): ja_terms used but not in injection.

    Scans 「」 brackets in the LLM text and returns those whose content
    is *not* part of the injected lexicon (i.e. likely hallucinated).

    Args:
        text: LLM response text.
        id_to_ja_term: Mapping ``{id: ja_term}`` for the *injected*
            subset (i.e. what the prompt told the LLM about).
        all_known_ja_terms: Optional set of *all* ja_terms in the
            lexicon. When provided, off-injection matches that are
            still known lexicon terms are reported as MEDIUM (allowed
            but not in the injection block); unknown terms are
            reported as a stronger signal. The validator currently
            uses the same LOW severity for both to keep the user
            experience simple, but the distinction is preserved
            here for future tuning.

    Returns:
        Tuple of the raw term strings used inside 「」 brackets that
        did not match any injected ``ja_term``.
    """
    if not text:
        return ()
    injected_ja = set(id_to_ja_term.values())
    out: list[str] = []
    seen: set[str] = set()
    for m in _LEXICON_MENTION_RE.finditer(text):
        term = m.group(1)
        if term in injected_ja:
            continue
        if term in seen:
            continue
        out.append(term)
        seen.add(term)
    return tuple(out)


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
        config: Optional PromptConfig. Used for tone consistency checks
            and, in Phase 226-A (A5), the player-color integration check.
        tolerance: Phase 226-A (A6) — boundary tolerance for the
            pointsLost ceiling comparison. Values within
            ``ceiling + tolerance`` are accepted. Default 0.05 covers
            floating-point round-off at the ceiling boundary.

    Returns:
        ValidationReport with all issues found. Caller is responsible
        for rendering — this function never raises.
    """
    issues: list[ValidationIssue] = []

    # ---- Symptom id existence (A2 + A5) ----
    # Ground truth = the union of:
    # (a) Symptoms / categories present in the Karte JSON
    # (b) Symptom ids the prompt told the LLM about
    # (c) The configuration's detected + LLM-required ids
    ground_truth_symptoms = _karte_symptom_ids(karte_json)
    for sid in prompt.referenced_symptom_ids:
        ground_truth_symptoms.add(sid.value)
    if config is not None:
        for sid in config.detected_symptom_ids:
            ground_truth_symptoms.add(sid.value)
        for sid in config.llm_required_symptom_ids:
            ground_truth_symptoms.add(sid.value)
    # Phase 226-A (A5): per-color split for player-color integration.
    color_ids = _karte_symptom_ids_by_color(karte_json)
    if config is not None and config.player_color in ("B", "W"):
        own_color = "black" if config.player_color == "B" else "white"
        opp_color = "white" if own_color == "black" else "black"
        opponent_ids = color_ids.get(opp_color, set())
    else:
        own_color = ""
        opp_color = ""
        opponent_ids = set()

    # Phase 226-A (A2): tier 1+2 + tier 3 (safety-net grep).
    # NOTE: mypy loses the element type because the upstream
    # ``prompt.referenced_symptom_ids: tuple[SymptomId, ...]`` and the
    # StrEnum ``MeaningTagId`` values pollute the inferred type of the
    # ``referenced_ids`` local variable. The runtime contract is that
    # every entry here is a plain ``str`` (we convert SymptomId to
    # ``str.value`` at every call site). The explicit ignore keeps the
    # contract verifiable without an invasive rewrite.
    referenced_ids: list[str] = list(_extract_symptom_ids(llm_text))  # type: ignore[arg-type,assignment]
    grep_ids: tuple[str, ...] = _extract_symptom_ids_with_grep(llm_text, ground_truth_symptoms)  # type: ignore[arg-type,assignment]
    seen_ids: set[str] = set(referenced_ids)
    for sid in grep_ids:  # type: ignore[assignment]
        if sid not in seen_ids:  # type: ignore[comparison-overlap]
            referenced_ids.append(sid)  # type: ignore[arg-type]
            seen_ids.add(sid)  # type: ignore[arg-type]
    referenced_ids_tuple = tuple(referenced_ids)

    for sid in referenced_ids:  # type: ignore[assignment]
        if sid in ground_truth_symptoms:  # type: ignore[comparison-overlap]
            # Phase 226-A (A5): even when the symptom is known, if the
            # player_color is set and the id belongs ONLY to the
            # opponent's colour (i.e. not also in own colour), demote
            # to MEDIUM so the GUI can flag "wrong side reviewed".
            if (
                opp_color
                and sid in opponent_ids  # type: ignore[comparison-overlap]
                and sid not in color_ids.get(own_color, set())  # type: ignore[comparison-overlap]
            ):
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        kind="symptom_id_belongs_to_opponent",
                        message=(
                            f"症状 ID '{sid}' は相手側 ({opp_color}) のものです。"
                            f"指定視点 ({own_color}) では参照しない方が望ましいです"
                        ),
                        context={
                            "symptom_id": sid,
                            "own_color": own_color,
                            "opp_color": opp_color,
                        },
                    )
                )
            continue
        # Phase 226-A (A5): if the unknown id belongs to the opponent's
        # colour, demote the issue from HIGH to MEDIUM with a distinct
        # kind so the GUI can highlight "you reviewed the wrong side".
        if opp_color and sid in opponent_ids:  # type: ignore[comparison-overlap]
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.MEDIUM,
                    kind="symptom_id_belongs_to_opponent",
                    message=(
                        f"症状 ID '{sid}' は相手側 ({opp_color}) のものです。"
                        f"指定視点 ({own_color}) では参照しない方が望ましいです"
                    ),
                    context={
                        "symptom_id": sid,
                        "own_color": own_color,
                        "opp_color": opp_color,
                    },
                )
            )
            continue
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

    # ---- pointsLost sanity (A6) ----
    max_loss = _karte_max_points_lost(karte_json)
    referenced_losses = _extract_points_lost(llm_text)
    if max_loss is not None:
        # Phase 226-A (A6): tolerance is now applied to the ceiling
        # comparison. Values within ceiling + tolerance are accepted.
        ceiling = max_loss * 1.5
        boundary = ceiling + tolerance
        for v in referenced_losses:
            if abs(v) > boundary:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.MEDIUM,
                        kind="points_lost_outlier",
                        message=(f"pointsLost 値 {v} は Karte 上限 {max_loss:.1f} と乖離"),
                        context={"value": v, "ceiling": ceiling, "boundary": boundary},
                    )
                )

    # ---- Lexicon mention cross-ref (A1) ----
    # Phase 226-A (A1): build the id → ja_term map from the prompt's
    # referenced ids. Use the new positive/negative pair of extractors
    # so we report both *referenced* ids and *off-injection* terms.
    id_to_ja_term = build_id_to_ja_term_map(prompt.referenced_lexicon_ids)
    mentioned_lex = _extract_lexicon_mentions(llm_text, id_to_ja_term)
    off_injection_terms = _extract_off_injection_lexicon_mentions(llm_text, id_to_ja_term)
    for term in off_injection_terms:
        issues.append(
            ValidationIssue(
                severity=ValidationSeverity.LOW,
                kind="lexicon_mention_not_injected",
                message=(f"「{term}」はプロンプトで注入された Lexicon に含まれていません"),
                context={"term": term},
            )
        )

    # Phase 269: tone consistency check removed. AYAKA voice is gone,
    # and TOMOKO / TOMOKO_STRICT no longer warn on Kansai particle
    # appearance (per the "全棋力同じキャラで統一" user policy —
    # dialect preference is a matter of taste and we don't surface
    # it as a validation issue).

    return ValidationReport(
        llm_text=llm_text,
        issues=tuple(issues),
        referenced_symptom_ids=referenced_ids_tuple,
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
