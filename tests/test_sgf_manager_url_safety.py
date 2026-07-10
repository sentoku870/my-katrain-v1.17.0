"""Tests for SSRF defense in sgf_manager URL fetcher (Phase A-6).

The clipboard URL feature in :mod:`katrain.gui.sgf_manager` accepts a
URL from the user's clipboard and fetches it. Without guard rails this
allows:

- Fetching private/loopback IPs (SSRF)
- Following redirects into internal services
- Pulling arbitrarily large bodies into memory

These tests exercise the public guard helper :func:`_safe_fetch_url`
without touching the network by feeding it bad URLs first.
"""

from __future__ import annotations

import pytest

from katrain.gui.sgf_manager import (
    _ALLOWED_URL_SCHEMES,
    _DISALLOWED_HOST_LITERALS,
    UnsafeClipboardURLError,
    _safe_fetch_url,
)


class TestSchemeAndHostValidation:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/x.sgf",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "data:text/plain;base64,SGVsbG8=",
            "",
            "no-scheme.example.com/x.sgf",
        ],
    )
    def test_non_http_schemes_are_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeClipboardURLError):
            _safe_fetch_url(url)

    def test_missing_hostname_is_rejected(self) -> None:
        with pytest.raises(UnsafeClipboardURLError):
            _safe_fetch_url("http:///path-only")


class TestPrivateAndLoopbackIPDefense:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/x.sgf",
            "http://127.0.0.1:8080/admin",
            "http://10.0.0.5/internal",
            "http://192.168.0.1/router",
            "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
            "http://172.16.0.1/internal",
            "http://localhost/x.sgf",
            "http://[::1]/x.sgf",
            "http://[fe80::1]/x.sgf",
            "http://224.0.0.1/multicast",
        ],
    )
    def test_private_loopback_and_special_ips_are_rejected(self, url: str) -> None:
        with pytest.raises(UnsafeClipboardURLError):
            _safe_fetch_url(url)


class TestAllowAndDisallowConstants:
    def test_allowed_schemes(self) -> None:
        assert frozenset({"http", "https"}) == _ALLOWED_URL_SCHEMES

    def test_disallowed_host_literals(self) -> None:
        assert "localhost" in _DISALLOWED_HOST_LITERALS


class TestResponseSizeCap:
    def test_response_larger_than_cap_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A response that exceeds the byte cap should be refused."""
        import katrain.gui.sgf_manager as sgf_mod

        class FakeResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload
                self._released = False

            def read(self, n: int) -> bytes:
                # Pretend the remote sent ``cap + 1`` bytes.
                return self._payload[:n]

            def release_conn(self) -> None:
                self._released = True

        fake = FakeResponse(b"x" * (sgf_mod._MAX_CLIPBOARD_FETCH_BYTES + 1))

        class FakePool:
            def request(self, *_args: object, **_kwargs: object) -> FakeResponse:
                return fake

        monkeypatch.setattr(sgf_mod.urllib3, "PoolManager", lambda **_kw: FakePool())
        monkeypatch.setattr(sgf_mod.urllib3, "Retry", lambda **_kw: None)

        with pytest.raises(UnsafeClipboardURLError):
            _safe_fetch_url("http://example.com/x.sgf", max_bytes=1024)
        assert fake._released, "response connection must be released even on size-cap failure"
