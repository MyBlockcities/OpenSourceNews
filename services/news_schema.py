"""Shared schema helpers for OpenSourceNews reports.

These helpers are intentionally dependency-light so pipelines, the Flask API,
webhook delivery, mission briefs, and MCP tools can all use the same stable IDs
without importing the API server.

Compatibility note for downstream consumers (Academy / Agency digest v1):
- Existing normalized fields are preserved.
- New sensor fields are additive.
- Digest schema remains ``open_source_news_daily_digest.v1``.
- ``signal_id`` is derived from canonical_url + title when a URL is present.
  Clean URLs (no tracking params) keep the same IDs as before.
"""

from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


_WHITESPACE_RE = re.compile(r"\s+")
_TITLE_CHARS_RE = re.compile(r"[^a-z0-9]+")
_SOURCE_DOMAIN_RE = re.compile(r"https?://([^/]+)")
_TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "utm_id",
    "utm_reader",
    "utm_name",
    "utm_social",
    "utm_social-type",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "si",
    "ref",
    "ref_src",
    "ref_url",
    "source",
    "nr_email_referer",
}
_TRACKING_FRAGMENT_PREFIXES = ("utm_", "~", "!")
EXCERPT_MAX_CHARS = 1500
EXCERPT_MIN_KEEP = 500


def normalize_title(title: str) -> str:
    """Normalize a title for deterministic story-level grouping."""
    unescaped = html.unescape(title or "").lower()
    normalized = _TITLE_CHARS_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def canonicalize_url(url: str) -> str:
    """Strip common tracking params/fragments and normalize immaterial trailing slashes."""
    raw = (url or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw)
    if not parsed.scheme and not parsed.netloc:
        return raw

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY_KEYS
    ]
    query = urlencode(query_pairs, doseq=True)

    fragment = parsed.fragment or ""
    fragment_lower = fragment.lower()
    if fragment_lower.startswith(_TRACKING_FRAGMENT_PREFIXES) or fragment_lower in {
        "utm_source",
        "utm_medium",
        "utm_campaign",
    }:
        fragment = ""

    path = parsed.path or ""
    # Keep root "/" but drop immaterial trailing slashes on resource paths.
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    netloc = parsed.netloc
    # Normalize default ports; leave host casing as-is for ID stability with historical URLs.
    if netloc.endswith(":80") and parsed.scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and parsed.scheme == "https":
        netloc = netloc[:-4]

    return urlunparse(
        (
            parsed.scheme.lower() if parsed.scheme else parsed.scheme,
            netloc,
            path,
            "",
            query,
            fragment,
        )
    )


def truncate_excerpt(text: str, max_chars: int = EXCERPT_MAX_CHARS) -> str:
    """Clean HTML entities/whitespace and truncate to a short public excerpt."""
    cleaned = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    # Prefer a word boundary after the minimum keep window.
    cut = cleaned[:max_chars]
    boundary = cut.rfind(" ")
    if boundary >= EXCERPT_MIN_KEEP:
        cut = cut[:boundary]
    return cut.rstrip(" ,;:-") + "…"


