# golem-www

Suite of web tools for [Golem](https://github.com/terracotta4u/golem). 

## Install

```bash
golem extension add https://github.com/terracotta4u/golem-web
```

## Usage

Ask Golem to read a page. It should call `web_fetch` with the URL and gets:

```json
{
  "url": "https://example.com/article",
  "title": "Article title",
  "content": "# Article title\n\nPublished 2026-09-23\n\nActual article text..."
}
```

`content` is the article in Markdown. Navigation, scripts, and styles are left out.

## Tools

| Tool | Description | Arguments | Returns |
| --- | --- | --- | --- |
| `web_fetch` | Fetch a URL and return its title and main text as Markdown. | `url` (string, required) | `url`, `title`, `content` |

