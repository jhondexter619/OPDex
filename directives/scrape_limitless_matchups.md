# Directive: OPTCG Matchup Scraper (Limitless TCG)

## Goal
Scrape real head-to-head deck matchup win-rates from `play.limitlesstcg.com` for the **current OPTCG format** and produce a JSON file consumable by the OPDex website. Replaces the placement-score *proxy* matchup logic with true tournament-derived win rates plus sample sizes.

## Why Limitless
- Only public source with real H2H win % + game counts (e.g. Bonney vs Lucci = 39.58% over 1180 games).
- Plain HTML, no auth, no API key, no SPA hydration — scrapes cleanly with `requests + BeautifulSoup`.
- Updates continuously as tournaments report.
- Index page auto-resolves to the **current** format → future-proof against new sets (OP16+) without code changes.

## Inputs
- `--limit N` *(optional)* — only scrape the first N leaders (smoke test). Default: all.
- `--rate-delay SECONDS` *(optional)* — politeness delay between leader fetches. Default: `1.0`.
- `--timeout SECONDS` *(optional)* — per-request HTTP timeout. Default: `30`.
- `--output PATH` *(optional)* — write JSON to file. Otherwise prints to stdout.

## Future-proofing strategy
**Never hardcode the set name.** The script:
1. Hits `https://play.limitlesstcg.com/decks?game=OP` with **no `set=` param** — Limitless serves the current format by default.
2. Reads each row's `<a href>` which already contains `?set=OPxx` baked in by Limitless, then **follows that href verbatim**.
3. Records whatever `set=` value Limitless served, so the UI can show "Based on OPxx tournament data" automatically.

When OP16 (or any future set) drops, Limitless updates their index → next scrape picks it up → JSON rotates → UI updates. Zero code changes.

## Execution
1. Script: `execution/scrape_limitless_matchups.py`
2. Run: `python execution/scrape_limitless_matchups.py [--limit N] [--output FILE]`
3. Sequence:
   a. `GET https://play.limitlesstcg.com/decks?game=OP` → parse the deck index table
   b. Extract `(leader_code, leader_name, matchup_path)` for each row, dedupe by leader code
   c. For each leader: `GET {matchup_path}` → parse the matchup HTML table
   d. Sleep `rate_delay` between requests (default 1s, polite to Limitless)
   e. Record `current_set` from the first observed `set=` query param
4. Polite headers: `User-Agent: Mozilla/5.0 (compatible; OPDex/1.0)`

## Output schema
```json
{
  "success": true,
  "source_url": "https://play.limitlesstcg.com/decks?game=OP",
  "format": "OP14",
  "total_leaders": 24,
  "leaders": {
    "OP07-019": "Jewelry Bonney",
    "OP13-002": "Portgas.D.Ace"
  },
  "matchups": {
    "OP07-019": {
      "OP07-001": {"win_pct": 39.58, "matches": 1180, "wins": 467, "losses": 713, "ties": 0, "opponent_name": "Rob Lucci"},
      "OP05-040": {"win_pct": 55.94, "matches": 783,  "wins": 438, "losses": 345, "ties": 0, "opponent_name": "Enel"}
    }
  },
  "timestamp": "2026-04-10T..."
}
```

- Top-level key: **player's leader code**
- Nested key: **opponent's leader code**
- Both join with the local `archetype.leader_code` field in `website/app.py`

## Edge cases & errors
- **Missing opponent code**: rows where the opponent link doesn't expose a `OPxx-yyy` slug are dropped (can't be joined to local archetypes).
- **Small sample sizes**: the scraper records all rows; **filtering by sample size happens at the website layer** (default cutoff: 30 matches). Keeps the JSON flexible.
- **Network/parse errors per leader**: logged and skipped; the run continues. A single bad leader never aborts the whole scrape.
- **Rate limiting**: 1s delay between fetches by default. If Limitless ever returns 429, increase `--rate-delay`.
- **Set name drift** (e.g. `OP14.5`, `OP15-bans`): we never parse it — just record and pass through.
- **Schema changes on Limitless**: matchup table is detected by header keywords (`matches`, `win`), not by CSS class — somewhat resilient. If Limitless redesigns the page, both `parse_index` and `parse_matchups` need to be re-inspected.

## Website integration
- Stored under `website/data/matchups_{timestamp}.json`
- `website/app.py::compute_matchups()` reads the latest matchups file and joins on `leader_code`
- **Fallback**: when no H2H data exists for an archetype (or sample size < cutoff), falls back to the existing placement-score proxy and tags the UI item as "limited data"

## Refresh cadence
Mirrors the existing deck scraper:
- Runs on Render startup if `matchups_*.json` is older than `OPDEX_SCRAPE_INTERVAL` (default 6h)
- Then re-runs on the same interval inside the background scraper thread

## Learnings
- Limitless has **two subdomains**: `onepiece.limitlesstcg.com/decks` (uses opaque numeric IDs `/decks/93`) and `play.limitlesstcg.com/decks` (uses **leader codes** `/decks/OP13-002`). Always use `play.` — only it exposes joinable codes.
- Leader codes can be `OPxx-yyy` or `STxx-yyy` (Starter Decks). Regex must allow both.
- Default page (no `set=` param) serves the current format — confirmed working as the future-proof entry point.
