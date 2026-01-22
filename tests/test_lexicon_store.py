"""
Tests for katrain.common.lexicon.store module.

Verifies:
- LexiconStore loading and validation
- Search operations (by ID, title, category, level)
- Error handling for invalid YAML
- Immutability of returned collections
- get_default_lexicon_path() function
"""

import os
from pathlib import Path

import pytest

from katrain.common.lexicon import get_default_lexicon_path
from katrain.common.lexicon.store import LexiconStore
from katrain.common.lexicon.validation import (
    LexiconNotLoadedError,
    LexiconParseError,
)
from katrain.common.lexicon.models import LexiconEntry


# ---------------------------------------------------------------------------
# Fixture Paths
# ---------------------------------------------------------------------------

# Use FIXTURES_DIR from conftest if available, otherwise define locally
try:
    from tests.conftest import FIXTURES_DIR
except ImportError:
    FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

LEXICON_FIXTURES_DIR = FIXTURES_DIR / "lexicon"


@pytest.fixture
def minimal_lexicon_path() -> Path:
    """Path to minimal valid lexicon fixture."""
    return LEXICON_FIXTURES_DIR / "minimal_valid.yaml"


@pytest.fixture
def invalid_syntax_path() -> Path:
    """Path to invalid YAML syntax fixture."""
    return LEXICON_FIXTURES_DIR / "invalid_yaml_syntax.yaml"


@pytest.fixture
def missing_entries_path() -> Path:
    """Path to YAML with missing entries key."""
    return LEXICON_FIXTURES_DIR / "missing_entries.yaml"


@pytest.fixture
def loaded_store(minimal_lexicon_path) -> LexiconStore:
    """A loaded LexiconStore for testing."""
    store = LexiconStore(minimal_lexicon_path)
    store.load()
    return store


# ---------------------------------------------------------------------------
# Basic Loading Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreLoading:
    """Tests for LexiconStore loading functionality."""

    def test_load_minimal_lexicon(self, minimal_lexicon_path):
        """Load minimal valid lexicon."""
        store = LexiconStore(minimal_lexicon_path)
        result = store.load()
        assert store.is_loaded
        assert result.entries_loaded == 3
        assert result.entries_skipped == 0
        assert not result.has_errors

    def test_not_loaded_before_load(self, minimal_lexicon_path):
        """Store is not loaded before load() is called."""
        store = LexiconStore(minimal_lexicon_path)
        assert not store.is_loaded

    def test_not_loaded_raises_error(self, minimal_lexicon_path):
        """Accessing store before load() raises LexiconNotLoadedError."""
        store = LexiconStore(minimal_lexicon_path)
        with pytest.raises(LexiconNotLoadedError):
            store.get("atari")

    def test_yaml_syntax_error_has_line_number(self, invalid_syntax_path):
        """YAML syntax error includes line number."""
        store = LexiconStore(invalid_syntax_path)
        with pytest.raises(LexiconParseError) as exc_info:
            store.load()
        assert exc_info.value.line is not None
        assert exc_info.value.line > 0

    def test_missing_entries_key_no_line_number(self, missing_entries_path):
        """Missing 'entries' key has no line number (schema error)."""
        store = LexiconStore(missing_entries_path)
        with pytest.raises(LexiconParseError) as exc_info:
            store.load()
        assert exc_info.value.line is None
        assert "entries" in str(exc_info.value).lower()

    def test_reload_lexicon(self, minimal_lexicon_path):
        """Can reload lexicon multiple times."""
        store = LexiconStore(minimal_lexicon_path)
        result1 = store.load()
        result2 = store.load()
        assert result1.entries_loaded == result2.entries_loaded


# ---------------------------------------------------------------------------
# Get by ID Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreGetById:
    """Tests for get() method."""

    def test_get_existing_entry(self, loaded_store):
        """Get existing entry by ID."""
        entry = loaded_store.get("atari")
        assert entry is not None
        assert entry.id == "atari"
        assert entry.ja_term == "アタリ"

    def test_get_nonexistent_entry(self, loaded_store):
        """Get nonexistent entry returns None."""
        entry = loaded_store.get("nonexistent")
        assert entry is None

    def test_get_all_entries_by_id(self, loaded_store):
        """Can get all entries by their IDs."""
        for entry_id in ["atari", "liberty", "tenuki-timing"]:
            entry = loaded_store.get(entry_id)
            assert entry is not None
            assert entry.id == entry_id


