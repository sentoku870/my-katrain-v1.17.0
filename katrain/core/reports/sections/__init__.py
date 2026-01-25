# -*- coding: utf-8 -*-
"""Report sections package.

Phase 60: Time Management section for Summary/Karte reports.
"""

from .time_section import (
    format_time_stats,
    format_tilt_episode,
    TimeStatsData,
)

__all__ = [
    "format_time_stats",
    "format_tilt_episode",
    "TimeStatsData",
]
