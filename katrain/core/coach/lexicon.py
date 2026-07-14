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

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

# YAML parser: PyYAML is already a project dependency (ai/constants etc.)
import yaml


DEFAULT_LEXICON_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "docs"
    / "resources"
    / "go_lexicon_master_last.yaml"
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
            for k, v in (Counter(e.level for e in bundle.entries)
                         + Counter(c.level for c in bundle.concepts)).items()
        },
        "category_distribution": dict(Counter(
            e.category for e in bundle.entries
        ) | Counter(
            c.category for c in bundle.concepts
        )),
    }


def inject_lexicon_for_prompt(
    entry_ids: Iterable[str],
    *,
    include_expanded: bool = True,
) -> str:
    """Build a prompt-friendly snippet from a subset of entries.

    Used by Phase 211 prompt_builder to embed Lexicon ground truth into
    an HTML-comment instruction block (Phase 203 §5.3).

    Args:
        entry_ids: Iterable of entry ids to embed (limit to 3-7 for token size).
        include_expanded: When True, include ``ja_expanded`` (long form).

    Returns:
        A multi-line string ready to be embedded in a Markdown block.

    Note:
        Missing ids are skipped silently — downstream validation (Phase 212)
        flags the discrepancy to the user.
    """
    bundle = _load_default_cached()
    by_id = bundle.entry_by_id
    lines: list[str] = []
    for eid in entry_ids:
        entry = by_id.get(eid)
        if entry is None:
            continue
        lines.append(f"【{entry.ja_term} ({entry.id})】")
        lines.append(f"定義: {entry.ja_one_liner}")
        lines.append(f"詳細: {entry.ja_short}")
        if entry.pitfalls:
            lines.append(f"注意点: {' / '.join(entry.pitfalls)}")
        if include_expanded and entry.ja_expanded:
            lines.append(f"拡張: {entry.ja_expanded}")
        lines.append("")
    return "\n".join(lines)


def all_ids() -> tuple[str, ...]:
    """Convenience: every known id (entries + concepts), sorted."""
    bundle = _load_default_cached()
    ids = [e.id for e in bundle.entries] + [c.id for c in bundle.concepts]
    return tuple(sorted(ids))


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
] 