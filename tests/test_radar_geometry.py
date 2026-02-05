"""Tests for radar_geometry pure functions.

NO Kivy imports - all tests run in headless CI.
"""

import math

import pytest

from katrain.gui.widgets.radar_geometry import (
    AXIS_ORDER,
    build_mesh_data,
    calculate_vertex,
    get_data_polygon,
    get_label_position,
    get_pentagon_points,
    tier_to_color,
)


class TestCalculateVertex:
    """Tests for calculate_vertex function."""

    def test_axis_0_at_top(self):
        """Axis 0 (opening) should be at 12 o'clock (top). In Kivy, y > center."""
        x, y = calculate_vertex(0, 5.0, (100, 100), 50)
        assert abs(x - 100) < 0.01  # x = center (straight up)
        assert y == pytest.approx(150, abs=0.01)  # y = center + radius (up)

    def test_axis_0_angle_is_90_degrees(self):
        """Axis 0 should be at 90 degrees (12 o'clock position)."""
        x, y = calculate_vertex(0, 5.0, (0, 0), 100)
        angle = math.degrees(math.atan2(y, x))
        assert angle == pytest.approx(90, abs=0.1)

    def test_axes_clockwise_order(self):
        """Axes should be in clockwise order (angle decreasing)."""
        pts = [calculate_vertex(i, 5.0, (0, 0), 100) for i in range(5)]
        angles = [math.degrees(math.atan2(p[1], p[0])) for p in pts]
        # 90 deg -> 18 deg -> -54 deg -> -126 deg -> -198 deg (clockwise)
        expected = [90, 18, -54, -126, -198]
        for actual, exp in zip(angles, expected, strict=False):
            # -198 deg and 162 deg are the same (360 deg period)
            diff = (actual - exp + 180) % 360 - 180
            assert abs(diff) < 0.1

    def test_axes_72_degrees_apart(self):
        """Each axis should be 72 degrees apart."""
        pts = [calculate_vertex(i, 5.0, (0, 0), 100) for i in range(5)]
        for i in range(5):
            a1 = math.atan2(pts[i][1], pts[i][0])
            a2 = math.atan2(pts[(i + 1) % 5][1], pts[(i + 1) % 5][0])
            # Clockwise so a2 < a1 (or 360 deg wrap)
            diff = (a1 - a2) % (2 * math.pi)  # Positive difference
            assert diff == pytest.approx(math.radians(72), abs=0.01)

    def test_score_1_at_center(self):
        """Score 1.0 should be at center (radius 0)."""
        x, y = calculate_vertex(0, 1.0, (50, 50), 100)
        assert x == pytest.approx(50, abs=0.01)
        assert y == pytest.approx(50, abs=0.01)

    def test_score_5_at_max_radius(self):
        """Score 5.0 should be at max radius."""
        x, y = calculate_vertex(0, 5.0, (0, 0), 80)
        assert math.sqrt(x**2 + y**2) == pytest.approx(80, abs=0.01)

    def test_score_clamped_below(self):
        """Score < 1.0 should be clamped to 1.0."""
        v1 = calculate_vertex(0, 0.5, (0, 0), 100)
        v2 = calculate_vertex(0, 1.0, (0, 0), 100)
        assert v1 == pytest.approx(v2, abs=0.01)

    def test_score_clamped_above(self):
        """Score > 5.0 should be clamped to 5.0."""
        v1 = calculate_vertex(0, 10.0, (0, 0), 100)
        v2 = calculate_vertex(0, 5.0, (0, 0), 100)
        assert v1 == pytest.approx(v2, abs=0.01)

    @pytest.mark.parametrize(
        "score,expected_norm",
        [
            (1.0, 0.0),
            (3.0, 0.5),
            (5.0, 1.0),
            (2.0, 0.25),
            (4.0, 0.75),
        ],
    )
    def test_score_normalization(self, score, expected_norm):
        """Score normalization: (score-1)/(5-1) = normalized radius."""
        x, y = calculate_vertex(0, score, (0, 0), 100)
        actual_r = math.sqrt(x**2 + y**2)
        assert actual_r == pytest.approx(100 * expected_norm, abs=0.01)


class TestLabelPosition:
    """Tests for get_label_position function."""

    def test_label_same_angle_as_vertex(self):
        """Label position should have same angle as vertex (only radius differs)."""
        center = (0, 0)
        max_r = 100
        for i in range(5):
            vx, vy = calculate_vertex(i, 5.0, center, max_r)
            lx, ly = get_label_position(i, center, max_r, offset=1.2)
            # Angles should match
            v_angle = math.atan2(vy, vx)
            l_angle = math.atan2(ly, lx)
            assert v_angle == pytest.approx(l_angle, abs=0.01)
            # Label should be outside vertex
            assert math.sqrt(lx**2 + ly**2) > math.sqrt(vx**2 + vy**2)

    def test_label_axis_1_is_right_upper(self):
        """Axis 1 (Fighting) label should be in upper-right (angle ~18 degrees)."""
        lx, ly = get_label_position(1, (0, 0), 100, offset=1.0)
        angle = math.degrees(math.atan2(ly, lx))
        assert angle == pytest.approx(18, abs=1)  # 90 - 72 = 18


