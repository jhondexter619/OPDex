# Directive: OPTCG Leader Logo Downloader

## Goal
Download crew/faction logos (Jolly Rogers, faction symbols) for every OPTCG leader character. These are used as website assets for archetype cards, navigation, and character identification on OPDex.

## Inputs
- `--output-dir` (optional): Where to save images. Default: `leader_artwork`
- `--leaders-json` (optional): Path to pre-scraped leader list JSON. Skips Bandai scrape if provided.
- `--timeout` (optional): Timeout for Bandai card list scrape. Default: 120s
- `--delay` (optional): Delay between wiki requests. Default: 1.5s (be polite to the wiki)

## Execution
1. Script: `execution/optcg_leader_art.py`
2. **Step 1** — Scrapes the official Bandai card list for all Leader-type cards using Playwright
   - Checks the `#category_Leader` checkbox via JS click (hidden input)
   - Sets series dropdown to "ALL" (index 1)
   - Handles pagination
3. **Step 2** — For each unique leader, queries the Fandom MediaWiki API (`api.php?action=query&prop=pageimages`)
4. **Step 3** — Downloads full-resolution images from `static.wikia.nocookie.net` CDN
5. **Step 4** — Saves manifest.json with all metadata

## Outputs
- One .webp image per leader character, named by character (e.g., `Monkey_D__Luffy.webp`)
- `leaders.json` — Full leader roster with card codes, names, colors (74 leaders as of OP15)
- `manifest.json` — Summary with success/fail counts, file paths, source URLs
- Total size: ~18MB for all 74 leaders

## Edge Cases & Errors
- **Wiki name mismatch**: Script has `WIKI_NAME_OVERRIDES` dict for characters whose card names differ from wiki page names (e.g., "Trafalgar Law" → "Trafalgar D. Water Law"). Add new overrides as needed.
- **403/blocked**: The API endpoint is not behind Cloudflare, but increase `--delay` if rate-limited
- **Missing artwork**: Some minor characters may not have infobox images; check `manifest.json` `failed_characters` list. Script falls back to `opensearch` API if direct title lookup fails.
- **Bandai site down**: Use `--leaders-json` to skip the Bandai scrape step with a pre-saved leader list
- **Image too small**: Images under 5KB are skipped as likely placeholders
- **Dual characters** (e.g., "Ace & Newgate", "Roronoa Zoro & Sanji"): Mapped to first character's art via overrides

## Learnings
- The Bandai card list requires Playwright (JS-rendered) — category filter is a hidden checkbox, must use `element.click()` via JS, not Playwright's `.check()` method
- The Fandom wiki pages are behind Cloudflare (even headless+stealth fails). **Use the MediaWiki API** (`api.php?action=query&prop=pageimages`) instead — it bypasses Cloudflare entirely and returns image CDN URLs
- Wiki CDN (`static.wikia.nocookie.net`) auto-converts PNG to WebP. Actual content-type should be checked to set correct file extension
- Strip `/scale-to-width-down/XXX` from CDN URLs to get full resolution images
- The `opensearch` API is a good fallback for fuzzy name matching when exact titles don't match
