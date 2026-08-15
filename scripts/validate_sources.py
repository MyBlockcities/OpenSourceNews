#!/usr/bin/env python3
"""Validate the typed source registry and optional feeds.yaml compatibility."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.source_registry import (  # noqa: E402
    SourceRegistryError,
    enabled_sources,
    load_policy,
    load_sources,
    registry_hash,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OpenSourceNews source registry.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable summary.",
    )
    args = parser.parse_args()
    try:
        policy = load_policy()
        sources = load_sources(policy=policy)
    except SourceRegistryError as exc:
        print(str(exc), file=sys.stderr)
        return 30
    enabled = enabled_sources(sources)
    by_tier: dict[str, int] = {}
    for source in sources:
        tier = str(source.get("tier") or "unknown")
        by_tier[tier] = by_tier.get(tier, 0) + 1
    summary = {
        "ok": True,
        "source_count": len(sources),
        "enabled_count": len(enabled),
        "disabled_count": len(sources) - len(enabled),
        "by_tier": by_tier,
        "registry_hash": registry_hash(sources),
        "schema": "source_registry_validation.v1",
    }
    print(json.dumps(summary, indent=2) if args.json else (
        f"OK: {summary['source_count']} sources "
        f"({summary['enabled_count']} enabled, {summary['disabled_count']} disabled) "
        f"hash={summary['registry_hash'][:19]}…"
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
