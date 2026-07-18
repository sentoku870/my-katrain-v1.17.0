"""Phase 91-92 / 179-186: cached entry points.

Phase 196 extraction: wraps :mod:`._dispatch` so results are stored on
the node itself, keyed by the inputs that affect them
(``require_reliable``, ``summary_flags``, ``user_weak_tags``). The cache
sentinel ``_NOT_COMPUTED`` is private to this layer.

Detector / compute calls go through ``katrain.core.beginner.hints`` (the
package, *not* the dispatch module) so test code that does
``patch("katrain.core.beginner.hints.compute_summary_hint", ...)``
keeps working unchanged across the refactor.
"""

from __future__ import annotations

from typing import Any, cast

from katrain.core.beginner import hints as _hints_pkg
from katrain.core.beginner.models import BeginnerHint

# Sentinel value for cache (distinguishes None from "not computed").
_NOT_COMPUTED = object()

# Phase 179: Relaxed threshold for summary hints. Summary hints are
# informational and tolerate lower visits; MISTAKE_GOOD still requires
# >= 300 (enforced inside detector_mistake.py).
MIN_SUMMARY_VISITS = 100


def get_beginner_hint_cached(
    game: Any,
    node: Any,
    *,
    require_reliable: bool = True,
    category_filter: dict[str, bool] | None = None,
) -> BeginnerHint | None:
    """Get beginner hint with node-level caching (Phase 91-92).

    Phase 251: ``category_filter`` is part of the cache key so toggling
    an individual category in the settings UI invalidates the cached
    hint for the current node.
    """
    cache_attr = "_beginner_hint_cache"
    filter_key = None if not category_filter else tuple(sorted((k, bool(v)) for k, v in category_filter.items()))

    cached = getattr(node, cache_attr, _NOT_COMPUTED)
    if cached is not _NOT_COMPUTED and isinstance(cached, tuple) and len(cached) == 3:
        cached_require_reliable, cached_filter_key, cached_hint = cached
        if cached_require_reliable == require_reliable and cached_filter_key == filter_key:
            if cached_hint is None:
                return None
            return cast(BeginnerHint | None, cached_hint)

    hint = _hints_pkg.compute_beginner_hint(
        game, node, require_reliable=require_reliable, category_filter=category_filter
    )
    setattr(node, cache_attr, (require_reliable, filter_key, hint))
    return hint


def get_summary_hint_cached(
    node: Any,
    *,
    summary_flags: dict[str, bool] | None = None,
    require_reliable: bool = True,
    user_weak_tags: dict[str, int] | None = None,
    curator_min_occurrences: int = 3,
    category_filter: dict[str, bool] | None = None,
) -> BeginnerHint | None:
    """Phase 179 + 186: Cached wrapper around ``compute_summary_hint``.

    Phase 251: ``category_filter`` joined into the cache key.
    """
    cache_attr = "_summary_hint_cache"
    flags_key = None if not summary_flags else tuple(sorted((k, bool(v)) for k, v in summary_flags.items()))
    curator_key = None if not user_weak_tags else tuple(sorted((k, int(v)) for k, v in user_weak_tags.items()))
    filter_key = None if not category_filter else tuple(sorted((k, bool(v)) for k, v in category_filter.items()))
    cache_key = (flags_key, bool(require_reliable), curator_key, int(curator_min_occurrences), filter_key)
    cached = getattr(node, cache_attr, _NOT_COMPUTED)
    if cached is not _NOT_COMPUTED and isinstance(cached, tuple) and len(cached) == 2:
        cached_cache_key, cached_hint = cached
        if cached_cache_key == cache_key:
            return cast(BeginnerHint | None, cached_hint)

    hint = _hints_pkg.compute_summary_hint(
        node,
        summary_flags=summary_flags,
        require_reliable=require_reliable,
        user_weak_tags=user_weak_tags,
        curator_min_occurrences=curator_min_occurrences,
        category_filter=category_filter,
    )
    setattr(node, cache_attr, (cache_key, hint))
    return hint
