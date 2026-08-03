"""Tutorial-candidate flags on signals (public heuristics)."""

from __future__ import annotations

import re
from typing import Any, Dict, List

_HOWTO_RE = re.compile(
    r"\b(how to|tutorial|guide|walkthrough|step[- ]by[- ]step|build a|getting started|intro to)\b",
    re.I,
)
_DEEP_RE = re.compile(r"\b(deep dive|architecture|internals|from scratch|advanced)\b", re.I)
_BEGINNER_RE = re.compile(r"\b(beginner|intro|101|for beginners|basics|explained)\b", re.I)


def flag_tutorial_potential(item: Dict[str, Any]) -> Dict[str, Any]:
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or item.get("excerpt") or "")
    blob = f"{title}\n{summary}"

    potential = 0.0
    if _HOWTO_RE.search(blob):
        potential += 0.55
    if _DEEP_RE.search(blob):
        potential += 0.25
    if "youtube" in str(item.get("source") or "").lower():
        potential += 0.1
    if any(t in (item.get("public_topics") or []) for t in ("ai_agents", "open_source_dev", "ai_models")):
        potential += 0.15
    potential = max(0.0, min(1.0, potential))

    if _BEGINNER_RE.search(blob):
        audience = "beginner"
        complexity = "low"
    elif _DEEP_RE.search(blob):
        audience = "practitioner"
        complexity = "high"
    elif potential >= 0.4:
        audience = "intermediate"
        complexity = "medium"
    else:
        audience = "general"
        complexity = "unknown"

    return {
        "tutorial_potential": round(potential, 3),
        "tutorial_complexity": complexity,
        "tutorial_audience": audience,
        "tutorial_candidate": potential >= 0.45,
    }


def apply_tutorial_flags(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        flagged = dict(item)
        flagged.update(flag_tutorial_potential(flagged))
        out.append(flagged)
    return out
