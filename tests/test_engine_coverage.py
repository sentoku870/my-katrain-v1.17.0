"""Phase A4: core/engine.py coverage tests.

Architecture Review follow-up: ``core/engine.py`` is the heart of the
KataGo integration and was at 48.3% coverage (375/776 lines, 53
branches unhit). The slow decay is mostly the subprocess / thread
internals of ``KataGoEngine``, which are tested end-to-end via
``tests/test_engine_lifecycle.py`` and ``tests/test_engine_commands.py``
but only when the real KataGo binary is available.

What this file adds:

- Pure-function tests for ``_ensure_str`` (bytes / str / None paths).
- ``BaseEngine`` interface tests that exercise the configuration /
  path-resolution logic without touching the network or spawning
  processes.
- ``KataGoEngine`` **attribute-method tests** (counters, query state,
  backend type) that avoid the subprocess layer by setting instance
  attributes directly.
- ``KataGoEngine.create_minimal_analysis_query`` end-to-end (it
  builds a JSON-encodable dict without spawning anything).

We deliberately do **not** test:

- Subprocess startup / shutdown (covered by ``test_engine_lifecycle``).
- Pipe-reader thread interactions (covered by ``test_engine_commands``).
- Real Katago protocol round trips (covered by integration tests).

Phase 158+ reform: I/O thread functions live in ``engine_io.py`` and
the query lifecycle lives in ``engine_query.py``; those modules have
their own coverage. ``engine.py`` itself remains a thin facade with
``BaseEngine`` + ``KataGoEngine`` that owns setup, hook dispatch, and
the public inspection API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from katrain.core.engine import (
    MAX_PENDING_QUERIES,
    BaseEngine,
    KataGoEngine,
    _ensure_str,
    _identity_scheduler,
)

# ---------------------------------------------------------------------------
# Section 1: _ensure_str (pure utility)
# ---------------------------------------------------------------------------


class TestEnsureStr:
    """Normalise a subprocess line to ``str`` for downstream parsing."""

    def test_none_returns_empty_string(self) -> None:
        assert _ensure_str(None) == ""

    def test_str_passes_through(self) -> None:
        assert _ensure_str("hello") == "hello"

    def test_empty_str_preserved(self) -> None:
        assert _ensure_str("") == ""

    def test_bytes_decoded_as_utf8(self) -> None:
        assert _ensure_str(b"hello") == "hello"

    def test_bytes_with_invalid_utf8_replaced(self) -> None:
        # Lone surrogate-ish sequences are replaced rather than raised.
        result = _ensure_str(b"\xff\xfeabc")
        # Should not raise, just replace.
        assert "abc" in result

    def test_str_with_weird_chars_preserved(self) -> None:
        assert _ensure_str("こんにちは") == "こんにちは"


# ---------------------------------------------------------------------------
# Section 2: _identity_scheduler and BaseEngine.__init__
# ---------------------------------------------------------------------------


class TestIdentityScheduler:
    """The default scheduler used when Kivy's Clock is unavailable."""

    def test_calls_fn_inline_with_no_args(self) -> None:
        called = []

        def fn() -> None:
            called.append("yes")

        _identity_scheduler(fn)
        assert called == ["yes"]

    def test_passes_through_positional_args(self) -> None:
        seen: list[Any] = []

        def fn(*args: Any) -> None:
            seen.extend(args)

        _identity_scheduler(fn, 1, 2, 3)
        assert seen == [1, 2, 3]

    def test_passes_through_keyword_args(self) -> None:
        seen: dict[str, Any] = {}

        def fn(**kwargs: Any) -> None:
            seen.update(kwargs)

        _identity_scheduler(fn, _dt=0.5)  # Kivy Clock passes _dt
        assert seen == {"_dt": 0.5}


