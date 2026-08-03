"""Public-domain topic ontology and signal tagging.

The topic ontology in `config/topics.yaml` is the public vocabulary Hermes
reads before applying its private project mapping. Keep additions here
generic, evidence-based, and reviewable via PR.

Design rules
------------
- Topics are public-domain. No private venture names live here.
- Each topic has keywords (matched case-insensitively) and optional exclusions
  (matched anywhere in the text — the signal is *rejected* from that topic).
- Subtopics inherit parent keywords; a hit on a subtopic also tags the parent.
- The match is deterministic. No LLM. Reproducible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

# Path to the public topic ontology. Override via env in tests if needed.
DEFAULT_TOPICS_PATH = Path(__file__).resolve().parents[1] / "config" / "topics.yaml"


def _normalize_topic_entry(name: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one topic entry to a stable internal shape."""
    keywords = [str(k).strip().lower() for k in (raw.get("keywords") or []) if str(k).strip()]
    exclusions = [str(k).strip().lower() for k in (raw.get("exclusions") or []) if str(k).strip()]
    subtopics = [str(s).strip() for s in (raw.get("subtopics") or []) if str(s).strip()]
    parent = (raw.get("parent") or "").strip() or None
    return {
        "name": name.strip(),
        "parent": parent,
        "keywords": keywords,
        "exclusions": exclusions,
        "subtopics": subtopics,
        "description": (raw.get("description") or "").strip(),
    }


def load_topics(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load the topic ontology. Returns name -> normalized entry."""
    p = path or DEFAULT_TOPICS_PATH
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    topics_raw = raw.get("topics") or {}
    if not isinstance(topics_raw, dict):
        return {}
    return {name: _normalize_topic_entry(name, entry) for name, entry in topics_raw.items()}


_WSPACE_RE = re.compile(r"\s+")


def _signal_text(item: Dict[str, Any]) -> str:
    """Lowercased, whitespace-normalized text used for matching."""
    parts: List[str] = [
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("excerpt") or ""),
        str(item.get("main_topic") or ""),
        str(item.get("category") or ""),
        str(item.get("bucket") or ""),
    ]
    for key in (
        "key_insights",
        "key_lessons",
        "tools_mentioned",
        "frameworks_mentioned",
        "entities",
        "topics",
    ):
        v = item.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v if str(x).strip())
    return _WSPACE_RE.sub(" ", "\n".join(parts)).strip().lower()


def _keyword_hits(text: str, keyword: str) -> int:
    """Count word-boundary hits. Cheap and good enough for short keywords."""
    if not keyword:
        return 0
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return len(re.findall(pattern, text))


def _has_exclusion(text: str, exclusion: str) -> bool:
    return exclusion and re.search(re.escape(exclusion.lower()), text) is not None


def tag_item(
    item: Dict[str, Any],
    topics: Dict[str, Dict[str, Any]],
    *,
    min_hits: int = 1,
) -> List[str]:
    """Return a sorted list of public topic names that apply to this item.

    A topic applies if:
    - It has at least `min_hits` keyword matches in the signal text, AND
    - None of its exclusions match the signal text.

    Subtopic hits also tag the parent topic.

    Parameters
    ----------
    item : dict
        A normalized signal item.
    topics : dict
        Output of `load_topics()`.
    min_hits : int
        Minimum keyword hits for a topic to apply. Default 1.

    Returns
    -------
    list of topic names, deduplicated, parent-then-child order.
    """
    text = _signal_text(item)
    if not text:
        return []

    matched: Set[str] = set()
    for name, entry in topics.items():
        if any(_has_exclusion(text, exc) for exc in entry["exclusions"]):
            continue
        hits = sum(_keyword_hits(text, kw) for kw in entry["keywords"])
        if hits >= min_hits:
            matched.add(name)
            # Inherit parent if any.
            if entry["parent"] and entry["parent"] in topics:
                matched.add(entry["parent"])

    # Sort: parents first, then alphabetical for stable output.
    def sort_key(name: str) -> Tuple[int, str]:
        return (0 if topics[name]["parent"] is None else 1, name)

    return sorted(matched, key=sort_key)


def add_public_topics(
    item: Dict[str, Any],
    topics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return the item with `public_topics` set. Pure function."""
    topics = topics if topics is not None else load_topics()
    enriched = dict(item)
    enriched["public_topics"] = tag_item(item, topics)
    return enriched


def topic_frequency(
    items: List[Dict[str, Any]],
    topics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, int]:
    """Count tag occurrences across a list of items."""
    topics = topics if topics is not None else load_topics()
    counts: Dict[str, int] = {name: 0 for name in topics}
    for item in items:
        for name in tag_item(item, topics):
            counts[name] = counts.get(name, 0) + 1
    return counts


def topic_cooccurrence(
    items: List[Dict[str, Any]],
    topics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[Tuple[str, str], int]:
    """Count (topic_a, topic_b) co-occurrences across items. Symmetric."""
    topics = topics if topics is not None else load_topics()
    pairs: Dict[Tuple[str, str], int] = {}
    for item in items:
        tag_list = tag_item(item, topics)
        for i, a in enumerate(tag_list):
            for b in tag_list[i + 1 :]:
                key = tuple(sorted((a, b)))
                pairs[key] = pairs.get(key, 0) + 1
    return pairs


def export_topic_snapshot(
    items: List[Dict[str, Any]],
    *,
    previous_frequency: Optional[Dict[str, int]] = None,
    topics: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build the public `outputs/topics/{date}.json` snapshot.

    Includes:
    - frequency: tag counts in this run
    - cooccurrence: top 25 most-co-occurring topic pairs
    - rising / cooling: topics whose frequency changed most vs previous run
    """
    topics = topics if topics is not None else load_topics()
    freq = topic_frequency(items, topics)
    cooc = topic_cooccurrence(items, topics)
    top_pairs = sorted(cooc.items(), key=lambda kv: kv[1], reverse=True)[:25]

    rising: List[Dict[str, Any]] = []
    cooling: List[Dict[str, Any]] = []
    if previous_frequency:
        for name, count in freq.items():
            prev = previous_frequency.get(name, 0)
            delta = count - prev
            record = {"topic": name, "current": count, "previous": prev, "delta": delta}
            if delta > 0:
                rising.append(record)
            elif delta < 0:
                cooling.append(record)
        rising.sort(key=lambda r: r["delta"], reverse=True)
        cooling.sort(key=lambda r: r["delta"])

    return {
        "frequency": freq,
        "cooccurrence": [{"topics": list(k), "count": v} for k, v in top_pairs],
        "rising": rising[:15],
        "cooling": cooling[:15],
        "topic_count": len(topics),
        "schema_version": "topics.v1",
    }


# Note: We define a small local text-normalization helper to keep this
# module self-contained while matching the repo's whitespace handling.
