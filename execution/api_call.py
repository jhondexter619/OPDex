"""Make HTTP API calls with retry logic."""

import argparse
import json
import time

import requests

from utils import env, output_json, setup_logging, timestamp

log = setup_logging("api_call")

MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


def call(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    auth_env_var: str | None = None,
    timeout: int = 30,
) -> dict:
    """Make an HTTP request with retry on rate limits."""
    headers = headers or {}

    if auth_env_var:
        token = env(auth_env_var)
        headers.setdefault("Authorization", f"Bearer {token}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("Attempt %d: %s %s", attempt, method, url)
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=body,
                timeout=timeout,
            )

            # Parse body
            try:
                resp_body = response.json()
            except (json.JSONDecodeError, ValueError):
                resp_body = response.text

            result = {
                "success": response.ok,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": resp_body,
                "timestamp": timestamp(),
            }

            if response.status_code == 429 and attempt < MAX_RETRIES:
                wait = BACKOFF_BASE**attempt
                log.warning("Rate limited. Waiting %ds before retry.", wait)
                time.sleep(wait)
                continue

            return result

        except requests.Timeout:
            log.error("Request timed out after %ds", timeout)
            return {
                "success": False,
                "status_code": None,
                "error": f"Timeout after {timeout}s",
                "timestamp": timestamp(),
            }
        except requests.RequestException as e:
            log.error("Request failed: %s", e)
            return {
                "success": False,
                "status_code": None,
                "error": str(e),
                "timestamp": timestamp(),
            }

    return result  # Last attempt result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make an API call")
    parser.add_argument("url", help="Request URL")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--headers", type=json.loads, default=None)
    parser.add_argument("--body", type=json.loads, default=None)
    parser.add_argument("--auth-env-var", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    result = call(args.url, args.method, args.headers, args.body, args.auth_env_var, args.timeout)
    output_json(result)
