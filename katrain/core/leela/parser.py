"""Parser for Leela Zero lz-analyze output.

Parses the GTP extended output format from lz-analyze command.
"""

import logging
import re
from typing import List, Optional

from katrain.core.leela.models import LeelaCandidate, LeelaPositionEval

logger = logging.getLogger(__name__)


# Regex pattern for parsing lz-analyze output
# Format: info move <coord> visits <n> winrate <wr> order <ord> pv <moves...>
CANDIDATE_PATTERN = re.compile(
    r"info\s+move\s+(\w+)\s+"  # move coordinate
    r"visits\s+(\d+)\s+"  # visits count
    r"winrate\s+(\d+)\s+"  # winrate (integer)
    r"order\s+(\d+)\s+"  # order (0-based)
    r"pv\s+([\w\s]+?)(?=\s*info\s+move|\s*$)",  # pv sequence
    re.IGNORECASE,
)


def normalize_winrate_from_raw(raw: float) -> float:
    """Normalize raw winrate value to 0.0-1.0 range.

    Handles different output formats:
    - raw > 100: Assume 0-10000 scale (Leela 0.110), divide by 10000
    - raw > 1.0: Assume 0-100 scale, divide by 100
    - raw <= 1.0: Already 0-1 scale, use as-is
    - Out of range: Clamp to 0.0-1.0

    Args:
        raw: Raw winrate value from engine output

    Returns:
        Normalized winrate in 0.0-1.0 range
    """
    if raw > 100:
        # Leela 0.110 format: 0-10000
        raw = raw / 10000.0
    elif raw > 1.0:
        # Percentage format: 0-100
        raw = raw / 100.0
    # Clamp to valid range
    return max(0.0, min(1.0, raw))


def parse_lz_analyze(raw_output: str) -> LeelaPositionEval:
    """Parse lz-analyze output into LeelaPositionEval.

    Contract:
    - winrate is always returned as 0.0-1.0 normalized
    - Candidates without valid winrate are skipped (not included in candidates)
    - Returns LeelaPositionEval with parse_error if parsing fails completely

    Args:
        raw_output: Raw string output from lz-analyze command

    Returns:
        LeelaPositionEval with parsed candidates
    """
    if not raw_output or not raw_output.strip():
        logger.debug("Empty lz-analyze output")
        return LeelaPositionEval(parse_error="Empty output")

    # Check for GTP error response
    if raw_output.strip().startswith("?"):
        error_msg = raw_output.strip()
        logger.warning(f"GTP error in lz-analyze: {error_msg}")
        return LeelaPositionEval(parse_error=f"GTP error: {error_msg}")

    candidates: List[LeelaCandidate] = []
    skipped_count = 0

    # Find all candidate matches
    matches = CANDIDATE_PATTERN.findall(raw_output)

    for match in matches:
        try:
            move = match[0].upper()
            visits_str = match[1]
            winrate_str = match[2]
            order_str = match[3]
            pv_str = match[4].strip()

            # Parse visits
            visits = int(visits_str)
            if visits < 1:
                logger.debug(f"Skipping candidate {move}: visits={visits} < 1")
                skipped_count += 1
                continue

            # Parse winrate
            try:
                raw_winrate = float(winrate_str)
            except ValueError:
                logger.debug(f"Skipping candidate {move}: invalid winrate '{winrate_str}'")
                skipped_count += 1
                continue

            winrate = normalize_winrate_from_raw(raw_winrate)

            # Parse order (not used in model but validates format)
            _ = int(order_str)

            # Parse PV
            pv = pv_str.split() if pv_str else []

            candidate = LeelaCandidate(
                move=move,
                winrate=winrate,
                visits=visits,
                pv=pv,
                prior=None,
                loss_est=None,
            )
            candidates.append(candidate)

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse candidate: {match}, error: {e}")
            skipped_count += 1
            continue

    if skipped_count > 0:
        logger.debug(f"Skipped {skipped_count} candidates without valid data")

    if not candidates:
        # No valid candidates found
        if matches:
            logger.warning("No valid candidates (all had invalid winrate or visits)")
            return LeelaPositionEval(parse_error="No valid candidates (winrate missing)")
        else:
            # Check if output contains 'info' at all
            if "info" not in raw_output.lower():
                logger.debug("No 'info' lines in output")
                return LeelaPositionEval(parse_error="No analysis data")
            else:
                logger.warning("Failed to parse any candidates from output")
                return LeelaPositionEval(parse_error="Parse failed")

    # Sort by visits (descending) to ensure best candidates first
    candidates.sort(key=lambda c: c.visits, reverse=True)

    return LeelaPositionEval(candidates=candidates)


def parse_single_info_line(line: str) -> Optional[LeelaCandidate]:
    """Parse a single info segment into a LeelaCandidate.

    Utility function for testing or incremental parsing.

    Args:
        line: Single info segment (e.g., "info move C4 visits 100 winrate 5000 order 0 pv C4 D4")

    Returns:
        LeelaCandidate if parsing succeeds, None otherwise
    """
    result = parse_lz_analyze(line)
    if result.candidates:
        return result.candidates[0]
    return None