# ---------------------------------------------------------------------------
# Get by Title Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreGetByTitle:
    """Tests for get_by_title() method."""

    def test_get_by_ja_term(self, loaded_store):
        """Get entry by Japanese term."""
        entry = loaded_store.get_by_title("アタリ", "ja")
        assert entry is not None
        assert entry.id == "atari"

    def test_get_by_ja_title(self, loaded_store):
        """Get entry by Japanese title (Level 3)."""
        entry = loaded_store.get_by_title("手抜きのタイミング", "ja")
        assert entry is not None
        assert entry.id == "tenuki-timing"

    def test_get_by_en_term(self, loaded_store):
        """Get entry by English term."""
        entry = loaded_store.get_by_title("atari", "en")
        assert entry is not None
        assert entry.id == "atari"

    def test_get_by_en_term_case_insensitive(self, loaded_store):
        """English title search is case insensitive."""
        entry = loaded_store.get_by_title("ATARI", "en")
        assert entry is not None
        assert entry.id == "atari"

    def test_get_by_en_title(self, loaded_store):
        """Get entry by English title (Level 3)."""
        entry = loaded_store.get_by_title("When to Tenuki", "en")
        assert entry is not None
        assert entry.id == "tenuki-timing"

    def test_get_by_multiple_en_terms(self, loaded_store):
        """Can find entry by any of its English terms."""
        # liberty has multiple en_terms: [liberty, liberties]
        entry1 = loaded_store.get_by_title("liberty", "en")
        entry2 = loaded_store.get_by_title("liberties", "en")
        assert entry1 is not None
        assert entry2 is not None
        assert entry1.id == entry2.id == "liberty"

    def test_get_by_title_not_found(self, loaded_store):
        """Get by title returns None if not found."""
        entry = loaded_store.get_by_title("nonexistent", "ja")
        assert entry is None

    def test_get_by_title_invalid_lang(self, loaded_store):
        """Invalid lang raises ValueError."""
        with pytest.raises(ValueError):
            loaded_store.get_by_title("atari", "ko")


# ---------------------------------------------------------------------------
# Get by Category Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreGetByCategory:
    """Tests for get_by_category() method."""

    def test_get_by_category(self, loaded_store):
        """Get entries by category."""
        rules_entries = loaded_store.get_by_category("rules")
        assert len(rules_entries) == 2
        assert all(e.category == "rules" for e in rules_entries)

    def test_get_by_category_empty(self, loaded_store):
        """Get by category returns empty tuple if not found."""
        entries = loaded_store.get_by_category("nonexistent")
        assert entries == ()

    def test_get_by_category_returns_tuple(self, loaded_store):
        """get_by_category returns a tuple."""
        entries = loaded_store.get_by_category("rules")
        assert isinstance(entries, tuple)


# ---------------------------------------------------------------------------
# Get by Level Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreGetByLevel:
    """Tests for get_by_level() method."""

    def test_get_by_level_1(self, loaded_store):
        """Get Level 1 entries."""
        entries = loaded_store.get_by_level(1)
        assert len(entries) == 1
        assert entries[0].id == "atari"

    def test_get_by_level_2(self, loaded_store):
        """Get Level 2 entries."""
        entries = loaded_store.get_by_level(2)
        assert len(entries) == 1
        assert entries[0].id == "liberty"

    def test_get_by_level_3(self, loaded_store):
        """Get Level 3 entries."""
        entries = loaded_store.get_by_level(3)
        assert len(entries) == 1
        assert entries[0].id == "tenuki-timing"

    def test_get_by_level_returns_tuple(self, loaded_store):
        """get_by_level returns a tuple."""
        entries = loaded_store.get_by_level(1)
        assert isinstance(entries, tuple)

    def test_get_by_invalid_level(self, loaded_store):
        """Get by invalid level returns empty tuple."""
        entries = loaded_store.get_by_level(99)
        assert entries == ()


# ---------------------------------------------------------------------------
# All Entries and Categories Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreAllEntries:
    """Tests for all_entries and all_categories properties."""

    def test_all_entries(self, loaded_store):
        """all_entries returns all loaded entries."""
        entries = loaded_store.all_entries
        assert len(entries) == 3

    def test_all_entries_is_tuple(self, loaded_store):
        """all_entries returns a tuple."""
        entries = loaded_store.all_entries
        assert isinstance(entries, tuple)

    def test_all_categories(self, loaded_store):
        """all_categories returns all category names."""
        categories = loaded_store.all_categories
        assert "rules" in categories
        assert "urgency" in categories

    def test_all_categories_is_frozenset(self, loaded_store):
        """all_categories returns a frozenset."""
        categories = loaded_store.all_categories
        assert isinstance(categories, frozenset)

    def test_len(self, loaded_store):
        """len() returns number of entries."""
        assert len(loaded_store) == 3


