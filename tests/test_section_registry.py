# tests/test_section_registry.py
"""Tests for section registry and insertion utilities.

PR #Phase55: Report foundation + User aggregation
"""

import pytest

from katrain.core.reports.insertion import (
    DuplicateSectionError,
    SectionRegistration,
    compute_section_order,
)
from katrain.core.reports.section_registry import (
    ReportType,
    SectionRegistry,
    _reset_section_registry_for_testing,
    get_section_registry,
    normalize_lang,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset singleton registry before and after each test."""
    _reset_section_registry_for_testing()
    yield
    _reset_section_registry_for_testing()


class MockSection:
    """Mock section for testing."""

    def __init__(self, section_id: str):
        self.section_id = section_id

    def get_title(self, lang: str) -> str:
        if lang == "jp":
            return f"## {self.section_id}（日本語）"
        return f"## {self.section_id}"

    def render_markdown(self, context):
        return f"Content for {self.section_id}"

    def is_applicable(self, context):
        return True


class TestNormalizeLang:
    """Tests for normalize_lang function."""

    def test_ja_to_jp(self):
        """Basic ja -> jp conversion."""
        assert normalize_lang("ja") == "jp"

    def test_jp_unchanged(self):
        """jp remains jp."""
        assert normalize_lang("jp") == "jp"

    def test_en_unchanged(self):
        """en remains en."""
        assert normalize_lang("en") == "en"

    def test_locale_variants(self):
        """Handle locale variants like ja_JP, en_US."""
        assert normalize_lang("ja_JP") == "jp"
        assert normalize_lang("ja-JP") == "jp"
        assert normalize_lang("en_US") == "en"
        assert normalize_lang("en-GB") == "en"

    def test_uppercase(self):
        """Handle uppercase input."""
        assert normalize_lang("JA") == "jp"
        assert normalize_lang("EN") == "en"
        assert normalize_lang("Ja_Jp") == "jp"


class TestSectionRegistry:
    """Tests for SectionRegistry class."""

    def test_register_and_get(self):
        """Basic registration and retrieval."""
        registry = SectionRegistry()
        registry.register(ReportType.KARTE, MockSection("test"))
        regs = registry.get_registrations(ReportType.KARTE)
        assert len(regs) == 1
        assert regs[0].section.section_id == "test"

    def test_duplicate_raises_error(self):
        """Duplicate section_id raises DuplicateSectionError."""
        registry = SectionRegistry()
        registry.register(ReportType.KARTE, MockSection("dup"))
        with pytest.raises(DuplicateSectionError):
            registry.register(ReportType.KARTE, MockSection("dup"))

    def test_same_id_different_types_ok(self):
        """Same section_id allowed for different report types."""
        registry = SectionRegistry()
        registry.register(ReportType.KARTE, MockSection("shared"))
        registry.register(ReportType.SUMMARY, MockSection("shared"))
        assert len(registry.get_registrations(ReportType.KARTE)) == 1
        assert len(registry.get_registrations(ReportType.SUMMARY)) == 1

    def test_clear(self):
        """Clear removes all registrations."""
        registry = SectionRegistry()
        registry.register(ReportType.KARTE, MockSection("test"))
        registry.clear()
        assert len(registry.get_registrations(ReportType.KARTE)) == 0

    def test_singleton_isolation(self):
        """Reset creates a new singleton instance."""
        reg1 = get_section_registry()
        reg1.register(ReportType.KARTE, MockSection("a"))
        _reset_section_registry_for_testing()
        reg2 = get_section_registry()
        assert reg1 is not reg2
        assert len(reg2.get_registrations(ReportType.KARTE)) == 0

    def test_registration_order_preserved(self):
        """Registrations are returned in registration order."""
        registry = SectionRegistry()
        registry.register(ReportType.KARTE, MockSection("first"))
        registry.register(ReportType.KARTE, MockSection("second"))
        ids = [r.section.section_id for r in registry.get_registrations(ReportType.KARTE)]
        assert ids == ["first", "second"]


class TestComputeSectionOrder:
    """Tests for compute_section_order function."""

    def test_append_when_after_is_none(self):
        """Sections with after_section_id=None are appended."""
        regs = [SectionRegistration(section=MockSection("new"), after_section_id=None)]
        ordered, warnings = compute_section_order(regs, ["meta", "summary"])
        assert [r.section.section_id for r in ordered] == ["new"]
        assert warnings == []

    def test_insert_after_base(self):
        """Sections are inserted after their anchor."""
        regs = [SectionRegistration(section=MockSection("style"), after_section_id="summary")]
        ordered, warnings = compute_section_order(regs, ["meta", "summary", "dist"])
        assert [r.section.section_id for r in ordered] == ["style"]
        assert ordered[0].after_section_id == "summary"
        assert warnings == []

    def test_stable_order_same_anchor(self):
        """Multiple sections with same anchor maintain registration order."""
        regs = [
            SectionRegistration(section=MockSection("first"), after_section_id="anchor"),
            SectionRegistration(section=MockSection("second"), after_section_id="anchor"),
            SectionRegistration(section=MockSection("third"), after_section_id="anchor"),
        ]
        ordered, warnings = compute_section_order(regs, ["anchor", "other"])
        ids = [r.section.section_id for r in ordered]
        assert ids == ["first", "second", "third"]
        assert warnings == []

    def test_chained_dependencies(self):
        """Chained dependencies are resolved correctly."""
        regs = [
            SectionRegistration(section=MockSection("c"), after_section_id="b"),
            SectionRegistration(section=MockSection("b"), after_section_id="a"),
            SectionRegistration(section=MockSection("a"), after_section_id=None),
        ]
        ordered, warnings = compute_section_order(regs, [])
        ids = [r.section.section_id for r in ordered]
        assert ids.index("a") < ids.index("b") < ids.index("c")
        assert warnings == []

    def test_after_not_found(self):
        """Missing anchor generates warning and appends at end."""
        regs = [SectionRegistration(section=MockSection("orphan"), after_section_id="nonexistent")]
        ordered, warnings = compute_section_order(regs, ["meta"])
        assert [r.section.section_id for r in ordered] == ["orphan"]
        assert len(warnings) == 1
        assert "Unresolved dependency: 'orphan' -> 'nonexistent'" in warnings[0]

    def test_cyclic_dependency(self):
        """Cyclic dependencies generate warnings and append at end."""
        regs = [
            SectionRegistration(section=MockSection("a"), after_section_id="b"),
            SectionRegistration(section=MockSection("b"), after_section_id="a"),
        ]
        ordered, warnings = compute_section_order(regs, [])
        assert len(ordered) == 2
        assert len(warnings) == 2
        assert all("Unresolved dependency:" in w for w in warnings)

    def test_duplicate_section_id_raises(self):
        """Duplicate section_id in registrations raises error."""
        regs = [
            SectionRegistration(section=MockSection("dup"), after_section_id=None),
            SectionRegistration(section=MockSection("dup"), after_section_id=None),
        ]
        with pytest.raises(DuplicateSectionError, match="Duplicate section_id 'dup'"):
            compute_section_order(regs, [])

    def test_disabled_excluded(self):
        """Disabled sections are excluded from output."""
        regs = [
            SectionRegistration(section=MockSection("enabled"), enabled_by_default=True),
            SectionRegistration(section=MockSection("disabled"), enabled_by_default=False),
        ]
        ordered, _ = compute_section_order(regs, [])
        assert [r.section.section_id for r in ordered] == ["enabled"]

    def test_base_collision_skipped(self):
        """Section colliding with base ID is skipped with warning."""
        regs = [
            SectionRegistration(section=MockSection("meta"), after_section_id=None),
            SectionRegistration(section=MockSection("new"), after_section_id=None),
        ]
        ordered, warnings = compute_section_order(regs, ["meta", "summary"])
        ids = [r.section.section_id for r in ordered]
        assert "meta" not in ids
        assert "new" in ids
        assert len(warnings) == 1
        assert "collides with base section ID" in warnings[0]


class TestLanguageWithSection:
    """Tests for language-aware section rendering."""

    def test_get_title_jp(self):
        """Japanese title includes Japanese text."""
        section = MockSection("style")
        assert "日本語" in section.get_title("jp")

    def test_get_title_en(self):
        """English title does not include Japanese text."""
        section = MockSection("style")
        assert "日本語" not in section.get_title("en")

    def test_normalized_ja_uses_jp(self):
        """Normalized 'ja' code uses 'jp' for rendering."""
        section = MockSection("style")
        lang = normalize_lang("ja")
        assert "日本語" in section.get_title(lang)
