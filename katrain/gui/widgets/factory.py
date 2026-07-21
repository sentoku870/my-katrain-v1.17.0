from __future__ import annotations

from typing import Any

from kivy.clock import Clock
from kivy.uix.button import Button as _Button
from kivy.uix.label import Label as _Label
from kivy.uix.popup import Popup as _Popup

from katrain.gui.theme import Theme

# Phase 281 (tofu-fix): KivyMD 1.2.0 internal Label attributes that need
# their ``font_name`` explicitly synced from the parent widget. KivyMD
# widgets like ``MDTextField`` build child ``Label`` instances internally
# (hint text, helper text, error text, max-length counter) that do NOT
# inherit the parent's ``font_name`` binding. When the parent uses our
# ``Theme.DEFAULT_FONT`` (NotoSansJP) those internal labels fall back to
# Kivy's built-in Roboto and render Japanese text as tofu boxes.
#
# Extend this list whenever KivyMD adds a new internal Label widget
# in a future version.
_HINT_LABEL_ATTRS = (
    "hint_text_label",
    "_hint_text_label",
    "helper_text_label",
    "max_length_label",
    "error_label",
    "counter_label",
)


def _sync_font_to_hint_labels(widget: Any) -> None:
    """Sync ``widget.font_name`` to KivyMD internal Label children.

    KivyMD 1.2.0's ``MDTextField`` builds several internal Label widgets
    for hint text, helper text, error display, and the max-length counter.
    Those children do not inherit ``font_name`` from the parent reliably
    (the Kivy binding propagates asynchronously, which can race with the
    first paint). This helper walks the known internal-label attributes
    and overwrites ``font_name`` on each one so the resolved font path is
    applied before the widget is rendered.

    The function is a no-op if the widget doesn't expose any of the
    known attributes (e.g. plain ``kivy.uix.label.Label``), making it
    safe to call on any widget.
    """
    parent_font = getattr(widget, "font_name", None)
    if not parent_font:
        return
    for attr in _HINT_LABEL_ATTRS:
        sub = getattr(widget, attr, None)
        if sub is None:
            continue
        try:
            if getattr(sub, "font_name", None) != parent_font:
                sub.font_name = parent_font
        except AttributeError:
            # Some KivyMD versions expose these as Kivy Properties only
            # after a specific attribute is touched; skip silently.
            continue


def _schedule_hint_label_sync(widget: Any) -> None:
    """Schedule ``_sync_font_to_hint_labels`` on the next frame.

    Used by the factory wrappers so the sync happens after Kivy has
    finished applying the initial property bindings (avoiding a race
    where the internal Label hasn't been instantiated yet at
    ``__init__`` time).
    """
    Clock.schedule_once(lambda _dt: _sync_font_to_hint_labels(widget), 0)


class Label(_Label):
    """
    A Label that defaults to Theme.DEFAULT_FONT to prevent Tofu (garbled text).
    """

    def __init__(self, **kwargs: Any) -> None:
        if "font_name" not in kwargs:
            kwargs["font_name"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)
        _schedule_hint_label_sync(self)


class Button(_Button):
    """
    A Button that defaults to Theme.DEFAULT_FONT to prevent Tofu (garbled text).
    """

    def __init__(self, **kwargs: Any) -> None:
        if "font_name" not in kwargs:
            kwargs["font_name"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)
        _schedule_hint_label_sync(self)


class Popup(_Popup):
    """
    A Popup that defaults title_font to Theme.DEFAULT_FONT to prevent Tofu in titles.
    """

    def __init__(self, **kwargs: Any) -> None:
        if "title_font" not in kwargs:
            kwargs["title_font"] = Theme.DEFAULT_FONT
        super().__init__(**kwargs)
        _schedule_hint_label_sync(self)
