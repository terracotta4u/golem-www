from golem_www.extract import extract_page

ARTICLE = """<!DOCTYPE html>
<html>
<head>
<title>Article title</title>
<meta property="article:published_time" content="2026-09-23">
</head>
<body>
<nav>Site navigation Home About</nav>
<script>var trackingPixel = 1;</script>
<style>.banner{color:red}</style>
<article>
<h1>Article title</h1>
<p>Actual article text lives here and is long enough to be kept by the extractor rather than discarded as boilerplate or a menu item.</p>
<h2>Section</h2>
<p>More of the article continues in this section with enough words to look like real prose instead of a menu.</p>
<p>A <a href="https://example.com/more">related link</a> belongs in the text.</p>
</article>
</body>
</html>
"""


def test_extracts_article_markdown() -> None:
    page = extract_page(ARTICLE, "https://example.com/article")
    assert page["url"] == "https://example.com/article"
    assert page["title"] == "Article title"
    assert page["content"].startswith("# Article title\n\nPublished 2026-09-23\n")
    assert "Actual article text" in page["content"]
    assert "## Section" in page["content"]
    assert "[related link](https://example.com/more)" in page["content"]
    assert "Site navigation" not in page["content"]
    assert "trackingPixel" not in page["content"]
    assert "color:red" not in page["content"]


def test_empty_page_notes_missing_text() -> None:
    html = "<html><head><title>Nothing</title></head><body><script>var x = 1;</script></body></html>"
    page = extract_page(html, "https://example.com/empty")
    assert page == {
        "url": "https://example.com/empty",
        "title": "",
        "content": "No article text found.",
    }


def test_keeps_the_full_article() -> None:
    sentence = "This sentence is unique enough to survive extraction. "
    body = "STARTMARKER " + sentence * 2000 + " ENDMARKER stays in the article."
    html = f"<html><head><title>Long</title></head><body><article><p>{body}</p></article></body></html>"
    page = extract_page(html, "https://example.com/long")
    assert page["title"] == "Long"
    assert "STARTMARKER" in page["content"]
    assert "ENDMARKER stays in the article." in page["content"]
