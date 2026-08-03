#!/usr/bin/env python3
"""Export embedding-ready JSONL (no vectors) for Hermes MiniLM upsert.

Hermes streams this file, embeds locally, and upserts to Qdrant.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import add_item_ids, canonicalize_url


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
ATOMS_DIR = ROOT_DIR / "outputs" / "atoms"
OUT_DIR = ROOT_DIR / "outputs" / "embedding_ready"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def latest_report(explicit: str = "") -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    files = sorted(DAILY_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def signal_records(report: Dict[str, Any], report_date: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for topic, items in (report or {}).items():
        if not isinstance(items, list):
            continue
        for raw in items:
            if not isinstance(raw, dict):
                continue
            item = add_item_ids(dict(raw))
            signal_id = item.get("signal_id") or ""
            title = item.get("title") or ""
            summary = item.get("summary") or item.get("excerpt") or ""
            url = item.get("canonical_url") or canonicalize_url(str(item.get("url") or ""))
            embedding_text = "\n\n".join(
                part for part in (title, summary, item.get("excerpt") or "") if str(part).strip()
            ).strip()
            if not embedding_text:
                continue
            rows.append(
                {
                    "external_id": f"opensourcenews:signal:{signal_id}",
                    "record_type": "news_signal",
                    "signal_id": signal_id,
                    "parent_signal_id": signal_id,
                    "atom_id": "",
                    "report_date": report_date,
                    "embedding_text": embedding_text[:12000],
                    "title": title,
                    "url": item.get("url") or "",
                    "canonical_url": url,
                    "source": item.get("source") or "",
                    "bucket": item.get("bucket") or "",
                    "topics": item.get("topics") or [topic],
                    "public_topics": item.get("public_topics") or [],
                    "entities": item.get("entities") or [],
                    "content_hash": item.get("content_hash") or "",
                    "fetched_at": item.get("fetched_at") or "",
                    "enrichment_status": item.get("enrichment_status") or "pending",
                    "tutorial_potential": item.get("tutorial_potential"),
                    "schema_version": "embedding_ready.v1",
                    "provenance": {
                        "source_url": item.get("url") or "",
                        "canonical_url": url,
                        "fetched_at": item.get("fetched_at") or "",
                        "report_date": report_date,
                    },
                }
            )
    return rows


def atom_records(atoms_path: Path, report_date: str) -> List[Dict[str, Any]]:
    if not atoms_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in atoms_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        atom = json.loads(line)
        text = str(atom.get("text") or "").strip()
        if not text:
            continue
        atom_id = atom.get("atom_id") or ""
        parent = atom.get("parent_signal_id") or ""
        rows.append(
            {
                "external_id": f"opensourcenews:atom:{atom_id}",
                "record_type": "news_atom",
                "signal_id": parent,
                "parent_signal_id": parent,
                "atom_id": atom_id,
                "atom_type": atom.get("atom_type") or "",
                "report_date": report_date,
                "embedding_text": text[:12000],
                "title": text[:160],
                "url": (atom.get("evidence_urls") or [""])[0],
                "canonical_url": (atom.get("evidence_urls") or [""])[0],
                "source": "atom_extraction",
                "bucket": "",
                "topics": [],
                "public_topics": atom.get("public_topics") or [],
                "entities": [],
                "content_hash": "",
                "fetched_at": atom.get("extracted_at") or "",
                "enrichment_status": "pending",
                "schema_version": "embedding_ready.v1",
                "provenance": {
                    "parent_signal_id": parent,
                    "atom_id": atom_id,
                    "extracted_at": atom.get("extracted_at") or "",
                    "report_date": report_date,
                },
            }
        )
    return rows


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    lines = [json.dumps(rec, ensure_ascii=False) for rec in records]
    _atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export embedding-ready JSONL for Hermes")
    parser.add_argument("--report", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--include-atoms", action="store_true", default=True)
    parser.add_argument("--signals-only", action="store_true")
    args = parser.parse_args()

    report_path = latest_report(args.report)
    if report_path is None:
        print("No daily report found")
        return
    report_date = args.date or report_path.stem
    report = json.loads(report_path.read_text(encoding="utf-8"))

    records = signal_records(report, report_date)
    if args.include_atoms and not args.signals_only:
        records.extend(atom_records(ATOMS_DIR / f"{report_date}.jsonl", report_date))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{report_date}.jsonl"
    latest = OUT_DIR / "latest.jsonl"
    count = write_jsonl(out, records)
    latest.write_bytes(out.read_bytes())
    meta = {
        "schema": "open_source_news_embedding_ready_manifest.v1",
        "report_date": report_date,
        "record_count": count,
        "generated_at": utc_now_iso(),
        "jsonl_path": f"outputs/embedding_ready/{report_date}.jsonl",
        "embedding_field": "embedding_text",
        "notes": "No vectors; Hermes embeds with local all-MiniLM (384-d).",
    }
    _atomic_write_text(OUT_DIR / f"{report_date}.manifest.json", json.dumps(meta, indent=2) + "\n")
    print(f"Embedding-ready written: {out} ({count})")


if __name__ == "__main__":
    main()
