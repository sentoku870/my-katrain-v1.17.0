"""Tests for katrain.common.model_labels module.

CI-safe: No Kivy imports.
"""
import pytest
from katrain.common.model_labels import (
    classify_model_strength,
    get_model_i18n_key,
    get_model_basename,
)


class TestClassifyModelStrength:
    def test_light_model(self):
        assert classify_model_strength("kata1-b10c128-xxx.bin.gz") == "light"

    def test_standard_model(self):
        assert classify_model_strength("kata1-b18c384nbt-xxx.bin.gz") == "standard"

    def test_strong_model_b28(self):
        assert classify_model_strength("kata1-b28c512-xxx.bin.gz") == "strong"

    def test_strong_model_b40(self):
        assert classify_model_strength("kata1-b40c256-xxx.bin.gz") == "strong"

    def test_unknown_model(self):
        assert classify_model_strength("custom-model.bin.gz") == "unknown"

    def test_empty_path(self):
        assert classify_model_strength("") == "unknown"

    def test_windows_full_path(self):
        assert classify_model_strength(r"C:\models\kata1-b18c384.bin.gz") == "standard"

    def test_unix_full_path(self):
        assert classify_model_strength("/home/user/kata1-b10c128.bin.gz") == "light"

    def test_case_insensitive(self):
        assert classify_model_strength("KATA1-B18C384.BIN.GZ") == "standard"


class TestGetModelI18nKey:
    def test_light_key(self):
        assert get_model_i18n_key("kata1-b10c128.bin.gz") == "model:light"

    def test_unknown_key(self):
        assert get_model_i18n_key("unknown.bin.gz") == "model:unknown"

    def test_empty_path_key(self):
        assert get_model_i18n_key("") == "model:unknown"


class TestGetModelBasename:
    """Cross-platform basename tests.

    These tests verify Windows paths work correctly on Linux CI.
    os.path.basename("C:\\models\\file.bin") returns the whole string on Linux,
    so we use _cross_platform_basename internally.
    """

    def test_windows_path_on_any_os(self):
        # This must pass on Linux CI (backslash handling)
        assert get_model_basename(r"C:\models\kata1.bin.gz") == "kata1.bin.gz"

    def test_windows_path_deep_nesting(self):
        assert get_model_basename(r"D:\foo\bar\baz\model.bin") == "model.bin"

    def test_unix_path(self):
        assert get_model_basename("/home/user/kata1.bin.gz") == "kata1.bin.gz"

    def test_unix_path_deep_nesting(self):
        assert get_model_basename("/a/b/c/d/model.bin") == "model.bin"

    def test_filename_only(self):
        assert get_model_basename("kata1.bin.gz") == "kata1.bin.gz"

    def test_empty_path(self):
        assert get_model_basename("") == ""

    def test_mixed_separators(self):
        # Forward slash after backslash - uses rightmost separator
        assert get_model_basename(r"C:\models/subdir/file.bin") == "file.bin"


class TestCrossPlatformInClassify:
    """Verify classify_model_strength uses cross-platform basename."""

    def test_windows_path_classification(self):
        # Must work on Linux CI
        assert classify_model_strength(r"C:\models\kata1-b18c384.bin.gz") == "standard"
        assert classify_model_strength(r"D:\foo\bar\kata1-b10c128.bin") == "light"
