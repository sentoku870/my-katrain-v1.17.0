"""Tests for ``LeelaManager.start_engine`` (Phase 170).

Phase 160/161 added a ``force=`` flag and a ``play_enabled`` toggle to
unblock the human-vs-Leela play path. Phase 170 abolished that path
(``LeelaStrategy`` removed), so the force branch is gone and the
manager now keys solely off ``leela/enabled``. These tests pin the
simplified behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from katrain.gui.leela_manager import LeelaManager


def _make_manager(
    *,
    config: dict[str, object],
) -> tuple[LeelaManager, list[tuple[str, int | None]]]:
    """Build a LeelaManager with mocked dependencies; return the
    manager and a shared list that captures every log call."""

    def config_getter(key: str, default: object = None) -> object:
        if "/" in key:
            cat, sub = key.split("/", 1)
            return config.get(cat, {}).get(sub, default)
        return config.get(key, default)

    captured: list[tuple[str, int | None]] = []

    def logger(message: str, level: int | None = None) -> None:
        captured.append((message, level))

    return (
        LeelaManager(
            config_getter=config_getter,
            logger=logger,
            update_state_callback=MagicMock(),
            schedule_resign_popup=MagicMock(),
        ),
        captured,
    )


def _base_leela_config(*, enabled: bool, exe_path: str) -> dict[str, object]:
    return {
        "leela": {
            "enabled": enabled,
            "exe_path": exe_path,
            "max_visits": 1000,
            "loss_scale_k": 0.5,
            "max_candidates": 5,
            "top_moves_show": "leela_top_move_loss",
            "top_moves_show_secondary": "leela_top_move_winrate",
            "fast_visits": 200,
            "resign_hint_enabled": False,
            "resign_winrate_threshold": 5,
            "resign_consecutive_moves": 3,
        }
    }


class TestLeelaManagerStartEnabledGate:
    """``start_engine`` short-circuits when ``leela/enabled`` is False."""

    def test_disabled_does_not_touch_exe_path(self) -> None:
        """With ``enabled=False`` ``start_engine`` returns False without logging.

        The manager must never reach exe-path validation when the user
        has the analysis engine turned off. We assert by checking the
        log buffer stays empty.
        """
        manager, logs = _make_manager(
            config=_base_leela_config(enabled=False, exe_path="/nonexistent/leela")
        )

        assert manager.start_engine(MagicMock()) is False
        assert logs == []

    def test_enabled_reaches_exe_path_validation(self) -> None:
        """With ``enabled=True`` the manager validates ``exe_path`` and
        emits the i18n error message for the missing file."""
        manager, logs = _make_manager(
            config=_base_leela_config(enabled=True, exe_path="/nonexistent/leela")
        )

        assert manager.start_engine(MagicMock()) is False
        assert any(
            "not found" in str(message).lower() or "見つかりません" in str(message)
            for message, _level in logs
        )


class TestLeelaManagerIgnoresLegacyPlayFields:
    """``play_enabled`` / ``play_visits`` are accepted but ignored."""

    def test_legacy_play_enabled_does_not_affect_enabled_gate(self) -> None:
        """A user config from Phase 159B-161 may still carry
        ``play_enabled=True`` even though Leela play is gone. The
        manager must still honour ``leela/enabled`` as the sole gate."""
        cfg = _base_leela_config(enabled=False, exe_path="/nonexistent/leela")
        # Inject the legacy Phase 159B-161 fields.
        cfg["leela"]["play_enabled"] = True  # type: ignore[union-attr]
        cfg["leela"]["play_visits"] = 500  # type: ignore[union-attr]
        manager, logs = _make_manager(config=cfg)

        # ``enabled=False`` still short-circuits even if play_enabled=True
        # is in the legacy config blob.
        assert manager.start_engine(MagicMock()) is False
        assert logs == []


# ---------------------------------------------------------------------------
# compute_leela_enabled: removed in Phase 170.
# ---------------------------------------------------------------------------


def test_compute_leela_enabled_was_removed() -> None:
    """Phase 170 removed the ``compute_leela_enabled`` helper that
    coupled ``play_enabled`` and ``enabled``. Importing the symbol from
    ``katrain.core.constants`` must raise so any lingering reference
    is caught at import time. (Python surfaces a missing name as
    ``ImportError`` from ``import name`` and as ``AttributeError`` from
    ``module.name``; we accept either to keep the test robust.)"""
    import katrain.core.constants as constants

    with pytest.raises((ImportError, AttributeError)):
        from katrain.core.constants import compute_leela_enabled  # noqa: F401

    assert not hasattr(constants, "compute_leela_enabled")
