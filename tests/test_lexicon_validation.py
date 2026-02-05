"""
Tests for katrain.common.lexicon.validation module.

Verifies:
- Two-stage validation pipeline
- Field type and requirement validation
- ID format validation
- Level-specific field requirements
- Reference validation
- Exception classes
"""

import pytest

from katrain.common.lexicon.models import LexiconEntry
from katrain.common.lexicon.validation import (
    LexiconError,
    LexiconNotLoadedError,
    LexiconParseError,
    ValidationIssue,
    ValidationResult,
    build_entry_from_dict,
    validate_entry_dict,
    validate_references,
)

# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestLexiconParseError:
    """Tests for LexiconParseError exception."""

    def test_without_line_number(self):
        """Error message without line number."""
        err = LexiconParseError("Missing 'entries' key")
        assert str(err) == "Missing 'entries' key"
        assert err.line is None
        assert err.column is None

    def test_with_line_number(self):
        """Error message with line number."""
        err = LexiconParseError("YAML syntax error", line=42)
        assert str(err) == "YAML syntax error (line 42)"
        assert err.line == 42
        assert err.column is None

    def test_with_line_and_column(self):
        """Error message with line and column."""
        err = LexiconParseError("YAML syntax error", line=42, column=10)
        assert str(err) == "YAML syntax error (line 42, column 10)"
        assert err.line == 42
        assert err.column == 10

    def test_inheritance(self):
        """LexiconParseError inherits from LexiconError."""
        assert issubclass(LexiconParseError, LexiconError)
        assert issubclass(LexiconParseError, Exception)


class TestLexiconNotLoadedError:
    """Tests for LexiconNotLoadedError exception."""

    def test_inheritance(self):
        """LexiconNotLoadedError inherits from LexiconError."""
        assert issubclass(LexiconNotLoadedError, LexiconError)
        assert issubclass(LexiconNotLoadedError, Exception)


# ---------------------------------------------------------------------------
# ValidationIssue Tests
# ---------------------------------------------------------------------------


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_error_issue(self):
        """Create an error issue."""
        issue = ValidationIssue(
            entry_index=0,
            entry_id="atari",
            field="level",
            message="Must be 1, 2, or 3",
            is_error=True,
        )
        assert issue.is_error is True
        assert issue.entry_id == "atari"
        assert issue.field == "level"

    def test_warning_issue(self):
        """Create a warning issue."""
        issue = ValidationIssue(
            entry_index=0,
            entry_id="atari",
            field="sources",
            message="Recommended field is empty",
            is_error=False,
        )
        assert issue.is_error is False

    def test_issue_without_entry_id(self):
        """Issue when entry ID is not available."""
        issue = ValidationIssue(
            entry_index=5,
            entry_id=None,
            field="id",
            message="ID is missing",
            is_error=True,
        )
        assert issue.entry_id is None
        assert issue.entry_index == 5


# ---------------------------------------------------------------------------
# ValidationResult Tests
# ---------------------------------------------------------------------------


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_empty_result(self):
        """Empty result has no issues."""
        result = ValidationResult()
        assert result.issues == []
        assert result.entries_loaded == 0
        assert result.entries_skipped == 0
        assert result.has_errors is False
        assert result.has_warnings is False
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_result_with_errors(self):
        """Result with errors."""
        result = ValidationResult(
            issues=[
                ValidationIssue(0, "test", "id", "error", is_error=True),
                ValidationIssue(1, "test2", "level", "error", is_error=True),
            ],
            entries_loaded=5,
            entries_skipped=2,
        )
        assert result.has_errors is True
        assert result.error_count == 2
        assert result.warning_count == 0

    def test_result_with_warnings(self):
        """Result with warnings only."""
        result = ValidationResult(
            issues=[
                ValidationIssue(0, "test", "sources", "warning", is_error=False),
            ],
            entries_loaded=10,
            entries_skipped=0,
        )
        assert result.has_errors is False
        assert result.has_warnings is True
        assert result.error_count == 0
        assert result.warning_count == 1

    def test_format_report(self):
        """Format report includes all information."""
        result = ValidationResult(
            issues=[
                ValidationIssue(0, "atari", "sources", "Recommended field is empty", is_error=False),
                ValidationIssue(1, None, "id", "ID is missing", is_error=True),
            ],
            entries_loaded=9,
            entries_skipped=1,
        )
        report = result.format_report()
        assert "Loaded: 9" in report
        assert "Skipped: 1" in report
        assert "Errors: 1" in report
        assert "Warnings: 1" in report
        assert "[WARN] atari.sources" in report
        assert "[ERROR] index 1.id" in report


