# Directive: OPTCG Deck PDF Generator

## Goal
Given a decklist URL, load card images from local assets, upscale 3×, and produce a print-ready A4 PDF with cards at 3.48 in × 2.49 in.

## Inputs
- `url` (required): URL containing a decklist in `QuantityxCARDBATCH-NUMBER` format (e.g. `4xOP14-083`)
- `deck_name` (optional): Override the auto-detected deck name

## Asset Folder Structure
```
OPTCG CARD ASSETS/
├── OP05/
│   ├── OP05-094.png
│   └── …
├── OP14/
│   ├── OP14-083.png
│   └── …
├── OP15/
│   └── …
```
- Folder per card batch (e.g. `OP14`, `OP15`)
- Image filename must contain the card code (e.g. `OP14-083`)
- The script picks the largest non-"small" image file matching each card code

## Execution
1. Script: `execution/optcg_deck_pdf.py`
2. Run: `python execution/optcg_deck_pdf.py <url> [--deck-name "Name"]`
3. Sequence:
   a. Parse the URL — first tries query params (`dg=` from onepiecetopdecks), falls back to scraping for `NxCODE` patterns
   b. For each card code, load the image from `OPTCG CARD ASSETS/<batch>/`
   c. Upscale 3× using Lanczos resampling
   d. Assemble a multi-page A4 PDF (3×3 grid, cards centered) — each card repeated per its quantity

## Outputs
- Folder: `OPTCG Decks/` in working directory (single folder for all decks)
- `OPTCG_<DeckName>_<date>.pdf` — print-ready A4 PDF

## Edge Cases & Errors
- **Missing asset folder**: script raises `FileNotFoundError` with the expected path — add the batch folder and images
- **Card image not found**: check filename contains the exact card code (e.g. `OP14-083`)
- **"small" images skipped**: any file with "small" in its name is excluded; the largest matching file is used
- **No cards parsed**: regex may need adjustment for the source site format

## Learnings
- PDF includes cutting guides: L-shaped corner crop marks, side crop marks at interior grid boundaries, and small dots at interior intersections — all 0.5mm from card edges