# ---------------------------------------------------------------------------
# Immutability Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreImmutability:
    """Tests for immutability of returned data."""

    def test_entry_is_frozen(self, loaded_store):
        """Entry is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        entry = loaded_store.get("atari")
        assert entry is not None
        with pytest.raises(FrozenInstanceError):
            entry.id = "modified"  # type: ignore

    def test_entry_tuple_fields_immutable(self, loaded_store):
        """Entry tuple fields are immutable."""
        entry = loaded_store.get("atari")
        assert entry is not None
        assert isinstance(entry.en_terms, tuple)
        # Tuples don't have append
        assert not hasattr(entry.en_terms, "append")

    def test_all_entries_is_immutable(self, loaded_store):
        """all_entries returns immutable tuple."""
        entries = loaded_store.all_entries
        assert isinstance(entries, tuple)
        with pytest.raises(TypeError):
            entries[0] = None  # type: ignore

    def test_all_categories_is_immutable(self, loaded_store):
        """all_categories returns immutable frozenset."""
        categories = loaded_store.all_categories
        assert isinstance(categories, frozenset)
        # frozensets don't have add
        assert not hasattr(categories, "add")

    def test_get_by_category_returns_immutable(self, loaded_store):
        """get_by_category returns immutable tuple."""
        entries = loaded_store.get_by_category("rules")
        assert isinstance(entries, tuple)
        with pytest.raises(TypeError):
            entries[0] = None  # type: ignore


# ---------------------------------------------------------------------------
# Validation and Error Tests
# ---------------------------------------------------------------------------


class TestLexiconStoreValidation:
    """Tests for validation during load."""

    def test_duplicate_id_skipped(self, tmp_path):
        """Duplicate IDs are skipped with error."""
        yaml_content = """
