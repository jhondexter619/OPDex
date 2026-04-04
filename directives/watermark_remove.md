# Directive: OPTCG Watermark Removal

## Goal
Remove SAMPLE (English) and 見本 (Japanese) watermarks from One Piece TCG card images using mathematical alpha reversal.

## Inputs
- `input_path` (required): Path to a single card image or directory of cards
- `output_path` (optional): Where to save the cleaned image(s). Defaults to `<input>_clean.<ext>` for single files or `<input_dir>_clean/` for directories
- `strength` (optional): Removal strength multiplier. Default `1.0`. Use `1.5` for stubborn watermarks on bright/high-contrast cards

## Execution

### Single card
```bash
python -m execution.watermark_remove remove <input_path> [--output <output_path>] [--strength 1.0]
```

### Batch (directory)
```bash
python -m execution.watermark_remove batch <input_dir> [--output-dir <output_dir>] [--strength 1.0]
```

### Recalibrate masks (only if watermark format changes)
```bash
python -m execution.watermark_remove calibrate "OPTCG CARD ASSETS"
```

Script: `execution/watermark_remove.py`

## How It Works
1. **Pre-computed region masks** (in `execution/assets/`) identify where the SAMPLE watermark typically appears, derived from median analysis across 500+ cards
2. **Per-card adaptive detection** uses multi-scale median filtering (31px, 51px, 81px kernels) to estimate the local background, then computes per-pixel watermark alpha from brightness excess and saturation deficit
3. **Alpha reversal** mathematically reverses the white overlay: `original = (pixel - 255 × alpha) / (1 - alpha)`
4. **Two-pass processing**: first pass removes bulk watermark, second pass catches residuals with boosted sensitivity

## Outputs
- Cleaned card image(s) in the same format as input (JPEG at quality 95, PNG with compression 3)
- JSON status to stdout with processed count, errors, and output path

## Edge Cases & Errors
- **Bright artwork (skin tones, white backgrounds)**: The watermark signal can be very small (~16px) compared to artwork variation (~60px std). Use `--strength 1.5` for better results
- **Non-standard card dimensions**: The region mask is computed for 670×480 and 671×480 cards. Other sizes are handled via resizing, but quality may vary
- **Don cards**: No watermark present — skip these (they are in the `Don/` subfolder)
- **_small thumbnails**: Skipped by default in batch mode (120×167 low-res variants)
- **Missing region masks**: Run `calibrate` first if `execution/assets/` is empty

## Learnings
- The SAMPLE watermark is a semi-transparent white text overlay (~25-40% opacity depending on letter position)
- Cards exist in two main heights: 670px (newer sets OP10+, EB04+) and 671px (older sets OP01-OP09, EB01-EB03)
- The watermark position is consistent within a height group but shifts ~1-2px between groups — separate masks needed
- On dark backgrounds, saturation-based detection is unreliable — brightness-only detection is used instead
- Leader cards have a different layout (no counter bar) but the watermark is in the same position
- The median-derived region mask is most accurate in the lower half of the artwork; the upper portion (where Japanese 見本 appears) is noisier
- Some cards with very bright, detailed artwork (e.g., skin tones against red backgrounds) are challenging — the two-pass approach helps but may not fully eliminate all traces
