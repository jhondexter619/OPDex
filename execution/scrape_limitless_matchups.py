"""Scrape OPTCG matchup win-rates from play.limitlesstcg.com.

Source of truth: real head-to-head tournament results, with game counts.
Future-proof: never hardcodes set names — always follows whatever the
Limitless index page links to, so new sets (OP16+) auto-rotate.

See `directives/scrape_limitless_matchups.md` for the full spec.
"""

import argparse
import json
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils import output_json, setup_logging, timestamp

log = setup_logging("limitless_matchups")

BASE = "https://play.limitlesstcg.com"
INDEX_URL = f"{BASE}/decks?game=OP"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OPDex/1.0; matchup-stats)",
    "Accept": "text/html,application/xhtml+xml",
}

# OPxx-yyy or STxx-yyy (also EBxx, PRBxx, etc. — accept any uppercase prefix)
LEADER_CODE_RE = re.compile(r"\b([A-Z]{2,4}\d{1,3}-\d{3})\b")
DECK_HREF_RE = re.compile(r"^/decks/([A-Z]{2,4}\d{1,3}-\d{3})(?:[/?]|$)")
SET_PARAM_RE = re.compile(r"[?&]set=([A-Za-z0-9._-]+)")


def fetch(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_index(html: str) -> tuple[str, list[dict]]:
    """Parse the deck index page.

    Returns:
        (current_set, decks) where decks is a list of
        {leader_code, leader_name, matchup_path}.
    """
    soup = BeautifulSoup(html, "html.parser")
    decks: list[dict] = []
    seen: set[str] = set()
    current_set = ""

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = DECK_HREF_RE.match(href)
        if not m:
            continue

        code = m.group(1)
        if code in seen:
            continue

        # Extract leader name from the link text (or its parent row if empty)
        name = a.get_text(" ", strip=True)
        if not name:
            parent = a.find_parent(["tr", "li", "div"])
            name = parent.get_text(" ", strip=True) if parent else code

        # Build the matchup URL — Limitless usually links straight to the
        # /decks/CODE page. Append /matchups while preserving the query string.
        if "/matchups" in href:
            matchup_path = href
        else:
            base, _, qs = href.partition("?")
            matchup_path = base.rstrip("/") + "/matchups"
            matchup_path += "?" + qs if qs else "?game=OP"

        decks.append({
            "leader_code": code,
            "leader_name": name,
            "matchup_path": matchup_path,
        })
        seen.add(code)

        if not current_set:
            sm = SET_PARAM_RE.search(matchup_path)
            if sm:
                current_set = sm.group(1)

    return current_set, decks


def _header_indices(headers: list[str]) -> dict[str, int]:
    """Map column purpose → index, by matching header keywords."""
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        h = h.lower()
        if "deck" in h or "opponent" in h:
            idx.setdefault("deck", i)
        elif "match" in h:
            idx.setdefault("matches", i)
        elif "score" in h or "record" in h:
            idx.setdefault("score", i)
        elif "win" in h or "%" in h:
            idx.setdefault("win", i)
    return idx


def parse_matchups(html: str) -> list[dict]:
    """Parse a deck's matchup table into a list of opponent rows."""
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not headers:
            continue
        col = _header_indices(headers)
        if "matches" not in col or "win" not in col:
            continue

        rows: list[dict] = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) <= max(col.values()):
                continue

            deck_cell = tds[col.get("deck", 0)]
            opp_link = deck_cell.find("a", href=True)
            opp_code = ""
            if opp_link:
                m = LEADER_CODE_RE.search(opp_link["href"])
                if m:
                    opp_code = m.group(1)
            opp_name = deck_cell.get_text(" ", strip=True)

            try:
                matches = int(tds[col["matches"]].get_text(strip=True).replace(",", ""))
            except (ValueError, IndexError):
                continue

            wins = losses = ties = 0
            if "score" in col:
                score_txt = tds[col["score"]].get_text(strip=True)
                sm = re.match(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", score_txt)
                if sm:
                    wins, losses, ties = (int(x) for x in sm.groups())

            win_txt = tds[col["win"]].get_text(strip=True).rstrip("%").replace(",", "")
            try:
                win_pct = float(win_txt)
            except ValueError:
                continue

            rows.append({
                "opponent_code": opp_code,
                "opponent_name": opp_name,
                "matches": matches,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "win_pct": win_pct,
            })

        if rows:
            return rows

    return []


def scrape_all(
    limit: int | None = None,
    rate_delay: float = 1.0,
    timeout: int = 30,
) -> dict:
    log.info("Fetching index: %s", INDEX_URL)
    try:
        index_html = fetch(INDEX_URL, timeout)
    except Exception as e:
        log.exception("Index fetch failed")
        return {"success": False, "error": f"index fetch failed: {e}", "timestamp": timestamp()}

    current_set, decks = parse_index(index_html)
    log.info("Found %d decks for current set: %s", len(decks), current_set or "(unknown)")

    if not decks:
        return {
            "success": False,
            "error": "no decks parsed from index",
            "source_url": INDEX_URL,
            "timestamp": timestamp(),
        }

    if limit is not None:
        decks = decks[:limit]
        log.info("Limiting to first %d decks", len(decks))

    matchups: dict[str, dict] = {}
    leaders: dict[str, str] = {}

    for i, d in enumerate(decks, 1):
        url = urljoin(BASE, d["matchup_path"])
        log.info("[%d/%d] %s — %s", i, len(decks), d["leader_code"], d["leader_name"])
        try:
            html = fetch(url, timeout)
            rows = parse_matchups(html)
        except Exception as e:
            log.warning("  fetch/parse failed: %s", e)
            time.sleep(rate_delay)
            continue

        leader_data = {}
        for r in rows:
            if not r["opponent_code"]:
                continue
            leader_data[r["opponent_code"]] = {
                "win_pct": r["win_pct"],
                "matches": r["matches"],
                "wins": r["wins"],
                "losses": r["losses"],
                "ties": r["ties"],
                "opponent_name": r["opponent_name"],
            }

        if leader_data:
            matchups[d["leader_code"]] = leader_data
            leaders[d["leader_code"]] = d["leader_name"]
            log.info("  %d matchups parsed", len(leader_data))
        else:
            log.warning("  no usable matchup rows")

        time.sleep(rate_delay)

    return {
        "success": True,
        "source_url": INDEX_URL,
        "format": current_set,
        "total_leaders": len(matchups),
        "leaders": leaders,
        "matchups": matchups,
        "timestamp": timestamp(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape OPTCG matchups from Limitless TCG")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only scrape the first N decks (for smoke testing)")
    parser.add_argument("--rate-delay", type=float, default=1.0,
                        help="Seconds between leader requests (default: 1.0)")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", default=None,
                        help="Optional output file path (JSON). Prints to stdout if omitted.")
    args = parser.parse_args()

    result = scrape_all(limit=args.limit, rate_delay=args.rate_delay, timeout=args.timeout)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        log.info("Results written to %s", args.output)
    else:
        output_json(result)
