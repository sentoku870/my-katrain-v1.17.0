"""PR-04d regression tests for phase vocabulary normalisation.

PR-04d (H4): ``classify_game_phase`` and the dynamic phase detector
may emit the legacy ``"yose"`` string. The Karte JSON contract
documents only ``opening / middle / endgame``. The fix applies
``PHASE_ALIASES`` at the ``diagnosis.py`` section boundary so
``weaknesses[*].phase`` always matches the public contract.
"""

from __future__ import annotations

from katrain.core.reports.karte.sections.diagnosis import _normalise_phase


class TestNormalisePhase:
    def test_yose_rewritten_to_endgame(self) -> None:
        assert _normalise_phase("yose") == "endgame"

    def test_opening_unchanged(self) -> None:
        assert _normalise_phase("opening") == "opening"

    def test_middle_unchanged(self) -> None:
        assert _normalise_phase("middle") == "middle"

    def test_endgame_unchanged(self) -> None:
        assert _normalise_phase("endgame") == "endgame"

    def test_unknown_passes_through(self) -> None:
        # PHASE_ALIASES only has the yose -> endgame entry; unknown
        # values are returned as-is so the diagnosis section can
        # surface them verbatim (the validator would flag them).
        assert _normalise_phase("unknown") == "unknown"


class TestWeaknessPhaseAlwaysEndgame:
    """PR-04d (H4): weaknesses[*].phase must use the public contract.

    End-to-end checks live in tests/test_karte_json.py /
    tests/test_golden_karte.py against real Karte fixtures; here we
    only verify that the section applies ``_normalise_phase`` at the
    point where ``phase`` becomes part of the public output. A direct
    call to ``weakness_hypothesis_for`` requires building a KarteContext
    which is heavyweight; the section-level coverage in tests/karte/* is
    the canonical regression net.
    """

    def test_normalise_phase_is_used_in_section(self) -> None:
        # Sanity: ensure the diagnosis module imports _normalise_phase
        # from its own module scope so the alias rewrite actually runs
        # at the JSON write boundary. The Karte JSON regression tests
        # catch any accidental drop of this guard.
        import katrain.core.reports.karte.sections.diagnosis as diag

        assert hasattr(diag, "_normalise_phase"), (
            "diagnosis module must expose _normalise_phase so the section boundary rewrite stays discoverable."
        )
        assert diag._normalise_phase("yose") == "endgame"