# ---------------------------------------------------------------------------
# validate_entry_dict Tests
# ---------------------------------------------------------------------------


class TestValidateEntryDict:
    """Tests for validate_entry_dict function."""

    @pytest.fixture
    def valid_level1_dict(self) -> dict:
        """Minimal valid Level 1 entry dict."""
        return {
            "id": "atari",
            "level": 1,
            "category": "rules",
            "ja_term": "アタリ",
            "en_terms": ["atari"],
            "ja_one_liner": "次に取れる状態",
            "en_one_liner": "A stone in immediate danger of capture.",
            "ja_short": "相手の石を次の一手で取れる状態。",
            "en_short": "When a stone has only one liberty left.",
            "sources": ["https://example.com"],
        }

    @pytest.fixture
    def valid_level3_dict(self) -> dict:
        """Valid Level 3 entry dict."""
        return {
            "id": "tenuki-timing",
            "level": 3,
            "category": "urgency",
            "ja_term": "手抜き",
            "en_terms": ["tenuki"],
            "ja_one_liner": "相手の手を無視する判断",
            "en_one_liner": "Deciding when to ignore opponent's move.",
            "ja_short": "局面の緊急度を判断する技術。",
            "en_short": "The skill of judging position urgency.",
            "ja_title": "手抜きのタイミング",
            "en_title": "When to Tenuki",
            "ja_expanded": "詳細な説明。",
            "en_expanded": "Detailed explanation.",
            "decision_checklist": ["Check local stability"],
            "signals": ["Opponent's move is slow"],
            "common_failure_modes": ["Ignoring urgent moves"],
            "drills": ["Practice with pro games"],
            "sources": ["https://example.com"],
        }

    def test_valid_level1_entry(self, valid_level1_dict):
        """Valid Level 1 entry produces no errors."""
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error]
        assert len(errors) == 0

    def test_valid_level3_entry(self, valid_level3_dict):
        """Valid Level 3 entry produces no errors."""
        issues = validate_entry_dict(valid_level3_dict, 0)
        errors = [i for i in issues if i.is_error]
        assert len(errors) == 0

    def test_not_a_dict(self):
        """Non-dict entry produces error."""
        issues = validate_entry_dict("not a dict", 0)
        assert len(issues) == 1
        assert issues[0].is_error is True
        assert "must be a dict" in issues[0].message

    def test_missing_id(self, valid_level1_dict):
        """Missing ID produces error."""
        del valid_level1_dict["id"]
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "id"]
        assert len(errors) == 1

    def test_empty_id(self, valid_level1_dict):
        """Empty ID produces error."""
        valid_level1_dict["id"] = ""
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "id"]
        assert len(errors) == 1

    def test_invalid_id_format(self, valid_level1_dict):
        """Invalid ID format produces error."""
        valid_level1_dict["id"] = "Atari"  # Uppercase not allowed
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "id"]
        assert len(errors) == 1
        assert "lowercase" in errors[0].message.lower()

    def test_invalid_id_with_space(self, valid_level1_dict):
        """ID with space is invalid."""
        valid_level1_dict["id"] = "tenuki timing"  # Space not allowed
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "id"]
        assert len(errors) == 1

    def test_valid_id_formats(self, valid_level1_dict):
        """Valid ID formats are accepted (kebab-case and snake_case)."""
        for valid_id in ["atari", "tenuki-timing", "level-3-concept", "a1-b2", "ko_threat_lv1", "two_eyes"]:
            valid_level1_dict["id"] = valid_id
            issues = validate_entry_dict(valid_level1_dict, 0)
            errors = [i for i in issues if i.is_error and i.field == "id"]
            assert len(errors) == 0, f"ID '{valid_id}' should be valid"

    def test_invalid_level(self, valid_level1_dict):
        """Invalid level produces error."""
        valid_level1_dict["level"] = 5
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "level"]
        assert len(errors) == 1
        assert "must be 1, 2, or 3" in errors[0].message

    def test_wrong_type_level(self, valid_level1_dict):
        """Wrong type for level produces error."""
        valid_level1_dict["level"] = "one"
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "level"]
        assert len(errors) >= 1

    def test_empty_en_terms(self, valid_level1_dict):
        """Empty en_terms produces error."""
        valid_level1_dict["en_terms"] = []
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "en_terms"]
        assert len(errors) == 1

    def test_en_terms_with_empty_string(self, valid_level1_dict):
        """en_terms with empty string produces error."""
        valid_level1_dict["en_terms"] = ["atari", ""]
        issues = validate_entry_dict(valid_level1_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "en_terms"]
        assert len(errors) == 1
        assert "non-empty strings" in errors[0].message

    def test_sources_empty_warning(self, valid_level1_dict):
        """Empty sources produces warning (not error)."""
        valid_level1_dict["sources"] = []
        issues = validate_entry_dict(valid_level1_dict, 0)
        warnings = [i for i in issues if not i.is_error and i.field == "sources"]
        errors = [i for i in issues if i.is_error and i.field == "sources"]
        assert len(warnings) == 1
        assert len(errors) == 0

    def test_sources_missing_warning(self, valid_level1_dict):
        """Missing sources produces warning (not error)."""
        del valid_level1_dict["sources"]
        issues = validate_entry_dict(valid_level1_dict, 0)
        warnings = [i for i in issues if not i.is_error and i.field == "sources"]
        errors = [i for i in issues if i.is_error and i.field == "sources"]
        assert len(warnings) == 1
        assert len(errors) == 0

    def test_related_ids_missing_ok(self, valid_level1_dict):
        """Missing related_ids is OK (no error, no warning)."""
        # related_ids is not in valid_level1_dict by default
        issues = validate_entry_dict(valid_level1_dict, 0)
        related_issues = [i for i in issues if i.field == "related_ids"]
        assert len(related_issues) == 0

    def test_level3_missing_title_error(self, valid_level3_dict):
        """Level 3 without ja_title produces error."""
        del valid_level3_dict["ja_title"]
        issues = validate_entry_dict(valid_level3_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "ja_title"]
        assert len(errors) == 1

    def test_level3_missing_expanded_error(self, valid_level3_dict):
        """Level 3 without ja_expanded produces error."""
        del valid_level3_dict["ja_expanded"]
        issues = validate_entry_dict(valid_level3_dict, 0)
        errors = [i for i in issues if i.is_error and i.field == "ja_expanded"]
        assert len(errors) == 1

    def test_level1_no_title_ok(self, valid_level1_dict):
        """Level 1 without ja_title is OK."""
        issues = validate_entry_dict(valid_level1_dict, 0)
        title_errors = [i for i in issues if i.is_error and i.field == "ja_title"]
        assert len(title_errors) == 0

    def test_level3_empty_signals_warning(self, valid_level3_dict):
        """Level 3 with empty signals produces warning."""
        valid_level3_dict["signals"] = []
        issues = validate_entry_dict(valid_level3_dict, 0)
        warnings = [i for i in issues if not i.is_error and i.field == "signals"]
        assert len(warnings) == 1


