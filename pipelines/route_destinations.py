"""
Destination routing for normalized daily items.

Routes each item to "academy", "godseye", or "both" using rules in
config/destinations.yaml: bucket match first, then keyword scoring over
title + summary + category + tags. Pure Python — deterministic and free.

Usage:
    from pipelines.route_destinations import route_normalized
    routed = route_normalized(normalized)        # tags item["destination"]
    academy_items = [i for i in routed["items"] if i["destination"] in ("academy", "both")]
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "destinations.yaml"

VALID_DESTINATIONS = ("academy", "godseye", "both")


@lru_cache(maxsize=1)
def _load_config(path: str = str(CONFIG_PATH)) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    for dest in ("academy", "godseye"):
        cfg.setdefault(dest, {})
        cfg[dest].setdefault("buckets", [])
        cfg[dest].setdefault("include_keywords", [])
    cfg.setdefault("both_if_overlap", True)
    cfg.setdefault("default", "academy")
    return cfg


def _item_text(item: Dict[str, Any]) -> str:
    """Build a lowercase haystack from the fields that signal topic."""
    parts: List[str] = []
    for key in ("title", "summary", "category", "neutral_synthesis", "main_topic"):
        val = item.get(key)
        if isinstance(val, str):
            parts.append(val)
    for key in ("tools_mentioned", "frameworks_mentioned", "entities", "key_lessons", "key_insights"):
        val = item.get(key)
        if isinstance(val, list):
            parts.extend(str(v) for v in val)
    # Pad with spaces so word-boundary keywords like " ai " match at string edges.
    return " " + " ".join(parts).lower() + " "


def _keyword_score(text: str, keywords: List[str]) -> int:
    return sum(1 for kw in keywords if kw.lower() in text)


def route_item(item: Dict[str, Any], config: Dict[str, Any] | None = None) -> str:
    """Return "academy" | "godseye" | "both" for a single normalized item."""
    cfg = config or _load_config()
    bucket = (item.get("bucket") or "").strip().lower()
    text = _item_text(item)

    academy_hit = bucket in [b.lower() for b in cfg["academy"]["buckets"]]
    godseye_hit = bucket in [b.lower() for b in cfg["godseye"]["buckets"]]

    academy_kw = _keyword_score(text, cfg["academy"]["include_keywords"])
    godseye_kw = _keyword_score(text, cfg["godseye"]["include_keywords"])

    # Bucket gives a strong prior; keywords can add the second destination or
    # decide when the bucket is neutral (e.g. "general").
    academy_signal = (2 if academy_hit else 0) + academy_kw
    godseye_signal = (2 if godseye_hit else 0) + godseye_kw

    if academy_signal > 0 and godseye_signal > 0:
        if cfg["both_if_overlap"] and min(academy_signal, godseye_signal) >= 2:
            return "both"
        return "academy" if academy_signal >= godseye_signal else "godseye"
    if academy_signal > 0:
        return "academy"
    if godseye_signal > 0:
        return "godseye"
    default = str(cfg["default"]).strip().lower()
    return default if default in VALID_DESTINATIONS else "academy"


def route_normalized(normalized: Dict[str, Any], config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Return a copy of a normalized report with item["destination"] set on every
    item and a counts.by_destination summary added.
    """
    cfg = config or _load_config()
    out = copy.deepcopy(normalized)
    by_destination: Dict[str, int] = {"academy": 0, "godseye": 0, "both": 0}
    for item in out.get("items") or []:
        dest = route_item(item, cfg)
        item["destination"] = dest
        by_destination[dest] = by_destination.get(dest, 0) + 1
    out.setdefault("counts", {})["by_destination"] = by_destination
    return out


def filter_for_destination(normalized: Dict[str, Any], destination: str) -> Dict[str, Any]:
    """
    Return a copy of a routed normalized report containing only the items bound
    for `destination` (items routed "both" are included for either).
    """
    if destination not in ("academy", "godseye"):
        raise ValueError(f"destination must be academy|godseye, got {destination!r}")
    out = copy.deepcopy(normalized)
    items = [
        i for i in out.get("items") or []
        if i.get("destination") in (destination, "both")
    ]
    out["items"] = items
    counts = out.setdefault("counts", {})
    counts["total"] = len(items)
    out["digest"] = f"{len(items)} items routed to {destination}."
    return out
