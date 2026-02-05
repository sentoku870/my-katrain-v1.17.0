"""Tests for katrain.common.sanitize module.

Phase 29: Diagnostics + Bug Report Bundle.
"""

import json

import pytest

from katrain.common.sanitize import (
    SanitizationContext,
    _normalize_path,
    get_sanitization_context,
    sanitize_dict,
    sanitize_path,
    sanitize_text,
)

# --- Test fixtures (deterministic, CI-stable) ---
# These values are used for all tests to avoid environment dependency.
# Constraints: 4+ chars, no common words, include separator for hostname.

TEST_USERNAME = "TestUser"
TEST_HOSTNAME = "TEST-PC"
TEST_HOME_WIN = "C:\\Users\\TestUser"
TEST_HOME_UNIX = "/home/testuser"
TEST_APP_DIR = "D:\\apps\\katrain"

# Windows case variants
TEST_HOME_WIN_LOWER = "c:\\users\\testuser"
TEST_HOME_WIN_MIXED = "C:/Users/TestUser"


@pytest.fixture
def ctx_windows() -> SanitizationContext:
    """Windows-style sanitization context."""
    return SanitizationContext(
        username=TEST_USERNAME,
        hostname=TEST_HOSTNAME,
        home_dir=TEST_HOME_WIN,
        app_dir=TEST_APP_DIR,
    )


@pytest.fixture
def ctx_unix() -> SanitizationContext:
    """Unix-style sanitization context."""
    return SanitizationContext(
        username="testuser",
        hostname="test-server",
        home_dir=TEST_HOME_UNIX,
        app_dir="/opt/katrain",
    )


class TestSanitizePath:
    """Tests for sanitize_path function."""

    def test_replaces_home_dir_windows(self, ctx_windows: SanitizationContext) -> None:
        """Home directory is replaced with <USER_HOME>."""
        path = "C:\\Users\\TestUser\\Documents\\game.sgf"
        result = sanitize_path(path, ctx_windows)
        assert "<USER_HOME>" in result
        assert "TestUser" not in result

    def test_replaces_home_dir_unix(self, ctx_unix: SanitizationContext) -> None:
        """Unix home directory is replaced."""
        path = "/home/testuser/games/game.sgf"
        result = sanitize_path(path, ctx_unix)
        assert "<USER_HOME>" in result
        assert "testuser" not in result

    def test_replaces_app_dir(self, ctx_windows: SanitizationContext) -> None:
        """App directory is replaced with <APP_DIR>."""
        path = "D:\\apps\\katrain\\models\\kata1.gz"
        result = sanitize_path(path, ctx_windows)
        assert "<APP_DIR>" in result
        assert "katrain" not in result.replace("<APP_DIR>", "")

    def test_replaces_multiple_occurrences(self, ctx_windows: SanitizationContext) -> None:
        """Multiple occurrences of username in path are replaced."""
        path = "C:\\Users\\TestUser\\TestUser\\file.txt"
        result = sanitize_path(path, ctx_windows)
        assert "TestUser" not in result

    def test_handles_mixed_slashes(self, ctx_windows: SanitizationContext) -> None:
        """Mixed forward/backslashes are handled."""
        path = "C:/Users/TestUser\\Documents\\file.txt"
        result = sanitize_path(path, ctx_windows)
        assert "<USER_HOME>" in result or "<USER>" in result
        assert "TestUser" not in result

    def test_case_insensitive_windows(self, ctx_windows: SanitizationContext) -> None:
        """Case-insensitive matching on Windows."""
        path = "c:\\users\\testuser\\documents"
        result = sanitize_path(path, ctx_windows)
        # Should still sanitize even with different case
        assert "testuser" not in result.lower() or "<USER>" in result

    def test_trailing_slash_removed(self, ctx_windows: SanitizationContext) -> None:
        """Trailing slashes don't affect matching."""
        path = "C:\\Users\\TestUser\\"
        result = sanitize_path(path, ctx_windows)
        assert "TestUser" not in result

    def test_preserves_unrelated_paths(self, ctx_windows: SanitizationContext) -> None:
        """Paths not matching home/app dir are preserved."""
        path = "E:\\SomeOtherPath\\file.txt"
        result = sanitize_path(path, ctx_windows)
        assert "SomeOtherPath" in result

    def test_empty_path(self, ctx_windows: SanitizationContext) -> None:
        """Empty path returns empty string."""
        assert sanitize_path("", ctx_windows) == ""

    def test_unc_path_hostname_replaced(self, ctx_windows: SanitizationContext) -> None:
        """UNC path with matching hostname is sanitized."""
        path = "\\\\TEST-PC\\share\\file.txt"
        result = sanitize_path(path, ctx_windows)
        assert "<HOST>" in result
        assert "TEST-PC" not in result

    def test_unc_path_unrelated_host_preserved(self, ctx_windows: SanitizationContext) -> None:
        """UNC path with different hostname is preserved."""
        path = "\\\\OTHER-PC\\share\\file.txt"
        result = sanitize_path(path, ctx_windows)
        assert "OTHER-PC" in result
        assert "<HOST>" not in result


