"""Popup geometry helpers (Kivy-independent core).

Phase 287-E introduced a popup-size clamp that previously lived in
``katrain/gui/popups/_base.py``. That placement forced the GUI layer
to also be imported from headless tests (which copy the function
body inline to avoid the Kivy import), and pulled a Kivy-only helper
into the GUI module for what is mathematically pure logic.

This module hosts the Kivy-independent pure-Python half of the
helper: given a requested ``[width, height]`` and the (optional)
current window dimensions, return the clamped ``[width, height]``.
The GUI layer can wrap this core helper to inject the live ``Window``
measurements; headless tests can call it directly without any Kivy
import path.
"""

from __future__ import annotations


def compute_clamped_popup_size(
    requested: list[float],
    window_width: float | None = None,
    window_height: float | None = None,
    max_ratio: float = 0.9,
) -> list[int]:
    """Return ``[width, height]`` clamped to ``max_ratio`` of the given window.

    This is the Kivy-independent, deterministic half of the popup
    sizing logic. Pass ``window_width`` / ``window_height`` explicitly
    (e.g. via ``kivy.core.window.Window``); when either is ``None`` or
    non-positive the corresponding dimension is left unchanged.

    Args:
        requested: ``[width, height]`` in dp / px.
        window_width: Current window width in px, or ``None``.
        window_height: Current window height in px, or ``None``.
        max_ratio: Maximum fraction of the window dimension the popup
            may occupy. Default 0.9 leaves a 5% margin on each side.

    Returns:
        A fresh ``[width, height]`` list with each dimension clamped
        independently and rounded to int (Kivy Popup size takes int).
    """
    width = float(requested[0])
    height = float(requested[1])
    if window_width and window_width > 0:
        width = min(width, window_width * max_ratio)
    if window_height and window_height > 0:
        height = min(height, window_height * max_ratio)
    return [int(round(width)), int(round(height))]
