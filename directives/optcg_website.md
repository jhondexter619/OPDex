# Directive: OPDex Website

## Goal
Serve a minimal web dashboard ("OPDex") that displays OPTCG competitive meta data, deck profiles, and generates print-ready PDFs on demand.

## Architecture

- **Framework:** Flask (Python)
- **Frontend:** Jinja2 templates + vanilla CSS/JS + Chart.js
- **Data:** JSON files produced by `execution/optcg_deck_scraper.py`, stored in `website/data/`
- **PDF:** Reuses `execution/optcg_deck_pdf.py` functions (load_card_image, upscale_image, create_pdf)
- **Card images:** Served directly from `OPTCG CARD ASSETS/` via Flask route

## Data Pipeline

**Automatic (default):** The Flask app runs a background scraper thread on startup.
- If no data exists in `website/data/`, it scrapes immediately
- Otherwise it uses existing data and schedules the next scrape
- Default interval: every 6 hours
- Old data files are cleaned up automatically (keeps last 10)
- Status shown in footer: last update time, next refresh, manual "Refresh Now" button

**Manual:** Can also scrape on demand:
```
cd execution && python optcg_deck_scraper.py --output ../website/data/meta.json
```

**Configuration (env vars):**
- `OPDEX_SCRAPE_INTERVAL` — seconds between scrapes (default: 21600 = 6h)
- `OPDEX_FORMAT_SLUGS` — comma-separated format slugs to scrape (default: OP-15)

## Pages

| Route | Description |
|---|---|
| `/` | Home — stat cards, top 5 horizontal bar chart, clickable archetype breakdown, searchable deck table |
| `/archetype/<name>` | Archetype detail — all decks of that type, matchup outlook |
| `/deck/<idx>` | Deck detail — player/tournament/placement info, matchup outlook, card image grid, PDF download |
| `/card-image/<code>` | Serves card image from local assets |
| `/download-pdf/<idx>` | Generates and returns print-ready A4 PDF (3x3 grid, crop marks) |
| `/refresh` (POST) | Trigger immediate scrape |
| `/api/meta` | JSON API for meta statistics |
| `/api/status` | JSON API for scraper status |

## Running

```bash
cd website && python app.py
# → http://localhost:5000

# Custom interval (e.g. every 1 hour):
OPDEX_SCRAPE_INTERVAL=3600 python app.py

# Multiple formats:
OPDEX_FORMAT_SLUGS="japan-op-15-deck-list-adventure-on-kamis-island,japan-op-14-deck-list-the-azure-sea-seven" python app.py
```

## Dependencies

- flask (added to requirements.txt)
- All existing execution dependencies (Pillow, fpdf2, playwright, etc.)

## Learnings

- Card images are served from `OPTCG CARD ASSETS/<batch>/` — the route finds the largest non-thumbnail file matching the card code
- PDF generation can take 10-30 seconds for large decks (51 cards × 3x upscale) — the button shows a loading state
- The scraper requires Playwright with headless Chromium — background thread handles this automatically
- Chart.js loaded via CDN (no build step needed)
- Flask debug reloader spawns two processes — scraper only starts in the child process (checks `WERKZEUG_RUN_MAIN`)
- Matchup outlook uses average placement scores as a heuristic — not true head-to-head data
- Render free tier suspends idle services, killing the background scraper thread. On restart, data can be days stale. Fixed by checking data age on startup and re-scraping if older than SCRAPE_INTERVAL (instead of only scraping when no data exists at all).
- The source site (onepiecetopdecks.com) caps visible decks at ~100 per format page. As new tournament results are added, older ones roll off. Frequent scraping ensures we capture everything.
