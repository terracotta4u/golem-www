import platform

import httpx
import pytest
from golem.tool import schema

from golem_www import tools, web_fetch
from golem_www.fetch import CONTENT_LIMIT, _TOO_LARGE, user_agent
from tests.test_extract import ARTICLE


def _mock(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr("golem_www.fetch._transport", lambda: httpx.MockTransport(handler))


def _ok(body: str, content_type: str) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": content_type})


def test_tool_schema() -> None:
    got = schema(web_fetch)
    assert got == {
        "name": "web_fetch",
        "description": (
            "Fetch a URL and return its title and main text as Markdown. "
            "Pass offset to continue when truncated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "offset": {"type": "integer"},
            },
            "required": ["url"],
        },
    }
    assert tools == [web_fetch]


def test_rejects_non_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock(monkeypatch, lambda request: _ok("nope", "text/plain"))
    with pytest.raises(ValueError, match="unsupported URL: file:///etc/passwd"):
        web_fetch("file:///etc/passwd")


def test_http_error_names_status_and_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    _mock(monkeypatch, handler)
    with pytest.raises(ValueError, match="HTTP 404 for https://example.com/missing"):
        web_fetch("https://example.com/missing")


def test_rejects_non_html_type(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})

    _mock(monkeypatch, handler)
    with pytest.raises(ValueError, match="unsupported content type: application/pdf"):
        web_fetch("https://example.com/file.pdf")


def test_plain_text_and_markdown_skip_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".md"):
            return _ok("# Note\n\nHello", "text/markdown; charset=utf-8")
        return _ok("Just the words.", "text/plain; charset=utf-8")

    _mock(monkeypatch, handler)
    plain = web_fetch("https://example.com/note.txt")
    markdown = web_fetch("https://example.com/note.md")
    assert plain == {
        "url": "https://example.com/note.txt",
        "title": "",
        "content": "Just the words.",
        "offset": 0,
        "truncated": False,
    }
    assert markdown == {
        "url": "https://example.com/note.md",
        "title": "",
        "content": "# Note\n\nHello",
        "offset": 0,
        "truncated": False,
    }


def test_html_uses_extractor_and_final_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == user_agent()
        if request.url.path == "/jump":
            return httpx.Response(302, headers={"location": "https://example.com/article"})
        return _ok(ARTICLE, "text/html; charset=utf-8")

    _mock(monkeypatch, handler)
    page = web_fetch("https://example.com/jump")
    assert page["url"] == "https://example.com/article"
    assert page["title"] == "Article title"
    assert page["content"].startswith("# Article title\n\nPublished 2026-09-23\n")
    assert page["offset"] == 0
    assert page["truncated"] is False
    assert "next_offset" not in page
    assert "Site navigation" not in page["content"]


def test_user_agent_matches_host() -> None:
    assert "Macintosh" in user_agent("Darwin")
    assert "Linux" in user_agent("Linux")
    assert "Windows" in user_agent("Windows")
    assert user_agent("FreeBSD") == user_agent("Linux")
    assert user_agent() == user_agent(platform.system())


def test_offset_continues_after_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    body = "a" * CONTENT_LIMIT + "ENDMARKER"

    def handler(request: httpx.Request) -> httpx.Response:
        return _ok(body, "text/plain")

    _mock(monkeypatch, handler)
    first = web_fetch("https://example.com/long")
    assert first["truncated"] is True
    assert first["offset"] == 0
    assert first["next_offset"] == CONTENT_LIMIT
    assert first["title"] == ""
    assert first["content"] == (
        "a" * CONTENT_LIMIT
        + f"\n\nThe rest of the page was omitted. Pass offset {CONTENT_LIMIT} to continue."
    )
    second = web_fetch("https://example.com/long", offset=int(first["next_offset"]))
    assert second["truncated"] is False
    assert second["offset"] == CONTENT_LIMIT
    assert second["content"] == "ENDMARKER"
    assert second["title"] == ""
    assert "next_offset" not in second


def test_offset_past_the_end(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock(monkeypatch, lambda request: _ok("hello", "text/plain"))
    with pytest.raises(ValueError, match="offset 10 is past the end of the page"):
        web_fetch("https://example.com/hello", offset=10)
    with pytest.raises(ValueError, match="offset must be zero or greater"):
        web_fetch("https://example.com/hello", offset=-1)


def test_rejects_response_over_two_mebibytes(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"a" * (2 * 1024 * 1024 + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload, headers={"content-type": "text/plain"})

    _mock(monkeypatch, handler)
    with pytest.raises(ValueError, match=_TOO_LARGE):
        web_fetch("https://example.com/big")
