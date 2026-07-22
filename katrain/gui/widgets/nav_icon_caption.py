"""NavIconButtonWithCaption — Phase 287-F paired icon + caption widget.

The KV template ``<NavIconButtonWithCaption@BoxLayout>`` references
``root.caption_text``, ``root.tooltip_text``, ``root.icon`` and
``root.color``. Kivy's templating system requires these properties
to be declared on the parent class so children can bind to them via
``root.<property>``. Without the declarations the KV parser raises::

    AttributeError: 'NavIconButtonWithCaption' object has no attribute
    'caption_text'

(see Phase 287-F regression on first runtime). Declare them here.
"""

from __future__ import annotations

from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout


class NavIconButtonWithCaption(BoxLayout):
    """Vertical pair of a NavIconButton (icon) + a small text caption.

    Phase 287-F: replaces the previous icon-only nav buttons along the
    bottom of the main window so users can see what each button does
    at a glance. The icon still carries a tooltip_text that the
    TooltipMixin turns into a 500 ms long-press popup with the keyboard
    shortcut hint.

    The class registers an explicit ``on_press`` event so callers can
    write ``NavIconButtonWithCaption: on_press: root.katrain(...)`` in
    KV. The inner NavIconButton's ``on_press`` bubbles via
    ``root.dispatch('on_press')`` (see board.kv).
    """

    icon = StringProperty("")
    caption_text = StringProperty("")
    tooltip_text = StringProperty("")
    color = ListProperty([1, 1, 1, 1])

    def __init__(self, **kwargs: object) -> None:
        # Kivy KV's ``on_press: ...`` rule requires the class to have
        # registered that event type; otherwise the parser raises
        # ``AttributeError: press`` at load time. The inner
        # NavIconButton dispatches ``on_press`` to the parent via
        # ``root.dispatch('on_press')``, so we just need to register
        # the event here.
        self.register_event_type("on_press")
        super().__init__(**kwargs)

    def on_press(self) -> None:
        """Default no-op handler. Real handlers come from KV bindings."""
        pass
