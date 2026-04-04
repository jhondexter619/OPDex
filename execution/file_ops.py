"""File operations: read, write, copy, move, delete, list."""

import argparse
import json
import shutil
from pathlib import Path

from utils import output_json, setup_logging, timestamp

log = setup_logging("file_ops")


def read_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"success": False, "error": f"File not found: {path}"}
    return {"success": True, "content": p.read_text(encoding="utf-8"), "size": p.stat().st_size}


def write_file(path: str, content: str) -> dict:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    log.info("Wrote %d bytes to %s", len(content), path)
    return {"success": True, "bytes_written": len(content), "path": str(p)}


def copy_file(path: str, destination: str) -> dict:
    src, dst = Path(path), Path(destination)
    if not src.exists():
        return {"success": False, "error": f"Source not found: {path}"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return {"success": True, "source": str(src), "destination": str(dst)}


def move_file(path: str, destination: str) -> dict:
    src, dst = Path(path), Path(destination)
    if not src.exists():
        return {"success": False, "error": f"Source not found: {path}"}
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"success": True, "source": str(src), "destination": str(dst)}


def delete_file(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"success": False, "error": f"Not found: {path}"}
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    log.info("Deleted %s", path)
    return {"success": True, "deleted": str(p)}


def list_dir(path: str) -> dict:
    p = Path(path)
    if not p.is_dir():
        return {"success": False, "error": f"Not a directory: {path}"}
    entries = []
    for item in sorted(p.iterdir()):
        entries.append({
            "name": item.name,
            "type": "dir" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })
    return {"success": True, "path": str(p), "entries": entries}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="File operations")
    parser.add_argument("operation", choices=["read", "write", "copy", "move", "delete", "list"])
    parser.add_argument("path", help="Target path")
    parser.add_argument("--content", help="Content for write operation")
    parser.add_argument("--destination", help="Destination for copy/move")
    args = parser.parse_args()

    ops = {
        "read": lambda: read_file(args.path),
        "write": lambda: write_file(args.path, args.content or ""),
        "copy": lambda: copy_file(args.path, args.destination or ""),
        "move": lambda: move_file(args.path, args.destination or ""),
        "delete": lambda: delete_file(args.path),
        "list": lambda: list_dir(args.path),
    }
    result = ops[args.operation]()
    result["timestamp"] = timestamp()
    output_json(result)
