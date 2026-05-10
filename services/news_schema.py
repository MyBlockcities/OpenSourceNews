"""Shared schema helpers for OpenSourceNews reports.

These helpers are intentionally dependency-light so pipelines, the Flask API,
webhook delivery, mission briefs, and MCP tools can all use the same stable IDs
without importing the API server.
"""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any, Dict, List


_WHITESPACE_RE = re.compile(r"\s+")
_TITLE_CHARS_RE = re.compile(r"[^a-z0-9]+")
_SOURCE_DOMAIN_RE = re.compile(r"https?://([^/]+)")


def normalize_title(title: str) -> str:
    """Normalize a title for deterministic story-level grouping."""
    unescaped = html.unescape(title or "").lower()
    normalized = _TITLE_CHARS_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def make_signal_id(item: Dict[str, Any]) -> str:
    """Stable item-level id based on source URL and title."""
    value = f"{item.get('url') or ''}\n{item.get('title') or ''}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def make_cluster_id(item: Dict[str, Any]) -> str:
    """Stable story-level id based on bucket and normalized headline text."""
    bucket = str(item.get("bucket") or "unknown").strip().lower() or "unknown"
    title = normalize_title(str(item.get("title") or ""))
    if not title:
        title = normalize_title(str(item.get("summary") or item.get("url") or "untitled"))
    canonical = f"{bucket}:{title}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def add_item_ids(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of an item with deterministic signal and cluster ids."""
    enriched = dict(item)
    enriched["signal_id"] = enriched.get("signal_id") or make_signal_id(enriched)
    enriched["cluster_id"] = enriched.get("cluster_id") or make_cluster_id(enriched)
    return enriched


def transcript_metadata_block(item: Dict[str, Any]) -> Dict[str, Any]:
    """Stable transcript sub-object for normalized items."""
    inner = item.get("transcript_metadata")
    inner_d: Dict[str, Any] = inner if isinstance(inner, dict) else {}
    return {
        "word_count": inner_d.get("word_count", item.get("transcript_word_count")),
        "mode": inner_d.get("mode", item.get("transcript_mode")),
        "source": inner_d.get("source", item.get("transcript_source")),
        "used_in_prompt": inner_d.get("used_in_prompt"),
    }


