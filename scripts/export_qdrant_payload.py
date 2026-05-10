#!/usr/bin/env python3
"""Export OpenSourceNews records as downstream-Qdrant-ready JSONL.

This does not embed text or call Qdrant. It prepares deterministic records that
another application can fetch, embed, and upsert into its own vector database.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

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
    cutoff_date = (datetime.utcnow().date() - timedelta(days=days)) if days else None
    for path in sorted(DAILY_DIR.glob("*.json"), reverse=True):
        dt = report_date(path)
        if cutoff_date and dt and dt.date() < cutoff_date:
            continue
        yield path


def text_parts(item: Dict[str, Any]) -> List[str]:
    parts: List[str] = [
        item.get("title") or "",
        item.get("summary") or "",
        item.get("neutral_synthesis") or "",
        item.get("implementation_notes") or "",
        item.get("unique_value") or "",
        item.get("source_category") or "",
        item.get("trust_layer") or "",
        item.get("evidence_level") or "",
        item.get("content_use") or "",
        item.get("safe_framing") or "",
    ]
    for key in (
        "key_insights",
        "key_lessons",
        "actionable_steps",
        "tools_mentioned",
        "frameworks_mentioned",
        "entities",
        "uncertainty_markers",
    ):
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(entry) for entry in value if str(entry).strip())
    claims = item.get("claims") or []
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, dict):
                parts.extend(
                    str(claim.get(key) or "")
                    for key in ("claim", "evidence_cited", "analyst_note")
                )
            else:
                parts.append(str(claim))
    return [part.strip() for part in parts if part and part.strip()]


def embedding_text(item: Dict[str, Any], max_chars: int) -> str:
    text = "\n\n".join(text_parts(item))
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars]
    return text


def point_id(report_date_str: str, signal_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, f"news_signal:{report_date_str}:{signal_id}"))


def _csv_set(value: str | None) -> Set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def export_records(
    days: int | None,
    max_chars: int,
    bucket_filter: Set[str] | None = None,
    topic_filter: str | None = None,
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
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
                text = embedding_text(normalized, max_chars=max_chars)
                if not text:
                    continue
                signal_id = normalized["signal_id"]
                record = {
                    "id": point_id(path.stem, signal_id),
                    "external_id": f"opensourcenews:{path.stem}:{signal_id}",
                    "record_type": "news_signal",
                    "embedding_text": text,
                    "payload": {
                        "source_system": "OpenSourceNews",
                        "report_date": path.stem,
                        "signal_id": signal_id,
                        "cluster_id": normalized["cluster_id"],
                        "title": normalized["title"],
                        "summary": normalized["summary"],
                        "source_urls": normalized["source_urls"],
                        "topics": normalized["topics"],
                        "source": normalized["source"],
                        "category": normalized["category"],
                        "content_type": normalized["content_type"],
                        "bucket": normalized["bucket"],
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
                    },
                }
                records.append(record)
    return records


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export normalized records for downstream Qdrant ingestion.")
    parser.add_argument("--days", type=int, default=30, help="Number of recent days to export. Use 0 for all reports.")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max embedding text chars per record.")
    parser.add_argument("--bucket", default="", help="Comma-separated bucket filter, e.g. peptides or ai,peptides.")
    parser.add_argument("--topic", default="", help="Case-insensitive topic-name substring filter.")
    parser.add_argument("--out", default=str(EXPORT_DIR / "news_signals.jsonl"), help="Output JSONL path.")
    args = parser.parse_args()

    days = None if args.days == 0 else max(1, args.days)
    bucket_filter = _csv_set(args.bucket)
    records = export_records(
        days=days,
        max_chars=max(1, args.max_chars),
        bucket_filter=bucket_filter or None,
        topic_filter=args.topic,
    )
    out_path = Path(args.out)
    count = write_jsonl(out_path, records)

    manifest = {
        "schema": "open_source_news_qdrant_export.v1",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "record_count": count,
        "days": args.days,
        "bucket_filter": sorted(bucket_filter),
        "topic_filter": args.topic,
        "jsonl_path": str(out_path.relative_to(ROOT_DIR)) if out_path.is_relative_to(ROOT_DIR) else str(out_path),
        "id_strategy": "uuid5(opensourcenews namespace, news_signal:{report_date}:{signal_id})",
        "embedding_field": "embedding_text",
        "payload_field": "payload",
    }
    manifest_path = out_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Qdrant export written to {out_path} ({count} records)")
    print(f"Manifest written to {manifest_path}")


if __name__ == "__main__":
    main()
