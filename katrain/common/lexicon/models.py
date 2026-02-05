"""
Data models for the Go lexicon system.

This module defines immutable dataclasses for lexicon entries.
All classes use frozen=True and Tuple[str, ...] for complete immutability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagramInfo:
    """SGF diagram information for a lexicon entry (immutable).

    Attributes:
        setup: Tuple of setup stone coordinates.
        annotation: Annotation text for the diagram.
    """

    setup: tuple[str, ...] = ()
    annotation: str = ""


@dataclass(frozen=True)
class AIPerspective:
    """AI perspective for Level 3 entries (immutable).

    Attributes:
        has_difference: Whether AI evaluation differs from human.
        summary: Summary of the AI perspective.
    """

    has_difference: bool = False
    summary: str = ""


@dataclass(frozen=True)
class LexiconEntry:
    """A single lexicon entry representing a Go term or concept.

    Completely immutable: frozen dataclass with tuple fields.
    All fields are constructor arguments; optional fields have defaults.

    Field Requirements by Level:
        - Required (all levels): id, level, category, ja_term, en_terms,
          ja_one_liner, en_one_liner, ja_short, en_short
        - Recommended (warning if empty): sources
        - Optional: related_ids, pitfalls, recognize_by, micro_example,
          diagram, contrast_with, nuances, ai_perspective
        - Level 3 required: ja_title, en_title, ja_expanded, en_expanded
        - Level 3 recommended: decision_checklist, signals, common_failure_modes,
          drills, prerequisites

    Attributes:
        id: Unique identifier in kebab-case (e.g., "atari", "tenuki-timing").
        level: Complexity level (1, 2, or 3).
        category: Category name (e.g., "rules", "urgency").
        ja_term: Japanese term.
        en_terms: English terms (non-empty tuple).
        ja_one_liner: Japanese one-line description.
        en_one_liner: English one-line description.
        ja_short: Japanese short description.
        en_short: English short description.
        sources: Source references (recommended, defaults to empty).
        related_ids: IDs of related entries (optional).
        ja_title: Japanese title (required for Level 3).
        en_title: English title (required for Level 3).
        ja_expanded: Japanese expanded explanation (required for Level 3).
        en_expanded: English expanded explanation (required for Level 3).
        decision_checklist: Decision checklist items (Level 3 recommended).
        signals: Signal indicators (Level 3 recommended).
        common_failure_modes: Common failure modes (Level 3 recommended).
        drills: Practice drill suggestions (Level 3 recommended).
        prerequisites: Prerequisite entry IDs (Level 3 recommended).
        pitfalls: Common pitfalls (optional).
        recognize_by: Recognition patterns (optional).
        micro_example: Micro example text (optional).
        diagram: Diagram information (optional).
        contrast_with: Contrasting entry IDs (optional).
        nuances: Nuance explanation (optional).
        ai_perspective: AI perspective information (optional).
    """

    # === Required fields (all levels) - missing/empty/invalid type = error ===
    id: str
    level: int  # 1, 2, or 3
    category: str
    ja_term: str
    en_terms: tuple[str, ...]  # Non-empty tuple required
    ja_one_liner: str
    en_one_liner: str
    ja_short: str
    en_short: str

    # === Recommended fields - missing/empty = warning, default used ===
    sources: tuple[str, ...] = ()
    related_ids: tuple[str, ...] = ()

    # === Level 3 required fields - missing/empty for Level 3 = error ===
    ja_title: str = ""
    en_title: str = ""
    ja_expanded: str = ""
    en_expanded: str = ""

    # === Level 3 recommended fields - empty for Level 3 = warning ===
    decision_checklist: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()
    common_failure_modes: tuple[str, ...] = ()
    drills: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()

    # === Optional fields - always use defaults ===
    pitfalls: tuple[str, ...] = ()
    recognize_by: tuple[str, ...] = ()
    micro_example: str = ""
    diagram: DiagramInfo | None = None
    contrast_with: tuple[str, ...] = ()
    nuances: str = ""
    ai_perspective: AIPerspective | None = None
