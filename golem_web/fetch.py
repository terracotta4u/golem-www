import platform
from urllib.parse import urlsplit

import httpx

from golem_web.extract import _limit, extract_page

MAX_BYTES = 2 * 1024 * 1024
_CHROME = "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_USER_AGENTS = {
    "Darwin": f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {_CHROME}",
    "Linux": f"Mozilla/5.0 (X11; Linux x86_64) {_CHROME}",
    "Windows": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {_CHROME}",
}
_HTML = "text/html"
_TEXT = {"text/plain", "text/markdown"}


def web_fetch(url: str) -> dict[str, str]:
    """Fetch a URL and return its title and main text as Markdown."""
    with _client() as client:
        return fetch_page(url, client)


def fetch_page(url: str, client: httpx.Client) -> dict[str, str]:
    """GET ``url`` and return ``url``, ``title``, and ``content``.

    ``url`` in the result is the final URL after redirects. HTML is extracted.
    Plain text and Markdown are returned as content with an empty title.
    """
    _check_url(url)
    try:
        with client.stream("GET", url) as response:
            page_url = str(response.url)
            if not response.is_success:
                raise ValueError(f"HTTP {response.status_code} for {page_url}")
            header = response.headers.get("content-type", "")
            text = _decode(_body(response), header)
            media = _media_type(header)
    except httpx.HTTPError as exc:
        raise ValueError(f"fetch failed for {url}: {exc}") from exc
    if media == _HTML:
        return extract_page(text, page_url)
    if media in _TEXT:
        return {"url": page_url, "title": "", "content": _limit(text.strip())}
    raise ValueError(f"unsupported content type: {media}")


def _client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        max_redirects=5,
        timeout=20.0,
        headers={"User-Agent": user_agent()},
    )


def user_agent(system: str | None = None) -> str:
    """Browser User-Agent for this host. Unknown systems use the Linux string."""
    name = platform.system() if system is None else system
    return _USER_AGENTS.get(name, _USER_AGENTS["Linux"])


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"unsupported URL: {url}")


def _body(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    stream = response.iter_bytes()
    while total < MAX_BYTES:
        try:
            chunk = next(stream)
        except StopIteration:
            break
        room = MAX_BYTES - total
        if len(chunk) > room:
            chunk = chunk[:room]
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def _media_type(header: str) -> str:
    media = header.split(";", 1)[0].strip().lower()
    return media or "unknown"


def _decode(raw: bytes, header: str) -> str:
    encoding = "utf-8"
    for part in header.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value.strip():
            encoding = value.strip().strip('"')
            break
    try:
        return raw.decode(encoding, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")
