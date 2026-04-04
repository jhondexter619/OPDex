"""Build a print-ready PDF from local OPTCG card assets and a decklist URL."""

import argparse
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fpdf import FPDF
from PIL import Image

from utils import output_json, setup_logging, timestamp

log = setup_logging("optcg_deck_pdf")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).resolve().parent.parent / "OPTCG CARD ASSETS"

CARD_WIDTH_IN = 2.49
CARD_HEIGHT_IN = 3.48
MM_PER_INCH = 25.4
CARD_WIDTH_MM = CARD_WIDTH_IN * MM_PER_INCH
CARD_HEIGHT_MM = CARD_HEIGHT_IN * MM_PER_INCH

A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297

COLS = int(A4_WIDTH_MM // CARD_WIDTH_MM)   # 3
ROWS = int(A4_HEIGHT_MM // CARD_HEIGHT_MM)  # 3
CARDS_PER_PAGE = COLS * ROWS                # 9


# ---------------------------------------------------------------------------
# Step 1: Parse decklist from URL
# ---------------------------------------------------------------------------

def _parse_url_params(url: str) -> tuple[list[tuple[int, str]], str] | None:
    """Extract decklist from URL query parameters (onepiecetopdecks.com deckgen).

    ``dn`` = deck name, ``dg`` = encoded list: ``{qty}n{code}a…``
    """
    qs = parse_qs(urlparse(url).query)

    dg = qs.get("dg", [None])[0]
    if not dg:
        return None

    deck_name = qs.get("dn", ["Deck"])[0]
    deck_name = re.sub(r'[<>:"/\\|?*]', "", deck_name).strip()[:50]

    matches = re.findall(r"(\d+)n([A-Z]{1,5}\d{1,3}-\d{1,3})", dg, re.IGNORECASE)
    if not matches:
        return None

    cards = [(int(qty), code.upper()) for qty, code in matches]
    log.info("Parsed %d unique cards (%d total) from URL params", len(cards), sum(q for q, _ in cards))
    return cards, deck_name


def parse_decklist(url: str) -> tuple[list[tuple[int, str]], str]:
    """Return [(quantity, card_code), …] and deck name from a decklist URL."""
    log.info("Decklist URL: %s", url)

    # Strategy 1: URL query parameters
    result = _parse_url_params(url)
    if result:
        return result

    # Strategy 2: scrape the page for QuantityxCode patterns
    import requests
    from bs4 import BeautifulSoup

    log.info("URL params empty — scraping page")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    deck_name = "Deck"
    title_el = soup.find("h1") or soup.find("title")
    if title_el:
        deck_name = re.sub(r'[<>:"/\\|?*]', "", title_el.get_text(strip=True)).strip()[:50]

    text = soup.get_text()

    # 4xOP14-083
    matches = re.findall(r"(\d+)\s*x\s*([A-Z]{1,5}\d{1,3}-\d{1,3})", text, re.IGNORECASE)
    if not matches:
        # 4 OP14-083
        matches = re.findall(r"(\d+)\s+([A-Z]{1,5}\d{1,3}-\d{1,3})", text, re.IGNORECASE)

    cards = [(int(qty), code.upper()) for qty, code in matches]
    log.info("Found %d unique cards (%d total)", len(cards), sum(q for q, _ in cards))
    return cards, deck_name


# ---------------------------------------------------------------------------
# Step 2: Load card image from local assets
# ---------------------------------------------------------------------------

def load_card_image(card_code: str) -> Image.Image:
    """Find and open the card image from OPTCG CARD ASSETS/<batch>/.

    Picks the largest (non-"small") image file whose name contains the card code.
    """
    batch = re.match(r"([A-Z]+\d+)", card_code, re.IGNORECASE).group(1).upper()
    batch_dir = ASSETS_DIR / batch

    if not batch_dir.is_dir():
        raise FileNotFoundError(f"Asset folder not found: {batch_dir}")

    # Find files whose name contains the card code (case-insensitive)
    candidates = [
        f for f in batch_dir.iterdir()
        if f.is_file()
        and card_code.lower() in f.name.lower()
        and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
        and "small" not in f.name.lower()
    ]

    if not candidates:
        raise FileNotFoundError(f"No image found for {card_code} in {batch_dir}")

    # Prefer the largest file (regular size, not thumbnail)
    best = max(candidates, key=lambda f: f.stat().st_size)
    log.info("  Loaded %s (%d KB)", best.name, best.stat().st_size // 1024)
    return Image.open(best).convert("RGB")


# ---------------------------------------------------------------------------
# Step 3: Upscale
# ---------------------------------------------------------------------------

def upscale_image(image: Image.Image, factor: int = 3) -> Image.Image:
    """Upscale image by *factor* using Lanczos resampling."""
    new_size = (image.width * factor, image.height * factor)
    return image.resize(new_size, Image.LANCZOS)


# ---------------------------------------------------------------------------
# Step 4: Assemble PDF
# ---------------------------------------------------------------------------

CROP_MARK_LEN = 5      # mm length of each crop mark line
CROP_MARK_GAP = 0.5    # mm tiny gap between card edge and start of mark
GUIDE_DOT_RADIUS = 0.4 # mm radius of cutting guide dots


def _draw_cutting_guides(pdf: FPDF, margin_x: float, margin_y: float) -> None:
    """Draw crop marks and guide dots around the card grid.

    - L-shaped corner marks at all 4 corners
    - Side marks where interior grid lines extend past the grid edge
    - Small dots at every interior grid intersection
    """
    grid_w = COLS * CARD_WIDTH_MM
    grid_h = ROWS * CARD_HEIGHT_MM
    grid_top = margin_y
    grid_bottom = margin_y + grid_h
    grid_left = margin_x
    grid_right = margin_x + grid_w

    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.3)

    # --- Corner crop marks (L-shaped) ---
    corners = [
        (grid_left, grid_top, -1, -1),      # top-left
        (grid_right, grid_top, 1, -1),       # top-right
        (grid_left, grid_bottom, -1, 1),     # bottom-left
        (grid_right, grid_bottom, 1, 1),     # bottom-right
    ]
    for cx, cy, h_dir, v_dir in corners:
        h_start = cx + h_dir * CROP_MARK_GAP
        pdf.line(h_start, cy, h_start + h_dir * CROP_MARK_LEN, cy)
        v_start = cy + v_dir * CROP_MARK_GAP
        pdf.line(cx, v_start, cx, v_start + v_dir * CROP_MARK_LEN)

    # --- Side crop marks where interior cuts meet the grid edges ---
    # Interior column boundaries → marks above top edge and below bottom edge
    for c in range(1, COLS):
        x = grid_left + c * CARD_WIDTH_MM
        pdf.line(x, grid_top - CROP_MARK_GAP, x, grid_top - CROP_MARK_GAP - CROP_MARK_LEN)
        pdf.line(x, grid_bottom + CROP_MARK_GAP, x, grid_bottom + CROP_MARK_GAP + CROP_MARK_LEN)

    # Interior row boundaries → marks left of left edge and right of right edge
    for r in range(1, ROWS):
        y = grid_top + r * CARD_HEIGHT_MM
        pdf.line(grid_left - CROP_MARK_GAP, y, grid_left - CROP_MARK_GAP - CROP_MARK_LEN, y)
        pdf.line(grid_right + CROP_MARK_GAP, y, grid_right + CROP_MARK_GAP + CROP_MARK_LEN, y)

    # --- Guide dots at interior grid intersections ---
    pdf.set_fill_color(0, 0, 0)
    d = GUIDE_DOT_RADIUS * 2
    for c in range(1, COLS):
        for r in range(1, ROWS):
            x = grid_left + c * CARD_WIDTH_MM
            y = grid_top + r * CARD_HEIGHT_MM
            pdf.ellipse(x - GUIDE_DOT_RADIUS, y - GUIDE_DOT_RADIUS, d, d, style="F")


def create_pdf(cards: list[tuple[int, Image.Image]], output_path: str) -> str:
    """Create an A4 PDF with cards in a centered 3×3 grid and cutting guides."""
    pdf = FPDF(unit="mm", format="A4")

    margin_x = (A4_WIDTH_MM - COLS * CARD_WIDTH_MM) / 2
    margin_y = (A4_HEIGHT_MM - ROWS * CARD_HEIGHT_MM) / 2

    # Flatten by quantity
    all_images: list[Image.Image] = []
    for qty, img in cards:
        all_images.extend([img] * qty)

    log.info("Laying out %d card copies across %d pages",
             len(all_images), -(-len(all_images) // CARDS_PER_PAGE))

    tmp_dir = tempfile.mkdtemp(prefix="optcg_")

    try:
        for page_start in range(0, len(all_images), CARDS_PER_PAGE):
            pdf.add_page()
            for slot, img in enumerate(all_images[page_start:page_start + CARDS_PER_PAGE]):
                row, col = divmod(slot, COLS)
                x = margin_x + col * CARD_WIDTH_MM
                y = margin_y + row * CARD_HEIGHT_MM

                tmp_path = os.path.join(tmp_dir, f"card_{page_start + slot}.jpg")
                img.save(tmp_path, "JPEG", quality=95)
                pdf.image(tmp_path, x=x, y=y, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM)

            # Draw cutting guides on top of card images
            _draw_cutting_guides(pdf, margin_x, margin_y)

        pdf.output(output_path)
        log.info("PDF saved to %s", output_path)
    finally:
        for f in Path(tmp_dir).glob("*.jpg"):
            f.unlink()
        Path(tmp_dir).rmdir()

    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(url: str, deck_name: str | None = None) -> dict:
    """Full pipeline: parse decklist → load local assets → upscale → PDF."""
    try:
        # 1. Parse decklist
        cards, auto_name = parse_decklist(url)
        if not cards:
            return {"success": False, "error": "No cards found in decklist", "timestamp": timestamp()}

        deck_name = deck_name or auto_name
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = ASSETS_DIR.parent / "OPTCG Decks"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 2. Load from local assets and upscale
        processed: list[tuple[int, Image.Image]] = []
        for qty, code in cards:
            log.info("Processing %dx %s …", qty, code)

            img = load_card_image(code)
            img = upscale_image(img, factor=3)
            log.info("  Upscaled to %dx%d", img.width, img.height)

            processed.append((qty, img))

        # 3. Build PDF
        pdf_name = f"OPTCG_{deck_name}_{date_str}.pdf"
        pdf_path = str(output_dir / pdf_name)
        create_pdf(processed, pdf_path)

        total = sum(q for q, _ in cards)
        return {
            "success": True,
            "deck_name": deck_name,
            "unique_cards": len(cards),
            "total_cards": total,
            "output_dir": str(output_dir),
            "pdf_path": pdf_path,
            "timestamp": timestamp(),
        }

    except Exception as e:
        log.exception("Pipeline failed")
        return {"success": False, "error": str(e), "timestamp": timestamp()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OPTCG Deck PDF Generator")
    parser.add_argument("url", help="URL containing the decklist")
    parser.add_argument("--deck-name", default=None, help="Override auto-detected deck name")
    args = parser.parse_args()

    result = run(args.url, args.deck_name)
    output_json(result)
