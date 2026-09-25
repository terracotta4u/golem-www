from trafilatura import bare_extraction

CONTENT_LIMIT = 80_000
EMPTY_PAGE = "No article text found."
_TRUNCATED = "\n\n[content truncated]"


def extract_page(html: str, url: str) -> dict[str, str]:
    """Extract a page's title and main text from HTML.

    ``url`` is returned unchanged. ``content`` is Markdown: a heading, a
    ``Published ...`` line when a date was found, then the article. Pages
    with no extractable text still return a page whose content says so.
    """
    document = bare_extraction(
        html,
        url=url,
        include_formatting=True,
        include_links=True,
        include_comments=False,
        with_metadata=True,
    )
    if document is None or not (document.text or "").strip():
        return {"url": url, "title": "", "content": EMPTY_PAGE}
    title = (document.title or "").strip()
    content = _content(title, (document.date or "").strip(), document.text.strip())
    return {"url": url, "title": title, "content": _limit(content)}


def _content(title: str, date: str, body: str) -> str:
    heading = f"# {title}" if title else ""
    if heading and not body.startswith(heading):
        body = f"{heading}\n\n{body}"
    if not date:
        return body
    published = f"Published {date}"
    if body.startswith("# "):
        first, _, rest = body.partition("\n")
        rest = rest.lstrip("\n")
        if rest:
            return f"{first}\n\n{published}\n\n{rest}"
        return f"{first}\n\n{published}"
    return f"{published}\n\n{body}"


def _limit(content: str) -> str:
    if len(content) <= CONTENT_LIMIT:
        return content
    keep = CONTENT_LIMIT - len(_TRUNCATED)
    return content[:keep].rstrip() + _TRUNCATED
