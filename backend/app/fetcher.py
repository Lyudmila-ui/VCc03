import re

import httpx
from bs4 import BeautifulSoup

from app.safety import UnsafeUrl, assert_public_url

MAX_BYTES = 1_000_000
MAX_TEXT = 14_000
MAX_REDIRECTS = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8",
    "Accept-Language": "ru,en;q=0.8",
}


class FetchError(RuntimeError):
    pass


async def fetch_page_text(url: str) -> str:
    current = assert_public_url(url)
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                response = await client.get(current, headers=HEADERS)
            except httpx.TimeoutException as exc:
                raise FetchError("Страница не ответила вовремя.") from exc
            except httpx.HTTPError as exc:
                raise FetchError("Не удалось открыть страницу.") from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("Страница перенаправила запрос без нового адреса.")
                current = assert_redirect(current, location)
                continue

            if response.status_code >= 400:
                raise FetchError(f"Страница ответила кодом {response.status_code}.")

            content_type = response.headers.get("content-type", "")
            if content_type and not _looks_like_text(content_type):
                raise FetchError(f"По ссылке не HTML, а {content_type.split(';')[0]}.")

            raw = response.content[:MAX_BYTES]
            html = decode_html(raw, response.charset_encoding)
            text = html_to_page_text(html, current)
            if len(text) < 80:
                raise FetchError(
                    "На странице почти нет текста. Возможно, она собирается только в браузере."
                )
            return text

    raise FetchError("Слишком много переадресаций.")


def assert_redirect(current: str, location: str) -> str:
    from urllib.parse import urljoin

    try:
        return assert_public_url(urljoin(current, location))
    except UnsafeUrl as exc:
        raise FetchError(str(exc)) from exc


def html_to_page_text(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        tag.decompose()

    title = " ".join(soup.title.get_text(" ", strip=True).split()) if soup.title else ""
    description = _meta(soup, "description")
    keywords = _meta(soup, "keywords")
    robots = _meta(soup, "robots")
    canonical = ""
    link = soup.find("link", rel=_is_canonical)
    if link and link.get("href"):
        canonical = str(link["href"]).strip()

    headings: list[str] = []
    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = " ".join(heading.get_text(" ", strip=True).split())
        if text:
            headings.append(f"{heading.name.upper()}: {text}")

    lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
    body = "\n".join(lines)

    parts = [
        f"URL: {url}",
        f"Title: {title}",
        f"Description: {description}",
        f"Keywords: {keywords}",
        f"Robots: {robots}",
        f"Canonical: {canonical}",
        "Заголовки:",
        "\n".join(headings[:40]) or "нет",
        "Текст:",
        body,
    ]
    full = "\n".join(parts).strip()
    if len(full) > MAX_TEXT:
        return full[:MAX_TEXT] + "\n[текст обрезан]"
    return full


def _meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
    if not tag:
        return ""
    return " ".join(str(tag.get("content") or "").split())


def _is_canonical(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.lower() == "canonical"
    return any(str(part).lower() == "canonical" for part in value)


def decode_html(raw: bytes, declared: str | None) -> str:
    if declared:
        try:
            return raw.decode(declared, errors="replace")
        except LookupError:
            pass
    head = raw[:4000].decode("ascii", errors="ignore")
    match = re.search(r"charset=['\"]?\s*([A-Za-z0-9._-]+)", head, flags=re.IGNORECASE)
    if match:
        try:
            return raw.decode(match.group(1), errors="replace")
        except LookupError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace")


def _looks_like_text(content_type: str) -> bool:
    lowered = content_type.lower()
    return any(token in lowered for token in ("html", "xml", "text", "json"))
