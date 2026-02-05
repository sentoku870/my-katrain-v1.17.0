# katrain/core/reports/section_registry.py
"""Section registry for pluggable report sections.

PR #Phase55: Report foundation + User aggregation

This module provides:
- normalize_lang: Language code normalization
- SectionContext: Protocol for section rendering context
- ReportSection: Protocol for pluggable sections
- ReportType: Enum for report types
- SectionRegistry: Registry for pluggable report sections
- get_section_registry: Singleton access
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .insertion import SectionRegistration


def normalize_lang(lang: str) -> str:
    """Normalize language code to project standard.

    Project uses "jp" for Japanese (matches gettext locales).
    Legacy code may use "ja", locale variants, or mixed case.

    Args:
        lang: Language code (e.g., "ja", "ja_JP", "ja-JP", "JP", "en")

    Returns:
        "jp" for Japanese variants, lowercase otherwise
    """
    normalized = lang.lower().replace("-", "_").split("_")[0]
    if normalized == "ja":
        return "jp"
    return normalized


class SectionContext(Protocol):
    """Context provided to section rendering."""

    @property
    def lang(self) -> str:
        """Language code ("jp" or "en"). Pre-normalized."""
        ...

    @property
    def focus_player(self) -> str | None:
        """Player filter ("B", "W", or None)."""
        ...

    def config(self, setting: str, default: Any = None) -> Any:
        """Read configuration value."""
        ...


class ReportSection(Protocol):
    """Protocol for pluggable report sections."""

    @property
    def section_id(self) -> str:
        """Unique section identifier."""
        ...

    def get_title(self, lang: str) -> str:
        """Get localized title. lang is "jp" or "en"."""
        ...

    def render_markdown(self, context: SectionContext) -> str | None:
        """Render content. Return None to skip."""
        ...

    def is_applicable(self, context: SectionContext) -> bool:
        """Return False to hide section."""
        ...


class ReportType(StrEnum):
    """Types of reports that support pluggable sections."""

    KARTE = "karte"
    SUMMARY = "summary"


class SectionRegistry:
    """Registry for pluggable report sections."""

    def __init__(self) -> None:

        self._registrations: dict[ReportType, list[SectionRegistration]] = {rt: [] for rt in ReportType}
        self._section_ids: dict[ReportType, set[str]] = {rt: set() for rt in ReportType}

    def register(
        self,
        report_type: ReportType,
        section: ReportSection,
        after_section_id: str | None = None,
        enabled_by_default: bool = True,
    ) -> None:
        """Register a section. Raises DuplicateSectionError if exists."""
        from .insertion import DuplicateSectionError, SectionRegistration

        sid = section.section_id
        if sid in self._section_ids[report_type]:
            raise DuplicateSectionError(f"Section '{sid}' already registered for {report_type.value}")

        self._section_ids[report_type].add(sid)
        self._registrations[report_type].append(
            SectionRegistration(
                section=section,
                after_section_id=after_section_id,
                enabled_by_default=enabled_by_default,
            )
        )

    def get_registrations(self, report_type: ReportType) -> list[SectionRegistration]:
        """Get all registrations in registration order."""
        return list(self._registrations[report_type])

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        for rt in ReportType:
            self._registrations[rt].clear()
            self._section_ids[rt].clear()


_SECTION_REGISTRY: SectionRegistry | None = None


def get_section_registry() -> SectionRegistry:
    """Get the global singleton registry."""
    global _SECTION_REGISTRY
    if _SECTION_REGISTRY is None:
        _SECTION_REGISTRY = SectionRegistry()
    return _SECTION_REGISTRY


def _reset_section_registry_for_testing() -> None:
    """Reset singleton. FOR TESTING ONLY. Not exported."""
    global _SECTION_REGISTRY
    _SECTION_REGISTRY = None
