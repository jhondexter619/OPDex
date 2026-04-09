"""OPDex - OPTCG Meta Dashboard.

Serves a minimal web interface showing competitive One Piece TCG meta data,
deck profiles, and print-ready PDF downloads. Auto-refreshes data from
onepiecetopdecks.com on a configurable schedule.
"""

import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import cv2
import numpy as np
from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_file, url_for
from supabase import create_client as supabase_create_client

# Add execution/ to path so we can import existing scripts
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from optcg_deck_pdf import create_pdf, load_card_image, upscale_image
from optcg_deck_scraper import scrape_deck_profiles

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Supabase server-side client
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_sb = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    _sb = supabase_create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

from auth import require_admin, require_auth  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"
ASSETS_DIR = ROOT / "OPTCG CARD ASSETS"

log = logging.getLogger("opdex")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Scrape interval in seconds (default 6 hours, override with env var)
SCRAPE_INTERVAL = int(os.environ.get("OPDEX_SCRAPE_INTERVAL", 6 * 60 * 60))

# Format slugs to scrape (comma-separated via env var, or default)
FORMAT_SLUGS = os.environ.get(
    "OPDEX_FORMAT_SLUGS",
    "japan-op-15-deck-list-adventure-on-kamis-island",
).split(",")

# Max data files to keep (older ones are cleaned up)
MAX_DATA_FILES = 10

# Scraper state (visible to templates via context processor)
_scraper_state = {
    "last_refresh": None,
    "next_refresh": None,
    "status": "idle",       # idle | scraping | error
    "error": None,
}


# ---------------------------------------------------------------------------
# Background scraper
# ---------------------------------------------------------------------------

