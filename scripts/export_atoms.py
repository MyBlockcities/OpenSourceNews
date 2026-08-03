#!/usr/bin/env python3
"""Export atoms as a Hermes-ready JSONL.

Wraps `pipelines.atom_extraction.run` for direct invocation from
GitHub Actions or the CLI. Writes:

- outputs/atoms/{date}.jsonl   : per-day atom stream
- outputs/atoms/latest.jsonl   : symlink to most recent

Usage:
    python scripts/export_atoms.py --date 2026-08-03
    ATOMS_LLM=1 python scripts/export_atoms.py   # enable LLM extraction
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from pipelines.atom_extraction import run as run_atom_extraction  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export atoms for Hermes.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Deterministic extraction only (overrides ATOMS_LLM env).",
    )
    args = parser.parse_args()
    summary = run_atom_extraction(args.date, allow_llm=False if args.no_llm else None)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
