# Directive: Python Script

## Goal
Run a Python execution script with defined inputs and capture its output.

## Inputs
- `script` (required): Path to script relative to `execution/`, e.g. `scrape_website.py`
- `args` (optional): List of CLI arguments to pass
- `env_vars` (optional): Additional environment variables beyond `.env`

## Execution
1. Script: `execution/shell_run.py` wrapping `python execution/<script>`
2. `.env` is loaded automatically by execution scripts via `dotenv`
3. Pass any extra args as CLI arguments

## Outputs
- Script stdout (usually JSON or structured text)
- Script stderr (logs/errors)
- Exit code

## Edge Cases & Errors
- Missing dependencies: run `pip install -r requirements.txt`
- Script not found: check `execution/` directory listing
- If script uses paid APIs, confirm with user before running

## Learnings
