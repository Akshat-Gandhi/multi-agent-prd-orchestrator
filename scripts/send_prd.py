#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Send PRD text to PRD Planner API.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--domain", default=None, help="Optional domain, e.g. fintech")
    parser.add_argument("--prd-file", default=None, help="Path to a PRD text/markdown file")
    parser.add_argument("--prd-text", default=None, help="Inline PRD text")
    args = parser.parse_args()

    if not args.prd_file and not args.prd_text:
        raise SystemExit("Provide --prd-file or --prd-text")

    prd_text = args.prd_text
    if args.prd_file:
        prd_text = Path(args.prd_file).read_text(encoding="utf-8")

    payload = {"prd_text": prd_text, "domain": args.domain, "constraints": []}

    create = httpx.post(f"{args.api.rstrip('/')}/runs", json=payload, timeout=60)
    create.raise_for_status()
    run = create.json()
    run_id = run["run_id"]

    print("Run created:", run_id)
    print(json.dumps(run, indent=2))
    print("\nEvents:")
    events = httpx.get(f"{args.api.rstrip('/')}/runs/{run_id}/events", timeout=30)
    events.raise_for_status()
    print(json.dumps(events.json(), indent=2))


if __name__ == "__main__":
    main()