class TestPentagonPoints:
    """Tests for get_pentagon_points function."""

    def test_returns_12_floats(self):
        """5 vertices + close = 12 elements."""
        pts = get_pentagon_points(3.0, (0, 0), 100)
        assert len(pts) == 12

    def test_closes_properly(self):
        """Start and end points should match."""
        pts = get_pentagon_points(3.0, (0, 0), 100)
        assert abs(pts[0] - pts[-2]) < 0.01
        assert abs(pts[1] - pts[-1]) < 0.01


class TestDataPolygon:
    """Tests for get_data_polygon function."""

    def test_handles_none_scores(self):
        """None scores should default to 3.0 (neutral)."""
        scores = {
            "opening": None,
            "fighting": 4.0,
            "endgame": None,
            "stability": 2.0,
            "awareness": None,
        }
        pts = get_data_polygon(scores, (0, 0), 100)
        assert len(pts) == 12

    def test_all_same_is_regular(self):
        """All same scores should create a regular pentagon."""
        scores = {a: 3.0 for a in AXIS_ORDER}
        pts = get_data_polygon(scores, (0, 0), 100)
        dists = [math.sqrt(pts[i * 2] ** 2 + pts[i * 2 + 1] ** 2) for i in range(5)]
        assert all(abs(d - dists[0]) < 0.01 for d in dists)


class TestMeshData:
    """Tests for build_mesh_data function."""

    def test_vertex_count(self):
        """Center + 5 peripherals = 6 vertices, each with 4 elements."""
        poly = [0, 100, 95, 31, 59, -81, -59, -81, -95, 31, 0, 100]
        verts, _ = build_mesh_data(poly, (0, 0))
        assert len(verts) == 6 * 4

    def test_index_count(self):
        """5 triangles = 15 indices."""
        poly = [0, 100, 95, 31, 59, -81, -59, -81, -95, 31, 0, 100]
        _, inds = build_mesh_data(poly, (0, 0))
        assert len(inds) == 15

    def test_empty_polygon_returns_empty(self):
        """Empty polygon should return empty vertices and indices."""
        verts, inds = build_mesh_data([], (0, 0))
        assert verts == []
        assert inds == []

    def test_too_small_polygon_returns_empty(self):
        """Polygon with less than 8 elements should return empty."""
        # 4 elements = 2 points, not enough for a triangle
        verts, inds = build_mesh_data([0, 0, 10, 10], (0, 0))
        assert verts == []
        assert inds == []

        # 6 elements = 3 points but no closing, treated as 2 vertices
        verts, inds = build_mesh_data([0, 0, 10, 0, 5, 10], (0, 0))
        assert verts == []
        assert inds == []

    def test_minimum_valid_polygon(self):
        """8 elements (3 points + closing) should work - forms 2 triangles."""
        # Triangle: (0,0), (10,0), (5,10), closed by (0,0)
        poly = [0, 0, 10, 0, 5, 10, 0, 0]
        verts, inds = build_mesh_data(poly, (5, 5))
        # Should have center + 3 vertices = 4 vertices * 4 elements = 16
        assert len(verts) == 16
        # Should have 2 triangles + 1 closing = 9 indices
        assert len(inds) == 9
        assert verts != []
        assert inds != []

    def test_nan_in_polygon_returns_empty(self):
        """Polygon with NaN values should return empty."""
        poly = [0, float("nan"), 10, 0, 5, 10, 0, 0]
        verts, inds = build_mesh_data(poly, (5, 5))
        assert verts == []
        assert inds == []

    def test_inf_in_polygon_returns_empty(self):
        """Polygon with Inf values should return empty."""
        poly = [0, float("inf"), 10, 0, 5, 10, 0, 0]
        verts, inds = build_mesh_data(poly, (5, 5))
        assert verts == []
        assert inds == []

    def test_nan_in_center_returns_empty(self):
        """Center with NaN should return empty."""
        poly = [0, 0, 10, 0, 5, 10, 0, 0]
        verts, inds = build_mesh_data(poly, (float("nan"), 5))
        assert verts == []
        assert inds == []


class TestTierToColor:
    """Tests for tier_to_color function."""

    @pytest.mark.parametrize(
        "tier,expected_r,expected_g",
        [
            ("tier_5", 0.2, 0.7),  # Green
            ("tier_4", 0.2, 0.7),  # Green
            ("tier_3", 0.8, 0.7),  # Yellow
            ("tier_2", 0.8, 0.2),  # Red
            ("tier_1", 0.8, 0.2),  # Red
            ("unknown", 0.5, 0.5),  # Gray
        ],
    )
    def test_tier_colors(self, tier, expected_r, expected_g):
        c = tier_to_color(tier)
        assert abs(c[0] - expected_r) < 0.01
        assert abs(c[1] - expected_g) < 0.01

    def test_invalid_tier_returns_gray(self):
        c = tier_to_color("invalid_tier")
        assert c == tier_to_color("unknown")

    def test_tier_4_5_same_color(self):
        """Tier 4 and 5 should have same color (both advanced)."""
        assert tier_to_color("tier_4") == tier_to_color("tier_5")

    def test_tier_1_2_same_color(self):
        """Tier 1 and 2 should have same color (both novice)."""
        assert tier_to_color("tier_1") == tier_to_color("tier_2")

    def test_all_tiers_have_4_components(self):
        """All tier colors should be RGBA with 4 components."""
        for tier in ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5", "unknown"]:
            c = tier_to_color(tier)
            assert len(c) == 4
            assert all(0 <= v <= 1 for v in c)
