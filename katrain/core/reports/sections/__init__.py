"""Report sections package.

Phase 60: Time Management section for Summary/Karte reports.
"""

from .time_section import (
    TimeStatsData,
    format_tilt_episode,
    format_time_stats,
)

__all__ = [
    "format_time_stats",
    "format_tilt_episode",
    "TimeStatsData",
]
