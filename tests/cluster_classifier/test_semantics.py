"""ClusterSemantics enum, opponent-gain, and localized labels (Phase G-1).

Extracted from tests/test_cluster_classifier.py. Covers the
``ClusterSemantics`` enum, the ``is_opponent_gain`` predicate, and
the :func:`get_semantics_label` i18n helper.
"""

from __future__ import annotations

from katrain.core.analysis.cluster_classifier import (
    ClusterSemantics,
    get_semantics_label,
    is_opponent_gain,
)
from katrain.core.analysis.ownership_cluster import ClusterType
from tests.cluster_classifier._helpers import create_mock_cluster


class TestClusterSemantics:
    """Test ClusterSemantics enum."""

    def test_enum_values(self):
        assert ClusterSemantics.GROUP_DEATH.value == "group_death"
        assert ClusterSemantics.TERRITORY_LOSS.value == "territory_loss"
        assert ClusterSemantics.MISSED_KILL.value == "missed_kill"
        assert ClusterSemantics.AMBIGUOUS.value == "ambiguous"

    def test_str_conversion(self):
        # str(Enum) gives value because ClusterSemantics inherits from str
        assert ClusterSemantics.GROUP_DEATH.value == "group_death"


# =====================================================================
# TestIsOpponentGain
# =====================================================================


class TestIsOpponentGain:
    """Test is_opponent_gain helper."""

    def test_black_actor_white_gains(self):
        """sum_delta < 0 means white gains (opponent of black)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,  # White gains
        )
        assert is_opponent_gain(cluster, "B") is True

    def test_black_actor_no_gain(self):
        """sum_delta > 0 means black gains (actor's gain, not opponent)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=2.0,  # Black gains
        )
        assert is_opponent_gain(cluster, "B") is False

    def test_white_actor_black_gains(self):
        """sum_delta > 0 means black gains (opponent of white)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            cluster_type=ClusterType.TO_BLACK,
            sum_delta=2.0,  # Black gains
        )
        assert is_opponent_gain(cluster, "W") is True

    def test_white_actor_no_gain(self):
        """sum_delta < 0 means white gains (actor's gain)."""
        cluster = create_mock_cluster(
            coords=frozenset([(0, 0)]),
            sum_delta=-2.0,  # White gains
        )
        assert is_opponent_gain(cluster, "W") is False


# =====================================================================
# TestComputeStonesAtNode
# =====================================================================
class TestGetSemanticsLabel:
    """Test localized labels."""

    def test_none_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, None)
        assert label == "Group captured"

    def test_empty_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "")
        assert label == "Group captured"

    def test_jp(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "jp")
        assert label == "石が取られた"

    def test_ja_normalized_to_jp(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "ja")
        assert label == "石が取られた"

    def test_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "en")
        assert label == "Group captured"

    def test_unknown_falls_back_to_en(self):
        label = get_semantics_label(ClusterSemantics.GROUP_DEATH, "fr")
        assert label == "Group captured"

    def test_all_semantics_have_labels(self):
        """All semantics have labels for both languages."""
        for semantics in ClusterSemantics:
            en_label = get_semantics_label(semantics, "en")
            jp_label = get_semantics_label(semantics, "jp")
            assert en_label, f"Missing en label for {semantics}"
            assert jp_label, f"Missing jp label for {semantics}"


# =====================================================================
# TestStoneCache
# =====================================================================
