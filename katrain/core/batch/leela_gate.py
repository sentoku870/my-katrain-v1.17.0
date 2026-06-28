"""UI gating helpers for batch analysis (Leela karte warnings)."""

from __future__ import annotations


def needs_leela_karte_warning(analysis_engine: str, generate_karte: bool) -> bool:
    """Check if Leela+karte warning should be displayed.

    Phase 36 MVP restriction: Leela batch analysis does not fully support
    karte generation. This function determines if a warning should be shown
    to the user when they select Leela with karte generation enabled.

    Args:
        analysis_engine: Selected analysis engine ("katago" or "leela")
        generate_karte: Whether karte generation is enabled

    Returns:
        True if warning should be displayed (Leela + karte enabled)
        False otherwise

    Example:
        >>> needs_leela_karte_warning("leela", generate_karte=True)
        True
        >>> needs_leela_karte_warning("leela", generate_karte=False)
        False
        >>> needs_leela_karte_warning("katago", generate_karte=True)
        False
    """
    return analysis_engine == "leela" and generate_karte
