"""Tests for Phase 155-A rank classifier."""
from __future__ import annotations

import pytest

from katrain.core.reports.utils.rank_classifier import (
    PRO_THRESHOLD,
    RankBucket,
    RankInfo,
    bucket_for_player,
    classify_rank_to_bucket,
)


class TestClassifyKyu:
    """Kyu rank parsing."""

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("1k", 1), ("5k", 5), ("10k", 10), ("30K", 30), (" 5k ", 5)],
    )
    def test_kyu_parses(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.KYU
        assert info.numeric == numeric
        assert info.is_dan is False
        assert info.is_pro is False


class TestClassifyDan:
    """Dan rank parsing (1d-6d, "weak amateur")."""

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("1d", 1), ("3d", 3), ("6d", 6), ("5D", 5), (" 6D ", 6)],
    )
    def test_dan_parses(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.DAN
        assert info.numeric == numeric
        assert info.is_dan is True
        assert info.is_pro is False


class TestClassifyHighDan:
    """High-dan / pro tier (>= 7d)."""

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("7d", 7), ("9d", 9), ("10d", 10), ("12D", 12)],
    )
    def test_high_dan(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.HIGH_DAN
        assert info.is_dan is True
        assert info.is_pro is True


class TestClassifyUnknown:
    """Empty / unparseable inputs return UNKNOWN."""

    @pytest.mark.parametrize("rank_str", [None, "", "  ", "?", "pro", "P", "5"])
    def test_unknown(self, rank_str: str | None):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.UNKNOWN
        assert info.numeric is None
        assert info.is_dan is False
        assert info.is_pro is False


class TestClassifyChineseKyu:
    """Phase 157-B: ``级`` (Chinese kyu) parses as KYU."""

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("5级", 5), ("15级", 15), ("30级", 30), ("1级", 1), (" 10级 ", 10)],
    )
    def test_chinese_kyu_parses(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.KYU
        assert info.numeric == numeric
        assert info.is_dan is False
        assert info.is_pro is False


class TestClassifyChineseDan:
    """Phase 157-B: ``段`` (Chinese dan) parses as DAN / HIGH_DAN."""

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("1段", 1), ("3段", 3), ("6段", 6), (" 4段 ", 4)],
    )
    def test_chinese_dan_parses(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.DAN
        assert info.numeric == numeric
        assert info.is_dan is True
        assert info.is_pro is False

    @pytest.mark.parametrize(
        "rank_str,numeric",
        [("7段", 7), ("9段", 9), ("10段", 10)],
    )
    def test_chinese_high_dan(self, rank_str: str, numeric: int):
        info = classify_rank_to_bucket(rank_str)
        assert info.bucket == RankBucket.HIGH_DAN
        assert info.numeric == numeric
        assert info.is_dan is True
        assert info.is_pro is True


class TestBucketForPlayerChinese:
    """Phase 157-B: ``bucket_for_player`` works with Chinese rank tokens."""

    def test_white_player_chinese_dan(self):
        assert bucket_for_player(None, "4段", "B") == RankBucket.DAN

    def test_black_player_chinese_kyu(self):
        assert bucket_for_player("15级", None, "W") == RankBucket.KYU

    def test_mixed_english_and_chinese(self):
        # B is English "5k", W is Chinese "4段".
        assert bucket_for_player("5k", "4段", "B") == RankBucket.DAN
        assert bucket_for_player("5k", "4段", "W") == RankBucket.KYU


class TestProThreshold:
    """Configurable pro threshold."""

    def test_default_threshold_is_seven(self):
        assert PRO_THRESHOLD == 7

    def test_custom_threshold(self):
        # With threshold=5, "5d" becomes high_dan.
        info = classify_rank_to_bucket("5d", pro_threshold=5)
        assert info.bucket == RankBucket.HIGH_DAN

    def test_custom_threshold_does_not_apply_below(self):
        info = classify_rank_to_bucket("4d", pro_threshold=5)
        assert info.bucket == RankBucket.DAN


class TestBucketForPlayer:
    """bucket_for_player returns the opponent's rank bucket."""

    def test_black_player_gets_white_rank(self):
        assert bucket_for_player("5d", "3k", "B") == RankBucket.KYU

    def test_white_player_gets_black_rank(self):
        assert bucket_for_player("5d", "3k", "W") == RankBucket.DAN

    def test_invalid_player_returns_unknown(self):
        assert bucket_for_player("5d", "3k", "X") == RankBucket.UNKNOWN

    def test_missing_rank(self):
        assert bucket_for_player(None, "3k", "B") == RankBucket.KYU
        assert bucket_for_player(None, None, "B") == RankBucket.UNKNOWN


class TestRankInfo:
    """RankInfo dataclass shape."""

    def test_kyu_dataclass(self):
        info = classify_rank_to_bucket("5k")
        assert isinstance(info, RankInfo)
        for f in ("bucket", "numeric", "is_dan", "is_pro"):
            assert hasattr(info, f)

    def test_frozen(self):
        info = classify_rank_to_bucket("5k")
        with pytest.raises((AttributeError, Exception)):
            info.bucket = RankBucket.DAN  # type: ignore[misc]