# ---------------------------------------------------------------------------
# build_entry_from_dict Tests
# ---------------------------------------------------------------------------


class TestBuildEntryFromDict:
    """Tests for build_entry_from_dict function."""

    @pytest.fixture
    def valid_dict(self) -> dict:
        """Valid entry dict."""
        return {
            "id": "atari",
            "level": 1,
            "category": "rules",
            "ja_term": "アタリ",
            "en_terms": ["atari", "check"],
            "ja_one_liner": "次に取れる状態",
            "en_one_liner": "A stone in immediate danger of capture.",
            "ja_short": "相手の石を次の一手で取れる状態。",
            "en_short": "When a stone has only one liberty left.",
            "sources": ["https://example.com"],
            "related_ids": ["liberty"],
        }

    def test_builds_entry(self, valid_dict):
        """Build entry from valid dict."""
        entry = build_entry_from_dict(valid_dict)
        assert isinstance(entry, LexiconEntry)
        assert entry.id == "atari"
        assert entry.level == 1

    def test_converts_lists_to_tuples(self, valid_dict):
        """Lists in dict are converted to tuples."""
        entry = build_entry_from_dict(valid_dict)
        assert isinstance(entry.en_terms, tuple)
        assert entry.en_terms == ("atari", "check")
        assert isinstance(entry.sources, tuple)
        assert isinstance(entry.related_ids, tuple)

    def test_missing_optional_uses_defaults(self, valid_dict):
        """Missing optional fields use defaults."""
        del valid_dict["related_ids"]
        entry = build_entry_from_dict(valid_dict)
        assert entry.related_ids == ()
        assert entry.ja_title == ""
        assert entry.diagram is None

    def test_builds_diagram_info(self, valid_dict):
        """DiagramInfo is built from dict."""
        valid_dict["diagram"] = {
            "setup": ["D4", "Q16"],
            "annotation": "Corner approach",
        }
        entry = build_entry_from_dict(valid_dict)
        assert entry.diagram is not None
        assert entry.diagram.setup == ("D4", "Q16")
        assert entry.diagram.annotation == "Corner approach"

    def test_builds_ai_perspective(self, valid_dict):
        """AIPerspective is built from dict."""
        valid_dict["ai_perspective"] = {
            "has_difference": True,
            "summary": "AI prefers aggressive play",
        }
        entry = build_entry_from_dict(valid_dict)
        assert entry.ai_perspective is not None
        assert entry.ai_perspective.has_difference is True
        assert entry.ai_perspective.summary == "AI prefers aggressive play"

    def test_handles_none_values(self, valid_dict):
        """None values are converted to defaults."""
        valid_dict["sources"] = None
        valid_dict["ja_title"] = None
        entry = build_entry_from_dict(valid_dict)
        assert entry.sources == ()
        assert entry.ja_title == ""


