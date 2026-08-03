"""Public topic tagging from config/topics.yaml."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
TOPICS_PATH = ROOT_DIR / "config" / "topics.yaml"
TOPICS_OUT = ROOT_DIR / "outputs" / "topics"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_topics(path: Path = TOPICS_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("topics") or [])


def tag_text(text: str, topics: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    blob = (text or "").lower()
    if not blob:
        return []
    ontology = topics if topics is not None else load_topics()
    hits: List[str] = []
    for topic in ontology:
        tid = str(topic.get("id") or "").strip()
        if not tid:
            continue
        keywords = topic.get("keywords") or []
        for kw in keywords:
            kw_l = str(kw).lower()
            if kw_l and kw_l in blob:
                hits.append(tid)
                break
    return sorted(set(hits))


def tag_item(item: Dict[str, Any], topics: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    parts = [
        item.get("title") or "",
        item.get("summary") or "",
        item.get("excerpt") or "",
        " ".join(item.get("topics") or []),
    ]
    return tag_text(" ".join(str(p) for p in parts), topics)


def build_topics_export(
    items: List[Dict[str, Any]],
    *,
    report_date: str,
    previous: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ontology = load_topics()
    freq: Counter[str] = Counter()
    co: Counter[Tuple[str, str]] = Counter()
    tagged_items = 0

    for item in items:
        tags = item.get("public_topics") or tag_item(item, ontology)
        if not tags:
            continue
        tagged_items += 1
        for t in tags:
            freq[t] += 1
        for i, a in enumerate(tags):
            for b in tags[i + 1 :]:
                pair = tuple(sorted((a, b)))
                co[pair] += 1

    prev_freq = {}
    if previous and isinstance(previous.get("frequency"), dict):
        prev_freq = previous["frequency"]

    rising: List[str] = []
    cooling: List[str] = []
    for tid, count in freq.items():
        old = int(prev_freq.get(tid) or 0)
        if count > old + 1:
            rising.append(tid)
        elif old and count < old:
            cooling.append(tid)

    return {
        "schema": "open_source_news_topics.v1",
        "report_date": report_date,
        "generated_at": utc_now_iso(),
        "tagged_item_count": tagged_items,
        "frequency": dict(freq),
        "rising": sorted(rising),
        "cooling": sorted(cooling),
        "co_occurrence": [
            {"topics": list(pair), "count": count}
            for pair, count in co.most_common(50)
        ],
        "ontology_version": "topics.yaml",
    }


def write_topics_export(payload: Dict[str, Any], report_date: str) -> Path:
    TOPICS_OUT.mkdir(parents=True, exist_ok=True)
    path = TOPICS_OUT / f"{report_date}.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(TOPICS_OUT / "latest.json", payload)
    return path
