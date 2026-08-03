"""Public entity registry and trajectory tracking.

Entities are people, companies, projects, and tools mentioned across signals.
The registry accumulates mention history and surfaces trajectory
(rising / cooling / stable). Hermes consumes this to map news to the
user's active memory banks.

Output
------
- outputs/entities/{date}.json         : daily snapshot of all known entities
- outputs/entity_pages/{entity_id}.json: per-entity detail page

Entity ID
---------
Stable: uuid5 over (namespace, lowercase-entity-name). Same name always
maps to the same ID; this lets us merge aliases if needed.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from services.news_schema import utc_now_iso
from services.atom_schema import make_atom_id

# Stable namespace for entity IDs.
_ENTITY_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews#entity"
)

# Path conventions (mirrors outputs/ in the repo).
DEFAULT_ENTITIES_DIR = Path(__file__).resolve().parents[1] / "outputs" / "entities"
DEFAULT_ENTITY_PAGES_DIR = Path(__file__).resolve().parents[1] / "outputs" / "entity_pages"

# Do not publish per-entity detail pages for these public-repo denylist slugs.
# Names can still appear in aggregate entity snapshots derived from collected signals.
ENTITY_PAGE_DENY_SLUGS = frozenset(
    {
        "alex_jones",
        "candace_owens",
        "tucker_carlson",
        "powerfuljre",
        "dave_smith",
        "danny_jones",
        "dr_jack_kruse",
        "david_martin_world",
        "align_podcast",
        "russell_brand",
        "timcast_irl",
    }
)

# Trajectory thresholds (mentions per day, 7-day window).
_RISING_THRESHOLD = 2.0   # current 7d rate >= 2.0x prior 7d rate
_COOLING_THRESHOLD = 0.5  # current 7d rate <= 0.5x prior 7d rate
_MIN_PRIOR_FOR_DELTA = 0.5  # need at least this much history to declare trajectory

# Common English stopwords that often appear capitalized in headlines.
_STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those", "i", "you", "we",
    "they", "it", "he", "she", "his", "her", "their", "our", "my", "your",
    "is", "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "have", "has", "had", "will", "would", "could", "should", "may", "might",
    "and", "or", "but", "so", "for", "of", "to", "in", "on", "at", "by",
    "from", "as", "with", "about", "into", "through", "during", "before",
    "after", "above", "below", "between", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "than", "too", "very", "can", "just",
}


def make_entity_id(name: str) -> str:
    """Stable ID for an entity name. Lowercase + whitespace-normalized."""
    norm = re.sub(r"\s+", " ", (name or "").strip().lower())
    if not norm:
        return ""
    return uuid.uuid5(_ENTITY_NAMESPACE, norm).hex[:24]


def _slug(name: str) -> str:
    """Filesystem-safe slug for entity page filenames."""
    norm = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower())
    return norm.strip("_") or "default"


def _coerce_mention(entity: Any) -> Optional[str]:
    """Accept a string OR a dict atom OR a tuple. Return the entity name."""
    if isinstance(entity, str):
        return entity.strip() or None
    if isinstance(entity, dict):
        text = entity.get("text") or entity.get("name") or entity.get("entity")
        if isinstance(text, str) and text.strip():
            return text.strip()
    if isinstance(entity, tuple) and len(entity) >= 1 and isinstance(entity[0], str):
        return entity[0].strip() or None
    return None


def extract_entities_from_item(item: Dict[str, Any]) -> List[str]:
    """Pull entity names from a normalized item.

    Priority:
    1. Declared `entities` list (authoritative — used by claim_mapping).
    2. Atom entities (from atom extraction if present).
    3. The author/channel as a single fallback (when source is a known publisher).
    """
    declared = [
        e for e in (item.get("entities") or []) if isinstance(e, str) and e.strip()
    ]
    if declared:
        return list(dict.fromkeys(declared))

    # Try atoms in the payload.
    atoms = item.get("atoms") or []
    if isinstance(atoms, list):
        names: List[str] = []
        for a in atoms:
            if not isinstance(a, dict):
                continue
            if a.get("atom_type") != "entity":
                continue
            t = a.get("text")
            if isinstance(t, str) and t.strip():
                names.append(t.strip())
        if names:
            return list(dict.fromkeys(names))

    # Fall back to the author/channel if it looks entity-like.
    author = (item.get("author") or "").strip()
    if author and not author.lower().startswith("http") and len(author) >= 3:
        return [author]
    return []


def _filter_noise(names: Iterable[str]) -> List[str]:
    """Drop overly generic capitalized phrases and short tokens."""
    out: List[str] = []
    seen: Set[str] = set()
    for n in names:
        if not n:
            continue
        if len(n) < 3:
            continue
        first = n.split()[0].lower()
        if first in _STOPWORDS:
            continue
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


# -- Registry state -----------------------------------------------------------

def load_registry_snapshot(path: Path) -> Dict[str, Dict[str, Any]]:
    """Load an existing entities snapshot, if any. Returns name -> record."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    entities = data.get("entities") if isinstance(data, dict) else None
    if not isinstance(entities, list):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for e in entities:
        if isinstance(e, dict) and isinstance(e.get("name"), str):
            out[e["name"]] = e
    return out


