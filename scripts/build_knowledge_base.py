#!/usr/bin/env python3
"""Build a consolidated knowledge base from generated scheduler outputs."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from services.news_schema import add_item_ids

OUTPUTS_DIR = ROOT_DIR / "outputs"
DAILY_DIR = OUTPUTS_DIR / "daily"
SCRIPTS_DIR = OUTPUTS_DIR / "scripts"
TRANSCRIPTS_DIR = OUTPUTS_DIR / "transcripts"
KNOWLEDGE_BASE_DIR = OUTPUTS_DIR / "knowledge_base"
DOCS_DIR = ROOT_DIR / "docs"
DOCS_DAILY_DIR = DOCS_DIR / "generated" / "daily"
DOCS_KB_DIR = DOCS_DIR / "generated" / "knowledge_base"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relpath(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR))


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_date(path: Path) -> Optional[str]:
    match = DATE_RE.search(path.stem)
    return match.group(1) if match else None


def make_record_id(parts: Iterable[str]) -> str:
    joined = "|".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return digest[:16]


def normalize_text_parts(parts: Iterable[Optional[str]]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def build_daily_section() -> Dict[str, Any]:
    reports: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []
    topic_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for report_path in sorted(DAILY_DIR.glob("*.json")):
        report_date = extract_date(report_path) or "unknown"
        markdown_path = DOCS_DAILY_DIR / f"{report_date}.md"
        report_data = load_json(report_path)

        topic_summaries: List[Dict[str, Any]] = []
        total_items = 0

        for topic_name, items in sorted(report_data.items()):
            topic_items = items if isinstance(items, list) else []
            topic_counts[topic_name] += len(topic_items)
            total_items += len(topic_items)
            topic_summaries.append({"topic": topic_name, "item_count": len(topic_items)})

            for index, item in enumerate(topic_items, start=1):
                item = add_item_ids(item)
                source = item.get("source", "Unknown")
                source_counts[source] += 1
                key_insights = item.get("key_insights") or []
                content = normalize_text_parts(
                    [
                        item.get("title"),
                        item.get("summary"),
                        "\n".join(f"- {insight}" for insight in key_insights),
                        item.get("unique_value"),
                    ]
                )
                record_id = make_record_id(
                    [
                        "daily_item",
                        report_date,
                        topic_name,
                        item.get("url", ""),
                        item.get("title", f"item-{index}"),
                    ]
                )
                # Build embedding text from all available content
                embedding_parts = [
                    item.get("title", ""),
                    item.get("summary", ""),
                    "\n".join(f"- {insight}" for insight in key_insights),
                    item.get("unique_value", ""),
                    item.get("neutral_synthesis", ""),
                    item.get("implementation_notes", ""),
                ]
                claims = item.get("claims") or []
                for claim in claims:
                    if isinstance(claim, dict):
                        embedding_parts.append(claim.get("claim", ""))
                lessons = item.get("key_lessons") or []
                embedding_parts.extend(lessons)
                entities = item.get("entities") or []
                embedding_parts.extend(entities)
                embedding_text = normalize_text_parts(embedding_parts)

                records.append(
                    {
                        "id": record_id,
                        "signal_id": item.get("signal_id"),
                        "cluster_id": item.get("cluster_id"),
                        "record_type": "daily_item",
                        "date": report_date,
                        "topic": topic_name,
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "source": source,
                        "category": item.get("category"),
                        "quality_score": item.get("quality_score"),
                        "target_audience": item.get("target_audience"),
                        "content_type": item.get("content_type"),
                        "key_insights": key_insights,
                        "content": content,
                        "origin_file": relpath(report_path),
                        # Enriched fields from pipeline classification & processing
                        "bucket": item.get("bucket"),
                        "processing_mode": item.get("processing_mode"),
                        "mode": item.get("mode"),
                        "stance": item.get("stance"),
                        "affiliation": item.get("affiliation"),
                        "risk_level": item.get("risk_level"),
                        "verification_mode": item.get("verification_mode"),
                        "content_warning": item.get("content_warning"),
                        "classification_confidence": item.get("classification_confidence"),
                        # Wisdom extraction fields
                        "key_lessons": item.get("key_lessons"),
                        "actionable_steps": item.get("actionable_steps"),
                        "tools_mentioned": item.get("tools_mentioned"),
                        "frameworks_mentioned": item.get("frameworks_mentioned"),
                        "implementation_notes": item.get("implementation_notes"),
                        "difficulty": item.get("difficulty"),
                        # Claim mapping fields
                        "claims": claims if claims else None,
                        "entities": entities if entities else None,
                        "uncertainty_markers": item.get("uncertainty_markers"),
                        "neutral_synthesis": item.get("neutral_synthesis"),
                        # Embedding-ready text
                        "embedding_text": embedding_text,
                    }
                )

        reports.append(
            {
                "date": report_date,
                "json_file": relpath(report_path),
                "markdown_file": relpath(markdown_path) if markdown_path.exists() else None,
                "total_items": total_items,
                "topics": topic_summaries,
            }
        )

    return {
        "reports": reports,
        "records": records,
        "topic_counts": dict(sorted(topic_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
    }


def build_scripts_section() -> Dict[str, Any]:
    packages: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []

    stems = sorted(
        {
            path.name.replace("-script.txt", "").replace("-storyboard.json", "")
            for path in SCRIPTS_DIR.glob("*")
            if path.is_file()
        }
    )

    for stem in stems:
        script_path = SCRIPTS_DIR / f"{stem}-script.txt"
        storyboard_path = SCRIPTS_DIR / f"{stem}-storyboard.json"
        script_text = safe_read_text(script_path) if script_path.exists() else None
        storyboard_data = load_json(storyboard_path) if storyboard_path.exists() else None

        sources = storyboard_data.get("sources", []) if isinstance(storyboard_data, dict) else []
        packages.append(
            {
                "date": stem,
                "script_file": relpath(script_path) if script_path.exists() else None,
                "storyboard_file": relpath(storyboard_path) if storyboard_path.exists() else None,
                "source_count": len(sources),
                "duration_seconds": storyboard_data.get("total_duration_seconds") if isinstance(storyboard_data, dict) else None,
                "sources": sources,
            }
        )

        if script_text:
            records.append(
                {
                    "id": make_record_id(["video_script", stem]),
                    "record_type": "video_script",
                    "date": stem,
                    "title": f"Video script for {stem}",
                    "content": script_text,
                    "origin_file": relpath(script_path),
                    "storyboard_file": relpath(storyboard_path) if storyboard_path.exists() else None,
                    "source_urls": [source.get("url") for source in sources if isinstance(source, dict)],
                }
            )

    return {"packages": packages, "records": records}


def build_transcripts_section() -> Dict[str, Any]:
    transcripts: List[Dict[str, Any]] = []
    records: List[Dict[str, Any]] = []

    for transcript_path in sorted(TRANSCRIPTS_DIR.glob("*.json")):
        data = load_json(transcript_path)
        video_id = data.get("video_id") or transcript_path.stem
        transcript_text = data.get("transcript", "")
        word_count = data.get("word_count")
        fetched_at = data.get("fetched_at")

        transcripts.append(
            {
                "video_id": video_id,
                "file": relpath(transcript_path),
                "video_url": data.get("video_url"),
                "word_count": word_count,
                "source": data.get("source"),
                "language": data.get("language"),
                "fetched_at": fetched_at,
                "cached": data.get("cached"),
            }
        )

        if transcript_text:
            records.append(
                {
                    "id": make_record_id(["transcript", video_id]),
                    "record_type": "transcript",
                    "date": extract_date(transcript_path),
                    "title": video_id,
                    "video_url": data.get("video_url"),
                    "word_count": word_count,
                    "content": transcript_text,
                    "origin_file": relpath(transcript_path),
                    "source": data.get("source"),
                }
            )

    return {"transcripts": transcripts, "records": records}


def build_summary_markdown(knowledge_base: Dict[str, Any]) -> str:
    stats = knowledge_base["stats"]
    recent_reports = knowledge_base["daily_reports"][-5:]
    recent_scripts = knowledge_base["video_scripts"][-5:]
    transcripts = knowledge_base["transcripts"]

    lines = [
        "# Knowledge Base Summary",
        "",
        f"- Generated at: `{knowledge_base['generated_at']}`",
        f"- Total records: `{stats['total_records']}`",
        f"- Daily reports: `{stats['daily_report_count']}`",
        f"- Daily items: `{stats['daily_item_count']}`",
        f"- Video scripts: `{stats['video_script_count']}`",
        f"- Transcripts: `{stats['transcript_count']}`",
        "",
        "## Date Coverage",
        "",
        f"- Earliest report date: `{stats['earliest_report_date']}`",
        f"- Latest report date: `{stats['latest_report_date']}`",
        "",
        "## Topic Counts",
        "",
    ]

    for topic, count in knowledge_base["daily_topic_counts"].items():
        lines.append(f"- `{topic}`: {count}")

    lines.extend(["", "## Source Counts", ""])
    for source, count in knowledge_base["daily_source_counts"].items():
        lines.append(f"- `{source}`: {count}")

    lines.extend(["", "## Recent Reports", ""])
    for report in recent_reports:
        lines.append(f"- `{report['date']}`: {report['total_items']} items from `{report['json_file']}`")

    lines.extend(["", "## Recent Scripts", ""])
    for package in recent_scripts:
        lines.append(f"- `{package['date']}`: {package['source_count']} sources")

    lines.extend(["", "## Transcript Inventory", ""])
    for transcript in transcripts:
        lines.append(
            f"- `{transcript['video_id']}`: {transcript.get('word_count') or 0} words from `{transcript['file']}`"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_KB_DIR.mkdir(parents=True, exist_ok=True)

    daily = build_daily_section()
    scripts = build_scripts_section()
    transcripts = build_transcripts_section()
    all_records = daily["records"] + scripts["records"] + transcripts["records"]

    report_dates = [report["date"] for report in daily["reports"] if report.get("date")]
    knowledge_base = {
        "generated_at": utc_now_iso(),
        "root": relpath(OUTPUTS_DIR),
        "stats": {
            "daily_report_count": len(daily["reports"]),
            "daily_item_count": len(daily["records"]),
            "video_script_count": len(scripts["records"]),
            "transcript_count": len(transcripts["records"]),
            "total_records": len(all_records),
            "earliest_report_date": min(report_dates) if report_dates else None,
            "latest_report_date": max(report_dates) if report_dates else None,
        },
        "daily_topic_counts": daily["topic_counts"],
        "daily_source_counts": daily["source_counts"],
        "daily_reports": daily["reports"],
        "video_scripts": scripts["packages"],
        "transcripts": transcripts["transcripts"],
        "records": all_records,
    }

    json_path = KNOWLEDGE_BASE_DIR / "knowledge_base.json"
    jsonl_path = KNOWLEDGE_BASE_DIR / "knowledge_base.jsonl"
    summary_path = DOCS_KB_DIR / "SUMMARY.md"

    json_path.write_text(json.dumps(knowledge_base, indent=2, ensure_ascii=False), encoding="utf-8")

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in all_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary_path.write_text(build_summary_markdown(knowledge_base), encoding="utf-8")

    print(f"Knowledge base written to {relpath(json_path)}")
    print(f"JSONL index written to {relpath(jsonl_path)}")
    print(f"Summary written to {relpath(summary_path)}")
    print(f"Total records: {knowledge_base['stats']['total_records']}")


if __name__ == "__main__":
    main()
