# Directive: Shell Run

## Goal
Execute shell commands on the host system.

## Inputs
- `command` (required): The shell command to execute
- `timeout` (optional): Max seconds to wait, default 120
- `cwd` (optional): Working directory, default project root

## Execution
1. Script: `execution/shell_run.py`
2. Pass `command`, `timeout`, and `cwd` as arguments
3. Script captures stdout, stderr, and return code

## Outputs
- `stdout`: Command standard output
- `stderr`: Command error output
- `returncode`: Exit code (0 = success)

## Edge Cases & Errors
- Non-zero exit code: log stderr, report failure
- Timeout: kill process, report timeout error
- Never run destructive commands without user confirmation

## Learnings
