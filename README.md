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
  "content": "# Article title\n\nPublished 2026-09-23\n\nActual article text...",
  "offset": 0,
  "truncated": false
}
```

`content` is the article in Markdown. Navigation, scripts, and styles are left out. When `truncated` is true, the result includes `next_offset`. Call `web_fetch` again with `offset` set to that value to read the rest.

## Tools

| Tool | Description | Arguments | Returns |
| --- | --- | --- | --- |
| `web_fetch` | Fetch a URL and return its title and main text as Markdown. Pass offset to continue when truncated. | `url` (string, required), `offset` (integer, optional) | `url`, `title`, `content`, `offset`, `truncated`, `next_offset` |

