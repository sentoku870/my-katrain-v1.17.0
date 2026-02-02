"""
Validation logic for lexicon entries.

This module provides:
- Two-stage validation pipeline (validate dict → build entry)
- ValidationIssue and ValidationResult dataclasses
- Exception classes for parse errors
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .models import AIPerspective, DiagramInfo, LexiconEntry


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LexiconError(Exception):
    """Base exception for lexicon operations."""

    pass


class LexiconParseError(LexiconError):
    """Raised when YAML file cannot be parsed or has invalid structure.

    Attributes:
        line: Line number (1-indexed) if available from YAML parser.
              None for structural/schema errors (e.g., missing 'entries' key).
        column: Column number (1-indexed) if available from YAML parser.
    """

    def __init__(
        self, message: str, line: int | None = None, column: int | None = None
    ):
        self.line = line
        self.column = column
        super().__init__(message)

    def __str__(self) -> str:
        if self.line is not None:
            loc = f"line {self.line}"
            if self.column is not None:
                loc += f", column {self.column}"
            return f"{super().__str__()} ({loc})"
        return super().__str__()


class LexiconNotLoadedError(LexiconError):
    """Raised when accessing store before loading."""

    pass


# ---------------------------------------------------------------------------
# Validation Issues
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation issue (error or warning).

    Attributes:
        entry_index: Index of the entry in the YAML entries list (0-indexed).
        entry_id: Entry ID if available, None if ID is missing/invalid.
        field: Field name where the issue occurred.
        message: Human-readable description of the issue.
        is_error: True for errors (entry skipped), False for warnings.
    """

    entry_index: int
    entry_id: str | None
    field: str
    message: str
    is_error: bool


