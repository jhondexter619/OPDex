# Directive: OPTCG Watermark Removal (PixelBin)

## Goal
Remove SAMPLE watermarks from One Piece TCG card images using PixelBin's AI watermark remover, then file the cleaned card into the correct `OPTCG CARD ASSETS/<batch>/` folder.

## Inputs
- `input_path` (required): Path to a watermarked card image (JPG, PNG, WEBP, HEIC)
- `card_code` (optional): Card code like `OP14-083`. If not provided, attempt to parse from filename. If unparseable, ask the user.

## Execution

Script: `execution/watermark_remove_pixelbin.py`

### Step-by-step flow

1. **Parse the card code** from the filename (or ask the user):
   ```bash
   python -m execution.watermark_remove_pixelbin parse "<filename>"
   ```
   This returns `{"batch": "OP14", "code": "OP14-083"}` or `null` values if unparseable.

2. **Remove the watermark** via PixelBin:
   ```bash
   python -m execution.watermark_remove_pixelbin remove "<input_path>" [--output "<output_path>"]
   ```
   - Opens a visible browser window, uploads the image, waits for AI processing, downloads result.
   - Default output: `<input>_clean.<ext>` next to the original.

3. **Check for existing card** at `OPTCG CARD ASSETS/<batch>/<code>.png`:
   - If **no existing file**: show the cleaned image to the user and ask: *"Save this as `<code>.png` in `OPTCG CARD ASSETS/<batch>/`?"*
   - If **file already exists**: create a side-by-side comparison and ask the user to confirm overwrite:
     ```bash
     python -m execution.watermark_remove_pixelbin compare "<existing_path>" "<new_path>" --out "<temp_comparison_path>"
     ```
     Then show the comparison image and ask: *"This card already exists. Replace it? (showing existing vs new)"*

4. **Place the card** (only after user confirmation):
   - Copy the cleaned image to `OPTCG CARD ASSETS/<batch>/<code>.png`
   - Create the batch subfolder if it doesn't exist

## Outputs
- Cleaned card image saved to `OPTCG CARD ASSETS/<batch>/<code>.png`
- Temporary files (`_clean`, comparison) can be deleted after placement

## Edge Cases & Errors
- **Captcha**: PixelBin may show a captcha — the browser is visible so the user can solve it manually
- **Processing timeout**: The script waits up to 2 minutes for processing. If it times out, suggest the user try manually at the URL
- **Unknown card code**: If the filename doesn't match any known pattern (OP/ST/EB/PRB/P), ask the user for the card code and batch
- **Don cards**: Don cards have no watermark. Skip if user tries to process one.
- **Browser not installed**: Run `playwright install chromium` if Playwright browsers are missing
- **Page layout changes**: If PixelBin changes their UI, the download selectors may need updating in the script

## Learnings
<!-- Append discoveries here as you encounter them -->
