"""
Test helpers for KaTrain E2E tests.

This package provides utilities for:
- Mock analysis injection
- Stats extraction from mock-analyzed games
"""

from .mock_analysis import (
    LOSS_AT_MOVE,
    create_mock_analysis_dict,
    inject_mock_analysis,
)
from .stats_extraction import extract_stats_from_nodes

__all__ = [
    "LOSS_AT_MOVE",
    "create_mock_analysis_dict",
    "inject_mock_analysis",
    "extract_stats_from_nodes",
]
