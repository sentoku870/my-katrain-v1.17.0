"""Data models for Leela Zero analysis results.

These models are separate from KataGo's analysis structures.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LeelaCandidate:
    """Leela candidate move evaluation.

    Attributes:
        move: GTP coordinate (e.g., "R6", "pass")
        winrate: Win probability as 0.0-1.0 ratio (internal representation)
        visits: Search visit count
        pv: Principal variation (reading sequence)
        prior: Prior probability 0.0-1.0 (if available, else None)
        loss_est: Estimated loss after compute_estimated_loss() (else None)
    """

    move: str
    winrate: float  # 0.0-1.0 normalized
    visits: int
    pv: List[str] = field(default_factory=list)
    prior: Optional[float] = None
    loss_est: Optional[float] = None  # Set by compute_estimated_loss()

    @property
    def eval_pct(self) -> float:
        """Display evaluation as percentage (0-100)."""
        return self.winrate * 100.0

    def __post_init__(self) -> None:
        """Validate and clamp winrate to 0.0-1.0."""
        if self.winrate < 0.0:
            self.winrate = 0.0
        elif self.winrate > 1.0:
            self.winrate = 1.0


@dataclass
class LeelaPositionEval:
    """Leela position evaluation (one move's analysis result).

    Attributes:
        candidates: List of candidate moves with evaluations
        root_visits: Total visits at root (sum of all candidates if not explicit)
        parse_error: Error message if parsing failed (else None)
    """

    candidates: List[LeelaCandidate] = field(default_factory=list)
    root_visits: int = 0
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if this evaluation is valid (has candidates and no error)."""
        return len(self.candidates) > 0 and self.parse_error is None

    @property
    def best_candidate(self) -> Optional[LeelaCandidate]:
        """Get the best candidate (order 0, or highest winrate)."""
        if not self.candidates:
            return None
        # Candidates should already be sorted by order, but use max as fallback
        return max(self.candidates, key=lambda c: c.winrate)

    @property
    def best_winrate(self) -> Optional[float]:
        """Get best candidate's winrate (0.0-1.0)."""
        best = self.best_candidate
        return best.winrate if best else None

    @property
    def best_eval_pct(self) -> Optional[float]:
        """Get best candidate's evaluation as percentage (0-100)."""
        best = self.best_candidate
        return best.eval_pct if best else None

    def __post_init__(self) -> None:
        """Calculate root_visits if not set."""
        if self.root_visits == 0 and self.candidates:
            self.root_visits = sum(c.visits for c in self.candidates)
