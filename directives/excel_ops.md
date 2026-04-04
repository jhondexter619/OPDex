# Directive: Excel Operations

## Goal
Create, write, append, and read Excel (.xlsx) files with formatted headers and auto-sized columns.

## Inputs
- `operation` (required): One of `create`, `append`, `read`
- `file_path` (required): Path to the .xlsx file
- `sheets` (optional, create only): JSON dict of `{sheet_name: [[row1], [row2], ...]}` — first row is treated as header
- `rows` (required for append): JSON array of arrays
- `sheet` (optional): Target sheet name, default "Sheet1"

## Execution
1. Script: `execution/excel_ops.py`
2. No API keys required — works fully offline.
3. Commands:
   - Create with data: `python execution/excel_ops.py create "LEADS/file.xlsx" --sheets '{"Sheet1": [["H1","H2"],["A","B"]]}'`
   - Append rows: `python execution/excel_ops.py append "LEADS/file.xlsx" --rows '[["A","B"]]' --sheet "Sheet1"`
   - Read: `python execution/excel_ops.py read "LEADS/file.xlsx" --sheet "Sheet1"`

## Outputs
- `success`: boolean
- `file_path`: absolute path to the file
- `sheets`: list of sheet names (create) or dict of sheet data (read)

## Edge Cases & Errors
- **File not found (append/read)**: Raises FileNotFoundError. Create the file first.
- **Parent directory missing**: `create` auto-creates parent directories.
- **Column width**: Capped at 50 characters to prevent absurdly wide columns.
- **Large files**: For files >50k rows, consider chunking appends.

## Learnings
<!-- Append discoveries here as you encounter them -->