def content_hash_for_item(item: Dict[str, Any]) -> str:
    """Stable content fingerprint from canonical URL, title, and excerpt/summary."""
    canonical = item.get("canonical_url") or canonicalize_url(str(item.get("url") or ""))
    title = normalize_title(str(item.get("title") or ""))
    body = truncate_excerpt(
        str(item.get("excerpt") or item.get("summary") or ""),
        max_chars=EXCERPT_MAX_CHARS,
    )
    value = f"{canonical}\n{title}\n{body}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_signal_id(item: Dict[str, Any]) -> str:
    """Stable item-level id based on canonical URL (preferred) and title.

    Clean URLs without tracking params produce the same IDs as the previous
    raw-url algorithm. Tracked URL variants collapse onto one ID.
    """
    url = item.get("canonical_url") or canonicalize_url(str(item.get("url") or "")) or str(item.get("url") or "")
    value = f"{url}\n{item.get('title') or ''}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def make_cluster_id(item: Dict[str, Any]) -> str:
    """Stable story-level id based on bucket and normalized headline text."""
    bucket = str(item.get("bucket") or "unknown").strip().lower() or "unknown"
    title = normalize_title(str(item.get("title") or ""))
    if not title:
        title = normalize_title(str(item.get("summary") or item.get("url") or "untitled"))
    canonical = f"{bucket}:{title}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def stamp_sensor_fields(
    item: Dict[str, Any],
    *,
    fetched_at: Optional[str] = None,
    enrichment_status: str = "pending",
) -> Dict[str, Any]:
    """Add collection-time sensor fields without removing existing keys."""
    enriched = dict(item)
    original_url = str(enriched.get("url") or "").strip()
    canonical = str(enriched.get("canonical_url") or "").strip() or canonicalize_url(original_url)
    if canonical:
        enriched["canonical_url"] = canonical
    elif "canonical_url" not in enriched:
        enriched["canonical_url"] = ""

    if original_url and not enriched.get("source_domain"):
        enriched["source_domain"] = source_domain(original_url)
    elif "source_domain" not in enriched:
        enriched["source_domain"] = source_domain(canonical)

    if "published_at" not in enriched:
        # Accept common fetcher aliases without inventing a timestamp.
        for alias in ("publishedAt", "pubDate", "created_at", "updated_at"):
            if enriched.get(alias):
                enriched["published_at"] = enriched.get(alias)
                break
        else:
            enriched["published_at"] = None

    if not enriched.get("fetched_at"):
        enriched["fetched_at"] = fetched_at or utc_now_iso()

    if "excerpt" not in enriched or enriched.get("excerpt") is None:
        seed = enriched.get("excerpt") or enriched.get("summary") or ""
        enriched["excerpt"] = truncate_excerpt(str(seed)) if seed else ""

    if "author" not in enriched or enriched.get("author") is None:
        for alias in ("channelTitle", "creator", "byline"):
            if enriched.get(alias):
                enriched["author"] = str(enriched.get(alias) or "")
                break
        else:
            enriched["author"] = str(enriched.get("author") or "")

    enriched["enrichment_status"] = enriched.get("enrichment_status") or enrichment_status
    enriched["content_hash"] = enriched.get("content_hash") or content_hash_for_item(enriched)
    return enriched


def add_item_ids(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of an item with deterministic signal and cluster ids."""
    enriched = stamp_sensor_fields(item)
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
    canonical_url = item_with_ids.get("canonical_url") or canonicalize_url(source_url)

    return {
        "source_system": "OpenSourceNews",
        "signal_id": item_with_ids["signal_id"],
        "cluster_id": item_with_ids["cluster_id"],
        "title": item_with_ids.get("title") or "",
        "summary": item_with_ids.get("summary") or "",
        "url": source_url,
        "canonical_url": canonical_url,
        "source_urls": [source_url] if source_url else ([canonical_url] if canonical_url else [""]),
        "source_domain": item_with_ids.get("source_domain") or source_domain(source_url or canonical_url),
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
        "source_category": item_with_ids.get("source_category") or "",
        "trust_layer": item_with_ids.get("trust_layer") or "",
        "trust_level": item_with_ids.get("trust_level") or "",
        "evidence_level": item_with_ids.get("evidence_level") or "",
        "regulatory_sensitivity": item_with_ids.get("regulatory_sensitivity") or "",
        "content_use": item_with_ids.get("content_use") or "",
        "safe_framing": item_with_ids.get("safe_framing") or "",
        "medical_claim_policy": item_with_ids.get("medical_claim_policy") or "",
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
        # Additive sensor fields for Hermes / collection-first consumers.
        "published_at": item_with_ids.get("published_at"),
        "fetched_at": item_with_ids.get("fetched_at") or "",
        "excerpt": item_with_ids.get("excerpt") or "",
        "author": item_with_ids.get("author") or "",
        "content_hash": item_with_ids.get("content_hash") or "",
        "enrichment_status": item_with_ids.get("enrichment_status") or "pending",
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
        str(item.get("excerpt") or ""),
        str(item.get("author") or ""),
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
        str(item.get("source_category") or ""),
        str(item.get("trust_layer") or ""),
        str(item.get("trust_level") or ""),
        str(item.get("evidence_level") or ""),
        str(item.get("regulatory_sensitivity") or ""),
        str(item.get("content_use") or ""),
        str(item.get("safe_framing") or ""),
        str(item.get("medical_claim_policy") or ""),
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
    summary = str(item.get("summary") or "").strip().lower()
    excerpt = str(item.get("excerpt") or "").strip().lower()
    search_text = item_search_text(topic_name, item)

    score = 0
    for term in query_terms:
        if not term:
            continue
        if term in title:
            score += 10
        if term in summary:
            score += 4
        if term in excerpt:
            score += 3
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
