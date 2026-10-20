import socket

import pytest

from app.safety import UnsafeUrl, assert_public_url


def test_rejects_empty():
    with pytest.raises(UnsafeUrl):
        assert_public_url("  ")


def test_rejects_non_http():
    with pytest.raises(UnsafeUrl):
        assert_public_url("file:///etc/passwd")


def test_rejects_localhost():
    with pytest.raises(UnsafeUrl):
        assert_public_url("http://localhost/secret")


def test_rejects_loopback_ip():
    with pytest.raises(UnsafeUrl):
        assert_public_url("http://127.0.0.1/")


def test_rejects_private_ip():
    with pytest.raises(UnsafeUrl):
        assert_public_url("http://192.168.1.10/admin")


def test_rejects_link_local():
    with pytest.raises(UnsafeUrl):
        assert_public_url("http://169.254.169.254/latest/meta-data")


def test_rejects_credentials():
    with pytest.raises(UnsafeUrl):
        assert_public_url("https://user:pass@example.com")


def test_rejects_name_that_resolves_private(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 0))],
    )
    with pytest.raises(UnsafeUrl):
        assert_public_url("https://internal.example")


def test_accepts_public_name(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    assert assert_public_url("https://example.com/page") == "https://example.com/page"
