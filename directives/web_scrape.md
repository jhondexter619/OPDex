# Directive: Web Scrape

## Goal
Scrape content from a webpage and return structured data.

## Inputs
- `url` (required): The URL to scrape
- `selectors` (optional): CSS selectors to extract specific elements
- `wait_for` (optional): Selector to wait for before scraping (for JS-rendered pages)
- `output_format` (optional): `json`, `text`, or `markdown`, default `markdown`

## Execution
1. Script: `execution/web_scrape.py`
2. Uses `requests` + `BeautifulSoup` for static pages
3. Falls back to `playwright` if `wait_for` is specified (JS rendering needed)

## Outputs
- Extracted content in the specified format
- Metadata: title, URL, timestamp

## Edge Cases & Errors
- 403/Blocked: try with different User-Agent header
- JS-rendered content missing: switch to playwright mode
- Timeout: default 30s, increase for slow sites
- Respect robots.txt — check before scraping

## Learnings