class TestSanitizeText:
    """Tests for sanitize_text function."""

    def test_replaces_username(self, ctx_windows: SanitizationContext) -> None:
        """Username in text is replaced with <USER>."""
        text = "User TestUser logged in successfully"
        result = sanitize_text(text, ctx_windows)
        assert "<USER>" in result
        assert "TestUser" not in result

    def test_replaces_hostname(self, ctx_windows: SanitizationContext) -> None:
        """Hostname in text is replaced with <HOST>."""
        text = "Connected to TEST-PC on port 8080"
        result = sanitize_text(text, ctx_windows)
        assert "<HOST>" in result
        assert "TEST-PC" not in result

    def test_replaces_path_in_text(self, ctx_windows: SanitizationContext) -> None:
        """Paths embedded in text are replaced."""
        text = f"Loading file from {TEST_HOME_WIN}\\game.sgf"
        result = sanitize_text(text, ctx_windows)
        assert "<USER_HOME>" in result or "<USER>" in result
        assert "TestUser" not in result

    def test_combined_replacements(self, ctx_windows: SanitizationContext) -> None:
        """Multiple sensitive items in text are all replaced."""
        text = f"User TestUser on TEST-PC loaded {TEST_HOME_WIN}"
        result = sanitize_text(text, ctx_windows)
        assert "TestUser" not in result
        assert "TEST-PC" not in result

    def test_unicode_preserved(self, ctx_windows: SanitizationContext) -> None:
        """Unicode characters are preserved."""
        text = "囲碁ゲーム by TestUser"
        result = sanitize_text(text, ctx_windows)
        assert "囲碁ゲーム" in result
        assert "<USER>" in result


class TestSanitizeDict:
    """Tests for sanitize_dict function."""

    def test_sanitizes_string_values(self, ctx_windows: SanitizationContext) -> None:
        """String values in dict are sanitized."""
        data = {"user": "TestUser", "host": "TEST-PC"}
        result = sanitize_dict(data, ctx_windows)
        assert result["user"] == "<USER>"
        assert result["host"] == "<HOST>"

    def test_preserves_non_string_values(self, ctx_windows: SanitizationContext) -> None:
        """Non-string values are preserved unchanged."""
        data = {
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
            "empty": None,
        }
        result = sanitize_dict(data, ctx_windows)
        assert result["count"] == 42
        assert result["ratio"] == 3.14
        assert result["enabled"] is True
        assert result["empty"] is None

    def test_recursive_nested_dict(self, ctx_windows: SanitizationContext) -> None:
        """Nested dicts are recursively sanitized."""
        data = {
            "level1": {
                "level2": {
                    "user": "TestUser",
                }
            }
        }
        result = sanitize_dict(data, ctx_windows)
        assert result["level1"]["level2"]["user"] == "<USER>"

    def test_list_of_strings(self, ctx_windows: SanitizationContext) -> None:
        """Lists of strings are sanitized."""
        data = {"users": ["TestUser", "OtherUser", "TestUser"]}
        result = sanitize_dict(data, ctx_windows)
        assert result["users"][0] == "<USER>"
        assert result["users"][1] == "OtherUser"
        assert result["users"][2] == "<USER>"

    def test_nested_list_of_dicts(self, ctx_windows: SanitizationContext) -> None:
        """Lists containing dicts are recursively sanitized."""
        data = {
            "items": [
                {"path": "C:\\Users\\TestUser\\file1.txt"},
                {"path": "C:\\Users\\TestUser\\file2.txt"},
            ]
        }
        result = sanitize_dict(data, ctx_windows)
        for item in result["items"]:
            assert "TestUser" not in item["path"]

    def test_output_is_json_valid(self, ctx_windows: SanitizationContext) -> None:
        """Sanitized dict can be serialized to valid JSON."""
        data = {
            "user": "TestUser",
            "path": "C:\\Users\\TestUser\\file.txt",
            "nested": {"host": "TEST-PC"},
            "list": ["TestUser", 123],
        }
        result = sanitize_dict(data, ctx_windows)

        # Should not raise
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)

        assert parsed["user"] == "<USER>"
        assert "TestUser" not in json_str


class TestGetSanitizationContext:
    """Tests for get_sanitization_context function."""

    def test_returns_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns a valid SanitizationContext."""
        monkeypatch.setenv("USERNAME", TEST_USERNAME)
        monkeypatch.setenv("USER", TEST_USERNAME)
        monkeypatch.setattr("socket.gethostname", lambda: TEST_HOSTNAME)

        ctx = get_sanitization_context(app_dir=TEST_APP_DIR)

        assert ctx.username == TEST_USERNAME
        assert ctx.hostname == TEST_HOSTNAME
        assert ctx.app_dir  # Should be set


class TestNormalizePath:
    """Tests for path normalization helper."""

    def test_converts_backslashes(self) -> None:
        """Backslashes are converted to forward slashes."""
        assert _normalize_path("C:\\Users\\Test") == "C:/Users/Test"

    def test_removes_trailing_slash(self) -> None:
        """Trailing slashes are removed."""
        assert _normalize_path("C:/Users/Test/") == "C:/Users/Test"

    def test_handles_mixed(self) -> None:
        """Mixed slashes are normalized."""
        assert _normalize_path("C:/Users\\Test/") == "C:/Users/Test"


class TestForbiddenTokenConstraints:
    """Verify test fixtures follow safety constraints."""

    def test_username_length(self) -> None:
        """Username is at least 4 characters to avoid false positives."""
        assert len(TEST_USERNAME) >= 4

    def test_hostname_length(self) -> None:
        """Hostname is at least 4 characters."""
        assert len(TEST_HOSTNAME) >= 4

    def test_hostname_has_separator(self) -> None:
        """Hostname contains separator to distinguish from common words."""
        assert "-" in TEST_HOSTNAME or "_" in TEST_HOSTNAME

    def test_username_not_common_word(self) -> None:
        """Username is not a common word that could cause false positives."""
        common_words = ["User", "Home", "Test", "Admin", "user", "home", "test", "admin"]
        assert TEST_USERNAME not in common_words
