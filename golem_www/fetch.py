import platform
from urllib.parse import urlsplit

import httpx

from golem_www.extract import extract_page

CONTENT_LIMIT = 80_000
MAX_BYTES = 2 * 1024 * 1024
_TOO_LARGE = "response is larger than 2 MiB and was not read"
_CHROME = "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_USER_AGENTS = {
    "Darwin": f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) {_CHROME}",
    "Linux": f"Mozilla/5.0 (X11; Linux x86_64) {_CHROME}",
    "Windows": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {_CHROME}",
}
_HTML = "text/html"
_TEXT = {"text/plain", "text/markdown"}


def web_fetch(url: str, offset: int = 0) -> dict[str, str | int | bool]:
    """Fetch a URL and return its title and main text as Markdown. Pass offset to continue when truncated."""
    _check_url(url)
    if offset < 0:
        raise ValueError("offset must be zero or greater")
    try:
        with _client() as client, client.stream("GET", url) as response:
            page_url = str(response.url)
            if not response.is_success:
                raise ValueError(f"HTTP {response.status_code} for {page_url}")
            header = response.headers.get("content-type", "")
            text = _decode(_body(response), header)
            media = _media_type(header)
    except httpx.HTTPError as exc:
        raise ValueError(f"fetch failed for {url}: {exc}") from exc
    if media == _HTML:
        page = extract_page(text, page_url)
    elif media in _TEXT:
        page = {"url": page_url, "title": "", "content": text.strip()}
    else:
        raise ValueError(f"unsupported content type: {media}")
    return _window(page, offset)


def _client() -> httpx.Client:
    return httpx.Client(
        transport=_transport(),
        follow_redirects=True,
        max_redirects=5,
        timeout=20.0,
        headers={"User-Agent": user_agent()},
    )


def _transport() -> httpx.BaseTransport | None:
    return None


def user_agent(system: str | None = None) -> str:
    """Browser User-Agent for this host. Unknown systems use the Linux string."""
    name = platform.system() if system is None else system
    return _USER_AGENTS.get(name, _USER_AGENTS["Linux"])


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"unsupported URL: {url}")


def _window(page: dict[str, str], offset: int) -> dict[str, str | int | bool]:
    content = page["content"]
    if offset > 0 and offset >= len(content):
        raise ValueError(f"offset {offset} is past the end of the page")
    chunk = content[offset : offset + CONTENT_LIMIT]
    next_offset = offset + len(chunk)
    truncated = next_offset < len(content)
    if truncated:
        chunk += f"\n\nThe rest of the page was omitted. Pass offset {next_offset} to continue."
    result: dict[str, str | int | bool] = {
        "url": page["url"],
        "title": page["title"],
        "content": chunk,
        "offset": offset,
        "truncated": truncated,
    }
    if truncated:
        result["next_offset"] = next_offset
    return result


def _body(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    total = 0
    stream = response.iter_bytes()
    while True:
        try:
            chunk = next(stream)
        except StopIteration:
            break
        total += len(chunk)
        if total > MAX_BYTES:
            raise ValueError(_TOO_LARGE)
        chunks.append(chunk)
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
