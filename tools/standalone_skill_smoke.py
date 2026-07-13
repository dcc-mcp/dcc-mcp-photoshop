"""Exercise the standalone executable as a Python skill subprocess."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", required=True)
    args = parser.parse_args()
    payload: dict[str, Any] = json.loads(sys.stdin.read() or "{}")
    if payload.get("message") != args.message:
        raise SystemExit("stdin and CLI parameters did not match")
    print(json.dumps({"success": True, "message": args.message}))


if __name__ == "__main__":
    main()
