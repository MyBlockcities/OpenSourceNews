"""Regression tests for the normalized item shape consumed by Academy ingest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.news_schema import normalize_item, normalize_report


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
