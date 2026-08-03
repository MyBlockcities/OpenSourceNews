"""Regression tests for the normalized item shape consumed by Academy ingest."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_report_manifest import build_manifest
from services.news_schema import (
    canonicalize_url,
    make_signal_id,
    normalize_item,
    normalize_report,
)


def _raw_item(**kw):
    base = {
        "title": "Open source MCP server released",
        "summary": "A new Model Context Protocol server for agent tooling.",
        "url": "https://example.com/mcp-server",
        "source": "Hacker News",
        "bucket": "ai",
    }
    base.update(kw)
    return base


def test_normalize_item_emits_url_and_source_urls():
    item = normalize_item("AI", _raw_item())
    assert item["url"] == "https://example.com/mcp-server"
    assert item["source_urls"] == ["https://example.com/mcp-server"]


def test_normalize_item_missing_url_is_empty_not_absent():
    raw = _raw_item()
    del raw["url"]
    item = normalize_item("AI", raw)
    assert item["url"] == ""
    assert item["source_urls"] == [""]


def test_normalize_report_items_carry_ingest_contract_fields():
    report = {"AI": [_raw_item()]}
    normalized = normalize_report("2026-06-12", report)
    assert normalized["items"], "expected at least one normalized item"
    it = normalized["items"][0]
    for field in ("signal_id", "title", "summary", "url", "source_urls", "source", "bucket"):
        assert field in it, f"missing contract field: {field}"
    # Additive sensor fields for Hermes — must not break v1 consumers.
    for field in (
        "canonical_url",
        "source_domain",
        "excerpt",
        "author",
        "content_hash",
        "enrichment_status",
        "fetched_at",
        "published_at",
    ):
        assert field in it, f"missing additive sensor field: {field}"


def test_canonicalize_url_strips_tracking_params():
    dirty = "https://Example.com/path/article/?utm_source=x&utm_medium=y&fbclid=1&keep=1#utm_campaign"
    clean = canonicalize_url(dirty)
    assert "utm_source" not in clean
    assert "fbclid" not in clean
    assert "keep=1" in clean
    assert clean.startswith("https://Example.com/path/article")


def test_signal_id_stable_for_clean_urls_and_collapses_tracking():
    clean = _raw_item(url="https://example.com/story")
    tracked = _raw_item(url="https://example.com/story?utm_source=rss&utm_campaign=daily")
    assert make_signal_id(clean) == make_signal_id(tracked)
    # Historical algorithm for clean URLs: sha256(url + "\\n" + title)[:16]
    legacy = hashlib.sha256(
        f"{clean['url']}\n{clean['title']}".encode("utf-8")
    ).hexdigest()[:16]
    assert make_signal_id(clean) == legacy


def test_manifest_keeps_legacy_keys_and_adds_sha256(tmp_path: Path):
    report = {
        "AI": [
            {
                "title": "Test",
                "url": "https://example.com/a",
                "source": "RSS",
                "bucket": "ai",
                "signal_id": "abc123",
                "cluster_id": "clu1",
                "enrichment_status": "pending",
            }
        ]
    }
    report_path = tmp_path / "2026-08-03.json"
    raw = json.dumps(report, indent=2).encode("utf-8")
    report_path.write_bytes(raw)

    manifest = build_manifest(report_path, workflow_run_id="99", commit_sha="deadbeef")
    for key in (
        "latest_report_date",
        "latest_report_path",
        "item_count",
        "topics",
        "bucket_counts",
        "generated_at",
    ):
        assert key in manifest
    assert manifest["schema"] == "open_source_news_manifest.v2"
    assert manifest["report_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["report_bytes"] == len(raw)
    assert manifest["enrichment_pending_count"] == 1
    assert manifest["workflow_run_id"] == "99"
    assert manifest["commit_sha"] == "deadbeef"
