"""Download crew/faction logos for every OPTCG leader character.

Sources Jolly Roger flags and faction symbols from the One Piece Wiki via the
Fandom MediaWiki API. Each leader is mapped to their crew/faction logo. These are
rectangular emblems suitable for website archetype cards and navigation on OPDex.

Pipeline:
  1. Scrape Bandai card list (Playwright) to get all Leader-type cards
  2. Map each leader to their crew/faction logo filename on the wiki
  3. Download images from the static.wikia.nocookie.net CDN
"""

import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from utils import output_json, setup_logging, timestamp

log = setup_logging("optcg_leader_art")

CARD_LIST_URL = "https://en.onepiece-cardgame.com/cardlist/"
WIKI_API = "https://onepiece.fandom.com/api.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── Leader → Logo mapping ────────────────────────────────────────────────
# Maps OPTCG leader card name → wiki image filename for their crew/faction logo.
# The wiki stores Jolly Rogers as "CrewName'_Jolly_Roger.png".

LEADER_LOGO_MAP = {
    # Straw Hat Pirates & allies
    "Roronoa Zoro": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Monkey.D.Luffy": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Nami": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Sanji": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Tony Tony.Chopper": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Nico Robin": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Brook": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Usopp": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Jinbe": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Roronoa Zoro & Sanji": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Lucy": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Whitebeard Pirates
    "Edward.Newgate": "Whitebeard_Pirates'_Jolly_Roger.png",
    "Marco": "Whitebeard_Pirates'_Jolly_Roger.png",
    "Ace & Newgate": "Whitebeard_Pirates'_Jolly_Roger.png",

    # Portgas D. Ace (Spade Pirates)
    "Portgas.D.Ace": "Spade_Pirates'_Jolly_Roger.png",

    # Heart Pirates (Trafalgar Law)
    "Trafalgar Law": "Heart_Pirates'_Jolly_Roger.png",

    # Red Hair Pirates
    "Shanks": "Red_Hair_Pirates'_Jolly_Roger.png",

    # Big Mom Pirates
    "Charlotte.Linlin": "Big_Mom_Pirates'_Jolly_Roger.png",
    "Charlotte Linlin": "Big_Mom_Pirates'_Jolly_Roger.png",
    "Charlotte Katakuri": "Big_Mom_Pirates'_Jolly_Roger.png",
    "Charlotte Pudding": "Big_Mom_Pirates'_Jolly_Roger.png",

    # Beasts Pirates
    "Kaido": "Beasts_Pirates'_Jolly_Roger.png",
    "King": "Beasts_Pirates'_Jolly_Roger.png",
    "Queen": "Beasts_Pirates'_Jolly_Roger.png",

    # Donquixote Pirates
    "Donquixote Doflamingo": "Donquixote_Pirates'_Jolly_Roger.png",
    "Donquixote Rosinante": "Donquixote_Pirates'_Jolly_Roger.png",
    "Sugar": "Donquixote_Pirates'_Jolly_Roger.png",

    # Blackbeard Pirates
    "Marshall.D.Teach": "Blackbeard_Pirates'_Jolly_Roger.png",

    # Roger Pirates
    "Gol.D.Roger": "Roger_Pirates'_Jolly_Roger.png",
    "Silvers Rayleigh": "Roger_Pirates'_Jolly_Roger.png",

    # Kid Pirates
    'Eustass"Captain"Kid': "Kid_Pirates'_Jolly_Roger.png",

    # Buggy Pirates / Cross Guild
    "Buggy": "Buggy_Pirates'_Jolly_Roger.png",
    "Crocodile": "Cross_Guild_Portrait.png",

    # Baroque Works (Crocodile's org — use Cross Guild since he's there now)
    # "Crocodile" mapped above to Cross Guild

    # Arlong Pirates
    "Arlong": "Arlong_Pirates'_Jolly_Roger.png",

    # Black Cat Pirates
    "Kuro": "Black_Cat_Pirates'_Jolly_Roger.png",

    # Krieg Pirates
    "Krieg": "Krieg_Pirates'_Jolly_Roger.png",

    # Foxy Pirates
    "Foxy": "Foxy_Pirates'_Current_Jolly_Roger.png",

    # Sun Pirates
    "Hody Jones": "New_Fish-Man_Pirates'_Jolly_Roger.png",

    # Bonney Pirates
    "Jewelry Bonney": "Bonney_Pirates'_Jolly_Roger.png",

    # Drake Pirates
    "X Drake": "Drake_Pirates'_Jolly_Roger.png",

    # On Air Pirates (Scratchmen Apoo) — not a leader but kept for reference

    # Kuja Pirates
    "Boa Hancock": "Kuja_Pirates_Portrait.png",

    # Thriller Bark / Gecko Moria
    "Gecko Moria": "Thriller_Bark_Pirates_Portrait.png",
    "Perona": "Perona's_Jolly_Roger.png",

    # Marines & World Government
    "Monkey.D.Garp": "Marines_Infobox.png",
    "Sakazuki": "Marines_Infobox.png",
    "Smoker": "Marines_Infobox.png",
    "Issho": "Marines_Infobox.png",
    "Koby": "Marines_Infobox.png",
    "Kuzan": "Marines_Infobox.png",
    "Sengoku": "Marines_Infobox.png",
    "Zephyr": "Marines_Infobox.png",
    "Magellan": "Impel_Down.png",
    "Hannyabal": "Impel_Down.png",
    "Rob Lucci": "World_Government_Portrait.png",
    "Imu": "World_Government_Portrait.png",

    # Revolutionary Army
    "Sabo": "Revolutionary_Army_Portrait.png",
    "Monkey.D.Dragon": "Revolutionary_Army_Portrait.png",
    "Belo Betty": "Revolutionary_Army_Portrait.png",
    "Koala": "Revolutionary_Army_Portrait.png",
    "Emporio.Ivankov": "Revolutionary_Army_Portrait.png",

    # Yamato (allied with Straw Hats, from Wano/Beasts Pirates)
    "Yamato": "Beasts_Pirates'_Jolly_Roger.png",

    # Uta (film character — use Straw Hat flag)
    "Uta": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Enel (Skypiea — no pirate crew, use his character portrait)
    "Enel": "Enel_Anime_Infobox.png",

    # Kalgara (Shandian warrior — use character portrait, no crew logo)
    "Kalgara": "Kalgara_Anime_Infobox.png",

    # Rumbar Pirates (Brook's old crew)
    # Brook is now Straw Hat, mapped above

    # Dressrosa
    "Rebecca": "Donquixote_Pirates'_Jolly_Roger.png",
    "Kyros": "Donquixote_Pirates'_Jolly_Roger.png",

    # Alabasta / Vivi
    "Nefeltari Vivi": "Straw_Hat_Pirates'_Jolly_Roger.png",
    "Nefertari Vivi": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Mink tribe
    "Carrot": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Wano
    "Kouzuki Oden": "Whitebeard_Pirates'_Jolly_Roger.png",
    "Kin'emon": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Vegapunk
    "Vegapunk": "World_Government_Portrait.png",

    # Iceburg (Water 7)
    "Iceburg": "World_Government_Portrait.png",

    # Shirahoshi (Ryugu Kingdom — use Sun Pirates)
    "Shirahoshi": "Sun_Pirates'_Jolly_Roger.png",

    # Caesar Clown
    "Caesar Clown": "Donquixote_Pirates'_Jolly_Roger.png",

    # Vinsmoke family
    "Vinsmoke Reiju": "Straw_Hat_Pirates'_Jolly_Roger.png",

    # Cavendish (Beautiful Pirates)
    "Cavendish": "Beautiful_Pirates_Digitally_Colored_Jolly_Roger.png",

    # Fire Tank Pirates
    "Capone Bege": "Fire_Tank_Pirates'_Jolly_Roger.png",

    # Dracule Mihawk (Cross Guild)
    "Dracule Mihawk": "Cross_Guild_Portrait.png",

    # On Air Pirates
    "Scratchmen Apoo": "On_Air_Pirates'_Jolly_Roger.png",

    # Lim (newer character)
    "Lim": "World_Government_Portrait.png",

    # Bentham (Mr. 2)
    "Bentham": "Straw_Hat_Pirates'_Jolly_Roger.png",
}