entries:
  - id: test
    level: 1
    category: test
    ja_term: テスト1
    en_terms: [test1]
    ja_one_liner: テスト1
    en_one_liner: Test 1
    ja_short: テスト1
    en_short: Test 1
    sources: [https://example.com]
  - id: test
    level: 1
    category: test
    ja_term: テスト2
    en_terms: [test2]
    ja_one_liner: テスト2
    en_one_liner: Test 2
    ja_short: テスト2
    en_short: Test 2
    sources: [https://example.com]
"""
        yaml_path = tmp_path / "duplicate.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        store = LexiconStore(yaml_path)
        result = store.load()

        assert result.entries_loaded == 1
        assert result.entries_skipped == 1
        assert result.has_errors

    def test_invalid_entry_skipped(self, tmp_path):
        """Invalid entries are skipped."""
        yaml_content = """
entries:
  - id: valid
    level: 1
    category: test
    ja_term: 有効
    en_terms: [valid]
    ja_one_liner: 有効
    en_one_liner: Valid
    ja_short: 有効
    en_short: Valid
    sources: [https://example.com]
  - id: invalid
    level: 99
    category: test
    ja_term: 無効
    en_terms: [invalid]
    ja_one_liner: 無効
    en_one_liner: Invalid
    ja_short: 無効
    en_short: Invalid
    sources: [https://example.com]
"""
        yaml_path = tmp_path / "invalid_entry.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        store = LexiconStore(yaml_path)
        result = store.load()

        assert result.entries_loaded == 1
        assert result.entries_skipped == 1
        assert result.has_errors

    def test_unknown_reference_warning(self, tmp_path):
        """Unknown ID references produce warnings."""
        yaml_content = """
entries:
  - id: test
    level: 1
    category: test
    ja_term: テスト
    en_terms: [test]
    ja_one_liner: テスト
    en_one_liner: Test
    ja_short: テスト
    en_short: Test
    sources: [https://example.com]
    related_ids: [nonexistent]
"""
        yaml_path = tmp_path / "unknown_ref.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        store = LexiconStore(yaml_path)
        result = store.load()

        assert result.entries_loaded == 1
        assert result.has_warnings
        assert any("nonexistent" in issue.message for issue in result.issues)

    def test_title_collision_warning(self, tmp_path):
        """Title collisions produce warnings."""
        yaml_content = """
entries:
  - id: test1
    level: 1
    category: test
    ja_term: 同じ名前
    en_terms: [same]
    ja_one_liner: テスト1
    en_one_liner: Test 1
    ja_short: テスト1
    en_short: Test 1
    sources: [https://example.com]
  - id: test2
    level: 1
    category: test
    ja_term: 同じ名前
    en_terms: [different]
    ja_one_liner: テスト2
    en_one_liner: Test 2
    ja_short: テスト2
    en_short: Test 2
    sources: [https://example.com]
"""
        yaml_path = tmp_path / "collision.yaml"
        yaml_path.write_text(yaml_content, encoding="utf-8")

        store = LexiconStore(yaml_path)
        result = store.load()

        # Both should load (first wins for title collision)
        assert result.entries_loaded == 2
        assert result.has_warnings
        assert any("collision" in issue.message.lower() for issue in result.issues)

        # First entry wins for title lookup
        entry = store.get_by_title("同じ名前", "ja")
        assert entry is not None
        assert entry.id == "test1"


# ---------------------------------------------------------------------------
# Slow Integration Tests (require RUN_SLOW_TESTS=1)
# ---------------------------------------------------------------------------

SKIP_SLOW = os.environ.get("RUN_SLOW_TESTS", "").lower() not in ("1", "true", "yes")


@pytest.mark.skipif(SKIP_SLOW, reason="Slow test: set RUN_SLOW_TESTS=1 to run")
class TestLexiconStoreIntegration:
    """Integration tests with the real lexicon file."""

    @pytest.fixture
    def real_lexicon_path(self) -> Path:
        """Path to the real lexicon file."""
        # repo_root/docs/resources/go_lexicon_master_last.yaml
        repo_root = Path(__file__).resolve().parent.parent
        return repo_root / "docs" / "resources" / "go_lexicon_master_last.yaml"

    def test_load_full_lexicon_no_errors(self, real_lexicon_path):
        """Load the full lexicon without errors."""
        if not real_lexicon_path.exists():
            pytest.skip(f"Real lexicon not found: {real_lexicon_path}")

        store = LexiconStore(real_lexicon_path)
        result = store.load()

        assert not result.has_errors, f"Has errors:\n{result.format_report()}"
        assert result.entries_loaded > 0

    def test_load_full_lexicon_counts_match_yaml(self, real_lexicon_path):
        """Integration test: store counts exactly match YAML source."""
        import yaml

        if not real_lexicon_path.exists():
            pytest.skip(f"Real lexicon not found: {real_lexicon_path}")

        # Parse YAML directly
        with open(real_lexicon_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        raw_entries = raw_data.get("entries", [])
        expected_total = len(raw_entries)
        expected_by_level = {1: 0, 2: 0, 3: 0}
        for entry in raw_entries:
            level = entry.get("level")
            if level in expected_by_level:
                expected_by_level[level] += 1

        # Load via LexiconStore
        store = LexiconStore(real_lexicon_path)
        result = store.load()

        # Precondition: no errors
        assert not result.has_errors, f"Has errors:\n{result.format_report()}"

        # Exact assertions
        assert len(store) == expected_total
        assert result.entries_loaded == expected_total

        for level in [1, 2, 3]:
            actual = len(store.get_by_level(level))
            expected = expected_by_level[level]
            assert actual == expected, f"Level {level}: {actual} != {expected}"


# ---------------------------------------------------------------------------
# get_default_lexicon_path Tests
# ---------------------------------------------------------------------------


class TestGetDefaultLexiconPath:
    """Tests for get_default_lexicon_path function."""

    def test_returns_path(self):
        """get_default_lexicon_path returns a Path object."""
        path = get_default_lexicon_path()
        assert isinstance(path, Path)

    def test_path_exists(self):
        """Default lexicon path exists."""
        path = get_default_lexicon_path()
        assert path.exists(), f"Expected path to exist: {path}"

    def test_path_is_yaml(self):
        """Default path is a YAML file."""
        path = get_default_lexicon_path()
        assert path.suffix in (".yaml", ".yml")

    def test_env_var_override(self, tmp_path, monkeypatch):
        """LEXICON_PATH environment variable overrides default."""
        # Create a temporary YAML file
        temp_yaml = tmp_path / "custom_lexicon.yaml"
        temp_yaml.write_text("entries: []", encoding="utf-8")

        # Set environment variable
        monkeypatch.setenv("LEXICON_PATH", str(temp_yaml))

        path = get_default_lexicon_path()
        assert path == temp_yaml

    def test_env_var_nonexistent_raises(self, monkeypatch):
        """LEXICON_PATH pointing to nonexistent file raises FileNotFoundError."""
        monkeypatch.setenv("LEXICON_PATH", "/nonexistent/path/lexicon.yaml")

        with pytest.raises(FileNotFoundError) as exc_info:
            get_default_lexicon_path()

        assert "LEXICON_PATH" in str(exc_info.value)

    def test_env_var_empty_uses_default(self, monkeypatch):
        """Empty LEXICON_PATH uses default path."""
        monkeypatch.setenv("LEXICON_PATH", "")

        path = get_default_lexicon_path()
        assert path.exists()

    def test_loadable_by_store(self):
        """Default lexicon path is loadable by LexiconStore."""
        path = get_default_lexicon_path()
        store = LexiconStore(path)
        result = store.load()

        assert not result.has_errors, f"Load errors:\n{result.format_report()}"
        assert result.entries_loaded > 0
