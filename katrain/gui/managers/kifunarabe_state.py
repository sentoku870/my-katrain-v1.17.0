"""Kifunarabe Controller — shared state attribute type hints.

Phase A3: each mixin declares the attributes it owns as instance-
attribute annotations. This file collects those into helper protocols
so mypy can verify the mixins agree on attribute types without forcing
runtime coupling.

Why this file exists
--------------------

Before Phase A3 the entire kifunarabe controller was a single 800-line
God Class. Splitting it into 4 mixin modules forces a clear contract
about which attributes the mixins touch. ``_ControllerSharedState`` is
the union of all instance attributes the facade's ``__init__``
initialises and the mixins subsequently read/write.

This module is **not** exported to the public API; it exists purely
for the runtime ``__init__`` type narrowing on the facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from katrain.core.study.kifunarabe import KifunarabeSession


class _ControllerSharedState:
    """Helper for mypy: declares (without initialising) the mixed
    attributes the facade owns.

    We deliberately keep this as a plain class (not a ``Protocol``) so
    that the facade's ``__init__`` can assign attributes with the wider
    types (``KifunarabeSession | None``, etc.) that mirror what the
    mixins read.
    """

    # Injected dependencies (set in facade ``__init__``).
    _get_ctx: Any
    _get_config: Any
    _get_game: Any
    _get_controls: Any
    _get_mode: Any
    _set_mode: Any
    _logger: Any

    # Optional callbacks (injected or None).
    _show_summary_fn: Any
    _on_guess_resolved_fn: Any

    # Session lifecycle attributes.
    _session: KifunarabeSession | None
    _source_sgf_path: str | None

    # Toggle snapshot.
    _saved_analysis_toggles: tuple[bool, bool] | None
    _last_critical_3_highlight: int

    # Summary popup tracking.
    _summary_popup: Any


__all__ = ["_ControllerSharedState"]
