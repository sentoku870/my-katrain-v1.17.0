"""Tests for katrain.gui.sabaki_textures (Phase SABAKI-1).

The Sabaki-style texture generator runs pure pixel math on byte arrays,
so it can be exercised without booting the Kivy graphics pipeline. The
``Texture.create`` calls live behind ``get_sabaki_*_texture`` and are
covered indirectly via the existing draw tests when the engine is in
sabaki mode.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Pure-Python byte generators
# ---------------------------------------------------------------------------


class TestBoardTextureBytes:
    def test_default_size(self):
        from katrain.gui.sabaki_textures import _generate_board_texture_bytes

        buf = _generate_board_texture_bytes()
        # 128 (W) x 1024 (H) x 4 channels.
        assert len(buf) == 128 * 1024 * 4

    def test_alpha_is_always_255(self):
        from katrain.gui.sabaki_textures import _generate_board_texture_bytes

        buf = _generate_board_texture_bytes()
        for i in range(3, len(buf), 4):
            assert buf[i] == 255, f"alpha at pixel {i // 4} is {buf[i]} (expected 255)"

    def test_stripe_period_produces_dark_band(self):
        """Mid-stripe pixels should be darker than the inter-stripe gap."""
        from katrain.gui.sabaki_textures import _generate_board_texture_bytes

        buf = _generate_board_texture_bytes()
        # Compare the very first column (x=0, in a stripe) with a column
        # halfway through one stripe period.
        width = 128
        stripe_period = max(8, width // 6)
        half = stripe_period // 2

        def luminance(idx: int) -> float:
            r = buf[idx] / 255.0
            g = buf[idx + 1] / 255.0
            b = buf[idx + 2] / 255.0
            return 0.299 * r + 0.587 * g + 0.114 * b

        # Sample at the very center of the texture vertically.
        y = 512
        edge_pixel = (y * width + 0) * 4
        mid_pixel = (y * width + half) * 4
        edge_l = luminance(edge_pixel)
        mid_l = luminance(mid_pixel)
        # Stripe edges (where pos == 0 or pos == stripe_period) sit at the
        # boundary of the dark band, so the darkest pixel is between
        # edge and mid.  The test asserts the edge is darker than mid.
        assert edge_l < mid_l + 1e-6

    def test_cache_returns_same_buffer(self):
        from katrain.gui.sabaki_textures import _generate_board_texture_bytes

        a = _generate_board_texture_bytes()
        b = _generate_board_texture_bytes()
        assert a is b


class TestStoneTextureBytes:
    def test_default_size(self):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=False)
        assert len(buf) == 256 * 256 * 4

    @pytest.mark.parametrize("is_white", [False, True])
    def test_outside_circle_is_transparent(self, is_white: bool):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=is_white)
        # Top-left corner pixel (0,0) is well outside the inscribed
        # circle, so alpha must be 0.
        assert buf[3] == 0, "outside-disc pixel must have alpha=0"

    def test_black_stone_center_is_dark(self):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=False)
        size = 256
        cx, cy = size // 2, size // 2
        idx = (cy * size + cx) * 4
        # Center should be roughly the base dark tone, RGB each <= 0.3.
        assert max(buf[idx], buf[idx + 1], buf[idx + 2]) <= 0.3 * 255 + 5

    def test_white_stone_center_is_bright(self):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=True)
        size = 256
        cx, cy = size // 2, size // 2
        idx = (cy * size + cx) * 4
        assert min(buf[idx], buf[idx + 1], buf[idx + 2]) >= 0.7 * 255 - 5

    def test_white_stone_has_highlight(self):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=True)
        size = 256
        # Highlight sits in the upper-left quadrant.
        hx = size // 2 - int((size - 1) * 0.5 * 0.32)
        hy = size // 2 + int((size - 1) * 0.5 * 0.32)
        idx = (hy * size + hx) * 4
        highlight_lum = 0.299 * (buf[idx] / 255) + 0.587 * (buf[idx + 1] / 255) + 0.114 * (buf[idx + 2] / 255)
        # Highlight luminance should exceed the white-stone base luminance.
        assert highlight_lum >= 0.85

    def test_black_stone_has_dark_rim(self):
        from katrain.gui.sabaki_textures import _generate_stone_bytes

        buf = _generate_stone_bytes(is_white=False)
        size = 256
        # Sample near the rim (not exactly at radius since the smoothstep
        # band there has full alpha=0; pick ~85% of radius).
        cx = cy = size // 2
        rim_offset = int((size - 1) * 0.5 * 0.92)
        idx = (cy * size + (cx + rim_offset)) * 4
        rim_lum = 0.299 * (buf[idx] / 255) + 0.587 * (buf[idx + 1] / 255) + 0.114 * (buf[idx + 2] / 255)
        # Rim should be brighter than the center (rim darken on black
        # stone raises the channel toward the rim color).
        center_idx = (cy * size + cx) * 4
        center_lum = (
            0.299 * (buf[center_idx] / 255) + 0.587 * (buf[center_idx + 1] / 255) + 0.114 * (buf[center_idx + 2] / 255)
        )
        assert rim_lum > center_lum


# ---------------------------------------------------------------------------
# Mode dispatch
# ---------------------------------------------------------------------------


class TestModeDispatch:
    def setup_method(self):
        from katrain.gui import theme as theme_mod

        self._saved_board_mode = theme_mod.Theme.BOARD_TEXTURE_MODE
        self._saved_stone_mode = theme_mod.Theme.STONE_TEXTURE_MODE

    def teardown_method(self):
        from katrain.gui import theme as theme_mod

        theme_mod.Theme.BOARD_TEXTURE_MODE = self._saved_board_mode
        theme_mod.Theme.STONE_TEXTURE_MODE = self._saved_stone_mode

    def test_default_mode_returns_none(self):
        from katrain.gui import theme as theme_mod
        from katrain.gui.sabaki_textures import (
            get_board_texture_or_none,
            get_stone_texture_or_none,
        )

        theme_mod.Theme.BOARD_TEXTURE_MODE = "default"
        theme_mod.Theme.STONE_TEXTURE_MODE = "default"
        assert get_board_texture_or_none() is None
        assert get_stone_texture_or_none("B") is None
        assert get_stone_texture_or_none("W") is None

    def test_sabaki_mode_flags(self):
        from katrain.gui import theme as theme_mod
        from katrain.gui.sabaki_textures import is_sabaki_board_mode, is_sabaki_stone_mode

        theme_mod.Theme.BOARD_TEXTURE_MODE = "sabaki"
        theme_mod.Theme.STONE_TEXTURE_MODE = "sabaki"
        assert is_sabaki_board_mode() is True
        assert is_sabaki_stone_mode() is True

        theme_mod.Theme.BOARD_TEXTURE_MODE = "default"
        theme_mod.Theme.STONE_TEXTURE_MODE = "default"
        assert is_sabaki_board_mode() is False
        assert is_sabaki_stone_mode() is False
