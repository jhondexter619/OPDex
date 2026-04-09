"""Scrape OPTCG deck profiles from onepiecetopdecks.com for a given format."""

import argparse
import json
import re
from urllib.parse import parse_qs

import requests
from bs4 import BeautifulSoup

from utils import output_json, setup_logging, timestamp

log = setup_logging("optcg_deck_scraper")

BASE_URL = "https://onepiecetopdecks.com/deck-list/"


def _decode_decklist(dg: str) -> list[dict]:
    """Decode the dg query param into a list of {quantity, card_code} dicts.

    Format: ``1nOP14-020a4nOP12-034a...``
    """
    matches = re.findall(r"(\d+)n([A-Za-z]+\d+-\d+)", dg)
    return [{"quantity": int(qty), "card_code": code.upper()} for qty, code in matches]


def _parse_deck_link(href: str) -> dict | None:
    """Extract deck profile metadata from a deckgen query-string link."""
    if "deckgen" not in href:
        return None

    # Extract query string — handle both absolute and relative URLs
    if "?" in href:
        qs_str = href.split("?", 1)[1]
    else:
        return None

    qs = parse_qs(qs_str)

    dg = qs.get("dg", [None])[0]
    if not dg:
        return None

    deck_name = qs.get("dn", ["Unknown"])[0]
    date = qs.get("date", [""])[0]
    author = qs.get("au", [""])[0]
    tournament = qs.get("tn", [""])[0]
    host = qs.get("hs", [""])[0]
    placement = qs.get("pl", [""])[0]
    country = qs.get("cn", [""])[0]

    cards = _decode_decklist(dg)
    if not cards:
        return None

    decklist_text = "\n".join(f"{c['quantity']}x {c['card_code']}" for c in cards)
    total_cards = sum(c["quantity"] for c in cards)

    return {
        "deck_name": deck_name,
        "date": date,
        "tournament": tournament,
        "host": host,
        "placement": placement,
        "player": author,
        "country": country,
        "total_cards": total_cards,
        "unique_cards": len(cards),
        "decklist": decklist_text,
        "cards": cards,
    }


def scrape_deck_profiles(
    format_slug: str = "japan-op-15-deck-list-adventure-on-kamis-island",
    timeout: int = 60,
) -> dict:
    """Scrape all deck profiles from a given format page using Playwright.

    Args:
        format_slug: The URL slug for the format page (after /deck-list/).
        timeout: Page load timeout in seconds.
    """
    url = f"{BASE_URL}{format_slug}/"
    log.info("Scraping deck profiles from: %s", url)

    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; OPDex/1.0)",
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        hrefs = [
            a["href"] for a in soup.find_all("a", href=True)
            if "deckgen" in a["href"]
        ]
    except Exception as e:
        log.exception("Scrape failed")
        return {"success": False, "error": str(e), "timestamp": timestamp()}

    # Parse each link
    decks = []
    seen = set()

    for href in hrefs:
        qs_part = href.split("?", 1)[-1] if "?" in href else ""
        if not qs_part or qs_part in seen:
            continue
        seen.add(qs_part)

        deck = _parse_deck_link(href)
        if deck:
            decks.append(deck)

    log.info("Found %d deck profiles", len(decks))

    return {
        "success": True,
        "source_url": url,
        "format": format_slug,
        "total_decks": len(decks),
        "decks": decks,
        "timestamp": timestamp(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape OPTCG deck profiles")
    parser.add_argument(
        "--format-slug",
        default="japan-op-15-deck-list-adventure-on-kamis-island",
        help="URL slug for the format page (after /deck-list/)",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--output", default=None,
        help="Optional output file path (JSON). Prints to stdout if omitted.",
    )
    args = parser.parse_args()

    result = scrape_deck_profiles(args.format_slug, args.timeout)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        log.info("Results written to %s", args.output)
    else:
        output_json(result)
