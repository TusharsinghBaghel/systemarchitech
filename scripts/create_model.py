#!/usr/bin/env python3
"""Standalone helper to trigger backend model creation."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Call POST /model/build on the backend.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8010",
        help="Backend base URL (default: http://127.0.0.1:8010)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = f"{args.base_url.rstrip('/')}/model/build"

    request = urllib.request.Request(endpoint, method="POST")
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body) if body else {}
            print("Model build requested successfully.")
            print(json.dumps(data, indent=2))
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} while calling {endpoint}")
        if body:
            print(body)
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach backend at {endpoint}")
        print(f"Reason: {exc.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
