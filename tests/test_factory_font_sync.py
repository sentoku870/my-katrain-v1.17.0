"""Phase 281 (tofu-fix): factory.py hint_label sync helper tests.

These tests exercise ``_sync_font_to_hint_labels`` directly so a
future refactor of the helper (e.g. renaming attributes, removing
the sync, or breaking the no-op-on-plain-Label contract) is caught
immediately.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tests.kivy_test_base import KivyUnitTest

# Runtime probe — same pattern as test_kivymd_hint_text_label.py.
try:
    import kivy  # noqa: F401

    _KIVY_AVAILABLE = True
except ImportError:
    _KIVY_AVAILABLE = False


REPO_ROOT = Path(__file__).resolve().parents[1]
FACTORY_PATH = REPO_ROOT / "katrain" / "gui" / "widgets" / "factory.py"


# ---------------------------------------------------------------------------
# Source-static regression guards (no Kivy required)
# ---------------------------------------------------------------------------


class TestFactorySourceStatic:
    """Static checks of ``factory.py`` so the helper contract is
    locked even when Kivy is unavailable.
    """

    def test_factory_declares_helper(self):
        text = FACTORY_PATH.read_text(encoding="utf-8")
        assert "def _sync_font_to_hint_labels" in text, "factory.py must export _sync_font_to_hint_labels helper"
        assert "def _schedule_hint_label_sync" in text, "factory.py must export _schedule_hint_label_sync helper"

    def test_factory_hint_label_attrs_listed(self):
        text = FACTORY_PATH.read_text(encoding="utf-8")
        # The known KivyMD internal Label attributes must appear in
        # the helper's attribute list. We check the most important
        # ones; missing one is the kind of regression this Phase
        # guards against.
        for required in ("hint_text_label", "_hint_text_label", "helper_text_label"):
            assert required in text, (
                f"_HINT_LABEL_ATTRS missing {required!r}; KivyMD 1.2.0 internal label may no longer sync."
            )

    def test_factory_wrappers_schedule_sync(self):
        text = FACTORY_PATH.read_text(encoding="utf-8")
        # All three wrappers (Label, Button, Popup) must call
        # _schedule_hint_label_sync after super().__init__.
        for cls in ("class Label(_Label):", "class Button(_Button):", "class Popup(_Popup):"):
            assert cls in text, f"factory.py missing {cls}"
        # The simplest reliable check: count occurrences of the
        # helper call. There must be exactly one per class.
        assert text.count("_schedule_hint_label_sync(self)") == 3, (
            "factory.py wrappers should each call _schedule_hint_label_sync(self) exactly once."
        )


# ---------------------------------------------------------------------------
# Runtime tests for the helper itself
# ---------------------------------------------------------------------------


def _make_mock_widget(parent_font, child_fonts):
    """Build a MagicMock widget that exposes ``font_name`` and a
    configurable set of internal hint-label attributes.

    Args:
        parent_font: The ``font_name`` value the parent widget should
            report (``str``). Passing ``""`` simulates a widget whose
            ``font_name`` hasn't been resolved yet.
        child_fonts: Mapping ``{attr_name: font_value}`` of internal
            Label attrs to expose. Each will be wrapped in a MagicMock
            with the given ``font_name`` already set.

    Returns:
        A MagicMock configured to behave like a KivyMD widget for the
        purposes of ``_sync_font_to_hint_labels``.
    """
    attrs = ["font_name"] + list(child_fonts.keys())
    widget = MagicMock(spec=attrs)
    widget.font_name = parent_font
    for attr, font_value in child_fonts.items():
        sub = MagicMock(spec=["font_name"])
        sub.font_name = font_value
        setattr(widget, attr, sub)
    return widget


@pytest.mark.skipif(
    not _KIVY_AVAILABLE,
    reason="Kivy not available.",
)
class TestSyncFontToHintLabelsHelper(KivyUnitTest):
    """Direct unit tests of ``_sync_font_to_hint_labels`` using
    ``MagicMock`` widgets so we don't depend on KivyMD instantiation.
    """

    def test_no_op_when_widget_has_no_font_name(self):
        from katrain.gui.widgets.factory import _sync_font_to_hint_labels

        widget = _make_mock_widget(parent_font="", child_fonts={})
        # Should not raise; should not touch anything.
        _sync_font_to_hint_labels(widget)

    def test_no_op_when_widget_has_no_hint_attrs(self):
        from katrain.gui.widgets.factory import _sync_font_to_hint_labels

        widget = _make_mock_widget(parent_font="MyFont.otf", child_fonts={})
        # No hint_label attrs exposed → helper has nothing to sync.
        _sync_font_to_hint_labels(widget)

    def test_propagates_font_name_to_hint_label(self):
        from katrain.gui.widgets.factory import _sync_font_to_hint_labels

        widget = _make_mock_widget(
            parent_font="MyFont.otf",
            child_fonts={"hint_text_label": "OldFont.otf"},
        )
        _sync_font_to_hint_labels(widget)
        assert widget.hint_text_label.font_name == "MyFont.otf"

    def test_no_change_when_already_in_sync(self):
        from katrain.gui.widgets.factory import _sync_font_to_hint_labels

        widget = _make_mock_widget(
            parent_font="MyFont.otf",
            child_fonts={"hint_text_label": "MyFont.otf"},
        )
        # Already in sync; should remain so without an unnecessary write.
        _sync_font_to_hint_labels(widget)
        assert widget.hint_text_label.font_name == "MyFont.otf"

    def test_propagates_to_all_known_internal_labels(self):
        from katrain.gui.widgets.factory import _HINT_LABEL_ATTRS, _sync_font_to_hint_labels

        child_fonts = {attr: "OldFont.otf" for attr in _HINT_LABEL_ATTRS}
        widget = _make_mock_widget(parent_font="MyFont.otf", child_fonts=child_fonts)
        _sync_font_to_hint_labels(widget)

        for attr in _HINT_LABEL_ATTRS:
            child = getattr(widget, attr)
            assert child.font_name == "MyFont.otf", f"{attr}.font_name not synced to parent"
