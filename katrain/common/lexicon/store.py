"""
LexiconStore for loading and searching Go lexicon entries.

This module provides:
- LexiconStore class with thread-safe read operations
- Lock-free reads with atomic snapshot swapping
- Search by ID, title, category, and level
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import yaml

from .models import LexiconEntry
from .validation import (
    LexiconNotLoadedError,
    LexiconParseError,
    ValidationIssue,
    ValidationResult,
    build_entry_from_dict,
    validate_entry_dict,
    validate_references,
)

# ---------------------------------------------------------------------------
# Internal Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _LexiconSnapshot:
    """Internal immutable snapshot of lexicon data.

    All collections are immutable for thread-safe access.
    """

    entries: tuple[LexiconEntry, ...]
    by_id: Mapping[str, LexiconEntry]
    by_category: Mapping[str, tuple[LexiconEntry, ...]]
    by_level: Mapping[int, tuple[LexiconEntry, ...]]
    by_ja_title: Mapping[str, LexiconEntry]
    by_en_title: Mapping[str, LexiconEntry]
    categories: frozenset[str]


def _build_snapshot(entries: list[LexiconEntry]) -> _LexiconSnapshot:
    """Build an immutable snapshot from a list of entries.

    Args:
        entries: List of validated LexiconEntry objects.

    Returns:
        Immutable _LexiconSnapshot.
    """
    # Build ID index
    by_id: dict[str, LexiconEntry] = {}
    for entry in entries:
        by_id[entry.id] = entry

    # Build category index
    by_category_temp: dict[str, list[LexiconEntry]] = {}
    for entry in entries:
        if entry.category not in by_category_temp:
            by_category_temp[entry.category] = []
        by_category_temp[entry.category].append(entry)

    by_category: dict[str, tuple[LexiconEntry, ...]] = {
        cat: tuple(entries_list) for cat, entries_list in by_category_temp.items()
    }

    # Build level index
    by_level_temp: dict[int, list[LexiconEntry]] = {1: [], 2: [], 3: []}
    for entry in entries:
        if entry.level in by_level_temp:
            by_level_temp[entry.level].append(entry)

    by_level: dict[int, tuple[LexiconEntry, ...]] = {
        level: tuple(entries_list) for level, entries_list in by_level_temp.items()
    }

    # Build title indices (first entry wins for collisions)
    by_ja_title: dict[str, LexiconEntry] = {}
    by_en_title: dict[str, LexiconEntry] = {}

    for entry in entries:
        # Japanese title lookup: ja_term, ja_title
        ja_key = entry.ja_term.strip()
        if ja_key and ja_key not in by_ja_title:
            by_ja_title[ja_key] = entry

        if entry.ja_title:
            ja_title_key = entry.ja_title.strip()
            if ja_title_key and ja_title_key not in by_ja_title:
                by_ja_title[ja_title_key] = entry

        # English title lookup: en_terms (all), en_title
        for en_term in entry.en_terms:
            en_key = en_term.strip().lower()
            if en_key and en_key not in by_en_title:
                by_en_title[en_key] = entry

        if entry.en_title:
            en_title_key = entry.en_title.strip().lower()
            if en_title_key and en_title_key not in by_en_title:
                by_en_title[en_title_key] = entry

    # Build categories set
    categories = frozenset(by_category.keys())

    return _LexiconSnapshot(
        entries=tuple(entries),
        by_id=MappingProxyType(by_id),
        by_category=MappingProxyType(by_category),
        by_level=MappingProxyType(by_level),
        by_ja_title=MappingProxyType(by_ja_title),
        by_en_title=MappingProxyType(by_en_title),
        categories=categories,
    )


# ---------------------------------------------------------------------------
# LexiconStore
# ---------------------------------------------------------------------------


class LexiconStore:
    """Store for Go lexicon entries.

    Thread-safe store using lock-free reads with atomic snapshot swapping.
    All returned collections are immutable. Entries themselves are frozen.

    Usage:
        store = LexiconStore(Path("lexicon.yaml"))
        result = store.load()
        if result.has_errors:
            print(result.format_report())
        else:
            entry = store.get("atari")
    """

    def __init__(self, path: Path) -> None:
        """Initialize the store with a path to the YAML file.

        Args:
            path: Path to the lexicon YAML file.
        """
        self._path = path
        self._snapshot: _LexiconSnapshot | None = None

    def load(self) -> ValidationResult:
        """Load and validate the lexicon YAML file.

        This method can be called multiple times to reload the lexicon.
        The snapshot is atomically swapped after successful loading.

        Returns:
            ValidationResult with load statistics and any issues.

        Raises:
            LexiconParseError: If YAML cannot be parsed or has invalid structure.
        """
        result = ValidationResult()

        # Load YAML
        raw_data = self._load_yaml()

        # Validate structure
        if "entries" not in raw_data:
            raise LexiconParseError("Missing 'entries' key in YAML")

        entries_data = raw_data["entries"]
        if not isinstance(entries_data, list):
            raise LexiconParseError("'entries' must be a list")

        # Process entries
        entries: list[LexiconEntry] = []
        seen_ids: set[str] = set()

        for i, entry_data in enumerate(entries_data):
            # Stage 1: Validate dict
            issues = validate_entry_dict(entry_data, i)
            result.issues.extend(issues)

            # Check for errors
            has_error = any(issue.is_error for issue in issues)
            if has_error:
                result.entries_skipped += 1
                continue

            # Check for duplicate ID
            entry_id = entry_data.get("id")
            if entry_id in seen_ids:
                result.issues.append(
                    ValidationIssue(
                        entry_index=i,
                        entry_id=entry_id,
                        field="id",
                        message=f"Duplicate ID: '{entry_id}'",
                        is_error=True,
                    )
                )
                result.entries_skipped += 1
                continue

            seen_ids.add(entry_id)

            # Stage 2: Build entry
            entry = build_entry_from_dict(entry_data)
            entries.append(entry)
            result.entries_loaded += 1

        # Validate references
        ref_issues = validate_references(entries, seen_ids)
        result.issues.extend(ref_issues)

        # Check for title collisions and emit warnings
        title_collision_issues = self._check_title_collisions(entries)
        result.issues.extend(title_collision_issues)

        # Atomically swap snapshot
        self._snapshot = _build_snapshot(entries)

        return result

    def _load_yaml(self) -> dict[str, Any]:
        """Load YAML with line number preservation for syntax errors."""
        try:
            with open(self._path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data is None:
                    raise LexiconParseError("YAML file is empty")
                return cast(dict[str, Any], data)
        except yaml.YAMLError as e:
            line = None
            column = None
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                line = e.problem_mark.line + 1  # 0-indexed -> 1-indexed
                column = e.problem_mark.column + 1
            raise LexiconParseError(f"YAML syntax error: {e}", line=line, column=column) from e

    def _check_title_collisions(self, entries: list[LexiconEntry]) -> list[ValidationIssue]:
        """Check for title collisions and emit warnings."""
        issues: list[ValidationIssue] = []
        seen_ja: dict[str, str] = {}  # title -> first entry id
        seen_en: dict[str, str] = {}  # title -> first entry id

        for i, entry in enumerate(entries):
            # Check Japanese titles
            ja_titles = [entry.ja_term.strip()]
            if entry.ja_title:
                ja_titles.append(entry.ja_title.strip())

            for title in ja_titles:
                if not title:
                    continue
                if title in seen_ja:
                    issues.append(
                        ValidationIssue(
                            entry_index=i,
                            entry_id=entry.id,
                            field="ja_term",
                            message=f"Title collision: '{title}' (first in '{seen_ja[title]}')",
                            is_error=False,
                        )
                    )
                else:
                    seen_ja[title] = entry.id

            # Check English titles
            en_titles = [t.strip().lower() for t in entry.en_terms]
            if entry.en_title:
                en_titles.append(entry.en_title.strip().lower())

            for title in en_titles:
                if not title:
                    continue
                if title in seen_en:
                    issues.append(
                        ValidationIssue(
                            entry_index=i,
                            entry_id=entry.id,
                            field="en_terms",
                            message=f"Title collision: '{title}' (first in '{seen_en[title]}')",
                            is_error=False,
                        )
                    )
                else:
                    seen_en[title] = entry.id

        return issues

    @property
    def is_loaded(self) -> bool:
        """Check if the lexicon has been loaded."""
        return self._snapshot is not None

    def _require_loaded(self) -> _LexiconSnapshot:
        """Get snapshot or raise if not loaded."""
        if self._snapshot is None:
            raise LexiconNotLoadedError("Lexicon not loaded. Call load() first.")
        return self._snapshot

    def get(self, entry_id: str) -> LexiconEntry | None:
        """Get an entry by ID.

        Args:
            entry_id: The entry ID to look up.

        Returns:
            LexiconEntry if found, None otherwise.

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return snapshot.by_id.get(entry_id)

    def get_by_title(self, title: str, lang: str = "ja") -> LexiconEntry | None:
        """Get an entry by title.

        Args:
            title: The title to search for.
            lang: Language ("ja" or "en"). Defaults to "ja".

        Returns:
            LexiconEntry if found, None otherwise.

        Raises:
            LexiconNotLoadedError: If load() has not been called.
            ValueError: If lang is not "ja" or "en".
        """
        if lang not in ("ja", "en"):
            raise ValueError(f"lang must be 'ja' or 'en', got '{lang}'")

        snapshot = self._require_loaded()

        if lang == "ja":
            key = title.strip()
            return snapshot.by_ja_title.get(key)
        else:
            key = title.strip().lower()
            return snapshot.by_en_title.get(key)

    def get_by_category(self, category: str) -> tuple[LexiconEntry, ...]:
        """Get all entries in a category.

        Args:
            category: The category name.

        Returns:
            Tuple of entries in the category (empty if none found).

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return snapshot.by_category.get(category, ())

    def get_by_level(self, level: int) -> tuple[LexiconEntry, ...]:
        """Get all entries at a specific level.

        Args:
            level: The level (1, 2, or 3).

        Returns:
            Tuple of entries at the level (empty if none found).

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return snapshot.by_level.get(level, ())

    @property
    def all_entries(self) -> tuple[LexiconEntry, ...]:
        """Get all entries.

        Returns:
            Tuple of all entries.

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return snapshot.entries

    @property
    def all_categories(self) -> frozenset[str]:
        """Get all category names.

        Returns:
            FrozenSet of category names.

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return snapshot.categories

    def __len__(self) -> int:
        """Get the number of loaded entries.

        Returns:
            Number of entries.

        Raises:
            LexiconNotLoadedError: If load() has not been called.
        """
        snapshot = self._require_loaded()
        return len(snapshot.entries)