# ---------------------------------------------------------------------------
# validate_references Tests
# ---------------------------------------------------------------------------


class TestValidateReferences:
    """Tests for validate_references function."""

    @pytest.fixture
    def entries(self) -> list:
        """Create test entries."""
        return [
            LexiconEntry(
                id="atari",
                level=1,
                category="rules",
                ja_term="アタリ",
                en_terms=("atari",),
                ja_one_liner="Test",
                en_one_liner="Test",
                ja_short="Test",
                en_short="Test",
                related_ids=("liberty",),
            ),
            LexiconEntry(
                id="liberty",
                level=1,
                category="rules",
                ja_term="呼吸点",
                en_terms=("liberty",),
                ja_one_liner="Test",
                en_one_liner="Test",
                ja_short="Test",
                en_short="Test",
                related_ids=("atari",),
            ),
        ]

    def test_valid_references(self, entries):
        """Valid references produce no issues."""
        known_ids = {"atari", "liberty"}
        issues = validate_references(entries, known_ids)
        assert len(issues) == 0

    def test_unknown_related_id(self, entries):
        """Unknown related_id produces warning."""
        entries[0] = LexiconEntry(
            id="atari",
            level=1,
            category="rules",
            ja_term="アタリ",
            en_terms=("atari",),
            ja_one_liner="Test",
            en_one_liner="Test",
            ja_short="Test",
            en_short="Test",
            related_ids=("unknown-id",),
        )
        known_ids = {"atari", "liberty"}
        issues = validate_references(entries, known_ids)
        assert len(issues) == 1
        assert issues[0].field == "related_ids"
        assert issues[0].is_error is False
        assert "unknown-id" in issues[0].message

    def test_unknown_prerequisites(self):
        """Unknown prerequisites produces warning."""
        entries = [
            LexiconEntry(
                id="advanced",
                level=3,
                category="strategy",
                ja_term="応用",
                en_terms=("advanced",),
                ja_one_liner="Test",
                en_one_liner="Test",
                ja_short="Test",
                en_short="Test",
                ja_title="Advanced",
                en_title="Advanced",
                ja_expanded="Test",
                en_expanded="Test",
                prerequisites=("nonexistent",),
            ),
        ]
        known_ids = {"advanced"}
        issues = validate_references(entries, known_ids)
        assert len(issues) == 1
        assert issues[0].field == "prerequisites"

    def test_unknown_contrast_with(self):
        """Unknown contrast_with produces warning."""
        entries = [
            LexiconEntry(
                id="offense",
                level=2,
                category="strategy",
                ja_term="攻め",
                en_terms=("offense",),
                ja_one_liner="Test",
                en_one_liner="Test",
                ja_short="Test",
                en_short="Test",
                contrast_with=("defense-nonexistent",),
            ),
        ]
        known_ids = {"offense"}
        issues = validate_references(entries, known_ids)
        assert len(issues) == 1
        assert issues[0].field == "contrast_with"