def _run_scrape():
    """Scrape all configured formats and merge results into one JSON file."""
    _scraper_state["status"] = "scraping"
    _scraper_state["error"] = None
    log.info("Auto-scrape starting for formats: %s", FORMAT_SLUGS)

    all_decks = []
    source_urls = []

    for slug in FORMAT_SLUGS:
        slug = slug.strip()
        if not slug:
            continue
        try:
            result = scrape_deck_profiles(slug, timeout=90)
            if result.get("success") and result.get("decks"):
                all_decks.extend(result["decks"])
                source_urls.append(result.get("source_url", ""))
                log.info("  %s: %d decks", slug, len(result["decks"]))
            else:
                log.warning("  %s: scrape returned no decks — %s", slug, result.get("error", "unknown"))
        except Exception as e:
            log.error("  %s: scrape failed — %s", slug, e)

    if not all_decks:
        _scraper_state["status"] = "error"
        _scraper_state["error"] = "No decks returned from any format"
        log.error("Auto-scrape finished with 0 decks")
        return

    # Save merged data
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = DATA_DIR / f"meta_{ts}.json"
    payload = {
        "success": True,
        "source_url": ", ".join(source_urls),
        "formats": [s.strip() for s in FORMAT_SLUGS],
        "total_decks": len(all_decks),
        "decks": all_decks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    log.info("Auto-scrape complete: %d decks → %s", len(all_decks), out_path.name)

    # Clean up old data files, keep the most recent MAX_DATA_FILES
    old_files = sorted(DATA_DIR.glob("meta_*.json"), key=lambda f: f.stat().st_mtime)
    while len(old_files) > MAX_DATA_FILES:
        removed = old_files.pop(0)
        removed.unlink()
        log.info("Cleaned up old data file: %s", removed.name)

    _scraper_state["status"] = "idle"
    _scraper_state["last_refresh"] = datetime.now(timezone.utc).isoformat()


def _scrape_loop():
    """Background loop: scrape on startup if data is stale, then every SCRAPE_INTERVAL."""
    existing = sorted(DATA_DIR.glob("meta_*.json"), key=lambda f: f.stat().st_mtime) if DATA_DIR.exists() else []

    if not existing:
        log.info("No existing data found — running initial scrape")
        _run_scrape()
    else:
        latest = existing[-1]
        age_secs = time.time() - latest.stat().st_mtime
        _scraper_state["last_refresh"] = datetime.fromtimestamp(
            latest.stat().st_mtime, tz=timezone.utc,
        ).isoformat()
        if age_secs > SCRAPE_INTERVAL:
            log.info("Data is %.1f hours old (> %d min interval) — refreshing now",
                     age_secs / 3600, SCRAPE_INTERVAL // 60)
            _run_scrape()
        else:
            log.info("Existing data is fresh (%.1f min old) — skipping initial scrape",
                     age_secs / 60)

    while True:
        _scraper_state["next_refresh"] = datetime.fromtimestamp(
            time.time() + SCRAPE_INTERVAL, tz=timezone.utc,
        ).isoformat()
        log.info("Next auto-scrape in %d minutes", SCRAPE_INTERVAL // 60)
        time.sleep(SCRAPE_INTERVAL)
        _run_scrape()


def start_scraper():
    """Launch the background scraper thread (called once at startup)."""
    t = threading.Thread(target=_scrape_loop, daemon=True, name="opdex-scraper")
    t.start()
    log.info("Background scraper started (interval: %d min)", SCRAPE_INTERVAL // 60)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data():
    """Load the most recent scraped meta data JSON from website/data/."""
    if not DATA_DIR.exists():
        return None
    json_files = sorted(
        DATA_DIR.glob("meta_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not json_files:
        return None
    with open(json_files[0], encoding="utf-8") as f:
        return json.load(f)


def _placement_score(placement: str) -> int:
    """Convert placement string to a numeric score (lower = better)."""
    if not placement:
        return 99
    p = placement.strip().lower()
    if p == "1st":
        return 1
    if p == "2nd":
        return 2
    if p == "3rd":
        return 3
    m = re.match(r"top\s*(\d+)", p)
    if m:
        return int(m.group(1))
    m = re.match(r"(\d+)", p)
    if m:
        return int(m.group(1))
    return 99


# ---------------------------------------------------------------------------
# Face / eye detection for card artwork cropping
# ---------------------------------------------------------------------------
_face_y_cache: dict[str, int] = {}

# Pre-load cascades once
_cascades = None


def _get_cascades():
    global _cascades
    if _cascades is None:
        hc = cv2.data.haarcascades
        _cascades = {
            "face": cv2.CascadeClassifier(hc + "haarcascade_frontalface_default.xml"),
            "alt2": cv2.CascadeClassifier(hc + "haarcascade_frontalface_alt2.xml"),
            "profile": cv2.CascadeClassifier(hc + "haarcascade_profileface.xml"),
            "eye": cv2.CascadeClassifier(hc + "haarcascade_eye.xml"),
        }
    return _cascades


def _find_card_image(card_code: str) -> Path | None:
    """Locate the card image file on disk."""
    m = re.match(r"([A-Z]+\d*)", card_code, re.IGNORECASE)
    batch = m.group(1).upper() if m else card_code.upper()
    batch_dir = ASSETS_DIR / batch
    if not batch_dir.is_dir():
        return None
    candidates = [
        f for f in batch_dir.iterdir()
        if f.is_file()
        and card_code.lower() in f.name.lower()
        and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        and "small" not in f.name.lower()
    ]
    return max(candidates, key=lambda f: f.stat().st_size) if candidates else None


def detect_face_y(card_code: str) -> int:
    """Detect the vertical eye-center position (%) for a card image.

    Uses OpenCV cascades with a priority pipeline:
      1. Eye pair on raw image (most reliable)
      2. Face cascades on raw image (high confidence)
      3. Face cascades on preprocessed images (fallback)
    Results are cached in memory. Returns 30 as a safe default.

    Disabled when OPDEX_SKIP_FACE_DETECT=1 (e.g. on Render where OpenCV
    cascade classifiers are broken on Python 3.14).
    """
    default = 30

    if os.environ.get("OPDEX_SKIP_FACE_DETECT") == "1":
        return default

    if card_code in _face_y_cache:
        return _face_y_cache[card_code]

    path = _find_card_image(card_code)
    if not path:
        _face_y_cache[card_code] = default
        return default

    img = cv2.imread(str(path))
    if img is None:
        _face_y_cache[card_code] = default
        return default

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Only scan artwork zone (5%–62% of card height)
    art_top = int(h * 0.05)
    art_bot = int(h * 0.62)
    art_raw = gray[art_top:art_bot, :]

    cascades = _get_cascades()

    def _eye_detect(art_gray):
        """Return (y_pct, area) from eye pair detection, or None."""
        eyes = cascades["eye"].detectMultiScale(
            art_gray, scaleFactor=1.05, minNeighbors=5,
            minSize=(15, 15), maxSize=(w // 3, h // 4),
        )
        if len(eyes) >= 2:
            top_eyes = sorted(eyes, key=lambda e: e[2] * e[3], reverse=True)[:2]
            avg_y = np.mean([ey + eh // 2 for _, ey, _, eh in top_eyes])
            return round((art_top + avg_y) / h * 100)
        return None

    def _face_detect(art_gray, min_neighbors=3):
        """Return y_pct from best face cascade hit, or None."""
        best_pct, best_area = None, 0
        for key in ("face", "alt2", "profile"):
            for scale in (1.05, 1.1, 1.15, 1.2):
                faces = cascades[key].detectMultiScale(
                    art_gray, scaleFactor=scale,
                    minNeighbors=min_neighbors, minSize=(20, 20),
                )
                if len(faces) > 0:
                    largest = max(faces, key=lambda f: f[2] * f[3])
                    _, fy, fw, fh = largest
                    area = fw * fh
                    if area > best_area:
                        eye_y = art_top + fy + int(fh * 0.35)
                        best_pct = round(eye_y / h * 100)
                        best_area = area
        return best_pct

    try:
        # Priority 1: Eye pairs on raw image
        result = _eye_detect(art_raw)

        # Priority 2: Face cascades on raw image (high confidence: minNeighbors=3)
        if result is None:
            result = _face_detect(art_raw, min_neighbors=3)

        # Priority 3: Preprocessed images (equalized, CLAHE) with relaxed params
        if result is None:
            clahe_obj = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            for art_gray in (cv2.equalizeHist(art_raw), clahe_obj.apply(art_raw)):
                result = _eye_detect(art_gray)
                if result:
                    break
                result = _face_detect(art_gray, min_neighbors=2)
                if result:
                    break
    except cv2.error as e:
        log.warning("OpenCV error for %s: %s", card_code, e)
        result = None

    if result is None:
        result = default

    # Clamp to artwork zone
    result = max(12, min(result, 55))
    _face_y_cache[card_code] = result
    log.debug("Face detect %s: %d%%", card_code, result)
    return result


def compute_meta(data):
    """Aggregate deck data into meta statistics."""
    if not data or not data.get("decks"):
        return {"total_decks": 0, "archetypes": [], "top5": [], "decks": []}

    decks = data["decks"]
    counts = Counter(d["deck_name"] for d in decks)
    total = len(decks)

    archetypes = []
    for name, count in counts.most_common():
        entries = [d for d in decks if d["deck_name"] == name]
        placements = [d.get("placement", "N/A") for d in entries]
        scores = [_placement_score(p) for p in placements]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 99

        # Leader card = first card (qty 1) from the first deck of this archetype
        leader_code = None
        for e in entries:
            for c in e.get("cards", []):
                if c.get("quantity") == 1:
                    leader_code = c["card_code"]
                    break
            if leader_code:
                break

        # Resolve colors from card DB first, fall back to name parsing
        leader_color = ""
        if leader_code:
            meta_db = _load_card_meta()
            leader_color = meta_db.get(leader_code, {}).get("color", "")

        archetypes.append({
            "name": name,
            "count": count,
            "share": round(count / total * 100, 1),
            "best_placement": placements[0] if placements else "N/A",
            "avg_placement": avg_score,
            "leader_code": leader_code,
            "leader_color": leader_color,
            "face_y": detect_face_y(leader_code) if leader_code else 30,
            "players": [d.get("player", "Unknown") for d in entries],
        })

    return {
        "total_decks": total,
        "total_archetypes": len(counts),
        "archetypes": archetypes,
        "top5": archetypes[:5],
        "decks": decks,
        "source": data.get("source_url", ""),
        "format": data.get("format", ""),
        "timestamp": data.get("timestamp", ""),
    }


def compute_matchups(deck_name: str, archetypes: list) -> dict:
    """Estimate threats and favorable matchups based on avg placement scores."""
    current = next((a for a in archetypes if a["name"] == deck_name), None)
    if not current:
        return {"threats": [], "favorable": []}

    current_score = current["avg_placement"]
    others = [a for a in archetypes if a["name"] != deck_name and a["count"] >= 2]

    threats = sorted(
        [a for a in others if a["avg_placement"] < current_score],
        key=lambda a: a["avg_placement"],
    )[:5]
    favorable = sorted(
        [a for a in others if a["avg_placement"] > current_score],
        key=lambda a: -a["avg_placement"],
    )[:5]

    return {"threats": threats, "favorable": favorable}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    data = load_data()
    meta = compute_meta(data)
    return render_template("index.html", meta=meta)


@app.route("/archetype/<path:name>")
def archetype_detail(name):
    name = unquote(name)
    data = load_data()
    meta = compute_meta(data)

    arch = next((a for a in meta["archetypes"] if a["name"] == name), None)
    if not arch:
        abort(404)

    # Collect all deck entries for this archetype with their global indices
    deck_entries = []
    for i, d in enumerate(meta["decks"]):
        if d["deck_name"] == name:
            deck_entries.append({"idx": i, **d})

    matchups = compute_matchups(name, meta["archetypes"])
    deck_colors = _resolve_deck_colors(name, arch.get("leader_color", ""))
    return render_template(
        "archetype.html", arch=arch, decks=deck_entries, matchups=matchups,
        deck_colors=deck_colors,
    )


@app.route("/deck/<int:idx>")
def deck_detail(idx):
    data = load_data()
    if not data or idx >= len(data.get("decks", [])):
        abort(404)
    deck = data["decks"][idx]
    meta = compute_meta(data)
    matchups = compute_matchups(deck["deck_name"], meta["archetypes"])
    # Find leader code (first card with qty 1)
    leader_code = None
    for c in deck.get("cards", []):
        if c.get("quantity") == 1:
            leader_code = c["card_code"]
            break
    leader_color = ""
    if leader_code:
        leader_color = _load_card_meta().get(leader_code, {}).get("color", "")
    deck_colors = _resolve_deck_colors(deck.get("deck_name", ""), leader_color)
    return render_template("deck.html", deck=deck, idx=idx, matchups=matchups, leader_code=leader_code, deck_colors=deck_colors)


# Header images for hero banners
_HEADER_IMAGES = {
    "meta": "META HEADER PICTURE.webp",
    "builder": "DECK BUILDER PICTURE.webp",
    "library": "LIBRARY PICTURE.webp",
}


@app.route("/header-image/<page>")
def header_image(page):
    """Serve a header image for hero banners."""
    filename = _HEADER_IMAGES.get(page)
    if not filename:
        abort(404)
    path = ASSETS_DIR / filename
    if not path.is_file():
        # Try other extensions
        stem = path.stem
        for ext in (".webp", ".jpg", ".jpeg", ".png"):
            alt = ASSETS_DIR / (stem + ext)
            if alt.is_file():
                path = alt
                break
        else:
            abort(404)
    return send_file(str(path))


# Leader artwork directory
LEADER_ART_DIR = Path(__file__).resolve().parent / "static" / "leader_artwork"

# Map common short names from deck names to artwork filenames
_LEADER_NAME_MAP = {
    "luffy": "Monkey_D_Luffy", "ace": "Portgas_D_Ace", "law": "Trafalgar_Law",
    "doffy": "Donquixote_Doflamingo", "doflamingo": "Donquixote_Doflamingo",
    "boa": "Boa_Hancock", "enel": "Enel", "moria": "Gecko_Moria",
    "mihawk": "Dracule_Mihawk", "bonney": "Jewelry_Bonney", "kid": "Eustass_Captain_Kid",
    "katakuri": "Charlotte_Katakuri", "linlin": "Charlotte_Linlin",
    "pudding": "Charlotte_Pudding", "teach": "Marshall_D_Teach",
    "blackbeard": "Marshall_D_Teach", "newgate": "Edward_Newgate",
    "whitebeard": "Edward_Newgate", "garp": "Monkey_D_Garp",
    "dragon": "Monkey_D_Dragon", "roger": "Gol_D_Roger",
    "zoro": "Roronoa_Zoro", "nami": "Nami", "sanji": "Sanji",
    "robin": "Nico_Robin", "chopper": "Tony_Tony_Chopper", "usopp": "Usopp",
    "brook": "Brook", "jinbe": "Jinbe", "franky": "Iceburg",
    "shanks": "Shanks", "crocodile": "Crocodile", "kaido": "Kaido",
    "yamato": "Yamato", "sabo": "Sabo", "koby": "Koby",
    "smoker": "Smoker", "imu": "Imu", "kalgara": "Kalgara",
    "ivankov": "Emporio_Ivankov", "vivi": "Nefeltari_Vivi",
    "rebecca": "Rebecca", "perona": "Perona", "reiju": "Vinsmoke_Reiju",
    "lucci": "Rob_Lucci", "rayleigh": "Silvers_Rayleigh",
    "kuzan": "Kuzan", "sakazuki": "Sakazuki", "marco": "Marco",
    "oden": "Kouzuki_Oden", "buggy": "Buggy", "arlong": "Arlong",
    "king": "King", "queen": "Queen", "sugar": "Sugar", "uta": "Uta",
    "betty": "Belo_Betty", "magellan": "Magellan", "caesar": "Caesar_Clown",
    "foxy": "Foxy", "carrot": "Carrot", "hannyabal": "Hannyabal",
    "hody": "Hody_Jones", "issho": "Issho", "koala": "Koala",
    "krieg": "Krieg", "kuro": "Kuro", "kyros": "Kyros",
    "rosinante": "Donquixote_Rosinante", "vegapunk": "Vegapunk",
    "zephyr": "Zephyr", "shirahoshi": "Shirahoshi", "lim": "Lim",
    "lucy": "Lucy",
}


# Single-letter and full-word color mappings
_SINGLE_COLORS = {
    "red": "#e05245", "r": "#e05245",
    "blue": "#4a90d9", "b": "#4a90d9",
    "green": "#3fb950", "g": "#3fb950",
    "purple": "#a855f7", "p": "#a855f7",
    "black": "#8b949e",
    "yellow": "#d4a843", "y": "#d4a843",
}

# Two-letter abbreviation -> (color1, color2)
_DUAL_PREFIX_MAP = {
    "rb": ("#e05245", "#4a90d9"),   # Red Blue
    "br": ("#4a90d9", "#e05245"),   # Blue Red
    "by": ("#4a90d9", "#d4a843"),   # Blue Yellow
    "yb": ("#d4a843", "#4a90d9"),   # Yellow Blue
    "rg": ("#e05245", "#3fb950"),   # Red Green
    "gr": ("#3fb950", "#e05245"),   # Green Red
    "gp": ("#3fb950", "#a855f7"),   # Green Purple
    "pg": ("#a855f7", "#3fb950"),   # Purple Green
    "up": ("#a855f7", "#a855f7"),   # Ultra Purple (just purple)
    "rp": ("#e05245", "#a855f7"),   # Red Purple
    "gb": ("#3fb950", "#4a90d9"),   # Green Blue
    "bg": ("#4a90d9", "#3fb950"),   # Blue Green
    "ry": ("#e05245", "#d4a843"),   # Red Yellow
}

# Multi-word color prefixes -> (color1, color2)
_MULTI_WORD_MAP = {
    "red blue": ("#e05245", "#4a90d9"),
    "blue red": ("#4a90d9", "#e05245"),
    "sky island": ("#58a6ff", "#58a6ff"),
}


def _resolve_deck_colors(deck_name: str, leader_color: str = "") -> tuple[str, str]:
    """Extract one or two CSS colors from leader_color (e.g. 'Red/Blue') or deck name.

    Returns (color1, color2) — for single-color decks both are the same.
    """
    default = ("#e6edf3", "#e6edf3")

    # Primary: use leader_color from card DB (e.g. "Red/Blue", "Purple")
    if leader_color:
        parts = [p.strip().lower() for p in leader_color.split("/")]
        colors = [_SINGLE_COLORS.get(p) for p in parts]
        colors = [c for c in colors if c]  # filter None
        if len(colors) >= 2:
            return (colors[0], colors[1])
        if len(colors) == 1:
            return (colors[0], colors[0])

    # Fallback: parse from deck name
    if not deck_name:
        return default
    parts = deck_name.strip().lower().split()

    # Try multi-word prefix first (e.g. "Red Blue", "Sky Island")
    if len(parts) >= 2:
        two_word = " ".join(parts[:2])
        if two_word in _MULTI_WORD_MAP:
            return _MULTI_WORD_MAP[two_word]

    prefix = parts[0]

    # Try dual-letter abbreviation (e.g. "BY", "RG", "UP")
    if prefix in _DUAL_PREFIX_MAP:
        return _DUAL_PREFIX_MAP[prefix]

    # Try single color word/letter (e.g. "Purple", "G")
    if prefix in _SINGLE_COLORS:
        c = _SINGLE_COLORS[prefix]
        return (c, c)

    return default


def _resolve_leader_art(deck_name: str) -> str | None:
    """Try to find a leader artwork URL from a deck name like 'Purple Enel'."""
    if not deck_name:
        return None
    # Extract the character part (last word, or known multi-word)
    parts = deck_name.strip().split()
    # Try progressively: full name, last word, second-to-last + last
    candidates = [
        "_".join(parts),                        # full name
        parts[-1] if parts else "",             # last word
        "_".join(parts[-2:]) if len(parts) >= 2 else "",  # last two words
    ]
    for candidate in candidates:
        key = candidate.lower().replace(" ", "_")
        if key in _LEADER_NAME_MAP:
            filename = _LEADER_NAME_MAP[key] + ".webp"
            if (LEADER_ART_DIR / filename).is_file():
                return f"/static/leader_artwork/{filename}"
    # Fallback: try direct file match
    for candidate in candidates:
        filename = candidate.replace(" ", "_") + ".webp"
        if (LEADER_ART_DIR / filename).is_file():
            return f"/static/leader_artwork/{filename}"
    return None


@app.route("/card-image/<card_code>")
def card_image(card_code):
    """Serve a card image from the local assets directory."""
    try:
        # Match set prefix: "OP01", "ST13", "EB02", or bare letter prefix like "P"
        m = re.match(r"([A-Z]+\d*)", card_code, re.IGNORECASE)
        batch = m.group(1).upper() if m else card_code.upper()
        batch_dir = ASSETS_DIR / batch

        if not batch_dir.is_dir():
            abort(404)

        candidates = [
            f for f in batch_dir.iterdir()
            if f.is_file()
            and card_code.lower() in f.name.lower()
            and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            and "small" not in f.name.lower()
        ]

        if not candidates:
            abort(404)

        best = max(candidates, key=lambda f: f.stat().st_size)
        return send_file(str(best))
    except Exception:
        abort(404)


@app.route("/download-pdf/<int:idx>")
def download_pdf(idx):
    """Generate and download a print-ready PDF for a deck."""
    data = load_data()
    if not data or idx >= len(data.get("decks", [])):
        abort(404)

    deck = data["decks"][idx]
    deck_name = deck.get("deck_name", "Deck")
    cards = deck.get("cards", [])

    if not cards:
        abort(400)

    processed = []
    for card in cards:
        try:
            img = load_card_image(card["card_code"])
            img = upscale_image(img, factor=3)
            processed.append((card["quantity"], img))
        except FileNotFoundError:
            continue

    if not processed:
        abort(500)

    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix=f"OPTCG_{deck_name}_",
    )
    create_pdf(processed, tmp.name)

    safe_name = re.sub(r'[<>:"/\\|?*]', "", deck_name).strip()
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f"OPTCG_{safe_name}.pdf",
        mimetype="application/pdf",
    )


# ---------------------------------------------------------------------------
# Deck Builder
# ---------------------------------------------------------------------------

_card_cache = None  # Cached on first request
_card_meta_cache = None  # Card metadata (color, cost, type)
_card_meta_mtime = 0  # Track file modification time for auto-reload


def _load_card_meta():
    """Load card metadata from card_db.json if it exists. Auto-reloads when file changes."""
    global _card_meta_cache, _card_meta_mtime

    db_path = DATA_DIR / "card_db.json"
    if db_path.is_file():
        mtime = db_path.stat().st_mtime
        if _card_meta_cache is not None and mtime == _card_meta_mtime:
            return _card_meta_cache
        with open(db_path, encoding="utf-8") as f:
            _card_meta_cache = json.load(f)
        _card_meta_mtime = mtime
        log.info("Card metadata loaded: %d cards", len(_card_meta_cache))
    else:
        if _card_meta_cache is None:
            _card_meta_cache = {}
            log.info("No card_db.json found — filters will be limited")
    return _card_meta_cache


# Display names for set folders (folder name -> display name)
SET_DISPLAY_NAMES = {
    "P": "Promo",
}


def _set_display(folder_name):
    """Return a user-friendly display name for a set folder."""
    return SET_DISPLAY_NAMES.get(folder_name, folder_name)


def _scan_cards():
    """Scan OPTCG CARD ASSETS and return list of available card codes by set."""
    global _card_cache
    if _card_cache is not None:
        return _card_cache

    cards = []
    if not ASSETS_DIR.is_dir():
        return cards

    for batch_dir in sorted(ASSETS_DIR.iterdir()):
        if not batch_dir.is_dir():
            continue
        batch = batch_dir.name
        display = _set_display(batch)
        seen = set()
        for f in sorted(batch_dir.iterdir()):
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            if "small" in f.name.lower():
                continue
            match = re.match(r"([A-Za-z]+\d*-\d+)", f.stem)
            if match:
                code = match.group(1).upper()
                if code not in seen:
                    seen.add(code)
                    cards.append({"code": code, "set": display})

    _card_cache = cards
    log.info("Card cache built: %d cards across %d sets",
             len(cards), len({c["set"] for c in cards}))
    return cards


@app.route("/builder")
def builder():
    """Deck builder page."""
    cards = _scan_cards()
    sets = sorted({c["set"] for c in cards})
    return render_template("builder.html", sets=sets)


@app.route("/library")
def library():
    """Deck library page (decks stored client-side in localStorage)."""
    return render_template("library.html")


@app.route("/api/cards")
def api_cards():
    """JSON list of available cards with metadata, optionally filtered by set."""
    cards = _scan_cards()
    meta = _load_card_meta()
    card_set = request.args.get("set")
    if card_set:
        cards = [c for c in cards if c["set"] == card_set]

    # Merge metadata into card list
    enriched = []
    for c in cards:
        entry = {"code": c["code"], "set": c["set"]}
        m = meta.get(c["code"], {})
        entry["name"] = m.get("name", c["code"])
        entry["color"] = m.get("color", "")
        entry["cost"] = m.get("cost")
        entry["type"] = m.get("type", "")
        enriched.append(entry)
    return jsonify(enriched)


@app.route("/api/card-meta")
def api_card_meta():
    """JSON card metadata summary (available colors, types, cost range)."""
    meta = _load_card_meta()
    colors = sorted({m["color"] for m in meta.values() if m.get("color")})
    types = sorted({m["type"] for m in meta.values() if m.get("type")})
    costs = [m["cost"] for m in meta.values() if m.get("cost") is not None]
    return jsonify({
        "colors": colors,
        "types": types,
        "cost_min": min(costs) if costs else 0,
        "cost_max": max(costs) if costs else 10,
        "total_cards": len(meta),
    })


@app.route("/build-pdf", methods=["POST"])
def build_pdf():
    """Generate a print-ready PDF from a custom deck list."""
    data = request.get_json()
    if not data:
        abort(400)

    cards = data.get("cards", [])
    deck_name = data.get("name", "Custom Deck")

    if not cards:
        abort(400)

    processed = []
    for card in cards:
        try:
            img = load_card_image(card["code"])
            img = upscale_image(img, factor=3)
            processed.append((card["qty"], img))
        except FileNotFoundError:
            continue

    if not processed:
        return jsonify({"error": "No card images found"}), 404

    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix="OPTCG_build_",
    )
    create_pdf(processed, tmp.name)

    safe_name = re.sub(r'[<>:"/\\|?*]', "", deck_name).strip() or "Deck"
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f"OPTCG_{safe_name}.pdf",
        mimetype="application/pdf",
    )


@app.route("/api/meta")
def api_meta():
    """JSON endpoint for meta statistics (used by the chart)."""
    data = load_data()
    meta = compute_meta(data)
    return jsonify(meta)


@app.route("/api/status")
def api_status():
    """JSON endpoint for scraper status."""
    return jsonify(_scraper_state)


@app.route("/refresh", methods=["POST"])
def manual_refresh():
    """Trigger an immediate scrape in a background thread."""
    if _scraper_state["status"] == "scraping":
        return jsonify({"message": "Scrape already in progress"}), 409

    threading.Thread(target=_run_scrape, daemon=True, name="opdex-manual").start()
    return redirect(url_for("index"))


@app.context_processor
def inject_globals():
    """Make scraper state and Supabase config available to all templates."""
    return {
        "scraper": _scraper_state,
        "scrape_interval_min": SCRAPE_INTERVAL // 60,
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    }


# ---------------------------------------------------------------------------
# Auth API routes
# ---------------------------------------------------------------------------

@app.route("/api/profile", methods=["GET"])
@require_auth
def api_profile_get():
    """Get the current user's profile."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    result = _sb.table("profiles").select("*").eq("id", g.user_id).single().execute()
    if result.data:
        return jsonify(result.data)
    return jsonify({"error": "Profile not found"}), 404


@app.route("/api/profile", methods=["PUT"])
@require_auth
def api_profile_update():
    """Update the current user's profile (avatar, username)."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    data = request.get_json()
    updates = {}
    if "avatar_leader_code" in data:
        updates["avatar_leader_code"] = data["avatar_leader_code"]
    if "username" in data:
        updates["username"] = data["username"]
    if not updates:
        return jsonify({"error": "Nothing to update"}), 400
    result = _sb.table("profiles").update(updates).eq("id", g.user_id).execute()
    return jsonify(result.data[0] if result.data else {})


@app.route("/api/leaders")
def api_leaders():
    """Return all Leader-type cards from the card database."""
    meta = _load_card_meta()
    leaders = [
        {"code": code, "name": info.get("name", code), "color": info.get("color", "")}
        for code, info in meta.items()
        if info.get("type") == "Leader"
    ]
    leaders.sort(key=lambda l: l["code"])
    return jsonify(leaders)


# ---------------------------------------------------------------------------
# Deck CRUD API routes
# ---------------------------------------------------------------------------

@app.route("/api/decks", methods=["GET"])
@require_auth
def api_list_decks():
    """List all decks for the current user."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    result = _sb.table("decks").select("*").eq("user_id", g.user_id).order(
        "updated_at", desc=True,
    ).execute()
    return jsonify(result.data or [])


@app.route("/api/decks", methods=["POST"])
@require_auth
def api_create_deck():
    """Create a new deck for the current user."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    data = request.get_json()
    if not data or not data.get("cards"):
        return jsonify({"error": "Missing cards"}), 400

    cards = data["cards"]
    deck_row = {
        "user_id": g.user_id,
        "name": data.get("name", "Custom Deck"),
        "cards": cards,
        "total_cards": sum(c.get("qty", 1) for c in cards),
        "unique_cards": len(cards),
        "leader_code": cards[0]["code"] if cards else None,
        "is_public": data.get("is_public", False),
    }
    result = _sb.table("decks").insert(deck_row).execute()
    return jsonify(result.data[0] if result.data else {}), 201


@app.route("/api/decks/<deck_id>", methods=["PUT"])
@require_auth
def api_update_deck(deck_id):
    """Update an existing deck (must be owned by the user)."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    data = request.get_json()
    updates = {}
    if "name" in data:
        updates["name"] = data["name"]
    if "cards" in data:
        cards = data["cards"]
        updates["cards"] = cards
        updates["total_cards"] = sum(c.get("qty", 1) for c in cards)
        updates["unique_cards"] = len(cards)
        updates["leader_code"] = cards[0]["code"] if cards else None
    if "is_public" in data:
        updates["is_public"] = data["is_public"]
    if not updates:
        return jsonify({"error": "Nothing to update"}), 400

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = _sb.table("decks").update(updates).eq("id", deck_id).eq(
        "user_id", g.user_id,
    ).execute()
    if not result.data:
        return jsonify({"error": "Deck not found"}), 404
    return jsonify(result.data[0])


@app.route("/api/decks/<deck_id>", methods=["DELETE"])
@require_auth
def api_delete_deck(deck_id):
    """Delete a deck (must be owned by the user)."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    _sb.table("decks").delete().eq("id", deck_id).eq("user_id", g.user_id).execute()
    return jsonify({"ok": True})


@app.route("/api/decks/import", methods=["POST"])
@require_auth
def api_import_decks():
    """Batch import decks from localStorage."""
    if not _sb:
        return jsonify({"error": "Supabase not configured"}), 503
    data = request.get_json()
    decks = data.get("decks", [])
    if not decks:
        return jsonify({"error": "No decks to import"}), 400

    rows = []
    for d in decks:
        cards = d.get("cards", [])
        rows.append({
            "user_id": g.user_id,
            "name": d.get("name", "Imported Deck"),
            "cards": cards,
            "total_cards": d.get("totalCards", sum(c.get("qty", 1) for c in cards)),
            "unique_cards": d.get("uniqueCards", len(cards)),
            "leader_code": d.get("leaderCode", cards[0]["code"] if cards else None),
            "is_public": False,
        })

    result = _sb.table("decks").insert(rows).execute()
    return jsonify({"imported": len(result.data or [])})


# ---------------------------------------------------------------------------
# Shared decks
# ---------------------------------------------------------------------------

@app.route("/shared/<deck_id>")
def shared_deck(deck_id):
    """View a publicly shared deck."""
    if not _sb:
        abort(503)
    result = _sb.table("decks").select("*, profiles(username, avatar_leader_code)").eq(
        "id", deck_id,
    ).eq("is_public", True).single().execute()
    if not result.data:
        abort(404)
    deck = result.data
    # Resolve colors
    leader_code = deck.get("leader_code")
    leader_color = ""
    if leader_code:
        leader_color = _load_card_meta().get(leader_code, {}).get("color", "")
    deck_colors = _resolve_deck_colors(deck.get("name", ""), leader_color)
    return render_template("shared.html", deck=deck, deck_colors=deck_colors, leader_code=leader_code)


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------

@app.route("/admin")
def admin_page():
    """Admin dashboard page."""
    return render_template("admin.html")


@app.route("/api/admin/scrape", methods=["POST"])
@require_auth
@require_admin
def admin_trigger_scrape():
    """Trigger an immediate scrape (admin only)."""
    if _scraper_state["status"] == "scraping":
        return jsonify({"message": "Already scraping"}), 409
    threading.Thread(target=_run_scrape, daemon=True, name="opdex-admin").start()
    return jsonify({"message": "Scrape started"})


@app.route("/api/admin/stats")
@require_auth
@require_admin
def admin_stats():
    """Return admin statistics."""
    stats = {"scraper": _scraper_state}
    if _sb:
        try:
            users = _sb.table("profiles").select("id", count="exact").execute()
            decks = _sb.table("decks").select("id", count="exact").execute()
            stats["user_count"] = users.count
            stats["deck_count"] = decks.count
        except Exception:
            stats["user_count"] = "?"
            stats["deck_count"] = "?"
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Startup: ensure data dir exists and start scraper
# ---------------------------------------------------------------------------
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Avoid double-start in Flask's debug reloader (only start in child process)
_is_reloader_parent = app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
if not _is_reloader_parent:
    start_scraper()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
