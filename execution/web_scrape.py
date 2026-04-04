"""Scrape a webpage and return structured content."""

import argparse
import json

import requests
from bs4 import BeautifulSoup

from utils import output_json, setup_logging, timestamp

log = setup_logging("web_scrape")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def scrape(
    url: str,
    selectors: list[str] | None = None,
    output_format: str = "markdown",
    timeout: int = 30,
) -> dict:
    """Scrape a webpage using requests + BeautifulSoup."""
    log.info("Scraping: %s", url)

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "timestamp": timestamp()}

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script/style elements
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    if selectors:
        elements = []
        for sel in selectors:
            for el in soup.select(sel):
                elements.append(el.get_text(strip=True))
        content = "\n\n".join(elements)
    else:
        content = soup.get_text(separator="\n", strip=True)

    # Format output
    if output_format == "json":
        content = {"text": content}
    elif output_format == "markdown":
        # Basic cleanup: collapse multiple newlines
        lines = [line for line in content.split("\n") if line.strip()]
        content = "\n\n".join(lines)

    return {
        "success": True,
        "url": url,
        "title": soup.title.string if soup.title else None,
        "content": content,
        "format": output_format,
        "timestamp": timestamp(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape a webpage")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--selectors", nargs="+", default=None)
    parser.add_argument("--format", dest="output_format", default="markdown",
                        choices=["json", "text", "markdown"])
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    result = scrape(args.url, args.selectors, args.output_format, args.timeout)
    output_json(result)