@dataclass
class ValidationResult:
    """Result of validation with issues and statistics.

    Attributes:
        issues: List of all validation issues (errors and warnings).
        entries_loaded: Number of entries successfully loaded.
        entries_skipped: Number of entries skipped due to errors.
    """

    issues: list[ValidationIssue] = field(default_factory=list)
    entries_loaded: int = 0
    entries_skipped: int = 0

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return any(issue.is_error for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(not issue.is_error for issue in self.issues)

    @property
    def error_count(self) -> int:
        """Count of error issues."""
        return sum(1 for issue in self.issues if issue.is_error)

    @property
    def warning_count(self) -> int:
        """Count of warning issues."""
        return sum(1 for issue in self.issues if not issue.is_error)

    def format_report(self) -> str:
        """Format a human-readable report of validation issues."""
        lines = []
        lines.append(f"Loaded: {self.entries_loaded}, Skipped: {self.entries_skipped}")
        lines.append(f"Errors: {self.error_count}, Warnings: {self.warning_count}")

        if self.issues:
            lines.append("")
            for issue in self.issues:
                level = "ERROR" if issue.is_error else "WARN"
                id_str = issue.entry_id or f"index {issue.entry_index}"
                lines.append(f"[{level}] {id_str}.{issue.field}: {issue.message}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Field Validation Specs
# ---------------------------------------------------------------------------

# (expected_type, requirement)
# requirement:
#   True = always required
#   False = optional
#   "level3" = required if level == 3
#   "warn" = warn if empty
#   "warn_level3" = warn if level == 3 and empty
FieldRequirement = Literal[True, False, "level3", "warn", "warn_level3"]

FIELD_TYPE_SPECS: dict[str, tuple[type, FieldRequirement]] = {
    # All levels required
    "id": (str, True),
    "level": (int, True),
    "category": (str, True),
    "ja_term": (str, True),
    "en_terms": (list, True),  # list in YAML, converted to tuple in Stage 2
    "ja_one_liner": (str, True),
    "en_one_liner": (str, True),
    "ja_short": (str, True),
    "en_short": (str, True),
    # Recommended (empty = warning, default used)
    "sources": (list, "warn"),
    "related_ids": (list, False),
    # Level 3 required
    "ja_title": (str, "level3"),
    "en_title": (str, "level3"),
    "ja_expanded": (str, "level3"),
    "en_expanded": (str, "level3"),
    # Level 3 recommended
    "decision_checklist": (list, "warn_level3"),
    "signals": (list, "warn_level3"),
    "common_failure_modes": (list, "warn_level3"),
    "drills": (list, "warn_level3"),
    "prerequisites": (list, False),
    # Optional
    "pitfalls": (list, False),
    "recognize_by": (list, False),
    "micro_example": (str, False),
    "diagram": (dict, False),
    "contrast_with": (list, False),
    "nuances": (str, False),
    "ai_perspective": (dict, False),
}

# ID format: lowercase letters, numbers, hyphens, and underscores
# (kebab-case or snake_case accepted)
# Pattern compiled lazily to avoid module-level side effects
_ID_PATTERN: re.Pattern[str] | None = None


def _get_id_pattern() -> re.Pattern[str]:
    """Get the compiled ID pattern (lazy initialization)."""
    global _ID_PATTERN
    if _ID_PATTERN is None:
        _ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
    return _ID_PATTERN


# ---------------------------------------------------------------------------
# Stage 1: Dict Validation
# ---------------------------------------------------------------------------


def validate_entry_dict(data: Any, entry_index: int) -> list[ValidationIssue]:
    """Stage 1: Validate raw dict from YAML.

    Checks:
    - Entry is a dict
    - Required fields exist and are non-empty
    - Types are correct
    - ID format is valid (kebab-case)
    - Level is 1, 2, or 3
    - Level 3 specific fields are present

    Args:
        data: Raw entry data from YAML.
        entry_index: Index of this entry in the entries list.

    Returns:
        List of ValidationIssue objects (errors and warnings).
    """
    issues: list[ValidationIssue] = []

    # Check if entry is a dict
    if not isinstance(data, dict):
        issues.append(
            ValidationIssue(
                entry_index=entry_index,
                entry_id=None,
                field="(entry)",
                message=f"Entry must be a dict, got {type(data).__name__}",
                is_error=True,
            )
        )
        return issues

    # Extract ID early for better error messages
    raw_id = data.get("id")
    entry_id = raw_id if isinstance(raw_id, str) else None

    # Validate ID
    if raw_id is None:
        issues.append(
            ValidationIssue(
                entry_index=entry_index,
                entry_id=None,
                field="id",
                message="Required field is missing",
                is_error=True,
            )
        )
    elif not isinstance(raw_id, str):
        issues.append(
            ValidationIssue(
                entry_index=entry_index,
                entry_id=None,
                field="id",
                message=f"Expected str, got {type(raw_id).__name__}",
                is_error=True,
            )
        )
    elif entry_id is not None:
        if not entry_id.strip():
            issues.append(
                ValidationIssue(
                    entry_index=entry_index,
                    entry_id=None,
                    field="id",
                    message="ID cannot be empty",
                    is_error=True,
                )
            )
            entry_id = None
        elif not _get_id_pattern().match(entry_id):
            issues.append(
                ValidationIssue(
                    entry_index=entry_index,
                    entry_id=entry_id,
                    field="id",
                    message=f"ID must be lowercase alphanumeric with hyphens/underscores (got '{entry_id}')",
                    is_error=True,
                )
            )

    # Get level for Level 3 specific checks
    level = data.get("level")
    is_level3 = isinstance(level, int) and level == 3

    # Validate level range
    if isinstance(level, int) and level not in (1, 2, 3):
        issues.append(
            ValidationIssue(
                entry_index=entry_index,
                entry_id=entry_id,
                field="level",
                message=f"Level must be 1, 2, or 3 (got {level})",
                is_error=True,
            )
        )

    # Validate each field
    for field_name, (expected_type, requirement) in FIELD_TYPE_SPECS.items():
        # Skip 'id' - already validated above with format check
        if field_name == "id":
            continue

        value = data.get(field_name)

        # Check type
        if value is not None and not isinstance(value, expected_type):
            issues.append(
                ValidationIssue(
                    entry_index=entry_index,
                    entry_id=entry_id,
                    field=field_name,
                    message=f"Expected {expected_type.__name__}, got {type(value).__name__}",
                    is_error=True,
                )
            )
            continue

        # Determine if field is required
        is_required = requirement is True
        is_level3_required = requirement == "level3" and is_level3
        is_warn = requirement == "warn"
        is_warn_level3 = requirement == "warn_level3" and is_level3

        # Check missing/empty
        is_empty = (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, list) and len(value) == 0)
        )

        if is_empty:
            if is_required or is_level3_required:
                issues.append(
                    ValidationIssue(
                        entry_index=entry_index,
                        entry_id=entry_id,
                        field=field_name,
                        message="Required field is missing or empty",
                        is_error=True,
                    )
                )
            elif is_warn or is_warn_level3:
                issues.append(
                    ValidationIssue(
                        entry_index=entry_index,
                        entry_id=entry_id,
                        field=field_name,
                        message="Recommended field is empty",
                        is_error=False,
                    )
                )

    # Validate en_terms is non-empty list
    en_terms = data.get("en_terms")
    if isinstance(en_terms, list):
        if len(en_terms) == 0:
            # Already caught above
            pass
        elif not all(isinstance(t, str) and t.strip() for t in en_terms):
            issues.append(
                ValidationIssue(
                    entry_index=entry_index,
                    entry_id=entry_id,
                    field="en_terms",
                    message="All en_terms must be non-empty strings",
                    is_error=True,
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Stage 2: Build Entry from Dict
# ---------------------------------------------------------------------------


def build_entry_from_dict(data: dict[str, Any]) -> LexiconEntry:
    """Stage 2: Build immutable LexiconEntry from validated dict.

    Precondition: validate_entry_dict() returned no errors.
    Converts all list fields to tuples for immutability.

    Args:
        data: Validated entry dict from YAML.

    Returns:
        Immutable LexiconEntry instance.
    """
    # Build DiagramInfo if present
    diagram_data = data.get("diagram")
    diagram = None
    if diagram_data and isinstance(diagram_data, dict):
        diagram = DiagramInfo(
            setup=tuple(diagram_data.get("setup", [])),
            annotation=diagram_data.get("annotation", ""),
        )

    # Build AIPerspective if present
    ai_data = data.get("ai_perspective")
    ai_perspective = None
    if ai_data and isinstance(ai_data, dict):
        ai_perspective = AIPerspective(
            has_difference=bool(ai_data.get("has_difference", False)),
            summary=ai_data.get("summary", ""),
        )

    return LexiconEntry(
        # Required fields (validated in Stage 1)
        id=data["id"],
        level=data["level"],
        category=data["category"],
        ja_term=data["ja_term"],
        en_terms=tuple(data["en_terms"]),
        ja_one_liner=data["ja_one_liner"],
        en_one_liner=data["en_one_liner"],
        ja_short=data["ja_short"],
        en_short=data["en_short"],
        # Recommended fields (defaults if missing)
        sources=tuple(data.get("sources") or []),
        related_ids=tuple(data.get("related_ids") or []),
        # Level 3 fields (defaults for non-Level-3)
        ja_title=data.get("ja_title") or "",
        en_title=data.get("en_title") or "",
        ja_expanded=data.get("ja_expanded") or "",
        en_expanded=data.get("en_expanded") or "",
        decision_checklist=tuple(data.get("decision_checklist") or []),
        signals=tuple(data.get("signals") or []),
        common_failure_modes=tuple(data.get("common_failure_modes") or []),
        drills=tuple(data.get("drills") or []),
        prerequisites=tuple(data.get("prerequisites") or []),
        # Optional fields
        pitfalls=tuple(data.get("pitfalls") or []),
        recognize_by=tuple(data.get("recognize_by") or []),
        micro_example=data.get("micro_example") or "",
        diagram=diagram,
        contrast_with=tuple(data.get("contrast_with") or []),
        nuances=data.get("nuances") or "",
        ai_perspective=ai_perspective,
    )


# ---------------------------------------------------------------------------
# Reference Validation
# ---------------------------------------------------------------------------


def validate_references(
    entries: list[LexiconEntry],
    known_ids: set[str],
) -> list[ValidationIssue]:
    """Validate ID references across all entries.

    Checks related_ids, prerequisites, and contrast_with fields for
    references to unknown IDs.

    Args:
        entries: List of validated LexiconEntry objects.
        known_ids: Set of all known entry IDs.

    Returns:
        List of warning issues for unknown ID references.
    """
    issues: list[ValidationIssue] = []

    # Create index mapping for error messages
    id_to_index = {entry.id: i for i, entry in enumerate(entries)}

    for entry in entries:
        entry_index = id_to_index.get(entry.id, -1)

        # Check related_ids
        for ref_id in entry.related_ids:
            if ref_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        entry_index=entry_index,
                        entry_id=entry.id,
                        field="related_ids",
                        message=f"References unknown ID: '{ref_id}'",
                        is_error=False,
                    )
                )

        # Check prerequisites
        for ref_id in entry.prerequisites:
            if ref_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        entry_index=entry_index,
                        entry_id=entry.id,
                        field="prerequisites",
                        message=f"References unknown ID: '{ref_id}'",
                        is_error=False,
                    )
                )

        # Check contrast_with
        for ref_id in entry.contrast_with:
            if ref_id not in known_ids:
                issues.append(
                    ValidationIssue(
                        entry_index=entry_index,
                        entry_id=entry.id,
                        field="contrast_with",
                        message=f"References unknown ID: '{ref_id}'",
                        is_error=False,
                    )
                )

    return issues