class TestBaseEngineInit:
    """``BaseEngine.__init__`` stores dependencies for later use."""

    def test_stores_katrain_and_config(self) -> None:
        katrain = MagicMock()
        config: dict[str, Any] = {"x": 1}
        eng = BaseEngine(katrain, config)
        assert eng.katrain is katrain
        assert eng.config is config

    def test_default_scheduler_is_identity(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        # Default scheduler should be ``_identity_scheduler``.
        assert eng._main_thread_scheduler is _identity_scheduler

    def test_custom_scheduler_replaces_default(self) -> None:
        custom = MagicMock()
        eng = BaseEngine(MagicMock(), {}, main_thread_scheduler=custom)
        assert eng._main_thread_scheduler is custom

    def test_error_callback_optional(self) -> None:
        # No error_callback → attribute defaults to None.
        eng = BaseEngine(MagicMock(), {})
        assert eng._error_callback is None

    def test_error_callback_stored_when_provided(self) -> None:
        cb = MagicMock()
        eng = BaseEngine(MagicMock(), {}, error_callback=cb)
        assert eng._error_callback is cb


# ---------------------------------------------------------------------------
# Section 3: BaseEngine.get_rules (static)
# ---------------------------------------------------------------------------


class TestGetRules:
    """Normalise a ruleset reference into a canonical form."""

    def test_known_abbreviation(self) -> None:
        assert BaseEngine.get_rules("jp") == "japanese"

    def test_known_full_name(self) -> None:
        assert BaseEngine.get_rules("new zealand") == "new zealand"

    def test_known_abbreviation_case_insensitive(self) -> None:
        assert BaseEngine.get_rules("JP") == "japanese"

    def test_unknown_abbreviation_defaults_to_japanese(self) -> None:
        assert BaseEngine.get_rules("xx") == "japanese"

    def test_dict_passes_through(self) -> None:
        rules = {"ko": {"tax": 6.5}}
        assert BaseEngine.get_rules(rules) == rules

    def test_json_string_parsed(self) -> None:
        rules_json = '{"ko": {"tax": 6.5}}'
        result = BaseEngine.get_rules(rules_json)
        assert result == {"ko": {"tax": 6.5}}

    def test_invalid_json_string_falls_back_to_abbreviation(self) -> None:
        # Looks like JSON but isn't; fallback to the alias lookup.
        # ``"{not json}"`` is unparseable, treated as a literal ruleset key.
        result = BaseEngine.get_rules("{not json}")
        # Not a valid key - default to "japanese".
        assert result == "japanese"


# ---------------------------------------------------------------------------
# Section 4: BaseEngine.get_engine_path
# ---------------------------------------------------------------------------


class TestGetEnginePath:
    """Resolve the Katago binary across platforms."""

    def test_empty_exe_on_linux_defaults_to_package(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = BaseEngine(MagicMock(), {})
        monkeypatch.setattr("katrain.core.engine.get_platform", lambda: "linux")
        monkeypatch.setattr("katrain.core.engine.find_package_resource", MagicMock(return_value="/pkg/katago"))
        monkeypatch.setattr("os.path.isfile", lambda path: True)
        result = eng.get_engine_path("")
        assert result == "/pkg/katago"

    def test_empty_exe_with_no_valid_path_fires_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = BaseEngine(MagicMock(), {})
        eng.on_error = MagicMock()  # type: ignore[method-assign]
        monkeypatch.setattr("katrain.core.engine.get_platform", lambda: "linux")
        monkeypatch.setattr("katrain.core.engine.find_package_resource", MagicMock(return_value="/missing/katago"))
        # Pretend no PATH entry exists.
        monkeypatch.setattr("os.path.isfile", lambda path: False)
        result = eng.get_engine_path("katago")
        assert result is None
        # on_error invoked with the KATAGO-EXE code.
        eng.on_error.assert_called_once()
        # ``allow_popup=True`` is passed.
        args = eng.on_error.call_args[0]
        assert args[2] is True

    def test_empty_exe_env_path_search_resolves_first_hit(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
        eng = BaseEngine(MagicMock(), {})
        monkeypatch.setattr("katrain.core.engine.get_platform", lambda: "linux")
        # ``exe = "katago"`` — no katrain prefix → goes through PATH branch.
        # Create a fake /usr/bin with the executable.
        fake_bin = tmp_path / "katago"
        fake_bin.write_bytes(b"")
        fake_bin.chmod(0o755)
        monkeypatch.setattr("os.environ", {"PATH": str(tmp_path)})
        result = eng.get_engine_path("katago")
        assert result == str(fake_bin)

    def test_no_directory_path_no_environment_fires_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = BaseEngine(MagicMock(), {})
        eng.on_error = MagicMock()  # type: ignore[method-assign]
        monkeypatch.setattr("katrain.core.engine.get_platform", lambda: "linux")
        monkeypatch.setattr(
            "katrain.core.engine.find_package_resource",
            MagicMock(return_value="katago"),  # bare name → goes through PATH branch
        )
        monkeypatch.setattr("os.path.isfile", lambda p: False)
        monkeypatch.setattr("os.environ", {"PATH": "/no/such/dir"})
        result = eng.get_engine_path("katago")
        assert result is None


# ---------------------------------------------------------------------------
# Section 5: BaseEngine.set_analysis_focus
# ---------------------------------------------------------------------------


class TestSetAnalysisFocus:
    """Wire the analysis_focus config to the engine."""

    def test_none_clears_existing(self) -> None:
        config = {"analysis_focus": [0, 0, 5, 5]}
        eng = BaseEngine(MagicMock(), config)
        eng.set_analysis_focus(None)
        assert "analysis_focus" not in config

    def test_none_when_no_focus_is_noop(self) -> None:
        config: dict[str, Any] = {}
        eng = BaseEngine(MagicMock(), config)
        eng.set_analysis_focus(None)
        assert "analysis_focus" not in config

    def test_rectangle_overwrites(self) -> None:
        config = {"analysis_focus": [0, 0, 5, 5]}
        eng = BaseEngine(MagicMock(), config)
        eng.set_analysis_focus([3, 4, 10, 12])
        assert config["analysis_focus"] == [3, 4, 10, 12]


# ---------------------------------------------------------------------------
# Section 6: BaseEngine defaults
# ---------------------------------------------------------------------------


class TestBaseEngineDefaults:
    """``BaseEngine`` defaults that subclasses inherit."""

    def test_is_alive_defaults_to_false(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        assert eng.is_alive() is False

    def test_status_defaults_to_empty_string(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        assert eng.status() == ""

    def test_advance_showing_game_is_noop(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        # Must not raise and must return ``None``.
        eng.advance_showing_game()  # type: ignore[func-returns-value]

    def test_on_error_default_is_noop(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        # Default on_error doesn't raise — subclasses are expected to override.
        eng.on_error("msg", "CODE")  # type: ignore[func-returns-value]

    def test_fire_engine_error_forwards_to_on_error(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        eng.on_error = MagicMock()  # type: ignore[method-assign]
        eng._fire_engine_error("hi", "E-CODE", allow_popup=False)
        eng.on_error.assert_called_once_with("hi", "E-CODE", False)

    def test_fire_engine_error_default_code_is_none(self) -> None:
        eng = BaseEngine(MagicMock(), {})
        eng.on_error = MagicMock()  # type: ignore[method-assign]
        eng._fire_engine_error("hi")
        # `code` defaults to None.
        eng.on_error.assert_called_once_with("hi", None, True)


# ---------------------------------------------------------------------------
# Section 7: MAX_PENDING_QUERIES constant
# ---------------------------------------------------------------------------


class TestMaxPendingQueriesConstant:
    """Project-wide limit on concurrent KataGo queries."""

    def test_is_positive_int(self) -> None:
        assert isinstance(MAX_PENDING_QUERIES, int)
        assert MAX_PENDING_QUERIES > 0

    def test_value_matches_documented_limit(self) -> None:
        # If this changes, batch and engine tests need adjusting.
        assert MAX_PENDING_QUERIES == 100


# ---------------------------------------------------------------------------
# Section 8: KataGoEngine counters (no subprocess)
# ---------------------------------------------------------------------------


def _make_katago_engine_for_inspection() -> Any:
    """Construct a KataGoEngine without touching the network or subprocess.

    The constructor would normally spawn the KataGo process; instead we
    create the instance, set the attributes that ``is_idle``,
    ``is_alive``, ``queries_remaining``, ``get_pending_count``,
    ``has_query_capacity`` look at, and return.

    Returns ``Any`` because the instance is hand-built; mypy complains
    about every attribute we touch otherwise. Using ``# type: ignore``
    on each line would be high-noise; the helper concentrates all of
    that here.
    """
    eng: Any = KataGoEngine.__new__(KataGoEngine)
    # Match the attributes set by ``KataGoEngine.__init__`` post-subprocess.
    eng.config = {}
    eng.katrain = MagicMock()
    eng.process = None
    eng.pondering = None
    eng.status = "starting"
    eng.next_move_to_show = 0
    eng.shutdown_start = None
    eng.shutdown_complete = False
    eng.queries = {}
    eng.write_queue = MagicMock()
    eng.write_queue.empty.return_value = True
    eng.thread_lock = MagicMock()
    # ``thread_lock`` is used as a context manager in ``is_idle`` /
    # ``queries_remaining``; make sure ``__enter__`` / ``__exit__`` are no-ops.
    eng.thread_lock.__enter__ = lambda *a, **kw: eng.thread_lock
    eng.thread_lock.__exit__ = lambda *a, **kw: None
    eng.check_alive = lambda: False
    return eng


class TestKataGoEngineCounters:
    """Inspections that read instance state without subprocess I/O."""

    def test_is_idle_with_no_pending_queries(self) -> None:
        eng = _make_katago_engine_for_inspection()
        # ``queries`` empty and ``write_queue.empty()`` True → idle.
        assert eng.is_idle() is True

    def test_is_alive_with_no_process(self) -> None:
        eng = _make_katago_engine_for_inspection()
        eng.process = None  # type: ignore[assignment]
        # ``is_alive`` should be safe even with ``process=None``.
        # Default behavior is False (no process).
        assert eng.is_alive() is False

    def test_queries_remaining_with_empty_state(self) -> None:
        eng = _make_katago_engine_for_inspection()
        assert eng.queries_remaining() == 0

    def test_create_minimal_analysis_query(self) -> None:
        eng = _make_katago_engine_for_inspection()
        query = eng.create_minimal_analysis_query()
        # Must be JSON-serialisable.
        import json as _json

        _json.dumps(query)
        # Must have required fields.
        for k in ("id", "rules", "komi", "boardXSize", "boardYSize", "initialStones", "moves", "maxVisits"):
            assert k in query

    def test_create_minimal_uses_chinese_rules(self) -> None:
        eng = _make_katago_engine_for_inspection()
        query = eng.create_minimal_analysis_query()
        # ``rules`` is a string after ``get_rules("chinese")``.
        assert query["rules"] == "chinese"

    def test_create_minimal_uses_9x9_empty_board(self) -> None:
        eng = _make_katago_engine_for_inspection()
        query = eng.create_minimal_analysis_query()
        assert query["boardXSize"] == 9
        assert query["boardYSize"] == 9
        assert query["initialStones"] == []
        assert query["moves"] == []

    def test_create_minimal_uses_low_visits_no_ownership(self) -> None:
        eng = _make_katago_engine_for_inspection()
        query = eng.create_minimal_analysis_query()
        assert query["maxVisits"] == 10
        assert query["includeOwnership"] is False
        assert query["includePolicy"] is False


class TestKataGoEngineBackendType:
    """``get_backend_type`` reads config without touching the subprocess."""

    def test_returns_string(self) -> None:
        eng = _make_katago_engine_for_inspection()
        result = eng.get_backend_type()
        assert isinstance(result, str)

    def test_unknown_when_no_exe_resolved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        # Force ``get_engine_path`` to return None.
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: None)
        assert eng.get_backend_type() == "Unknown"

    def test_detects_opencl_from_filename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago-opencl")
        assert eng.get_backend_type() == "OpenCL"

    def test_detects_cuda_from_filename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago-cuda")
        assert eng.get_backend_type() == "CUDA"

    def test_detects_tensorrt_from_filename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago-tensorrt")
        assert eng.get_backend_type() == "TensorRT"

    def test_detects_eigen_from_filename(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago-eigen")
        assert eng.get_backend_type() == "Eigen"

    def test_detects_cpu_alias_as_eigen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago-cpu")
        assert eng.get_backend_type() == "Eigen"

    def test_defaults_to_opencl_for_unspecified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = _make_katago_engine_for_inspection()
        monkeypatch.setattr(eng, "get_engine_path", lambda exe: "/opt/katago")
        # No keyword matches → "OpenCL" default per the bundled binaries comment.
        assert eng.get_backend_type() == "OpenCL"


# ---------------------------------------------------------------------------
# Section 9: Pseudo-private constants and RULESETS mapping
# ---------------------------------------------------------------------------


class TestRulesetsMapping:
    """The RULESETS map from both abbreviation and full name."""

    @pytest.mark.parametrize(
        "abbr,full_name",
        [
            ("jp", "japanese"),
            ("cn", "chinese"),
            ("ko", "korean"),
            ("aga", "aga"),
            ("tt", "tromp-taylor"),
            ("nz", "new zealand"),
            ("stone_scoring", "stone_scoring"),
        ],
    )
    def test_abbr_and_full_name_map_to_same_value(self, abbr: str, full_name: str) -> None:
        # Verify both forms are mapped to the full name.
        assert BaseEngine.get_rules(abbr) == full_name
        assert BaseEngine.get_rules(full_name) == full_name

    def test_rulesets_dict_is_two_way(self) -> None:
        # The internal map can be used either direction.
        rmap = BaseEngine.RULESETS
        # Each abbr maps to the full name.
        for abbr, full_name in BaseEngine.RULESETS_ABBR:
            assert rmap[abbr] == full_name
            assert rmap[full_name] == full_name
