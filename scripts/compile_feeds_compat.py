#!/usr/bin/env python3
"""Compile config/feeds.yaml from the typed source registry."""

from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.source_registry import enabled_sources, load_sources  # noqa: E402

FEEDS_PATH = ROOT_DIR / "config" / "feeds.yaml"

TOPIC_ORDER = [
    "General News & Research",
    "AI / AI Tools / AI Agents",
    "Blockchain / Crypto / Web3",
    "Sense-Making & Narrative Analysis",
    "Alternative News & Independent Commentary",
    "Peptides / Wellness / Longevity",
    "Official Records & Primary Sources",
    "Investigative Documents & Public Records",
]

FEEDS_KEYS = (
    "github_sources",
    "hackernews_sources",
    "rss_sources",
    "youtube_sources",
    "pubmed_sources",
    "clinical_trials_sources",
    "x_sources",
)


def compile_topics(sources=None):
    sources = sources if sources is not None else load_sources()
    grouped: OrderedDict[str, dict] = OrderedDict((name, {}) for name in TOPIC_ORDER)
    for source in enabled_sources(sources):
        topic = source.get("feeds_topic")
        key = source.get("feeds_key")
        if not topic or not key:
            continue
        if key not in FEEDS_KEYS:
            continue
        bucket = grouped.setdefault(topic, {})
        values = bucket.setdefault(key, [])
        for endpoint in source.get("endpoints") or []:
            if endpoint not in values:
                values.append(endpoint)
    topics = []
    for name, keys in grouped.items():
        if not keys:
            continue
        row = {"topic_name": name}
        row.update(keys)
        topics.append(row)
    return {"topics": topics}


def render_yaml(payload: dict) -> str:
    header = (
        "# GENERATED FILE. Edit config/sources/*.yaml and run\n"
        "#   python scripts/compile_feeds_compat.py --write\n"
        "# Compatibility export for pipelines/daily_run.py.\n"
        "# Policy, tiers, and disabled sources live in the typed registry.\n\n"
    )
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    return header + body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Overwrite config/feeds.yaml")
    parser.add_argument("--check", action="store_true", help="Exit 1 if feeds.yaml is stale")
    args = parser.parse_args()
    payload = compile_topics()
    rendered = render_yaml(payload)
    if args.check:
        current = FEEDS_PATH.read_text(encoding="utf-8") if FEEDS_PATH.exists() else ""
        if current != rendered:
            print("config/feeds.yaml is out of date with the source registry.", file=sys.stderr)
            return 1
        print("feeds.yaml matches the source registry.")
        return 0
    if args.write:
        FEEDS_PATH.write_text(rendered, encoding="utf-8")
        print(f"Wrote {FEEDS_PATH}")
        return 0
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
