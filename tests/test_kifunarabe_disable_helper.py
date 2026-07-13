"""Phase 178: tests for the centralised kifunarabe disable helper.

The helper ``disable_kifunarabe_if_active`` is the single entry point
used by every "exit path" that needs to take the user out of kifunarabe
mode (regular SGF load, popup manager dismissals, save-game-after-
kifunarabe flows, future transitions). Its contract is intentionally
narrow:

1. When a kifunarabe controller is attached to ``katrain`` and exposes
   ``disable_if_needed()``, the helper invokes it exactly once.
2. When the controller attribute is missing (e.g. during early
   startup, in tests, or in headless contexts), the helper is a no-op.
3. If ``disable_if_needed()`` raises, the helper swallows the
   exception so the caller's main flow is never disrupted.

These three guarantees are the entirety of the Phase 178 acceptance
criteria for this surface; everything else belongs to
``KifunarabeController.disable_if_needed`` itself, which has its own
test suite under ``tests/test_kifunarabe_controller.py``.
"""

from __future__ import annotations

import unittest
from typing import Any


class _MockController:
    """Minimal stand-in for ``KifunarabeController``."""

    def __init__(self) -> None:
        self.call_count = 0
        self.disabled = False

    def disable_if_needed(self) -> None:
        self.call_count += 1
        self.disabled = True


class _MockGui:
    """Object shaped like ``KaTrainGui`` for the helper's purposes."""

    def __init__(self, controller: Any = None) -> None:
        # ``getattr(katrain, "_kifunarabe_controller", None)`` is the
        # lookup pattern the helper uses.
        self._kifunarabe_controller = controller


class _RaisingController:
    """Controller whose ``disable_if_needed`` always raises."""

    def disable_if_needed(self) -> None:
        raise RuntimeError("boom")


class TestDisableKifunarabeHelper(unittest.TestCase):
    def test_disable_helper_calls_controller(self) -> None:
        """The controller's ``disable_if_needed`` is invoked exactly once."""
        from katrain.gui.managers.kifunarabe_controller import (
            disable_kifunarabe_if_active,
        )

        ctrl = _MockController()
        gui = _MockGui(controller=ctrl)

        disable_kifunarabe_if_active(gui)

        self.assertTrue(ctrl.disabled)
        self.assertEqual(ctrl.call_count, 1)

    def test_disable_helper_noop_when_no_controller(self) -> None:
        """Missing controller attribute is a no-op, not an error."""
        from katrain.gui.managers.kifunarabe_controller import (
            disable_kifunarabe_if_active,
        )

        gui = _MockGui(controller=None)

        # Must not raise.
        disable_kifunarabe_if_active(gui)

    def test_disable_helper_swallows_exceptions(self) -> None:
        """An exception inside ``disable_if_needed`` does not propagate."""
        from katrain.gui.managers.kifunarabe_controller import (
            disable_kifunarabe_if_active,
        )

        gui = _MockGui(controller=_RaisingController())

        # Must not raise even though the controller raises.
        disable_kifunarabe_if_active(gui)

    def test_disable_helper_idempotent_across_calls(self) -> None:
        """Repeated calls keep working (idempotent under the contract)."""
        from katrain.gui.managers.kifunarabe_controller import (
            disable_kifunarabe_if_active,
        )

        ctrl = _MockController()
        gui = _MockGui(controller=ctrl)

        disable_kifunarabe_if_active(gui)
        disable_kifunarabe_if_active(gui)
        disable_kifunarabe_if_active(gui)

        # The controller itself is responsible for idempotency, but the
        # helper should not introduce its own guard logic.
        self.assertEqual(ctrl.call_count, 3)


if __name__ == "__main__":
    unittest.main()
