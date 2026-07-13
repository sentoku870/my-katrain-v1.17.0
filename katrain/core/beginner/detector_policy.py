"""Phase 182: Policy Summary Hint Detectors

Derives beginner hints from KataGo's policy probability distribution
(``node.policy`` flat list). The maximum probability captures how
"decided" KataGo's first choice is — high values mean one move stands
out, low values mean the top candidates are nearly tied.

Categories:
- POLICY_CONFIDENT: best_policy >= threshold_confident (default 0.5)
- POLICY_CONFLICT:  best_policy <= threshold_conflict (default 0.15)

Design notes:
- Both detectors are pure: they read ``best_policy`` from the
  pre-computed SummaryHintContext.
- Severity is 0/1 (lowest). Pure context info; never outranks mistake /
  structural hints.
- ``best_policy`` is computed by ``_compute_summary_context`` from
  ``node.policy``. If the policy list is empty or missing, the field is
  None and both detectors return None.
- POLICY_CONFIDENT and POLICY_CONFLICT are mutually exclusive by
  construction: confident uses ``>= 0.5`` and conflict uses ``<= 0.15``.
  The priority chain picks one (CONFIDENT first when both somehow apply
  via threshold overlap).
"""

from __future__ import annotations

from katrain.core.beginner.models import BeginnerHint, HintCategory, SummaryHintContext

# Phase 182: minimum visits for the policy estimate to be stable enough
# to fire any of the policy hints. Below this, the network is biased
# toward the prior and produces extreme best_policy values.
_POLICY_MIN_VISITS = 100


def detect_policy_confident(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Policy confident summary hint (Phase 182).

    Fires when KataGo's top-policy probability is high (>= 0.5), meaning
    one move clearly stands out as KataGo's preferred choice.
    """
    if ctx.best_policy is None:
        return None
    if ctx.root_visits < _POLICY_MIN_VISITS:
        return None

    value = float(ctx.best_policy)
    threshold = float(ctx.best_policy_threshold_confident)
    if value < threshold:
        return None

    return BeginnerHint(
        category=HintCategory.POLICY_CONFIDENT,
        coords=None,
        severity=0,
        context={"best_policy": value, "threshold": threshold},
    )


def detect_policy_conflict(ctx: SummaryHintContext) -> BeginnerHint | None:
    """Detect Policy conflict summary hint (Phase 182).

    Fires when KataGo's top-policy probability is low (<= 0.15), meaning
    multiple candidates are roughly equally good and KataGo is unsure
    which to recommend.
    """
    if ctx.best_policy is None:
        return None
    if ctx.root_visits < _POLICY_MIN_VISITS:
        return None

    value = float(ctx.best_policy)
    threshold = float(ctx.best_policy_threshold_conflict)
    if value > threshold:
        return None

    return BeginnerHint(
        category=HintCategory.POLICY_CONFLICT,
        coords=None,
        severity=1,
        context={"best_policy": value, "threshold": threshold},
    )


__all__ = ["detect_policy_confident", "detect_policy_conflict"]
