"""Pure geometry calculations for radar chart.

NO Kivy imports - all functions are pure and deterministic.

Coordinate System (Kivy):
- Origin at bottom-left, Y increases upward
- Angle 0 degrees = right (3 o'clock), 90 degrees = up (12 o'clock)
- Counter-clockwise is positive angle direction

Radar Layout:
- Axis 0 (Opening) at 12 o'clock (top)
- Clockwise order: Opening -> Fighting -> Endgame -> Stability -> Awareness
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

NUM_AXES = 5
ANGLE_OFFSET_DEG = 90  # 12 o'clock position (top) = 90 degrees
AXIS_ORDER = ("opening", "fighting", "endgame", "stability", "awareness")
SCORE_MIN, SCORE_MAX = 1.0, 5.0
NEUTRAL_SCORE = 3.0


def calculate_vertex(
    axis_index: int,
    score: float,
    center: Tuple[float, float],
    max_radius: float,
) -> Tuple[float, float]:
    """Calculate (x, y) coordinate from axis index (0-4) and score (1.0-5.0).

    Args:
        axis_index: 0-4 (clockwise, 0=top)
        score: 1.0-5.0 (clamped if out of range)
        center: (cx, cy) center coordinate
        max_radius: radius when score=5.0

    Returns:
        (x, y) pixel coordinate (Kivy coordinate system: Y increases upward)

    Note:
        Clockwise = angle decrease, so OFFSET - 72*i
    """
    # Clockwise: 90 deg -> 18 deg -> -54 deg -> -126 deg -> -198 deg
    angle_deg = ANGLE_OFFSET_DEG - (360 / NUM_AXES) * axis_index
    angle_rad = math.radians(angle_deg)

    clamped = max(SCORE_MIN, min(SCORE_MAX, score))
    normalized = (clamped - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
    radius = max_radius * normalized

    x = center[0] + radius * math.cos(angle_rad)
    y = center[1] + radius * math.sin(angle_rad)
    return (x, y)


def get_pentagon_points(
    level: float,
    center: Tuple[float, float],
    max_radius: float,
) -> List[float]:
    """Get regular pentagon points for specified level (for grid).

    Returns:
        [x0, y0, x1, y1, ..., x0, y0] closed 12-element list
    """
    points: List[float] = []
    for i in range(NUM_AXES):
        x, y = calculate_vertex(i, level, center, max_radius)
        points.extend([x, y])
    points.extend(points[:2])  # Close the polygon
    return points


def get_data_polygon(
    scores: Dict[str, Optional[float]],
    center: Tuple[float, float],
    max_radius: float,
) -> List[float]:
    """Generate data polygon points from score dictionary.

    Args:
        scores: {"opening": 3.5, "fighting": None, ...}
    """
    points: List[float] = []
    for i, axis in enumerate(AXIS_ORDER):
        score = scores.get(axis) or NEUTRAL_SCORE
        x, y = calculate_vertex(i, score, center, max_radius)
        points.extend([x, y])
    points.extend(points[:2])
    return points


def get_label_position(
    axis_index: int,
    center: Tuple[float, float],
    max_radius: float,
    offset: float = 1.18,
) -> Tuple[float, float]:
    """Get axis label position (outside the pentagon).

    IMPORTANT: Must use the same angle formula as calculate_vertex!
    Clockwise = OFFSET - 72*i
    """
    # BUG FIX: Originally was + but changed to - to match calculate_vertex
    angle_deg = ANGLE_OFFSET_DEG - (360 / NUM_AXES) * axis_index
    angle_rad = math.radians(angle_deg)
    radius = max_radius * offset
    return (
        center[0] + radius * math.cos(angle_rad),
        center[1] + radius * math.sin(angle_rad),
    )


def build_mesh_data(
    polygon: List[float],
    center: Tuple[float, float],
) -> Tuple[List[float], List[int]]:
    """Generate vertices and indices for Kivy Mesh (triangle fan).

    Returns:
        (vertices, indices)
        vertices: [x, y, u, v, ...]
        indices: [0, 1, 2, 0, 2, 3, ...]
    """
    vertices: List[float] = [center[0], center[1], 0.0, 0.0]
    n = (len(polygon) - 2) // 2
    for i in range(n):
        vertices.extend([polygon[i * 2], polygon[i * 2 + 1], 0.0, 0.0])

    indices: List[int] = []
    for i in range(1, n):
        indices.extend([0, i, i + 1])
    indices.extend([0, n, 1])
    return (vertices, indices)


def tier_to_color(tier_value: str) -> List[float]:
    """Get color from tier string."""
    colors = {
        "tier_5": [0.2, 0.7, 0.2, 1.0],  # Green (Advanced/Elite)
        "tier_4": [0.2, 0.7, 0.2, 1.0],  # Green
        "tier_3": [0.8, 0.7, 0.2, 1.0],  # Yellow (Proficient)
        "tier_2": [0.8, 0.2, 0.2, 1.0],  # Red (Novice/Apprentice)
        "tier_1": [0.8, 0.2, 0.2, 1.0],  # Red
        "unknown": [0.5, 0.5, 0.5, 0.6],  # Gray
    }
    return colors.get(tier_value, colors["unknown"])
