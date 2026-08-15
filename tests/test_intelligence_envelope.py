"""IntelligenceEnvelope.v1 contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.intelligence_envelope import build_envelope, compact_item
from services.source_policy import annotate_item


def test_envelope_required_fields(tmp_path):
    item = annotate_item(
        {
            "title": "FOMC statement",
            "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260815a.htm",
            "summary": "Policy update",
            "excerpt": "See also https://www.federalregister.gov/d/2026-1",
            "signal_id": "sigfed001",
            "content_hash": "abcd1234",
            "source_id": "federal_reserve_press",
            "source_tier": "T0",
            "permitted_use": "factual_support",
        },
        endpoint="https://www.federalreserve.gov/feeds/press_all.xml",
    )
    report = {"Official Records & Primary Sources": [item]}
    report_path = tmp_path / "2026-08-15.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    envelope = build_envelope(
        report=report,
        report_path=report_path,
        report_date="2026-08-15",
        started_at="2026-08-15T07:17:00Z",
        run_id="run-test-1",
    )
    assert envelope["schema"] == "intelligence_envelope.v1"
    assert envelope["producer"] == "opensourcenews"
    assert envelope["run_id"] == "run-test-1"
    assert envelope["item_count"] == 1
    assert envelope["report_hash"].startswith("sha256:")
    assert envelope["source_registry_hash"].startswith("sha256:")
    assert envelope["config_hash"].startswith("sha256:")
    assert envelope["signature"] is None
    assert envelope["items"][0]["source_tier"] == "T0"
    assert envelope["items"][0]["source_id"] == "federal_reserve_press"
    assert envelope["health"]["expected_sources"] >= 1


def test_compact_item_keeps_policy_fields():
    packed = compact_item(
        {
            "signal_id": "abc",
            "content_hash": "def",
            "source_id": "sec_press",
            "source_tier": "T1",
            "permitted_use": "factual_support",
            "canonical_url": "https://www.sec.gov/news/press-release/2026-1",
            "title": "SEC charges",
            "_topic": "Official Records & Primary Sources",
        }
    )
    assert packed["source_tier"] == "T1"
    assert packed["topics"] == ["Official Records & Primary Sources"]