def _trajectory(prior_7d: float, current_7d: float) -> str:
    """Classify trajectory from 7-day rates."""
    if prior_7d < _MIN_PRIOR_FOR_DELTA:
        return "emerging" if current_7d > 0.5 else "stable"
    ratio = current_7d / max(prior_7d, 0.01)
    if ratio >= _RISING_THRESHOLD:
        return "rising"
    if ratio <= _COOLING_THRESHOLD:
        return "cooling"
    return "stable"


def update_registry(
    items: List[Dict[str, Any]],
    *,
    report_date: str,
    prior_snapshot: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a fresh entities snapshot from today's items.

    `prior_snapshot` is the previous day's output (name -> record).
    Each entity gets a stable id, mention counts, first/last seen, and
    a 7-day trajectory.
    """
    prior = prior_snapshot or {}
    today_counts: Dict[str, int] = defaultdict(int)
    today_source_buckets: Dict[str, Set[str]] = defaultdict(set)
    today_first_signal: Dict[str, str] = {}

    for item in items:
        names = _filter_noise(extract_entities_from_item(item))
        source_domain = (item.get("source_domain") or "").strip()
        bucket = (item.get("bucket") or "").strip()
        for n in names:
            today_counts[n] += 1
            if source_domain:
                today_source_buckets[n].add(source_domain)
            today_first_signal.setdefault(n, item.get("signal_id") or "")

    # Merge with prior registry.
    all_names = set(prior) | set(today_counts)
    entities: List[Dict[str, Any]] = []
    for name in all_names:
        prior_record = prior.get(name, {})
        prior_total = int(prior_record.get("mention_count_total", 0))
        prior_first = prior_record.get("first_seen") or report_date
        prior_last = prior_record.get("last_seen") or report_date
        prior_7d = float(prior_record.get("mentions_7d_rate", 0.0))
        prior_30d = float(prior_record.get("mentions_30d_rate", 0.0))
        prior_signal_ids = list(prior_record.get("recent_signal_ids", []))[:20]

        new_total = prior_total + int(today_counts.get(name, 0))
        # Update 7d / 30d rates with simple EWMA toward today's count.
        today_count = int(today_counts.get(name, 0))
        # Decay old rate slightly so a quiet day doesn't pin the rate.
        new_7d = round(0.7 * prior_7d + 0.3 * today_count, 3)
        new_30d = round(0.85 * prior_30d + 0.15 * today_count, 3)
        trajectory = _trajectory(prior_7d, new_7d)
        last_seen = report_date if today_count else prior_last
        first_seen = min(prior_first, report_date) if prior_first else report_date

        # Track a small ring of recent signal ids.
        recent = [s for s in prior_signal_ids if s]
        if today_first_signal.get(name):
            recent = ([today_first_signal[name]] + recent)[:20]

        entities.append(
            {
                "entity_id": make_entity_id(name),
                "name": name,
                "slug": _slug(name),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "mention_count_total": new_total,
                "mentions_7d_rate": new_7d,
                "mentions_30d_rate": new_30d,
                "trajectory": trajectory,
                "source_domains": sorted(today_source_buckets.get(name, set())),
                "recent_signal_ids": recent,
                "schema_version": "entity.v1",
            }
        )

    entities.sort(key=lambda e: e["mention_count_total"], reverse=True)
    return {
        "report_date": report_date,
        "entities": entities,
        "schema_version": "entities.v1",
    }


def export_entity_pages(
    snapshot: Dict[str, Any],
    *,
    out_dir: Path = DEFAULT_ENTITY_PAGES_DIR,
) -> int:
    """Write one JSON file per entity. Returns count written.

    Filename: {slug}.json — slug derived from name. Collision policy: append
    a short hash of the entity_id when slugs collide.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    seen_slugs: Dict[str, int] = {}
    count = 0
    for e in snapshot.get("entities", []):
        slug = e.get("slug") or _slug(e.get("name", ""))
        if slug in ENTITY_PAGE_DENY_SLUGS or any(
            deny in slug for deny in ("alex_jones", "candace_owens", "tucker_carlson")
        ):
            continue
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}_{e['entity_id'][:6]}"
        else:
            seen_slugs[slug] = 1
        path = out_dir / f"{slug}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(e, f, indent=2, ensure_ascii=False)
        count += 1
    return count


def export_entity_snapshot(
    snapshot: Dict[str, Any],
    *,
    out_dir: Path = DEFAULT_ENTITIES_DIR,
) -> Path:
    """Write the per-day entities snapshot. Atomic write (temp + rename)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report_date = snapshot.get("report_date") or utc_now_iso()[:10]
    final = out_dir / f"{report_date}.json"
    tmp = out_dir / f"{report_date}.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    tmp.replace(final)
    latest = out_dir / "latest.json"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(final.read_bytes())
    return final
