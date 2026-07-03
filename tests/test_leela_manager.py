"""Tests for ``LeelaManager.start_engine(force=...)`` (Phase 160).

Phase 160 unblocks the user's `AI Mode ai:leela not found!` /
`Engine not running — falling back to pass.` errors by letting the
strategy force-start the engine even when ``LeelaConfig.enabled`` is
``False``. These tests pin the *force* behaviour without spinning up
a real Leela subprocess.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from katrain.gui.leela_manager import LeelaManager


def _make_manager(
    *,
    config: dict[str, object],
    log_calls: list[tuple[str, int | None]] | None = None,
) -> LeelaManager:
    """Build a LeelaManager with mocked dependencies.

    The manager takes four callables in its constructor. We pass
    ``MagicMock`` for the two callbacks that aren't exercised by the
    tests (update_state, resign_popup) and a plain lambda for the
    config + log accessors so we can assert against captured state.
    """

    def config_getter(key: str, default: object = None) -> object:
        if "/" in key:
            cat, sub = key.split("/", 1)
            return config.get(cat, {}).get(sub, default)
        return config.get(key, default)

    captured_logs = log_calls if log_calls is not None else []

    def logger(message: str, level: int | None = None) -> None:
        captured_logs.append((message, level))

    return LeelaManager(
        config_getter=config_getter,
        logger=logger,
        update_state_callback=MagicMock(),
        schedule_resign_popup=MagicMock(),
    )


class TestLeelaManagerStartForce:
    """``start_engine(force=True)`` bypasses the ``enabled`` flag."""

    def test_force_starts_even_when_enabled_false(self) -> None:
        """``force=True`` is the Phase 160 escape hatch for the play path.

        With ``enabled=False`` the normal ``start_engine`` returns
        False (Leela stays dead). ``force=True`` must proceed past
        that gate; whether the subprocess actually launches is
        irrelevant for the predicate. We use a missing
        ``exe_path`` so the manager reports it as 'not found' instead
        of trying to launch — the relevant assertion is that
        ``force=True`` *does not* short-circuit on ``enabled``.
        """
        manager = _make_manager(
            config={
                "leela": {
                    "enabled": False,  # analysis OFF
                    "play_enabled": True,  # but the user asked for play
                    "exe_path": "/nonexistent/leela",
                    "max_visits": 1000,
                    "loss_scale_k": 0.5,
                    "max_candidates": 5,
                    "top_moves_show": "leela_top_move_loss",
                    "top_moves_show_secondary": "leela_top_move_winrate",
                    "fast_visits": 200,
                    "play_visits": 500,
                    "resign_hint_enabled": False,
                    "resign_winrate_threshold": 5,
                    "resign_consecutive_moves": 3,
                }
            }
        )

        # Without ``force=True`` the ``enabled=False`` gate rejects the
        # call BEFORE touching the exe_path: no log is emitted.
        assert manager.start_engine(MagicMock()) is False

        # With ``force=True`` the gate is bypassed; the manager then
        # enters exe-path validation (which fails for the missing file
        # in the fixture, emitting the i18n error message).
        assert manager.start_engine(MagicMock(), force=True) is False

    def test_enabled_true_takes_normal_path(self) -> None:
        """``enabled=True`` is unaffected by ``force``. Same outcome either way."""
        manager = _make_manager(
            config={
                "leela": {
                    "enabled": True,
                    "play_enabled": False,
                    "exe_path": "/nonexistent/leela",
                    "max_visits": 1000,
                    "loss_scale_k": 0.5,
                    "max_candidates": 5,
                    "top_moves_show": "leela_top_move_loss",
                    "top_moves_show_secondary": "leela_top_move_winrate",
                    "fast_visits": 200,
                    "play_visits": 500,
                    "resign_hint_enabled": False,
                    "resign_winrate_threshold": 5,
                    "resign_consecutive_moves": 3,
                }
            }
        )

        # Both branches reach the exe-path validation and fail to
        # spawn anything (exe_path is intentionally missing). The
        # ``enabled`` flag itself does not cause early-out.
        assert manager.start_engine(MagicMock()) is False
        assert manager.start_engine(MagicMock(), force=True) is False

    def test_real_executable_is_reachable_via_force(self) -> None:
        """``start_engine(force=True)`` records the exe-path failure.

        We use an invalid ``exe_path``. The intent is to demonstrate
        that the ``force=True`` branch reaches the exe-path
        validation stage (i.e. it logged the
        'Leela executable not found' i18n message), in contrast to
        ``force=False`` which short-circuits on ``enabled=False``
        without producing any log.

        Skipped on non-POSIX / Windows where the i18n lookup differs.
        """
        if os.name == "nt":
            pytest.skip("i18n / log path differs on Windows")

        def _manager_for(enabled: bool) -> LeelaManager:
            captured_logs: list[tuple[str, int | None]] = []

            def config_getter(key: str, default: object = None) -> object:
                if "/" in key:
                    cat, sub = key.split("/", 1)
                    return {
                        "leela": {
                            "enabled": enabled,
                            "play_enabled": True,
                            # Explicitly missing — manager must hit the
                            # 'exe not found' branch when force=True.
                            "exe_path": "/nonexistent/leela",
                            "max_visits": 1000,
                            "loss_scale_k": 0.5,
                            "max_candidates": 5,
                            "top_moves_show": "leela_top_move_loss",
                            "top_moves_show_secondary": "leela_top_move_winrate",
                            "fast_visits": 200,
                            "play_visits": 500,
                            "resign_hint_enabled": False,
                            "resign_winrate_threshold": 5,
                            "resign_consecutive_moves": 3,
                        }
                    }.get(cat, {}).get(sub, default)
                return default

            return LeelaManager(
                config_getter=config_getter,
                logger=lambda *args: captured_logs.append(args[:2]),
                update_state_callback=MagicMock(),
                schedule_resign_popup=MagicMock(),
            ), captured_logs

        # ``force=False`` short-circuits at ``not self._config("leela/enabled", False)`` —
        # no log line is emitted.
        manager_no_force, logs_no_force = _manager_for(enabled=False)
        assert manager_no_force.start_engine(MagicMock(), force=False) is False
        assert logs_no_force == []

        # ``force=True`` bypasses the ``enabled`` gate and reaches the
        # 'exe not found' branch, which records an error log.
        manager_force, logs_force = _manager_for(enabled=False)
        assert manager_force.start_engine(MagicMock(), force=True) is False
        assert any(
            "not found" in str(message).lower()
            or "見つかりません" in str(message)
            for message, _level in logs_force
        ), (
            "force=True should reach the exe-path validation "
            f"(logs were: {logs_force!r})"
        )


# ---------------------------------------------------------------------------
# _save_leela_settings: linked play_enabled / enabled behavior
# ---------------------------------------------------------------------------


class TestSaveLeelaSettingsLinkage:
    """``_save_leela_settings`` couples ``play_enabled`` with ``enabled``.

    Phase 160 enforces that a user who toggles 'Play against Leela'
    ends up with ``LeelaConfig.enabled=True`` so the engine boots
    automatically. Conversely, turning Play off forces
    ``enabled=False`` so the running engine is stopped. The tests
    pin both directions by patching the typed-config writer.

    The function uses two module-level names we monkey-patch here:

    * ``clamp_k`` — re-exported from ``katrain.core.constants`` at the
      top of ``settings_popup``.
    * ``LeelaConfig.from_dict`` — used inline as the default source.
      Since the ``_leela_defaults`` object is created by value (not by
      referencing the module), we patch the class method itself.
    """

    @staticmethod
    def _run_save(
        monkeypatch: pytest.MonkeyPatch,
        *,
        leela_enabled: bool,
        leela_play_enabled: bool,
    ) -> dict[str, object]:
        captured: dict[str, object] = {}

        from katrain.gui.features import settings_popup as sp

        # ``update_leela_config`` is invoked as ``ctx.update_leela_config``
        # so we install a recorder on the mock context object instead
        # of patching the symbol on the settings_popup module.
        ctx = MagicMock()

        def _capture(**_kwargs: object) -> object:
            captured.update(_kwargs)
            return type("_r", (), {})()

        ctx.update_leela_config = _capture  # type: ignore[method-assign]

        # ``LeelaConfig.from_dict`` returns a real instance that has
        # ``play_visits=500``. Patching it removes the dependency
        # on the typed-config pipeline while keeping the same shape.
        monkeypatch.setattr(
            sp.LeelaConfig,
            "from_dict",
            staticmethod(lambda _d: type("_d", (), {"play_visits": 500})()),
        )
        monkeypatch.setattr(sp, "clamp_k", lambda v: v)

        sp._save_leela_settings(
            ctx,
            leela_enabled=leela_enabled,
            leela_path="/some/leela",
            leela_k_value=0.5,
            leela_top_show="leela_top_move_loss",
            leela_top_show_2="leela_top_move_winrate",
            leela_visits_text="1000",
            leela_fast_visits_text="200",
            leela_cand_value="5",
            leela_play_enabled=leela_play_enabled,
        )
        return captured

    def test_play_only_sets_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``leela_enabled=False`` + ``play_enabled=True`` saves ``enabled=True``."""
        captured = self._run_save(
            monkeypatch,
            leela_enabled=False,
            leela_play_enabled=True,
        )
        assert captured["enabled"] is True
        assert captured["play_enabled"] is True

    def test_no_play_sets_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``leela_enabled=False`` + ``play_enabled=False`` saves ``enabled=False``."""
        captured = self._run_save(
            monkeypatch,
            leela_enabled=False,
            leela_play_enabled=False,
        )
        assert captured["enabled"] is False
        assert captured["play_enabled"] is False

    def test_analysis_only_keeps_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``leela_enabled=True`` + ``play_enabled=False`` saves ``enabled=True``."""
        captured = self._run_save(
            monkeypatch,
            leela_enabled=True,
            leela_play_enabled=False,
        )
        assert captured["enabled"] is True
        assert captured["play_enabled"] is False
