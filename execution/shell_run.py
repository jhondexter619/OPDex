"""Execute a shell command and return structured output."""

import argparse
import subprocess

from utils import output_json, setup_logging, timestamp

log = setup_logging("shell_run")


def run(command: str, timeout: int = 120, cwd: str | None = None) -> dict:
    """Run a shell command and capture output."""
    log.info("Running: %s", command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timestamp": timestamp(),
        }
    except subprocess.TimeoutExpired:
        log.error("Command timed out after %ds", timeout)
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "timestamp": timestamp(),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a shell command")
    parser.add_argument("command", help="Command to execute")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--cwd", default=None)
    args = parser.parse_args()

    result = run(args.command, args.timeout, args.cwd)
    output_json(result)
