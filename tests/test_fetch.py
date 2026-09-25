import platform

import httpx
import pytest
from golem.tool import schema

from golem_web import tools, web_fetch
from golem_web.fetch import _body, fetch_page, user_agent
from tests.test_extract import ARTICLE


def _transport(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": user_agent()},
    )


def _ok(body: str, content_type: str) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": content_type})


def test_tool_schema() -> None:
    got = schema(web_fetch)
    assert got == {
        "name": "web_fetch",
        "description": "Fetch a URL and return its title and main text as Markdown.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    }
    assert tools == [web_fetch]


def test_rejects_non_http_url() -> None:
    with _transport(lambda request: _ok("nope", "text/plain")) as client:
        with pytest.raises(ValueError, match="unsupported URL: file:///etc/passwd"):
            fetch_page("file:///etc/passwd", client)


def test_http_error_names_status_and_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    with _transport(handler) as client:
        with pytest.raises(ValueError, match="HTTP 404 for https://example.com/missing"):
            fetch_page("https://example.com/missing", client)


def test_rejects_non_html_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})

    with _transport(handler) as client:
        with pytest.raises(ValueError, match="unsupported content type: application/pdf"):
            fetch_page("https://example.com/file.pdf", client)


def test_plain_text_and_markdown_skip_extraction() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".md"):
            return _ok("# Note\n\nHello", "text/markdown; charset=utf-8")
        return _ok("Just the words.", "text/plain; charset=utf-8")

    with _transport(handler) as client:
        plain = fetch_page("https://example.com/note.txt", client)
        markdown = fetch_page("https://example.com/note.md", client)
    assert plain == {"url": "https://example.com/note.txt", "title": "", "content": "Just the words."}
    assert markdown == {
        "url": "https://example.com/note.md",
        "title": "",
        "content": "# Note\n\nHello",
    }


def test_html_uses_extractor_and_final_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == user_agent()
        if request.url.path == "/jump":
            return httpx.Response(302, headers={"location": "https://example.com/article"})
        return _ok(ARTICLE, "text/html; charset=utf-8")

    with _transport(handler) as client:
        page = fetch_page("https://example.com/jump", client)
    assert page["url"] == "https://example.com/article"
    assert page["title"] == "Article title"
    assert page["content"].startswith("# Article title\n\nPublished 2026-09-23\n")
    assert "Site navigation" not in page["content"]


def test_web_fetch_returns_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(lambda request: _ok("hello", "text/plain"))
    monkeypatch.setattr(
        "golem_web.fetch._client",
        lambda: httpx.Client(transport=transport),
    )
    assert web_fetch("https://example.com/hello")["content"] == "hello"


def test_user_agent_matches_host() -> None:
    assert "Macintosh" in user_agent("Darwin")
    assert "Linux" in user_agent("Linux")
    assert "Windows" in user_agent("Windows")
    assert user_agent("FreeBSD") == user_agent("Linux")
    assert user_agent() == user_agent(platform.system())


def test_body_stops_at_two_mebibytes() -> None:
    class Chunks:
        def __init__(self) -> None:
            self.reads = 0

        def iter_bytes(self) -> object:
            self.reads += 1
            yield b"a" * (2 * 1024 * 1024)
            self.reads += 1
            yield b"b" * 32

    source = Chunks()
    assert _body(source) == b"a" * (2 * 1024 * 1024)
    assert source.reads == 1