def _normalize_card_name(raw_name: str) -> str:
    """Clean card name."""
    name = raw_name.strip()
    name = re.sub(r"\[.*?\]", "", name).strip()
    name = name.strip(".")
    return name


# ── Step 1: Scrape leader list from Bandai ────────────────────────────────

def scrape_leaders(timeout: int = 120) -> list[dict]:
    """Scrape all Leader cards from the official Bandai card list."""
    log.info("Scraping leader cards from Bandai card list...")
    leaders = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(CARD_LIST_URL, timeout=timeout * 1000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        page.evaluate('document.querySelector("#category_Leader").click()')
        page.wait_for_timeout(500)
        page.evaluate('document.querySelector("#series").selectedIndex = 1')
        page.wait_for_timeout(500)

        page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[value=SEARCH]');
            if (inputs.length > 1) inputs[1].click();
            else if (inputs.length > 0) inputs[0].click();
        }""")
        page.wait_for_timeout(5000)

        _JS_EXTRACT = """els => els.map(el => {
            const info = el.querySelector('.infoCol');
            const spans = info ? Array.from(info.querySelectorAll('span')) : [];
            const code = spans[0] ? spans[0].textContent.trim() : '';
            const cardType = spans[2] ? spans[2].textContent.trim() : '';
            const nameEl = el.querySelector('.cardName');
            const name = nameEl ? nameEl.textContent.trim() : '';
            const colorEl = el.querySelector('.color');
            const color = colorEl ? colorEl.textContent.replace('Color', '').trim() : '';
            return { code, cardType, name, color };
        })"""

        cards_raw = page.eval_on_selector_all("dl.modalCol", _JS_EXTRACT)

        for _ in range(50):
            try:
                next_li = page.query_selector(".pagerCol li:last-child")
                if not next_li:
                    break
                classes = next_li.get_attribute("class") or ""
                if "disableBtn" in classes:
                    break
                link = next_li.query_selector("a")
                if not link:
                    break
                link.click(timeout=5000)
                page.wait_for_timeout(2000)
                cards_raw.extend(page.eval_on_selector_all("dl.modalCol", _JS_EXTRACT))
            except Exception:
                break

        browser.close()

    seen_names = set()
    for card in cards_raw:
        if "leader" not in card.get("cardType", "").lower():
            continue
        name = _normalize_card_name(card.get("name", ""))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        leaders.append({
            "code": card.get("code", "").strip(),
            "name": name,
            "color": card.get("color", ""),
        })

    log.info("Found %d unique leader characters", len(leaders))
    return leaders


# ── Step 2: Download logos via wiki API ───────────────────────────────────

def _get_image_url(filename: str) -> str | None:
    """Get the CDN URL for a wiki image file via the MediaWiki API."""
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|size",
        "format": "json",
    })
    url = f"{WIKI_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())

    pages = data.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        if page_id == "-1":
            return None
        info = page_data.get("imageinfo", [{}])[0]
        return info.get("url")
    return None


def download_logo(character_name: str, output_dir: Path) -> dict | None:
    """Download the crew/faction logo for a character."""
    wiki_filename = LEADER_LOGO_MAP.get(character_name)
    if not wiki_filename:
        log.warning("  No logo mapping for %s", character_name)
        return None

    log.info("  Wiki file: %s", wiki_filename)
    img_url = _get_image_url(wiki_filename)
    if not img_url:
        log.warning("  Image not found on wiki: %s", wiki_filename)
        return None

    # Download
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", character_name)
    log.info("  Downloading: %s", img_url[:120])
    req = urllib.request.Request(img_url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as e:
        log.warning("  Download failed: %s", str(e)[:80])
        return None

    if len(data) < 1000:
        log.warning("  Image too small (%d bytes)", len(data))
        return None

    ext = ".webp" if "webp" in content_type else ".png" if "png" in content_type else ".jpg"
    out_path = output_dir / f"{safe_name}{ext}"
    out_path.write_bytes(data)
    size_kb = len(data) / 1024
    log.info("  Saved: %s (%.1f KB)", out_path.name, size_kb)

    return {
        "character": character_name,
        "file": str(out_path),
        "filename": out_path.name,
        "source_url": img_url,
        "wiki_file": wiki_filename,
        "size_kb": round(size_kb, 1),
    }


# ── Main pipeline ─────────────────────────────────────────────────────────

def run(output_dir: str = "leader_artwork", leaders_json: str | None = None,
        timeout: int = 120, delay: float = 0.5) -> dict:
    """Get leader list, then download logos for each.

    Args:
        output_dir: Directory to save logo images.
        leaders_json: Optional path to pre-existing leaders JSON (skip Bandai scrape).
        timeout: Timeout for the Bandai card list scrape.
        delay: Delay between API requests.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if leaders_json and os.path.exists(leaders_json):
        log.info("Loading leaders from %s", leaders_json)
        with open(leaders_json, "r", encoding="utf-8") as f:
            leaders = json.load(f)
    else:
        leaders = scrape_leaders(timeout)
        leaders_path = out / "leaders.json"
        with open(leaders_path, "w", encoding="utf-8") as f:
            json.dump(leaders, f, indent=2, ensure_ascii=False)
        log.info("Leader list saved to %s", leaders_path)

    log.info("Downloading logos for %d leader characters", len(leaders))

    results = []
    failed = []
    # Track which wiki files we've already downloaded to avoid duplicates
    downloaded_files: dict[str, str] = {}

    for idx, leader in enumerate(leaders):
        name = leader["name"]
        log.info("[%d/%d] %s (%s)", idx + 1, len(leaders), name, leader.get("code", ""))

        wiki_file = LEADER_LOGO_MAP.get(name)
        if wiki_file and wiki_file in downloaded_files:
            # Same logo already downloaded — just copy/link the reference
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
            existing = downloaded_files[wiki_file]
            ext = Path(existing).suffix
            out_path = out / f"{safe_name}{ext}"
            if str(out_path) != existing:
                # Copy the file
                out_path.write_bytes(Path(existing).read_bytes())
            log.info("  Reused: %s (same as %s)", out_path.name, Path(existing).name)
            results.append({
                "character": name,
                "file": str(out_path),
                "filename": out_path.name,
                "wiki_file": wiki_file,
                "reused_from": existing,
                "code": leader.get("code", ""),
                "color": leader.get("color", ""),
            })
            continue

        result = download_logo(name, out)
        if result:
            result["code"] = leader.get("code", "")
            result["color"] = leader.get("color", "")
            results.append(result)
            if wiki_file:
                downloaded_files[wiki_file] = result["file"]
        else:
            failed.append({"name": name, "code": leader.get("code", "")})

        if delay > 0:
            time.sleep(delay)

    manifest = {
        "success": True,
        "total_leaders": len(leaders),
        "logos_found": len(results),
        "logos_missing": len(failed),
        "failed_characters": failed,
        "assets": results,
        "timestamp": timestamp(),
    }
    manifest_path = out / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info("Done: %d/%d logos downloaded. Manifest: %s",
             len(results), len(leaders), manifest_path)
    if failed:
        log.info("Missing logos for: %s", ", ".join(f["name"] for f in failed))

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download crew/faction logos for OPTCG leaders")
    parser.add_argument(
        "--output-dir", default="leader_artwork",
        help="Directory to save logo images (default: leader_artwork)",
    )
    parser.add_argument(
        "--leaders-json", default=None,
        help="Path to pre-existing leaders JSON file (skip Bandai scrape)",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between API requests in seconds (default: 0.5)")
    args = parser.parse_args()

    result = run(
        output_dir=args.output_dir,
        leaders_json=args.leaders_json,
        timeout=args.timeout,
        delay=args.delay,
    )
    output_json(result)
