---
name: optcg-deck-scraper
description: Use when the user wants to scrape, fetch, or analyze OPTCG deck profiles from Japanese tournaments. Triggers on mentions of "deck profiles", "OPTCG decks", "Japan format", "OP-15 decks", or "tournament decks".
---

# OPTCG Deck Profile Scraper

Scrape all deck profiles from onepiecetopdecks.com for a given OPTCG format and return structured data.

## What This Skill Does

Runs the execution script at `execution/optcg_deck_scraper.py` using Playwright to scrape deck profiles. Each profile includes:
- **Deck Name** (e.g. "Purple Enel", "Green Mihawk")
- **Date** (tournament date)
- **Tournament** (type and record, e.g. "FS(5-0)", "TC(6-0)")
- **Host** (venue/shop)
- **Player** name
- **Placement** (e.g. "1st Place")
- **Decklist** in text (e.g. "4x OP15-061")

## Instructions

1. Read the directive at `directives/optcg_deck_scraper.md` for full context.
2. Parse `$ARGUMENTS` for optional inputs:
   - A format slug (e.g. `japan-op-14-deck-list-the-azure-sea-seven`) — defaults to `japan-op-15-deck-list-adventure-on-kamis-island`
   - An output file path (e.g. `--output decks.json`) — defaults to stdout
3. Run the scraper:
   ```bash
   python execution/optcg_deck_scraper.py [--format-slug SLUG] [--output FILE]
   ```
4. Present results to the user in a readable summary:
   - Total decks found
   - Breakdown by deck archetype (count per deck name)
   - If the user asked for a specific deck or analysis, filter/highlight accordingly
5. If `--output` was specified, confirm the file was written.

## Known Format Slugs (Japan)

- **OP-15**: `japan-op-15-deck-list-adventure-on-kamis-island` (default)
- **OP-14**: `japan-op-14-deck-list-the-azure-sea-seven`

## Tournament Type Abbreviations

- **FS** — Flagship
- **TC** — Treasure Cup
- **SB** — Standard Battle
- **GAO** — Grand Area Open
