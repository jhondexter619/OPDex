"""Scrape OPTCG card metadata (color, cost, type, name) from the official Bandai card database."""

import argparse
import json
import re

from playwright.sync_api import sync_playwright

from utils import output_json, setup_logging, timestamp

log = setup_logging("optcg_card_meta")

CARD_LIST_URL = "https://en.onepiece-cardgame.com/cardlist/"


def _extract_cards_from_page(page) -> list[dict]:
    """Extract card metadata from all dl.modalCol elements on the current page."""
    return page.eval_on_selector_all(
        'dl.modalCol',
        """els => els.map(el => {
            const info = el.querySelector('.infoCol');
            const spans = info ? Array.from(info.querySelectorAll('span')) : [];
            const code = spans[0] ? spans[0].textContent.trim() : '';
            const rarity = spans[1] ? spans[1].textContent.trim() : '';
            const cardType = spans[2] ? spans[2].textContent.trim() : '';

            const nameEl = el.querySelector('.cardName');
            const name = nameEl ? nameEl.textContent.trim() : '';

            const costEl = el.querySelector('.cost');
            const cost = costEl ? costEl.textContent.replace(/[^0-9]/g, '') : '';

            const powerEl = el.querySelector('.power');
            const power = powerEl ? powerEl.textContent.replace(/[^0-9]/g, '') : '';

            const colorEl = el.querySelector('.color');
            const color = colorEl ? colorEl.textContent.replace('Color', '').trim() : '';

            return { code, rarity, cardType, name, cost, power, color };
        })"""
    )


def scrape_card_metadata(timeout: int = 180) -> dict:
    """Scrape all card metadata from the official Bandai One Piece TCG card list.

    Returns a dict mapping card_code -> {name, color, cost, type, power, set}.
    """
    log.info("Scraping card metadata from: %s", CARD_LIST_URL)
    card_db = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(CARD_LIST_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Get all series options
            series_options = page.eval_on_selector_all(
                'select#series option',
                "els => els.map(el => ({value: el.value, text: el.textContent.trim()}))"
            )
            series_list = [s for s in series_options if s["value"]]
            log.info("Found %d series to scrape", len(series_list))

            for idx, series in enumerate(series_list):
                series_val = series["value"]
                series_name = re.sub(r'<[^>]+>', ' ', series["text"]).strip()[:60]
                log.info("  [%d/%d] %s", idx + 1, len(series_list), series_name)

                try:
                    # Navigate directly with series param (avoids form interaction issues)
                    page.goto(
                        f"{CARD_LIST_URL}?series={series_val}",
                        timeout=20000,
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(2000)

                    # Check if cards loaded
                    card_count = page.eval_on_selector_all('dl.modalCol', 'els => els.length')
                    if not card_count:
                        log.info("    No cards found, skipping")
                        continue

                    # Extract from current page
                    cards_raw = _extract_cards_from_page(page)
                    page_num = 1

                    # Handle pagination — click NEXT until no more pages
                    for _ in range(30):
                        try:
                            next_li = page.query_selector('.pagerCol li:last-child')
                            if not next_li:
                                break
                            classes = next_li.get_attribute('class') or ''
                            if 'disableBtn' in classes:
                                break
                            link = next_li.query_selector('a')
                            if not link:
                                break
                            link.click(timeout=5000)
                            page.wait_for_timeout(1500)
                            page_num += 1
                            cards_raw.extend(_extract_cards_from_page(page))
                        except Exception:
                            break

                    # Process extracted cards
                    parsed = 0
                    for card in cards_raw:
                        code = card.get("code", "").strip().upper()
                        if not code or not re.match(r"[A-Z]+\d*-\d+", code):
                            continue

                        cost_str = card.get("cost", "")
                        cost = int(cost_str) if cost_str.isdigit() else None

                        card_type = card.get("cardType", "").strip()
                        # Normalize type
                        t = card_type.upper()
                        if "LEADER" in t:
                            card_type = "Leader"
                        elif "CHARACTER" in t:
                            card_type = "Character"
                        elif "EVENT" in t:
                            card_type = "Event"
                        elif "STAGE" in t:
                            card_type = "Stage"

                        color = card.get("color", "").strip()

                        batch = re.match(r"([A-Z]+\d+)", code)
                        card_set = batch.group(1).upper() if batch else ""

                        card_db[code] = {
                            "name": card.get("name", code),
                            "color": color,
                            "cost": cost,
                            "type": card_type,
                            "power": card.get("power", ""),
                            "set": card_set,
                        }
                        parsed += 1

                    log.info("    %d cards (%d pages)", parsed, page_num)

                except Exception as e:
                    log.warning("    Failed: %s", str(e)[:80])
                    continue

            browser.close()

    except Exception as e:
        log.exception("Browser scrape failed")
        return {"success": False, "error": str(e), "card_db": card_db, "timestamp": timestamp()}

    log.info("Total cards scraped: %d", len(card_db))
    return {
        "success": True,
        "total_cards": len(card_db),
        "card_db": card_db,
        "timestamp": timestamp(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape OPTCG card metadata")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--output", default=None,
        help="Output file path (JSON). Prints to stdout if omitted.",
    )
    args = parser.parse_args()

    result = scrape_card_metadata(args.timeout)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result["card_db"], f, indent=2, ensure_ascii=False)
        log.info("Card database written to %s (%d cards)", args.output, len(result["card_db"]))
    else:
        output_json(result)
