# Directive: File Operations

## Goal
Read, write, move, copy, or delete files and directories.

## Inputs
- `operation` (required): One of `read`, `write`, `copy`, `move`, `delete`, `list`
- `path` (required): Target file or directory path
- `content` (optional): Content to write (for `write` operation)
- `destination` (optional): Destination path (for `copy`/`move`)

## Execution
1. Script: `execution/file_ops.py`
2. Pass operation and paths as arguments
3. Script handles encoding, permissions, and path validation

## Outputs
- `read`: File contents as string
- `write`: Confirmation with bytes written
- `copy`/`move`: Confirmation with source and destination
- `delete`: Confirmation of removal
- `list`: Directory listing as JSON array

## Edge Cases & Errors
- Path not found: return clear error, do not create directories silently
- Permission denied: report and suggest fix
- Delete operations: always require confirmation unless `--force` flag

## Learnings
