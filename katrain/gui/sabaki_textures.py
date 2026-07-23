"""Sabaki-style board and stone texture generators.

This module produces the same visual quality as Sabaki's default rendering
without bundling any PNG assets. All textures are generated at runtime
through ``Texture.create()`` + ``blit_buffer()`` (the same pattern used by
``badukpan_drawing.draw_territory_color``) and cached with ``lru_cache`` so
the per-frame cost is a single cached texture lookup.

Design notes
------------
Sabaki (https://github.com/SabakiHQ/Sabaki) renders the board and stones
purely with CSS gradients / box-shadow; the upstream repository does NOT
ship any PNG textures. This module reproduces the most distinctive visual
cues with deterministic pixel math:

* **Board**: vertical wooden stripes.  A smooth warm gradient on top of
  equally-spaced slightly darker bands reproduces the look of the wood
  grain you see in Sabaki's default theme.  The texture is wider than
  tall so the stripes stretch along the long edge when tiled.
* **Black stone**: radial gradient with a soft white highlight near the
  upper-left and a dark rim near the lower-right (Sabaki stones have a
  very subtle hemisphere look, not the glossy 3D ball used by KaTrain's
  default PNG).
* **White stone**: mirror image - the highlight is a faint shadow, the
  rim is slightly brighter, evoking a polished shell stone.

Activating
----------
The textures are gated behind ``Theme.STONE_TEXTURE_MODE`` and
``Theme.BOARD_TEXTURE_MODE``.  Users opt in via a ``theme-sabaki.json``
file (see ``themes/theme-sabaki.json`` in the repo root).  When the mode
is ``"default"`` (the upstream default) this module is not invoked.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from kivy.graphics.texture import Texture

from katrain.gui.theme import Theme

# Texture resolutions are picked to look smooth at any reasonable window
# size (KaTrain rarely exceeds ~1500 px on the long edge) while keeping the
# generation cost well under one frame.
BOARD_TEX_W = 128
BOARD_TEX_H = 1024

STONE_TEX_SIZE = 256

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    """Parse ``"#rrggbb"`` or ``"#rgb"`` into floats in [0, 1]."""
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        return (0.5, 0.5, 0.5)
    return (int(v[0:2], 16) / 255.0, int(v[2:4], 16) / 255.0, int(v[4:6], 16) / 255.0)


def _board_base_color() -> tuple[float, float, float]:
    """Return the base wood color for the Sabaki board.

    Falls back to a warm tan if ``Theme.BOARD_COLOR`` is missing or in an
    unexpected shape.
    """
    color = getattr(Theme, "BOARD_COLOR", [0.85, 0.68, 0.40, 1])
    try:
        r, g, b = float(color[0]), float(color[1]), float(color[2])
    except (TypeError, ValueError, IndexError):
        return (0.92, 0.78, 0.52)
    return (_clamp01(r), _clamp01(g), _clamp01(b))


# ---------------------------------------------------------------------------
# Board texture
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _generate_board_texture_bytes(
    width: int = BOARD_TEX_W,
    height: int = BOARD_TEX_H,
    base_hex: str = "auto",
) -> bytes:
    """Build the byte buffer for a Sabaki-style wooden board texture.

    The texture is **taller than wide** so that when tiled horizontally the
    stripes look like long grain planks.  Stripe spacing is tuned so the
    texture reads correctly at the smallest sensible board size (9x9).

    Args:
        width: Texture width in pixels (vertical stripe pitch).
        height: Texture height in pixels.
        base_hex: Base wood color in ``#rrggbb``.  ``"auto"`` reads
            ``Theme.BOARD_COLOR`` at generation time.
    """
    if base_hex == "auto":
        r, g, b = _board_base_color()
    else:
        r, g, b = _hex_to_rgb(base_hex)

    # Darker stripe color: mix the base toward dark brown.  The mix is
    # intentionally gentle (0.78) so the stripes read as wood plank
    # boundaries rather than dark bands - this matches Sabaki's
    # CSS-rendered plank look.
    dark_r, dark_g, dark_b = r * 0.78, g * 0.72, b * 0.62

    # 4 vertical stripes per tile width gives the broad-plank spacing
    # seen in Sabaki's default board (8-10 planks across a 19x19 board).
    stripe_period = max(8, width // 4)
    half_stripe = stripe_period * 0.12

    buf = bytearray(4 * width * height)
    for y in range(height):
        # Slow vertical luminance drift to avoid an obvious banded seam
        # at the tile boundary.
        v_drift = 1.0 + 0.05 * math.sin((y / height) * math.pi * 2.0)
        for x in range(width):
            # Position within the stripe (0..stripe_period).
            pos = x % stripe_period
            # Distance from nearest stripe edge in 0..1.
            edge_dist = min(pos, stripe_period - pos) / half_stripe
            # Stripe darkening: 0 at edge, 1 in the center.
            stripe_factor = _clamp01(edge_dist)
            # Smoothstep the stripe factor so the edges are soft.
            stripe_factor = stripe_factor * stripe_factor * (3 - 2 * stripe_factor)
            # Mix between dark stripe and base color.
            base_r = dark_r + (r - dark_r) * stripe_factor
            base_g = dark_g + (g - dark_g) * stripe_factor
            base_b = dark_b + (b - dark_b) * stripe_factor
            # Apply the slow vertical drift.
            cr = _clamp01(base_r * v_drift)
            cg = _clamp01(base_g * v_drift)
            cb = _clamp01(base_b * v_drift)
            # Add a tiny noise term so the stripes do not look perfectly
            # mechanical when blown up.
            noise = (((x * 1103515245 + y * 12345) & 0xFFFF) / 65535.0 - 0.5) * 0.012
            cr = _clamp01(cr + noise)
            cg = _clamp01(cg + noise)
            cb = _clamp01(cb + noise)

            idx = 4 * (y * width + x)
            buf[idx] = int(cr * 255)
            buf[idx + 1] = int(cg * 255)
            buf[idx + 2] = int(cb * 255)
            buf[idx + 3] = 255
    return bytes(buf)


@lru_cache(maxsize=4)
def get_sabaki_board_texture() -> Texture:
    """Return a cached Sabaki-style wooden board ``Texture``."""
    tex = Texture.create(size=(BOARD_TEX_W, BOARD_TEX_H), colorfmt="rgba")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    tex.wrap = "repeat"
    tex.blit_buffer(
        _generate_board_texture_bytes(),
        colorfmt="rgba",
        bufferfmt="ubyte",
    )
    return tex


# ---------------------------------------------------------------------------
# Stone textures
# ---------------------------------------------------------------------------


def _generate_stone_bytes(
    size: int = STONE_TEX_SIZE,
    *,
    is_white: bool,
    rim_darken: float = 0.55,
    highlight_offset: float = 0.32,
    highlight_strength: float = 0.18,
) -> bytes:
    """Build a Sabaki-style hemispherical stone texture.

    The gradient is intentionally understated compared to the default
    KaTrain PNGs - the look is closer to a flat matte pebble than a
    glossy billiard ball.

    Args:
        size: Square texture side in pixels.
        is_white: ``True`` for white stone, ``False`` for black.
        rim_darken: How much the rim is pulled toward the opposite extreme
            (0=no rim, 1=rim equals opposite color).
        highlight_offset: Position of the highlight blob (0..1, where 0 is
            exactly at the center and 1 is at the rim).
        highlight_strength: Strength of the highlight (0..1).
    """
    cx = (size - 1) * 0.5
    cy = (size - 1) * 0.5
    radius = (size - 1) * 0.5

    if is_white:
        base_r, base_g, base_b = 0.96, 0.95, 0.93
        rim_r, rim_g, rim_b = base_r * 0.78, base_g * 0.78, base_b * 0.78
        hl_r, hl_g, hl_b = 1.0, 1.0, 1.0
    else:
        base_r, base_g, base_b = 0.10, 0.10, 0.11
        rim_r, rim_g, rim_b = base_r * 1.55, base_g * 1.55, base_b * 1.55
        hl_r, hl_g, hl_b = 0.78, 0.78, 0.80

    # Highlight sits in the upper-left quadrant.
    hx = cx - radius * highlight_offset
    hy = cy + radius * highlight_offset
    highlight_radius = radius * 0.45

    buf = bytearray(4 * size * size)
    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > radius:
                # Fully transparent outside the stone disc.  The
                # ``Rectangle`` drawing instruction treats this as a
                # non-stone region when alpha < 1.
                idx = 4 * (y * size + x)
                buf[idx] = 0
                buf[idx + 1] = 0
                buf[idx + 2] = 0
                buf[idx + 3] = 0
                continue

            t = dist / radius  # 0 at center, 1 at rim.
            # Rim darkening (subtle, only kicks in near the edge).
            rim_t = max(0.0, (t - 0.7) / 0.3)
            cr = base_r + (rim_r - base_r) * rim_t * rim_darken
            cg = base_g + (rim_g - base_g) * rim_t * rim_darken
            cb = base_b + (rim_b - base_b) * rim_t * rim_darken

            # Highlight blob.
            hdx = x - hx
            hdy = y - hy
            hdist = math.sqrt(hdx * hdx + hdy * hdy)
            if hdist < highlight_radius:
                ht = 1.0 - (hdist / highlight_radius)
                # Smoothstep so the highlight edge is soft.
                ht = ht * ht * (3 - 2 * ht)
                cr = cr + (hl_r - cr) * ht * highlight_strength
                cg = cg + (hl_g - cg) * ht * highlight_strength
                cb = cb + (hl_b - cb) * ht * highlight_strength

            idx = 4 * (y * size + x)
            buf[idx] = int(_clamp01(cr) * 255)
            buf[idx + 1] = int(_clamp01(cg) * 255)
            buf[idx + 2] = int(_clamp01(cb) * 255)
            buf[idx + 3] = 255
    return bytes(buf)


@lru_cache(maxsize=4)
def _get_sabaki_stone_texture(is_white: bool) -> Texture:
    tex = Texture.create(size=(STONE_TEX_SIZE, STONE_TEX_SIZE), colorfmt="rgba")
    tex.mag_filter = "linear"
    tex.min_filter = "linear"
    tex.blit_buffer(
        _generate_stone_bytes(STONE_TEX_SIZE, is_white=is_white),
        colorfmt="rgba",
        bufferfmt="ubyte",
    )
    return tex


def get_sabaki_stone_texture(player: str) -> Texture:
    """Return a cached Sabaki-style stone ``Texture`` for ``"B"`` or ``"W"``."""
    return _get_sabaki_stone_texture(player == "W")


# ---------------------------------------------------------------------------
# Mode-aware dispatcher
# ---------------------------------------------------------------------------


def is_sabaki_board_mode() -> bool:
    """True iff the board texture should come from the Sabaki generator."""
    return getattr(Theme, "BOARD_TEXTURE_MODE", "default") == "sabaki"


def is_sabaki_stone_mode() -> bool:
    """True iff the stone textures should come from the Sabaki generator."""
    return getattr(Theme, "STONE_TEXTURE_MODE", "default") == "sabaki"


def get_board_texture_or_none() -> Any:
    """Return the Sabaki board ``Texture`` when in Sabaki mode, else ``None``.

    Returning ``None`` lets callers fall back to the default PNG cache
    without duplicating the if-tree at every call site.
    """
    if is_sabaki_board_mode():
        return get_sabaki_board_texture()
    return None


def get_stone_texture_or_none(player: str) -> Any:
    """Return the Sabaki stone ``Texture`` for ``player`` when in Sabaki mode."""
    if is_sabaki_stone_mode():
        return get_sabaki_stone_texture(player)
    return None


__all__ = [
    "get_board_texture_or_none",
    "get_sabaki_board_texture",
    "get_sabaki_stone_texture",
    "get_stone_texture_or_none",
    "is_sabaki_board_mode",
    "is_sabaki_stone_mode",
]
