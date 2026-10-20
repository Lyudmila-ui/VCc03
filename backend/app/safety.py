import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrl(ValueError):
    pass


def assert_public_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise UnsafeUrl("Вставьте ссылку на страницу.")
    if len(cleaned) > 2000:
        raise UnsafeUrl("Ссылка слишком длинная.")
    if "\\" in cleaned:
        raise UnsafeUrl("Нужна ссылка, которая начинается с http:// или https://.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrl("Нужна ссылка, которая начинается с http:// или https://.")
    if parsed.username or parsed.password:
        raise UnsafeUrl("Уберите логин и пароль из ссылки.")

    host = parsed.hostname
    if not host:
        raise UnsafeUrl("В ссылке нет домена.")

    host_lower = host.lower().rstrip(".")
    if host_lower in {"localhost", "localhost.localdomain"} or host_lower.endswith(".localhost"):
        raise UnsafeUrl("Локальные адреса не подходят.")

    try:
        literal = ipaddress.ip_address(host_lower)
    except ValueError:
        literal = None

    if literal is not None:
        _reject_ip(literal)
        return cleaned

    try:
        infos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeUrl("Домен не открывается. Проверьте ссылку.") from exc

    if not infos:
        raise UnsafeUrl("Домен не открывается. Проверьте ссылку.")

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        _reject_ip(ip)
    return cleaned


def _reject_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise UnsafeUrl("Ссылка ведёт на внутренний адрес. Нужна публичная страница.")
