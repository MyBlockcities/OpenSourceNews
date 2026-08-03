#!/usr/bin/env python3
"""Export canonical + occurrence Qdrant-ready JSONL (v2).

v1 (``export_qdrant_payload.py``) remains unchanged for existing consumers.
This exporter separates:

- Canonical signal ID: uuid5("news_signal:{signal_id}")
- Occurrence ID:      uuid5("news_occurrence:{report_date}:{signal_id}")

It does not embed text or call Qdrant. Hermes should own embeddings.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import normalize_item


DAILY_DIR = ROOT_DIR / "outputs" / "daily"
EXPORT_DIR = ROOT_DIR / "outputs" / "qdrant_export"
POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/MyBlockcities/OpenSourceNews")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def report_date(path: Path) -> datetime | None:
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d")
    except ValueError:
        return None


def iter_report_paths(days: int | None = None) -> Iterable[Path]:
    cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=days)) if days else None
    for path in sorted(DAILY_DIR.glob("*.json"), reverse=True):
        dt = report_date(path)
        if cutoff_date and dt and dt.date() < cutoff_date:
            continue
        yield path


def canonical_point_id(signal_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, f"news_signal:{signal_id}"))


def occurrence_point_id(report_date_str: str, signal_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, f"news_occurrence:{report_date_str}:{signal_id}"))


def _csv_set(value: str | None) -> Set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def _sensor_payload(normalized: Dict[str, Any], report_date_str: str) -> Dict[str, Any]:
    return {
        "source_system": "OpenSourceNews",
        "report_date": report_date_str,
        "signal_id": normalized["signal_id"],
        "cluster_id": normalized["cluster_id"],
        "title": normalized["title"],
        "summary": normalized["summary"],
        "excerpt": normalized.get("excerpt") or "",
        "url": normalized.get("url") or "",
        "canonical_url": normalized.get("canonical_url") or "",
        "source_urls": normalized["source_urls"],
        "source_domain": normalized.get("source_domain") or "",
        "topics": normalized["topics"],
        "source": normalized["source"],
        "category": normalized["category"],
        "content_type": normalized["content_type"],
        "bucket": normalized["bucket"],
        "author": normalized.get("author") or "",
        "published_at": normalized.get("published_at"),
        "fetched_at": normalized.get("fetched_at") or "",
        "content_hash": normalized.get("content_hash") or "",
        "enrichment_status": normalized.get("enrichment_status") or "pending",
        "processing_mode": normalized["processing_mode"],
        "mode": normalized["mode"],
        "stance": normalized["stance"],
        "affiliation": normalized["affiliation"],
        "risk_level": normalized["risk_level"],
        "verification_mode": normalized["verification_mode"],
        "content_warning": normalized["content_warning"],
        "source_category": normalized["source_category"],
        "trust_layer": normalized["trust_layer"],
        "trust_level": normalized["trust_level"],
        "evidence_level": normalized["evidence_level"],
        "regulatory_sensitivity": normalized["regulatory_sensitivity"],
        "content_use": normalized["content_use"],
        "safe_framing": normalized["safe_framing"],
        "medical_claim_policy": normalized["medical_claim_policy"],
        "classification_confidence": normalized["classification_confidence"],
        "quality_score": normalized["quality_score"],
        "has_transcript": normalized["has_transcript"],
    }


def collect_occurrences(
    days: int | None,
    bucket_filter: Set[str] | None = None,
    topic_filter: str | None = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Return (occurrence records, canonical accumulators keyed by signal_id)."""
    occurrences: List[Dict[str, Any]] = []
    canonicals: Dict[str, Dict[str, Any]] = {}
    topic_term = (topic_filter or "").strip().lower()

    for path in iter_report_paths(days=days):
        data = load_json(path)
        for topic_name, items in data.items():
            if not isinstance(items, list):
                continue
            if topic_term and topic_term not in topic_name.lower():
                continue
            for raw_item in items:
                if not isinstance(raw_item, dict):
                    continue
                normalized = normalize_item(topic_name, raw_item)
                if bucket_filter and (normalized.get("bucket") or "").lower() not in bucket_filter:
                    continue
                signal_id = normalized["signal_id"]
                if not signal_id:
                    continue

                date_str = path.stem
                occurrence = {
                    "id": occurrence_point_id(date_str, signal_id),
                    "external_id": f"opensourcenews:occurrence:{date_str}:{signal_id}",
                    "record_type": "news_occurrence",
                    "embedding_text": "",
                    "payload": {
                        **_sensor_payload(normalized, date_str),
                        "canonical_id": canonical_point_id(signal_id),
                    },
                }
                occurrences.append(occurrence)

                existing = canonicals.get(signal_id)
                if existing is None:
                    canonicals[signal_id] = {
                        "id": canonical_point_id(signal_id),
                        "external_id": f"opensourcenews:signal:{signal_id}",
                        "record_type": "news_signal",
                        "embedding_text": "",
                        "payload": {
                            **_sensor_payload(normalized, date_str),
                            "first_seen": date_str,
                            "last_seen": date_str,
                            "occurrence_count": 1,
                        },
                    }
                else:
                    payload = existing["payload"]
                    first_seen = payload.get("first_seen") or date_str
                    last_seen = payload.get("last_seen") or date_str
                    # Reports are iterated newest-first; keep chronological bounds.
                    if date_str < first_seen:
                        payload["first_seen"] = date_str
                        # Prefer earliest metadata for stable canonical fields.
                        for key in (
                            "title",
                            "summary",
                            "excerpt",
                            "url",
                            "canonical_url",
                            "source_urls",
                            "source_domain",
                            "topics",
                            "source",
                            "category",
                            "content_type",
                            "bucket",
                            "author",
                            "published_at",
                        ):
                            payload[key] = _sensor_payload(normalized, date_str)[key]
                    if date_str > last_seen:
                        payload["last_seen"] = date_str
                    payload["occurrence_count"] = int(payload.get("occurrence_count") or 0) + 1
                    # Refresh enrichment/status from newest sighting when newer.
                    if date_str >= (payload.get("last_seen") or date_str):
                        payload["enrichment_status"] = normalized.get("enrichment_status") or "pending"
                        payload["fetched_at"] = normalized.get("fetched_at") or payload.get("fetched_at") or ""
                        payload["content_hash"] = normalized.get("content_hash") or payload.get("content_hash") or ""

    return occurrences, canonicals


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export canonical + occurrence records for downstream Qdrant (v2)."
    )
    parser.add_argument("--days", type=int, default=30, help="Recent days to export. 0 = all.")
    parser.add_argument("--bucket", default="", help="Comma-separated bucket filter.")
    parser.add_argument("--topic", default="", help="Case-insensitive topic substring filter.")
    parser.add_argument(
        "--canonical-out",
        default=str(EXPORT_DIR / "news_signals_v2_canonical.jsonl"),
        help="Canonical signals JSONL path.",
    )
    parser.add_argument(
        "--occurrence-out",
        default=str(EXPORT_DIR / "news_signals_v2_occurrences.jsonl"),
        help="Occurrence JSONL path.",
    )
    parser.add_argument(
        "--combined-out",
        default="",
        help="Optional combined JSONL (canonical then occurrences).",
    )
    args = parser.parse_args()

    days = None if args.days == 0 else max(1, args.days)
    bucket_filter = _csv_set(args.bucket)
    occurrences, canonical_map = collect_occurrences(
        days=days,
        bucket_filter=bucket_filter or None,
        topic_filter=args.topic,
    )
    canonical_records = list(canonical_map.values())
    # Stable order: oldest first_seen, then signal_id.
    canonical_records.sort(
        key=lambda rec: (
            str((rec.get("payload") or {}).get("first_seen") or ""),
            str((rec.get("payload") or {}).get("signal_id") or ""),
        )
    )

    canonical_path = Path(args.canonical_out)
    occurrence_path = Path(args.occurrence_out)
    c_count = write_jsonl(canonical_path, canonical_records)
    o_count = write_jsonl(occurrence_path, occurrences)

    combined_count = 0
    combined_path = Path(args.combined_out) if args.combined_out else None
    if combined_path:
        combined_count = write_jsonl(combined_path, [*canonical_records, *occurrences])

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT_DIR))
        except ValueError:
            return str(path)

    manifest = {
        "schema": "open_source_news_qdrant_export.v2",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "days": args.days,
        "bucket_filter": sorted(bucket_filter),
        "topic_filter": args.topic,
        "canonical_count": c_count,
        "occurrence_count": o_count,
        "combined_count": combined_count,
        "canonical_jsonl_path": _rel(canonical_path),
        "occurrence_jsonl_path": _rel(occurrence_path),
        "combined_jsonl_path": _rel(combined_path) if combined_path else "",
        "id_strategy": {
            "canonical": "uuid5(opensourcenews namespace, news_signal:{signal_id})",
            "occurrence": "uuid5(opensourcenews namespace, news_occurrence:{report_date}:{signal_id})",
        },
        "embedding_field": "embedding_text",
        "notes": "embedding_text left empty for Hermes-owned embedding models.",
    }
    manifest_path = canonical_path.with_name("news_signals_v2.manifest.json")
    if args.canonical_out != str(EXPORT_DIR / "news_signals_v2_canonical.jsonl"):
        manifest_path = canonical_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"v2 canonical export: {canonical_path} ({c_count} records)")
    print(f"v2 occurrence export: {occurrence_path} ({o_count} records)")
    if combined_path:
        print(f"v2 combined export: {combined_path} ({combined_count} records)")
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
