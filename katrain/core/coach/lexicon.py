"""Phase 208: Go Lexicon YAML loader.

Loads `docs/resources/go_lexicon_master_last.yaml` (116 entries + 23 concepts)
into immutable dataclasses suitable for use as Ground Truth in LLM
"translation" prompts (Phase 203 spec §2.1 / §5.2).

YAML schema: ``go_lexicon_master_v1`` (lexicon-integration.md master).

The YAML is owned by ``D:\\github\\myKatrain_参考資料\\00_最重要_コーチング``
(the integrated coaching master) and mirrored at
``docs/resources/go_lexicon_master_last.yaml``. This loader only reads —
it does not modify the file.

Public API:
- ``load_lexicon(path=None)`` — parse the YAML
- ``LexiconEntry`` / ``LexiconConcept`` — frozen dataclasses
- ``get_entry(id)`` / ``get_concept(id)`` — O(1) lookup by id
- ``entries_by_level`` / ``entries_by_category`` — filtered iterators
- ``validate_references()`` — internal ``related_ids`` integrity check

Usage::

    from katrain.core.coach.lexicon import load_lexicon, get_entry
    lex = load_lexicon()
    lib = get_entry("liberty")
    lib.ja_one_liner       # "石に隣接する空点"
    lib.ja_short[:80]      # "囲碁のルールで、石の上下左右にある空いている交点を..."
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

# YAML parser: PyYAML is already a project dependency (ai/constants etc.)
import yaml

DEFAULT_LEXICON_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "docs" / "resources" / "go_lexicon_master_last.yaml"
)


# --- Dataclasses ---


@dataclass(frozen=True)
class LexiconEntry:
    """A single Go terminology entry (level 1 or 2).

    Mirrors the YAML schema's ``entries[]`` records. Optional fields are
    ``None`` when absent (e.g. ``contrast_with`` only present in ~49% of
    entries; ``ja_expanded`` only in Lv2).

    Attributes:
        id: Stable identifier (e.g. "liberty", "aji_keshi"). Cross-ref key.
        level: 1 (beginner) or 2 (intermediate).
        category: Topical bucket (e.g. "rules", "tactic", "shape").
        ja_term: Japanese primary term.
        en_terms: English term variants (list).
        ja_one_liner: One-sentence Japanese definition.
        en_one_liner: One-sentence English definition.
        ja_short: Short Japanese explanation (1-3 sentences).
        en_short: Short English explanation.
        pitfalls: Common pitfalls (Japanese bullet list).
        recognize_by: How to recognise the pattern on a board.
        micro_example: Compact example / anecdote.
        related_ids: References to other entries/concepts (strings).
        sources: External references (URLs).
        contrast_with: Optional — opposite concepts.
        ja_expanded: Optional — long-form Japanese elaboration.
        en_expanded: Optional — long-form English elaboration.
        diagram: Optional — raw diagram spec (kept as dict for downstream use).
        ai_perspective: Optional — AI-era commentary dict.
    """

    id: str
    level: int
    category: str
    ja_term: str
    en_terms: tuple[str, ...]
    ja_one_liner: str
    en_one_liner: str
    ja_short: str
    en_short: str
    pitfalls: tuple[str, ...]
    recognize_by: tuple[str, ...]
    micro_example: str
    related_ids: tuple[str, ...]
    sources: tuple[str, ...]
    contrast_with: tuple[str, ...] | None = None
    ja_expanded: str | None = None
    en_expanded: str | None = None
    diagram: dict[str, Any] | None = None
    ai_perspective: dict[str, Any] | None = None


@dataclass(frozen=True)
class LexiconConcept:
    """A higher-level concept entry (level 3 / advanced concepts).

    Has a different schema than LexiconEntry:
    uses ``ja_title`` / ``en_title`` instead of ``ja_term`` / ``en_terms``,
    plus decision_checklist / signals / common_failure_modes / drills /
    prerequisites / nuances fields.

    Attributes:
        id: Stable identifier (e.g. "urgent_vs_big").
        level: Always 3 for concepts.
        category: Topical bucket.
        ja_title / en_title: Title (Japanese / English).
        ja_one_liner / en_one_liner: One-sentence summary.
        ja_expanded / en_expanded: Long-form elaboration.
        decision_checklist: Concrete steps to apply the concept.
        signals: Cues that trigger consideration of the concept.
        common_failure_modes: Mistakes learners commonly make.
        drills: Practice ideas.
        prerequisites: Concepts that should be understood first.
        related_ids: Cross-references.
        nuances: Subtle considerations.
        sources: External references.
        ai_perspective: AI-era commentary.
    """

    id: str
    level: int
    category: str
    ja_title: str
    en_title: str
    ja_one_liner: str
    en_one_liner: str
    ja_expanded: str
    en_expanded: str
    decision_checklist: tuple[str, ...]
    signals: tuple[str, ...]
    common_failure_modes: tuple[str, ...]
    drills: tuple[str, ...]
    prerequisites: tuple[str, ...]
    related_ids: tuple[str, ...]
    nuances: str
    sources: tuple[str, ...]
    ai_perspective: dict[str, Any] | None = None


@dataclass(frozen=True)
class LexiconBundle:
    """Top-level YAML bundle.

    Attributes:
        schema_version: ``meta.schema`` value (currently ``go_lexicon_master_v1``).
        entries: Frozen tuple of LexiconEntry.
        concepts: Frozen tuple of LexiconConcept.
        katago_metadata: Raw katago metadata dict (for diagnostic use).
    """

    schema_version: str
    entries: tuple[LexiconEntry, ...]
    concepts: tuple[LexiconConcept, ...]
    katago_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def entry_by_id(self) -> dict[str, LexiconEntry]:
        return {e.id: e for e in self.entries}

    @property
    def concept_by_id(self) -> dict[str, LexiconConcept]:
        return {c.id: c for c in self.concepts}


# --- Loaders ---


def _str_tuple(v: Any) -> tuple[str, ...]:
    """Coerce list-of-str (or None / single str) into a tuple of str."""
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,)
    return tuple(str(x) for x in v)


def _entry_from_raw(raw: dict[str, Any]) -> LexiconEntry:
    return LexiconEntry(
        id=str(raw["id"]),
        level=int(raw["level"]),
        category=str(raw["category"]),
        ja_term=str(raw["ja_term"]),
        en_terms=_str_tuple(raw.get("en_terms")),
        ja_one_liner=str(raw["ja_one_liner"]),
        en_one_liner=str(raw["en_one_liner"]),
        ja_short=str(raw["ja_short"]),
        en_short=str(raw["en_short"]),
        pitfalls=_str_tuple(raw.get("pitfalls")),
        recognize_by=_str_tuple(raw.get("recognize_by")),
        micro_example=str(raw.get("micro_example", "")),
        related_ids=_str_tuple(raw.get("related_ids")),
        sources=_str_tuple(raw.get("sources")),
        contrast_with=_str_tuple(raw.get("contrast_with")) or None,
        ja_expanded=raw.get("ja_expanded"),
        en_expanded=raw.get("en_expanded"),
        diagram=raw.get("diagram"),
        ai_perspective=raw.get("ai_perspective"),
    )


def _concept_from_raw(raw: dict[str, Any]) -> LexiconConcept:
    return LexiconConcept(
        id=str(raw["id"]),
        level=int(raw["level"]),
        category=str(raw["category"]),
        ja_title=str(raw["ja_title"]),
        en_title=str(raw["en_title"]),
        ja_one_liner=str(raw["ja_one_liner"]),
        en_one_liner=str(raw["en_one_liner"]),
        ja_expanded=str(raw["ja_expanded"]),
        en_expanded=str(raw["en_expanded"]),
        decision_checklist=_str_tuple(raw.get("decision_checklist")),
        signals=_str_tuple(raw.get("signals")),
        common_failure_modes=_str_tuple(raw.get("common_failure_modes")),
        drills=_str_tuple(raw.get("drills")),
        prerequisites=_str_tuple(raw.get("prerequisites")),
        related_ids=_str_tuple(raw.get("related_ids")),
        nuances=str(raw.get("nuances", "")),
        sources=_str_tuple(raw.get("sources")),
        ai_perspective=raw.get("ai_perspective"),
    )


def load_lexicon(path: str | Path | None = None) -> LexiconBundle:
    """Parse the YAML and return a LexiconBundle.

    Args:
        path: Optional YAML path. Defaults to ``docs/resources/go_lexicon_master_last.yaml``.

    Raises:
        FileNotFoundError: If path does not exist.
        yaml.YAMLError: If the YAML is malformed.
        KeyError: If a required field is missing on an entry.
    """
    target = Path(path) if path else DEFAULT_LEXICON_PATH
    with open(target, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    meta = raw.get("meta", {})
    schema_version = str(meta.get("schema", "unknown"))

    entries_raw = raw.get("entries", []) or []
    concepts_raw = raw.get("concepts", []) or []

    entries = tuple(_entry_from_raw(e) for e in entries_raw)
    concepts = tuple(_concept_from_raw(c) for c in concepts_raw)

    return LexiconBundle(
        schema_version=schema_version,
        entries=entries,
        concepts=concepts,
        katago_metadata=raw.get("katago", {}),
    )


# --- Cached lookup (single global bundle) ---


@lru_cache(maxsize=1)
def _load_default_cached() -> LexiconBundle:
    """Memoised load for the default path. Use ``load_lexicon()`` instead
    when you need a specific path or want to bypass the cache.
    """
    return load_lexicon()


def get_entry(entry_id: str) -> LexiconEntry | None:
    """Return entry by id, or None if not found. Uses cached bundle."""
    return _load_default_cached().entry_by_id.get(entry_id)


def get_concept(concept_id: str) -> LexiconConcept | None:
    """Return concept by id, or None if not found. Uses cached bundle."""
    return _load_default_cached().concept_by_id.get(concept_id)


def entries_by_level(level: int) -> list[LexiconEntry]:
    """Return all entries with the given level (1 or 2)."""
    return [e for e in _load_default_cached().entries if e.level == level]


def entries_by_category(category: str) -> list[LexiconEntry]:
    """Return all entries with the given category (e.g. "rules", "tactic")."""
    return [e for e in _load_default_cached().entries if e.category == category]


def validate_references() -> dict[str, Any]:
    """Verify internal ``related_ids`` / ``contrast_with`` integrity.

    Returns a small dict summary::

        {
            "total_entries": 116,
            "total_concepts": 23,
            "broken_refs": 0,                # refs that point nowhere
            "duplicate_ids": [],             # id collisions
            "level_distribution": {"1": 60, "2": 56, "3": 23},
            "category_distribution": {...},
        }

    The YAML validation report (2025-12-24) asserts broken_refs == 0 and
    duplicate_ids == []. This function is meant for sanity checks during
    dev/test, not for hot-path use.
    """
    bundle = _load_default_cached()
    known_ids: set[str] = set()
    known_ids.update(e.id for e in bundle.entries)
    known_ids.update(c.id for c in bundle.concepts)

    broken: list[tuple[str, str]] = []
    for e in bundle.entries:
        for rid in e.related_ids:
            if rid not in known_ids:
                broken.append((e.id, rid))
        for cid in e.contrast_with or ():
            if cid not in known_ids:
                broken.append((e.id, cid))
    for c in bundle.concepts:
        for rid in c.related_ids:
            if rid not in known_ids:
                broken.append((c.id, rid))

    all_ids = [e.id for e in bundle.entries] + [c.id for c in bundle.concepts]
    dupes = [i for i, n in Counter(all_ids).items() if n > 1]

    return {
        "total_entries": len(bundle.entries),
        "total_concepts": len(bundle.concepts),
        "schema_version": bundle.schema_version,
        "broken_refs": len(broken),
        "broken_ref_samples": broken[:10],
        "duplicate_ids": dupes,
        "level_distribution": {
            str(k): v
            for k, v in (Counter(e.level for e in bundle.entries) + Counter(c.level for c in bundle.concepts)).items()
        },
        "category_distribution": dict(
            Counter(e.category for e in bundle.entries) | Counter(c.category for c in bundle.concepts)
        ),
    }


def inject_lexicon_for_prompt(
    entry_ids: Iterable[str],
    *,
    include_expanded: bool = True,
) -> str:
    """Build a prompt-friendly snippet from a subset of entries.

    Used by Phase 211 prompt_builder to embed Lexicon ground truth into
    an HTML-comment instruction block (Phase 203 §5.3).

    Phase 244: also accepts concept ids (Lv3 entries) which are stored
    in the YAML's ``concepts`` section. Previously the function only
    looked at ``entries``, so ``urgent_vs_big`` / ``direction_of_play``
    / etc. (referenced by ``symptom_index.py`` ``related_lexicon_ids``)
    were silently skipped because they live in ``concepts`` rather than
    ``entries``. Concepts use a different field set (``ja_title`` /
    ``ja_one_liner`` / ``ja_expanded``) so the formatter picks the
    right block per-id.

    Args:
        entry_ids: Iterable of entry/concept ids to embed (limit to
            3-7 for token size).
        include_expanded: When True, include ``ja_expanded`` (long form).

    Returns:
        A multi-line string ready to be embedded in a Markdown block.

    Note:
        Missing ids are skipped silently — downstream validation
        (Phase 212) flags the discrepancy to the user.
    """
    bundle = _load_default_cached()
    entry_by_id = bundle.entry_by_id
    concept_by_id = bundle.concept_by_id
    lines: list[str] = []
    for eid in entry_ids:
        entry = entry_by_id.get(eid)
        if entry is not None:
            lines.append(f"【{entry.ja_term} ({entry.id})】")
            lines.append(f"定義: {entry.ja_one_liner}")
            lines.append(f"詳細: {entry.ja_short}")
            if entry.pitfalls:
                lines.append(f"注意点: {' / '.join(entry.pitfalls)}")
            if include_expanded and entry.ja_expanded:
                lines.append(f"拡張: {entry.ja_expanded}")
            lines.append("")
            continue
        concept = concept_by_id.get(eid)
        if concept is not None:
            # Concepts use ja_title / ja_one_liner / ja_expanded.
            lines.append(f"【{concept.ja_title} ({concept.id})】")
            lines.append(f"定義: {concept.ja_one_liner}")
            if include_expanded and concept.ja_expanded:
                lines.append(f"詳細: {concept.ja_expanded}")
            lines.append("")
            continue
        # Unknown id — skip silently. Phase 212 validator flags this.
    return "\n".join(lines)


def all_ids() -> tuple[str, ...]:
    """Convenience: every known id (entries + concepts), sorted."""
    bundle = _load_default_cached()
    ids = [e.id for e in bundle.entries] + [c.id for c in bundle.concepts]
    return tuple(sorted(ids))


def extract_all_injected_terms(
    injection_text: str | None = None,
    *,
    entry_ids: Iterable[str] | None = None,
) -> set[str]:
    """Build a permissive whitelist of every Japanese term related to the injection.

    Phase 272-B5: the validator previously used the ``ja_term`` map
    plus the ``「…」`` brackets from the injection block as the
    whitelist for "off-injection" warnings. That was too narrow:
    the LLM often uses a term that was taught via the entry's
    ``ja_one_liner`` / ``ja_short`` / ``pitfalls`` / ``recognize_by``
    prose (which may contain sub-terms like ``捨て石`` or
    ``大場`` that are *not* the entry's primary ``ja_term``).

    This helper builds a comprehensive whitelist:

    - The ``ja_term`` / ``ja_title`` of every entry / concept
      (or every entry matching ``entry_ids`` when provided)
    - The ``「…」`` / ``『…』`` brackets from ``injection_text``
    - Japanese compound words (2-15 chars, Kana + CJK) extracted from
      each entry's ``pitfalls`` / ``recognize_by`` / ``micro_example``
      / ``ja_short`` / ``ja_one_liner`` / ``ja_expanded`` (entries)
      and ``ja_one_liner`` / ``ja_expanded`` / ``decision_checklist``
      / ``drills`` / ``nuances`` (concepts)

    The whitelist is then consumed by
    :func:`katrain.core.coach.llm_validator._extract_off_injection_lexicon_mentions`
    so terms that legitimately come from the injection block are not
    reported as ``lexicon_mention_not_injected``.

    Args:
        injection_text: Raw text of the injected Lexicon block (with
            HTML comment markers stripped — i.e. ``prompt.lex_injection``).
            ``None`` is allowed; only the explicit entry ids are used.
        entry_ids: When provided, restrict the whitelist to those
            entry/concept ids. When ``None``, the full bundle is used
            (useful for callers that don't know which entries were
            injected).

    Returns:
        A set of Japanese terms that should be accepted as "injected".
        Duplicate terms are collapsed.
    """
    bundle = _load_default_cached()
    terms: set[str] = set()

    # 1. Primary ``ja_term`` / ``ja_title`` for the requested entries.
    if entry_ids is None:
        candidates: Iterable[str] = list(bundle.entry_by_id) + list(bundle.concept_by_id)
    else:
        candidates = list(entry_ids)

    for eid in candidates:
        entry = bundle.entry_by_id.get(eid)
        if entry is not None and entry.ja_term:
            terms.add(entry.ja_term)
            # Sub-extract from description text.
            for source in (entry.ja_one_liner, entry.ja_short, entry.ja_expanded or ""):
                _collect_japanese_compounds(source, terms)
            for pitfall in entry.pitfalls:
                _collect_japanese_compounds(pitfall, terms)
            for recog in entry.recognize_by:
                _collect_japanese_compounds(recog, terms)
            _collect_japanese_compounds(entry.micro_example, terms)
            continue
        concept = bundle.concept_by_id.get(eid)
        if concept is not None and concept.ja_title:
            terms.add(concept.ja_title)
            for source in (concept.ja_one_liner, concept.ja_expanded, concept.nuances):
                _collect_japanese_compounds(source, terms)
            for step in concept.decision_checklist:
                _collect_japanese_compounds(step, terms)
            for drill in concept.drills:
                _collect_japanese_compounds(drill, terms)

    # 2. Bracketed terms from the rendered injection block.
    if injection_text:
        terms.update(re.findall(r"[「『]([^」』]{2,20})[」』]", injection_text))

    return terms


# Phase 272-B5: extract Japanese compound words (Kana + CJK Unified Ideographs)
# of 2-15 characters from free-form text. Capped so we don't accidentally
# accept very long phrases that would over-match.
_JAPANESE_COMPOUND_RE = re.compile(r"[ぁ-んァ-ヴ一-鿿]{2,15}")


def _collect_japanese_compounds(text: str, target: set[str]) -> None:
    """Phase 272-B5 helper: append Japanese compounds from ``text`` to ``target``."""
    if not text:
        return
    for compound in _JAPANESE_COMPOUND_RE.findall(text):
        # Skip very common particles / short particles that would
        # cause false positives in the validator.
        if compound in ("こと", "もの", "ため", "よう", "として", "による"):
            continue
        target.add(compound)


def build_id_to_ja_term_map(entry_ids: Iterable[str] | None = None) -> dict[str, str]:
    """Build a mapping ``{id: ja_term}`` for the requested entry ids.

    Phase 226-A: provides the reverse-lookup bridge between the
    English-style lexicon ids (e.g. ``"liberty"``) and the Japanese
    ``ja_term`` strings (e.g. ``"呼吸点"``) that appear in the injected
    prompt block and — by extension — in the LLM's response text.

    The LLM validator (Phase 212 / Phase 226-A) needs this to detect
    "hallucinated" ja_terms that were *not* part of the injection
    block but were still written inside 「」 brackets.

    Phase 272: also includes Lv3 concept ids (e.g. ``"urgent_vs_big"``)
    using their ``ja_title`` field. The previous implementation only
    looked at :attr:`LexiconBundle.entry_by_id`, so concept ids were
    silently dropped — making every concept-related term (``"大場"``,
    ``"急場"`` etc.) appear as off-injection even when the concept was
    actually injected. Concepts use ``ja_title`` (mirrors
    :func:`inject_lexicon_for_prompt` which already handles both).

    Args:
        entry_ids: Iterable of ids to look up. ``None`` means *all* ids
            (entries + concepts).

    Returns:
        A dict containing only the ids that were actually found in the
        cached bundle. Unknown ids are silently skipped — the caller can
        compare the returned length against ``len(tuple(entry_ids))`` to
        detect missing entries.
    """
    bundle = _load_default_cached()
    if entry_ids is None:
        ids: list[str] = list(bundle.entry_by_id) + list(bundle.concept_by_id)
    else:
        ids = list(entry_ids)
    out: dict[str, str] = {}
    for eid in ids:
        entry = bundle.entry_by_id.get(eid)
        if entry is not None:
            out[eid] = entry.ja_term
            continue
        concept = bundle.concept_by_id.get(eid)
        if concept is not None:
            out[eid] = concept.ja_title
    return out


def all_ja_terms() -> tuple[str, ...]:
    """Convenience: every known ``ja_term`` (entries only), sorted.

    PR-06 (S11): kept for API stability but **currently unused**. The
    docstring previously claimed the validator consumes this list, but
    no validator call site references it. Downstream code that wants
    the Japanese term inventory should call
    :func:`build_id_to_ja_term_map` (concepts-aware) instead.
    """
    bundle = _load_default_cached()
    return tuple(sorted({e.ja_term for e in bundle.entries}))


__all__ = [
    "LexiconEntry",
    "LexiconConcept",
    "LexiconBundle",
    "DEFAULT_LEXICON_PATH",
    "load_lexicon",
    "get_entry",
    "get_concept",
    "entries_by_level",
    "entries_by_category",
    "validate_references",
    "inject_lexicon_for_prompt",
    "all_ids",
    "build_id_to_ja_term_map",
    "all_ja_terms",
]
