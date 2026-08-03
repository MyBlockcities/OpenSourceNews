"""Public-learnable per-source per-topic trust scores."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
TRUST_OUT = ROOT_DIR / "outputs" / "source_trust"

# Baseline priors by source class (public heuristic; Hermes may reweight privately).
_SOURCE_PRIORS = {
    "pubmed": 0.85,
    "clinicaltrials": 0.8,
    "rss": 0.65,
    "hackernews": 0.6,
    "github": 0.7,
    "youtube": 0.55,
    "x": 0.45,
    "unknown": 0.5,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _source_key(item: Dict[str, Any]) -> str:
    return str(item.get("source") or item.get("source_domain") or "unknown").strip() or "unknown"


def _source_class(item: Dict[str, Any]) -> str:
    source = _source_key(item).lower()
    bucket_hint = str(item.get("bucket") or "").lower()
    if "pubmed" in source:
        return "pubmed"
    if "clinical" in source:
        return "clinicaltrials"
    if "github" in source:
        return "github"
    if "youtube" in source or source.startswith("@"):
        return "youtube"
    if "hacker" in source or source == "hn":
        return "hackernews"
    if source in {"x", "twitter"}:
        return "x"
    if "rss" in source or bucket_hint:
        return "rss"
    return "unknown"


def build_source_trust(
    items: List[Dict[str, Any]],
    consensus: Optional[Dict[str, Any]] = None,
    *,
    report_date: str,
) -> Dict[str, Any]:
    """Score sources per public topic using volume + consensus confirmation boosts."""
    by_source_topic: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(lambda: {"count": 0.0, "confirm": 0.0, "contradict": 0.0})
    )
    source_class: Dict[str, str] = {}

    for item in items:
        src = _source_key(item)
        source_class[src] = _source_class(item)
        topics = item.get("public_topics") or ["untagged"]
        for topic in topics:
            by_source_topic[src][topic]["count"] += 1.0

    # Fold consensus confirmation/contradiction when available.
    if consensus:
        signal_to_source = {
            str(i.get("signal_id") or ""): _source_key(i) for i in items
        }
        # Consensus rows don't map 1:1 to signals; use source lists on claims.
        for claim in consensus.get("claims") or []:
            for src in claim.get("confirming_sources") or []:
                by_source_topic[src]["__global__"]["confirm"] += 1.0
            for src in claim.get("contradicting_sources") or []:
                by_source_topic[src]["__global__"]["contradict"] += 1.0
            for src in claim.get("sources") or []:
                source_class.setdefault(src, "unknown")

    rows = []
    for src, topic_map in by_source_topic.items():
        prior = _SOURCE_PRIORS.get(source_class.get(src, "unknown"), 0.5)
        for topic, stats in topic_map.items():
            count = stats["count"]
            confirm = stats["confirm"]
            contradict = stats["contradict"]
            # Volume soft-cap + confirmation boost − contradiction penalty
            volume = min(1.0, count / 10.0) if count else 0.0
            confirm_boost = min(0.2, confirm * 0.05)
            contradict_pen = min(0.25, contradict * 0.08)
            score = max(0.0, min(1.0, prior * 0.6 + volume * 0.3 + confirm_boost - contradict_pen))
            rows.append(
                {
                    "source": src,
                    "source_class": source_class.get(src, "unknown"),
                    "topic": topic,
                    "item_count": int(count),
                    "confirmation_events": int(confirm),
                    "contradiction_events": int(contradict),
                    "trust_score": round(score, 4),
                }
            )

    rows.sort(key=lambda r: (-r["trust_score"], r["source"], r["topic"]))
    return {
        "schema": "open_source_news_source_trust.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "methodology": "prior*0.6 + volume*0.3 + confirm_boost - contradict_penalty",
        "scores": rows[:500],
    }


def write_source_trust(payload: Dict[str, Any], report_date: str) -> Path:
    TRUST_OUT.mkdir(parents=True, exist_ok=True)
    path = TRUST_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(TRUST_OUT / "latest.json", payload)
    return path
