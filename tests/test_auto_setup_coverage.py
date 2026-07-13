"""Phase A2: Auto Setup module coverage tests.

Architecture Review follow-up: ``core/auto_setup.py`` was at 9.8%
coverage (36/368 lines) — the lowest of the production core files at
the time of the review. This file raises that to a comfortable level by
exercising every public function plus the helpers used by them.

The module is pure-function style (no classes), with three places that
touch the filesystem:

- ``get_model_search_dirs`` / ``find_lightweight_model`` — read the
  user / package ``models`` directories.
- ``find_cpu_katago`` — search the package ``KataGo`` directory.
- ``_get_packaged_defaults`` — load the bundled ``config.json``.

We avoid those real paths in tests by:

- patching ``find_package_resource`` so the package-resource lookups
  return ``tmp_path``-relative locations we control;
- redirecting ``DATA_FOLDER`` via ``monkeypatch.setattr`` so the user
  directory lives in ``tmp_path``;
- resetting the cached ``_PACKAGED_DEFAULTS`` between tests so state
  from one test cannot leak into the next.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from katrain.core.analysis_result import EngineTestResult, ErrorCategory
from katrain.core.auto_setup import (
    DEFAULT_AUTO_SETUP,
    MIGRATED_DEFAULT_MODE,
    _get_packaged_defaults,
    _has_custom_engine_settings,
    _is_likely_opencl_binary,
    find_cpu_katago,
    find_lightweight_model,
    get_auto_setup_config,
    get_model_search_dirs,
    get_packaged_engine_defaults,
    prepare_reset_to_auto,
    resolve_auto_engine_settings,
    should_show_auto_tab_first,
)


@pytest.fixture(autouse=True)
def reset_packaged_defaults() -> Any:
    """Clear the cached packaged defaults before and after each test."""
    import katrain.core.auto_setup as auto_setup_mod

    saved = auto_setup_mod._PACKAGED_DEFAULTS
    auto_setup_mod._PACKAGED_DEFAULTS = None
    yield
    auto_setup_mod._PACKAGED_DEFAULTS = saved


# ---------------------------------------------------------------------------
# Section 1: should_show_auto_tab_first (pure config gate)
# ---------------------------------------------------------------------------


class TestShouldShowAutoTabFirst:
    """Phase 89 config gate for the Auto tab first-run UX."""

    @pytest.mark.parametrize(
        "mode,first_run,expected",
        [
            ("auto", False, True),
            ("auto", True, False),
            ("standard", False, False),
            ("advanced", False, False),
            ("auto", None, False),  # None != False → False
            (None, False, False),  # mode != "auto" → False
        ],
    )
    def test_matrix(self, mode: Any, first_run: Any, expected: bool) -> None:
        config = {"mode": mode, "first_run_completed": first_run}
        assert should_show_auto_tab_first(config) is expected

    def test_empty_dict_defaults_to_no(self) -> None:
        # ``mode`` is missing so it doesn't equal ``"auto"``.
        assert should_show_auto_tab_first({}) is False


# ---------------------------------------------------------------------------
# Section 2: _has_custom_engine_settings (pure config compare)
# ---------------------------------------------------------------------------


class TestHasCustomEngineSettings:
    """Comparison against packaged defaults to detect user customisation."""

    def test_empty_engine_returns_false(self) -> None:
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "", "config": ""},
        ):
            assert _has_custom_engine_settings({}) is False

    def test_all_match_packaged_returns_false(self) -> None:
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "x", "model": "y", "config": "z"},
        ):
            assert _has_custom_engine_settings({"katago": "x", "model": "y", "config": "z"}) is False

    def test_different_katago_path_returns_true(self) -> None:
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "/usr/bin/katago", "model": "", "config": ""},
        ):
            assert _has_custom_engine_settings({"katago": "/opt/custom/katago", "model": "", "config": ""}) is True

    def test_different_model_returns_true(self) -> None:
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "default.bin.gz", "config": ""},
        ):
            assert _has_custom_engine_settings({"katago": "", "model": "custom.bin.gz", "config": ""}) is True

    def test_different_config_returns_true(self) -> None:
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "", "model": "", "config": "default.cfg"},
        ):
            assert _has_custom_engine_settings({"katago": "", "model": "", "config": "custom.cfg"}) is True

    def test_empty_katago_ignored(self) -> None:
        # Empty strings are treated as "use default".
        with patch(
            "katrain.core.auto_setup.get_packaged_engine_defaults",
            return_value={"katago": "/usr/bin/katago", "model": "", "config": ""},
        ):
            assert _has_custom_engine_settings({"katago": "", "model": "", "config": ""}) is False


# ---------------------------------------------------------------------------
# Section 3: get_auto_setup_config (migration logic)
# ---------------------------------------------------------------------------


class TestGetAutoSetupConfig:
    """Phase 89 migration logic for the ``auto_setup`` config section."""

    def test_existing_auto_setup_section_preserved(self) -> None:
        user_config = {"auto_setup": {"mode": "advanced", "first_run_completed": True}}
        result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "advanced"
        assert result["first_run_completed"] is True

    def test_existing_section_missing_keys_get_defaults(self) -> None:
        user_config = {"auto_setup": {"mode": "advanced"}}  # no first_run_completed
        result = get_auto_setup_config(user_config, is_new_user=False)
        assert result["mode"] == "advanced"
        assert result["first_run_completed"] is False  # default

    def test_new_user_gets_auto_mode(self) -> None:
        result = get_auto_setup_config({}, is_new_user=True)
        assert result["mode"] == "auto"
        assert result["first_run_completed"] is False
        assert result["last_test_result"] is None

    def test_existing_user_no_custom_engine_gets_standard(self) -> None:
        with patch("katrain.core.auto_setup._has_custom_engine_settings", return_value=False):
            result = get_auto_setup_config({"engine": {}}, is_new_user=False)
        assert result["mode"] == "standard"

    def test_existing_user_with_custom_engine_gets_advanced(self) -> None:
        with patch("katrain.core.auto_setup._has_custom_engine_settings", return_value=True):
            result = get_auto_setup_config({"engine": {"katago": "x"}}, is_new_user=False)
        assert result["mode"] == "advanced"

    def test_default_mode_constant_is_standard(self) -> None:
        # Sanity check: the migrated default is "standard", not "auto".
        # Critical for the new-vs-existing-user distinction.
        assert MIGRATED_DEFAULT_MODE == "standard"

    def test_default_auto_setup_mode_is_auto(self) -> None:
        # Mirror of the new-user path.
        assert DEFAULT_AUTO_SETUP["mode"] == "auto"
        assert DEFAULT_AUTO_SETUP["first_run_completed"] is False


# ---------------------------------------------------------------------------
# Section 4: get_packaged_engine_defaults
# ---------------------------------------------------------------------------


class TestGetPackagedEngineDefaults:
    """Read-only wrapper around the bundled ``config.json`` engine block."""

    def test_returns_dict(self) -> None:
        with patch(
            "katrain.core.auto_setup._get_packaged_defaults",
            return_value={"engine": {"katago": "/x", "model": "y"}},
        ):
            result = get_packaged_engine_defaults()
        assert isinstance(result, dict)
        assert result["katago"] == "/x"

    def test_returns_copy_not_reference(self) -> None:
        with patch(
            "katrain.core.auto_setup._get_packaged_defaults",
            return_value={"engine": {"katago": "/x"}},
        ):
            first = get_packaged_engine_defaults()
            first["__mutation_marker__"] = "leaked"
            second = get_packaged_engine_defaults()
        assert "__mutation_marker__" not in second

    def test_handles_missing_engine_section(self) -> None:
        with patch(
            "katrain.core.auto_setup._get_packaged_defaults",
            return_value={"not_engine": {}},
        ):
            assert get_packaged_engine_defaults() == {}

    def test_handles_empty_packaged_defaults(self) -> None:
        # When the file is missing entirely, the function must not crash.
        with patch(
            "katrain.core.auto_setup._get_packaged_defaults",
            return_value={},
        ):
            assert get_packaged_engine_defaults() == {}

    def test_packaged_defaults_cached(self) -> None:
        # First call should hit the file; subsequent calls reuse the cache.
        fake_load = MagicMock(return_value={"engine": {}})
        with (
            patch(
                "katrain.core.auto_setup.find_package_resource",
                return_value="/dev/null",
            ) as find,
            patch("builtins.open", new=MagicMock()),
            patch("json.load", new=fake_load),
        ):
            _get_packaged_defaults()
            _get_packaged_defaults()
        # find_package_resource is called only on first invocation.
        assert find.call_count == 1


# ---------------------------------------------------------------------------
# Section 5: get_model_search_dirs
# ---------------------------------------------------------------------------


class TestGetModelSearchDirs:
    """Resolve the user + package models directories."""

    def test_user_dir_created_if_missing(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        user_models = tmp_path / "models"
        monkeypatch.setattr("katrain.core.auto_setup.DATA_FOLDER", str(tmp_path), raising=False)
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_package_resource",
            MagicMock(return_value=str(tmp_path / "nonexistent_pkg_models")),
        )
        result = get_model_search_dirs()
        assert str(user_models) in result
        assert user_models.exists()
        assert str(tmp_path / "nonexistent_pkg_models") not in result

    def test_existing_user_dir_kept(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        user_models = tmp_path / "models"
        user_models.mkdir()
        monkeypatch.setattr("katrain.core.auto_setup.DATA_FOLDER", str(tmp_path), raising=False)
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_package_resource", MagicMock(return_value=str(tmp_path / "pkg_models"))
        )
        result = get_model_search_dirs()
        assert str(user_models) in result

    def test_pkg_dir_added_when_it_exists(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        pkg = tmp_path / "pkg_models"
        pkg.mkdir()
        user = tmp_path / "models"
        user.mkdir()
        monkeypatch.setattr("katrain.core.auto_setup.DATA_FOLDER", str(tmp_path), raising=False)
        monkeypatch.setattr("katrain.core.auto_setup.find_package_resource", MagicMock(return_value=str(pkg)))
        result = get_model_search_dirs()
        assert str(user) in result
        assert str(pkg) in result


# ---------------------------------------------------------------------------
# Section 6: find_lightweight_model
# ---------------------------------------------------------------------------


class TestFindLightweightModel:
    """Search the user / package models dirs for a b10c128 bin.gz file."""

    def test_returns_none_when_no_dirs_have_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("katrain.core.auto_setup.get_model_search_dirs", MagicMock(return_value=[]))
        assert find_lightweight_model() is None

    def test_returns_first_match_when_single_candidate(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "kata1-b10c128-s123.bin.gz"
        target.write_bytes(b"")
        monkeypatch.setattr("katrain.core.auto_setup.get_model_search_dirs", MagicMock(return_value=[str(tmp_path)]))
        assert find_lightweight_model() == str(target)

    def test_picks_newest_when_multiple_candidates(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        old = tmp_path / "kata1-b10c128-20200101.bin.gz"
        new = tmp_path / "kata1-b10c128-20231201.bin.gz"
        old.write_bytes(b"")
        new.write_bytes(b"")
        os.utime(str(old), (1577836800, 1577836800))
        os.utime(str(new), (1701388800, 1701388800))
        monkeypatch.setattr("katrain.core.auto_setup.get_model_search_dirs", MagicMock(return_value=[str(tmp_path)]))
        assert find_lightweight_model() == str(new)

    def test_falls_back_to_mtime_when_no_timestamp_in_name(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        old = tmp_path / "b10c128-old.bin.gz"
        new = tmp_path / "b10c128-new.bin.gz"
        old.write_bytes(b"")
        new.write_bytes(b"")
        os.utime(str(old), (1577836800, 1577836800))
        os.utime(str(new), (1701388800, 1701388800))
        monkeypatch.setattr("katrain.core.auto_setup.get_model_search_dirs", MagicMock(return_value=[str(tmp_path)]))
        assert find_lightweight_model() == str(new)

    def test_empty_dir_returns_none(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        # tmp_path exists but no b10c128 file inside.
        monkeypatch.setattr("katrain.core.auto_setup.get_model_search_dirs", MagicMock(return_value=[str(tmp_path)]))
        assert find_lightweight_model() is None


# ---------------------------------------------------------------------------
# Section 7: _is_likely_opencl_binary
# ---------------------------------------------------------------------------


class TestIsLikelyOpenClBinary:
    """Filename-based heuristic for OpenCL / CUDA / TensorRT rejection."""

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/opt/katago-opencl", True),
            ("/usr/local/KATAGO-CUDA", True),
            ("C:/bin/katago-tensorrt.exe", True),
            ("/opt/katago", False),
            ("/usr/local/katago-eigen", False),
            ("/opt/KataGo/katago-cpu", False),
            ("", False),
        ],
    )
    def test_filename_detection(self, path: str, expected: bool) -> None:
        assert _is_likely_opencl_binary(path) is expected


# ---------------------------------------------------------------------------
# Section 8: find_cpu_katago
# ---------------------------------------------------------------------------


class TestFindCpuKatago:
    """Search the package KataGo directory for a non-OpenCL binary."""

    def test_returns_first_non_opencl_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_package_resource", MagicMock(return_value="/opt/katago-eigen")
        )
        monkeypatch.setattr("katrain.core.auto_setup.get_platform", MagicMock(return_value="linux"))
        with patch("os.path.isfile", return_value=True):
            assert find_cpu_katago() == "/opt/katago-eigen"

    def test_skips_opencl_binary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # First candidate is opencl; second is eigen.
        paths = iter(["/opt/katago-opencl", "/opt/katago-eigen"])

        def fake_find_resource(name: str) -> str:
            return next(paths)

        monkeypatch.setattr("katrain.core.auto_setup.find_package_resource", MagicMock(side_effect=fake_find_resource))
        monkeypatch.setattr("katrain.core.auto_setup.get_platform", MagicMock(return_value="linux"))
        with patch("os.path.isfile", return_value=True):
            result = find_cpu_katago()
        assert result == "/opt/katago-eigen"

    def test_returns_none_when_no_candidate_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_package_resource", MagicMock(return_value="/nonexistent/katago")
        )
        monkeypatch.setattr("katrain.core.auto_setup.get_platform", MagicMock(return_value="linux"))
        with patch("os.path.isfile", return_value=False):
            assert find_cpu_katago() is None

    def test_windows_uses_exe_extensions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[str] = []

        def fake_find_resource(name: str) -> str:
            captured.append(name)
            return f"/fake/{name.split('/')[-1]}"

        monkeypatch.setattr("katrain.core.auto_setup.find_package_resource", MagicMock(side_effect=fake_find_resource))
        monkeypatch.setattr("katrain.core.auto_setup.get_platform", MagicMock(return_value="win"))
        with patch("os.path.isfile", return_value=False):
            find_cpu_katago()
        # First candidate must be the eigen exe.
        assert captured[0] == "katrain/KataGo/katago-eigen.exe"
        assert captured[1] == "katrain/KataGo/katago-cpu.exe"
        assert captured[2] == "katrain/KataGo/katago.exe"


# ---------------------------------------------------------------------------
# Section 9: resolve_auto_engine_settings
# ---------------------------------------------------------------------------


class TestResolveAutoEngineSettings:
    """Build the engine settings block for auto mode."""

    def test_success_when_model_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_lightweight_model", MagicMock(return_value="/opt/models/b10c128.bin.gz")
        )
        settings, err = resolve_auto_engine_settings({"base": True})
        assert err is None
        assert settings is not None
        assert settings["base"] is True
        assert settings["model"] == "/opt/models/b10c128.bin.gz"
        assert settings["max_visits"] == 100
        assert settings["fast_visits"] == 10

    def test_failure_when_model_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("katrain.core.auto_setup.find_lightweight_model", MagicMock(return_value=None))
        settings, err = resolve_auto_engine_settings({})
        assert settings is None
        assert err is not None
        assert err.success is False
        assert err.error_category == ErrorCategory.LIGHTWEIGHT_MISSING
        assert err.error_message is not None
        assert "b10c128" in err.error_message

    def test_failure_returns_engine_test_result_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("katrain.core.auto_setup.find_lightweight_model", MagicMock(return_value=None))
        _, err = resolve_auto_engine_settings({})
        assert isinstance(err, EngineTestResult)

    def test_success_preserves_base_engine_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "katrain.core.auto_setup.find_lightweight_model", MagicMock(return_value="/opt/models/b10c128.bin.gz")
        )
        settings, _ = resolve_auto_engine_settings({"threads": 4, "katago": "/x", "extra": [1, 2, 3]})
        assert settings is not None
        assert settings["threads"] == 4
        assert settings["katago"] == "/x"
        assert settings["extra"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Section 10: prepare_reset_to_auto
# ---------------------------------------------------------------------------


class TestPrepareResetToAuto:
    """Phase 90 config-reset helper."""

    def test_returns_single_section(self) -> None:
        result = prepare_reset_to_auto()
        assert list(result.keys()) == ["auto_setup"]

    def test_mode_is_auto(self) -> None:
        result = prepare_reset_to_auto()
        assert result["auto_setup"]["mode"] == "auto"

    def test_first_run_completed_reset_to_false(self) -> None:
        result = prepare_reset_to_auto()
        assert result["auto_setup"]["first_run_completed"] is False

    def test_last_test_result_reset_to_none(self) -> None:
        result = prepare_reset_to_auto()
        assert result["auto_setup"]["last_test_result"] is None

    def test_does_not_apply_changes(self) -> None:
        # The function returns a dict; it must NOT mutate any state.
        # Verify by calling twice and checking both results are equivalent.
        first = prepare_reset_to_auto()
        second = prepare_reset_to_auto()
        assert first == second
