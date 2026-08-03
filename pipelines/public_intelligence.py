#!/usr/bin/env python3
"""Back-compat orchestrator: atoms + sidecars + embedding-ready.

Prefer:
  python scripts/export_atoms.py
  python scripts/export_embedding_ready.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from pipelines.atom_extraction import run as run_atoms
from scripts.export_embedding_ready import run as run_embed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--skip-pages", action="store_true", help="ignored (compat)")
    args = parser.parse_args()
    atoms = run_atoms(args.date, allow_llm=False if args.no_llm else None)
    print(json.dumps({"atoms": atoms}, indent=2, ensure_ascii=False))
    if not atoms.get("ok"):
        raise SystemExit(1)
    embed = run_embed(args.date or atoms.get("report_date"))
    print(json.dumps({"embedding_ready": embed}, indent=2, ensure_ascii=False))
    raise SystemExit(0 if embed.get("ok") else 1)


if __name__ == "__main__":
    main()