def normalize_item(topic_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Single normalized item with a fixed key set for external consumers."""
    item_with_ids = add_item_ids(item)

    def _list(key: str) -> List[Any]:
        value = item_with_ids.get(key)
        return value if isinstance(value, list) else []

    claims = item_with_ids.get("claims")
    normalized_claims = claims if isinstance(claims, list) else []
    source_url = item_with_ids.get("url") or ""

    return {
        "source_system": "OpenSourceNews",
        "signal_id": item_with_ids["signal_id"],
        "cluster_id": item_with_ids["cluster_id"],
        "title": item_with_ids.get("title") or "",
        "summary": item_with_ids.get("summary") or "",
        "source_urls": [source_url],
        "topics": [topic_name],
        "source": item_with_ids.get("source") or "Unknown",
        "category": item_with_ids.get("category") or "",
        "content_type": item_with_ids.get("content_type") or "",
        "bucket": item_with_ids.get("bucket") or "",
        "processing_mode": item_with_ids.get("processing_mode") or "standard_summary",
        "mode": item_with_ids.get("mode") or "",
        "stance": item_with_ids.get("stance") or "",
        "affiliation": item_with_ids.get("affiliation") or "",
        "risk_level": item_with_ids.get("risk_level") or "",
        "verification_mode": item_with_ids.get("verification_mode") or "",
        "content_warning": item_with_ids.get("content_warning") or "",
        "classification_confidence": item_with_ids.get("classification_confidence"),
        "quality_score": item_with_ids.get("quality_score"),
        "has_transcript": bool(item_with_ids.get("has_transcript")),
        "transcript_metadata": transcript_metadata_block(item_with_ids),
        "key_lessons": _list("key_lessons"),
        "actionable_steps": _list("actionable_steps"),
        "tools_mentioned": _list("tools_mentioned"),
        "frameworks_mentioned": _list("frameworks_mentioned"),
        "claims": normalized_claims,
        "entities": _list("entities"),
        "uncertainty_markers": _list("uncertainty_markers"),
        "neutral_synthesis": item_with_ids.get("neutral_synthesis") or "",
        "implementation_notes": item_with_ids.get("implementation_notes") or "",
        "difficulty": item_with_ids.get("difficulty") or "",
        "main_topic": item_with_ids.get("main_topic") or "",
        "key_insights": _list("key_insights"),
        "target_audience": item_with_ids.get("target_audience") or "",
        "unique_value": item_with_ids.get("unique_value") or "",
        "transcript_error": item_with_ids.get("transcript_error"),
    }


def normalize_report(report_date: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a raw daily report into a stable normalized schema."""
    items: List[Dict[str, Any]] = []
    sources_seen = set()
    topic_counts: Dict[str, int] = {}
    source_counts: Dict[str, int] = {}
    bucket_counts: Dict[str, int] = {}
    cluster_counts: Dict[str, int] = {}

    for topic_name, topic_items in report_data.items():
        safe_items = topic_items if isinstance(topic_items, list) else []
        topic_counts[topic_name] = len(safe_items)
        for item in safe_items:
            if not isinstance(item, dict):
                continue
            normalized = normalize_item(topic_name, item)
            src = normalized.get("source") or "Unknown"
            bucket = normalized.get("bucket") or "unknown"
            cluster_id = normalized.get("cluster_id") or "unknown"

            sources_seen.add(src)
            source_counts[src] = source_counts.get(src, 0) + 1
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
            cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
            items.append(normalized)

    total = len(items)
    digest = (
        f"{total} items across {len(topic_counts)} topics from "
        f"{len(sources_seen)} source types."
    )

    return {
        "report_date": report_date,
        "items": items,
        "sources": sorted(sources_seen),
        "counts": {
            "total": total,
            "by_topic": topic_counts,
            "by_source": source_counts,
            "by_bucket": bucket_counts,
            "by_cluster": cluster_counts,
        },
        "digest": digest,
    }


def item_search_text(topic_name: str, item: Dict[str, Any]) -> str:
    fields: List[str] = [
        topic_name,
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("category") or ""),
        str(item.get("source") or ""),
        str(item.get("content_type") or ""),
        str(item.get("bucket") or ""),
        str(item.get("mode") or ""),
        str(item.get("stance") or ""),
        str(item.get("affiliation") or ""),
        str(item.get("risk_level") or ""),
        str(item.get("verification_mode") or ""),
        str(item.get("content_warning") or ""),
        str(item.get("main_topic") or ""),
        str(item.get("neutral_synthesis") or ""),
        str(item.get("implementation_notes") or ""),
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
            fields.extend(str(entry) for entry in value)
    claims = item.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if isinstance(claim, dict):
                fields.extend(
                    str(claim.get(k) or "")
                    for k in ("claim", "evidence_cited", "analyst_note")
                )
            else:
                fields.append(str(claim))
    return " ".join(fields).lower()


def search_score(query_terms: List[str], topic_name: str, item: Dict[str, Any]) -> int:
    title = str(item.get("title") or "").lower()
    summary = str(item.get("summary") or "").lower()
    search_text = item_search_text(topic_name, item)

    score = 0
    for term in query_terms:
        if not term:
            continue
        if term in title:
            score += 10
        if term in summary:
            score += 4
        if term in search_text:
            score += 1
    phrase = " ".join(query_terms)
    if phrase and phrase in search_text:
        score += 8
    quality = item.get("quality_score")
    if isinstance(quality, (int, float)):
        score += min(int(quality), 10)
    return score


def source_domain(url: str) -> str:
    match = _SOURCE_DOMAIN_RE.match(url or "")
    return match.group(1).lower().removeprefix("www.") if match else ""


def slugify_name(value: str) -> str:
    slug = _TITLE_CHARS_RE.sub("_", (value or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "default"
