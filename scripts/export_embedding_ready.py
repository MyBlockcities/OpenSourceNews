#!/usr/bin/env python3
"""Export embedding-ready JSONL for Hermes.

Produces one record per line, ready for the local MiniLM embedder.
This script does NOT embed. It only prepares clean text + provenance
+ stable external_id so Hermes can stream-embed in one pass.

Per-line record shape
---------------------
{
  "external_id":      "opensourcenews:atom:{atom_id}" | "opensourcenews:signal:{signal_id}",
  "record_type":      "atom" | "signal",
  "embedding_text":   "<clean text for embedding>",
  "payload": {
    "schema_version":  "embed_ready.v1",
    "source":          "OpenSourceNews",
    "report_date":     "YYYY-MM-DD",
    "public_topics":   ["ai_agents", "real_estate_tech"],
    "parent_signal_id":"...",
    "atom_id":         "..." | null,
    "atom_type":       "claim" | null,
    "source_domain":   "...",
    "url":             "...",
    "title":           "...",
  }
}

Usage:
    python scripts/export_embedding_ready.py --date 2026-08-03
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

DAILY_DIR = ROOT_DIR / "outputs" / "daily"
ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"
EMBED_DIR = ROOT_DIR / "outputs" / "embedding_ready"
EMBED_DIR.mkdir(parents=True, exist_ok=True)

# Cap embedding text length to keep MiniLM input reasonable.
MAX_EMBED_CHARS = 1800


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _clip(text: str, limit: int = MAX_EMBED_CHARS) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = cut.rfind(" ")
    if boundary >= limit * 0.6:
        cut = cut[:boundary]
    return cut.rstrip(" ,;:-") + "…"


def _build_embedding_text(item: Dict[str, Any]) -> str:
    """Build a clean text representation for the local embedder."""
    parts: List[str] = []
    title = (item.get("title") or "").strip()
    if title:
        parts.append(title)
    summary = (item.get("summary") or "").strip()
    if summary:
        parts.append(summary)
    excerpt = (item.get("excerpt") or "").strip()
    if excerpt and excerpt != summary:
        parts.append(excerpt)
    bucket = (item.get("bucket") or "").strip()
    if bucket:
        parts.append(f"[bucket: {bucket}]")
    return _clip("\n\n".join(parts))


def _iter_items(date_str: str) -> Iterable[Dict[str, Any]]:
    """Yield normalized items from outputs/daily/{date}.json, all topics."""
    from services.news_schema import add_item_ids
    from services.topics import add_public_topics, load_topics

    report = _read_json(DAILY_DIR / f"{date_str}.json")
    if not isinstance(report, dict):
        return
    topics = load_topics()
    for _topic, topic_items in report.items():
        if not isinstance(topic_items, list):
            continue
        for it in topic_items:
            if isinstance(it, dict):
                item = add_item_ids(dict(it))
                yield add_public_topics(item, topics)


def _signal_record(item: Dict[str, Any], date_str: str) -> Optional[Dict[str, Any]]:
    text = _build_embedding_text(item)
    if not text:
        return None
    signal_id = (item.get("signal_id") or "").strip()
    if not signal_id:
        return None
    return {
        "external_id": f"opensourcenews:signal:{signal_id}",
        "record_type": "signal",
        "embedding_text": text,
        "payload": {
            "schema_version": "embed_ready.v1",
            "source": "OpenSourceNews",
            "report_date": date_str,
            "public_topics": list(item.get("public_topics") or []),
            "parent_signal_id": signal_id,
            "atom_id": None,
            "atom_type": None,
            "source_domain": (item.get("source_domain") or "").strip(),
            "source_id": (item.get("source_id") or "").strip(),
            "source_tier": (item.get("source_tier") or "").strip(),
            "permitted_use": (item.get("permitted_use") or "").strip(),
            "url": (item.get("canonical_url") or item.get("url") or "").strip(),
            "title": (item.get("title") or "").strip(),
        },
    }


def _atom_record(atom: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = _clip(str(atom.get("text") or ""))
    if not text:
        return None
    atom_id = (atom.get("atom_id") or "").strip()
    if not atom_id:
        return None
    return {
        "external_id": f"opensourcenews:atom:{atom_id}",
        "record_type": "atom",
        "embedding_text": text,
        "payload": {
            "schema_version": "embed_ready.v1",
            "source": "OpenSourceNews",
            "report_date": atom.get("report_date", ""),
            "public_topics": list(atom.get("public_topics") or []),
            "parent_signal_id": (atom.get("parent_signal_id") or "").strip(),
            "atom_id": atom_id,
            "atom_type": atom.get("atom_type", ""),
            "source_domain": (atom.get("parent_source_domain") or "").strip(),
            "url": (atom.get("parent_canonical_url") or "").strip(),
            "title": (atom.get("text") or "")[:120],
        },
    }


def run(date_str: Optional[str] = None) -> Dict[str, Any]:
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = EMBED_DIR / f"{date_str}.jsonl"
    tmp = EMBED_DIR / f"{date_str}.jsonl.tmp"
    counts = {"signal": 0, "atom": 0, "skipped": 0}
    with open(tmp, "w", encoding="utf-8") as f:
        # One record per signal.
        for item in _iter_items(date_str):
            rec = _signal_record(item, date_str)
            if rec is None:
                counts["skipped"] += 1
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts["signal"] += 1
        # One record per atom.
        for atom in _read_jsonl(ATOMS_DIR / f"{date_str}.jsonl"):
            rec = _atom_record(atom)
            if rec is None:
                counts["skipped"] += 1
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts["atom"] += 1
    tmp.replace(out_path)
    latest = EMBED_DIR / "latest.jsonl"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(out_path.read_bytes())
    return {
        "ok": True,
        "date": date_str,
        "out_path": str(out_path),
        **counts,
        "schema_version": "embed_ready_run.v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export embedding-ready JSONL for Hermes.")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today UTC)")
    args = parser.parse_args()
    summary = run(args.date)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
