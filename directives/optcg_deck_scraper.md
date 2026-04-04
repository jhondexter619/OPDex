# Directive: OPTCG Deck Profile Scraper

## Goal
Scrape all deck profiles from onepiecetopdecks.com for a given format (e.g. Japan OP-15) and extract structured data: deck name, date, tournament, host, player, placement, and full decklist in text.

## Inputs
- `format_slug` (optional): URL slug for the format page. Default: `japan-op-15-deck-list-adventure-on-kamis-island`
- `output` (optional): File path to write JSON results. If omitted, prints to stdout.

## Known Format Slugs (Japan)
- OP-15: `japan-op-15-deck-list-adventure-on-kamis-island`
- OP-14: `japan-op-14-deck-list-the-azure-sea-seven/`
- Earlier sets follow the same pattern on `onepiecetopdecks.com/deck-list/`

## Execution
1. Script: `execution/optcg_deck_scraper.py`
2. Run: `python execution/optcg_deck_scraper.py [--format-slug SLUG] [--output FILE]`
3. Sequence:
   a. Fetches the format page from onepiecetopdecks.com
   b. Finds all `<a>` tags with `deckgen` in the href
   c. Parses query params: `dn` (deck name), `date`, `au` (player), `tn` (tournament), `hs` (host), `pl` (placement), `dg` (card list)
   d. Decodes the `dg` param (format: `{qty}n{code}a...`) into a readable decklist

## Outputs
Each deck profile contains:
- `deck_name` — e.g. "Purple Enel", "Green Mihawk"
- `date` — tournament date (e.g. "3/29/2026")
- `tournament` — tournament type and record (e.g. "FS(5-0)", "TC(6-0)")
- `host` — venue/shop name (e.g. "Cardlab", "Bookoff(22)")
- `player` — player name
- `placement` — e.g. "1st Place"
- `decklist` — human-readable text, one card per line (e.g. "4x OP15-061")
- `cards` — structured list of `{quantity, card_code}` objects

## Tournament Type Abbreviations
- **FS** — Flagship
- **TC** — Treasure Cup
- **SB** — Standard Battle
- **GAO** — Grand Area Open
- Number in parentheses = win-loss record or player count

## Edge Cases & Errors
- **Page structure changes**: if onepiecetopdecks.com changes their HTML, the `deckgen` href pattern may break — inspect the page and adjust selectors
- **Rate limiting**: add delay between requests if scraping multiple format pages
- **Duplicate decks**: script deduplicates by full query string
- **Pagination/infinite scroll**: page may load more decks on scroll — the script currently captures what loads on initial page render (~100 decks). If more are needed, add scroll-to-bottom logic

## Learnings
- Site has Cloudflare protection — `requests` and `cloudscraper` both get 403/SSL errors. Must use Playwright (headless browser) to fetch the page
- Deck data is not in the page body text — it's entirely encoded in `<a href="deckgen?...">` query parameters
- ~100 deck profiles load on initial page render for OP-15
