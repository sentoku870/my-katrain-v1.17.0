# katrain/core/reports/insertion.py
"""Section insertion utilities for pluggable report sections.

PR #Phase55: Report foundation + User aggregation

This module provides:
- DuplicateSectionError: Exception for duplicate section_id
- SectionRegistration: Frozen dataclass for registration metadata
- compute_section_order: Algorithm for stable section ordering
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .section_registry import ReportSection

_logger = logging.getLogger("katrain.core.reports.insertion")


class DuplicateSectionError(Exception):
    """Raised when duplicate section_id is registered."""

    pass


@dataclass(frozen=True)
class SectionRegistration:
    """Registration metadata for a section."""

    section: ReportSection
    after_section_id: str | None = None
    enabled_by_default: bool = True


def compute_section_order(
    registrations: list[SectionRegistration],
    base_section_ids: list[str],
) -> tuple[list[SectionRegistration], list[str]]:
    """Compute ordered registrations with stable insertion.

    Stable insertion: Multiple sections with the same after_section_id
    are inserted in registration order (first registered = first in output).

    Args:
        registrations: From registry.get_registrations() (unique section_ids)
        base_section_ids: IDs of existing hardcoded sections (anchors)

    Returns:
        Tuple of (ordered_registrations, warnings)

    Raises:
        DuplicateSectionError: If duplicate section_id found (defensive check)

    Note:
        Warnings are returned, not logged. Caller is responsible for surfacing
        them via _logger.warning() or similar.
    """
    warnings: list[str] = []
    base_set = set(base_section_ids)
    result_ids: list[str] = list(base_section_ids)
    regs_by_id: dict[str, SectionRegistration] = {}
    pending: list[SectionRegistration] = []

    # Track insertion offsets per anchor for stable ordering
    insertion_offsets: dict[str, int] = defaultdict(int)

    # Defensive: check for duplicate section_ids in input
    seen_ids: set[str] = set()
    for reg in registrations:
        sid = reg.section.section_id
        if sid in seen_ids:
            raise DuplicateSectionError(f"Duplicate section_id '{sid}' in registrations")
        seen_ids.add(sid)

    # Filter enabled registrations and check base collision
    enabled: list[SectionRegistration] = []
    for reg in registrations:
        if not reg.enabled_by_default:
            continue
        sid = reg.section.section_id
        if sid in base_set:
            warnings.append(f"Section '{sid}' collides with base section ID. Skipping.")
            continue
        enabled.append(reg)
        regs_by_id[sid] = reg

    # First pass: process registrations with known anchors
    for reg in enabled:
        sid = reg.section.section_id
        if reg.after_section_id is None:
            result_ids.append(sid)
        elif reg.after_section_id in result_ids:
            anchor = reg.after_section_id
            base_idx = result_ids.index(anchor)
            insert_idx = base_idx + 1 + insertion_offsets[anchor]
            result_ids.insert(insert_idx, sid)
            insertion_offsets[anchor] += 1
        else:
            pending.append(reg)

    # Second pass: resolve chained dependencies
    max_iter = len(pending) + 1
    for _ in range(max_iter):
        if not pending:
            break
        still_pending = []
        made_progress = False
        for reg in pending:
            sid = reg.section.section_id
            if reg.after_section_id in result_ids:
                anchor = reg.after_section_id
                base_idx = result_ids.index(anchor)
                insert_idx = base_idx + 1 + insertion_offsets[anchor]
                result_ids.insert(insert_idx, sid)
                insertion_offsets[anchor] += 1
                made_progress = True
            else:
                still_pending.append(reg)

        if not made_progress and still_pending:
            for reg in still_pending:
                sid = reg.section.section_id
                after = reg.after_section_id
                # Unified message: covers both cycles and missing anchors
                warnings.append(f"Unresolved dependency: '{sid}' -> '{after}'. Appending at end.")
                result_ids.append(sid)
            break
        pending = still_pending

    # Build final list
    result = [regs_by_id[sid] for sid in result_ids if sid in regs_by_id]
    return result, warnings
