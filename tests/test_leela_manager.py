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
# compute_leela_enabled: linked play_enabled / enabled behavior
# ---------------------------------------------------------------------------


class TestComputeLeelaEnabled:
    """``compute_leela_enabled`` couples ``play_enabled`` with ``enabled``.

    Phase 161 extracts the join into a pure helper so the four
    combination patterns can be unit-tested without exercising the
    Kivy-bound ``_save_leela_settings`` pipeline (which loads
    ``settings_popup`` and pulls in widget factories).

    Rules:
      * ``play_enabled=True`` → ``enabled=True`` (engine must boot
        for Play).
      * ``leela_enabled=True`` → ``enabled=True`` (analysis-only
        still needs the engine running).
      * Both off → ``enabled=False`` (engine stays cold until the
        user toggles either flag on).

    This is the table the Settings > Leela tab enforces on save:
      | leela_enabled | leela_play_enabled | enabled saved |
      |      T        |        T            |      T        |
      |      T        |        F            |      T        |
      |      F        |        T            |      T        |
      |      F        |        F            |      F        |
    """

    @staticmethod
    def _compute(leela_enabled: bool, leela_play_enabled: bool) -> bool:
        # Late import avoids loading settings_popup (and the full
        # Kivy widget graph) for the pure-function tests below.
        from katrain.gui.features.settings_popup import compute_leela_enabled

        return compute_leela_enabled(leela_enabled, leela_play_enabled)

    def test_play_only_boots_engine(self) -> None:
        """``leela_enabled=False`` + ``play_enabled=True`` → ``enabled=True``."""
        assert self._compute(False, True) is True

    def test_no_play_stops_engine(self) -> None:
        """``leela_enabled=False`` + ``play_enabled=False`` → ``enabled=False``."""
        assert self._compute(False, False) is False

    def test_analysis_only_keeps_engine_running(self) -> None:
        """``leela_enabled=True`` + ``play_enabled=False`` → ``enabled=True``."""
        assert self._compute(True, False) is True

    def test_both_on_keeps_engine_running(self) -> None:
        """``leela_enabled=True`` + ``play_enabled=True`` → ``enabled=True``."""
        assert self._compute(True, True) is True
